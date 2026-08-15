package com.inflexion.konstryx.bud;

import com.sap.cds.CdsData;
import com.sap.cds.Row;
import com.sap.cds.ql.Delete;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.request.UserInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import com.inflexion.konstryx.apr.ApprovalEngine;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;
import java.util.UUID;

/**
 * The budget engine.
 *
 * Two taxonomies live here and they must never be conflated. A line's cost
 * nature is one of the six verticals, carried from the resource build-up the
 * line was generated from. The movement ledger is the four categories of
 * KX-BUD-004 — Original, Shift, Risk Transfer, Variation — and every dirham
 * of budget movement is exactly one ledger entry. After baseline a line's
 * amount is nothing but the sum of its ledger entries, which is what keeps
 * "why is this number this number" answerable a year later.
 */
@Component
@ServiceName("BudgetService")
public class BudgetHandler implements EventHandler {

    private static final String E_BUDGET = "konstryx.bud.Budget";
    private static final String E_LINE = "konstryx.bud.BudgetLine";
    private static final String E_LEDGER = "konstryx.bud.BudgetLedgerEntry";
    private static final String E_BUILDUP = "konstryx.prj.BOQItemResource";
    private static final String E_BOQ = "konstryx.prj.BOQ";
    private static final String E_BOQ_ITEM = "konstryx.prj.BOQItem";
    private static final String E_CBS = "konstryx.prj.CBSInstance";
    private static final String E_RATE = "konstryx.master.RateMaster";
    private static final String E_RESOURCE = "konstryx.master.ResourceNode";
    private static final String E_RES_LINE = "konstryx.wf.ReservationLine";
    private static final String E_RR_LINE = "konstryx.wf.ResourceRequestLine";

    @Autowired
    private PersistenceService db;

    @Autowired
    private ApprovalEngine approvals;

    @Autowired
    private UserInfo userInfo;

    // ---------------------------------------------------------------- generate

    @On(event = "generateLines", entity = "BudgetService.Budgets")
    public void onGenerate(EventContext context) {
        Row budget = targetOf(context);
        String budgetId = str(budget.get("ID"));
        String status = str(budget.get("status"));

        if ("Baselined".equals(status) || "Locked".equals(status)) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    budget.get("docNo") + " is " + status + " — a baselined budget moves "
                            + "through its ledger, it is not regenerated.");
        }
        String projectId = str(budget.get("project_ID"));
        if (projectId == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The budget names no project, so there is no build-up to price.");
        }
        String companyId = str(budget.get("company_ID"));

        // The priced build-up, grouped by CBS x cost nature.
        Map<String, BigDecimal> amounts = new TreeMap<>();
        Map<String, String> cbsOf = new HashMap<>();
        Map<String, String> categoryOf = new HashMap<>();
        List<String> unpriced = new ArrayList<>();
        int rows = 0;

        for (Row buildUp : buildUpOf(projectId)) {
            rows++;
            String resourceId = str(buildUp.get("resource_ID"));
            BigDecimal qty = dec(buildUp.get("totalQty"));
            String category = str(buildUp.get("category"));
            String cbsId = cbsOfItem(str(buildUp.get("boqItem_ID")));
            if (qty == null || cbsId == null) {
                continue;
            }
            BigDecimal rate = rateFor(resourceId, companyId);
            if (rate == null) {
                unpriced.add(resourceCode(resourceId));
                continue;
            }
            String key = cbsId + "|" + category;
            amounts.merge(key, qty.multiply(rate).setScale(2, RoundingMode.HALF_UP),
                    BigDecimal::add);
            cbsOf.put(key, cbsId);
            categoryOf.put(key, category);
        }

        if (rows == 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The project has no resource build-up. Generate it on the bill first "
                            + "— a budget not built from the build-up is a typed number.");
        }
        if (!unpriced.isEmpty()) {
            // Refused whole. A budget with a hole where a rate should be is not
            // conservative — it is wrong by exactly the size of the hole.
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "No rate in force for: " + String.join(", ",
                            unpriced.stream().distinct().toList())
                            + ". Price every resource before generating the budget.");
        }

        // Regeneration before baseline replaces everything, ledger included.
        db.run(Delete.from(E_LEDGER).where(l -> l.get("budget_ID").eq(budgetId)));
        db.run(Delete.from(E_LINE).where(l -> l.get("budget_ID").eq(budgetId)));

        BigDecimal total = BigDecimal.ZERO;
        for (Map.Entry<String, BigDecimal> entry : amounts.entrySet()) {
            String lineId = UUID.randomUUID().toString();
            Map<String, Object> line = new LinkedHashMap<>();
            line.put("ID", lineId);
            line.put("budget_ID", budgetId);
            line.put("cbs_ID", cbsOf.get(entry.getKey()));
            line.put("category", categoryOf.get(entry.getKey()));
            line.put("amount", entry.getValue());
            line.put("authorised", BigDecimal.ZERO);
            line.put("committed", BigDecimal.ZERO);
            line.put("encumbered", BigDecimal.ZERO);
            line.put("actual", BigDecimal.ZERO);
            line.put("available", entry.getValue());
            db.run(Insert.into(E_LINE).entry(line));

            ledger(budgetId, lineId, "ORIGINAL", entry.getValue(),
                    str(budget.get("docNo")), "Generated from the resource build-up", null);
            total = total.add(entry.getValue());
        }

        Map<String, Object> patch = new HashMap<>();
        patch.put("totalAmount", total);
        db.run(Update.entity(E_BUDGET).data(patch).where(b -> b.get("ID").eq(budgetId)));

        result(context, budget.get("docNo") + ": " + amounts.size()
                + " line(s) totalling " + total.toPlainString()
                + ", each with its ORIGINAL ledger entry.");
    }

    // ------------------------------------------------------ submit and baseline

    @On(event = "submit", entity = "BudgetService.Budgets")
    public void onSubmit(EventContext context) {
        Row budget = targetOf(context);
        String status = str(budget.get("status"));
        if (!(status == null || status.isBlank() || "Draft".equals(status)
                || "Rejected".equals(status))) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    budget.get("docNo") + " is " + status + ".");
        }
        BigDecimal total = dec(budget.get("totalAmount"));
        if (total == null || total.signum() <= 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Generate the lines first — an empty budget cannot be approved.");
        }

        Map<String, Object> outcome = approvals.submit(E_BUDGET, str(budget.get("ID")),
                str(budget.get("docNo")), total, str(budget.get("company_ID")),
                userInfo.getName());

        Map<String, Object> patch = new HashMap<>();
        patch.put("status", "In Approval");
        String budgetId = str(budget.get("ID"));
        db.run(Update.entity(E_BUDGET).data(patch).where(b -> b.get("ID").eq(budgetId)));

        result(context, budget.get("docNo") + " submitted at " + total.toPlainString()
                + ". " + outcome.get("message"));
    }

    @On(event = "baseline", entity = "BudgetService.Budgets")
    public void onBaseline(EventContext context) {
        Row budget = targetOf(context);
        if (!"Approved".equals(str(budget.get("status")))) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    budget.get("docNo") + " is " + budget.get("status")
                            + " — only an approved budget baselines.");
        }
        Map<String, Object> patch = new HashMap<>();
        patch.put("status", "Baselined");
        String budgetId = str(budget.get("ID"));
        db.run(Update.entity(E_BUDGET).data(patch).where(b -> b.get("ID").eq(budgetId)));

        result(context, budget.get("docNo") + " is baselined. From here the amounts move "
                + "only through the ledger.");
    }

    /**
     * The lock that makes the ledger the only door. Without this, "the amount
     * moves only through ledger entries" is a comment, not a rule.
     */
    @Before(event = CqnService.EVENT_UPDATE, entity = "BudgetService.BudgetLines")
    public void guardBaselinedLines(EventContext context, List<CdsData> lines) {
        for (CdsData line : lines) {
            if (!line.containsKey("amount") && !line.containsKey("category")) {
                continue;
            }
            String lineId = str(line.get("ID"));
            if (lineId == null) {
                continue;
            }
            Optional<Row> stored = db.run(Select.from(E_LINE)
                    .where(l -> l.get("ID").eq(lineId))).first();
            if (stored.isEmpty()) {
                continue;
            }
            Object budgetId = stored.get().get("budget_ID");
            String status = budgetId == null ? null : db.run(Select.from(E_BUDGET)
                    .where(b -> b.get("ID").eq(budgetId.toString()))).first()
                    .map(b -> str(b.get("status"))).orElse(null);
            if ("Baselined".equals(status) || "Locked".equals(status)) {
                throw new ServiceException(ErrorStatuses.FORBIDDEN,
                        "This budget is " + status.toLowerCase()
                                + ". Amounts move through the ledger — shift, risk transfer "
                                + "or variation — never by editing the line.");
            }
        }
    }

    // -------------------------------------------------------------------- shift

    @On(event = "shift", entity = "BudgetService.Budgets")
    public void onShift(EventContext context) {
        Row budget = targetOf(context);
        String budgetId = str(budget.get("ID"));
        if (!"Baselined".equals(str(budget.get("status")))) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "Shifts apply to a baselined budget; " + budget.get("docNo")
                            + " is " + budget.get("status") + ".");
        }

        BigDecimal amount = dec(context.get("amount"));
        if (amount == null || amount.signum() <= 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A shift needs a positive amount.");
        }
        String reason = str(context.get("reason"));
        if (reason == null || reason.isBlank()) {
            // Ten unexplained shifts later, nobody can say why waterproofing
            // sits at 1.4m. The reason is the ledger's whole value.
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A shift without a reason defeats the ledger. Say why.");
        }

        Row from = lineOf(budgetId, str(context.get("fromCBS")), str(context.get("fromCategory")));
        Row to = lineOf(budgetId, str(context.get("toCBS")), str(context.get("toCategory")));
        if (str(from.get("ID")).equals(str(to.get("ID")))) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A shift onto the same line moves nothing.");
        }

        BigDecimal fromAvailable = orZero(dec(from.get("available")));
        if (amount.compareTo(fromAvailable) > 0) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "Only " + fromAvailable.toPlainString() + " is available to shift — "
                            + "the rest is already encumbered or spent.");
        }

        String pairKey = UUID.randomUUID().toString();
        ledger(budgetId, str(from.get("ID")), "SHIFT", amount.negate(),
                str(budget.get("docNo")), reason, pairKey);
        ledger(budgetId, str(to.get("ID")), "SHIFT", amount,
                str(budget.get("docNo")), reason, pairKey);

        adjust(from, amount.negate());
        adjust(to, amount);

        result(context, amount.toPlainString() + " shifted. Two SHIFT entries share pair "
                + pairKey.substring(0, 8) + "; the budget total is unchanged.");
    }

    private void adjust(Row line, BigDecimal delta) {
        String lineId = str(line.get("ID"));
        BigDecimal amount = orZero(dec(line.get("amount"))).add(delta);
        BigDecimal available = orZero(dec(line.get("available"))).add(delta);
        Map<String, Object> patch = new HashMap<>();
        patch.put("amount", amount);
        patch.put("available", available);
        db.run(Update.entity(E_LINE).data(patch).where(l -> l.get("ID").eq(lineId)));
    }

    // ----------------------------------------------------------------- control

    @On(event = "refreshControl", entity = "BudgetService.Budgets")
    public void onRefresh(EventContext context) {
        Row budget = targetOf(context);
        String budgetId = str(budget.get("ID"));

        int touched = 0;
        for (Row line : db.run(Select.from(E_LINE).where(l -> l.get("budget_ID").eq(budgetId)))) {
            String cbsId = str(line.get("cbs_ID"));
            String category = str(line.get("category"));
            BigDecimal encumbered = encumbranceFor(cbsId, category);

            BigDecimal amount = orZero(dec(line.get("amount")));
            BigDecimal committed = orZero(dec(line.get("committed")));
            BigDecimal actual = orZero(dec(line.get("actual")));
            BigDecimal available = amount.subtract(committed).subtract(encumbered).subtract(actual);

            Map<String, Object> patch = new HashMap<>();
            patch.put("encumbered", encumbered);
            patch.put("available", available);
            if (amount.signum() > 0) {
                patch.put("availPct", available.multiply(new BigDecimal("100"))
                        .divide(amount, 2, RoundingMode.HALF_UP));
                patch.put("usedPct", new BigDecimal("100").subtract(
                        available.multiply(new BigDecimal("100"))
                                .divide(amount, 2, RoundingMode.HALF_UP)));
            }
            String lineId = str(line.get("ID"));
            db.run(Update.entity(E_LINE).data(patch).where(l -> l.get("ID").eq(lineId)));
            touched++;
        }

        result(context, budget.get("docNo") + ": encumbrance refreshed on " + touched
                + " line(s) from open reservations. Committed and actual are S/4's to "
                + "fill and were not touched.");
    }

    /**
     * Open reservation encumbrance charged to this CBS in this cost nature.
     * The match runs reservation line -> request line -> CBS, and the nature
     * comes from the reserved resource's vertical.
     */
    private BigDecimal encumbranceFor(String cbsId, String category) {
        BigDecimal total = BigDecimal.ZERO;
        if (cbsId == null) {
            return total;
        }
        for (Row resLine : db.run(Select.from(E_RES_LINE))) {
            if ("Closed".equals(str(resLine.get("lineStatus")))) {
                continue;
            }
            Object rrLineId = resLine.get("rrLine_ID");
            if (rrLineId == null) {
                continue;
            }
            Optional<Row> rrLine = db.run(Select.from(E_RR_LINE)
                    .where(l -> l.get("ID").eq(rrLineId.toString()))).first();
            if (rrLine.isEmpty() || !cbsId.equals(str(rrLine.get().get("cbs_ID")))) {
                continue;
            }
            if (category != null
                    && !category.equals(verticalOf(str(resLine.get("resource_ID"))))) {
                continue;
            }
            total = total.add(orZero(dec(resLine.get("encumberedAmount"))));
        }
        return total;
    }

    // ----------------------------------------------------------------- helpers

    private List<Row> buildUpOf(String projectId) {
        List<String> itemIds = new ArrayList<>();
        for (Row boq : db.run(Select.from(E_BOQ).where(b -> b.get("project_ID").eq(projectId)))) {
            String boqId = str(boq.get("ID"));
            for (Row item : db.run(Select.from(E_BOQ_ITEM).where(i -> i.get("boq_ID").eq(boqId)))) {
                itemIds.add(str(item.get("ID")));
            }
        }
        List<Row> rows = new ArrayList<>();
        for (String itemId : itemIds) {
            for (Row buildUp : db.run(Select.from(E_BUILDUP)
                    .where(b -> b.get("boqItem_ID").eq(itemId)))) {
                rows.add(buildUp);
            }
        }
        return rows;
    }

    private String cbsOfItem(String itemId) {
        if (itemId == null) {
            return null;
        }
        return db.run(Select.from(E_BOQ_ITEM).where(i -> i.get("ID").eq(itemId)))
                .first().map(r -> str(r.get("cbs_ID"))).orElse(null);
    }

    private Row lineOf(String budgetId, String cbsCode, String category) {
        if (cbsCode == null || category == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Name both lines by CBS code and cost nature.");
        }
        for (Row line : db.run(Select.from(E_LINE).where(l -> l.get("budget_ID").eq(budgetId)))) {
            if (!category.equals(str(line.get("category")))) {
                continue;
            }
            Object cbsId = line.get("cbs_ID");
            if (cbsId != null) {
                Optional<Row> cbs = db.run(Select.from(E_CBS)
                        .where(c -> c.get("ID").eq(cbsId.toString()))).first();
                if (cbs.isPresent() && cbsCode.equals(str(cbs.get().get("code")))) {
                    return line;
                }
            }
        }
        throw new ServiceException(ErrorStatuses.NOT_FOUND,
                "This budget has no " + category + " line on CBS " + cbsCode + ".");
    }

    private void ledger(String budgetId, String lineId, String category, BigDecimal amount,
                        String reference, String reason, String pairKey) {
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("ID", UUID.randomUUID().toString());
        entry.put("budget_ID", budgetId);
        entry.put("line_ID", lineId);
        entry.put("category", category);
        entry.put("amount", amount);
        entry.put("reference", reference);
        entry.put("reason", reason);
        entry.put("pairKey", pairKey);
        db.run(Insert.into(E_LEDGER).entry(entry));
    }

    /** Latest rate in force today, the budget's company beating group. */
    private BigDecimal rateFor(String resourceId, String companyId) {
        if (resourceId == null) {
            return null;
        }
        LocalDate today = LocalDate.now();
        Row best = null;
        boolean bestIsCompany = false;
        LocalDate bestFrom = null;
        for (Row rate : db.run(Select.from(E_RATE).where(r -> r.get("resource_ID").eq(resourceId)))) {
            LocalDate from = date(rate.get("effectiveFrom"));
            if (from == null || from.isAfter(today)) {
                continue;
            }
            String owner = str(rate.get("owningCompany_ID"));
            boolean isCompany = companyId != null && companyId.equalsIgnoreCase(owner);
            boolean isGroup = owner == null;
            if (!isCompany && !isGroup) {
                continue;
            }
            if (best == null
                    || (isCompany && !bestIsCompany)
                    || (isCompany == bestIsCompany && from.isAfter(bestFrom))) {
                best = rate;
                bestIsCompany = isCompany;
                bestFrom = from;
            }
        }
        return best == null ? null : dec(best.get("rateValue"));
    }

    private String resourceCode(String resourceId) {
        if (resourceId == null) {
            return "?";
        }
        return db.run(Select.from(E_RESOURCE).where(r -> r.get("ID").eq(resourceId)))
                .first().map(r -> str(r.get("code"))).orElse(resourceId);
    }

    private String verticalOf(String resourceId) {
        if (resourceId == null) {
            return null;
        }
        return db.run(Select.from(E_RESOURCE).where(r -> r.get("ID").eq(resourceId)))
                .first().map(r -> str(r.get("verticalType"))).orElse(null);
    }

    private Row targetOf(EventContext context) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        return (select == null ? Optional.<Row>empty() : db.run(select).first())
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "Budget not found."));
    }

    private static void result(EventContext context, String message) {
        context.put("result", message);
        context.setCompleted();
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static BigDecimal orZero(BigDecimal v) { return v == null ? BigDecimal.ZERO : v; }

    private static BigDecimal dec(Object v) {
        if (v == null) { return null; }
        if (v instanceof BigDecimal b) { return b; }
        try { return new BigDecimal(String.valueOf(v)); }
        catch (NumberFormatException e) { return null; }
    }

    private static LocalDate date(Object v) {
        if (v == null) { return null; }
        if (v instanceof LocalDate d) { return d; }
        try { return LocalDate.parse(String.valueOf(v).substring(0, 10)); }
        catch (RuntimeException e) { return null; }
    }
}
