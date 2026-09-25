package com.inflexion.konstryx.bil;

import com.sap.cds.CdsData;
import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.cqn.CqnAnalyzer;
import com.sap.cds.ql.cqn.CqnInsert;
import com.sap.cds.ql.Update;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.draft.DraftService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.After;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * A measured line, filled in from what it points at.
 *
 * A quantity surveyor measuring a period types one number per item: how much
 * of it was built. Everything else on the line already exists somewhere and
 * typing it again is how two records of the same thing start to disagree. The
 * rate, the description, the unit and the contract quantity belong to the bill
 * item; the prior quantity belongs to the claims that came before; the value
 * is the quantity times the rate and the cumulative percentage follows from
 * both. None of it is a judgement, so none of it should be re-keyed.
 *
 * The header is the sum of its lines, and it is never typed either. A claim
 * whose gross disagrees with the lines beneath it is the single most common
 * reason a certificate is disputed, and the discrepancy is always found by
 * the person paying rather than the person claiming.
 *
 * Both paths are covered: editing the claim in its draft, where a surveyor
 * works through a period item by item, and editing a line on its own, which
 * the service allows so that remeasuring one item does not mean opening and
 * re-activating the whole claim.
 */
@Component
@ServiceName("BillingService")
public class BillingHandler implements EventHandler {

    private static final String E_APP = "konstryx.bil.PaymentApplication";
    private static final String E_LINE = "konstryx.bil.PaymentApplicationLine";
    /**
     * The same line while somebody is still editing it.
     *
     * Named after the service entity rather than the database one, because that
     * is what CAP calls the table it keeps drafts in. A draft row has no active
     * twin until the claim is saved, so a lookup by key against the active
     * table finds nothing. Reading the stored row is how
     * this handler fills in what a PATCH left out - the rate, the item, the
     * parent - and against a draft it was finding none of them, so correcting
     * a quantity repriced nothing.
     */
    private static final String E_LINE_DRAFT = "BillingService.PaymentApplicationLines_drafts";
    private static final String E_BOQ_ITEM = "konstryx.prj.BOQItem";
    private static final String E_VO_LINE = "konstryx.vo.VariationLine";

    private static final BigDecimal HUNDRED = new BigDecimal("100");

    @Autowired
    private PersistenceService db;

    @Autowired
    private com.sap.cds.services.runtime.CdsRuntime runtime;

    // ------------------------------------------------------------- the line

    /**
     * Fill the line from what it points at, then price it.
     *
     * Registered for the plain writes and for the draft ones, because the same
     * line is edited both ways and a figure that appears only after activation
     * is a figure the person typing never sees.
     */
    @Before(event = { CqnService.EVENT_CREATE, CqnService.EVENT_UPDATE,
                      DraftService.EVENT_DRAFT_NEW, DraftService.EVENT_DRAFT_PATCH },
            entity = "BillingService.PaymentApplicationLines")
    public void deriveLine(EventContext context, List<CdsData> lines) {
        // A line created through its claim - POST .../PaymentApplications(..)/lines,
        // which is what the app does - carries no parent in its payload. CAP sets
        // it from the navigation after the handlers run, so without this the
        // prior quantity had no chain to look down and stayed empty.
        String fromPath = parentFromPath(context);
        for (CdsData line : lines) {
            if (fromPath != null && line.get("parent_ID") == null) {
                line.put("parent_ID", fromPath);
            }
            deriveLine(line);
        }
    }

    /**
     * The claim named in the request path, where the request came through one.
     *
     * Asked of the model rather than parsed out of the URL: CqnAnalyzer knows
     * which segment is the root and which key identifies it, and a path that
     * does not have one simply answers nothing.
     */
    private String parentFromPath(EventContext context) {
        try {
            Object cqn = context.get("cqn");
            if (!(cqn instanceof CqnInsert insert) || insert.ref() == null) {
                return null;
            }
            Map<String, Object> keys = CqnAnalyzer.create(runtime.getCdsModel())
                    .analyze(insert.ref()).rootKeys();
            Object id = keys == null ? null : keys.get("ID");
            return id == null ? null : String.valueOf(id);
        } catch (RuntimeException e) {
            // The request did not come through a navigation, or came in a form
            // this cannot read. The payload then has to carry the parent, and
            // where it does not the line keeps no prior quantity rather than
            // guessing at one.
            return null;
        }
    }

    private void deriveLine(CdsData line) {
        String id = str(line.get("ID"));
        Row stored = id == null ? null : storedLine(id);

        // What the line is measuring. A bill item where the work was sold, a
        // variation line where it was added afterwards - a claim carries both,
        // and the reader should not have to know which to get a rate.
        String itemId = str(merged(line, stored, "boqItem_ID"));
        String voLineId = str(merged(line, stored, "variationLine_ID"));
        Row source = itemId != null ? one(E_BOQ_ITEM, itemId)
                   : voLineId != null ? one(E_VO_LINE, voLineId) : null;

        BigDecimal rate = dec(merged(line, stored, "rate"));
        BigDecimal contractQty = dec(merged(line, stored, "contractQty"));

        if (source != null) {
            // Copied only where the line is silent. A surveyor who has typed a
            // rate has a reason - a remeasure at a provisional rate, a star
            // rate agreed on site - and overwriting it would discard the one
            // number on the line that was a decision.
            boolean isVariation = itemId == null;
            copyIfAbsent(line, "itemNo", source.get(isVariation ? "lineNo" : "itemNo"));
            copyIfAbsent(line, "description", source.get("description"));
            copyIfAbsent(line, "uom", source.get("uom"));
            if (rate == null) {
                rate = dec(source.get(isVariation ? "revenueRate" : "rate"));
                line.put("rate", rate);
            }
            if (contractQty == null) {
                contractQty = dec(source.get("qty"));
                line.put("contractQty", contractQty);
            }
        }

        BigDecimal proposedQty = dec(merged(line, stored, "proposedQty"));
        BigDecimal qsQty = dec(merged(line, stored, "qsQty"));
        BigDecimal approvedQty = dec(merged(line, stored, "approvedQty"));

        // Each stage prices its own quantity at the same rate. The stages differ
        // on how much was built, never on what it is worth per unit.
        if (rate != null) {
            if (proposedQty != null) { line.put("proposedValue", money(proposedQty, rate)); }
            if (qsQty != null) { line.put("qsValue", money(qsQty, rate)); }
            if (approvedQty != null) { line.put("approvedValue", money(approvedQty, rate)); }
        }

        // What every earlier claim established for this item. Read from the
        // chain rather than carried forward by hand, so a reader comparing it
        // against the previous claim finds the same number.
        String parentId = str(merged(line, stored, "parent_ID"));
        String measuring = itemId != null ? itemId : voLineId;
        BigDecimal prior = priorQty(parentId, measuring, id);
        if (prior != null) {
            line.put("priorQty", prior);
        }

        // Where the item now stands: what came before plus what this claim
        // settles on, which is the approved quantity once there is one and the
        // surveyor's before that.
        BigDecimal thisPeriod = approvedQty != null ? approvedQty
                              : qsQty != null ? qsQty : proposedQty;
        if (thisPeriod != null) {
            BigDecimal cum = orZero(prior).add(thisPeriod);
            line.put("cumQty", cum);
            if (contractQty != null && contractQty.signum() != 0) {
                line.put("cumPct", cum.multiply(HUNDRED)
                        .divide(contractQty, 2, RoundingMode.HALF_UP));
            }
        }
    }

    /**
     * What earlier claims on this project already measured of one item.
     *
     * Earlier by the period measured, not by the date somebody typed it: claims
     * are raised late and corrected out of order, and a prior quantity that
     * depended on entry order would change when a clerk went back to fix a
     * typo. The line being edited is excluded so that re-saving it does not
     * count its own quantity as its own history.
     */
    private BigDecimal priorQty(String parentId, String measuring, String selfId) {
        if (parentId == null || measuring == null) {
            return null;
        }
        Row parent = one(E_APP, parentId);
        if (parent == null) {
            return null;
        }
        LocalDate until = date(parent.get("periodEnd"));
        String projectId = str(parent.get("project_ID"));
        BigDecimal prior = BigDecimal.ZERO;

        for (Row claim : db.run(Select.from(E_APP)
                .where(a -> a.get("project_ID").eq(projectId)))) {
            String claimId = str(claim.get("ID"));
            if (claimId == null || claimId.equals(parentId)) {
                continue;
            }
            LocalDate end = date(claim.get("periodEnd"));
            if (until != null && (end == null || !end.isBefore(until))) {
                continue;
            }
            for (Row other : db.run(Select.from(E_LINE)
                    .where(l -> l.get("parent_ID").eq(claimId)))) {
                if (selfId != null && selfId.equals(str(other.get("ID")))) {
                    continue;
                }
                if (!measuring.equals(str(other.get("boqItem_ID")))
                        && !measuring.equals(str(other.get("variationLine_ID")))) {
                    continue;
                }
                BigDecimal q = dec(other.get("approvedQty"));
                if (q == null) { q = dec(other.get("qsQty")); }
                if (q == null) { q = dec(other.get("proposedQty")); }
                prior = prior.add(orZero(q));
            }
        }
        return prior;
    }

    // ----------------------------------------------------------- the header

    /**
     * The claim totals its lines, after they have been written.
     *
     * After rather than before, because the sum has to include the line that
     * has just changed, and before the write it is still the old one.
     */
    @After(event = { CqnService.EVENT_CREATE, CqnService.EVENT_UPDATE,
                     CqnService.EVENT_DELETE },
           entity = "BillingService.PaymentApplicationLines")
    public void totalAfterLineWrite(EventContext context, List<CdsData> lines) {
        lines.stream()
                .map(this::parentOf)
                .filter(p -> p != null)
                .distinct()
                .forEach(this::total);
    }

    /**
     * Which claim a written line belongs to.
     *
     * A PATCH carries only what changed. Someone correcting a quantity sends
     * that quantity and nothing else, so the parent has to be read from the
     * stored row - taken from the payload alone it was null, the total never
     * ran, and the claim went on reporting a gross its own lines no longer
     * added up to.
     */
    private String parentOf(CdsData line) {
        String parent = str(line.get("parent_ID"));
        if (parent != null) {
            return parent;
        }
        String id = str(line.get("ID"));
        Row stored = id == null ? null : storedLine(id);
        return stored == null ? null : str(stored.get("parent_ID"));
    }

    /** And again when a claim edited in its draft is saved. */
    @After(event = DraftService.EVENT_DRAFT_SAVE, entity = "BillingService.PaymentApplications")
    public void totalAfterSave(EventContext context, List<CdsData> apps) {
        apps.stream()
                .map(a -> str(a.get("ID")))
                .filter(id -> id != null)
                .forEach(this::total);
    }

    /**
     * Gross at each stage is the sum of the lines at that stage; retention is
     * the rate applied to what was approved; net payable is what is left.
     *
     * Nothing here is accepted from the client. A header typed over its lines
     * is a claim that will be certified for a different figure than it asked
     * for, and neither party will know which was meant.
     */
    private void total(String appId) {
        Row app = one(E_APP, appId);
        if (app == null) {
            return;
        }
        BigDecimal proposed = BigDecimal.ZERO, qs = BigDecimal.ZERO, approved = BigDecimal.ZERO;
        boolean anyApproved = false, anyQs = false, any = false;

        for (Row line : db.run(Select.from(E_LINE).where(l -> l.get("parent_ID").eq(appId)))) {
            any = true;
            proposed = proposed.add(orZero(dec(line.get("proposedValue"))));
            BigDecimal q = dec(line.get("qsValue"));
            if (q != null) { anyQs = true; qs = qs.add(q); }
            BigDecimal ap = dec(line.get("approvedValue"));
            if (ap != null) { anyApproved = true; approved = approved.add(ap); }
        }
        if (!any) {
            return;
        }

        Map<String, Object> patch = new HashMap<>();
        patch.put("proposedGross", proposed);
        patch.put("qsReviewedGross", anyQs ? qs : null);
        patch.put("approvedGross", anyApproved ? approved : null);

        // The gross the deductions come off: what was approved once a
        // consultant has approved something, and what the surveyor made of it
        // before that. A retention held against a figure nobody has agreed
        // would move when they agreed it.
        BigDecimal basis = anyApproved ? approved : anyQs ? qs : proposed;
        BigDecimal pct = dec(app.get("retentionPct"));
        BigDecimal retention = pct == null ? orZero(dec(app.get("retentionAmount")))
                : basis.multiply(pct).divide(HUNDRED, 2, RoundingMode.HALF_UP);
        BigDecimal recovery = orZero(dec(app.get("advanceRecovery")));
        BigDecimal other = orZero(dec(app.get("otherDeductions")));

        patch.put("retentionAmount", retention);
        patch.put("netPayable", basis.subtract(retention).subtract(recovery).subtract(other));

        db.run(Update.entity(E_APP).data(patch).where(a -> a.get("ID").eq(appId)));
    }

    // ---------------------------------------------------------------- helpers

    private Row one(String entity, String id) {
        return db.run(Select.from(entity).where(e -> e.get("ID").eq(id))).first().orElse(null);
    }

    /** A line wherever it currently lives: activated, or still in a draft. */
    private Row storedLine(String id) {
        Row active = one(E_LINE, id);
        if (active != null) {
            return active;
        }
        try {
            return one(E_LINE_DRAFT, id);
        } catch (RuntimeException e) {
            return null;
        }
    }

    private static void copyIfAbsent(CdsData line, String field, Object value) {
        if (value != null && line.get(field) == null && !line.containsKey(field)) {
            line.put(field, value);
        }
    }

    /** The value in the entry where it has one, the stored value where it does not. */
    private Object merged(CdsData entry, Row stored, String field) {
        Object value = entry.get(field);
        if (value != null) {
            return value;
        }
        if (entry.containsKey(field)) {
            return null;
        }
        return stored == null ? null : stored.get(field);
    }

    private static BigDecimal money(BigDecimal qty, BigDecimal rate) {
        return qty.multiply(rate).setScale(2, RoundingMode.HALF_UP);
    }

    private static BigDecimal orZero(BigDecimal v) {
        return v == null ? BigDecimal.ZERO : v;
    }

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }

    private static BigDecimal dec(Object v) {
        if (v == null) { return null; }
        if (v instanceof BigDecimal b) { return b; }
        try {
            return new BigDecimal(String.valueOf(v));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static LocalDate date(Object v) {
        if (v == null) { return null; }
        if (v instanceof LocalDate d) { return d; }
        try {
            return LocalDate.parse(String.valueOf(v));
        } catch (RuntimeException e) {
            return null;
        }
    }
}
