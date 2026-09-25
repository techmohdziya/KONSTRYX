package com.inflexion.konstryx.vo;

import com.sap.cds.CdsData;
import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.ql.cqn.CqnAnalyzer;
import com.sap.cds.ql.cqn.CqnInsert;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.draft.DraftService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.After;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.runtime.CdsRuntime;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * What a variation is worth, and what it costs, from the lines that make it up.
 *
 * A variation is priced the same way a bill is: a quantity at a rate, for
 * revenue and again for cost. The amounts were being stored as nothing at all,
 * so the screen showed three orders with blank money while the reconciliation
 * computed the right figure from the quantity and the rate every time it ran.
 * Two answers to one question, and the one on the screen was empty.
 *
 * An omission carries its sign. A variation that omits work reduces what the
 * job is worth, and a column of absolute values totalled by a reader would
 * report the omission as extra revenue.
 *
 * The margin is revenue less cost, and the percentage follows. Neither is
 * accepted from the client: a variation whose margin disagrees with its own
 * two amounts is a number somebody will act on and nobody can reproduce.
 */
@Component
@ServiceName("ProjectService")
public class VariationHandler implements EventHandler {

    private static final String E_VO = "konstryx.vo.VariationOrder";
    private static final String E_LINE = "konstryx.vo.VariationLine";
    /** The same line while it is still being edited. */
    private static final String E_LINE_DRAFT = "ProjectService.VariationLines_drafts";
    private static final String E_BOQ_ITEM = "konstryx.prj.BOQItem";

    private static final BigDecimal HUNDRED = new BigDecimal("100");

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    // ------------------------------------------------------------- the line

    @Before(event = { CqnService.EVENT_CREATE, CqnService.EVENT_UPDATE,
                      DraftService.EVENT_DRAFT_NEW, DraftService.EVENT_DRAFT_PATCH },
            entity = "ProjectService.VariationLines")
    public void deriveLine(EventContext context, List<CdsData> lines) {
        String fromPath = parentFromPath(context);
        for (CdsData line : lines) {
            if (fromPath != null && line.get("variation_ID") == null) {
                line.put("variation_ID", fromPath);
            }
            deriveLine(line);
        }
    }

    private void deriveLine(CdsData line) {
        String id = str(line.get("ID"));
        Row stored = id == null ? null : storedLine(id);

        // Where the variation remeasures a bill item, the item supplies what
        // the line is silent about. A star rate typed on the line stays, because
        // a variation priced at a new rate is the ordinary case.
        String itemId = str(merged(line, stored, "boqItem_ID"));
        if (itemId != null) {
            Row item = one(E_BOQ_ITEM, itemId);
            if (item != null) {
                copyIfAbsent(line, "description", item.get("description"));
                copyIfAbsent(line, "uom", item.get("uom"));
                copyIfAbsent(line, "revenueRate", item.get("rate"));
            }
        }

        BigDecimal qty = dec(merged(line, stored, "qty"));
        BigDecimal revenueRate = dec(merged(line, stored, "revenueRate"));
        BigDecimal costRate = dec(merged(line, stored, "costRate"));
        boolean omits = "OMIT".equalsIgnoreCase(str(merged(line, stored, "changeType")));

        if (qty != null && revenueRate != null) {
            line.put("revenueAmount", signed(qty.multiply(revenueRate), omits));
        }
        if (qty != null && costRate != null) {
            line.put("costAmount", signed(qty.multiply(costRate), omits));
        }
    }

    // ----------------------------------------------------------- the header

    @After(event = { CqnService.EVENT_CREATE, CqnService.EVENT_UPDATE,
                     CqnService.EVENT_DELETE },
           entity = "ProjectService.VariationLines")
    public void totalAfterLineWrite(EventContext context, List<CdsData> lines) {
        lines.stream().map(this::parentOf).filter(p -> p != null).distinct().forEach(this::total);
    }

    @After(event = DraftService.EVENT_DRAFT_SAVE, entity = "ProjectService.Variations")
    public void totalAfterSave(EventContext context, List<CdsData> orders) {
        orders.stream().map(o -> str(o.get("ID"))).filter(id -> id != null).forEach(this::total);
    }

    /** Revenue, cost, and the margin between them - all from the lines. */
    private void total(String voId) {
        BigDecimal revenue = BigDecimal.ZERO;
        BigDecimal cost = BigDecimal.ZERO;
        boolean any = false;

        for (Row line : db.run(Select.from(E_LINE).where(l -> l.get("variation_ID").eq(voId)))) {
            any = true;
            revenue = revenue.add(orZero(dec(line.get("revenueAmount"))));
            cost = cost.add(orZero(dec(line.get("costAmount"))));
        }
        if (!any) {
            return;
        }
        BigDecimal margin = revenue.subtract(cost);

        Map<String, Object> patch = new HashMap<>();
        patch.put("revenueAmount", revenue);
        patch.put("costAmount", cost);
        patch.put("marginAmount", margin);
        // A percentage of nothing is not nought, it is nothing. A variation
        // that adds no revenue and some cost has no margin percentage to state.
        patch.put("marginPct", revenue.signum() == 0 ? null
                : margin.multiply(HUNDRED).divide(revenue, 2, RoundingMode.HALF_UP));

        db.run(Update.entity(E_VO).data(patch).where(v -> v.get("ID").eq(voId)));
    }

    private String parentOf(CdsData line) {
        String parent = str(line.get("variation_ID"));
        if (parent != null) {
            return parent;
        }
        String id = str(line.get("ID"));
        Row stored = id == null ? null : storedLine(id);
        return stored == null ? null : str(stored.get("variation_ID"));
    }

    // ---------------------------------------------------------------- helpers

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
            return null;
        }
    }

    private Row one(String entity, String id) {
        return db.run(Select.from(entity).where(e -> e.get("ID").eq(id))).first().orElse(null);
    }

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

    private static BigDecimal signed(BigDecimal amount, boolean omits) {
        BigDecimal value = amount.setScale(2, RoundingMode.HALF_UP);
        return omits ? value.negate() : value;
    }

    private static void copyIfAbsent(CdsData line, String field, Object value) {
        if (value != null && line.get(field) == null && !line.containsKey(field)) {
            line.put(field, value);
        }
    }

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
}
