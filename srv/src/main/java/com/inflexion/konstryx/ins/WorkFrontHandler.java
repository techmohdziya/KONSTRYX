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
import java.time.Instant;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Today's work front: what the job is standing on, who is on it, and what
 * nobody has touched.
 *
 * Recomputed before every read, like the overview and for a stronger reason:
 * a stored row that says "today" is wrong by tomorrow morning, and nothing on
 * the screen would say so.
 *
 * The verdict on each row is the point of the screen. A percentage on its own
 * says nothing - 40 % done is good or terrible depending on where the activity
 * should be - so every front carries the straight line through its own
 * duration beside it, and the drift between the two. QUIET is the state worth
 * building this for: an activity inside its dates, not overdue, nothing
 * visibly wrong, and nobody has signed a day against it in a week.
 */
@Component
@ServiceName("ProjectService")
public class WorkFrontHandler implements EventHandler {

    private static final String E_FRONT = "konstryx.ins.WorkFront";
    private static final String E_PROJECT = "konstryx.prj.Project";
    private static final String E_ACTIVITY = "konstryx.prj.Activity";
    private static final String E_WBS = "konstryx.prj.WBSElement";
    private static final String E_TIMESHEET = "konstryx.mpr.TimesheetEntry";
    private static final String E_LOCATION = "konstryx.prj.SiteLocation";

    private static final BigDecimal HUNDRED = new BigDecimal("100");
    private static final Set<String> DAY_COUNTED = Set.of("Signed", "Posted");
    /** A front is only interesting while it is live or nearly so. */
    private static final int STARTING_WINDOW_DAYS = 7;

    @Autowired
    private PersistenceService db;

    @Before(event = CqnService.EVENT_READ, entity = "ProjectService.WorkFronts")
    @HandlerOrder(HandlerOrder.EARLY)
    public void refresh(CdsReadEventContext context) {
        LocalDate today = LocalDate.now();
        List<Map<String, Object>> rows = new ArrayList<>();

        Map<String, Row> wbsById = new LinkedHashMap<>();
        for (Row wbs : db.run(Select.from(E_WBS))) {
            wbsById.put(str(wbs.get("ID")), wbs);
        }
        Map<String, String> locationById = new LinkedHashMap<>();
        for (Row loc : db.run(Select.from(E_LOCATION))) {
            locationById.put(str(loc.get("ID")),
                    str(loc.get("name") != null ? loc.get("name") : loc.get("code")));
        }
        List<Row> days = new ArrayList<>();
        for (Row day : db.run(Select.from(E_TIMESHEET))) {
            if (DAY_COUNTED.contains(str(day.get("logStatus")))) {
                days.add(day);
            }
        }

        for (Row project : db.run(Select.from(E_PROJECT))) {
            for (Row activity : rowsWhere(E_ACTIVITY, "project_ID", str(project.get("ID")))) {
                Map<String, Object> front =
                        frontOf(project, activity, wbsById, locationById, days, today);
                if (front != null) {
                    rows.add(front);
                }
            }
        }
        db.run(Delete.from(E_FRONT));
        if (!rows.isEmpty()) {
            db.run(Insert.into(E_FRONT).entries(rows));
        }
    }

    private Map<String, Object> frontOf(Row project, Row activity, Map<String, Row> wbsById,
            Map<String, String> locationById, List<Row> days, LocalDate today) {

        // The network's own dates where the critical path has run, the agreed
        // programme where it has not. Nothing here invents a date.
        LocalDate start = firstDate(activity.get("earlyStart"), activity.get("plannedStart"));
        LocalDate finish = firstDate(activity.get("earlyFinish"), activity.get("plannedFinish"));
        BigDecimal percentDone = orZero(dec(activity.get("percentDone")));

        String state = stateOf(start, finish, percentDone, today);
        if (state == null) {
            // Finished and behind it, or not started and far off. A front is
            // what the job is standing on now, and a list that included every
            // activity of a three-year programme would not be one.
            return null;
        }

        String wbsId = str(activity.get("wbs_ID"));
        Row wbs = wbsId == null ? null : wbsById.get(wbsId);
        String activityCode = str(activity.get("code"));

        // ---- who has been on it
        int headsToday = 0;
        int headsWeek = 0;
        BigDecimal hoursToday = BigDecimal.ZERO;
        BigDecimal hoursWeek = BigDecimal.ZERO;
        LocalDate lastWorked = null;
        Set<String> places = new LinkedHashSet<>();
        LocalDate weekAgo = today.minusDays(7);

        for (Row day : days) {
            if (!claims(day, activityCode, wbsId)) {
                continue;
            }
            LocalDate on = date(day.get("workDate"));
            if (on == null) {
                continue;
            }
            if (lastWorked == null || on.isAfter(lastWorked)) {
                lastWorked = on;
            }
            BigDecimal hours = orZero(dec(day.get("regularHrs")))
                    .add(orZero(dec(day.get("otHrs"))));
            int heads = intOf(day.get("headsPresent"));
            if (on.equals(today)) {
                headsToday += heads;
                hoursToday = hoursToday.add(hours);
            }
            if (!on.isBefore(weekAgo)) {
                headsWeek += heads;
                hoursWeek = hoursWeek.add(hours);
                String place = locationById.get(str(day.get("location_ID")));
                if (place != null) {
                    places.add(place);
                }
            }
        }

        // An activity nobody has signed a day against this week is quiet,
        // whatever its percentage says. Applied after the hours are counted
        // because that is the only thing that can tell.
        if ("OPEN".equals(state) && headsWeek == 0) {
            state = "QUIET";
        }

        Map<String, Object> r = new LinkedHashMap<>();
        r.put("ID", UUID.randomUUID().toString());
        r.put("project_ID", project.get("ID"));
        r.put("projectCode", project.get("code"));
        r.put("projectName", project.get("name"));
        r.put("onDate", today);
        r.put("refreshedAt", Instant.now());

        r.put("activity_ID", activity.get("ID"));
        r.put("activityCode", activityCode);
        r.put("activityName", activity.get("name"));
        r.put("wbs_ID", wbsId);
        r.put("wbsCode", wbs == null ? null : wbs.get("code"));
        r.put("wbsName", wbs == null ? null : wbs.get("name"));
        r.put("isCritical", Boolean.TRUE.equals(activity.get("isCritical")));

        r.put("startDate", start);
        r.put("finishDate", finish);
        r.put("durationDays", activity.get("durationDays"));
        r.put("daysElapsed", start == null ? null : (int) ChronoUnit.DAYS.between(start, today));
        r.put("daysRemaining", finish == null ? null : (int) ChronoUnit.DAYS.between(today, finish));
        r.put("totalFloat", activity.get("totalFloat"));

        r.put("percentDone", percentDone);
        BigDecimal expected = expectedPct(start, finish, today);
        r.put("expectedPct", expected);
        r.put("driftPct", expected == null ? null : percentDone.subtract(expected));

        r.put("headsToday", headsToday);
        r.put("hoursToday", hoursToday);
        r.put("headsWeek", headsWeek);
        r.put("hoursWeek", hoursWeek);
        r.put("lastWorkedOn", lastWorked);
        r.put("daysSinceWorked", lastWorked == null ? null
                : (int) ChronoUnit.DAYS.between(lastWorked, today));
        r.put("locations", places.isEmpty() ? null
                : truncate(String.join(", ", places), 255));

        r.put("state", state);
        r.put("stateCriticality", criticalityOf(state));

        List<String> caveats = new ArrayList<>();
        if (activity.get("earlyStart") == null) {
            caveats.add("dates are the agreed programme; no critical path has run");
        }
        if (lastWorked == null) {
            caveats.add("nobody has ever signed a day against this element");
        }
        r.put("note", caveats.isEmpty() ? null : truncate(String.join("; ", caveats), 255));
        return r;
    }

    /**
     * Whether a signed day belongs to this activity.
     *
     * The daily log names its activity as a project-qualified code, so the
     * code is matched on its own and as a suffix. Where the log names no
     * activity the WBS carries it, which is coarser - two activities on one
     * element both claim the day - and deliberately preferred to dropping the
     * hours, because an element with people on it reading as untouched is the
     * worse error.
     */
    private static boolean claims(Row day, String activityCode, String wbsId) {
        String named = str(day.get("activity"));
        if (named != null && activityCode != null && !named.isBlank()) {
            return named.equals(activityCode) || named.endsWith("." + activityCode);
        }
        return wbsId != null && wbsId.equals(str(day.get("wbs_ID")));
    }

    /** Where a straight line through the duration would have the activity today. */
    private static BigDecimal expectedPct(LocalDate start, LocalDate finish, LocalDate today) {
        if (start == null || finish == null || !finish.isAfter(start)) {
            return null;
        }
        if (!today.isAfter(start)) {
            return BigDecimal.ZERO;
        }
        if (!today.isBefore(finish)) {
            return HUNDRED;
        }
        long total = ChronoUnit.DAYS.between(start, finish);
        long done = ChronoUnit.DAYS.between(start, today);
        return BigDecimal.valueOf(done).multiply(HUNDRED)
                .divide(BigDecimal.valueOf(total), 2, RoundingMode.HALF_UP);
    }

    private static String stateOf(LocalDate start, LocalDate finish,
            BigDecimal percentDone, LocalDate today) {
        boolean complete = percentDone.compareTo(HUNDRED) >= 0;
        if (finish != null && today.isAfter(finish)) {
            // Finished work past its date is history, not a front.
            return complete ? null : "OVERDUE";
        }
        if (complete) {
            return "FINISHING";
        }
        if (start != null && today.isBefore(start)) {
            return ChronoUnit.DAYS.between(today, start) <= STARTING_WINDOW_DAYS
                    ? "STARTING" : null;
        }
        // Inside its dates and not finished. Whether it is OPEN or QUIET is
        // decided by the hours, which the caller counts.
        return "OPEN";
    }

    private static int criticalityOf(String state) {
        return switch (state) {
            case "OVERDUE", "QUIET" -> 1;
            case "STARTING" -> 2;
            default -> 3;
        };
    }

    private Iterable<Row> rowsWhere(String entity, String column, Object value) {
        if (value == null) {
            return List.of();
        }
        String v = String.valueOf(value);
        return db.run(Select.from(entity).where(r -> r.get(column).eq(v)));
    }

    private static LocalDate firstDate(Object preferred, Object fallback) {
        LocalDate d = date(preferred);
        return d != null ? d : date(fallback);
    }

    private static int intOf(Object v) {
        if (v instanceof Number n) {
            return n.intValue();
        }
        try {
            return v == null ? 0 : Integer.parseInt(String.valueOf(v));
        } catch (NumberFormatException e) {
            return 0;
        }
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

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max - 1) + "…";
    }
}
