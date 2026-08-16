package com.inflexion.konstryx.prj;

import com.sap.cds.Row;
import com.sap.cds.ql.Insert;
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
import java.util.UUID;

/**
 * Allocation, and the project's own cost breakdown structure.
 *
 * Allocation is where the commercial view meets the cost view: a bill line says
 * what was sold, a WBS element says where the work happens, and a CBS node says
 * which cost bucket carries it. Until a line is allocated it contributes
 * revenue with no cost home, which is why an unallocated bill is the usual
 * reason a project cannot be reconciled.
 *
 * The rule that earns its place here is the over-allocation guard. Allocating
 * 60% of a line to one WBS and 60% to another is arithmetically possible and
 * commercially meaningless, and nothing in the data model prevents it — the
 * quantities live on separate rows.
 */
@Component
@ServiceName("ProjectService")
public class AllocationHandler implements EventHandler {

    private static final String E_ITEM = "konstryx.prj.BOQItem";
    private static final String E_BOQ = "konstryx.prj.BOQ";
    private static final String E_ALLOC = "konstryx.prj.Allocation";
    private static final String E_WBS = "konstryx.prj.WBSElement";
    private static final String E_CBS_INSTANCE = "konstryx.prj.CBSInstance";
    private static final String E_CBS_LIBRARY = "konstryx.master.CBSNode";
    private static final String E_PROJECT = "konstryx.prj.Project";

    @Autowired
    private PersistenceService db;

    // ------------------------------------------------------------- allocation

    @On(event = "allocate")
    public void onAllocate(EventContext context) {
        Row item = targetOf(context, "Bill line not found.");
        String itemId = str(item.get("ID"));

        BigDecimal itemQty = dec(item.get("qty"));
        if (itemQty == null || itemQty.signum() <= 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Line " + item.get("itemNo") + " has no quantity to allocate.");
        }

        BigDecimal qty = dec(context.get("qty"));
        if (qty == null || qty.signum() <= 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Say how much of the line to allocate.");
        }

        String projectId = projectOf(item);
        Row wbs = findWbs(str(context.get("wbsCode")), projectId);
        Row cbs = findCbs(str(context.get("cbsCode")), projectId);

        BigDecimal already = allocatedSoFar(itemId, null);
        BigDecimal after = already.add(qty);
        if (after.compareTo(itemQty) > 0) {
            BigDecimal left = itemQty.subtract(already);
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "Line " + item.get("itemNo") + " has " + left.toPlainString() + " of "
                            + itemQty.toPlainString() + " left to allocate; this asks for "
                            + qty.toPlainString() + ".");
        }

        BigDecimal pct = qty.multiply(new BigDecimal("100"))
                .divide(itemQty, 2, RoundingMode.HALF_UP);

        Map<String, Object> allocation = new LinkedHashMap<>();
        allocation.put("ID", UUID.randomUUID().toString());
        allocation.put("boqItem_ID", itemId);
        allocation.put("wbs_ID", wbs.get("ID"));
        allocation.put("cbs_ID", cbs.get("ID"));
        allocation.put("allocQty", qty);
        allocation.put("allocPct", pct);
        allocation.put("pctOfItem", after.multiply(new BigDecimal("100"))
                .divide(itemQty, 2, RoundingMode.HALF_UP));
        db.run(Insert.into(E_ALLOC).entry(allocation));

        BigDecimal budget = rollUpCbs(str(cbs.get("ID")));

        BigDecimal remaining = itemQty.subtract(after);
        return_(context, qty.toPlainString() + " of line " + item.get("itemNo")
                + " allocated to " + wbs.get("code") + " / " + cbs.get("code") + ". "
                + (remaining.signum() == 0
                        ? "The line is now fully allocated."
                        : remaining.toPlainString() + " still unallocated.")
                + " " + cbs.get("code") + " now carries " + budget.toPlainString() + ".");
    }

    /**
     * What a CBS node carries is the sum of what has been allocated to it,
     * priced at the bill rate. Stored rather than computed on read because a
     * budget is compared against it constantly and the join is over three
     * tables.
     */
    private BigDecimal rollUpCbs(String cbsId) {
        BigDecimal total = BigDecimal.ZERO;
        for (Row allocation : db.run(Select.from(E_ALLOC).where(a -> a.get("cbs_ID").eq(cbsId)))) {
            BigDecimal qty = dec(allocation.get("allocQty"));
            Object itemId = allocation.get("boqItem_ID");
            if (qty == null || itemId == null) {
                continue;
            }
            Optional<Row> item = db.run(Select.from(E_ITEM)
                    .where(i -> i.get("ID").eq(itemId.toString()))).first();
            BigDecimal rate = item.map(r -> dec(r.get("rate"))).orElse(null);
            if (rate != null) {
                total = total.add(qty.multiply(rate));
            }
        }
        total = total.setScale(2, RoundingMode.HALF_UP);

        Map<String, Object> update = new HashMap<>();
        update.put("budgetAmount", total);
        db.run(Update.entity(E_CBS_INSTANCE).data(update).where(c -> c.get("ID").eq(cbsId)));
        return total;
    }

    private BigDecimal allocatedSoFar(String itemId, String exceptId) {
        BigDecimal total = BigDecimal.ZERO;
        for (Row allocation : db.run(Select.from(E_ALLOC)
                .where(a -> a.get("boqItem_ID").eq(itemId)))) {
            if (exceptId != null && exceptId.equals(str(allocation.get("ID")))) {
                continue;
            }
            BigDecimal qty = dec(allocation.get("allocQty"));
            if (qty != null) {
                total = total.add(qty);
            }
        }
        return total;
    }

    // ------------------------------------------------------------ distribution

    private static final List<String> TEMPLATES =
            List.of("TPL-SINGLE", "TPL-FLOORS", "TPL-ZONES");

    /**
     * The template distribution: one decision, many lines. TPL-SINGLE puts each
     * line whole onto one WBS element; TPL-FLOORS and TPL-ZONES split by
     * weight. The mechanism is identical - a weighted split - and the template
     * name records WHY the weights are what they are (GFA shares, zone
     * shares), which is what the QS reads back a year later.
     *
     * Re-running REPLACES the targeted lines' allocations. Stacking a second
     * distribution on top of a first would over-allocate every line by
     * construction; a replaced decision is visible in the template column.
     * Rounding residue goes to the last target so the sum equals the contract
     * quantity exactly - VAL-02 checks to the third decimal and "nearly" is a
     * fail.
     */
    @On(event = "distributeToWBS", entity = "ProjectService.BOQs")
    public void onDistribute(EventContext context) {
        Row boq = targetOf(context, "Bill of quantities not found.");
        String boqId = str(boq.get("ID"));
        String projectId = str(boq.get("project_ID"));

        String template = str(context.get("template"));
        if (template == null || !TEMPLATES.contains(template)) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The template must be one of " + String.join(", ", TEMPLATES) + ".");
        }

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> targets =
                (List<Map<String, Object>>) context.get("targets");
        if (targets == null || targets.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Name at least one WBS target.");
        }
        if ("TPL-SINGLE".equals(template) && targets.size() != 1) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "TPL-SINGLE means one element. For a split, use TPL-FLOORS or TPL-ZONES.");
        }
        if (!"TPL-SINGLE".equals(template) && targets.size() < 2) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    template + " splits across several elements - give at least two targets.");
        }

        // Resolve every target before touching anything.
        List<Row> wbsRows = new ArrayList<>();
        List<BigDecimal> weights = new ArrayList<>();
        BigDecimal weightSum = BigDecimal.ZERO;
        for (Map<String, Object> target : targets) {
            Row wbs = findWbs(str(target.get("wbsCode")), projectId);
            BigDecimal weight = dec(target.get("weight"));
            if (weight == null) {
                weight = BigDecimal.ONE;   // no weights given: an equal split
            }
            if (weight.signum() <= 0) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "A weight of " + weight.toPlainString() + " on "
                                + target.get("wbsCode") + " distributes nothing.");
            }
            wbsRows.add(wbs);
            weights.add(weight);
            weightSum = weightSum.add(weight);
        }

        @SuppressWarnings("unchecked")
        List<String> itemNos = (List<String>) context.get("itemNos");
        boolean scoped = itemNos != null && !itemNos.isEmpty();

        int distributed = 0, skipped = 0;
        List<String> skippedNames = new ArrayList<>();
        java.util.Set<String> touchedCbs = new java.util.HashSet<>();

        for (Row item : db.run(Select.from(E_ITEM).where(i -> i.get("boq_ID").eq(boqId)))) {
            String itemNo = str(item.get("itemNo"));
            if (scoped && !itemNos.contains(itemNo)) {
                continue;
            }
            Object cbsId = item.get("cbs_ID");
            BigDecimal qty = dec(item.get("qty"));
            if (cbsId == null || qty == null || qty.signum() <= 0) {
                skipped++;
                skippedNames.add(itemNo + (cbsId == null ? " (no CBS)" : " (no qty)"));
                continue;
            }
            String itemId = str(item.get("ID"));

            // The last decision wins - and is seen to win.
            db.run(com.sap.cds.ql.Delete.from(E_ALLOC)
                    .where(a -> a.get("boqItem_ID").eq(itemId)));

            BigDecimal assigned = BigDecimal.ZERO;
            BigDecimal cumulative = BigDecimal.ZERO;
            for (int t = 0; t < wbsRows.size(); t++) {
                BigDecimal share;
                if (t == wbsRows.size() - 1) {
                    share = qty.subtract(assigned);   // residue lands here
                } else {
                    share = qty.multiply(weights.get(t))
                            .divide(weightSum, 3, RoundingMode.HALF_UP);
                }
                assigned = assigned.add(share);
                cumulative = cumulative.add(share);

                Map<String, Object> allocation = new LinkedHashMap<>();
                allocation.put("ID", UUID.randomUUID().toString());
                allocation.put("boqItem_ID", itemId);
                allocation.put("wbs_ID", wbsRows.get(t).get("ID"));
                allocation.put("cbs_ID", cbsId);
                allocation.put("allocQty", share);
                allocation.put("allocPct", share.multiply(new BigDecimal("100"))
                        .divide(qty, 2, RoundingMode.HALF_UP));
                allocation.put("pctOfItem", cumulative.multiply(new BigDecimal("100"))
                        .divide(qty, 2, RoundingMode.HALF_UP));
                allocation.put("template", template);
                allocation.put("splitBasis", "TPL-SINGLE".equals(template)
                        ? "whole line"
                        : ("TPL-FLOORS".equals(template) ? "GFA-weighted per floor"
                                : "zone-weighted") + " " + weights.get(t).stripTrailingZeros()
                                .toPlainString() + "/" + weightSum.stripTrailingZeros()
                                .toPlainString());
                db.run(Insert.into(E_ALLOC).entry(allocation));
            }
            touchedCbs.add(cbsId.toString());
            distributed++;
        }

        for (String cbs : touchedCbs) {
            rollUpCbs(cbs);
        }

        StringBuilder message = new StringBuilder(template + ": " + distributed
                + " line(s) distributed across " + wbsRows.size() + " WBS element(s)");
        if (skipped > 0) {
            message.append("; ").append(skipped).append(" skipped - ")
                    .append(String.join(", ",
                            skippedNames.subList(0, Math.min(3, skippedNames.size()))))
                    .append(skippedNames.size() > 3 ? " ..." : "");
        }
        message.append(". Prior allocations of the distributed lines were replaced.");
        return_(context, message.toString());
    }

    // ------------------------------------------------------- CBS instantiation

    @On(event = "instantiateCBS")
    public void onInstantiateCBS(EventContext context) {
        Row project = targetOf(context, "Project not found.");
        String projectId = str(project.get("ID"));

        boolean already = db.run(Select.from(E_CBS_INSTANCE)
                .where(c -> c.get("project_ID").eq(projectId))).first().isPresent();
        if (already) {
            // Re-running would duplicate the structure a project is already
            // costing against, and the allocations would point at the old copy.
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    project.get("code") + " already has a CBS. Delete it first if it "
                            + "genuinely needs rebuilding.");
        }

        List<Row> library = new ArrayList<>();
        for (Row node : db.run(Select.from(E_CBS_LIBRARY))) {
            library.add(node);
        }
        if (library.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The CBS library is empty, so there is nothing to instantiate.");
        }

        // Two passes, as the template instantiation does: create every node,
        // then link parents, because a child can be read before its parent.
        Map<String, String> libraryToInstance = new HashMap<>();
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Row node : library) {
            String id = UUID.randomUUID().toString();
            libraryToInstance.put(str(node.get("ID")), id);

            Map<String, Object> instance = new LinkedHashMap<>();
            instance.put("ID", id);
            instance.put("project_ID", projectId);
            instance.put("libraryNode_ID", node.get("ID"));
            instance.put("code", node.get("code"));
            instance.put("level", node.get("level"));
            instance.put("budgetAmount", BigDecimal.ZERO);
            rows.add(instance);
        }
        db.run(Insert.into(E_CBS_INSTANCE).entries(rows));

        int linked = 0;
        for (Row node : library) {
            String parentLibraryId = str(node.get("parent_ID"));
            String childId = libraryToInstance.get(str(node.get("ID")));
            String parentId = parentLibraryId == null ? null : libraryToInstance.get(parentLibraryId);
            if (childId == null || parentId == null) {
                continue;
            }
            Map<String, Object> patch = new HashMap<>();
            patch.put("parent_ID", parentId);
            db.run(Update.entity(E_CBS_INSTANCE).data(patch).where(c -> c.get("ID").eq(childId)));
            linked++;
        }

        return_(context, project.get("code") + " now has its own CBS: " + rows.size()
                + " node(s), " + linked + " parented. It is a copy — later changes to the "
                + "library will not reshape this project.");
    }

    // ---------------------------------------------------------------- helpers

    private String projectOf(Row item) {
        Object boqId = item.get("boq_ID");
        if (boqId == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "This bill line does not belong to a bill.");
        }
        Row boq = db.run(Select.from(E_BOQ).where(b -> b.get("ID").eq(boqId.toString())))
                .first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "The bill this line belongs to no longer exists."));
        String projectId = str(boq.get("project_ID"));
        if (projectId == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The bill is not attached to a project.");
        }
        return projectId;
    }

    /**
     * Both the WBS and the CBS must belong to the same project as the bill.
     * Allocating across projects would post one project's cost against
     * another's structure, and nothing downstream would ever flag it.
     */
    private Row findWbs(String code, String projectId) {
        if (code == null || code.isBlank()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, "Name the WBS element.");
        }
        return db.run(Select.from(E_WBS)
                        .where(w -> w.get("code").eq(code).and(w.get("project_ID").eq(projectId))))
                .first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "This project has no WBS element " + code + "."));
    }

    private Row findCbs(String code, String projectId) {
        if (code == null || code.isBlank()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, "Name the CBS node.");
        }
        return db.run(Select.from(E_CBS_INSTANCE)
                        .where(c -> c.get("code").eq(code).and(c.get("project_ID").eq(projectId))))
                .first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "This project has no CBS node " + code
                                + ". Instantiate the CBS before allocating."));
    }

    private Row targetOf(EventContext context, String missing) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        return (select == null ? Optional.<Row>empty() : db.run(select).first())
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND, missing));
    }

    private static void return_(EventContext context, String message) {
        context.put("result", message);
        context.setCompleted();
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static BigDecimal dec(Object v) {
        if (v == null) { return null; }
        if (v instanceof BigDecimal b) { return b; }
        try { return new BigDecimal(String.valueOf(v)); }
        catch (NumberFormatException e) { return null; }
    }
}
