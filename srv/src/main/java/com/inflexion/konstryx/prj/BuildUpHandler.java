package com.inflexion.konstryx.prj;

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

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * Generates the resource build-up of a bill from the CBS recipes.
 *
 * The join is deliberate: a BOQ line resolves through its CBS leaf to every
 * norm keyed to that leaf, and nobody keys resources per BOQ line (wireframe
 * cost-mapping, step 3). Two consequences follow and both are enforced here
 * rather than documented and hoped for:
 *
 *   - Two lines on the same leaf get the same recipe. Spec variance must be a
 *     distinct leaf or a distinct activity code — that is CBS governance, and
 *     the coverage report is where a missing distinction becomes visible.
 *   - A MANUAL build-up row is an exception awaiting a recipe, not a second
 *     way of working. Regeneration replaces RECIPE rows and leaves MANUAL rows
 *     standing, counted separately, so the defect list never silently shrinks.
 *
 * Difficulty applies on top of productivity norms — hours = qty / output x
 * difficulty — and never touches the master norm or material consumption;
 * wastage is the material-side allowance (KX-BUD-014).
 */
@Component
@ServiceName("ProjectService")
public class BuildUpHandler implements EventHandler {

    private static final String E_BOQ = "konstryx.prj.BOQ";
    private static final String E_ITEM = "konstryx.prj.BOQItem";
    private static final String E_BUILDUP = "konstryx.prj.BOQItemResource";
    private static final String E_CBS_INSTANCE = "konstryx.prj.CBSInstance";
    private static final String E_PRODUCTIVITY = "konstryx.master.ProductivityRate";
    private static final String E_CONSUMPTION = "konstryx.master.ConsumptionRate";
    private static final String E_RATE = "konstryx.master.RateMaster";
    private static final String E_RESOURCE = "konstryx.master.ResourceNode";
    private static final String E_PROJECT = "konstryx.prj.Project";

    @Autowired
    private PersistenceService db;

    @On(event = "generateBuildUp", entity = "ProjectService.BOQs")
    public void onGenerate(EventContext context) {
        Row boq = targetOf(context);
        String boqId = str(boq.get("ID"));
        String companyId = companyOf(boq);

        BigDecimal difficulty = dec(context.get("difficultyPct"));
        if (difficulty == null || difficulty.signum() <= 0) {
            difficulty = new BigDecimal("100");
        }
        if (difficulty.compareTo(new BigDecimal("500")) > 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A difficulty of " + difficulty.toPlainString()
                            + "% is not an adjustment, it is a different job.");
        }

        int recipeFound = 0, noRecipe = 0, unmapped = 0, rateMissing = 0, manualKept = 0;
        List<String> gaps = new ArrayList<>();

        for (Row item : db.run(Select.from(E_ITEM).where(i -> i.get("boq_ID").eq(boqId)))) {
            String itemId = str(item.get("ID"));

            // Someone's judgement survives; the generated rows are recomputed.
            manualKept += countManual(itemId);
            db.run(Delete.from(E_BUILDUP).where(b -> b.get("boqItem_ID").eq(itemId)
                    .and(b.get("source").eq("RECIPE"))));

            String libraryLeaf = libraryLeafOf(item);
            if (libraryLeaf == null) {
                unmapped++;
                gaps.add(item.get("itemNo") + ": no CBS mapped");
                continue;
            }

            List<Map<String, Object>> rows = new ArrayList<>();
            // Cost scales by the budgeted quantity, never the contract quantity
            // (CALC-05). Where no budget quantity has been entered yet, the
            // contract quantity stands in - visibly, via the basis string.
            BigDecimal contractQty = orZero(dec(item.get("qty")));
            BigDecimal budgetQty = dec(item.get("budgetQty"));
            boolean budgeted = budgetQty != null && budgetQty.signum() > 0;
            BigDecimal qty = budgeted ? budgetQty : contractQty;

            for (Row norm : recipeRows(E_CONSUMPTION, "material_ID", libraryLeaf, companyId)) {
                rows.add(materialRow(itemId, norm, qty));
            }
            for (Row norm : recipeRows(E_PRODUCTIVITY, "resource_ID", libraryLeaf, companyId)) {
                rows.addAll(productivityRows(itemId, norm, qty, difficulty));
            }

            if (rows.isEmpty()) {
                noRecipe++;
                gaps.add(item.get("itemNo") + ": no recipe on its CBS leaf");
                continue;
            }

            // A demand line without a money rate is an exception, not a row.
            // Writing it priced at nothing would flow a silent zero into the
            // budget (IT-08); the gate is where the gap becomes visible.
            List<Map<String, Object>> priced = new ArrayList<>();
            for (Map<String, Object> row : rows) {
                BigDecimal unitRate = moneyRate(str(row.get("resource_ID")), companyId);
                if (unitRate == null) {
                    rateMissing++;
                    gaps.add(item.get("itemNo") + ": no rate for "
                            + resourceCode(str(row.get("resource_ID"))));
                    continue;
                }
                BigDecimal perUom = orZero(dec(row.get("qtyPerUom")));
                BigDecimal totalQty = orZero(dec(row.get("totalQty")));
                row.put("unitRate", unitRate);
                row.put("amountPerUnit", perUom.multiply(unitRate)
                        .setScale(4, RoundingMode.HALF_UP));
                row.put("totalAmount", totalQty.multiply(unitRate)
                        .setScale(2, RoundingMode.HALF_UP));
                if (!budgeted) {
                    row.put("basis", row.get("basis") + " · qty=contract (no budget qty yet)");
                }
                priced.add(row);
            }
            if (!priced.isEmpty()) {
                db.run(Insert.into(E_BUILDUP).entries(priced));
            }
            recipeFound++;
        }

        StringBuilder message = new StringBuilder()
                .append(boq.get("boqId")).append(" build-up: ")
                .append(recipeFound).append(" recipe-found · ")
                .append(manualKept).append(" manual kept · ")
                .append(noRecipe).append(" no-recipe · ")
                .append(unmapped).append(" unmapped · ")
                .append(rateMissing).append(" rate-missing.");
        if (!gaps.isEmpty()) {
            message.append(" Gaps: ")
                    .append(String.join("; ", gaps.subList(0, Math.min(4, gaps.size()))))
                    .append(gaps.size() > 4 ? " …" : "");
        }
        context.put("result", message.toString());
        context.setCompleted();
    }

    // ------------------------------------------------------------- generation

    /** Material: line qty x consumption x (1 + wastage). Difficulty stays out. */
    private Map<String, Object> materialRow(String itemId, Row norm, BigDecimal qty) {
        BigDecimal cons = orZero(dec(norm.get("consRate")));
        BigDecimal wastage = orZero(dec(norm.get("wastageAllowancePct")));
        BigDecimal perUom = cons.multiply(BigDecimal.ONE.add(
                wastage.divide(new BigDecimal("100"), 6, RoundingMode.HALF_UP)));

        Map<String, Object> row = base(itemId, str(norm.get("material_ID")));
        row.put("qtyPerUom", perUom.setScale(4, RoundingMode.HALF_UP));
        row.put("totalQty", qty.multiply(perUom).setScale(3, RoundingMode.HALF_UP));
        row.put("uom", norm.get("consUoM"));
        row.put("sourceNorm", "ConsumptionRate/" + str(norm.get("ID")));
        // Difficulty never touches material consumption; wastage is the
        // material-side allowance (KX-BUD-014).
        row.put("difficultyPct", new BigDecimal("100"));
        row.put("difficultySrc", "none");
        row.put("basis", "cons " + cons.stripTrailingZeros().toPlainString()
                + " + wastage " + wastage.stripTrailingZeros().toPlainString() + "%");
        return row;
    }

    /**
     * Manpower and equipment: hours = qty / output x difficulty, once (CALC-03).
     *
     * The crew composition then EXPANDS the hours across the crew, it does not
     * divide them (CALC-02): "1 SK + 1 HLP" on 800 crew-hours is 800
     * skilled-hours AND 800 helper-hours - every member of the crew is present
     * for every crew-hour. Each role becomes its own demand line; a role token
     * that matches a resource code resolves to that resource, otherwise the
     * line stays on the norm resource with the role named, because a
     * role-to-resource mapping master does not exist yet and inventing one
     * silently would hide the gap.
     */
    private List<Map<String, Object>> productivityRows(String itemId, Row norm, BigDecimal qty,
                                                       BigDecimal difficulty) {
        List<Map<String, Object>> rows = new ArrayList<>();
        BigDecimal output = dec(norm.get("outputPerHr"));
        if (output == null || output.signum() <= 0) {
            return rows;   // validation refuses these now; legacy rows are skipped
        }
        BigDecimal factor = difficulty.divide(new BigDecimal("100"), 6, RoundingMode.HALF_UP);
        BigDecimal hoursPerUom = BigDecimal.ONE.divide(output, 6, RoundingMode.HALF_UP)
                .multiply(factor);
        String stdText = "std " + output.stripTrailingZeros().toPlainString() + "/hr x "
                + difficulty.stripTrailingZeros().toPlainString() + "%";
        String normRef = "ProductivityRate/" + str(norm.get("ID"));

        List<String[]> roles = parseCrew(str(norm.get("crewComposition")));

        if (roles.isEmpty()) {
            rows.add(demandRow(itemId, str(norm.get("resource_ID")),
                    hoursPerUom, BigDecimal.ONE, qty, stdText, normRef, difficulty));
            return rows;
        }

        for (String[] role : roles) {
            BigDecimal count = new BigDecimal(role[0]);
            String token = role[1];
            String resourceId = resourceIdByCode(token);
            boolean resolved = resourceId != null;
            if (!resolved) {
                resourceId = str(norm.get("resource_ID"));
            }
            rows.add(demandRow(itemId, resourceId, hoursPerUom, count, qty,
                    stdText + " · role " + token + " x" + role[0]
                            + (resolved ? "" : " (unmapped role - on norm resource)"),
                    normRef, difficulty));
        }
        return rows;
    }

    private Map<String, Object> demandRow(String itemId, String resourceId,
                                          BigDecimal hoursPerUom, BigDecimal count,
                                          BigDecimal qty, String basis, String normRef,
                                          BigDecimal difficulty) {
        Map<String, Object> row = base(itemId, resourceId);
        BigDecimal perUom = hoursPerUom.multiply(count);
        row.put("qtyPerUom", perUom.setScale(4, RoundingMode.HALF_UP));
        row.put("totalQty", qty.multiply(perUom).setScale(3, RoundingMode.HALF_UP));
        row.put("uom", "hr");
        row.put("basis", basis);
        row.put("sourceNorm", normRef);
        row.put("difficultyPct", difficulty);
        row.put("difficultySrc",
                difficulty.compareTo(new BigDecimal("100")) == 0 ? "none" : "project");
        return row;
    }

    /** "1 SK + 1 HLP" becomes [[1,SK],[1,HLP]]. Tolerant of spacing. */
    private static List<String[]> parseCrew(String crew) {
        List<String[]> roles = new ArrayList<>();
        if (crew == null || crew.isBlank()) {
            return roles;
        }
        for (String part : crew.split("\\+")) {
            String[] tokens = part.trim().split("\\s+");
            if (tokens.length >= 2 && tokens[0].matches("\\d+")) {
                roles.add(new String[] { tokens[0], tokens[1] });
            }
        }
        return roles;
    }

    private String resourceIdByCode(String code) {
        return db.run(Select.from(E_RESOURCE).where(r -> r.get("code").eq(code)))
                .first().map(r -> str(r.get("ID"))).orElse(null);
    }

    private String resourceCode(String resourceId) {
        if (resourceId == null) {
            return "?";
        }
        return db.run(Select.from(E_RESOURCE).where(r -> r.get("ID").eq(resourceId)))
                .first().map(r -> str(r.get("code"))).orElse(resourceId);
    }

    private Map<String, Object> base(String itemId, String resourceId) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("ID", UUID.randomUUID().toString());
        row.put("boqItem_ID", itemId);
        row.put("resource_ID", resourceId);
        row.put("category", verticalOf(resourceId));
        row.put("source", "RECIPE");
        return row;
    }

    // ------------------------------------------------------------- resolution

    /**
     * The recipe rows for one CBS leaf: rows whose linkedCBS is the leaf, the
     * company override beating the group default per resource — the same
     * scope rule the money rates follow.
     */
    private List<Row> recipeRows(String entity, String subjectField, String leafId,
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

    private String libraryLeafOf(Row item) {
        Object cbsId = item.get("cbs_ID");
        if (cbsId == null) {
            return null;
        }
        return db.run(Select.from(E_CBS_INSTANCE).where(c -> c.get("ID").eq(cbsId.toString())))
                .first()
                .map(r -> str(r.get("libraryNode_ID")))
                .orElse(null);
    }

    /** Latest money rate in force today, company beating group - or null. */
    private BigDecimal moneyRate(String resourceId, String companyId) {
        if (resourceId == null) {
            return null;
        }
        java.time.LocalDate today = java.time.LocalDate.now();
        Row best = null;
        boolean bestIsCompany = false;
        java.time.LocalDate bestFrom = null;
        for (Row rate : db.run(Select.from(E_RATE).where(r -> r.get("resource_ID").eq(resourceId)))) {
            java.time.LocalDate from = dateOf(rate.get("effectiveFrom"));
            if (from == null || from.isAfter(today)) {
                continue;
            }
            String owner = str(rate.get("owningCompany_ID"));
            boolean isCompany = companyId != null && companyId.equalsIgnoreCase(owner);
            boolean isGroup = owner == null;
            if (!isCompany && !isGroup) {
                continue;
            }
            if (best == null || (isCompany && !bestIsCompany)
                    || (isCompany == bestIsCompany && from.isAfter(bestFrom))) {
                best = rate;
                bestIsCompany = isCompany;
                bestFrom = from;
            }
        }
        return best == null ? null : dec(best.get("rateValue"));
    }

    private static java.time.LocalDate dateOf(Object v) {
        if (v == null) { return null; }
        if (v instanceof java.time.LocalDate d) { return d; }
        try { return java.time.LocalDate.parse(String.valueOf(v).substring(0, 10)); }
        catch (RuntimeException e) { return null; }
    }

    private String verticalOf(String resourceId) {
        if (resourceId == null) {
            return null;
        }
        return db.run(Select.from(E_RESOURCE).where(r -> r.get("ID").eq(resourceId)))
                .first().map(r -> str(r.get("verticalType"))).orElse(null);
    }

    private String companyOf(Row boq) {
        Object projectId = boq.get("project_ID");
        if (projectId == null) {
            return null;
        }
        return db.run(Select.from(E_PROJECT).where(p -> p.get("ID").eq(projectId.toString())))
                .first().map(r -> str(r.get("company_ID"))).orElse(null);
    }

    private int countManual(String itemId) {
        int count = 0;
        for (Row row : db.run(Select.from(E_BUILDUP).where(b -> b.get("boqItem_ID").eq(itemId)
                .and(b.get("source").eq("MANUAL"))))) {
            count++;
        }
        return count;
    }

    @Autowired
    private BudgetGateService gate;

    @On(event = "validateForBudget", entity = "ProjectService.Projects")
    public void onValidate(EventContext context) {
        Row project = db.run((CqnSelect) context.get("cqn")).first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "Project not found."));
        List<Map<String, Object>> out = new ArrayList<>();
        for (BudgetGateService.RuleResult rule : gate.evaluate(str(project.get("ID")))) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("ruleId", rule.ruleId);
            row.put("description", rule.description);
            row.put("linesChecked", rule.linesChecked);
            row.put("failing", rule.failing);
            row.put("result", rule.result());
            out.add(row);
        }
        context.put("result", out);
        context.setCompleted();
    }

    private Row targetOf(EventContext context) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        return (select == null ? Optional.<Row>empty() : db.run(select).first())
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "Bill of quantities not found."));
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
