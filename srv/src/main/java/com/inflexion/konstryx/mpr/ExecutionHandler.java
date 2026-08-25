package com.inflexion.konstryx.mpr;

import com.sap.cds.Row;
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
import com.sap.cds.services.request.UserInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/**
 * Site execution: signing a day's work and posting it against the reservation
 * that paid for it.
 *
 * Consumption, cost to date, burn and drift were stored on the reservation
 * line and derived from nothing, so a line could report a burn its own
 * timesheets contradicted. They are computed here from the signed days, and a
 * day nobody has signed is not consumption.
 */
@Component
@ServiceName("WorkflowService")
public class ExecutionHandler implements EventHandler {

    private static final String E_TIMESHEET = "konstryx.mpr.TimesheetEntry";
    private static final String E_MANPOWER_LINE = "konstryx.mpr.ManpowerRequestLine";
    private static final String E_RESERVATION_LINE = "konstryx.wf.ReservationLine";

    private static final BigDecimal HUNDRED = new BigDecimal("100");
    private static final BigDecimal DEFAULT_DAY_HOURS = new BigDecimal("8");

    @Autowired
    private PersistenceService db;

    @Autowired
    private UserInfo userInfo;

    // ----------------------------------------------------------------- sign

    @On(event = "sign")
    public void onSign(EventContext context) {
        Row timesheet = targetOf(context, "Timesheet");
        String id = str(timesheet.get("ID"));

        String status = str(timesheet.get("logStatus"));
        if ("Posted".equalsIgnoreCase(status)) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "This day has already been posted and cannot be signed again.");
        }
        if ("Signed".equalsIgnoreCase(status)) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "This day is already signed.");
        }

        int heads = intOf(timesheet.get("headsPresent"));
        BigDecimal regular = orZero(decimal(timesheet.get("regularHrs")));
        BigDecimal overtime = orZero(decimal(timesheet.get("otHrs")));
        if (heads <= 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A day with nobody present cannot be signed.");
        }
        if (regular.add(overtime).signum() <= 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A day with no hours on it cannot be signed.");
        }

        BigDecimal dayHours = decimal(context.get("standardDayHours"));
        if (dayHours == null || dayHours.signum() <= 0) {
            dayHours = DEFAULT_DAY_HOURS;
        }

        Row line = manpowerLineOf(timesheet);
        BigDecimal rate = line == null ? null : decimal(line.get("ratePerHeadDay"));
        if (rate == null || rate.signum() <= 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The manpower line carries no head-day rate, so this day "
                            + "cannot be costed. Set the rate on the line first.");
        }

        // The rate is all-in per head per day, so hours are converted to
        // head-days against the standard day. Overtime is costed at the same
        // hourly rate: the model holds no premium, and inventing one here
        // would put a commercial decision in the code.
        BigDecimal headDays = regular.add(overtime)
                .divide(dayHours, 6, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(heads));
        BigDecimal cost = headDays.multiply(rate).setScale(2, RoundingMode.HALF_UP);

        Map<String, Object> update = new HashMap<>();
        update.put("costAmount", cost);
        update.put("logStatus", "Signed");
        update.put("signedBy", userName());
        db.run(Update.entity(E_TIMESHEET).data(update).where(t -> t.get("ID").eq(id)));

        return_(context, String.format(
                "%s heads for %s regular and %s overtime hours = %s head-days at %s = %s. Signed by %s.",
                heads, regular.toPlainString(), overtime.toPlainString(),
                headDays.setScale(2, RoundingMode.HALF_UP).toPlainString(),
                rate.toPlainString(), cost.toPlainString(), userName()));
    }

    // ------------------------------------------------------ postConsumption

    @On(event = "postConsumption")
    public void onPostConsumption(EventContext context) {
        Row reservation = targetOf(context, "Reservation");
        String reservationId = str(reservation.get("ID"));

        int linesTouched = 0;
        int daysCounted = 0;
        BigDecimal totalCost = BigDecimal.ZERO;
        StringBuilder detail = new StringBuilder();

        for (Row line : db.run(Select.from(E_RESERVATION_LINE)
                .where(l -> l.get("reservation_ID").eq(reservationId)))) {

            String rrLineId = str(line.get("rrLine_ID"));
            if (rrLineId == null) {
                continue;
            }

            // Head-days, not hours. The reservation line is measured in
            // heads and the cost is derived per head-day, so head-days is the
            // one unit all three agree on. Hours are carried alongside for the
            // report because that is what a site actually records.
            BigDecimal hours = BigDecimal.ZERO;
            BigDecimal headDays = BigDecimal.ZERO;
            BigDecimal cost = BigDecimal.ZERO;
            int days = 0;

            for (Row manpower : db.run(Select.from(E_MANPOWER_LINE)
                    .where(m -> m.get("line_ID").eq(rrLineId)))) {
                String manpowerId = str(manpower.get("ID"));
                BigDecimal lineRate = orZero(decimal(manpower.get("ratePerHeadDay")));
                for (Row day : db.run(Select.from(E_TIMESHEET)
                        .where(t -> t.get("manpowerLine_ID").eq(manpowerId)))) {
                    // Drafts are not consumption. A day nobody has signed is
                    // a claim, not a fact.
                    if (!"Signed".equalsIgnoreCase(str(day.get("logStatus")))
                            && !"Posted".equalsIgnoreCase(str(day.get("logStatus")))) {
                        continue;
                    }
                    BigDecimal dayHours = orZero(decimal(day.get("regularHrs")))
                            .add(orZero(decimal(day.get("otHrs"))));
                    BigDecimal dayCost = orZero(decimal(day.get("costAmount")));
                    hours = hours.add(dayHours);
                    cost = cost.add(dayCost);
                    // Recovered from the cost and the rate it was costed at,
                    // so the head-days always match the money rather than
                    // re-deriving them from hours and a standard day that may
                    // have differed on the day it was signed.
                    if (lineRate.signum() > 0) {
                        headDays = headDays.add(
                                dayCost.divide(lineRate, 6, RoundingMode.HALF_UP));
                    }
                    days++;
                }
            }
            if (days == 0) {
                continue;
            }

            BigDecimal encumbered = orZero(decimal(line.get("encumberedAmount")));
            BigDecimal reservedRate = orZero(decimal(line.get("dailyRate")));
            cost = cost.setScale(2, RoundingMode.HALF_UP);
            hours = hours.setScale(3, RoundingMode.HALF_UP);
            headDays = headDays.setScale(3, RoundingMode.HALF_UP);

            BigDecimal burn = encumbered.signum() == 0 ? BigDecimal.ZERO
                    : cost.multiply(HUNDRED).divide(encumbered, 2, RoundingMode.HALF_UP);

            // Drift is what the consumed work cost against what it was
            // reserved to cost - the same head-days priced at the rate the
            // line was encumbered at. It is only ever non-zero when the rate
            // actually paid differs from the rate reserved, which is exactly
            // the thing worth reporting.
            //
            // It used to prorate the encumbrance by consumed/qty, which
            // compared hours against a quantity measured in heads and
            // produced a drift of millions on a line worth four hundred
            // thousand.
            BigDecimal drift = reservedRate.signum() == 0 ? BigDecimal.ZERO
                    : cost.subtract(headDays.multiply(reservedRate))
                            .setScale(2, RoundingMode.HALF_UP);

            Map<String, Object> update = new HashMap<>();
            update.put("consumedToDate", headDays);
            update.put("costToDate", cost);
            update.put("burnPct", burn);
            update.put("drift", drift);
            update.put("lineStatus", burn.compareTo(HUNDRED) >= 0 ? "Reconciling" : "Consuming");
            String lineId = str(line.get("ID"));
            db.run(Update.entity(E_RESERVATION_LINE).data(update)
                    .where(l -> l.get("ID").eq(lineId)));

            linesTouched++;
            daysCounted += days;
            totalCost = totalCost.add(cost);
            if (detail.length() < 400) {
                detail.append(String.format(
                        " [%s head-days from %s hrs over %d day(s), %s spent, %s%% burn, drift %s]",
                        headDays.toPlainString(), hours.toPlainString(), days,
                        cost.toPlainString(), burn.toPlainString(), drift.toPlainString()));
            }
        }

        if (linesTouched == 0) {
            return_(context, "No signed daily logs stand behind this reservation, "
                    + "so nothing was posted. Sign the days first — a draft is not consumption.");
            return;
        }
        return_(context, String.format(
                "%d line(s) updated from %d signed day(s), %s consumed in total.%s",
                linesTouched, daysCounted,
                totalCost.setScale(2, RoundingMode.HALF_UP).toPlainString(), detail));
    }

    // ---------------------------------------------------------------- helpers

    private Row manpowerLineOf(Row timesheet) {
        Object lineId = timesheet.get("manpowerLine_ID");
        if (lineId == null) {
            return null;
        }
        String id = String.valueOf(lineId);
        return db.run(Select.from(E_MANPOWER_LINE).where(m -> m.get("ID").eq(id)))
                .first().orElse(null);
    }

    private Row targetOf(EventContext context, String label) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        return (select == null ? Optional.<Row>empty() : db.run(select).first())
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        label + " not found."));
    }

    private String userName() {
        String name = userInfo == null ? null : userInfo.getName();
        return isBlank(name) ? "unknown" : name;
    }

    private static void return_(EventContext context, String message) {
        context.put("result", message);
        context.setCompleted();
    }

    private static int intOf(Object value) {
        return value instanceof Number n ? n.intValue() : 0;
    }

    private static BigDecimal orZero(BigDecimal value) {
        return value == null ? BigDecimal.ZERO : value;
    }

    private static BigDecimal decimal(Object value) {
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

    private static boolean isBlank(String s) {
        return s == null || s.isBlank();
    }

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }
}
