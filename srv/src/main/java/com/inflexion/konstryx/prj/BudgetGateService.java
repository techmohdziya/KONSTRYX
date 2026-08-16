package com.inflexion.konstryx.prj;

import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.persistence.PersistenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * The validation gate (KX-GOV-002): nothing generates budget lines until every
 * rule passes. One component, used by both the validateForBudget action and the
 * budget generation refusal, so the screen and the refusal can never disagree
 * about what is failing.
 *
 * VAL-05 is the rule that guards the whole design: because recipes are keyed
 * on the CBS leaf, a leaf carrying two material grades is unresolvable — the
 * generator would attach both materials to every line on the leaf. Grade must
 * ride on which material row is attached to which leaf (spec Part A.3).
 */
@Component
public class BudgetGateService {

    private static final String E_BOQ = "konstryx.prj.BOQ";
    private static final String E_ITEM = "konstryx.prj.BOQItem";
    private static final String E_ALLOC = "konstryx.prj.Allocation";
    private static final String E_WBS = "konstryx.prj.WBSElement";
    private static final String E_BUILDUP = "konstryx.prj.BOQItemResource";
    private static final String E_CBS_INSTANCE = "konstryx.prj.CBSInstance";
    private static final String E_CONSUMPTION = "konstryx.master.ConsumptionRate";
    private static final String E_RESOURCE = "konstryx.master.ResourceNode";

    @Autowired
    private PersistenceService db;

    public static final class RuleResult {
        public final String ruleId;
        public final String description;
        public final int linesChecked;
        public final int failing;

        RuleResult(String ruleId, String description, int linesChecked, int failing) {
            this.ruleId = ruleId;
            this.description = description;
            this.linesChecked = linesChecked;
            this.failing = failing;
        }

        public String result() { return failing == 0 ? "Pass" : "Fail"; }
    }

    public List<RuleResult> evaluate(String projectId) {
        List<Row> items = itemsOf(projectId);
        List<RuleResult> results = new ArrayList<>();

        // VAL-01 · every BOQ line maps to a CBS code
        int unmapped = 0;
        for (Row item : items) {
            if (item.get("cbs_ID") == null) {
                unmapped++;
            }
        }
        results.add(new RuleResult("VAL-01", "Every BOQ line maps to a CBS code",
                items.size(), unmapped));

        // VAL-02 · allocated quantities sum to the contract quantity per line
        int misallocated = 0;
        for (Row item : items) {
            BigDecimal contractQty = dec(item.get("qty"));
            if (contractQty == null) {
                continue;
            }
            BigDecimal allocated = BigDecimal.ZERO;
            String itemId = str(item.get("ID"));
            for (Row alloc : db.run(Select.from(E_ALLOC)
                    .where(a -> a.get("boqItem_ID").eq(itemId)))) {
                BigDecimal qty = dec(alloc.get("allocQty"));
                if (qty != null) {
                    allocated = allocated.add(qty);
                }
            }
            if (allocated.compareTo(contractQty) != 0) {
                misallocated++;
            }
        }
        results.add(new RuleResult("VAL-02",
                "Allocated quantities sum to the contract quantity on each line",
                items.size(), misallocated));

        // VAL-03 · every allocation resolves to a WBS element
        int danglingWbs = 0;
        int allocations = 0;
        for (Row item : items) {
            String itemId = str(item.get("ID"));
            for (Row alloc : db.run(Select.from(E_ALLOC)
                    .where(a -> a.get("boqItem_ID").eq(itemId)))) {
                allocations++;
                Object wbsId = alloc.get("wbs_ID");
                boolean resolves = wbsId != null && db.run(Select.from(E_WBS)
                        .where(w -> w.get("ID").eq(wbsId.toString()))).first().isPresent();
                if (!resolves) {
                    danglingWbs++;
                }
            }
        }
        results.add(new RuleResult("VAL-03", "Every allocation resolves to a WBS element",
                allocations, danglingWbs));

        // VAL-04 · every mapped line's recipe left a priced build-up row for
        // every resolved norm. A rate-missing demand writes no row (IT-08), so
        // absence is the evidence: re-resolve the recipe and require each
        // resolved norm's ID to appear in some row's sourceNorm. This is also
        // what makes sourceNorm auditable (IT-16) — a row that cannot name its
        // norm fails here.
        int unpriced = 0;
        int mapped = 0;
        String companyId = companyOf(projectId);
        for (Row item : items) {
            Object cbsId = item.get("cbs_ID");
            if (cbsId == null) {
                continue;
            }
            mapped++;
            String itemId = str(item.get("ID"));
            String leaf = db.run(Select.from(E_CBS_INSTANCE)
                            .where(c -> c.get("ID").eq(cbsId.toString()))).first()
                    .map(r -> str(r.get("libraryNode_ID"))).orElse(null);
            if (leaf == null) {
                unpriced++;
                continue;
            }
            Set<String> written = new HashSet<>();
            for (Row buildUp : db.run(Select.from(E_BUILDUP)
                    .where(b -> b.get("boqItem_ID").eq(itemId)))) {
                String sourceNorm = str(buildUp.get("sourceNorm"));
                if (sourceNorm != null) {
                    written.add(sourceNorm);
                }
            }
            boolean complete = true;
            for (Row norm : resolvedNorms(E_CONSUMPTION, "material_ID", leaf, companyId)) {
                if (!written.contains("ConsumptionRate/" + str(norm.get("ID")))) {
                    complete = false;
                }
            }
            for (Row norm : resolvedNorms("konstryx.master.ProductivityRate", "resource_ID",
                    leaf, companyId)) {
                if (!written.contains("ProductivityRate/" + str(norm.get("ID")))) {
                    complete = false;
                }
            }
            if (!complete) {
                unpriced++;
            }
        }
        results.add(new RuleResult("VAL-04",
                "Every mapped line has a complete, priced build-up",
                mapped, unpriced));

        // VAL-05 · no CBS leaf carries two material grades (spec Part A.3)
        Map<String, Set<String>> materialsByLeaf = new LinkedHashMap<>();
        for (Row norm : db.run(Select.from(E_CONSUMPTION))) {
            String leaf = str(norm.get("linkedCBS_ID"));
            String material = str(norm.get("material_ID"));
            if (leaf == null || material == null) {
                continue;
            }
            materialsByLeaf.computeIfAbsent(leaf, k -> new HashSet<>()).add(material);
        }
        int conflictedLeaves = 0;
        for (Set<String> materials : materialsByLeaf.values()) {
            if (materials.size() > 1) {
                conflictedLeaves++;
            }
        }
        results.add(new RuleResult("VAL-05",
                "No CBS leaf carries two material grades",
                materialsByLeaf.size(), conflictedLeaves));

        // VAL-06 · every build-up resource resolves to an active L5 leaf
        int badResources = 0;
        int buildUpRows = 0;
        for (Row item : items) {
            String itemId = str(item.get("ID"));
            for (Row buildUp : db.run(Select.from(E_BUILDUP)
                    .where(b -> b.get("boqItem_ID").eq(itemId)))) {
                buildUpRows++;
                Object resourceId = buildUp.get("resource_ID");
                Optional<Row> resource = resourceId == null ? Optional.empty()
                        : db.run(Select.from(E_RESOURCE)
                                .where(r -> r.get("ID").eq(resourceId.toString()))).first();
                boolean ok = resource.isPresent()
                        && "L5".equals(str(resource.get().get("level")))
                        && "ACTIVE".equals(str(resource.get().get("masterStatus")));
                if (!ok) {
                    badResources++;
                }
            }
        }
        results.add(new RuleResult("VAL-06",
                "Every build-up resource resolves to an active L5 leaf",
                buildUpRows, badResources));

        return results;
    }

    public List<RuleResult> failing(String projectId) {
        List<RuleResult> failing = new ArrayList<>();
        for (RuleResult rule : evaluate(projectId)) {
            if (rule.failing > 0) {
                failing.add(rule);
            }
        }
        return failing;
    }

    /**
     * The same company-first resolution the generator uses (BuildUpHandler
     * .recipeRows) — duplicated knowingly: the gate must judge the build-up by
     * the same rules that produced it, and a shared mutable dependency between
     * a gate and the thing it gates invites exactly the drift it exists to
     * catch. Change both together.
     */
    private List<Row> resolvedNorms(String entity, String subjectField, String leafId,
                                    String companyId) {
        Map<String, Row> bySubject = new LinkedHashMap<>();
        java.time.LocalDate today = java.time.LocalDate.now();
        for (Row norm : db.run(Select.from(entity)
                .where(n -> n.get("linkedCBS_ID").eq(leafId)))) {
            String subject = str(norm.get(subjectField));
            if (subject == null) {
                continue;
            }
            java.time.LocalDate from = normDate(norm.get("effectiveFrom"));
            if (from == null || from.isAfter(today)) {
                continue;   // a norm dated in the future is not yet in force
            }
            String owner = str(norm.get("owningCompany_ID"));
            boolean isCompany = companyId != null && companyId.equalsIgnoreCase(owner);
            boolean isGroup = owner == null;
            if (!isCompany && !isGroup) {
                continue;
            }
            Row current = bySubject.get(subject);
            if (current == null) {
                bySubject.put(subject, norm);
                continue;
            }
            boolean currentIsCompany = companyId != null
                    && companyId.equalsIgnoreCase(str(current.get("owningCompany_ID")));
            java.time.LocalDate currentFrom = normDate(current.get("effectiveFrom"));
            // Company beats group; within a scope the latest start in force
            // wins - the same rule the money rates resolve by, so a rate
            // revision and a norm revision behave identically.
            if ((isCompany && !currentIsCompany)
                    || (isCompany == currentIsCompany
                        && currentFrom != null && from.isAfter(currentFrom))) {
                bySubject.put(subject, norm);
            }
        }
        return new ArrayList<>(bySubject.values());
    }

    private static java.time.LocalDate normDate(Object v) {
        if (v == null) { return null; }
        if (v instanceof java.time.LocalDate d) { return d; }
        try { return java.time.LocalDate.parse(String.valueOf(v).substring(0, 10)); }
        catch (RuntimeException e) { return null; }
    }

    private String companyOf(String projectId) {
        return db.run(Select.from("konstryx.prj.Project")
                        .where(p -> p.get("ID").eq(projectId))).first()
                .map(r -> str(r.get("company_ID"))).orElse(null);
    }

    private List<Row> itemsOf(String projectId) {
        List<Row> items = new ArrayList<>();
        for (Row boq : db.run(Select.from(E_BOQ).where(b -> b.get("project_ID").eq(projectId)))) {
            String boqId = str(boq.get("ID"));
            for (Row item : db.run(Select.from(E_ITEM).where(i -> i.get("boq_ID").eq(boqId)))) {
                items.add(item);
            }
        }
        return items;
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static BigDecimal dec(Object v) {
        if (v == null) { return null; }
        if (v instanceof BigDecimal b) { return b; }
        try { return new BigDecimal(String.valueOf(v)); }
        catch (NumberFormatException e) { return null; }
    }
}
