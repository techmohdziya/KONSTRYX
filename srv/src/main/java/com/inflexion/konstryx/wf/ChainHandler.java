package com.inflexion.konstryx.wf;

import com.sap.cds.Row;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.cds.ApplicationService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.request.UserInfo;
import com.sap.cds.services.runtime.CdsRuntime;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import com.inflexion.konstryx.apr.ApprovalEngine;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * The document spine: request, advisory, availability, reservation.
 *
 * Each step exists because a different person answers a different question.
 * The site asks for the resource; an approver signs for the value; the
 * coordinator decides where it comes from; availability says whether the fleet
 * can supply it; the reservation locks the money. Skipping a step does not
 * remove the question — it just means nobody answered it before the cost
 * landed.
 *
 * The engine's job is sequence and arithmetic. It refuses steps out of order
 * with a message that names the step that is missing, prices lines from the
 * rate master so a request cannot be approved unpriced, and encumbers exactly
 * the value the approval was shown.
 */
@Component
@ServiceName("WorkflowService")
public class ChainHandler implements EventHandler {

    private static final String E_RR = "konstryx.wf.ResourceRequest";
    private static final String E_RR_LINE = "konstryx.wf.ResourceRequestLine";
    private static final String E_ADVISORY = "konstryx.wf.AdvisoryDecision";
    private static final String E_AVC = "konstryx.wf.AvailabilityCheck";
    private static final String E_AVC_LINE = "konstryx.wf.AvailabilityCheckLine";
    private static final String E_RES = "konstryx.wf.Reservation";
    private static final String E_RES_LINE = "konstryx.wf.ReservationLine";
    private static final String E_HISTORY = "konstryx.wf.StatusHistory";
    private static final String E_LINK = "konstryx.wf.DocumentLink";
    private static final String E_RESOURCE = "konstryx.master.ResourceNode";
    private static final String E_RATE = "konstryx.master.RateMaster";

    private static final List<String> DECISIONS = List.of("IN_HOUSE", "PROCURE", "SUBSTITUTE", "REJECT");

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    @Autowired
    private ApprovalEngine approvals;

    @Autowired
    private UserInfo userInfo;

    // ------------------------------------------------------------------ submit

    @On(event = "submit", entity = "WorkflowService.ResourceRequests")
    public void onSubmit(EventContext context) {
        Row rr = targetOf(context, "Resource request not found.");
        String rrId = str(rr.get("ID"));
        String status = str(rr.get("status"));

        if (!(status == null || status.isBlank() || "Draft".equals(status) || "Rejected".equals(status))) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    rr.get("docNo") + " is " + status + " — only a draft or a rejected "
                            + "request can be submitted.");
        }

        List<Row> lines = linesOf(rrId);
        if (lines.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A request with no lines asks for nothing. Add lines before submitting.");
        }

        // Price what is unpriced. An approver shown a request without a value
        // is signing for an unknown number, which is not approval.
        BigDecimal total = BigDecimal.ZERO;
        for (Row line : lines) {
            BigDecimal qty = dec(line.get("qty"));
            if (qty == null || qty.signum() <= 0) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "Line " + line.get("lineNo") + " has no quantity.");
            }
            BigDecimal estTotal = dec(line.get("estTotal"));
            if (estTotal == null || estTotal.signum() == 0) {
                BigDecimal unit = dec(line.get("estUnitCost"));
                if (unit == null || unit.signum() == 0) {
                    unit = rateFor(str(line.get("resource_ID")), line.get("lineNo"));
                }
                estTotal = qty.multiply(unit).setScale(2, RoundingMode.HALF_UP);
                Map<String, Object> patch = new HashMap<>();
                patch.put("estUnitCost", unit);
                patch.put("estTotal", estTotal);
                String lineId = str(line.get("ID"));
                db.run(Update.entity(E_RR_LINE).data(patch).where(l -> l.get("ID").eq(lineId)));
            }
            total = total.add(estTotal);
        }

        Map<String, Object> outcome = approvals.submit(E_RR, rrId,
                str(rr.get("docNo")), total, str(rr.get("company_ID")), userInfo.getName());

        move(rrId, rr, status, "In Approval", "Submitted at " + total.toPlainString());

        result(context, rr.get("docNo") + " submitted at " + total.toPlainString()
                + ". " + outcome.get("message"));
    }

    /**
     * The line's rate comes from the rate master via the same resolution every
     * other consumer uses — the latest rate in force, company beating group.
     */
    private BigDecimal rateFor(String resourceId, Object lineNo) {
        if (resourceId == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Line " + lineNo + " names no resource, so it cannot be priced.");
        }
        java.time.LocalDate today = java.time.LocalDate.now();
        Row best = null;
        java.time.LocalDate bestFrom = null;
        for (Row rate : db.run(Select.from(E_RATE).where(r -> r.get("resource_ID").eq(resourceId)))) {
            java.time.LocalDate from = date(rate.get("effectiveFrom"));
            if (from == null || from.isAfter(today)) {
                continue;
            }
            if (best == null || from.isAfter(bestFrom)) {
                best = rate;
                bestFrom = from;
            }
        }
        if (best == null) {
            String code = db.run(Select.from(E_RESOURCE).where(r -> r.get("ID").eq(resourceId)))
                    .first().map(r -> str(r.get("code"))).orElse(resourceId);
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Line " + lineNo + ": no rate is in force for " + code
                            + ", so the request cannot be priced. Maintain a rate first.");
        }
        BigDecimal value = dec(best.get("rateValue"));
        return value == null ? BigDecimal.ZERO : value;
    }

    // ---------------------------------------------------------------- advisory

    @On(event = "decideLine", entity = "WorkflowService.ResourceRequests")
    public void onDecideLine(EventContext context) {
        Row rr = targetOf(context, "Resource request not found.");
        String rrId = str(rr.get("ID"));
        String status = str(rr.get("status"));

        if (!"Approved".equals(status) && !"In Advisory".equals(status)) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    rr.get("docNo") + " is " + status
                            + " — advisory decisions come after approval.");
        }

        String decision = str(context.get("decision"));
        if (decision == null || !DECISIONS.contains(decision)) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The decision must be one of " + String.join(", ", DECISIONS) + ".");
        }
        if ("REJECT".equals(decision) && isBlank(str(context.get("rationale")))) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Rejecting a line without a rationale sends the site back with nothing "
                            + "to act on.");
        }

        Integer lineNo = intOf(context.get("lineNo"));
        Row line = linesOf(rrId).stream()
                .filter(l -> lineNo != null && lineNo.equals(intOf(l.get("lineNo"))))
                .findFirst()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        rr.get("docNo") + " has no line " + lineNo + "."));
        String lineId = str(line.get("ID"));

        if (line.get("advisory_ID") != null) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "Line " + lineNo + " is already decided. Advisory decisions are not "
                            + "revised in place — reject and re-raise the line.");
        }

        String advisoryId = UUID.randomUUID().toString();
        Map<String, Object> advisory = new LinkedHashMap<>();
        advisory.put("ID", advisoryId);
        advisory.put("rr_ID", rrId);
        advisory.put("line_ID", lineId);
        advisory.put("decision", decision);
        advisory.put("decidedBy", userInfo.getName());
        advisory.put("decidedOn", Instant.now());
        advisory.put("rationale", context.get("rationale"));
        db.run(Insert.into(E_ADVISORY).entry(advisory));

        Map<String, Object> patch = new HashMap<>();
        patch.put("advisory_ID", advisoryId);
        patch.put("lineStatus", "REJECT".equals(decision) ? "Rejected" : "Advised");
        db.run(Update.entity(E_RR_LINE).data(patch).where(l -> l.get("ID").eq(lineId)));

        if ("Approved".equals(status)) {
            move(rrId, rr, status, "In Advisory", "First line decided");
        }

        long undecided = linesOf(rrId).stream().filter(l -> l.get("advisory_ID") == null).count();
        if (undecided == 0) {
            move(rrId, rr, "In Advisory", "Advised", "Every line decided");
        }

        result(context, "Line " + lineNo + ": " + decision + ". "
                + (undecided == 0 ? "All lines are decided."
                        : undecided + " line(s) still to decide."));
    }

    // ------------------------------------------------------------ availability

    @On(event = "runAvailabilityCheck", entity = "WorkflowService.ResourceRequests")
    public void onAvailability(EventContext context) {
        Row rr = targetOf(context, "Resource request not found.");
        String rrId = str(rr.get("ID"));

        if (!"Advised".equals(str(rr.get("status")))) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    rr.get("docNo") + " is " + rr.get("status")
                            + " — every line must be decided before availability is checked.");
        }

        List<Row> inHouse = inHouseLines(rrId);
        if (inHouse.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "No line was decided IN_HOUSE, so there is nothing to check — "
                            + "procured lines are the buyer's problem, not the fleet's.");
        }

        // Through the application service so the AVC receives its document
        // number from the configured range like any other document.
        ApplicationService workflow = serviceFor("WorkflowService");
        String avcId = UUID.randomUUID().toString();
        Map<String, Object> avc = new LinkedHashMap<>();
        avc.put("ID", avcId);
        avc.put("rr_ID", rrId);
        avc.put("project_ID", rr.get("project_ID"));
        avc.put("company_ID", rr.get("company_ID"));
        avc.put("status", "Done");
        avc.put("raisedBy", userInfo.getName());
        avc.put("raisedOn", java.time.LocalDate.now());
        workflow.run(Insert.into("WorkflowService.AvailabilityChecks").entry(avc));

        StringBuilder summary = new StringBuilder();
        for (Row line : inHouse) {
            BigDecimal requested = dec(line.get("qty"));
            BigDecimal committed = committedElsewhere(str(line.get("resource_ID")), rrId);

            // What KONSTRYX itself can know: which reservations already hold
            // the same resource. Stock and inbound receipts are S/4's answer
            // (Q-09) and are left empty rather than invented.
            Map<String, Object> avcLine = new LinkedHashMap<>();
            String avcLineId = UUID.randomUUID().toString();
            avcLine.put("ID", avcLineId);
            avcLine.put("parent_ID", avcId);
            avcLine.put("rrLine_ID", line.get("ID"));
            avcLine.put("atpQty", requested);
            avcLine.put("result", committed.signum() == 0
                    ? "No competing reservation"
                    : committed.stripTrailingZeros().toPlainString() + " reserved elsewhere");
            db.run(Insert.into(E_AVC_LINE).entry(avcLine));

            Map<String, Object> patch = new HashMap<>();
            patch.put("avcResult_ID", avcLineId);
            String lineId = str(line.get("ID"));
            db.run(Update.entity(E_RR_LINE).data(patch).where(l -> l.get("ID").eq(lineId)));

            summary.append(summary.length() == 0 ? "" : "; ")
                    .append("line ").append(line.get("lineNo")).append(": ")
                    .append(committed.signum() == 0 ? "clear"
                            : committed.toPlainString() + " committed elsewhere");
        }

        String avcDocNo = db.run(Select.from(E_AVC).where(a -> a.get("ID").eq(avcId)))
                .first().map(r -> str(r.get("docNo"))).orElse(avcId);
        link(str(rr.get("docNo")), avcDocNo, "AVAILABILITY");
        move(rrId, rr, "Advised", "AVC Done", avcDocNo);

        result(context, avcDocNo + " checked " + inHouse.size() + " in-house line(s): "
                + summary + ".");
    }

    /** Encumbered reservation quantity held against the same resource by others. */
    private BigDecimal committedElsewhere(String resourceId, String exceptRrId) {
        BigDecimal total = BigDecimal.ZERO;
        if (resourceId == null) {
            return total;
        }
        for (Row resLine : db.run(Select.from(E_RES_LINE)
                .where(l -> l.get("resource_ID").eq(resourceId)))) {
            if ("Closed".equals(str(resLine.get("lineStatus")))) {
                continue;
            }
            Object resId = resLine.get("reservation_ID");
            if (resId != null) {
                Optional<Row> reservation = db.run(Select.from(E_RES)
                        .where(r -> r.get("ID").eq(resId.toString()))).first();
                if (reservation.isPresent()
                        && exceptRrId.equals(str(reservation.get().get("rr_ID")))) {
                    continue;
                }
            }
            BigDecimal qty = dec(resLine.get("qty"));
            if (qty != null) {
                total = total.add(qty);
            }
        }
        return total;
    }

    // ------------------------------------------------------------- reservation

    @On(event = "createReservation", entity = "WorkflowService.ResourceRequests")
    public void onReserve(EventContext context) {
        Row rr = targetOf(context, "Resource request not found.");
        String rrId = str(rr.get("ID"));

        if (!"AVC Done".equals(str(rr.get("status")))) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    rr.get("docNo") + " is " + rr.get("status")
                            + " — availability comes before reservation.");
        }

        boolean already = db.run(Select.from(E_RES).where(r -> r.get("rr_ID").eq(rrId)))
                .first().isPresent();
        if (already) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    rr.get("docNo") + " already has a reservation. One request, one "
                            + "reservation — the money is already locked once.");
        }

        List<Row> inHouse = inHouseLines(rrId);

        ApplicationService workflow = serviceFor("WorkflowService");
        String resId = UUID.randomUUID().toString();
        Map<String, Object> reservation = new LinkedHashMap<>();
        reservation.put("ID", resId);
        reservation.put("rr_ID", rrId);
        reservation.put("project_ID", rr.get("project_ID"));
        reservation.put("company_ID", rr.get("company_ID"));
        reservation.put("executionFlow", "IN_HOUSE");
        reservation.put("status", "Created");
        reservation.put("raisedBy", userInfo.getName());
        reservation.put("raisedOn", java.time.LocalDate.now());
        workflow.run(Insert.into("WorkflowService.Reservations").entry(reservation));

        BigDecimal encumbered = BigDecimal.ZERO;
        for (Row line : inHouse) {
            BigDecimal estTotal = dec(line.get("estTotal"));
            BigDecimal unit = dec(line.get("estUnitCost"));
            if (estTotal == null) {
                estTotal = BigDecimal.ZERO;
            }

            // The encumbrance is the line's approved value — the figure the
            // approval chain was shown, not a fresher rate. A rate change
            // between approval and reservation is a variance to surface, not
            // something to silently absorb into the lock.
            Map<String, Object> resLine = new LinkedHashMap<>();
            resLine.put("ID", UUID.randomUUID().toString());
            resLine.put("reservation_ID", resId);
            resLine.put("rrLine_ID", line.get("ID"));
            resLine.put("resource_ID", line.get("resource_ID"));
            resLine.put("qty", line.get("qty"));
            resLine.put("uom", line.get("uom"));
            resLine.put("dailyRate", unit);
            resLine.put("encumberedAmount", estTotal);
            resLine.put("consumedToDate", BigDecimal.ZERO);
            resLine.put("burnPct", BigDecimal.ZERO);
            resLine.put("costToDate", BigDecimal.ZERO);
            resLine.put("drift", BigDecimal.ZERO);
            resLine.put("lineStatus", "Created");
            db.run(Insert.into(E_RES_LINE).entry(resLine));

            Map<String, Object> patch = new HashMap<>();
            patch.put("lineStatus", "Reserved");
            String lineId = str(line.get("ID"));
            db.run(Update.entity(E_RR_LINE).data(patch).where(l -> l.get("ID").eq(lineId)));

            encumbered = encumbered.add(estTotal);
        }

        String resDocNo = db.run(Select.from(E_RES).where(r -> r.get("ID").eq(resId)))
                .first().map(r -> str(r.get("docNo"))).orElse(resId);
        link(str(rr.get("docNo")), resDocNo, "RESERVATION");
        move(rrId, rr, "AVC Done", "Reserved", resDocNo);

        result(context, resDocNo + " reserves " + inHouse.size() + " line(s) and encumbers "
                + encumbered.toPlainString() + " — the value the approval was shown.");
    }

    @On(event = "close", entity = "WorkflowService.Reservations")
    public void onClose(EventContext context) {
        Row reservation = targetOf(context, "Reservation not found.");
        String resId = str(reservation.get("ID"));

        if ("Closed".equals(str(reservation.get("status")))) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    reservation.get("docNo") + " is already closed.");
        }

        int lines = 0;
        for (Row line : db.run(Select.from(E_RES_LINE)
                .where(l -> l.get("reservation_ID").eq(resId)))) {
            Map<String, Object> patch = new HashMap<>();
            patch.put("lineStatus", "Closed");
            String lineId = str(line.get("ID"));
            db.run(Update.entity(E_RES_LINE).data(patch).where(l -> l.get("ID").eq(lineId)));
            lines++;
        }

        Map<String, Object> patch = new HashMap<>();
        patch.put("status", "Closed");
        db.run(Update.entity(E_RES).data(patch).where(r -> r.get("ID").eq(resId)));
        history("RES", str(reservation.get("docNo")),
                str(reservation.get("status")), "Closed", "Closed by " + userInfo.getName());

        result(context, reservation.get("docNo") + " closed with " + lines
                + " line(s). The encumbrance record remains for reconciliation.");
    }

    // ----------------------------------------------------------------- helpers

    private List<Row> linesOf(String rrId) {
        List<Row> lines = new ArrayList<>();
        for (Row line : db.run(Select.from(E_RR_LINE).where(l -> l.get("parent_ID").eq(rrId)))) {
            lines.add(line);
        }
        return lines;
    }

    private List<Row> inHouseLines(String rrId) {
        List<Row> inHouse = new ArrayList<>();
        for (Row line : linesOf(rrId)) {
            Object advisoryId = line.get("advisory_ID");
            if (advisoryId == null) {
                continue;
            }
            Optional<Row> advisory = db.run(Select.from(E_ADVISORY)
                    .where(a -> a.get("ID").eq(advisoryId.toString()))).first();
            if (advisory.isPresent() && "IN_HOUSE".equals(str(advisory.get().get("decision")))) {
                inHouse.add(line);
            }
        }
        return inHouse;
    }

    private void move(String rrId, Row rr, String from, String to, String comment) {
        Map<String, Object> patch = new HashMap<>();
        patch.put("status", to);
        db.run(Update.entity(E_RR).data(patch).where(r -> r.get("ID").eq(rrId)));
        history("RR", str(rr.get("docNo")), from, to, comment);
    }

    private void history(String docType, String docNo, String from, String to, String comment) {
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("ID", UUID.randomUUID().toString());
        entry.put("docType", docType);
        entry.put("docId", docNo);
        entry.put("fromState", from);
        entry.put("toState", to);
        entry.put("changedBy", userInfo.getName());
        entry.put("changedOn", Instant.now());
        entry.put("comment", comment);
        db.run(Insert.into(E_HISTORY).entry(entry));
    }

    private void link(String fromDoc, String toDoc, String type) {
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("ID", UUID.randomUUID().toString());
        entry.put("fromDoc", fromDoc);
        entry.put("toDoc", toDoc);
        entry.put("linkType", type);
        db.run(Insert.into(E_LINK).entry(entry));
    }

    private ApplicationService serviceFor(String name) {
        return runtime.getServiceCatalog().getServices(ApplicationService.class)
                .filter(s -> s.getName().equals(name))
                .findFirst()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.SERVER_ERROR,
                        "No such service: " + name));
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

    private static java.time.LocalDate date(Object v) {
        if (v == null) { return null; }
        if (v instanceof java.time.LocalDate d) { return d; }
        try { return java.time.LocalDate.parse(String.valueOf(v).substring(0, 10)); }
        catch (RuntimeException e) { return null; }
    }
}
