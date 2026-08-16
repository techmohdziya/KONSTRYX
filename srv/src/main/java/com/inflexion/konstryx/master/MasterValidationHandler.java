package com.inflexion.konstryx.master;

import com.sap.cds.CdsData;
import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.cds.CdsCreateEventContext;
import com.sap.cds.services.cds.CdsUpdateEventContext;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Optional;

/**
 * Integrity rules for stewarded master data.
 *
 * These run on activation rather than on draft edit: a steward part-way through
 * building a hierarchy will legitimately have an incomplete record, and
 * refusing their keystrokes is not the same as refusing bad data.
 */
@Component
@ServiceName("MasterDataService")
public class MasterValidationHandler implements EventHandler {

    private static final String E_RESOURCE = "konstryx.master.ResourceNode";
    private static final String E_CBS = "konstryx.master.CBSNode";
    private static final String E_RATE = "konstryx.master.RateMaster";
    private static final String E_PRODUCTIVITY = "konstryx.master.ProductivityRate";
    private static final String E_CONSUMPTION = "konstryx.master.ConsumptionRate";

    private static final List<String> RESOURCE_LEVELS = List.of("L1", "L2", "L3", "L4", "L5");
    private static final List<String> CBS_LEVELS = List.of("L1", "L2", "L3");

    @Autowired
    private PersistenceService db;

    // ------------------------------------------------------------- resources

    @Before(event = CqnService.EVENT_CREATE, entity = "MasterDataService.Resources")
    public void validateResourceCreate(CdsCreateEventContext context, List<CdsData> entries) {
        entries.forEach(e -> validateNode(e, E_RESOURCE, RESOURCE_LEVELS));
    }

    @Before(event = CqnService.EVENT_UPDATE, entity = "MasterDataService.Resources")
    public void validateResourceUpdate(CdsUpdateEventContext context, List<CdsData> entries) {
        entries.forEach(e -> validateNode(e, E_RESOURCE, RESOURCE_LEVELS));
    }

    @Before(event = CqnService.EVENT_CREATE, entity = "MasterDataService.CBSLibrary")
    public void validateCbsCreate(CdsCreateEventContext context, List<CdsData> entries) {
        entries.forEach(e -> validateNode(e, E_CBS, CBS_LEVELS));
    }

    @Before(event = CqnService.EVENT_UPDATE, entity = "MasterDataService.CBSLibrary")
    public void validateCbsUpdate(CdsUpdateEventContext context, List<CdsData> entries) {
        entries.forEach(e -> validateNode(e, E_CBS, CBS_LEVELS));
    }

    private void validateNode(CdsData entry, String entity, List<String> levels) {
        String id = str(entry.get("ID"));
        Row stored = id == null ? null : db.run(Select.from(entity)
                .where(e -> e.get("ID").eq(id))).first().orElse(null);

        String code = merged(entry, stored, "code");
        String level = merged(entry, stored, "level");
        String parentId = merged(entry, stored, "parent_ID");
        String scope = Optional.ofNullable(merged(entry, stored, "scope")).orElse("COMPANY");
        String owner = merged(entry, stored, "owningCompany_ID");

        if (code == null || code.isBlank()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, "A master needs a code.");
        }

        // ---- level and parent must agree ---------------------------------
        if (level != null && !levels.contains(level)) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Level " + level + " is not valid here — expected one of " + levels + ".");
        }

        if (level != null) {
            int depth = levels.indexOf(level);
            if (depth == 0 && parentId != null) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        levels.get(0) + " is the top of the hierarchy and cannot have a parent.");
            }
            if (depth > 0) {
                if (parentId == null) {
                    throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                            level + " needs a parent at " + levels.get(depth - 1) + ".");
                }
                Row parent = db.run(Select.from(entity)
                        .where(e -> e.get("ID").eq(parentId))).first().orElse(null);
                if (parent == null) {
                    throw new ServiceException(ErrorStatuses.BAD_REQUEST, "The parent does not exist.");
                }
                String parentLevel = str(parent.get("level"));
                String expected = levels.get(depth - 1);
                if (!expected.equals(parentLevel)) {
                    throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                            "A " + level + " must hang off a " + expected
                                    + ", but its parent is " + parentLevel + ".");
                }
            }
        }

        assertCodeIsUnambiguous(entity, code, scope, owner, id);
    }

    /**
     * A code has to resolve to one record for everyone who can see it.
     *
     * Two companies may each hold a local EQ-001 — that is the point of
     * company scope, and no user sees both unless they work group-wide. But a
     * group EQ-001 alongside a local EQ-001 is ambiguous for every user in that
     * company, so the pair is refused.
     */
    private void assertCodeIsUnambiguous(String entity, String code, String scope,
                                         String owner, String selfId) {
        for (Row other : db.run(Select.from(entity).where(e -> e.get("code").eq(code)))) {
            String otherId = str(other.get("ID"));
            if (otherId != null && otherId.equals(selfId)) {
                continue;
            }
            String otherScope = Optional.ofNullable(str(other.get("scope"))).orElse("COMPANY");
            String otherOwner = str(other.get("owningCompany_ID"));

            boolean sameScopeKey = "GROUP".equals(scope) && "GROUP".equals(otherScope)
                    || (owner != null && owner.equals(otherOwner));
            boolean groupVersusCompany = "GROUP".equals(scope) ^ "GROUP".equals(otherScope);

            if (sameScopeKey) {
                throw new ServiceException(ErrorStatuses.CONFLICT,
                        "Code " + code + " already exists in this scope.");
            }
            if (groupVersusCompany) {
                throw new ServiceException(ErrorStatuses.CONFLICT,
                        "Code " + code + " already exists at "
                                + ("GROUP".equals(otherScope) ? "group" : "company")
                                + " scope. One code cannot mean two things for the same user.");
            }
        }
    }

    // ----------------------------------------------------------------- rates

    @Before(event = CqnService.EVENT_CREATE, entity = "MasterDataService.Rates")
    public void validateRateCreate(CdsCreateEventContext context, List<CdsData> entries) {
        entries.forEach(this::validateRate);
    }

    @Before(event = CqnService.EVENT_UPDATE, entity = "MasterDataService.Rates")
    public void validateRateUpdate(CdsUpdateEventContext context, List<CdsData> entries) {
        entries.forEach(this::validateRate);
    }

    /**
     * Two rates for the same resource, in the same scope, effective the same
     * day give the costing engine no way to choose. Later start dates are
     * fine — that is how a rate revision is expressed.
     */
    private void validateRate(CdsData entry) {
        String id = str(entry.get("ID"));
        Row stored = id == null ? null : db.run(Select.from(E_RATE)
                .where(e -> e.get("ID").eq(id))).first().orElse(null);

        String resource = merged(entry, stored, "resource_ID");
        String from = merged(entry, stored, "effectiveFrom");
        String owner = merged(entry, stored, "owningCompany_ID");

        if (resource == null || from == null) {
            return;   // incomplete rows are caught by the model, not here
        }

        for (Row other : db.run(Select.from(E_RATE)
                .where(e -> e.get("resource_ID").eq(resource)
                        .and(e.get("effectiveFrom").eq(from))))) {
            String otherId = str(other.get("ID"));
            if (otherId != null && otherId.equals(id)) {
                continue;
            }
            String otherOwner = str(other.get("owningCompany_ID"));
            boolean sameScope = owner == null ? otherOwner == null : owner.equals(otherOwner);
            if (sameScope) {
                throw new ServiceException(ErrorStatuses.CONFLICT,
                        "A rate for this resource already takes effect on " + from
                                + " in the same scope.");
            }
        }
    }

    // ----------------------------------------------------------------- norms

    /**
     * Productivity and consumption norms had no validation at all, which made
     * them the weakest link in costing: a budget built on a norm of zero, or on
     * two norms effective the same day, is wrong in a way nobody notices until
     * the numbers are challenged. They are effective-dated exactly like rates,
     * so they are checked exactly like rates.
     */
    @Before(event = CqnService.EVENT_CREATE, entity = "MasterDataService.ProductivityRates")
    public void validateProductivityCreate(CdsCreateEventContext context, List<CdsData> entries) {
        entries.forEach(e -> {
            deriveManday(e);
            validateNorm(e, E_PRODUCTIVITY, "resource_ID", "productivity norm");
        });
    }

    @Before(event = CqnService.EVENT_UPDATE, entity = "MasterDataService.ProductivityRates")
    public void validateProductivityUpdate(CdsUpdateEventContext context, List<CdsData> entries) {
        entries.forEach(e -> {
            deriveManday(e);
            validateNorm(e, E_PRODUCTIVITY, "resource_ID", "productivity norm");
        });
    }

    /** The 8-hour man-day figure is derived from the hourly norm when absent. */
    private void deriveManday(CdsData entry) {
        Object perHour = entry.get("outputPerHr");
        if (perHour == null || entry.get("outputPerManday8h") != null) {
            return;
        }
        try {
            entry.put("outputPerManday8h", new java.math.BigDecimal(perHour.toString())
                    .multiply(new java.math.BigDecimal("8"))
                    .setScale(3, java.math.RoundingMode.HALF_UP));
        } catch (NumberFormatException ignored) { }
    }

    @Before(event = CqnService.EVENT_CREATE, entity = "MasterDataService.ConsumptionRates")
    public void validateConsumptionCreate(CdsCreateEventContext context, List<CdsData> entries) {
        entries.forEach(e -> {
            deriveNetRate(e, E_CONSUMPTION);
            validateNorm(e, E_CONSUMPTION, "material_ID", "consumption norm");
        });
    }

    @Before(event = CqnService.EVENT_UPDATE, entity = "MasterDataService.ConsumptionRates")
    public void validateConsumptionUpdate(CdsUpdateEventContext context, List<CdsData> entries) {
        entries.forEach(e -> {
            deriveNetRate(e, E_CONSUMPTION);
            validateNorm(e, E_CONSUMPTION, "material_ID", "consumption norm");
        });
    }

    /**
     * netRate is derived, never keyed (CALC-01): theoretical x (1 + wastage/100),
     * four decimals, half-up. Whatever the caller sent in that field is
     * discarded before it can be believed — an importer asserting netRate 9.999
     * against a 2.5% wastage persists 1.0250 (UT-03).
     */
    private void deriveNetRate(CdsData entry, String entity) {
        String id = str(entry.get("ID"));
        Row stored = id == null ? null : db.run(Select.from(entity)
                .where(e -> e.get("ID").eq(id))).first().orElse(null);
        String cons = merged(entry, stored, "consRate");
        String wastage = merged(entry, stored, "wastageAllowancePct");
        if (cons == null) {
            entry.remove("netRate");
            return;
        }
        try {
            java.math.BigDecimal theoretical = new java.math.BigDecimal(cons);
            java.math.BigDecimal pct = wastage == null
                    ? java.math.BigDecimal.ZERO : new java.math.BigDecimal(wastage);
            entry.put("netRate", theoretical.multiply(
                    java.math.BigDecimal.ONE.add(pct.divide(new java.math.BigDecimal("100"),
                            8, java.math.RoundingMode.HALF_UP)))
                    .setScale(4, java.math.RoundingMode.HALF_UP));
        } catch (NumberFormatException e) {
            // the validation below produces the readable refusal
        }
    }

    private void validateNorm(CdsData entry, String entity, String subjectField, String what) {
        String id = str(entry.get("ID"));
        Row stored = id == null ? null : db.run(Select.from(entity)
                .where(e -> e.get("ID").eq(id))).first().orElse(null);

        String subject = merged(entry, stored, subjectField);
        String from = merged(entry, stored, "effectiveFrom");

        if (subject == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A " + what + " has to say which resource it is for.");
        }
        if (from == null) {
            // Without a date nothing can resolve which norm applies when, and
            // effective dating is the only reason these are separate rows.
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A " + what + " needs an effective-from date.");
        }

        assertPositive(entry, stored, "outputPerHr", "Output per hour");
        assertPositive(entry, stored, "outputPerManday8h", "Output per man-day");
        assertPositive(entry, stored, "consRate", "Consumption rate");

        String wastage = merged(entry, stored, "wastageAllowancePct");
        if (wastage != null) {
            try {
                java.math.BigDecimal pct = new java.math.BigDecimal(wastage);
                if (pct.signum() < 0 || pct.compareTo(new java.math.BigDecimal("100")) > 0) {
                    throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                            "A wastage allowance of " + wastage
                                    + "% is not a proportion of anything. Use 0 to 100.");
                }
            } catch (NumberFormatException e) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "The wastage allowance must be a number.");
            }
        }

        String owner = merged(entry, stored, "owningCompany_ID");
        // The norm's key is subject x linked CBS x activity x company
        // (wireframe m-prodrates / m-consrates). Only a row matching on ALL of
        // those and the same start date is a duplicate; the same material with
        // a different linked CBS is a different recipe line, not a clash.
        String cbs = merged(entry, stored, "linkedCBS_ID");
        String activity = merged(entry, stored, "activity");
        for (Row other : db.run(Select.from(entity)
                .where(e -> e.get(subjectField).eq(subject).and(e.get("effectiveFrom").eq(from))))) {
            String otherId = str(other.get("ID"));
            if (otherId != null && otherId.equals(id)) {
                continue;
            }
            String otherOwner = str(other.get("owningCompany_ID"));
            boolean sameScope = owner == null ? otherOwner == null : owner.equals(otherOwner);
            boolean sameCbs = cbs == null ? other.get("linkedCBS_ID") == null
                    : cbs.equals(str(other.get("linkedCBS_ID")));
            boolean sameActivity = activity == null ? other.get("activity") == null
                    : activity.equals(str(other.get("activity")));
            if (sameScope && sameCbs && sameActivity) {
                throw new ServiceException(ErrorStatuses.CONFLICT,
                        "A " + what + " with this key already takes effect on " + from
                                + " in the same scope.");
            }
        }
    }

    /** A norm of zero silently prices work at nothing, or divides by it. */
    private void assertPositive(CdsData entry, Row stored, String field, String label) {
        String value = merged(entry, stored, field);
        if (value == null) {
            return;
        }
        try {
            if (new java.math.BigDecimal(value).signum() <= 0) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        label + " must be greater than zero.");
            }
        } catch (NumberFormatException e) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, label + " must be a number.");
        }
    }

    // ---------------------------------------------------------------- helpers

    private String merged(CdsData entry, Row stored, String field) {
        Object value = entry.get(field);
        if (value != null) {
            return String.valueOf(value);
        }
        if (entry.containsKey(field)) {
            return null;    // explicitly cleared by the caller
        }
        return stored == null ? null : str(stored.get(field));
    }

    private static String str(Object value) {
        return value == null ? null : String.valueOf(value);
    }
}
