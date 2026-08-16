package com.inflexion.konstryx.prj;

import com.sap.cds.Row;
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

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * The Cost Mapping workbench's data: four step tiles and the exception queue.
 *
 * The design rule this serves (wireframe cost-mapping): the user only resolves
 * exceptions. The canonical bill maps 1,127 of 1,142 lines automatically and
 * those are never rendered — so this action returns counts for the tiles and
 * ONLY the rows that need a human, each with its reason and, where the system
 * can offer one, a suggestion.
 *
 * A suggestion is a token overlap between the line's description and a CBS
 * leaf's description — deliberately modest. A wrong confident suggestion costs
 * more than no suggestion, so anything without an overlap simply has none.
 */
@Component
@ServiceName("ProjectService")
public class CostMappingHandler implements EventHandler {

    private static final String E_BOQ = "konstryx.prj.BOQ";
    private static final String E_ITEM = "konstryx.prj.BOQItem";
    private static final String E_ALLOC = "konstryx.prj.Allocation";
    private static final String E_BUILDUP = "konstryx.prj.BOQItemResource";
    private static final String E_CBS_INSTANCE = "konstryx.prj.CBSInstance";
    private static final String E_CBS_LIBRARY = "konstryx.master.CBSNode";
    private static final String E_RESOURCE = "konstryx.master.ResourceNode";

    @Autowired
    private PersistenceService db;

    @Autowired
    private BudgetGateService gate;

    @On(event = "costMappingSummary", entity = "ProjectService.Projects")
    public void onSummary(EventContext context) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        Row project = (select == null ? Optional.<Row>empty() : db.run(select).first())
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "Project not found."));
        String projectId = str(project.get("ID"));
        String companyId = gate.companyOf(projectId);

        List<Row> items = new ArrayList<>();
        for (Row boq : db.run(Select.from(E_BOQ).where(b -> b.get("project_ID").eq(projectId)))) {
            String boqId = str(boq.get("ID"));
            for (Row item : db.run(Select.from(E_ITEM).where(i -> i.get("boq_ID").eq(boqId)))) {
                items.add(item);
            }
        }

        // The project's CBS instances, and their library leaves, once.
        Map<String, Row> instanceById = new HashMap<>();
        List<Row> instances = new ArrayList<>();
        for (Row instance : db.run(Select.from(E_CBS_INSTANCE)
                .where(c -> c.get("project_ID").eq(projectId)))) {
            instanceById.put(str(instance.get("ID")), instance);
            instances.add(instance);
        }

        int cbsMapped = 0, wbsDone = 0, resResolved = 0;
        List<Map<String, Object>> exceptions = new ArrayList<>();

        for (Row item : items) {
            String itemId = str(item.get("ID"));
            String itemNo = str(item.get("itemNo"));

            // ---- step 1 · CBS ------------------------------------------------
            Object cbsId = item.get("cbs_ID");
            if (cbsId == null) {
                Map<String, Object> suggestion = suggestLeaf(
                        str(item.get("description")), instances);
                exceptions.add(exception(itemId, itemNo, "CBS_UNMAPPED",
                        "No CBS assigned",
                        suggestion == null ? null : str(suggestion.get("code")),
                        suggestion == null ? null : str(suggestion.get("ID"))));
                continue;   // nothing downstream can be judged without the map
            }
            cbsMapped++;

            // ---- step 2 · WBS distribution ----------------------------------
            BigDecimal contractQty = orZero(dec(item.get("qty")));
            BigDecimal allocated = BigDecimal.ZERO;
            for (Row alloc : db.run(Select.from(E_ALLOC)
                    .where(a -> a.get("boqItem_ID").eq(itemId)))) {
                allocated = allocated.add(orZero(dec(alloc.get("allocQty"))));
            }
            if (allocated.compareTo(contractQty) == 0 && contractQty.signum() > 0) {
                wbsDone++;
            } else {
                exceptions.add(exception(itemId, itemNo, "UNALLOCATED",
                        allocated.stripTrailingZeros().toPlainString() + " of "
                                + contractQty.stripTrailingZeros().toPlainString()
                                + " distributed to WBS", null, null));
            }

            // ---- step 3 · resources -----------------------------------------
            Row instance = instanceById.get(cbsId.toString());
            String leaf = instance == null ? null : str(instance.get("libraryNode_ID"));
            if (leaf == null) {
                exceptions.add(exception(itemId, itemNo, "NO_LIBRARY_ORIGIN",
                        "The assigned CBS node has no library origin, so no recipe can attach",
                        null, null));
                continue;
            }
            List<Row> consumption = gate.resolvedNorms(
                    "konstryx.master.ConsumptionRate", "material_ID", leaf, companyId);
            List<Row> productivity = gate.resolvedNorms(
                    "konstryx.master.ProductivityRate", "resource_ID", leaf, companyId);
            if (consumption.isEmpty() && productivity.isEmpty()) {
                boolean imported = db.run(Select.from(E_BUILDUP)
                        .where(b -> b.get("boqItem_ID").eq(itemId)
                                .and(b.get("source").eq("IMPORTED")))).first().isPresent();
                if (imported) {
                    // An imported estimate build-up stands in for a recipe; the
                    // leaf still deserves one, but the line is workable.
                    resResolved++;
                } else {
                    exceptions.add(exception(itemId, itemNo, "NO_RECIPE_FOR_CBS",
                            "No norm is keyed to leaf "
                                    + (instance == null ? "?" : str(instance.get("code"))),
                            null, null));
                }
                continue;
            }

            // The real blocker first: a recipe resource with no money rate can
            // never produce a build-up row, however many times generation runs.
            // Telling the user to "run Generate Build-up" against that is a
            // treadmill; naming the unrated resource is a work item.
            List<String> unrated = new ArrayList<>();
            for (Row norm : consumption) {
                String materialId = str(norm.get("material_ID"));
                if (!hasMoneyRate(materialId, companyId)) {
                    unrated.add(resourceCode(materialId));
                }
            }
            for (Row norm : productivity) {
                String resourceId = str(norm.get("resource_ID"));
                if (!hasMoneyRate(resourceId, companyId)) {
                    unrated.add(resourceCode(resourceId));
                }
            }
            if (!unrated.isEmpty()) {
                exceptions.add(exception(itemId, itemNo, "RATE_MISSING",
                        "No money rate for " + String.join(", ",
                                unrated.stream().distinct().toList()), null, null));
                continue;
            }

            Set<String> written = new HashSet<>();
            for (Row buildUp : db.run(Select.from(E_BUILDUP)
                    .where(b -> b.get("boqItem_ID").eq(itemId)))) {
                String source = str(buildUp.get("sourceNorm"));
                if (source != null) {
                    written.add(source);
                }
            }
            boolean complete = true;
            for (Row norm : consumption) {
                if (!written.contains("ConsumptionRate/" + str(norm.get("ID")))) {
                    complete = false;
                }
            }
            for (Row norm : productivity) {
                if (!written.contains("ProductivityRate/" + str(norm.get("ID")))) {
                    complete = false;
                }
            }
            if (complete) {
                resResolved++;
            } else {
                exceptions.add(exception(itemId, itemNo, "BUILDUP_NOT_GENERATED",
                        "Recipe and rates exist; run Generate Build-up", null, null));
            }
        }

        int gatePassing = 0, gateFailing = 0;
        for (BudgetGateService.RuleResult rule : gate.evaluate(projectId)) {
            if (rule.failing == 0) {
                gatePassing++;
            } else {
                gateFailing++;
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("totalLines", items.size());
        result.put("cbsMapped", cbsMapped);
        result.put("cbsOpen", items.size() - cbsMapped);
        result.put("wbsDone", wbsDone);
        result.put("wbsOpen", items.size() - wbsDone);
        result.put("resResolved", resResolved);
        result.put("resOpen", items.size() - resResolved);
        result.put("gatePassing", gatePassing);
        result.put("gateFailing", gateFailing);
        result.put("exceptions", exceptions);
        context.put("result", result);
        context.setCompleted();
    }

    // ----------------------------------------------------------------- helpers

    private Map<String, Object> exception(String itemId, String itemNo, String reason,
                                          String detail, String suggestedCbs,
                                          String suggestedCbsId) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("boqItemId", itemId);
        row.put("itemNo", itemNo);
        row.put("reason", reason);
        row.put("detail", detail);
        row.put("suggestedCbs", suggestedCbs);
        row.put("suggestedCbsId", suggestedCbsId);
        return row;
    }

    /**
     * Token overlap between the line description and a leaf's library
     * description. Modest on purpose: a wrong confident suggestion costs more
     * than no suggestion.
     */
    private Map<String, Object> suggestLeaf(String description, List<Row> instances) {
        if (description == null) {
            return null;
        }
        Set<String> tokens = tokensOf(description);
        Row best = null;
        int bestScore = 0;
        for (Row instance : instances) {
            Object leafId = instance.get("libraryNode_ID");
            if (leafId == null) {
                continue;
            }
            Optional<Row> leaf = db.run(Select.from(E_CBS_LIBRARY)
                    .where(n -> n.get("ID").eq(leafId.toString()))).first();
            if (leaf.isEmpty()) {
                continue;
            }
            Set<String> leafTokens = tokensOf(str(leaf.get().get("phase")));
            leafTokens.retainAll(tokens);
            if (leafTokens.size() > bestScore) {
                bestScore = leafTokens.size();
                best = instance;
            }
        }
        if (best == null) {
            return null;
        }
        Map<String, Object> suggestion = new HashMap<>();
        suggestion.put("ID", best.get("ID"));
        suggestion.put("code", best.get("code"));
        return suggestion;
    }

    private static Set<String> tokensOf(String text) {
        Set<String> tokens = new HashSet<>();
        if (text == null) {
            return tokens;
        }
        for (String token : text.toLowerCase(Locale.ROOT).split("[^a-z0-9]+")) {
            if (token.length() >= 4) {
                tokens.add(token);
            }
        }
        return tokens;
    }

    /** Any money rate in force today for this resource, group or this company. */
    private boolean hasMoneyRate(String resourceId, String companyId) {
        if (resourceId == null) {
            return false;
        }
        java.time.LocalDate today = java.time.LocalDate.now();
        for (Row rate : db.run(Select.from("konstryx.master.RateMaster")
                .where(r -> r.get("resource_ID").eq(resourceId)))) {
            Object from = rate.get("effectiveFrom");
            java.time.LocalDate date;
            try {
                date = java.time.LocalDate.parse(String.valueOf(from).substring(0, 10));
            } catch (RuntimeException e) {
                continue;
            }
            if (date.isAfter(today)) {
                continue;
            }
            String owner = str(rate.get("owningCompany_ID"));
            if (owner == null || (companyId != null && companyId.equalsIgnoreCase(owner))) {
                return true;
            }
        }
        return false;
    }

    private String resourceCode(String resourceId) {
        if (resourceId == null) {
            return "?";
        }
        return db.run(Select.from(E_RESOURCE).where(r -> r.get("ID").eq(resourceId)))
                .first().map(r -> str(r.get("code"))).orElse(resourceId);
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static BigDecimal orZero(BigDecimal v) { return v == null ? BigDecimal.ZERO : v; }

    private static BigDecimal dec(Object v) {
        if (v == null) { return null; }
        if (v instanceof BigDecimal b) { return b; }
        try { return new BigDecimal(String.valueOf(v)); }
        catch (NumberFormatException e) { return null; }
    }
}
