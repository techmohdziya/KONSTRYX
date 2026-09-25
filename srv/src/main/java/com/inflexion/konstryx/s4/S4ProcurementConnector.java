package com.inflexion.konstryx.s4;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sap.cds.Row;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.services.persistence.PersistenceService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Reads the procurement documents S/4 owns into the KONSTRYX mirrors.
 *
 * The split is the one the site map draws: KONSTRYX decides what to buy and
 * pushes a requisition; from the moment S/4 accepts it, S/4 is the author of
 * everything that follows. The order, the receipt and the service entry sheet
 * are read back, never written here.
 *
 *   purchase order         API_PURCHASEORDER_2 (A2X, V4)      SAP_COM_0053
 *   goods receipt          API_MATERIAL_DOCUMENT_SRV          SAP_COM_0107
 *   service entry sheet    API_SERVICE_ENTRY_SHEET_SRV        SAP_COM_0237
 *
 * A service entry sheet is the receipt of work that arrives on no lorry -
 * plant hire, scaffolding, a design package - and it is read for the same
 * reason a goods receipt is: it is the document that releases commitment and
 * the middle leg of the three-way match. A rental billed monthly posts one a
 * month against the same order, so they are keyed on their own number rather
 * than on the order.
 *
 * Only what the site has a stake in. A tenant's S/4 holds orders for every
 * plant and company code it runs; this reads the ones whose purchasing
 * document carries a project the mirror already knows, because an order
 * against a project KONSTRYX has never heard of is not this system's business
 * and mirroring it would put rows on screens that can never be reconciled.
 *
 * Read-only in the mirror, so a row that exists is updated in place rather
 * than skipped. S/4 is the author; a local edit is not something to preserve.
 */
@Component
public class S4ProcurementConnector {

    private static final Logger log = LoggerFactory.getLogger(S4ProcurementConnector.class);

    private static final String E_PO = "konstryx.mat.PurchaseOrder";
    private static final String E_PO_LINE = "konstryx.mat.PurchaseOrderLine";
    private static final String E_GR = "konstryx.mat.GoodsReceipt";
    private static final String E_SES = "konstryx.mat.ServiceEntrySheet";
    private static final String E_PROJECT = "konstryx.prj.Project";
    private static final String E_VENDOR = "konstryx.master.Vendor";
    private static final String E_COMPANY = "konstryx.admin.Company";

    /**
     * The purchase order service, as this tenant exposes it.
     *
     * API_PURCHASEORDER_2 on the A2X protocol, which is OData V4 and lives
     * under /sap/opu/odata4 rather than /sap/opu/odata. The older
     * API_PURCHASEORDER_PROCESS_SRV is V2 and is what the requirements named;
     * the tenant publishes the V4 one, and a connector pointed at a path the
     * tenant does not publish fails in a way that reads like a credential
     * problem. Repointable through S4SyncConfig for a tenant on the other one.
     */
    static final String PO_SRV =
            "/sap/opu/odata4/sap/api_purchaseorder_2/srvd_a2x/sap/purchaseorder/0001";
    static final String GR_SRV = "/sap/opu/odata/sap/API_MATERIAL_DOCUMENT_SRV";
    static final String SES_SRV = "/sap/opu/odata/sap/API_SERVICE_ENTRY_SHEET_SRV";

    private static final int PAGE = 200;
    private static final int SAFETY_LIMIT = 50_000;

    private final ObjectMapper mapper = new ObjectMapper();

    @Autowired
    private S4Connection connection;

    @Autowired
    private PersistenceService db;

    public boolean isConfigured() {
        return connection.isConfigured();
    }

    public String sync() {
        if (!connection.isConfigured()) {
            return "No S/4 connection is configured. The ITS_S4 destination must "
                    + "resolve before purchase orders, receipts or service entry "
                    + "sheets can be read.";
        }
        StringBuilder report = new StringBuilder("Read from ")
                .append(connection.host())
                .append(connection.usesDestination()
                        ? " via the ITS_S4 destination" : " via local configuration")
                .append(".\n\n");

        // Orders first. A receipt or an entry sheet that cannot find its order
        // has nothing to price itself against, so the order has to be there
        // before either of them is read.
        report.append("  ").append(safely("purchase orders", this::syncOrders)).append('\n');
        report.append("  ").append(safely("goods receipts", this::syncReceipts)).append('\n');
        report.append("  ").append(safely("service entry sheets", this::syncEntrySheets))
              .append('\n');
        return report.toString();
    }

    private interface Step {
        String run() throws Exception;
    }

    /**
     * One feed's failure is its own. A tenant with no service entry sheet
     * scenario activated should still get its orders, and the report should
     * say which leg was missing rather than answering with one exception.
     */
    private String safely(String what, Step step) {
        try {
            return step.run();
        } catch (Exception e) {
            log.warn("Procurement sync failed for {}: {}", what, e.toString());
            return what + ": failed (" + e.getClass().getSimpleName() + ")";
        }
    }

    // ------------------------------------------------------------ the orders

    private String syncOrders() throws Exception {
        Map<String, String> projects = byCode(E_PROJECT, "code");
        Map<String, String> vendors = byCode(E_VENDOR, "vendorCode");
        Map<String, String> companies = byCode(E_COMPANY, "code");

        int read = 0, created = 0, updated = 0, skipped = 0, lines = 0;

        for (int skip = 0; skip < SAFETY_LIMIT; skip += PAGE) {
            String url = PO_SRV + "/PurchaseOrder?%24top=" + PAGE
                    + "&%24skip=" + skip
                    + "&%24select=PurchaseOrder,Supplier,CompanyCode,PurchaseOrderDate,"
                    + "PurchasingDocumentDeletionCode,PurchaseOrderNetAmount,DocumentCurrency";
            S4Connection.S4Response response = connection.get(url);
            if (response.status != 200) {
                return "purchase orders: not available (" + response.status + ")";
            }
            List<JsonNode> page = rowsOf(response.body);
            if (page.isEmpty()) {
                break;
            }
            for (JsonNode po : page) {
                String poNo = text(po, "PurchaseOrder");
                if (poNo == null) {
                    continue;
                }
                read++;

                List<JsonNode> itemRows = items(poNo);
                String projectId = projectOf(itemRows, projects);
                if (projectId == null) {
                    // Not a project this system runs. Counted, and left alone.
                    skipped++;
                    continue;
                }

                Map<String, Object> data = new HashMap<>();
                data.put("poNo", poNo);
                data.put("project_ID", projectId);
                data.put("company_ID", companies.get(text(po, "CompanyCode")));
                data.put("vendor_ID", vendors.get(text(po, "Supplier")));
                data.put("orderedOn", date(text(po, "PurchaseOrderDate")));
                data.put("netValue", decimal(text(po, "PurchaseOrderNetAmount")));
                // A deletion code is S/4 saying the order is struck out. It
                // stays in the mirror, because a commitment that disappears
                // without trace is how a cost report stops reconciling.
                data.put("status", isBlank(text(po, "PurchasingDocumentDeletionCode"))
                        ? "Open" : "Cancelled");

                String poId = upsert(E_PO, "poNo", poNo, data);
                if (poId.startsWith("new:")) {
                    created++;
                } else {
                    updated++;
                }
                lines += syncOrderLines(poId.substring(4), poNo, itemRows, projects);
            }
            if (page.size() < PAGE) {
                break;
            }
        }
        return "purchase orders <- PurchaseOrder: " + read + " read, " + created
                + " new, " + updated + " updated, " + lines + " line(s)"
                + (skipped > 0 ? ", " + skipped + " for projects this system does not run" : "");
    }

    private List<JsonNode> items(String poNo) throws Exception {
        String url = PO_SRV + "/PurchaseOrderItem?%24top=" + PAGE
                + "&%24filter=PurchaseOrder%20eq%20'" + poNo + "'"
                + "&%24select=PurchaseOrder,PurchaseOrderItem,Material,PurchaseOrderItemText,"
                + "OrderQuantity,PurchaseOrderQuantityUnit,NetPriceAmount,NetAmount,"
                + "WBSElement,ScheduleLineDeliveryDate";
        S4Connection.S4Response response = connection.get(url);
        return response.status == 200 ? rowsOf(response.body) : List.of();
    }

    /**
     * Which project an order belongs to, taken from the account assignment on
     * its items rather than from the header, because the header has none. An
     * order whose items point at several projects is mirrored against the
     * first one found and the rest are visible on the lines.
     */
    private String projectOf(List<JsonNode> itemRows, Map<String, String> projects) {
        for (JsonNode item : itemRows) {
            String wbs = text(item, "WBSElement");
            if (wbs == null) {
                // The V2 service spells it WBSElementInternalID. Both are read
                // so that repointing the feed at the older service through
                // S4SyncConfig does not silently stop finding the project.
                wbs = text(item, "WBSElementInternalID");
            }
            if (wbs == null) {
                continue;
            }
            // A WBS id in S/4 carries the project code as its leading segment,
            // which is how a project raised from here is recognised coming back.
            for (Map.Entry<String, String> entry : projects.entrySet()) {
                if (wbs.startsWith(entry.getKey())) {
                    return entry.getValue();
                }
            }
        }
        return null;
    }

    private int syncOrderLines(String poId, String poNo, List<JsonNode> itemRows,
                               Map<String, String> projects) {
        int n = 0;
        for (JsonNode item : itemRows) {
            String itemNo = text(item, "PurchaseOrderItem");
            if (itemNo == null) {
                continue;
            }
            Map<String, Object> data = new HashMap<>();
            data.put("parent_ID", poId);
            data.put("lineNo", integer(itemNo));
            data.put("description", text(item, "PurchaseOrderItemText"));
            data.put("qty", decimal(text(item, "OrderQuantity")));
            data.put("netValue", decimal(text(item, "NetAmount")));
            data.put("eta", date(text(item, "ScheduleLineDeliveryDate")));
            upsertLine(E_PO_LINE, poId, integer(itemNo), data, poNo + "/" + itemNo);
            n++;
        }
        return n;
    }

    // ---------------------------------------------------------- the receipts

    /**
     * Goods receipts, read as material documents of the movement types that
     * receive against an order.
     *
     * 101 is the receipt and 102 is its reversal. Both are read: a receipt
     * that was reversed and a receipt that never happened are different facts,
     * and a mirror holding only the first would accrue cost twice.
     */
    private String syncReceipts() throws Exception {
        Map<String, String> orders = byCode(E_PO, "poNo");
        int read = 0, created = 0, updated = 0, skipped = 0;

        for (int skip = 0; skip < SAFETY_LIMIT; skip += PAGE) {
            String url = GR_SRV + "/A_MaterialDocumentItem?%24format=json&%24top=" + PAGE
                    + "&%24skip=" + skip
                    + "&%24filter=GoodsMovementType%20eq%20'101'%20or%20GoodsMovementType%20eq%20'102'"
                    + "&%24select=MaterialDocument,MaterialDocumentItem,MaterialDocumentYear,"
                    + "PurchaseOrder,PurchaseOrderItem,QuantityInEntryUnit,GoodsMovementType,"
                    + "PostingDate,TotalGoodsMvtAmtInCCCrcy";
            S4Connection.S4Response response = connection.get(url);
            if (response.status != 200) {
                return "goods receipts: not available (" + response.status + ")";
            }
            List<JsonNode> page = rowsOf(response.body);
            if (page.isEmpty()) {
                break;
            }
            for (JsonNode row : page) {
                String poNo = text(row, "PurchaseOrder");
                String poId = poNo == null ? null : orders.get(poNo);
                if (poId == null) {
                    skipped++;
                    continue;
                }
                read++;
                String doc = text(row, "MaterialDocument");
                String itemNo = text(row, "MaterialDocumentItem");
                String key = doc + "/" + itemNo;

                BigDecimal qty = decimal(text(row, "QuantityInEntryUnit"));
                BigDecimal value = decimal(text(row, "TotalGoodsMvtAmtInCCCrcy"));
                boolean reversal = "102".equals(text(row, "GoodsMovementType"));

                Map<String, Object> data = new HashMap<>();
                data.put("grDoc", doc);
                data.put("po_ID", poId);
                data.put("poLineNo", integer(text(row, "PurchaseOrderItem")));
                data.put("poLine_ID", lineOf(poId, integer(text(row, "PurchaseOrderItem"))));
                data.put("grQty", reversal ? negate(qty) : qty);
                data.put("grValue", reversal ? negate(value) : value);
                data.put("datePosted", date(text(row, "PostingDate")));

                if (upsert(E_GR, "s4Key", key, data).startsWith("new:")) {
                    created++;
                } else {
                    updated++;
                }
            }
            if (page.size() < PAGE) {
                break;
            }
        }
        return "goods receipts <- A_MaterialDocumentItem: " + read + " read, " + created
                + " new, " + updated + " updated"
                + (skipped > 0 ? ", " + skipped + " against orders not mirrored here" : "");
    }

    // ----------------------------------------------------- the entry sheets

    private String syncEntrySheets() throws Exception {
        Map<String, String> orders = byCode(E_PO, "poNo");
        int read = 0, created = 0, updated = 0, skipped = 0;

        for (int skip = 0; skip < SAFETY_LIMIT; skip += PAGE) {
            String url = SES_SRV + "/A_ServiceEntrySheetItem?%24format=json&%24top=" + PAGE
                    + "&%24skip=" + skip
                    + "&%24select=ServiceEntrySheet,ServiceEntrySheetItem,PurchaseOrder,"
                    + "PurchaseOrderItem,ServiceEntrySheetItemDesc,ConfirmedQuantity,"
                    + "QuantityUnit,NetAmount,Currency,ServicePerformanceDate,"
                    + "ServicePerformanceEndDate,AccountAssignmentStatus";
            S4Connection.S4Response response = connection.get(url);
            if (response.status != 200) {
                return "service entry sheets: not available (" + response.status + ")";
            }
            List<JsonNode> page = rowsOf(response.body);
            if (page.isEmpty()) {
                break;
            }
            for (JsonNode row : page) {
                String poNo = text(row, "PurchaseOrder");
                String poId = poNo == null ? null : orders.get(poNo);
                if (poId == null) {
                    skipped++;
                    continue;
                }
                read++;
                String sheet = text(row, "ServiceEntrySheet");
                String itemNo = text(row, "ServiceEntrySheetItem");
                String key = sheet + "/" + itemNo;

                Map<String, Object> data = new HashMap<>();
                data.put("sesNo", sheet);
                data.put("po_ID", poId);
                data.put("poLineNo", integer(text(row, "PurchaseOrderItem")));
                data.put("poLine_ID", lineOf(poId, integer(text(row, "PurchaseOrderItem"))));
                data.put("description", text(row, "ServiceEntrySheetItemDesc"));
                data.put("qty", decimal(text(row, "ConfirmedQuantity")));
                data.put("uom", text(row, "QuantityUnit"));
                data.put("netValue", decimal(text(row, "NetAmount")));
                data.put("ccy_code", text(row, "Currency"));
                data.put("periodFrom", date(text(row, "ServicePerformanceDate")));
                data.put("periodTo", date(text(row, "ServicePerformanceEndDate")));
                data.put("status", text(row, "AccountAssignmentStatus"));

                if (upsert(E_SES, "s4Key", key, data).startsWith("new:")) {
                    created++;
                } else {
                    updated++;
                }
            }
            if (page.size() < PAGE) {
                break;
            }
        }
        return "service entry sheets <- A_ServiceEntrySheetItem: " + read + " read, "
                + created + " new, " + updated + " updated"
                + (skipped > 0 ? ", " + skipped + " against orders not mirrored here" : "");
    }

    // ---------------------------------------------------------------- helpers

    /** An index of the mirror by whatever code S/4 knows it as. */
    private Map<String, String> byCode(String entity, String field) {
        Map<String, String> index = new HashMap<>();
        for (Row row : db.run(Select.from(entity))) {
            String code = str(row.get(field));
            if (code != null) {
                index.put(code, str(row.get("ID")));
            }
        }
        return index;
    }

    private String lineOf(String poId, Integer lineNo) {
        if (lineNo == null) {
            return null;
        }
        return db.run(Select.from(E_PO_LINE)
                .where(l -> l.get("parent_ID").eq(poId).and(l.get("lineNo").eq(lineNo))))
                .first().map(r -> str(r.get("ID"))).orElse(null);
    }

    /** Inserts or updates one mirror row. Answers "new:<id>" or "old:<id>". */
    private String upsert(String entity, String keyField, String keyValue,
                          Map<String, Object> data) {
        data.put("s4Key", keyValue);
        data.put("s4System", systemId());
        data.put("lastSyncedAt", Instant.now());
        data.put("syncStatus", "OK");

        Row existing = db.run(Select.from(entity)
                .where(e -> e.get(keyField).eq(keyValue))).first().orElse(null);
        if (existing == null) {
            String id = UUID.randomUUID().toString();
            data.put("ID", id);
            db.run(Insert.into(entity).entry(data));
            return "new:" + id;
        }
        String id = str(existing.get("ID"));
        db.run(Update.entity(entity).data(data).where(e -> e.get("ID").eq(id)));
        return "old:" + id;
    }

    /** An order line is identified by its order and its number, not by a code. */
    private void upsertLine(String entity, String poId, Integer lineNo,
                            Map<String, Object> data, String s4Key) {
        data.put("s4Key", s4Key);
        data.put("s4System", systemId());
        data.put("lastSyncedAt", Instant.now());
        data.put("syncStatus", "OK");

        Row existing = lineNo == null ? null : db.run(Select.from(entity)
                .where(l -> l.get("parent_ID").eq(poId).and(l.get("lineNo").eq(lineNo))))
                .first().orElse(null);
        if (existing == null) {
            data.put("ID", UUID.randomUUID().toString());
            db.run(Insert.into(entity).entry(data));
            return;
        }
        String id = str(existing.get("ID"));
        db.run(Update.entity(entity).data(data).where(l -> l.get("ID").eq(id)));
    }

    private List<JsonNode> rowsOf(String body) throws Exception {
        JsonNode root = mapper.readTree(body);
        JsonNode v4 = root.path("value");
        JsonNode array = v4.isArray() ? v4 : root.path("d").path("results");
        List<JsonNode> rows = new ArrayList<>();
        if (array.isArray()) {
            array.forEach(rows::add);
        }
        return rows;
    }

    private static String text(JsonNode row, String field) {
        String value = row.path(field).asText(null);
        return isBlank(value) ? null : value.trim();
    }

    private static BigDecimal decimal(String v) {
        if (isBlank(v)) {
            return null;
        }
        try {
            return new BigDecimal(v);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static BigDecimal negate(BigDecimal v) {
        return v == null ? null : v.negate();
    }

    private static Integer integer(String v) {
        if (isBlank(v)) {
            return null;
        }
        try {
            return Integer.valueOf(v.trim());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /**
     * A date as S/4 gives it: ISO in V4, and the OData V2 epoch form in older
     * services. Both are accepted rather than assuming which version a tenant
     * activated.
     */
    private static LocalDate date(String v) {
        if (isBlank(v)) {
            return null;
        }
        String s = v.trim();
        if (s.startsWith("/Date(")) {
            try {
                String millis = s.substring(6, s.indexOf(')')).split("[+-]")[0];
                return Instant.ofEpochMilli(Long.parseLong(millis))
                        .atZone(java.time.ZoneOffset.UTC).toLocalDate();
            } catch (RuntimeException e) {
                return null;
            }
        }
        try {
            return LocalDate.parse(s.length() > 10 ? s.substring(0, 10) : s);
        } catch (RuntimeException e) {
            return null;
        }
    }

    private String systemId() {
        String host = connection.host();
        if (isBlank(host)) {
            return "S4";
        }
        String h = host.replaceFirst("^https?://", "");
        int dot = h.indexOf('.');
        return dot > 0 ? h.substring(0, dot) : h;
    }

    private static boolean isBlank(String s) {
        return s == null || s.isBlank();
    }

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }
}
