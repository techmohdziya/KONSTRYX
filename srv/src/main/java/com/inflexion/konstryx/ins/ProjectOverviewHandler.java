package com.inflexion.konstryx.ins;

import com.sap.cds.Row;
import com.sap.cds.ql.Delete;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.services.cds.CdsReadEventContext;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.HandlerOrder;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * Fills the project overview, one pass over each project's own rows.
 *
 * Before the read rather than on it, which is what the model asks for and is
 * also the only way the projection's own thresholds keep working: the colours
 * on ProjectOverviews are case expressions over these columns, and a handler
 * that answered the read itself would have to restate every one of them in
 * Java. Two statements of the same threshold is how the summary and the screen
 * beneath it come to disagree, which is the failure this page exists to avoid.
 *
 * The row is keyed on the project, so a refresh replaces a project's own row
 * and nothing else — a reader filtering to one project does not pay for the
 * others, and two readers refreshing at once cannot interleave into a third
 * project's figures.
 *
 * What cannot be derived is left null and said out loud in `note`. Every
 * figure below is a sum or a ratio of rows that already exist; none of them is
 * a constant, and the two that would have to be — a signed earned-value
 * measurement and a critical path — are reported as absent instead. A summary
 * that quietly invents the number it could not find is worse than one that
 * admits the gap, because only the second can be checked.
 */
@Component
@ServiceName("ProjectService")
public class ProjectOverviewHandler implements EventHandler {

    private static final String E_OVERVIEW = "konstryx.ins.ProjectOverview";
    private static final String E_PROJECT = "konstryx.prj.Project";
    private static final String E_COMPANY = "konstryx.admin.Company";
    private static final String E_BOQ = "konstryx.prj.BOQ";
    private static final String E_BUDGET = "konstryx.bud.Budget";
    private static final String E_BUDGET_LINE = "konstryx.bud.BudgetLine";
    private static final String E_ACTIVITY = "konstryx.prj.Activity";
    private static final String E_WBS = "konstryx.prj.WBSElement";
    private static final String E_RR = "konstryx.wf.ResourceRequest";
    private static final String E_RESERVATION = "konstryx.wf.Reservation";
    private static final String E_RESERVATION_LINE = "konstryx.wf.ReservationLine";
    private static final String E_TIMESHEET = "konstryx.mpr.TimesheetEntry";
    private static final String E_REQUISITION = "konstryx.mat.PurchaseRequisition";
    private static final String E_PAYMENT_CERT = "konstryx.scr.PaymentCertificate";
    private static final String E_REPORT = "konstryx.ins.ProjectPeriodReport";
    private static final String E_PERIOD = "konstryx.fin.FiscalPeriod";

    private static final BigDecimal HUNDRED = new BigDecimal("100");

    /** A request still wants something from somebody until it reaches one of these. */
    private static final Set<String> REQUEST_SETTLED = Set.of("Closed", "Rejected", "Cancelled");
    /** A day is somebody's problem until it is signed or posted. */
    private static final Set<String> DAY_SETTLED = Set.of("Signed", "Posted");
    /** A requisition that has not reached ERP, either because it has not gone or because it bounced. */
    private static final Set<String> REQUISITION_UNSENT = Set.of("NOT_SENT", "PENDING", "FAILED");

    @Autowired
    private PersistenceService db;

    /**
     * The projects, read through the application service rather than the
     * database, so the authorization layer narrows them to the ones this
     * reader may see.
     *
     * Read straight from persistence, this page listed five jobs while every
     * other screen in the product listed three, because those screens go
     * through the service and this one did not. A summary that shows a reader
     * a project they cannot open is worse than one that omits it.
     */
    @Autowired
    @Qualifier("ProjectService")
    private CqnService projects;

    @Before(event = CqnService.EVENT_READ, entity = "ProjectService.ProjectOverviews")
    @HandlerOrder(HandlerOrder.EARLY)
    public void refresh(CdsReadEventContext context) {
        List<Map<String, Object>> rows = new ArrayList<>();
        // Active rows only. A draft-enabled entity answers a plain read with
        // both the active row and anybody's draft of it, which gave this
        // handler two rows carrying the same project key and a unique
        // constraint violation on the insert.
        for (Row project : projects.run(Select.from("ProjectService.Projects")
                .where(p -> p.get("IsActiveEntity").eq(true)))) {
            rows.add(overviewOf(project));
        }
        // Replaced wholesale rather than merged: a project deleted since the
        // last read must not leave its summary behind on the page.
        db.run(Delete.from(E_OVERVIEW));
        if (!rows.isEmpty()) {
            db.run(Insert.into(E_OVERVIEW).entries(rows));
        }
    }

    private Map<String, Object> overviewOf(Row project) {
        String projectId = str(project.get("ID"));
        Map<String, Object> o = new LinkedHashMap<>();
        List<String> caveats = new ArrayList<>();

        // The overview is the project, seen from further away, so it carries the
        // project's own key. A fresh UUID per refresh would change the row's
        // identity every time anyone looked at it.
        o.put("ID", projectId);
        o.put("project_ID", projectId);
        o.put("code", project.get("code"));
        o.put("name", project.get("name"));
        o.put("stage", project.get("stage"));
        o.put("ccy_code", project.get("ccy_code"));
        o.put("startDate", project.get("startDate"));
        o.put("endDate", project.get("endDate"));
        o.put("refreshedAt", Instant.now());
        o.put("companyName", first(E_COMPANY, "ID", project.get("company_ID"))
                .map(c -> c.get("name")).orElse(null));

        // ---------------------------------------------------------- the money
        BigDecimal contractValue = orZero(dec(project.get("contractValue")));
        o.put("contractValue", contractValue);

        BigDecimal boqValue = BigDecimal.ZERO;
        for (Row boq : rowsWhere(E_BOQ, "project_ID", projectId)) {
            boqValue = boqValue.add(orZero(dec(boq.get("contractValue"))));
        }
        o.put("boqValue", boqValue);

        BigDecimal budgetTotal = BigDecimal.ZERO;
        Set<String> budgetIds = new HashSet<>();
        for (Row budget : rowsWhere(E_BUDGET, "project_ID", projectId)) {
            budgetIds.add(str(budget.get("ID")));
            budgetTotal = budgetTotal.add(orZero(dec(budget.get("totalAmount"))));
        }

        BigDecimal committed = BigDecimal.ZERO;
        BigDecimal encumbered = BigDecimal.ZERO;
        BigDecimal actual = BigDecimal.ZERO;
        BigDecimal available = BigDecimal.ZERO;
        int linesOverBudget = 0;
        for (String budgetId : budgetIds) {
            for (Row line : rowsWhere(E_BUDGET_LINE, "budget_ID", budgetId)) {
                committed = committed.add(orZero(dec(line.get("committed"))));
                encumbered = encumbered.add(orZero(dec(line.get("encumbered"))));
                actual = actual.add(orZero(dec(line.get("actual"))));
                available = available.add(orZero(dec(line.get("available"))));
                if (orZero(dec(line.get("available"))).signum() < 0) {
                    linesOverBudget++;
                }
            }
        }
        o.put("budgetTotal", budgetTotal);
        o.put("committed", committed);
        o.put("encumbered", encumbered);
        o.put("actual", actual);
        o.put("available", available);

        BigDecimal spokenFor = committed.add(encumbered).add(actual);
        o.put("budgetUsedPct", pct(spokenFor, budgetTotal, 2));
        if (budgetTotal.signum() == 0) {
            caveats.add("no budget on this project, so nothing below is measured against one");
        } else if (spokenFor.signum() == 0) {
            // The control record is read as it stands rather than recomputed
            // from the documents behind it. Summing the reservations here would
            // put a number on this page that the budget's own lines contradict,
            // and a summary that disagrees with the screen underneath it is
            // worth less than a blank one. What is missing is the encumbrance
            // handler, so the page says that instead of covering for it.
            BigDecimal held = BigDecimal.ZERO;
            int reservations = 0;
            for (Row reservation : rowsWhere(E_RESERVATION, "project_ID", projectId)) {
                reservations++;
                for (Row line : rowsWhere(E_RESERVATION_LINE, "reservation_ID", str(reservation.get("ID")))) {
                    held = held.add(orZero(dec(line.get("encumberedAmount"))));
                }
            }
            if (reservations > 0) {
                caveats.add(String.format(
                        "budget lines show nothing spoken for: no encumbrance handler, "
                                + "so %d reservation(s) holding %s are uncounted",
                        reservations, held.setScale(2, RoundingMode.HALF_UP).toPlainString()));
            }
        }

        // ------------------------------------------------------ the programme
        int activitiesTotal = 0;
        int activitiesDone = 0;
        int activitiesCritical = 0;
        BigDecimal weightedProgress = BigDecimal.ZERO;
        BigDecimal totalDuration = BigDecimal.ZERO;
        LocalDate scheduleFinish = null;
        boolean anyEarlyFinish = false;
        for (Row activity : rowsWhere(E_ACTIVITY, "project_ID", projectId)) {
            activitiesTotal++;
            BigDecimal done = orZero(dec(activity.get("percentDone")));
            if (done.compareTo(HUNDRED) >= 0) {
                activitiesDone++;
            }
            if (Boolean.TRUE.equals(activity.get("isCritical"))) {
                activitiesCritical++;
            }
            // Weighted by duration, so a six-month activity at half way counts
            // for more than a week-long one that is finished. An unweighted
            // mean of percentDone is the figure that makes a job look half
            // built because somebody closed out the small jobs first.
            BigDecimal duration = orZero(dec(activity.get("durationDays")));
            weightedProgress = weightedProgress.add(done.multiply(duration));
            totalDuration = totalDuration.add(duration);

            if (activity.get("earlyFinish") != null) {
                anyEarlyFinish = true;
            }
            LocalDate finish = date(activity.get("earlyFinish") != null
                    ? activity.get("earlyFinish") : activity.get("plannedFinish"));
            if (finish != null && (scheduleFinish == null || finish.isAfter(scheduleFinish))) {
                scheduleFinish = finish;
            }
        }
        o.put("activitiesTotal", activitiesTotal);
        o.put("activitiesDone", activitiesDone);
        o.put("activitiesCritical", activitiesCritical);
        o.put("scheduleFinish", scheduleFinish);

        LocalDate contractFinish = date(project.get("endDate"));
        o.put("slipDays", scheduleFinish == null || contractFinish == null ? null
                : (int) ChronoUnit.DAYS.between(contractFinish, scheduleFinish));

        BigDecimal percentComplete = totalDuration.signum() > 0
                ? weightedProgress.divide(totalDuration, 2, RoundingMode.HALF_UP)
                : null;
        o.put("percentComplete", percentComplete);

        if (activitiesTotal == 0) {
            caveats.add("no programme loaded, so there is no progress and no finish date");
        } else if (!anyEarlyFinish) {
            caveats.add("no critical path: finish is the latest planned date, "
                    + "none marked critical");
        }

        // ------------------------------------------------------------ the EVM
        //
        // Read from the reconciliation, not computed a second time.
        //
        // This used to derive its own earned value from the programme, which
        // gave a project two of them: the overview said 13.2m from activity
        // progress and the period report said 18.8m from measured quantities,
        // with a margin of 28 % beside one of 15 %. Both were arrived at
        // honestly and only one can be true, and a summary that disagrees with
        // the screen a reader opens next to check it is the one thing this
        // page must never do.
        //
        // So the measurement is the reconciliation's, and this reports it. The
        // programme still supplies percent complete below, which is a
        // different question - how far through the work is the job, rather
        // than what has it earned.
        Row latest = latestReportOf(projectId);
        BigDecimal earnedValue = latest == null ? null : dec(latest.get("earnedValue"));
        BigDecimal cpi = latest == null ? null : dec(latest.get("cpi"));
        BigDecimal forecastMargin = latest == null ? null : dec(latest.get("forecastMargin"));
        BigDecimal forecastMarginPct = latest == null ? null : dec(latest.get("forecastMarginPct"));

        o.put("earnedValue", earnedValue);
        o.put("actualCost", latest == null ? actual : orZero(dec(latest.get("actualCost"))));
        o.put("cpi", cpi);
        o.put("forecastMargin", forecastMargin);
        o.put("forecastMarginPct", forecastMarginPct);
        o.put("measuredPeriod", latest == null
                ? "Not reconciled"
                : truncate(str(latest.get("periodName")), 40));

        if (latest == null) {
            caveats.add("this project has not been reconciled, so there is no earned "
                    + "value, no cost index and no forecast - run reconcile on it");
        }

        // ------------------------------------------------- what needs a human
        int openRequests = 0;
        for (Row request : rowsWhere(E_RR, "project_ID", projectId)) {
            if (!REQUEST_SETTLED.contains(str(request.get("status")))) {
                openRequests++;
            }
        }
        o.put("openRequests", openRequests);

        // A day is reached through the WBS it was booked to; the timesheet
        // carries no project of its own, and going through the manpower line
        // and its request would say the same thing one join later.
        Set<String> projectWbs = new HashSet<>();
        for (Row wbs : rowsWhere(E_WBS, "project_ID", projectId)) {
            projectWbs.add(str(wbs.get("ID")));
        }
        int unsignedDays = 0;
        for (Row day : db.run(Select.from(E_TIMESHEET))) {
            if (projectWbs.contains(str(day.get("wbs_ID")))
                    && !DAY_SETTLED.contains(str(day.get("logStatus")))) {
                unsignedDays++;
            }
        }
        o.put("unsignedDays", unsignedDays);

        int requisitionsUnsent = 0;
        for (Row requisition : rowsWhere(E_REQUISITION, "project_ID", projectId)) {
            if (REQUISITION_UNSENT.contains(str(requisition.get("syncStatus")))) {
                requisitionsUnsent++;
            }
        }
        o.put("requisitionsUnsent", requisitionsUnsent);
        o.put("linesOverBudget", linesOverBudget);

        BigDecimal certifiedNet = BigDecimal.ZERO;
        for (Row cert : rowsWhere(E_PAYMENT_CERT, "project_ID", projectId)) {
            certifiedNet = certifiedNet.add(orZero(dec(cert.get("netCertified"))));
        }
        o.put("certifiedNet", certifiedNet);

        o.put("note", caveats.isEmpty() ? null : truncate(capitalise(String.join("; ", caveats)), 255));
        return o;
    }


    /**
     * The most recent reconciliation for a project, by the period it measured.
     *
     * Most recent rather than any: a project reconciled for three months has
     * three reports, and the overview shows where it stands now.
     */
    private Row latestReportOf(String projectId) {
        Row best = null;
        java.time.LocalDate bestOn = null;
        for (Row report : rowsWhere(E_REPORT, "project_ID", projectId)) {
            java.time.LocalDate on = first(E_PERIOD, "ID", report.get("period_ID"))
                    .map(period -> date(period.get("startDate"))).orElse(null);
            if (best == null || (on != null && (bestOn == null || on.isAfter(bestOn)))) {
                best = report;
                bestOn = on;
            }
        }
        return best;
    }

    // ---------------------------------------------------------------- helpers

    private Iterable<Row> rowsWhere(String entity, String column, Object value) {
        if (value == null) {
            return List.of();
        }
        String v = String.valueOf(value);
        return db.run(Select.from(entity).where(r -> r.get(column).eq(v)));
    }

    private Optional<Row> first(String entity, String column, Object value) {
        if (value == null) {
            return Optional.empty();
        }
        String v = String.valueOf(value);
        return db.run(Select.from(entity).where(r -> r.get(column).eq(v))).first();
    }

    /** Percentage of one figure against another, null-safe and zero-safe. */
    private static BigDecimal pct(BigDecimal part, BigDecimal whole, int scale) {
        if (whole == null || whole.signum() == 0) {
            return null;
        }
        return part.multiply(HUNDRED).divide(whole, scale, RoundingMode.HALF_UP);
    }

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }

    private static BigDecimal orZero(BigDecimal v) {
        return v == null ? BigDecimal.ZERO : v;
    }

    private static BigDecimal dec(Object v) {
        if (v == null) {
            return null;
        }
        if (v instanceof BigDecimal b) {
            return b;
        }
        try {
            return new BigDecimal(String.valueOf(v));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static LocalDate date(Object v) {
        if (v == null) {
            return null;
        }
        if (v instanceof LocalDate d) {
            return d;
        }
        try {
            return LocalDate.parse(String.valueOf(v));
        } catch (RuntimeException e) {
            return null;
        }
    }

    private static String capitalise(String s) {
        return s.isEmpty() ? s : Character.toUpperCase(s.charAt(0)) + s.substring(1);
    }

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max - 1) + "\u2026";
    }
}
