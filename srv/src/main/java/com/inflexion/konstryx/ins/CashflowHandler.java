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
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * The spend curve: what each period was planned to cost, and what it did.
 *
 * Recomputed before every read rather than kept, unlike the period report,
 * and the difference is what each one is for. A reconciliation is a
 * measurement somebody signed off for a month and has to be reproducible
 * afterwards. A cashflow is a view of the phased budget against the cost
 * ledger, and both of those move underneath it - a stored curve would be a
 * picture of a budget that has since been re-phased.
 *
 * Both halves, each on its own date.
 *
 * Money out sits on the period the cost fell. Money in sits on the period the
 * cash arrives - the settlement date where a certificate has been paid, the
 * due date where it has been issued and not paid, and otherwise the end of
 * the valued period plus the payment terms. The valuation that earned it
 * stays on its own period in billedGross, several columns to the left.
 *
 * Keeping them apart is the entire point. A contractor pays for a month's
 * work inside that month and is paid for it two months later, so the running
 * position runs negative through the middle of every job and comes back at
 * the end. That trough is what the job has to fund, and a report that valued
 * revenue in the month the cost fell would draw a straight line through it
 * and show nothing to fund at all.
 */
@Component
@ServiceName("ProjectService")
public class CashflowHandler implements EventHandler {

    private static final String E_CASHFLOW = "konstryx.ins.ProjectCashflow";
    private static final String E_PROJECT = "konstryx.prj.Project";
    private static final String E_PERIOD = "konstryx.fin.FiscalPeriod";
    private static final String E_CALENDAR = "konstryx.fin.FiscalCalendar";
    private static final String E_PHASE = "konstryx.bud.BudgetPhase";
    private static final String E_WBS = "konstryx.prj.WBSElement";
    private static final String E_TIMESHEET = "konstryx.mpr.TimesheetEntry";
    private static final String E_PULL = "konstryx.mat.PullRequest";
    private static final String E_INVOICE = "konstryx.mat.SupplierInvoice";
    private static final String E_PAYMENT_CERT = "konstryx.scr.PaymentCertificate";
    private static final String E_CLIENT_APP = "konstryx.bil.PaymentApplication";
    private static final String E_CLIENT_CERT = "konstryx.bil.PaymentCertificate";
    private static final String E_BOQ = "konstryx.prj.BOQ";
    private static final String E_BOQ_ITEM = "konstryx.prj.BOQItem";

    private static final BigDecimal HUNDRED = new BigDecimal("100");
    private static final BigDecimal HALF = new BigDecimal("50");
    private static final Set<String> DAY_COUNTED = Set.of("Signed", "Posted");

    /**
     * Payment terms assumed where a claim carries no date of its own.
     *
     * Sixty days is the Gulf construction norm for a main contract - thirty
     * to certify and thirty to pay - and it is an assumption, which is why
     * every row says which lag produced its cash in the lagDays column rather
     * than leaving a reader to infer it.
     */
    private static final int DEFAULT_LAG_DAYS = 60;

    /** Held back on each valuation where no claim states a rate. */
    private static final BigDecimal DEFAULT_RETENTION_PCT = new BigDecimal("10.00");

    @Autowired
    private PersistenceService db;

    @Before(event = CqnService.EVENT_READ, entity = "ProjectService.Cashflow")
    @HandlerOrder(HandlerOrder.EARLY)
    public void refresh(CdsReadEventContext context) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Row project : db.run(Select.from(E_PROJECT))) {
            rows.addAll(curveOf(project));
        }
        db.run(Delete.from(E_CASHFLOW));
        if (!rows.isEmpty()) {
            db.run(Insert.into(E_CASHFLOW).entries(rows));
        }
    }

    private List<Map<String, Object>> curveOf(Row project) {
        String projectId = str(project.get("ID"));
        List<Row> periods = periodsFor(str(project.get("company_ID")));

        // ---- what was planned, and how much of it rests on an even spread
        Map<String, BigDecimal> planned = new LinkedHashMap<>();
        Map<String, BigDecimal> envelope = new LinkedHashMap<>();
        for (Row phase : rowsWhere(E_PHASE, "project_ID", projectId)) {
            String periodId = str(phase.get("period_ID"));
            BigDecimal amount = orZero(dec(phase.get("amount")));
            planned.merge(periodId, amount, BigDecimal::add);
            if ("ENVELOPE".equalsIgnoreCase(str(phase.get("basis")))) {
                envelope.merge(periodId, amount, BigDecimal::add);
            }
        }

        // ---- what was spent, each kind of cost on the date it carries
        Set<String> projectWbs = new HashSet<>();
        for (Row wbs : rowsWhere(E_WBS, "project_ID", projectId)) {
            projectWbs.add(str(wbs.get("ID")));
        }
        List<Dated> costs = new ArrayList<>();
        for (Row day : db.run(Select.from(E_TIMESHEET))) {
            if (projectWbs.contains(str(day.get("wbs_ID")))
                    && DAY_COUNTED.contains(str(day.get("logStatus")))) {
                costs.add(new Dated(date(day.get("workDate")),
                        orZero(dec(day.get("costAmount")))));
            }
        }
        for (Row pull : rowsWhere(E_PULL, "project_ID", projectId)) {
            // The goods issue is the cost, so it falls in the month ERP moved
            // the stock rather than the month the site asked for it.
            LocalDate issued = date(pull.get("s4GIDate"));
            costs.add(new Dated(issued != null ? issued : date(pull.get("raisedOn")),
                    orZero(dec(pull.get("issuedValue")))));
        }
        for (Row invoice : rowsWhere(E_INVOICE, "project_ID", projectId)) {
            costs.add(new Dated(date(invoice.get("postingDate")),
                    orZero(dec(invoice.get("netAmount")))));
        }
        for (Row cert : rowsWhere(E_PAYMENT_CERT, "project_ID", projectId)) {
            costs.add(new Dated(date(cert.get("raisedOn")),
                    orZero(dec(cert.get("netCertified")))));
        }

        // ---- what was valued, and when the money for it arrives
        //
        // A claim states both: the period it measured, and the date it is due
        // or was settled. Where a project has no claims yet the valuation is
        // taken from measured quantities instead, spread on the same curve the
        // cost follows, so every job draws a position rather than only the two
        // that have been billed.
        Map<String, BigDecimal> billed = new LinkedHashMap<>();
        Map<String, BigDecimal> retention = new LinkedHashMap<>();
        Map<String, BigDecimal> retentionRate = new LinkedHashMap<>();
        Map<String, BigDecimal> recovery = new LinkedHashMap<>();
        List<Dated> receipts = new ArrayList<>();
        int lagDays = DEFAULT_LAG_DAYS;
        boolean anyClaim = false;

        for (Row app : rowsWhere(E_CLIENT_APP, "project_ID", projectId)) {
            // A draft claim is a working paper, not a valuation.
            if (Boolean.FALSE.equals(app.get("IsActiveEntity"))) {
                continue;
            }
            BigDecimal gross = orZero(dec(app.get("approvedGross")));
            if (gross.signum() == 0) {
                gross = orZero(dec(app.get("submittedGross")));
            }
            if (gross.signum() == 0) {
                continue;
            }
            anyClaim = true;
            String periodId = periodCovering(periods, date(app.get("periodEnd")));
            BigDecimal pct = dec(app.get("retentionPct"));
            BigDecimal held = orZero(dec(app.get("retentionAmount")));
            if (held.signum() == 0 && pct != null) {
                held = gross.multiply(pct).divide(HUNDRED, 2, RoundingMode.HALF_UP);
            }
            if (periodId != null) {
                billed.merge(periodId, gross, BigDecimal::add);
                retention.merge(periodId, held, BigDecimal::add);
                retentionRate.put(periodId, pct == null ? DEFAULT_RETENTION_PCT : pct);
                recovery.merge(periodId, orZero(dec(app.get("advanceRecovery"))),
                        BigDecimal::add);
            }

            BigDecimal net = orZero(dec(app.get("netPayable")));
            if (net.signum() == 0) {
                net = gross.subtract(held).subtract(orZero(dec(app.get("advanceRecovery"))));
            }
            LocalDate valued = date(app.get("periodEnd"));
            LocalDate paid = settlementOf(app, valued);
            if (paid != null && net.signum() != 0) {
                receipts.add(new Dated(paid, net));
                if (valued != null) {
                    lagDays = (int) java.time.temporal.ChronoUnit.DAYS.between(valued, paid);
                }
            }
        }

        // No claims yet: value the measured work instead, and assume the terms.
        // Said in the note on each row, because an assumed receipt date is not
        // the same kind of fact as a certificate that names one.
        if (!anyClaim) {
            BigDecimal measured = measuredValueOf(projectId);
            if (measured.signum() > 0) {
                BigDecimal spentTotal = BigDecimal.ZERO;
                for (Dated cost : costs) {
                    spentTotal = spentTotal.add(cost.amount());
                }
                for (Row period : periods) {
                    String periodId = str(period.get("ID"));
                    LocalDate from = date(period.get("startDate"));
                    LocalDate to = date(period.get("endDate"));
                    BigDecimal spent = BigDecimal.ZERO;
                    for (Dated cost : costs) {
                        if (within(cost.on(), from, to)) {
                            spent = spent.add(cost.amount());
                        }
                    }
                    if (spent.signum() == 0 || spentTotal.signum() == 0) {
                        continue;
                    }
                    // Valued in proportion to what the period cost: the bill is
                    // measured against work done, and work done is what the
                    // money was spent on.
                    BigDecimal gross = measured.multiply(spent)
                            .divide(spentTotal, 2, RoundingMode.HALF_UP);
                    BigDecimal held = gross.multiply(DEFAULT_RETENTION_PCT)
                            .divide(HUNDRED, 2, RoundingMode.HALF_UP);
                    billed.merge(periodId, gross, BigDecimal::add);
                    retention.merge(periodId, held, BigDecimal::add);
                    retentionRate.put(periodId, DEFAULT_RETENTION_PCT);
                    if (to != null) {
                        receipts.add(new Dated(to.plusDays(DEFAULT_LAG_DAYS),
                                gross.subtract(held)));
                    }
                }
            }
        }

        // ---- one row per period, in date order, carrying the running totals
        List<Map<String, Object>> out = new ArrayList<>();
        BigDecimal plannedCum = BigDecimal.ZERO;
        BigDecimal actualCum = BigDecimal.ZERO;
        BigDecimal cashInCum = BigDecimal.ZERO;
        BigDecimal position = BigDecimal.ZERO;

        for (Row period : periods) {
            String periodId = str(period.get("ID"));
            LocalDate from = date(period.get("startDate"));
            LocalDate to = date(period.get("endDate"));

            BigDecimal plannedOut = planned.getOrDefault(periodId, BigDecimal.ZERO);
            BigDecimal actualOut = BigDecimal.ZERO;
            for (Dated cost : costs) {
                if (within(cost.on(), from, to)) {
                    actualOut = actualOut.add(cost.amount());
                }
            }
            BigDecimal cashIn = BigDecimal.ZERO;
            for (Dated receipt : receipts) {
                if (within(receipt.on(), from, to)) {
                    cashIn = cashIn.add(receipt.amount());
                }
            }
            BigDecimal billedGross = billed.getOrDefault(periodId, BigDecimal.ZERO);
            // A period with no plan, no spend and no money moving either way
            // is not part of this curve. Emitting it would put a flat run of
            // zeroes either side of every job and leave the chart mostly
            // empty space.
            if (plannedOut.signum() == 0 && actualOut.signum() == 0
                    && cashIn.signum() == 0 && billedGross.signum() == 0) {
                continue;
            }
            plannedCum = plannedCum.add(plannedOut);
            actualCum = actualCum.add(actualOut);
            cashInCum = cashInCum.add(cashIn);

            BigDecimal held = retention.getOrDefault(periodId, BigDecimal.ZERO);
            BigDecimal recovered = recovery.getOrDefault(periodId, BigDecimal.ZERO);
            BigDecimal netMonthly = cashIn.subtract(actualOut);
            position = position.add(netMonthly);

            BigDecimal envelopePct = plannedOut.signum() > 0
                    ? envelope.getOrDefault(periodId, BigDecimal.ZERO)
                            .multiply(HUNDRED).divide(plannedOut, 2, RoundingMode.HALF_UP)
                    : null;

            Map<String, Object> r = new LinkedHashMap<>();
            r.put("ID", UUID.randomUUID().toString());
            r.put("project_ID", projectId);
            r.put("period_ID", periodId);
            r.put("periodName", period.get("name"));
            r.put("startDate", period.get("startDate"));
            r.put("endDate", period.get("endDate"));
            r.put("ccy_code", project.get("ccy_code"));
            r.put("plannedOut", plannedOut);
            r.put("plannedOutCum", plannedCum);
            r.put("actualOut", actualOut);
            r.put("actualOutCum", actualCum);
            r.put("variance", plannedOut.subtract(actualOut));
            r.put("varianceCum", plannedCum.subtract(actualCum));
            r.put("envelopePct", envelopePct);

            r.put("billedGross", billedGross);
            r.put("retentionPct", retentionRate.get(periodId));
            r.put("retentionHeld", held);
            r.put("netCertified", billedGross.subtract(held));
            r.put("retentionRelease", BigDecimal.ZERO);
            r.put("advanceIn", BigDecimal.ZERO);
            r.put("advanceRecovery", recovered);
            r.put("cashIn", cashIn);
            r.put("cashOutSigned", actualOut.negate());
            r.put("cashInCum", cashInCum);
            r.put("lagDays", lagDays);
            r.put("netMonthly", netMonthly);
            r.put("cumPosition", position);
            // Red while the job is funding itself, neutral once it is not.
            // Not amber in between: a position is either below the line or it
            // is not, and a threshold in the middle would be invented.
            r.put("positionCriticality", position.signum() < 0 ? 1 : 3);
            // The one thing a spend curve must not do is read as a forecast
            // while most of it is a straight line, so the row says when it is.
            String note = null;
            if (!anyClaim && billedGross.signum() > 0) {
                note = "No client claim covers this period, so the valuation is "
                        + "measured work and the receipt assumes " + DEFAULT_LAG_DAYS
                        + "-day terms";
            } else if (envelopePct != null && envelopePct.compareTo(HALF) > 0) {
                note = "Most of this period is spread from the programme shape rather "
                        + "than traced to dated work";
            }
            r.put("note", note);
            out.add(r);
        }
        return out;
    }


    /** True where a date falls inside a period, both ends included. */
    private static boolean within(LocalDate on, LocalDate from, LocalDate to) {
        return on != null && from != null && to != null
                && !on.isBefore(from) && !on.isAfter(to);
    }

    /** The period a date falls in, or null where the calendar does not cover it. */
    private static String periodCovering(List<Row> periods, LocalDate on) {
        for (Row period : periods) {
            if (within(on, date(period.get("startDate")), date(period.get("endDate")))) {
                return str(period.get("ID"));
            }
        }
        return null;
    }

    /**
     * When a claim's money arrives: settled, else due, else the terms.
     *
     * In that order because each is a harder fact than the one after it. A
     * settlement date is what happened; a due date is what was agreed; the
     * assumed terms are neither, which is why a row that falls back to them
     * says so in its note.
     */
    private LocalDate settlementOf(Row app, LocalDate valued) {
        for (Row cert : rowsWhere(E_CLIENT_CERT, "application_ID", str(app.get("ID")))) {
            LocalDate settled = date(cert.get("settledOn"));
            if (settled != null) {
                return settled;
            }
        }
        LocalDate due = date(app.get("dueOn"));
        if (due != null) {
            return due;
        }
        return valued == null ? null : valued.plusDays(DEFAULT_LAG_DAYS);
    }

    /** Measured work at contract rates, for a project with no claims yet. */
    private BigDecimal measuredValueOf(String projectId) {
        BigDecimal value = BigDecimal.ZERO;
        for (Row boq : rowsWhere(E_BOQ, "project_ID", projectId)) {
            for (Row item : rowsWhere(E_BOQ_ITEM, "boq_ID", str(boq.get("ID")))) {
                value = value.add(orZero(dec(item.get("cumDoneQty")))
                        .multiply(orZero(dec(item.get("rate")))));
            }
        }
        return value.setScale(2, RoundingMode.HALF_UP);
    }

    /** One cost, and the date it belongs in. */
    private record Dated(LocalDate on, BigDecimal amount) {}

    /** The periods of the calendar governing this company, in date order. */
    private List<Row> periodsFor(String companyId) {
        String calendarId = null;
        if (companyId != null) {
            Row own = one(E_CALENDAR, "company_ID", companyId);
            if (own != null) {
                calendarId = str(own.get("ID"));
            }
        }
        if (calendarId == null) {
            for (Row calendar : db.run(Select.from(E_CALENDAR))) {
                if (Boolean.TRUE.equals(calendar.get("isDefault"))) {
                    calendarId = str(calendar.get("ID"));
                    break;
                }
            }
        }
        List<Row> periods = new ArrayList<>();
        for (Row period : calendarId == null
                ? db.run(Select.from(E_PERIOD))
                : rowsWhere(E_PERIOD, "calendar_ID", calendarId)) {
            if (!Boolean.TRUE.equals(period.get("isAdjustment"))) {
                periods.add(period);
            }
        }
        periods.sort(Comparator.comparing(p -> date(p.get("startDate")),
                Comparator.nullsLast(Comparator.naturalOrder())));
        return periods;
    }

    private Iterable<Row> rowsWhere(String entity, String column, Object value) {
        if (value == null) {
            return List.of();
        }
        String v = String.valueOf(value);
        return db.run(Select.from(entity).where(r -> r.get(column).eq(v)));
    }

    private Row one(String entity, String column, Object value) {
        if (value == null) {
            return null;
        }
        String v = String.valueOf(value);
        return db.run(Select.from(entity).where(r -> r.get(column).eq(v))).first().orElse(null);
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
}
