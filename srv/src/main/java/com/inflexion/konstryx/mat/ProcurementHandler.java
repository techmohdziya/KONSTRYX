package com.inflexion.konstryx.mat;

import com.sap.cds.Row;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * The S/4 side of procurement, both directions.
 *
 * The split follows the ownership table in INTEGRATION.md, and the two halves
 * are deliberately not symmetric. The requisition is raised in KONSTRYX and
 * sent out, so it takes its NUMBER back from S/4 — recordRequisitionResult is
 * that return leg. The purchase order is raised in S/4 entirely; KONSTRYX
 * never creates one, so recordPurchaseOrder is a mirror, not a create.
 *
 * Neither action talks to S/4 itself. They are the entry points a connector
 * calls with an outcome, which is also what makes them testable without a
 * tenant — the same reason ProjectService.recordSyncResult exists alongside
 * the live syncToS4 push.
 */
@Component
@ServiceName("MaterialService")
public class ProcurementHandler implements EventHandler {

    private static final String E_PR = "konstryx.mat.PurchaseRequisition";
    private static final String E_PR_LINE = "konstryx.mat.PurchaseRequisitionLine";
    private static final String E_PO = "konstryx.mat.PurchaseOrder";
    private static final String E_PO_LINE = "konstryx.mat.PurchaseOrderLine";
    private static final String E_VENDOR = "konstryx.master.Vendor";

    @Autowired
    private PersistenceService db;

    // ------------------------------------------------- requisition, return leg

    @On(event = "recordRequisitionResult", entity = "MaterialService.PurchaseRequisitions")
    public void onRequisitionResult(EventContext context) {
        Row pr = targetOf(context, "Requisition not found.");
        String prId = str(pr.get("ID"));
        boolean success = Boolean.TRUE.equals(context.get("success"));
        String prNo = str(context.get("prNo"));
        String message = str(context.get("message"));

        if (success && isBlank(prNo)) {
            // Accepting without a number would leave the requisition looking
            // sent while still being unidentifiable in S/4.
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "S/4 accepted the requisition but returned no number. "
                            + "Nothing to record — the requisition stays unsent.");
        }

        Map<String, Object> patch = new HashMap<>();
        patch.put("syncStatus", success ? "SENT" : "FAILED");
        patch.put("lastSyncedAt", Instant.now());
        patch.put("syncMessage", message);
        patch.put("syncAttempts", intOf(pr.get("syncAttempts")) == null
                ? 1 : intOf(pr.get("syncAttempts")) + 1);
        if (success) {
            patch.put("prNo", prNo);
            patch.put("s4Key", prNo);
            patch.put("s4System", str(context.get("s4System")));
            patch.put("status", "Requisitioned");
        }
        db.run(Update.entity(E_PR).data(patch).where(p -> p.get("ID").eq(prId)));

        result(context, success
                ? "Requisition is now in S/4 as " + prNo + "."
                : "S/4 refused the requisition: " + message);
    }

    // ------------------------------------------------------ purchase order mirror

    @On(event = "recordPurchaseOrder")
    public void onRecordPurchaseOrder(EventContext context) {
        String requisitionId = str(context.get("requisitionId"));
        String poNo = str(context.get("poNo"));
        if (isBlank(poNo)) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A purchase order needs its S/4 number — it is S/4's document.");
        }

        Row pr = db.run(Select.from(E_PR).where(p -> p.get("ID").eq(requisitionId)))
                .first().orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "No such requisition — a purchase order mirrors one of ours."));

        if (!"SENT".equals(str(pr.get("syncStatus")))) {
            // S/4 cannot have ordered against a requisition it never received.
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "That requisition is " + str(pr.get("syncStatus"))
                            + " — S/4 cannot have raised an order against it.");
        }

        boolean exists = db.run(Select.from(E_PO).where(o -> o.get("poNo").eq(poNo)))
                .first().isPresent();
        if (exists) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "Purchase order " + poNo + " is already mirrored.");
        }

        List<Map<String, Object>> lines = linesParam(context);
        if (lines.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A purchase order with no lines commits nothing — nothing to mirror.");
        }

        String prId = str(pr.get("ID"));
        Map<Integer, Row> prLinesByNo = new HashMap<>();
        for (Row prLine : db.run(Select.from(E_PR_LINE)
                .where(l -> l.get("parent_ID").eq(prId)))) {
            prLinesByNo.put(intOf(prLine.get("lineNo")), prLine);
        }

        String poId = UUID.randomUUID().toString();
        Map<String, Object> po = new LinkedHashMap<>();
        po.put("ID", poId);
        po.put("poNo", poNo);
        po.put("sourceRequisition_ID", prId);
        po.put("project_ID", pr.get("project_ID"));
        po.put("company_ID", pr.get("company_ID"));
        po.put("status", "Ordered");
        po.put("orderedOn", context.get("orderedOn"));
        po.put("vendor_ID", vendorIdFor(str(context.get("vendorBP"))));
        po.put("s4Key", poNo);
        po.put("s4System", str(context.get("s4System")));
        po.put("lastSyncedAt", Instant.now());
        po.put("syncStatus", "OK");
        db.run(Insert.into(E_PO).entry(po));

        BigDecimal ordered = BigDecimal.ZERO;
        int lineNo = 0;
        for (Map<String, Object> line : lines) {
            Integer prLineNo = intOf(line.get("prLineNo"));
            Row prLine = prLinesByNo.get(prLineNo);
            if (prLine == null) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "The order references requisition line " + prLineNo
                                + ", which does not exist on that requisition.");
            }
            BigDecimal netValue = orZero(dec(line.get("netValue")));

            Map<String, Object> poLine = new LinkedHashMap<>();
            poLine.put("ID", UUID.randomUUID().toString());
            poLine.put("parent_ID", poId);
            poLine.put("lineNo", ++lineNo);
            poLine.put("sourcePRLine_ID", prLine.get("ID"));
            // Account assignment is inherited, never re-stated by the caller:
            // an order that charged somewhere other than the requisition it
            // came from would commit against the wrong budget line.
            poLine.put("wbs_ID", prLine.get("wbs_ID"));
            poLine.put("cbs_ID", prLine.get("cbs_ID"));
            poLine.put("resource_ID", prLine.get("resource_ID"));
            poLine.put("material_ID", prLine.get("material_ID"));
            poLine.put("description", prLine.get("description"));
            poLine.put("qty", line.get("qty"));
            poLine.put("openQty", line.get("qty"));
            poLine.put("netValue", netValue);
            poLine.put("eta", line.get("eta"));
            poLine.put("acknowledged", Boolean.FALSE);
            poLine.put("status", "Ordered");
            db.run(Insert.into(E_PO_LINE).entry(poLine));

            Map<String, Object> prPatch = new HashMap<>();
            prPatch.put("status", "Ordered");
            String prLineId = str(prLine.get("ID"));
            db.run(Update.entity(E_PR_LINE).data(prPatch)
                    .where(l -> l.get("ID").eq(prLineId)));

            ordered = ordered.add(netValue);
        }

        long open = db.run(Select.from(E_PR_LINE).where(l -> l.get("parent_ID").eq(prId)))
                .stream().filter(l -> !"Ordered".equals(str(l.get("status")))).count();
        Map<String, Object> prPatch = new HashMap<>();
        prPatch.put("status", open == 0 ? "Ordered" : "Partly ordered");
        db.run(Update.entity(E_PR).data(prPatch).where(p -> p.get("ID").eq(prId)));

        result(context, poNo + " mirrored against the requisition: " + lineNo
                + " line(s) worth " + ordered.toPlainString()
                + ". Run Refresh Control on the budget to see it committed.");
    }

    // ----------------------------------------------------------------- helpers

    /** The vendor mirror for an S/4 business partner, when we hold one. */
    private String vendorIdFor(String bpNumber) {
        if (isBlank(bpNumber)) {
            return null;
        }
        return db.run(Select.from(E_VENDOR).where(v -> v.get("bpNumber").eq(bpNumber)))
                .first().map(v -> str(v.get("ID"))).orElse(null);
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> linesParam(EventContext context) {
        Object raw = context.get("lines");
        if (raw instanceof List<?> list) {
            List<Map<String, Object>> out = new ArrayList<>();
            for (Object o : list) {
                if (o instanceof Map<?, ?> m) {
                    out.add((Map<String, Object>) m);
                }
            }
            return out;
        }
        return List.of();
    }

    private Row targetOf(EventContext context, String missing) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        return (select == null ? Optional.<Row>empty() : db.run(select).first())
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND, missing));
    }

    private static void result(EventContext context, String message) {
        context.put("result", message);
        context.setCompleted();
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static boolean isBlank(String s) { return s == null || s.isBlank(); }

    private static BigDecimal orZero(BigDecimal v) { return v == null ? BigDecimal.ZERO : v; }

    private static Integer intOf(Object v) {
        if (v instanceof Number n) {
            return n.intValue();
        }
        try { return v == null ? null : Integer.valueOf(v.toString()); }
        catch (NumberFormatException e) { return null; }
    }

    private static BigDecimal dec(Object v) {
        if (v == null) { return null; }
        if (v instanceof BigDecimal b) { return b; }
        try { return new BigDecimal(String.valueOf(v)); }
        catch (NumberFormatException e) { return null; }
    }
}
