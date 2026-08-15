package com.inflexion.konstryx.master;

import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.request.UserInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Answers "which rate applies to this resource on this day".
 *
 * Effective dating is only worth having if something resolves it. A resource
 * accumulates rate revisions over years, and every consumer — a budget, a
 * reservation, a variation, a payment certificate — needs the rate in force on
 * its own date, not the newest row in the table. Left to each module, that
 * becomes several different readings of the word "current", and two screens
 * costing the same work differently is the kind of defect nobody can explain
 * to a client.
 *
 * Two rules decide the answer:
 *
 *   1. The latest rate whose effectiveFrom is on or before the date. A rate
 *      dated in the future is a decision already taken, not one in force.
 *   2. A company rate beats a group rate. A local negotiated rate exists
 *      precisely because the group rate does not apply to that company.
 */
@Component
@ServiceName("MasterDataService")
public class RateResolutionHandler implements EventHandler {

    private static final String E_RATE = "konstryx.master.RateMaster";
    private static final String E_RESOURCE = "konstryx.master.ResourceNode";
    private static final String E_COMPANY = "konstryx.admin.Company";

    @Autowired
    private PersistenceService db;

    @Autowired
    private UserInfo userInfo;

    @On(event = "rateOn")
    public void onRateOn(EventContext context) {
        String code = str(context.get("resourceCode"));
        if (code == null || code.isBlank()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, "Name the resource.");
        }
        LocalDate on = date(context.get("onDate"));
        if (on == null) {
            // "Today" is the overwhelmingly common case and asking for it
            // explicitly every time is friction with no benefit.
            on = LocalDate.now();
        }

        Row resource = findResource(code);
        String resourceId = str(resource.get("ID"));
        String companyId = companyIdFor(str(context.get("companyCode")));

        List<Row> candidates = new ArrayList<>();
        for (Row rate : db.run(Select.from(E_RATE)
                .where(r -> r.get("resource_ID").eq(resourceId)))) {
            LocalDate from = date(rate.get("effectiveFrom"));
            if (from == null || from.isAfter(on)) {
                continue;   // not yet in force on the date asked about
            }
            String owner = str(rate.get("owningCompany_ID"));
            boolean isGroup = owner == null;
            boolean isMine = companyId != null && companyId.equalsIgnoreCase(owner);
            if (isGroup || isMine) {
                candidates.add(rate);
            }
        }

        if (candidates.isEmpty()) {
            throw new ServiceException(ErrorStatuses.NOT_FOUND,
                    "No rate for " + code + " is in force on " + on
                            + (companyId == null ? "." : " for that company."));
        }

        Row winner = pick(candidates, companyId);

        Map<String, Object> result = new HashMap<>();
        result.put("resourceCode", code);
        result.put("rateValue", winner.get("rateValue"));
        result.put("netRate", winner.get("netRate") != null
                ? winner.get("netRate") : winner.get("rateValue"));
        result.put("basis", winner.get("basis"));
        result.put("currency", winner.get("ccy_code"));
        result.put("effectiveFrom", winner.get("effectiveFrom"));
        result.put("scope", winner.get("owningCompany_ID") == null ? "GROUP" : "COMPANY");
        result.put("source", describe(winner, on));

        context.put("result", result);
        context.setCompleted();
    }

    /**
     * Company beats group; within the same scope, the latest start date wins.
     * Ties cannot happen — the validation refuses two rates for one resource in
     * one scope on one date, which is exactly why that rule exists.
     */
    private Row pick(List<Row> candidates, String companyId) {
        Row best = null;
        for (Row candidate : candidates) {
            if (best == null || beats(candidate, best, companyId)) {
                best = candidate;
            }
        }
        return best;
    }

    private boolean beats(Row a, Row b, String companyId) {
        boolean aCompany = companyId != null && companyId.equalsIgnoreCase(str(a.get("owningCompany_ID")));
        boolean bCompany = companyId != null && companyId.equalsIgnoreCase(str(b.get("owningCompany_ID")));
        if (aCompany != bCompany) {
            return aCompany;
        }
        LocalDate aFrom = date(a.get("effectiveFrom"));
        LocalDate bFrom = date(b.get("effectiveFrom"));
        if (aFrom == null || bFrom == null) {
            return false;
        }
        return aFrom.isAfter(bFrom);
    }

    private String describe(Row rate, LocalDate on) {
        String scope = rate.get("owningCompany_ID") == null ? "group rate" : "company rate";
        return scope + " effective " + rate.get("effectiveFrom") + ", read for " + on;
    }

    private Row findResource(String code) {
        return db.run(Select.from(E_RESOURCE).where(r -> r.get("code").eq(code)))
                .first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "There is no resource with code " + code + "."));
    }

    private String companyIdFor(String companyCode) {
        if (companyCode == null || companyCode.isBlank()) {
            return null;
        }
        Optional<Row> company = db.run(Select.from(E_COMPANY)
                .where(c -> c.get("code").eq(companyCode))).first();
        if (company.isEmpty()) {
            throw new ServiceException(ErrorStatuses.NOT_FOUND,
                    "There is no company with code " + companyCode + ".");
        }
        return str(company.get().get("ID"));
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static LocalDate date(Object v) {
        if (v == null) { return null; }
        if (v instanceof LocalDate d) { return d; }
        try { return LocalDate.parse(String.valueOf(v).substring(0, 10)); }
        catch (RuntimeException e) { return null; }
    }
}
