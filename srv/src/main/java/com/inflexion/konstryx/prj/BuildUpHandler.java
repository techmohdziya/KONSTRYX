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
            BigDecimal qty = dec(item.get("qty"));
            if (qty == null) {
                qty = BigDecimal.ZERO;
            }

            for (Row norm : recipeRows(E_CONSUMPTION, "material_ID", libraryLeaf, companyId)) {
                rows.add(materialRow(itemId, norm, qty));
            }
            for (Row norm : recipeRows(E_PRODUCTIVITY, "resource_ID", libraryLeaf, companyId)) {
                Map<String, Object> row = productivityRow(itemId, norm, qty, difficulty);
                if (row != null) {
                    rows.add(row);
                }
            }

            if (rows.isEmpty()) {
                noRecipe++;
                gaps.add(item.get("itemNo") + ": no recipe on its CBS leaf");
                continue;
            }

            for (Map<String, Object> row : rows) {
                if (!hasMoneyRate(str(row.get("resource_ID")))) {
                    rateMissing++;
                    row.put("basis", row.get("basis") + " · RATE MISSING");
                }
            }
            db.run(Insert.into(E_BUILDUP).entries(rows));
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
        row.put("basis", "cons " + cons.stripTrailingZeros().toPlainString()
                + " + wastage " + wastage.stripTrailingZeros().toPlainString() + "%");
        return row;
    }

    /**
     * Manpower and equipment: hours = qty / output x difficulty. The norm is
     * the central standard; difficulty rides on top and is recorded in the
     * basis so "std 0.20 x 110%" is readable on the row itself.
     */
    private Map<String, Object> productivityRow(String itemId, Row norm, BigDecimal qty,
                                                BigDecimal difficulty) {
        BigDecimal output = dec(norm.get("outputPerHr"));
        if (output == null || output.signum() <= 0) {
            return null;   // validation refuses these now; legacy rows are skipped
        }
        BigDecimal factor = difficulty.divide(new BigDecimal("100"), 6, RoundingMode.HALF_UP);
        BigDecimal hoursPerUom = BigDecimal.ONE.divide(output, 6, RoundingMode.HALF_UP)
                .multiply(factor);

        Map<String, Object> row = base(itemId, str(norm.get("resource_ID")));
        row.put("qtyPerUom", hoursPerUom.setScale(4, RoundingMode.HALF_UP));
        row.put("totalQty", qty.multiply(hoursPerUom).setScale(3, RoundingMode.HALF_UP));
        row.put("uom", "hr");
        String crew = str(norm.get("crewComposition"));
        row.put("basis", "std " + output.stripTrailingZeros().toPlainString() + "/hr x "
                + difficulty.stripTrailingZeros().toPlainString() + "%"
                + (crew == null ? "" : " · crew " + crew));
        return row;
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
        for (Row norm : db.run(Select.from(entity)
                .where(n -> n.get("linkedCBS_ID").eq(leafId)))) {
            String subject = str(norm.get(subjectField));
            if (subject == null) {
                continue;
            }
            String owner = str(norm.get("owningCompany_ID"));
            boolean isCompany = companyId != null && companyId.equalsIgnoreCase(owner);
            boolean isGroup = owner == null;
            if (!isCompany && !isGroup) {
                continue;   // another company's local norm
            }
            Row current = bySubject.get(subject);
            if (current == null) {
                bySubject.put(subject, norm);
            } else {
                boolean currentIsCompany = companyId != null
                        && companyId.equalsIgnoreCase(str(current.get("owningCompany_ID")));
                if (isCompany && !currentIsCompany) {
                    bySubject.put(subject, norm);
                }
            }
        }
        return new ArrayList<>(bySubject.values());
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

    private boolean hasMoneyRate(String resourceId) {
        if (resourceId == null) {
            return false;
        }
        return db.run(Select.from(E_RATE).where(r -> r.get("resource_ID").eq(resourceId)))
                .first().isPresent();
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
