package com.inflexion.konstryx.ins;

import com.inflexion.konstryx.fin.CurrencyService;
import com.sap.cds.Row;
import com.sap.cds.ql.Delete;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
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
import java.math.RoundingMode;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Cost value reconciliation: what the project is worth, what it has cost, and
 * what it will cost, measured for one period and kept.
 *
 * Kept rather than recomputed, which is what makes it a report. A margin on
 * its own says far less than the same margin falling for three months, and a
 * figure recomputed later cannot be compared with what was reported at the
 * time, because the quantities and the hours behind it have moved since.
 *
 * Three rules hold the numbers honest, and each of them is a decision that
 * could have gone the other way:
 *
 *   Only approved variations count. A submitted claim is a negotiating
 *   position, and letting one into the adjusted value makes the margin depend
 *   on the client agreeing something they have not agreed. What is still
 *   being argued goes in the note.
 *
 *   Cost to complete is priced at what the work has actually cost, not at
 *   what it was budgeted to cost. A job running at 1.10 finishes at 1.10
 *   unless something changes, and re-pricing the remainder at the budget is
 *   how a forecast stays green until the month it cannot.
 *
 *   Planned value comes only from a phased budget. Where the budget has not
 *   been phased there is no planned value, no schedule variance and no SPI -
 *   nulls with the reason on the row, because a schedule index computed from
 *   an assumption is indistinguishable on a board pack from one computed from
 *   a programme.
 */
@Component
@ServiceName("ProjectService")
public class ReconcileHandler implements EventHandler {

    private static final String E_REPORT = "konstryx.ins.ProjectPeriodReport";
    private static final String E_PROJECT = "konstryx.prj.Project";
    private static final String E_COMPANY = "konstryx.admin.Company";
    private static final String E_GROUP = "konstryx.admin.CompanyGroup";
    private static final String E_PERIOD = "konstryx.fin.FiscalPeriod";
    private static final String E_CALENDAR = "konstryx.fin.FiscalCalendar";
    private static final String E_BOQ = "konstryx.prj.BOQ";
    private static final String E_BOQ_ITEM = "konstryx.prj.BOQItem";
    private static final String E_VO = "konstryx.vo.VariationOrder";
    private static final String E_VO_LINE = "konstryx.vo.VariationLine";
    private static final String E_BUDGET = "konstryx.bud.Budget";
    private static final String E_BUDGET_LINE = "konstryx.bud.BudgetLine";
    private static final String E_PHASE = "konstryx.bud.BudgetPhase";
    private static final String E_WBS = "konstryx.prj.WBSElement";
    private static final String E_TIMESHEET = "konstryx.mpr.TimesheetEntry";
    private static final String E_PULL = "konstryx.mat.PullRequest";
    private static final String E_INVOICE = "konstryx.mat.SupplierInvoice";
    private static final String E_PAYMENT_CERT = "konstryx.scr.PaymentCertificate";

    private static final BigDecimal HUNDRED = new BigDecimal("100");
    private static final Set<String> DAY_COUNTED = Set.of("Signed", "Posted");

    @Autowired
    private PersistenceService db;

    @Autowired
    private CurrencyService currency;

    @On(event = "reconcile", entity = "ProjectService.Projects")
    public void onReconcile(EventContext context) {
        Row project = targetOf(context);
        String projectId = str(project.get("ID"));
        LocalDate onDate = date(context.get("onDate"));
        if (onDate == null) {
            onDate = LocalDate.now();
        }

        Row period = periodOn(str(project.get("company_ID")), onDate);
        if (period == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, String.format(
                    "No fiscal period covers %s. Generate the year on the fiscal "
                            + "calendar before reconciling into it.", onDate));
        }
        LocalDate periodEnd = date(period.get("endDate"));
        List<String> caveats = new ArrayList<>();

        Map<String, Object> r = new LinkedHashMap<>();
        r.put("ID", UUID.randomUUID().toString());
        r.put("project_ID", projectId);
        r.put("period_ID", period.get("ID"));
        r.put("periodName", period.get("name"));
        r.put("takenAt", Instant.now());

        // ------------------------------------------------------ what it is worth
        BigDecimal contractValue = BigDecimal.ZERO;
        Set<String> boqIds = new HashSet<>();
        for (Row boq : rowsWhere(E_BOQ, "project_ID", projectId)) {
            boqIds.add(str(boq.get("ID")));
            contractValue = contractValue.add(orZero(dec(boq.get("contractValue"))));
        }

        // Approved only, and the omissions subtract. A variation that omits work
        // reduces what the job is worth, and summing its lines without a sign
        // would report an omission as extra revenue.
        BigDecimal variations = BigDecimal.ZERO;
        int approvedVOs = 0;
        BigDecimal claimedNotApproved = BigDecimal.ZERO;
        int openVOs = 0;
        for (Row vo : rowsWhere(E_VO, "project_ID", projectId)) {
            BigDecimal value = BigDecimal.ZERO;
            for (Row line : rowsWhere(E_VO_LINE, "variation_ID", str(vo.get("ID")))) {
                BigDecimal lineValue = orZero(dec(line.get("qty")))
                        .multiply(orZero(dec(line.get("revenueRate"))))
                        .setScale(2, RoundingMode.HALF_UP);
                if ("OMIT".equalsIgnoreCase(str(line.get("changeType")))) {
                    lineValue = lineValue.negate();
                }
                value = value.add(lineValue);
            }
            if ("Approved".equalsIgnoreCase(str(vo.get("status")))) {
                approvedVOs++;
                variations = variations.add(value);
            } else if (!"Rejected".equalsIgnoreCase(str(vo.get("status")))) {
                openVOs++;
                claimedNotApproved = claimedNotApproved.add(value);
            }
        }
        BigDecimal adjustedValue = contractValue.add(variations);
        r.put("contractValue", contractValue);
        r.put("variations", variations);
        r.put("adjustedValue", adjustedValue);
        if (openVOs > 0) {
            caveats.add(String.format(
                    "%d variation(s) worth %s are claimed but not approved and are "
                            + "excluded from the adjusted value", openVOs,
                    claimedNotApproved.setScale(2, RoundingMode.HALF_UP).toPlainString()));
        }

        // -------------------------------------------------------- earned value
        // Measured work at contract rates: the quantity the bill says has been
        // built, priced at the rate it was sold at.
        BigDecimal earnedValue = BigDecimal.ZERO;
        int measuredItems = 0;
        int totalItems = 0;
        for (String boqId : boqIds) {
            for (Row item : rowsWhere(E_BOQ_ITEM, "boq_ID", boqId)) {
                totalItems++;
                BigDecimal done = orZero(dec(item.get("cumDoneQty")));
                if (done.signum() > 0) {
                    measuredItems++;
                }
                earnedValue = earnedValue.add(
                        done.multiply(orZero(dec(item.get("rate")))).setScale(2, RoundingMode.HALF_UP));
            }
        }
        r.put("earnedValue", earnedValue);
        r.put("percentComplete", pct(earnedValue, adjustedValue, 2));

        // ---------------------------------------------------------- earned cost
        // The same work priced at what it was budgeted to cost. A budget line
        // carries its BOQ item where the cost mapping gave it one, so the
        // budgeted cost of work performed is that line's amount at the item's
        // own measured percentage.
        BigDecimal earnedCost = BigDecimal.ZERO;
        BigDecimal costedScope = BigDecimal.ZERO;
        boolean anyCosted = false;
        for (Row budget : rowsWhere(E_BUDGET, "project_ID", projectId)) {
            for (Row line : rowsWhere(E_BUDGET_LINE, "budget_ID", str(budget.get("ID")))) {
                String itemId = str(line.get("boqItem_ID"));
                if (itemId == null) {
                    continue;
                }
                Row item = one(E_BOQ_ITEM, "ID", itemId);
                if (item == null) {
                    continue;
                }
                anyCosted = true;
                BigDecimal amount = orZero(dec(line.get("amount")));
                costedScope = costedScope.add(amount);
                earnedCost = earnedCost.add(amount
                        .multiply(orZero(dec(item.get("cumDonePct"))))
                        .divide(HUNDRED, 2, RoundingMode.HALF_UP));
            }
        }
        r.put("earnedCost", anyCosted ? earnedCost : null);
        if (totalItems > 0 && measuredItems < totalItems) {
            caveats.add(String.format(
                    "%d of %d bill items carry no measured quantity, so the earned value "
                            + "is of what has been measured rather than of what is built",
                    totalItems - measuredItems, totalItems));
        }

        // ---------------------------------------------------------- actual cost
        Set<String> projectWbs = new HashSet<>();
        for (Row wbs : rowsWhere(E_WBS, "project_ID", projectId)) {
            projectWbs.add(str(wbs.get("ID")));
        }
        BigDecimal signedLabour = BigDecimal.ZERO;
        for (Row day : db.run(Select.from(E_TIMESHEET))) {
            if (projectWbs.contains(str(day.get("wbs_ID")))
                    && DAY_COUNTED.contains(str(day.get("logStatus")))) {
                signedLabour = signedLabour.add(orZero(dec(day.get("costAmount"))));
            }
        }
        BigDecimal stockIssued = BigDecimal.ZERO;
        for (Row pull : rowsWhere(E_PULL, "project_ID", projectId)) {
            stockIssued = stockIssued.add(orZero(dec(pull.get("issuedValue"))));
        }
        // Bought-and-billed and subcontracted-and-certified reach cost directly,
        // without passing through a reservation line, which is why they are not
        // one of the two halves above.
        BigDecimal invoiced = BigDecimal.ZERO;
        for (Row invoice : rowsWhere(E_INVOICE, "project_ID", projectId)) {
            invoiced = invoiced.add(orZero(dec(invoice.get("netAmount"))));
        }
        BigDecimal certified = BigDecimal.ZERO;
        for (Row cert : rowsWhere(E_PAYMENT_CERT, "project_ID", projectId)) {
            certified = certified.add(orZero(dec(cert.get("netCertified"))));
        }

        BigDecimal actualCost = signedLabour.add(stockIssued).add(invoiced).add(certified);
        r.put("signedLabourCost", signedLabour);
        r.put("stockIssuedCost", stockIssued);
        r.put("actualCost", actualCost);
        r.put("costToDate", actualCost);
        r.put("costVariance", earnedValue.subtract(actualCost));

        // An index needs both halves. Nothing earned yet is not an index of
        // zero - it is no index at all, and 0.0000 in this column reads as a
        // job that has spent money and built nothing, which is a different and
        // much worse statement than "not measured yet".
        BigDecimal cpi = actualCost.signum() > 0 && earnedValue.signum() > 0
                ? earnedValue.divide(actualCost, 4, RoundingMode.HALF_UP)
                : null;
        r.put("cpi", cpi);

        // The index with the margin taken out of it, which is the one a cost
        // report is actually asking about.
        BigDecimal costCPI = anyCosted && actualCost.signum() > 0 && earnedCost.signum() > 0
                ? earnedCost.divide(actualCost, 4, RoundingMode.HALF_UP)
                : null;
        r.put("costCPI", costCPI);
        if (!anyCosted) {
            caveats.add("no budget line carries a bill item, so no work can be priced at "
                    + "what it was budgeted to cost and there is no cost CPI");
        }

        // A budget far below the bill it prices is the usual reason a revenue
        // index looks impossible, and it is a finding about the budget rather
        // than about the site. Said here because the two indices disagreeing by
        // this much is the first thing a reader will ask about.
        if (contractValue.signum() > 0 && costedScope.signum() > 0) {
            BigDecimal impliedMargin = pct(contractValue.subtract(budgetTotalOf(projectId)),
                    contractValue, 1);
            if (impliedMargin != null && impliedMargin.compareTo(new BigDecimal("40")) > 0) {
                caveats.add(String.format(
                        "the budget is only %s%% of the bill, an implied margin of %s%% - "
                                + "the budget does not cover the whole priced scope, which "
                                + "is why the revenue index reads far above the cost one",
                        pct(budgetTotalOf(projectId), contractValue, 1).toPlainString(),
                        impliedMargin.toPlainString()));
            }
        }
        if (actualCost.signum() == 0) {
            caveats.add("no cost is booked against this project, so there is no cost "
                    + "index and no forecast");
        } else if (earnedValue.signum() == 0) {
            caveats.add("nothing is measured as built, so there is no cost index: the "
                    + "cost above is real, the absence of an index is not a zero");
        }

        // A cost index this far above 1 on a construction job almost always
        // means the cost is only partly captured rather than that the job is
        // earning three times what it spends. The projection deliberately
        // colours it neutral instead of green and leaves the explaining to this
        // note, so the note has to name which categories are actually empty.
        if (cpi != null && cpi.compareTo(new BigDecimal("1.15")) > 0) {
            List<String> missing = new ArrayList<>();
            if (signedLabour.signum() == 0) {
                missing.add("signed labour");
            }
            if (stockIssued.signum() == 0) {
                missing.add("stock issued");
            }
            if (invoiced.signum() == 0) {
                missing.add("supplier invoices");
            }
            if (certified.signum() == 0) {
                missing.add("subcontract certificates");
            }
            caveats.add(String.format(
                    "a cost index of %s means cost is only partly captured, not that "
                            + "the job earns %sx what it spends%s",
                    cpi.toPlainString(), cpi.setScale(1, RoundingMode.HALF_UP).toPlainString(),
                    missing.isEmpty()
                            ? " - every cost category has some value, so the gap is within them"
                            : " - nothing is booked to " + String.join(", ", missing)));
        }

        // --------------------------------------------------------- planned value
        // Every period that has already begun, which is what "planned to date"
        // means: a period still running has had its money planned into it.
        BigDecimal plannedValue = BigDecimal.ZERO;
        int phases = 0;
        int envelopePhases = 0;
        for (Row phase : rowsWhere(E_PHASE, "project_ID", projectId)) {
            LocalDate phaseStart = date(phase.get("startDate"));
            if (phaseStart == null || periodEnd == null || phaseStart.isAfter(periodEnd)) {
                continue;
            }
            phases++;
            if ("ENVELOPE".equalsIgnoreCase(str(phase.get("basis")))) {
                envelopePhases++;
            }
            plannedValue = plannedValue.add(orZero(dec(phase.get("amount"))));
        }
        if (phases == 0) {
            r.put("plannedValue", null);
            r.put("scheduleVariance", null);
            r.put("spi", null);
            caveats.add("the budget is not phased, so there is no planned value, no "
                    + "schedule variance and no SPI - run phaseBudget on the budget");
        } else {
            r.put("plannedValue", plannedValue);
            r.put("scheduleVariance", earnedValue.subtract(plannedValue));
            // Same rule as the cost index: an unmeasured job has no schedule
            // index, and 0.0000 would report one.
            r.put("spi", plannedValue.signum() > 0 && earnedValue.signum() > 0
                    ? earnedValue.divide(plannedValue, 4, RoundingMode.HALF_UP) : null);
            if (envelopePhases > 0) {
                caveats.add(String.format(
                        "%d of %d phase rows behind the planned value are even spreads "
                                + "rather than programme-driven, so the schedule index is "
                                + "firmer on some lines than others", envelopePhases, phases));
            }
        }

        // ------------------------------------------------------------- forecast
        // The remaining value, priced at what work has actually cost so far.
        BigDecimal costToComplete = null;
        if (earnedValue.signum() > 0 && actualCost.signum() > 0) {
            BigDecimal remaining = adjustedValue.subtract(earnedValue);
            costToComplete = remaining.multiply(actualCost)
                    .divide(earnedValue, 2, RoundingMode.HALF_UP);
        }
        r.put("costToComplete", costToComplete);

        BigDecimal forecastCost = costToComplete == null ? null : actualCost.add(costToComplete);
        BigDecimal forecastMargin = forecastCost == null ? null : adjustedValue.subtract(forecastCost);
        r.put("forecastCost", forecastCost);
        r.put("forecastMargin", forecastMargin);
        r.put("forecastMarginPct", forecastMargin == null ? null
                : pct(forecastMargin, adjustedValue, 2));

        // ------------------------------------------------------ both currencies
        String companyCcy = str(project.get("ccy_code"));
        r.put("companyCcy_code", companyCcy);

        Row group = groupOf(str(project.get("company_ID")));
        String groupCcy = group == null ? null : str(group.get("reportingCcy_code"));
        String rateType = group == null ? null : str(group.get("reportingRateType"));
        if (rateType == null) {
            rateType = "AVERAGE";
        }
        r.put("groupCcy_code", groupCcy);
        r.put("rateType", rateType);

        if (groupCcy != null && companyCcy != null) {
            // convertOrPass, not convert: a reconciliation must not fail because
            // a rate is missing. It reports UNCONVERTED instead, and the note
            // says so, so nobody reads a company figure as a group one.
            CurrencyService.Conversion probe = currency.convertOrPass(
                    adjustedValue, companyCcy, groupCcy, rateType, date(period.get("endDate")));
            r.put("rateApplied", probe.rate());
            r.put("adjustedValueGroup", probe.amount());
            r.put("forecastCostGroup", forecastCost == null ? null
                    : currency.convertOrPass(forecastCost, companyCcy, groupCcy, rateType,
                            date(period.get("endDate"))).amount());
            r.put("forecastMarginGroup", forecastMargin == null ? null
                    : currency.convertOrPass(forecastMargin, companyCcy, groupCcy, rateType,
                            date(period.get("endDate"))).amount());
            if ("UNCONVERTED".equals(probe.source())) {
                caveats.add(String.format(
                        "no %s rate covers %s to %s on this date, so the group figures "
                                + "repeat the company ones unconverted",
                        rateType, companyCcy, groupCcy));
            }
        }

        r.put("note", caveats.isEmpty() ? null
                : truncate(capitalise(String.join("; ", caveats)), 2000));

        // One report per project per period: reconciling the same period again
        // replaces the measurement rather than filing a second one beside it.
        String periodId = str(period.get("ID"));
        db.run(Delete.from(E_REPORT).where(x -> x.get("project_ID").eq(projectId)
                .and(x.get("period_ID").eq(periodId))));
        db.run(Insert.into(E_REPORT).entry(r));

        context.put("result", String.format(
                "%s reconciled for %s: worth %s, earned %s, spent %s%s.",
                project.get("code"), period.get("name"),
                adjustedValue.setScale(2, RoundingMode.HALF_UP).toPlainString(),
                earnedValue.setScale(2, RoundingMode.HALF_UP).toPlainString(),
                actualCost.setScale(2, RoundingMode.HALF_UP).toPlainString(),
                forecastMargin == null ? "" : ", forecast margin "
                        + forecastMargin.setScale(2, RoundingMode.HALF_UP).toPlainString()));
        context.setCompleted();
    }

    // ---------------------------------------------------------------- helpers

    /** Everything this project's budgets add up to. */
    private BigDecimal budgetTotalOf(String projectId) {
        BigDecimal total = BigDecimal.ZERO;
        for (Row budget : rowsWhere(E_BUDGET, "project_ID", projectId)) {
            total = total.add(orZero(dec(budget.get("totalAmount"))));
        }
        return total;
    }

    /** The period of this company's calendar that contains the date. */
    private Row periodOn(String companyId, LocalDate onDate) {
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
        for (Row period : calendarId == null
                ? db.run(Select.from(E_PERIOD))
                : rowsWhere(E_PERIOD, "calendar_ID", calendarId)) {
            if (Boolean.TRUE.equals(period.get("isAdjustment"))) {
                continue;
            }
            LocalDate start = date(period.get("startDate"));
            LocalDate end = date(period.get("endDate"));
            if (start != null && end != null
                    && !onDate.isBefore(start) && !onDate.isAfter(end)) {
                return period;
            }
        }
        return null;
    }

    private Row groupOf(String companyId) {
        Row company = one(E_COMPANY, "ID", companyId);
        if (company == null) {
            return null;
        }
        Row group = one(E_GROUP, "ID", company.get("group_ID"));
        if (group != null) {
            return group;
        }
        return db.run(Select.from(E_GROUP)).first().orElse(null);
    }

    private Row targetOf(EventContext context) {
        Object cqn = context.get("cqn");
        if (cqn instanceof com.sap.cds.ql.cqn.CqnSelect select) {
            return db.run(select).first().orElseThrow(() -> new ServiceException(
                    ErrorStatuses.NOT_FOUND, "Project not found."));
        }
        throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                "This action has to be called on one project.");
    }

    private Iterable<Row> rowsWhere(String entity, String column, Object value) {
        if (value == null) {
            return List.of();
        }
        String v = String.valueOf(value);
        return db.run(Select.from(entity).where(x -> x.get(column).eq(v)));
    }

    private Row one(String entity, String column, Object value) {
        if (value == null) {
            return null;
        }
        String v = String.valueOf(value);
        return db.run(Select.from(entity).where(x -> x.get(column).eq(v))).first().orElse(null);
    }

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
        return s.length() <= max ? s : s.substring(0, max - 1) + "…";
    }
}
