package com.inflexion.konstryx.prj;

import com.sap.cds.CdsData;
import com.sap.cds.Row;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.cds.CdsCreateEventContext;
import com.sap.cds.services.cds.CdsUpdateEventContext;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.runtime.CdsRuntime;
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
 * The bill of quantities: what was sold, at what price.
 *
 * Everything downstream leans on it. The contract value comes from it, revenue
 * is certified against it, and the allocation of its quantities to WBS and CBS
 * is the join between what was sold and where the cost lands. So the arithmetic
 * has to be the system's, not the spreadsheet's: a bill whose lines do not sum
 * to its header is the single most common cause of a project that cannot be
 * reconciled, and it is always discovered late.
 */
@Component
@ServiceName("ProjectService")
public class BOQHandler implements EventHandler {

    private static final String E_BOQ = "konstryx.prj.BOQ";
    private static final String E_ITEM = "konstryx.prj.BOQItem";

    private static final char DELIMITER = ';';

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    // ------------------------------------------------------------- validation

    @Before(event = { CqnService.EVENT_CREATE, CqnService.EVENT_UPDATE },
            entity = "ProjectService.BOQItems")
    public void validateItem(EventContext context, List<CdsData> items) {
        items.forEach(this::validateItem);
    }

    private void validateItem(CdsData item) {
        String id = str(item.get("ID"));
        Row stored = id == null ? null : db.run(Select.from(E_ITEM)
                .where(i -> i.get("ID").eq(id))).first().orElse(null);

        String boqId = merged(item, stored, "boq_ID");
        String itemNo = merged(item, stored, "itemNo");

        if (isBlank(itemNo)) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A bill line needs an item number — it is how the QS, the client "
                            + "and the certificate all refer to it.");
        }
        if (boqId != null) {
            assertItemNumberIsFree(boqId, itemNo, id);
        }

        BigDecimal qty = dec(merged(item, stored, "qty"));
        BigDecimal rate = dec(merged(item, stored, "rate"));

        if (qty != null && qty.signum() < 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Line " + itemNo + " has a negative quantity.");
        }
        if (rate != null && rate.signum() < 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Line " + itemNo + " has a negative rate.");
        }

        // The amount is derived, never accepted. A spreadsheet whose amount
        // column has been overtyped is exactly how a bill stops adding up, and
        // the discrepancy is invisible until someone totals it by hand.
        if (qty != null && rate != null) {
            item.put("amount", qty.multiply(rate).setScale(2, RoundingMode.HALF_UP));
        }
    }

    private void assertItemNumberIsFree(String boqId, String itemNo, String selfId) {
        for (Row other : db.run(Select.from(E_ITEM)
                .where(i -> i.get("boq_ID").eq(boqId).and(i.get("itemNo").eq(itemNo))))) {
            String otherId = str(other.get("ID"));
            if (otherId != null && !otherId.equals(selfId)) {
                throw new ServiceException(ErrorStatuses.CONFLICT,
                        "Item " + itemNo + " already exists in this bill.");
            }
        }
    }

    // ---------------------------------------------------------------- actions

    @On(event = "recalculate")
    public void onRecalculate(EventContext context) {
        Row boq = targetOf(context, E_BOQ, "Bill of quantities not found.");
        BigDecimal total = recalculate(str(boq.get("ID")));
        result(context, boq.get("boqId") + " totals " + total.toPlainString()
                + " across its priced lines.");
    }

    /** The header value is the sum of the lines. It is never typed in. */
    private BigDecimal recalculate(String boqId) {
        BigDecimal total = BigDecimal.ZERO;
        for (Row item : db.run(Select.from(E_ITEM).where(i -> i.get("boq_ID").eq(boqId)))) {
            BigDecimal amount = dec(item.get("amount"));
            if (amount != null) {
                total = total.add(amount);
            }
        }
        Map<String, Object> update = new HashMap<>();
        update.put("contractValue", total);
        db.run(Update.entity(E_BOQ).data(update).where(b -> b.get("ID").eq(boqId)));
        return total;
    }

    @On(event = "importItems")
    public void onImportItems(EventContext context) {
        Row boq = targetOf(context, E_BOQ, "Bill of quantities not found.");
        String boqId = str(boq.get("ID"));

        Object content = context.get("content");
        if (content == null || String.valueOf(content).isBlank()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, "The file is empty.");
        }
        boolean validateOnly = Boolean.TRUE.equals(context.get("validateOnly"));

        List<String> lines = String.valueOf(content).lines()
                .filter(l -> !l.isBlank())
                .toList();
        if (lines.size() < 2) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The file has a header but no lines.");
        }

        List<String> header = split(lines.get(0));
        int iItemNo = header.indexOf("itemNo");
        int iDesc = header.indexOf("description");
        int iQty = header.indexOf("qty");
        int iUom = header.indexOf("uom");
        int iRate = header.indexOf("rate");
        int iCode = header.indexOf("code");

        if (iItemNo < 0 || iQty < 0 || iRate < 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The file needs at least itemNo, qty and rate columns. Found: "
                            + String.join(", ", header));
        }

        List<String> problems = new ArrayList<>();
        List<Map<String, Object>> rows = new ArrayList<>();
        BigDecimal total = BigDecimal.ZERO;

        for (int i = 1; i < lines.size(); i++) {
            List<String> cells = split(lines.get(i));
            String itemNo = at(cells, iItemNo);
            try {
                if (isBlank(itemNo)) {
                    throw new IllegalArgumentException("no item number");
                }
                BigDecimal qty = new BigDecimal(at(cells, iQty));
                BigDecimal rate = new BigDecimal(at(cells, iRate));
                BigDecimal amount = qty.multiply(rate).setScale(2, RoundingMode.HALF_UP);

                Map<String, Object> row = new LinkedHashMap<>();
                row.put("ID", java.util.UUID.randomUUID().toString());
                row.put("boq_ID", boqId);
                row.put("itemNo", itemNo);
                row.put("code", iCode >= 0 ? at(cells, iCode) : null);
                row.put("description", iDesc >= 0 ? at(cells, iDesc) : null);
                row.put("qty", qty);
                row.put("uom", iUom >= 0 ? at(cells, iUom) : null);
                row.put("rate", rate);
                row.put("amount", amount);
                rows.add(row);
                total = total.add(amount);
            } catch (Exception e) {
                problems.add("line " + i + " (" + (itemNo == null ? "?" : itemNo) + "): "
                        + readable(e));
            }
        }

        // Duplicates within the file itself, which a per-row check cannot see.
        Map<String, Integer> seen = new HashMap<>();
        for (Map<String, Object> row : rows) {
            String itemNo = str(row.get("itemNo"));
            seen.merge(itemNo, 1, Integer::sum);
        }
        seen.forEach((itemNo, count) -> {
            if (count > 1) {
                problems.add("item " + itemNo + " appears " + count + " times in the file");
            }
        });

        if (!problems.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Nothing was imported. " + problems.size() + " problem(s): "
                            + String.join("; ", problems.subList(0, Math.min(5, problems.size())))
                            + (problems.size() > 5 ? " …" : ""));
        }

        if (validateOnly) {
            result(context, rows.size() + " line(s) totalling " + total.toPlainString()
                    + " would import cleanly. Nothing was changed — this was a check.");
            return;
        }

        // Replacing rather than appending: a re-issued bill is a new bill, and
        // merging two revisions line by line produces a total nobody agreed to.
        db.run(com.sap.cds.ql.Delete.from(E_ITEM).where(i -> i.get("boq_ID").eq(boqId)));
        db.run(Insert.into(E_ITEM).entries(rows));
        BigDecimal stored = recalculate(boqId);

        result(context, "Imported " + rows.size() + " line(s). " + boq.get("boqId")
                + " now totals " + stored.toPlainString()
                + ". Any previous lines on this bill were replaced.");
    }

    // ---------------------------------------------------------------- helpers

    private Row targetOf(EventContext context, String entity, String missing) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        return (select == null ? Optional.<Row>empty() : db.run(select).first())
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND, missing));
    }

    private static void result(EventContext context, String message) {
        context.put("result", message);
        context.setCompleted();
    }

    private String merged(CdsData entry, Row stored, String field) {
        Object value = entry.get(field);
        if (value != null) {
            return String.valueOf(value);
        }
        if (entry.containsKey(field)) {
            return null;
        }
        return stored == null ? null : str(stored.get(field));
    }

    private static List<String> split(String line) {
        List<String> out = new ArrayList<>();
        StringBuilder field = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') {
                if (quoted && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    field.append('"');
                    i++;
                } else {
                    quoted = !quoted;
                }
            } else if (c == DELIMITER && !quoted) {
                out.add(field.toString().trim());
                field.setLength(0);
            } else {
                field.append(c);
            }
        }
        out.add(field.toString().trim());
        return out;
    }

    private static String at(List<String> cells, int index) {
        if (index < 0 || index >= cells.size()) {
            return null;
        }
        String v = cells.get(index);
        return v == null || v.isBlank() ? null : v.trim();
    }

    private static String readable(Exception e) {
        if (e instanceof NumberFormatException) {
            return "quantity or rate is not a number";
        }
        return e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
    }

    private static boolean isBlank(String s) { return s == null || s.isBlank(); }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static BigDecimal dec(Object v) {
        if (v == null) { return null; }
        if (v instanceof BigDecimal b) { return b; }
        try { return new BigDecimal(String.valueOf(v)); }
        catch (NumberFormatException e) { return null; }
    }
}
