package com.inflexion.konstryx.fin;

import com.sap.cds.Row;
import com.sap.cds.ql.Delete;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
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

import java.time.LocalDate;
import java.time.format.TextStyle;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * The period grid, and the answer to "which period is this date in".
 *
 * Every time-phased figure in the product has to bucket into the same periods
 * — cashflow into months, EVM's planned and earned value into a series, a
 * certificate into a cut-off. Each module deriving its own definition is how
 * two reports on the same month come to disagree by three days, which is
 * exactly enough to move a certificate from one period into the next.
 */
@Component
@ServiceName("AdminService")
public class FiscalCalendarHandler implements EventHandler {

    private static final String E_CALENDAR = "konstryx.fin.FiscalCalendar";
    private static final String E_PERIOD = "konstryx.fin.FiscalPeriod";
    private static final String E_COMPANY = "konstryx.admin.Company";

    @Autowired
    private PersistenceService db;

    // ------------------------------------------------------------- generate

    @On(event = "generate")
    public void onGenerate(EventContext context) {
        Row calendar = targetOf(context);
        String calendarId = str(calendar.get("ID"));

        Integer fiscalYear = intOrNull(context.get("fiscalYear"));
        if (fiscalYear == null || fiscalYear < 1900 || fiscalYear > 2999) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A fiscal year between 1900 and 2999 is needed.");
        }
        boolean replace = Boolean.TRUE.equals(context.get("replace"));

        List<Row> existing = new ArrayList<>();
        for (Row period : db.run(Select.from(E_PERIOD)
                .where(p -> p.get("calendar_ID").eq(calendarId)))) {
            if (fiscalYear.equals(intOrNull(period.get("fiscalYear")))) {
                existing.add(period);
            }
        }
        if (!existing.isEmpty() && !replace) {
            throw new ServiceException(ErrorStatuses.CONFLICT, String.format(
                    "FY%d already has %d period(s) on this calendar. Regenerating "
                            + "would reopen any that are closed, so it has to be asked "
                            + "for: set replace to do it deliberately.",
                    fiscalYear, existing.size()));
        }
        // Refuse to regenerate over a closed period even when asked. A closed
        // period is a statement that its numbers are final, and quietly
        // reopening one is how a reported month changes after it was reported.
        for (Row period : existing) {
            if ("CLOSED".equalsIgnoreCase(str(period.get("status")))) {
                throw new ServiceException(ErrorStatuses.CONFLICT, String.format(
                        "%s is closed. Reopen it before the year can be regenerated — "
                                + "a closed period's figures have already been reported.",
                        str(period.get("name"))));
            }
        }
        if (!existing.isEmpty()) {
            db.run(Delete.from(E_PERIOD).where(p -> p.get("calendar_ID").eq(calendarId)
                    .and(p.get("fiscalYear").eq(fiscalYear))));
        }

        String variant = str(calendar.get("variant"));
        int startMonth = Optional.ofNullable(intOrNull(calendar.get("startMonth"))).orElse(1);
        if (startMonth < 1 || startMonth > 12) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The calendar's start month must be between 1 and 12.");
        }

        List<Map<String, Object>> periods = "FOUR_FOUR_FIVE".equalsIgnoreCase(variant)
                ? fourFourFive(calendarId, fiscalYear, startMonth)
                : calendarMonths(calendarId, fiscalYear, startMonth);

        assertContiguous(periods, fiscalYear);
        for (Map<String, Object> period : periods) {
            db.run(Insert.into(E_PERIOD).entry(period));
        }

        Map<String, Object> first = periods.get(0);
        Map<String, Object> last = periods.get(periods.size() - 1);
        return_(context, String.format(
                "FY%d generated: %d periods from %s to %s%s.",
                fiscalYear, periods.size(), first.get("startDate"), last.get("endDate"),
                existing.isEmpty() ? "" : ", replacing " + existing.size() + " existing"));
    }

    /** Twelve calendar months from the fiscal year's opening month. */
    private List<Map<String, Object>> calendarMonths(String calendarId, int fiscalYear,
                                                     int startMonth) {
        List<Map<String, Object>> out = new ArrayList<>();
        // A fiscal year that opens in a month other than January spans two
        // calendar years, and it is named for the one it ends in.
        LocalDate cursor = startMonth == 1
                ? LocalDate.of(fiscalYear, 1, 1)
                : LocalDate.of(fiscalYear - 1, startMonth, 1);
        for (int periodNo = 1; periodNo <= 12; periodNo++) {
            LocalDate end = cursor.withDayOfMonth(cursor.lengthOfMonth());
            out.add(period(calendarId, fiscalYear, periodNo, cursor, end, false));
            cursor = end.plusDays(1);
        }
        return out;
    }

    /**
     * The 4-4-5 retail pattern: quarters of four, four and five weeks.
     *
     * Periods are whole weeks, so they do not align to month ends — which is
     * the point of the variant, not a defect in it. The year is 52 weeks and
     * runs from the first configured weekday on or after the opening month's
     * first day.
     */
    private List<Map<String, Object>> fourFourFive(String calendarId, int fiscalYear,
                                                   int startMonth) {
        List<Map<String, Object>> out = new ArrayList<>();
        LocalDate anchor = startMonth == 1
                ? LocalDate.of(fiscalYear, 1, 1)
                : LocalDate.of(fiscalYear - 1, startMonth, 1);
        LocalDate cursor = anchor;
        int[] weeks = {4, 4, 5, 4, 4, 5, 4, 4, 5, 4, 4, 5};
        for (int periodNo = 1; periodNo <= 12; periodNo++) {
            LocalDate end = cursor.plusWeeks(weeks[periodNo - 1]).minusDays(1);
            out.add(period(calendarId, fiscalYear, periodNo, cursor, end, false));
            cursor = end.plusDays(1);
        }
        return out;
    }

    private Map<String, Object> period(String calendarId, int fiscalYear, int periodNo,
                                       LocalDate start, LocalDate end, boolean adjustment) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("ID", UUID.randomUUID().toString());
        row.put("calendar_ID", calendarId);
        row.put("fiscalYear", fiscalYear);
        row.put("periodNo", periodNo);
        row.put("name", String.format("FY%02d P%02d - %s %d",
                fiscalYear % 100, periodNo,
                start.getMonth().getDisplayName(TextStyle.SHORT, Locale.ENGLISH),
                start.getYear()));
        row.put("startDate", start);
        row.put("endDate", end);
        row.put("status", "OPEN");
        row.put("isAdjustment", adjustment);
        return row;
    }

    /**
     * Every day of the year falls in exactly one period, or nothing is written.
     *
     * A generated set is rejected whole rather than written and flagged: a gap
     * between two periods is invisible until something dated into it drops out
     * of every report, and by then it has been there for months.
     */
    private void assertContiguous(List<Map<String, Object>> periods, int fiscalYear) {
        for (int i = 1; i < periods.size(); i++) {
            LocalDate previousEnd = (LocalDate) periods.get(i - 1).get("endDate");
            LocalDate start = (LocalDate) periods.get(i).get("startDate");
            if (!start.equals(previousEnd.plusDays(1))) {
                throw new ServiceException(ErrorStatuses.CONFLICT, String.format(
                        "FY%d would have a %s between %s and %s. Nothing was written.",
                        fiscalYear,
                        start.isAfter(previousEnd.plusDays(1)) ? "gap" : "overlap",
                        previousEnd, start));
            }
        }
    }

    // ------------------------------------------------------------ periodFor

    @On(event = "periodFor")
    public void onPeriodFor(EventContext context) {
        String companyId = str(context.get("companyID"));
        LocalDate onDate = date(context.get("onDate"));
        if (onDate == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, "A date is needed.");
        }

        Row calendar = calendarFor(companyId);
        if (calendar == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "No fiscal calendar governs this company, and none is marked as the "
                            + "group default. An administrator must define one.");
        }
        String calendarId = str(calendar.get("ID"));

        for (Row period : db.run(Select.from(E_PERIOD)
                .where(p -> p.get("calendar_ID").eq(calendarId)))) {
            LocalDate start = date(period.get("startDate"));
            LocalDate end = date(period.get("endDate"));
            if (start == null || end == null) {
                continue;
            }
            if (!onDate.isBefore(start) && !onDate.isAfter(end)) {
                Map<String, Object> out = new LinkedHashMap<>();
                out.put("periodID", period.get("ID"));
                out.put("name", period.get("name"));
                out.put("fiscalYear", period.get("fiscalYear"));
                out.put("periodNo", period.get("periodNo"));
                out.put("startDate", start);
                out.put("endDate", end);
                out.put("status", period.get("status"));
                context.put("result", out);
                context.setCompleted();
                return;
            }
        }
        throw new ServiceException(ErrorStatuses.BAD_REQUEST, String.format(
                "%s falls outside every period on calendar %s. Generate the fiscal "
                        + "year that covers it.", onDate, str(calendar.get("code"))));
    }

    /**
     * The calendar governing a company: its own if it has one, otherwise the
     * group default. A company-specific calendar wins, the same way a
     * company-specific approval scheme does.
     */
    private Row calendarFor(String companyId) {
        Row groupWide = null;
        for (Row calendar : db.run(Select.from(E_CALENDAR))) {
            String owner = str(calendar.get("company_ID"));
            if (companyId != null && companyId.equals(owner)) {
                return calendar;
            }
            if (owner == null && (groupWide == null
                    || Boolean.TRUE.equals(calendar.get("isDefault")))) {
                groupWide = calendar;
            }
        }
        return groupWide;
    }

    // ---------------------------------------------------------------- helpers

    private Row targetOf(EventContext context) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        return (select == null ? Optional.<Row>empty() : db.run(select).first())
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "Fiscal calendar not found."));
    }

    private static void return_(EventContext context, String message) {
        context.put("result", message);
        context.setCompleted();
    }

    private static Integer intOrNull(Object value) {
        return value instanceof Number n ? n.intValue() : null;
    }

    private static LocalDate date(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof LocalDate d) {
            return d;
        }
        try {
            return LocalDate.parse(String.valueOf(value));
        } catch (RuntimeException e) {
            return null;
        }
    }

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }
}
