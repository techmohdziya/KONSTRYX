package com.inflexion.konstryx.sys;

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

/**
 * The numbers the launchpad tiles show.
 *
 * A tile that reads only its own name makes a launchpad a menu. A tile that
 * reads "3 lines over budget" in red is the reason someone opens that app
 * rather than another one, and it is the difference between a home page and a
 * list of links.
 *
 * Two rules run through all of these. A count is never the whole story, so
 * every tile carries the count and the thing worth knowing about it — a
 * reservation tile says how many reservations exist and how many are
 * overspending. And a state is computed from the number rather than fixed: a
 * tile whose colour never changes tells a reader nothing its title did not.
 */
@Component
@ServiceName("CollaborationService")
public class LaunchpadKpiHandler implements EventHandler {

    private static final String E_PROJECT = "konstryx.prj.Project";
    private static final String E_BOQ = "konstryx.prj.BOQ";
    private static final String E_BUDGET_LINE = "konstryx.bud.BudgetLine";
    private static final String E_RR = "konstryx.wf.ResourceRequest";
    private static final String E_RESERVATION_LINE = "konstryx.wf.ReservationLine";
    private static final String E_TIMESHEET = "konstryx.mpr.TimesheetEntry";
    private static final String E_SNAPSHOT = "konstryx.mpr.ProductivitySnapshot";
    private static final String E_CERTIFICATE = "konstryx.scr.PaymentCertificate";
    private static final String E_REQUISITION = "konstryx.mat.PurchaseRequisition";
    private static final String E_RESOURCE = "konstryx.master.ResourceNode";
    private static final String E_MATERIAL = "konstryx.master.Material";
    private static final String E_VENDOR = "konstryx.master.Vendor";
    private static final String E_RATE = "konstryx.fin.ExchangeRate";

    private static final BigDecimal HUNDRED = new BigDecimal("100");

    @Autowired
    private PersistenceService db;

    @On(event = "launchpadKpis")
    public void onKpis(EventContext context) {
        List<Map<String, Object>> tiles = new ArrayList<>();

        // ---- planning ----------------------------------------------------
        long projects = count(E_PROJECT);
        long unsynced = countWhere(E_PROJECT, r -> !"SENT".equalsIgnoreCase(str(r.get("syncStatus"))));
        tiles.add(tile("KonstryxProject", "Projects", projects, "projects",
                "Setup, WBS and schedule",
                unsynced == 0 ? "Positive" : "Critical",
                unsynced == 0 ? "All reached S/4" : unsynced + " not yet in S/4"));

        BigDecimal contractValue = sum(E_BOQ, "contractValue");
        tiles.add(tile("KonstryxBOQ", "Bills of Quantities",
                contractValue.divide(new BigDecimal("1000000"), 2, RoundingMode.HALF_UP),
                "M AED", "Contract value on the bills", "Neutral",
                count(E_BOQ) + " bill(s)"));

        // A budget line that has spent more than it holds is the one number a
        // controller opens the app for.
        long overspent = countWhere(E_BUDGET_LINE, r -> {
            BigDecimal available = decimal(r.get("available"));
            return available != null && available.signum() < 0;
        });
        tiles.add(tile("KonstryxBudget", "Budgets", count(E_BUDGET_LINE), "lines",
                "Lines and encumbrance",
                overspent == 0 ? "Positive" : "Negative",
                overspent == 0 ? "Every line within budget"
                        : overspent + " line(s) over budget"));

        // ---- sourcing ----------------------------------------------------
        long awaiting = countWhere(E_RR, r -> {
            String status = str(r.get("status"));
            return status != null && status.toLowerCase().contains("approval");
        });
        tiles.add(tile("KonstryxResourceRequest", "Resource Requests", count(E_RR),
                "requests", "The RR spine of the chain",
                awaiting == 0 ? "Neutral" : "Critical",
                awaiting == 0 ? "None awaiting approval"
                        : awaiting + " awaiting approval"));

        long notSent = countWhere(E_REQUISITION,
                r -> str(r.get("prNo")) == null || str(r.get("prNo")).isBlank());
        tiles.add(tile("KonstryxPurchaseRequisition", "Purchase Requisitions",
                count(E_REQUISITION), "requisitions", "Raised to S/4",
                notSent == 0 ? "Positive" : "Critical",
                notSent == 0 ? "All have an S/4 number"
                        : notSent + " without an S/4 number"));

        // ---- execution ---------------------------------------------------
        long burning = countWhere(E_RESERVATION_LINE, r -> {
            BigDecimal burn = decimal(r.get("burnPct"));
            return burn != null && burn.compareTo(HUNDRED) > 0;
        });
        tiles.add(tile("KonstryxReservation", "Reservations",
                count(E_RESERVATION_LINE), "lines", "Reserved and encumbered",
                burning == 0 ? "Positive" : "Negative",
                burning == 0 ? "None over its encumbrance"
                        : burning + " line(s) over encumbrance"));

        long drafts = countWhere(E_TIMESHEET,
                r -> "Draft".equalsIgnoreCase(str(r.get("logStatus"))));
        tiles.add(tile("KonstryxTimesheet", "Daily Logs", count(E_TIMESHEET), "days",
                "Site attendance and hours",
                drafts == 0 ? "Positive" : "Critical",
                drafts == 0 ? "Every day signed"
                        : drafts + " day(s) unsigned"));

        // Productivity leads with the slowest location, because the average
        // across a project is a number nobody can act on.
        Row worst = null;
        BigDecimal worstRate = null;
        for (Row row : db.run(Select.from(E_SNAPSHOT))) {
            BigDecimal rate = decimal(row.get("outputPerHour"));
            if (rate == null || rate.signum() <= 0) {
                continue;
            }
            if (worstRate == null || rate.compareTo(worstRate) < 0) {
                worstRate = rate;
                worst = row;
            }
        }
        tiles.add(tile("KonstryxProductivity", "Productivity",
                worstRate == null ? BigDecimal.ZERO : worstRate, "per hour",
                "Output per man-hour",
                worstRate == null ? "Neutral" : "Critical",
                worst == null ? "Nothing measured yet"
                        : "Slowest: " + str(worst.get("locationCode"))));

        // ---- commercial --------------------------------------------------
        long rejected = countWhere(E_CERTIFICATE,
                r -> "Rejected".equalsIgnoreCase(str(r.get("status"))));
        BigDecimal certified = sum(E_CERTIFICATE, "netCertified");
        tiles.add(tile("KonstryxPaymentCertificate", "Payment Certificates",
                certified.divide(new BigDecimal("1000"), 0, RoundingMode.HALF_UP),
                "K AED net", "Subcontractor certification",
                rejected == 0 ? "Positive" : "Negative",
                rejected == 0 ? count(E_CERTIFICATE) + " certificate(s)"
                        : rejected + " rejected"));

        // ---- master data -------------------------------------------------
        tiles.add(tile("KonstryxResource", "Resources", count(E_RESOURCE), "resources",
                "Resource catalogue", "Neutral", "RBS L1 to L5"));
        tiles.add(tile("KonstryxMaterial", "Materials", count(E_MATERIAL), "materials",
                "Material master from S/4", "Neutral", "Mirrored from S/4"));
        tiles.add(tile("KonstryxVendor", "Vendors", count(E_VENDOR), "vendors",
                "Supplier master from S/4", "Neutral", "Mirrored from S/4"));
        long rates = count(E_RATE);
        tiles.add(tile("KonstryxExchangeRate", "Exchange Rates", rates, "rates",
                "Rates by pair and type",
                rates == 0 ? "Critical" : "Neutral",
                rates == 0 ? "None maintained — conversion will refuse"
                        : "Contract, budget and spot"));

        context.put("result", tiles);
        context.setCompleted();
    }

    // ---------------------------------------------------------------- helpers

    private Map<String, Object> tile(String semanticObject, String title, long number,
                                     String unit, String subtitle, String state,
                                     String info) {
        return tile(semanticObject, title, BigDecimal.valueOf(number), unit, subtitle,
                state, info);
    }

    private Map<String, Object> tile(String semanticObject, String title,
                                     BigDecimal number, String unit, String subtitle,
                                     String state, String info) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("tile", semanticObject);
        row.put("title", title);
        row.put("number", number.setScale(2, RoundingMode.HALF_UP));
        row.put("numberUnit", unit);
        row.put("subtitle", subtitle);
        row.put("state", state);
        row.put("info", info);
        return row;
    }

    private long count(String entity) {
        long n = 0;
        for (Row ignored : db.run(Select.from(entity))) {
            n++;
        }
        return n;
    }

    private long countWhere(String entity, java.util.function.Predicate<Row> test) {
        long n = 0;
        for (Row row : db.run(Select.from(entity))) {
            if (test.test(row)) {
                n++;
            }
        }
        return n;
    }

    private BigDecimal sum(String entity, String column) {
        BigDecimal total = BigDecimal.ZERO;
        for (Row row : db.run(Select.from(entity))) {
            BigDecimal value = decimal(row.get(column));
            if (value != null) {
                total = total.add(value);
            }
        }
        return total;
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
