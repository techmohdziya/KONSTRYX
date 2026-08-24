package com.inflexion.konstryx.s4;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.persistence.PersistenceService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Pushes a KONSTRYX-raised purchase requisition to S/4.
 *
 * This is the outbound half of D-21: KONSTRYX decides WHAT to buy from a
 * resource request's PROCURE lines, S/4 owns the requisition from the moment
 * it accepts one. The number that comes back is S/4's, and recording it is
 * ProcurementHandler's job through recordRequisitionResult — the same entry
 * point a manual correction uses, so both paths write identical state. This
 * class returns an outcome and writes nothing, exactly as S4ProjectConnector
 * does for projects.
 *
 * **API and scenario: `API_PURCHASEREQUISITION_2` under `SAP_COM_0102`**, per
 * the consolidated requirements §15.2 row 9 and RB-145. An earlier revision of
 * this class targeted `API_PURCHASEREQ_PROCESS_SRV` under `SAP_COM_0053`; both
 * halves of that were wrong. SAP_COM_0053 is the PURCHASE ORDER scenario — the
 * requirements attach it to `API_PURCHASEORDER_PROCESS_SRV` every time it
 * appears and never to a requisition.
 *
 * The whole document goes in one deep insert: header, its items, and each
 * item's account assignment. That is not a style choice — an item posted
 * separately would be a requisition of its own, and a requisition posted
 * without its account assignment would commit against nothing, which is the
 * very thing the WBS/CBS on the line exists to prevent.
 *
 * **Unverified, and deliberately kept easy to correct.** SAP_COM_0102 is not
 * activated on the tenant, so nothing here has met a live S/4: not the service
 * path, not the property names, not the org defaults. `API_PURCHASEREQUISITION_2`
 * is the V4-generation API, so this builds a V4 payload — ISO dates rather than
 * V2's `/Date(millis)/`, navigation properties rather than `to_` sets, and a
 * response read from the top level rather than from a `d` wrapper. Every one of
 * those is an informed assumption. **Read the tenant's own `$metadata` before
 * trusting this**, and override the path with `S4_PR_SERVICE` rather than
 * editing source. Contrast the project connector, whose defaults were read off
 * the tenant's own projects and are therefore known good.
 */
@Component
public class S4RequisitionConnector {

    private static final Logger log = LoggerFactory.getLogger(S4RequisitionConnector.class);

    /**
     * The V4 service root. Overridable because the exact path is the single
     * most likely thing to be wrong until a Communication Arrangement exists.
     */
    private static final String DEFAULT_SERVICE =
            "/sap/opu/odata4/sap/api_purchaserequisition_2/srvd_a2x/sap/purchaserequisition/0001";
    private static final String E_PR_LINE = "konstryx.mat.PurchaseRequisitionLine";
    private static final String E_WBS = "konstryx.prj.WBSElement";
    private static final String E_MATERIAL = "konstryx.master.Material";

    private final ObjectMapper mapper = new ObjectMapper();

    @Autowired
    private S4Connection connection;

    @Autowired
    private PersistenceService db;

    public boolean isConfigured() {
        return connection.isConfigured();
    }

    public static final class SyncOutcome {
        public final boolean success;
        public final String prNo;
        public final String s4System;
        public final String message;

        SyncOutcome(boolean success, String prNo, String s4System, String message) {
            this.success = success;
            this.prNo = prNo;
            this.s4System = s4System;
            this.message = message;
        }
    }

    /**
     * Why this requisition cannot be sent, or null if it can — asked and
     * answered before any connection is opened, because "this line names no
     * material" is a KONSTRYX fact about the document, not something S/4 has
     * to be contacted to discover. Reported one line at a time and by line
     * number, because that is how the buyer fixes them.
     */
    public String blocker(Row requisition) {
        List<Row> lines = linesOf(str(requisition.get("ID")));
        if (lines.isEmpty()) {
            return "The requisition has no lines, so there is nothing to order.";
        }
        for (Row line : lines) {
            int no = intOf(line.get("lineNo"));
            if (materialCode(line) == null) {
                return "Line " + no + " has nothing registered in S/4 to order "
                        + "against. Map its resource — a material if it is bought, "
                        + "a service product if it is hired or subcontracted — then "
                        + "raise the requisition again.";
            }
            if (wbsKey(line) == null) {
                return "Line " + no + "'s WBS element is not in S/4 yet, so the "
                        + "requisition would commit against nothing. Sync the "
                        + "project first.";
            }
        }
        return null;
    }

    public SyncOutcome push(Row requisition) {
        String prId = str(requisition.get("ID"));
        try {
            // Checked by the caller too. Repeated here so the connector cannot
            // be made to send an unorderable document by a future caller that
            // forgets — the cost is one query, the alternative is a real order.
            String blocked = blocker(requisition);
            if (blocked != null) {
                return new SyncOutcome(false, null, null, blocked);
            }
            List<Row> lines = linesOf(prId);

            ObjectNode header = mapper.createObjectNode();
            header.put("PurchaseRequisitionType", envOr("S4_PR_TYPE", "NB"));

            ArrayNode items = header.putArray("_PurchaseRequisitionItem");
            for (Row line : lines) {
                ObjectNode item = mapper.createObjectNode();
                // S/4 numbers requisition items in tens, and its own UI relies
                // on that spacing when an item is inserted later.
                item.put("PurchaseRequisitionItem",
                        String.format("%05d", intOf(line.get("lineNo")) * 10));
                item.put("Material", materialCode(line));
                item.put("PurchaseRequisitionItemText", trim(str(line.get("description")), 40));
                item.put("RequestedQuantity", plain(line.get("qtyProcure")));
                item.put("BaseUnit", uom(line));
                item.put("Plant", envOr("S4_PLANT", "1010"));
                item.put("PurchasingOrganization", envOr("S4_PURCH_ORG", "1010"));
                item.put("PurchasingGroup", envOr("S4_PURCH_GROUP", "001"));
                // 'P' — account assignment to a project. Without it S/4 books
                // the requisition to stock and the WBS below is ignored.
                item.put("AccountAssignmentCategory", "P");
                putDate(item, "DeliveryDate", line.get("needBy"));
                BigDecimal price = dec(line.get("estUnitPrice"));
                if (price != null) {
                    item.put("PurchaseRequisitionPrice", price.toPlainString());
                }

                ArrayNode accounts = item.putArray("_PurReqnAcctAssgmt");
                ObjectNode account = accounts.addObject();
                account.put("PurchaseRequisitionItem",
                        item.get("PurchaseRequisitionItem").asText());
                account.put("PurReqnAcctAssgmtNumber", "01");
                account.put("WBSElementExternalID", wbsKey(line));
            }

            String service = envOr("S4_PR_SERVICE", DEFAULT_SERVICE);
            S4Connection.S4Response response = connection.post(
                    service + "/PurchaseRequisition?%24top=1",
                    service + "/PurchaseRequisition",
                    mapper.writeValueAsString(header));

            if (response.status != 201) {
                return new SyncOutcome(false, null, null,
                        "S/4 refused the requisition (" + response.status + "): "
                                + errorText(response.body));
            }
            // V4 returns the created entity at the top level; V2 wrapped it in
            // "d". Read the top level and fall back, so a tenant that turns out
            // to expose the V2 service still resolves its number rather than
            // reporting a successful push it cannot name.
            JsonNode body = mapper.readTree(response.body);
            JsonNode created = body.has("PurchaseRequisition") ? body : body.path("d");
            String prNo = created.path("PurchaseRequisition").asText(null);
            if (prNo == null || prNo.isBlank()) {
                // Accepted but unnumbered is worse than refused: something
                // exists in S/4 that we cannot name, and re-pushing would
                // duplicate it. Say so rather than record a blank number.
                return new SyncOutcome(false, null, null,
                        "S/4 accepted the requisition but returned no number. "
                                + "Check the buyer's worklist before re-sending — "
                                + "a second push would order the same scope twice.");
            }
            return new SyncOutcome(true, prNo, systemId(),
                    "Created in S/4 as requisition " + prNo + " with "
                            + items.size() + " item(s).");

        } catch (Exception e) {
            log.warn("S/4 requisition push failed for {}: {}", prId, e.toString());
            return new SyncOutcome(false, null, null, "Push failed: " + e.getMessage());
        }
    }

    // ----------------------------------------------------------------- helpers

    /** A requisition's lines in the order S/4 will number them. */
    private List<Row> linesOf(String prId) {
        List<Row> lines = new ArrayList<>();
        for (Row line : db.run(Select.from(E_PR_LINE)
                .where(l -> l.get("parent_ID").eq(prId)))) {
            lines.add(line);
        }
        lines.sort((a, b) -> intOf(a.get("lineNo")) - intOf(b.get("lineNo")));
        return lines;
    }

    /** The S/4 material number behind a line's material reference. */
    private String materialCode(Row line) {
        Object materialId = line.get("material_ID");
        if (materialId == null) {
            return null;
        }
        String id = String.valueOf(materialId);
        return db.run(Select.from(E_MATERIAL).where(m -> m.get("ID").eq(id)))
                .first().map(m -> blankToNull(str(m.get("materialCode")))).orElse(null);
    }

    /**
     * The WBS element as S/4 knows it — its recorded s4Key, never the KONSTRYX
     * code re-normalised. An element that was never pushed has no key, and that
     * is a blocker rather than something to guess at.
     */
    private String wbsKey(Row line) {
        Object wbsId = line.get("wbs_ID");
        if (wbsId == null) {
            return null;
        }
        String id = String.valueOf(wbsId);
        Optional<Row> wbs = db.run(Select.from(E_WBS).where(w -> w.get("ID").eq(id))).first();
        return wbs.map(w -> blankToNull(str(w.get("s4Key")))).orElse(null);
    }

    /** The line's unit, upper-cased the way S/4 keys units of measure. */
    private static String uom(Row line) {
        String uom = str(line.get("uom"));
        return uom == null ? "EA" : uom.toUpperCase();
    }

    private String systemId() {
        String host = connection.host();
        if (host == null || host.isBlank()) {
            return "S4";
        }
        String h = host.replaceFirst("^https?://", "");
        int dot = h.indexOf('.');
        return dot > 0 ? h.substring(0, dot) : h;
    }

    /**
     * V4 serialises Edm.Date as a plain ISO day. V2's /Date(epoch-millis)/ is
     * not accepted here — it was the shape the previous, wrongly-targeted
     * revision of this class sent.
     */
    private static void putDate(ObjectNode node, String field, Object value) {
        if (value == null) {
            return;
        }
        try {
            LocalDate date = value instanceof LocalDate d
                    ? d : LocalDate.parse(String.valueOf(value).substring(0, 10));
            node.put(field, date.toString());
        } catch (RuntimeException ignored) { }
    }

    /** V4 puts the message directly on error.message; V2 nested it under .value. */
    private String errorText(String body) {
        try {
            JsonNode message = mapper.readTree(body).path("error").path("message");
            if (message.isTextual()) {
                return message.asText();
            }
            JsonNode nested = message.path("value");
            if (!nested.isMissingNode()) {
                return nested.asText();
            }
        } catch (Exception ignored) { }
        return body == null ? "?" : body.substring(0, Math.min(200, body.length()));
    }

    /** S/4 serialises Edm.Decimal as a string; a bare number loses scale. */
    private static String plain(Object value) {
        BigDecimal d = dec(value);
        return d == null ? "0" : d.toPlainString();
    }

    private static BigDecimal dec(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof BigDecimal d) {
            return d;
        }
        try {
            return new BigDecimal(String.valueOf(value));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static String trim(String value, int max) {
        if (value == null) {
            return "";
        }
        return value.length() <= max ? value : value.substring(0, max);
    }

    private static String envOr(String key, String fallback) {
        String value = System.getenv(key);
        return value == null || value.isBlank() ? fallback : value;
    }

    private static int intOf(Object v) {
        return v instanceof Number n ? n.intValue() : 0;
    }

    private static String blankToNull(String v) {
        return v == null || v.isBlank() ? null : v;
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }
}
