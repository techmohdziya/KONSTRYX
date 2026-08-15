package com.inflexion.konstryx.nr;

import com.sap.cds.Result;
import com.sap.cds.Row;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.runtime.CdsRuntime;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * Issues document numbers from the configured ranges.
 *
 * Scope and pattern are read from configuration on every call rather than
 * cached: an administrator switching an object from GLOBAL to COMPANY expects
 * the next document to reflect it, and the read is a single indexed lookup.
 */
@Component
public class NumberRangeService {

    private static final String E_OBJECT  = "konstryx.nr.NumberRangeObject";
    private static final String E_COUNTER = "konstryx.nr.NumberRangeCounter";

    private static final int MAX_ATTEMPTS = 5;

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    /**
     * Next number for an object, in the given company and on the given date.
     *
     * @param objectCode  the range object, e.g. "RR"
     * @param companyCode the legal entity; ignored when the object is GLOBAL
     */
    public String next(String objectCode, String companyCode, LocalDate date) {
        Row config = configFor(objectCode);

        String scope = str(config, "scope", "GLOBAL");
        String pattern = str(config, "pattern", "{OBJ}-{YYYY}-{SEQ}");
        String reset = str(config, "resetPolicy", "YEARLY");
        int seqLength = intOf(config, "seqLength", 4);
        int startAt = intOf(config, "startAt", 1);
        String objectId = str(config, "ID", null);

        // The partition key. A GLOBAL object ignores the company entirely, which
        // is what makes one series across the group possible while the pattern
        // may still print a company code.
        String partition = "COMPANY".equals(scope) ? nullSafe(companyCode) : "";
        int year = "YEARLY".equals(reset) ? (date == null ? LocalDate.now() : date).getYear() : 0;

        int sequence = reserve(objectId, partition, year, startAt);

        return render(pattern, objectCode, nullSafe(companyCode),
                (date == null ? LocalDate.now() : date).getYear(), sequence, seqLength);
    }

    public String next(String objectCode, String companyCode) {
        return next(objectCode, companyCode, LocalDate.now());
    }

    // ------------------------------------------------------------ internals

    private Row configFor(String objectCode) {
        Optional<Row> found = db.run(Select.from(E_OBJECT)
                .where(o -> o.get("code").eq(objectCode).and(o.get("isActive").eq(true))))
                .first();
        return found.orElseThrow(() -> new ServiceException(ErrorStatuses.SERVER_ERROR,
                "No active number range configured for object '" + objectCode
                        + "'. An administrator must define one before documents of this type can be created."));
    }

    /**
     * Claims the next sequence value.
     *
     * The read-modify-write is retried rather than locked optimistically in a
     * single statement, because the counter row may not exist yet on the first
     * document of a year and CAP has no upsert-and-return. Two requests racing
     * on the same partition either see different lastNumber values and both
     * succeed, or collide and retry; MAX_ATTEMPTS bounds the collision case.
     */
    private int reserve(String objectId, String partition, int year, int startAt) {
        for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
            Optional<Row> existing = db.run(Select.from(E_COUNTER)
                    .where(c -> c.get("rangeObject_ID").eq(objectId)
                            .and(c.get("companyCode").eq(partition))
                            .and(c.get("fiscalYear").eq(year))))
                    .first();

            if (existing.isEmpty()) {
                Map<String, Object> row = new HashMap<>();
                row.put("ID", UUID.randomUUID().toString());
                row.put("rangeObject_ID", objectId);
                row.put("companyCode", partition);
                row.put("fiscalYear", year);
                row.put("lastNumber", startAt);
                try {
                    db.run(Insert.into(E_COUNTER).entry(row));
                    return startAt;
                } catch (RuntimeException raced) {
                    continue; // another request created it first — re-read and bump
                }
            }

            Row counter = existing.get();
            int current = intOf(counter, "lastNumber", startAt - 1);
            int nextValue = current + 1;

            Result updated = db.run(Update.entity(E_COUNTER)
                    .data("lastNumber", nextValue)
                    .where(c -> c.get("ID").eq(counter.get("ID"))
                            .and(c.get("lastNumber").eq(current))));

            if (updated.rowCount() == 1) {
                return nextValue;
            }
            // lastNumber moved under us: another request took this value. Retry.
        }
        throw new ServiceException(ErrorStatuses.SERVER_ERROR,
                "Could not obtain a document number after " + MAX_ATTEMPTS + " attempts.");
    }

    static String render(String pattern, String objectCode, String companyCode,
                         int year, int sequence, int seqLength) {
        String seq = String.format("%0" + Math.max(1, seqLength) + "d", sequence);
        return pattern
                .replace("{OBJ}", nullSafe(objectCode))
                .replace("{CC}", nullSafe(companyCode))
                .replace("{YYYY}", String.valueOf(year))
                .replace("{YY}", String.format("%02d", year % 100))
                .replace("{SEQ}", seq);
    }

    private static String nullSafe(String s) {
        return s == null ? "" : s;
    }

    private static String str(Row r, String key, String fallback) {
        Object v = r.get(key);
        return v == null ? fallback : v.toString();
    }

    private static int intOf(Row r, String key, int fallback) {
        Object v = r.get(key);
        if (v instanceof Number n) {
            return n.intValue();
        }
        try {
            return v == null ? fallback : Integer.parseInt(v.toString());
        } catch (NumberFormatException e) {
            return fallback;
        }
    }
}
