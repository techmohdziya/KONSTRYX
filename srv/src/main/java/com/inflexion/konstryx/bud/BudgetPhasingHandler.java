package com.inflexion.konstryx.bud;

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
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Spreads a budget across the periods its work actually falls in.
 *
 * Three figures were missing for one reason, and this is the reason: planned
 * value, the schedule performance index, and any cashflow curve at all. A
 * budget line knew its amount and its CBS, and nothing said which month the
 * amount was meant to go out in, so every one of them was an index of a guess.
 *
 * A line is phased from the programme where it can be traced to dated
 * activities, and spread evenly across the project's own dates where it
 * cannot. The two are told apart on every phase, because a curve built from
 * even spreads is a straight line and reads on a chart exactly like a
 * forecast. A reader who cannot tell which lines are which cannot tell how
 * much of the curve to believe.
 */
@Component
@ServiceName("BudgetService")
public class BudgetPhasingHandler implements EventHandler {

    private static final String E_BUDGET = "konstryx.bud.Budget";
    private static final String E_LINE = "konstryx.bud.BudgetLine";
    private static final String E_PHASE = "konstryx.bud.BudgetPhase";
    private static final String E_ACTIVITY = "konstryx.prj.Activity";
    private static final String E_PROJECT = "konstryx.prj.Project";
    private static final String E_PERIOD = "konstryx.fin.FiscalPeriod";
    private static final String E_CALENDAR = "konstryx.fin.FiscalCalendar";

    private static final String BASIS_PROGRAMME = "PROGRAMME";
    private static final String BASIS_ENVELOPE = "ENVELOPE";

    @Autowired
    private PersistenceService db;

    @On(event = "phaseBudget", entity = "BudgetService.Budgets")
    public void onPhaseBudget(EventContext context) {
        Row budget = targetOf(context);
        String budgetId = str(budget.get("ID"));
        String projectId = str(budget.get("project_ID"));
        if (projectId == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The budget names no project, so there are no dates to phase it over.");
        }
        Row project = one(E_PROJECT, "ID", projectId);
        if (project == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The project this budget belongs to is missing.");
        }
        LocalDate projectStart = date(project.get("startDate"));
        LocalDate projectEnd = date(project.get("endDate"));

        List<Row> periods = periodsFor(str(budget.get("company_ID")));
        if (periods.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "No fiscal periods are defined, so there is nothing to phase into. "
                            + "Generate them on the fiscal calendar first.");
        }

        // Activities, once, grouped by the WBS they sit on. A line resolves its
        // own WBS against this rather than querying per line.
        Map<String, List<Row>> activitiesByWbs = new LinkedHashMap<>();
        for (Row activity : rowsWhere(E_ACTIVITY, "project_ID", projectId)) {
            String wbs = str(activity.get("wbs_ID"));
            if (wbs != null) {
                activitiesByWbs.computeIfAbsent(wbs, k -> new ArrayList<>()).add(activity);
            }
        }

        List<Map<String, Object>> phases = new ArrayList<>();
        int programmeLines = 0;
        int envelopeLines = 0;
        int unphased = 0;

        for (Row line : rowsWhere(E_LINE, "budget_ID", budgetId)) {
            BigDecimal amount = dec(line.get("amount"));
            if (amount == null || amount.signum() == 0) {
                continue;
            }
            List<Row> activities = activitiesByWbs.getOrDefault(str(line.get("wbs_ID")), List.of());

            Map<Row, BigDecimal> weights = activities.isEmpty()
                    ? envelopeWeights(periods, projectStart, projectEnd)
                    : programmeWeights(periods, activities);
            String basis = activities.isEmpty() ? BASIS_ENVELOPE : BASIS_PROGRAMME;

            // A line whose work falls entirely outside every defined period has
            // no month to go in. Counted and reported rather than dropped into
            // the nearest one, which would put money in a month nothing happens.
            if (weights.isEmpty()) {
                unphased++;
                continue;
            }
            if (BASIS_PROGRAMME.equals(basis)) {
                programmeLines++;
            } else {
                envelopeLines++;
            }
            phases.addAll(split(line, budget, projectId, amount, weights, basis));
        }

        // Replaces rather than adds: re-phasing a budget that was already
        // phased must leave one curve behind it, not two summed together.
        db.run(Delete.from(E_PHASE).where(p -> p.get("budget_ID").eq(budgetId)));
        if (!phases.isEmpty()) {
            db.run(Insert.into(E_PHASE).entries(phases));
        }

        String message = String.format(
                "%s phased into %d period rows: %d line(s) from the programme, "
                        + "%d spread as an envelope%s.",
                budget.get("docNo"), phases.size(), programmeLines, envelopeLines,
                unphased == 0 ? "" : String.format(
                        ", %d line(s) left unphased - their work falls outside every "
                                + "defined fiscal period", unphased));
        context.put("result", message);
        context.setCompleted();
    }

    /**
     * Weight per period from the activities themselves: the days of each
     * activity that fall inside each period.
     *
     * Days rather than activity count, so a six-month activity carries six
     * times the money of a one-month one instead of the same share, and so an
     * activity spanning a month boundary puts part of its cost either side of
     * it rather than all of it in whichever month it started.
     */
    private Map<Row, BigDecimal> programmeWeights(List<Row> periods, List<Row> activities) {
        Map<Row, BigDecimal> weights = new LinkedHashMap<>();
        for (Row period : periods) {
            LocalDate periodStart = date(period.get("startDate"));
            LocalDate periodEnd = date(period.get("endDate"));
            long days = 0;
            for (Row activity : activities) {
                days += overlapDays(date(activity.get("plannedStart")),
                        date(activity.get("plannedFinish")), periodStart, periodEnd);
            }
            if (days > 0) {
                weights.put(period, BigDecimal.valueOf(days));
            }
        }
        return weights;
    }

    /** Even across the project's own dates, for a line no activity claims. */
    private Map<Row, BigDecimal> envelopeWeights(List<Row> periods, LocalDate start, LocalDate end) {
        Map<Row, BigDecimal> weights = new LinkedHashMap<>();
        if (start == null || end == null) {
            return weights;
        }
        for (Row period : periods) {
            long days = overlapDays(start, end,
                    date(period.get("startDate")), date(period.get("endDate")));
            if (days > 0) {
                weights.put(period, BigDecimal.valueOf(days));
            }
        }
        return weights;
    }

    /**
     * The line's amount across its periods, in proportion to the weights.
     *
     * The last period takes the remainder rather than its own rounded share,
     * so the phases of a line sum to the line exactly. A curve that is a few
     * fils short of its own budget invites the reader to work out which of the
     * two is wrong, and the answer is neither.
     */
    private List<Map<String, Object>> split(Row line, Row budget, String projectId,
            BigDecimal amount, Map<Row, BigDecimal> weights, String basis) {
        BigDecimal total = weights.values().stream()
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        List<Map<String, Object>> out = new ArrayList<>();
        BigDecimal assigned = BigDecimal.ZERO;
        int remaining = weights.size();

        for (Map.Entry<Row, BigDecimal> entry : weights.entrySet()) {
            remaining--;
            BigDecimal share = remaining == 0
                    ? amount.subtract(assigned)
                    : amount.multiply(entry.getValue())
                            .divide(total, 2, RoundingMode.HALF_UP);
            assigned = assigned.add(share);

            Row period = entry.getKey();
            Map<String, Object> phase = new LinkedHashMap<>();
            phase.put("ID", UUID.randomUUID().toString());
            phase.put("line_ID", line.get("ID"));
            phase.put("project_ID", projectId);
            phase.put("budget_ID", budget.get("ID"));
            phase.put("period_ID", period.get("ID"));
            phase.put("periodName", period.get("name"));
            phase.put("startDate", period.get("startDate"));
            phase.put("amount", share);
            phase.put("basis", basis);
            out.add(phase);
        }
        return out;
    }

    /** Days of [aStart, aEnd] that fall inside [bStart, bEnd], both inclusive. */
    private static long overlapDays(LocalDate aStart, LocalDate aEnd,
            LocalDate bStart, LocalDate bEnd) {
        if (aStart == null || aEnd == null || bStart == null || bEnd == null) {
            return 0;
        }
        LocalDate from = aStart.isAfter(bStart) ? aStart : bStart;
        LocalDate to = aEnd.isBefore(bEnd) ? aEnd : bEnd;
        return from.isAfter(to) ? 0 : ChronoUnit.DAYS.between(from, to) + 1;
    }

    /**
     * The periods of the calendar that governs this company, in date order;
     * the group default where the company names none of its own.
     */
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
            // An adjustment period is a place to book a correction, not a month
            // work happens in; phasing into it would put budget in a thirteenth
            // month that no activity can ever earn against.
            if (!Boolean.TRUE.equals(period.get("isAdjustment"))) {
                periods.add(period);
            }
        }
        periods.sort(Comparator.comparing(p -> date(p.get("startDate")),
                Comparator.nullsLast(Comparator.naturalOrder())));
        return periods;
    }

    // ---------------------------------------------------------------- helpers

    private Row targetOf(EventContext context) {
        Object cqn = context.get("cqn");
        if (cqn instanceof com.sap.cds.ql.cqn.CqnSelect select) {
            return db.run(select).first().orElseThrow(() -> new ServiceException(
                    ErrorStatuses.NOT_FOUND, "Budget not found."));
        }
        throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                "This action has to be called on one budget.");
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
