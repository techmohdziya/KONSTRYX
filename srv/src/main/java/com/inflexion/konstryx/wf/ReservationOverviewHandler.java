package com.inflexion.konstryx.wf;

import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Computes the reservation overview: chain progress and S/4 state per row.
 *
 * The ten-step chain is the product's spine, so the overview reports against
 * all ten — including the steps this build cannot yet complete. A step that is
 * pending because the module is not built reads differently from one that is
 * pending because someone has not done it, and the CMT step says plainly that
 * its S/4 connector is not wired yet. A screen that only counts the steps it
 * happens to implement would always look nearly finished, which is exactly the
 * lie an overview exists to prevent.
 */
@Component
@ServiceName("WorkflowService")
public class ReservationOverviewHandler implements EventHandler {

    private static final String E_RES = "konstryx.wf.Reservation";
    private static final String E_RES_LINE = "konstryx.wf.ReservationLine";
    private static final String E_RR = "konstryx.wf.ResourceRequest";
    private static final String E_RR_LINE = "konstryx.wf.ResourceRequestLine";
    private static final String E_AVC = "konstryx.wf.AvailabilityCheck";
    private static final String E_PROJECT = "konstryx.prj.Project";

    @Autowired
    private PersistenceService db;

    @On(event = "reservationOverview")
    public void onOverview(EventContext context) {
        List<Map<String, Object>> out = new ArrayList<>();

        for (Row reservation : db.run(Select.from(E_RES))) {
            String resId = str(reservation.get("ID"));
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("reservationID", resId);
            row.put("docNo", reservation.get("docNo"));
            row.put("executionFlow", reservation.get("executionFlow"));
            row.put("status", reservation.get("status"));

            // ---- the money on the reservation itself -----------------------
            int lines = 0;
            BigDecimal encumbered = BigDecimal.ZERO;
            BigDecimal consumed = BigDecimal.ZERO;
            for (Row line : db.run(Select.from(E_RES_LINE)
                    .where(l -> l.get("reservation_ID").eq(resId)))) {
                lines++;
                encumbered = encumbered.add(orZero(dec(line.get("encumberedAmount"))));
                consumed = consumed.add(orZero(dec(line.get("costToDate"))));
            }
            row.put("lines", lines);
            row.put("encumbered", encumbered);
            row.put("consumed", consumed);
            row.put("burnPct", encumbered.signum() > 0
                    ? consumed.multiply(new BigDecimal("100"))
                            .divide(encumbered, 2, RoundingMode.HALF_UP)
                    : BigDecimal.ZERO);

            // ---- the thread: which of the ten steps stand ------------------
            Object rrId = reservation.get("rr_ID");
            Optional<Row> rr = rrId == null ? Optional.empty()
                    : db.run(Select.from(E_RR).where(r -> r.get("ID").eq(rrId.toString()))).first();
            row.put("rrID", rrId == null ? null : rrId.toString());
            row.put("rrDocNo", rr.map(r -> r.get("docNo")).orElse(null));

            boolean advisoryDone = false;
            boolean avcDone = false;
            if (rr.isPresent()) {
                String theRrId = rrId.toString();
                long undecided = 0, lineCount = 0;
                for (Row line : db.run(Select.from(E_RR_LINE)
                        .where(l -> l.get("parent_ID").eq(theRrId)))) {
                    lineCount++;
                    if (line.get("advisory_ID") == null) {
                        undecided++;
                    }
                }
                advisoryDone = lineCount > 0 && undecided == 0;
                avcDone = db.run(Select.from(E_AVC)
                        .where(a -> a.get("rr_ID").eq(theRrId))).first().isPresent();
            }
            boolean closed = "Closed".equals(str(reservation.get("status")));

            int done = 0;
            List<String> pending = new ArrayList<>();
            // 1 RR — the reservation cannot exist without it
            if (rr.isPresent()) { done++; } else { pending.add("RR"); }
            // 2 ADV
            if (advisoryDone) { done++; } else { pending.add("ADV"); }
            // 3 AVC
            if (avcDone) { done++; } else { pending.add("AVC"); }
            // 4 RES — this row
            done++;
            // 5 CMT — S/4-owned; the connector is not wired yet, and pretending
            //   the KONSTRYX-side encumbrance is the S/4 commitment would be
            //   the exact confusion the split exists to prevent.
            pending.add("CMT (S/4)");
            // 6-9 MOB / OPL / VAR / DMB — modules not built in CAP yet
            pending.add("MOB");
            pending.add("OPL");
            pending.add("VAR");
            pending.add("DMB");
            // 10 CLS
            if (closed) { done++; } else { pending.add("CLS"); }

            row.put("stepsDone", done);
            row.put("stepsTotal", 10);
            // · = middle dot; escaped so a platform-encoding javac cannot mangle it.
            row.put("pendingSteps", String.join(" · ", pending));

            // ---- S/4, honestly ---------------------------------------------
            Object projectId = reservation.get("project_ID");
            Optional<Row> project = projectId == null ? Optional.empty()
                    : db.run(Select.from(E_PROJECT)
                            .where(p -> p.get("ID").eq(projectId.toString()))).first();
            row.put("projectCode", project.map(p -> p.get("code")).orElse(null));
            row.put("projectSync", project.map(p -> str(p.get("syncStatus"))).orElse(null));
            row.put("s4Commitment", "CONNECTOR PENDING");

            out.add(row);
        }

        context.put("result", out);
        context.setCompleted();
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static BigDecimal orZero(BigDecimal v) { return v == null ? BigDecimal.ZERO : v; }

    private static BigDecimal dec(Object v) {
        if (v == null) { return null; }
        if (v instanceof BigDecimal b) { return b; }
        try { return new BigDecimal(String.valueOf(v)); }
        catch (NumberFormatException e) { return null; }
    }
}
