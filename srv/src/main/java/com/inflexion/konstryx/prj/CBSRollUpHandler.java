package com.inflexion.konstryx.prj;

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
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Rolls a project's cost breakdown up from the budget lines beneath it.
 *
 * CBSInstance.budgetAmount was a stored decimal that nothing recomputed, so a
 * node could report a figure its own budget lines contradicted and neither
 * number was obviously the wrong one. It is the same defect the payment
 * certificate had, where a net was stated independently of the back charges
 * that produced it, and the reservation line had, where a burn was stated
 * independently of the timesheets behind it. Both were fixed by deriving.
 *
 * Two figures are kept rather than one. ownAmount is what is budgeted against
 * the node itself; budgetAmount is that plus everything beneath it. Keeping
 * only the rolled-up total makes it impossible to tell a parent that carries
 * real budget of its own from one that is merely a heading.
 */
@Component
@ServiceName("ProjectService")
public class CBSRollUpHandler implements EventHandler {

    private static final String E_CBS = "konstryx.prj.CBSInstance";
    private static final String E_BUDGET_LINE = "konstryx.bud.BudgetLine";

    @Autowired
    private PersistenceService db;

    @On(event = "rollUpBudget")
    public void onRollUp(EventContext context) {
        Row node = targetOf(context);
        String projectId = str(node.get("project_ID"));
        if (projectId == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "This CBS node belongs to no project, so there is nothing to roll up.");
        }

        // The whole tree, not the branch the action was called on. Rolling up
        // one branch is exactly how a parent and its siblings come to disagree.
        Map<String, Row> nodes = new LinkedHashMap<>();
        for (Row row : db.run(Select.from(E_CBS)
                .where(c -> c.get("project_ID").eq(projectId)))) {
            nodes.put(str(row.get("ID")), row);
        }
        if (nodes.isEmpty()) {
            throw new ServiceException(ErrorStatuses.NOT_FOUND,
                    "This project has no CBS to roll up.");
        }

        Map<String, BigDecimal> own = new HashMap<>();
        for (String id : nodes.keySet()) {
            own.put(id, BigDecimal.ZERO);
        }

        // Budget lines are read once and bucketed, rather than queried per
        // node. A project with a three-level CBS and a few thousand lines
        // would otherwise issue one select per node to add up the same table.
        int lines = 0;
        int orphaned = 0;
        for (Row line : db.run(Select.from(E_BUDGET_LINE))) {
            String cbsId = str(line.get("cbs_ID"));
            if (cbsId == null) {
                continue;
            }
            if (!own.containsKey(cbsId)) {
                continue;      // a line on another project's CBS
            }
            own.merge(cbsId, orZero(decimal(line.get("amount"))), BigDecimal::add);
            lines++;
        }

        Map<String, BigDecimal> total = new HashMap<>(own);
        List<String> cyclic = new ArrayList<>();

        // Each node's own amount is added to every ancestor above it. Walking
        // upward from the leaves needs no ordering pass and no recursion, and
        // a node whose parent chain loops is reported by name rather than
        // hanging the request.
        for (String id : nodes.keySet()) {
            BigDecimal amount = own.get(id);
            if (amount.signum() == 0) {
                continue;
            }
            String parentId = str(nodes.get(id).get("parent_ID"));
            int guard = 0;
            while (parentId != null && nodes.containsKey(parentId)) {
                if (++guard > nodes.size()) {
                    cyclic.add(code(nodes.get(id)));
                    break;
                }
                total.merge(parentId, amount, BigDecimal::add);
                parentId = str(nodes.get(parentId).get("parent_ID"));
            }
        }

        if (!cyclic.isEmpty()) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "The CBS cannot be rolled up because these nodes sit above "
                            + "themselves: " + String.join(", ", cyclic)
                            + ". Correct the parent before rolling up.");
        }

        int changed = 0;
        for (Map.Entry<String, Row> entry : nodes.entrySet()) {
            String id = entry.getKey();
            BigDecimal ownAmount = own.get(id).setScale(2, RoundingMode.HALF_UP);
            BigDecimal rolled = total.get(id).setScale(2, RoundingMode.HALF_UP);

            BigDecimal wasRolled = orZero(decimal(entry.getValue().get("budgetAmount")))
                    .setScale(2, RoundingMode.HALF_UP);
            if (wasRolled.compareTo(rolled) != 0) {
                changed++;
            }

            Map<String, Object> update = new HashMap<>();
            update.put("ownAmount", ownAmount);
            update.put("budgetAmount", rolled);
            db.run(Update.entity(E_CBS).data(update).where(c -> c.get("ID").eq(id)));
        }

        BigDecimal projectTotal = BigDecimal.ZERO;
        for (Row row : nodes.values()) {
            if (str(row.get("parent_ID")) == null) {
                projectTotal = projectTotal.add(total.get(str(row.get("ID"))));
            }
        }

        return_(context, String.format(
                "%d CBS node(s) rolled up from %d budget line(s). %s at the roots. "
                        + "%s",
                nodes.size(), lines,
                projectTotal.setScale(2, RoundingMode.HALF_UP).toPlainString(),
                changed == 0
                        ? "Every node already agreed with its lines."
                        : changed + " node(s) had been reporting a figure their lines "
                                + "did not support and were corrected."));
    }

    // ---------------------------------------------------------------- helpers

    private Row targetOf(EventContext context) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        return (select == null ? Optional.<Row>empty() : db.run(select).first())
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "CBS node not found."));
    }

    private static String code(Row node) {
        String code = str(node.get("code"));
        return code == null ? str(node.get("ID")) : code;
    }

    private static void return_(EventContext context, String message) {
        context.put("result", message);
        context.setCompleted();
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
