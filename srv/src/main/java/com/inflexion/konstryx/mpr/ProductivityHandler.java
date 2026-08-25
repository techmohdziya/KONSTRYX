package com.inflexion.konstryx.mpr;

import com.sap.cds.Row;
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
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Output per man-hour, per site location.
 *
 * This is the number a site is actually run on, and it was not computable —
 * not for want of arithmetic, but because a daily log had nowhere to record
 * where the crew worked. A productivity figure for a whole project tells a
 * project manager nothing they can act on; the same figure per floor tells
 * them which floor is losing money this week.
 *
 * Two halves have to meet on the location. The man-hours come from signed
 * daily logs — hours per head multiplied by heads present, because a daily log
 * records a shift length and a headcount, not a crew total — and the installed
 * quantity from the bill lines allocated there. Rows
 * are returned even when one half is missing, because the asymmetry is the
 * finding: hours against no measured output is work being paid for that
 * nothing has claimed, and it is the most useful row on the screen.
 */
@Component
@ServiceName("WorkflowService")
public class ProductivityHandler implements EventHandler {

    private static final String E_LOCATION = "konstryx.prj.SiteLocation";
    private static final String E_TIMESHEET = "konstryx.mpr.TimesheetEntry";
    private static final String E_ALLOCATION = "konstryx.prj.Allocation";
    private static final String E_BOQ_ITEM = "konstryx.prj.BOQItem";
    private static final String E_MANPOWER_LINE = "konstryx.mpr.ManpowerRequestLine";
    private static final String E_SNAPSHOT = "konstryx.mpr.ProductivitySnapshot";

    @Autowired
    private PersistenceService db;

    @On(event = "productivity")
    public void onProductivity(EventContext context) {
        String projectId = str(context.get("projectID"));
        if (projectId == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A project is needed — productivity is only meaningful within one.");
        }

        Map<String, Row> locations = new LinkedHashMap<>();
        for (Row row : db.run(Select.from(E_LOCATION)
                .where(l -> l.get("project_ID").eq(projectId)))) {
            locations.put(str(row.get("ID")), row);
        }
        if (locations.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "This project has no site locations, so there is nothing to measure "
                            + "productivity against. Define its buildings, floors and zones first.");
        }

        // The rate a day was costed at, kept so head-days can be recovered from
        // the money rather than re-derived from hours and a standard day that
        // may have differed on the day it was signed.
        Map<String, BigDecimal> lineRates = new HashMap<>();
        for (Row line : db.run(Select.from(E_MANPOWER_LINE))) {
            lineRates.put(str(line.get("ID")), orZero(decimal(line.get("ratePerHeadDay"))));
        }

        Map<String, Tally> tallies = new LinkedHashMap<>();
        for (String id : locations.keySet()) {
            tallies.put(id, new Tally());
        }

        for (Row day : db.run(Select.from(E_TIMESHEET))) {
            String locationId = str(day.get("location_ID"));
            Tally tally = locationId == null ? null : tallies.get(locationId);
            if (tally == null) {
                continue;
            }
            // A draft day is a claim, not a fact. Counting it would flatter the
            // rate, because the hours arrive before anyone stands behind them.
            String status = str(day.get("logStatus"));
            if (!"Signed".equalsIgnoreCase(status) && !"Posted".equalsIgnoreCase(status)) {
                continue;
            }
            // regularHrs and otHrs are hours PER HEAD, not crew totals - the
            // costing multiplies by headsPresent to reach head-days, and a
            // sign message reads "5 heads for 8.00 regular ... = 5.00
            // head-days". Man-hours are therefore hours x heads. Summing the
            // raw hours counted a five-man day as eight man-hours and made
            // output per hour five times too good.
            BigDecimal perHead = orZero(decimal(day.get("regularHrs")))
                    .add(orZero(decimal(day.get("otHrs"))));
            BigDecimal hours = perHead.multiply(
                    BigDecimal.valueOf(intOf(day.get("headsPresent"))));
            BigDecimal cost = orZero(decimal(day.get("costAmount")));
            BigDecimal rate = lineRates.getOrDefault(str(day.get("manpowerLine_ID")), BigDecimal.ZERO);

            tally.days++;
            tally.hours = tally.hours.add(hours);
            tally.cost = tally.cost.add(cost);
            if (rate.signum() > 0) {
                tally.headDays = tally.headDays.add(cost.divide(rate, 6, RoundingMode.HALF_UP));
            }
        }

        // Installed quantity: what the bill lines allocated to this location
        // report as done. cumDoneQty is measured work, not the contract
        // quantity — productivity has to be against what was actually built.
        Map<String, Row> boqItems = new HashMap<>();
        for (Row item : db.run(Select.from(E_BOQ_ITEM))) {
            boqItems.put(str(item.get("ID")), item);
        }
        for (Row allocation : db.run(Select.from(E_ALLOCATION))) {
            String locationId = str(allocation.get("location_ID"));
            Tally tally = locationId == null ? null : tallies.get(locationId);
            if (tally == null) {
                continue;
            }
            Row item = boqItems.get(str(allocation.get("boqItem_ID")));
            if (item == null) {
                continue;
            }
            BigDecimal done = orZero(decimal(item.get("cumDoneQty")));
            if (done.signum() == 0) {
                continue;
            }
            // The allocation carries this location's share of the bill line, so
            // the measured quantity is apportioned by it rather than counted
            // whole against every location the line touches.
            BigDecimal share = orZero(decimal(allocation.get("allocPct")));
            BigDecimal quantity = share.signum() > 0
                    ? done.multiply(share).divide(new BigDecimal("100"), 3, RoundingMode.HALF_UP)
                    : orZero(decimal(allocation.get("allocQty")));
            tally.installed = tally.installed.add(quantity);
            if (tally.uom == null) {
                tally.uom = str(item.get("uom"));
            }
            tally.mixedUom |= tally.uom != null && !tally.uom.equals(str(item.get("uom")));
        }

        List<Map<String, Object>> out = new ArrayList<>();
        for (Map.Entry<String, Row> entry : locations.entrySet()) {
            Tally tally = tallies.get(entry.getKey());
            Row location = entry.getValue();
            if (tally.days == 0 && tally.installed.signum() == 0) {
                continue;     // nothing has happened here at all
            }

            Map<String, Object> row = new LinkedHashMap<>();
            row.put("locationID", entry.getKey());
            row.put("locationCode", location.get("code"));
            row.put("locationName", location.get("name"));
            row.put("locationType", location.get("locationType"));
            row.put("signedDays", tally.days);
            row.put("headDays", tally.headDays.setScale(3, RoundingMode.HALF_UP));
            row.put("labourHours", tally.hours.setScale(2, RoundingMode.HALF_UP));
            row.put("labourCost", tally.cost.setScale(2, RoundingMode.HALF_UP));
            row.put("installedQty", tally.installed.setScale(3, RoundingMode.HALF_UP));
            row.put("uom", tally.uom);

            String note;
            if (tally.hours.signum() == 0) {
                row.put("outputPerHour", null);
                row.put("costPerUnit", null);
                note = "Measured work with no signed hours against it.";
            } else if (tally.installed.signum() == 0) {
                row.put("outputPerHour", null);
                row.put("costPerUnit", null);
                note = "Hours signed but nothing measured as installed yet.";
            } else {
                row.put("outputPerHour",
                        tally.installed.divide(tally.hours, 4, RoundingMode.HALF_UP));
                row.put("costPerUnit",
                        tally.cost.divide(tally.installed, 2, RoundingMode.HALF_UP));
                note = tally.mixedUom
                        ? "Quantities span more than one unit of measure; the rate mixes them."
                        : "";
            }
            row.put("note", note);
            out.add(row);
        }

        // Each measurement is kept. A rate on its own answers far less than the
        // same rate falling for three weeks, and a figure recomputed later can
        // never be compared with what was reported last month - the hours and
        // quantities behind it have moved since.
        Instant takenAt = Instant.now();
        for (Map<String, Object> row : out) {
            Map<String, Object> snapshot = new LinkedHashMap<>(row);
            snapshot.put("ID", UUID.randomUUID().toString());
            snapshot.put("project_ID", projectId);
            snapshot.put("location_ID", snapshot.remove("locationID"));
            snapshot.put("takenAt", takenAt);
            db.run(Insert.into(E_SNAPSHOT).entry(snapshot));
        }

        context.put("result", out);
        context.setCompleted();
    }

    /** What has accumulated against one location. */
    private static final class Tally {
        int days = 0;
        BigDecimal hours = BigDecimal.ZERO;
        BigDecimal headDays = BigDecimal.ZERO;
        BigDecimal cost = BigDecimal.ZERO;
        BigDecimal installed = BigDecimal.ZERO;
        String uom = null;
        /**
         * Bill lines in different units allocated to one location. The rate is
         * still returned, because suppressing it hides the work — but it is
         * flagged, because square metres added to cubic metres is not a
         * quantity and the number must not be read as one.
         */
        boolean mixedUom = false;
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

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }
}
