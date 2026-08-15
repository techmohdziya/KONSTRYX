package com.inflexion.konstryx.apr;

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

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * Runs approvals.
 *
 * The scheme is configuration, not code: an administrator defines the steps,
 * who approves each one, and the value bands they apply within. The engine
 * picks the steps that match the amount at the moment of submission and freezes
 * them onto the instance, so a scheme edited next month does not silently
 * rewrite what an in-flight approval requires.
 *
 * Steps sharing a step number are parallel and must all clear before the next
 * number begins. One rejection ends the whole approval — an object half
 * approved and half rejected has no meaning.
 */
@Component
public class ApprovalEngine {

    private static final String E_SCHEME = "konstryx.apr.ApprovalScheme";
    private static final String E_STEP_DEF = "konstryx.apr.ApprovalStepDef";
    private static final String E_INSTANCE = "konstryx.apr.ApprovalInstance";
    private static final String E_STEP = "konstryx.apr.ApprovalStepInstance";
    private static final String E_ASSIGNMENT = "konstryx.auth.UserAssignment";
    private static final String E_AUTH_OBJECT = "konstryx.auth.AuthObject";
    private static final String E_ATTACHMENT = "konstryx.sys.Attachment";
    private static final String E_ATTACH_CATEGORY = "konstryx.sys.AttachmentCategory";

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    // -------------------------------------------------------------- submission

    /**
     * Starts an approval for a business object.
     *
     * @param entityName  the object under approval, e.g. konstryx.bud.Budget
     * @param objectID    its key
     * @param docNo       denormalised so a worklist needs no join
     * @param amount      matched against the steps' value bands
     */
    public Map<String, Object> submit(String entityName, String objectID, String docNo,
                                      BigDecimal amount, String companyId, String user) {

        assertObjectExists(entityName, objectID);

        Optional<Row> existing = db.run(Select.from(E_INSTANCE)
                .where(i -> i.get("objectID").eq(objectID).and(i.get("status").eq("PENDING"))))
                .first();
        if (existing.isPresent()) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    docNo + " is already awaiting approval.");
        }

        assertMandatoryAttachmentsPresent(entityName, objectID, docNo);

        Row scheme = findScheme(entityName, companyId);
        List<Row> steps = matchingSteps(String.valueOf(scheme.get("ID")), amount);

        if (steps.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Scheme " + scheme.get("code") + " has no step covering "
                            + (amount == null ? "an unspecified amount" : amount.toPlainString())
                            + ". Nobody would be asked to approve this.");
        }

        String instanceId = UUID.randomUUID().toString();
        Map<String, Object> instance = new HashMap<>();
        instance.put("ID", instanceId);
        instance.put("scheme_ID", scheme.get("ID"));
        instance.put("entityName", entityName);
        instance.put("objectID", objectID);
        instance.put("objectDocNo", docNo);
        instance.put("amount", amount);
        instance.put("status", "PENDING");
        instance.put("startedAt", Instant.now());
        db.run(Insert.into(E_INSTANCE).entry(instance));

        List<Map<String, Object>> stepRows = new ArrayList<>();
        for (Row def : steps) {
            Map<String, Object> step = new HashMap<>();
            step.put("ID", UUID.randomUUID().toString());
            step.put("instance_ID", instanceId);
            step.put("stepDef_ID", def.get("ID"));
            step.put("stepNo", def.get("stepNo"));
            step.put("name", def.get("name"));
            step.put("decision", "PENDING");
            stepRows.add(step);
        }
        db.run(Insert.into(E_STEP).entries(stepRows));

        Map<String, Object> result = new HashMap<>();
        result.put("instanceId", instanceId);
        result.put("steps", stepRows.size());
        result.put("message", docNo + " submitted for approval: "
                + stepRows.size() + " step(s) under " + scheme.get("code") + ".");
        return result;
    }

    /**
     * The target is polymorphic — a string and a key, not a typed association —
     * so nothing in the model stops an approval being raised against an object
     * that does not exist. That approval would sit in an inbox forever, pointing
     * at nothing, and no foreign key would ever complain.
     */
    private void assertObjectExists(String entityName, String objectID) {
        if (runtime.getCdsModel().findEntity(entityName).isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    entityName + " is not an entity in this model.");
        }
        boolean exists = db.run(Select.from(entityName).where(e -> e.get("ID").eq(objectID)))
                .first().isPresent();
        if (!exists) {
            throw new ServiceException(ErrorStatuses.NOT_FOUND,
                    "There is no " + entityName + " with key " + objectID + " to approve.");
        }
    }

    /**
     * An administrator can mark an attachment category mandatory for an object
     * type — a permit before a mobilization authorization, a signed drawing
     * before a variation. Submission is the point where that has to bite: an
     * approver asked to sign for something with no supporting document either
     * refuses and the cycle repeats, or signs blind.
     */
    private void assertMandatoryAttachmentsPresent(String entityName, String objectID, String docNo) {
        List<String> missing = new ArrayList<>();

        for (Row category : db.run(Select.from(E_ATTACH_CATEGORY)
                .where(c -> c.get("isMandatory").eq(true).and(c.get("isActive").eq(true))))) {

            Object authObjectId = category.get("authObject_ID");
            if (authObjectId == null) {
                continue;   // applies to any object type, so it cannot be required of a specific one
            }
            Optional<Row> authObject = db.run(Select.from(E_AUTH_OBJECT)
                    .where(a -> a.get("ID").eq(authObjectId.toString()))).first();
            if (authObject.isEmpty() || !entityName.equals(str(authObject.get().get("entityName")))) {
                continue;
            }

            String categoryId = str(category.get("ID"));
            boolean present = db.run(Select.from(E_ATTACHMENT)
                            .where(a -> a.get("entityName").eq(entityName)
                                    .and(a.get("objectID").eq(objectID))
                                    .and(a.get("category_ID").eq(categoryId))))
                    .first().isPresent();
            if (!present) {
                missing.add(String.valueOf(category.get("name")));
            }
        }

        if (!missing.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    docNo + " cannot be submitted without " + String.join(" and ", missing)
                            + " attached.");
        }
    }

    /**
     * The scheme for this object type. A company-specific scheme wins over a
     * group-wide one, so a legal entity can impose stricter approval without
     * everyone else inheriting it.
     */
    private Row findScheme(String entityName, String companyId) {
        List<Row> candidates = new ArrayList<>();
        for (Row scheme : db.run(Select.from(E_SCHEME).where(s -> s.get("isActive").eq(true)))) {
            Object authObjectId = scheme.get("authObject_ID");
            if (authObjectId == null) {
                continue;
            }
            Optional<Row> authObject = db.run(Select.from(E_AUTH_OBJECT)
                    .where(a -> a.get("ID").eq(authObjectId.toString()))).first();
            if (authObject.isPresent() && entityName.equals(String.valueOf(authObject.get().get("entityName")))) {
                candidates.add(scheme);
            }
        }
        if (candidates.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "No approval scheme is configured for " + entityName
                            + ". An administrator must define one before this can be submitted.");
        }
        return candidates.stream()
                .filter(s -> companyId != null && companyId.equals(str(s.get("company_ID"))))
                .findFirst()
                .orElse(candidates.get(0));
    }

    /** Steps whose value band brackets the amount; an open bound always matches. */
    private List<Row> matchingSteps(String schemeId, BigDecimal amount) {
        List<Row> steps = new ArrayList<>();
        for (Row def : db.run(Select.from(E_STEP_DEF).where(d -> d.get("scheme_ID").eq(schemeId)))) {
            BigDecimal min = dec(def.get("minAmount"));
            BigDecimal max = dec(def.get("maxAmount"));
            boolean matches = true;
            if (amount != null) {
                if (min != null && amount.compareTo(min) < 0) {
                    matches = false;
                }
                if (max != null && amount.compareTo(max) >= 0) {
                    matches = false;
                }
            }
            if (matches) {
                steps.add(def);
            }
        }
        steps.sort(Comparator.comparingInt(d -> intOf(d.get("stepNo"))));
        return steps;
    }

    // ---------------------------------------------------------------- decisions

    public String decide(String stepId, String decision, String comment, String user) {
        Row step = db.run(Select.from(E_STEP).where(s -> s.get("ID").eq(stepId))).first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND, "Step not found."));

        if (!"PENDING".equals(String.valueOf(step.get("decision")))) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "This step was already decided by " + step.get("actedBy") + ".");
        }

        String instanceId = str(step.get("instance_ID"));
        Row instance = db.run(Select.from(E_INSTANCE).where(i -> i.get("ID").eq(instanceId))).first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND, "Approval not found."));

        if (!"PENDING".equals(String.valueOf(instance.get("status")))) {
            throw new ServiceException(ErrorStatuses.CONFLICT, "This approval is already closed.");
        }

        assertIsCurrentStep(instanceId, intOf(step.get("stepNo")));
        assertMayAct(step, user);
        assertNoSelfChaining(step, instanceId, user);

        Map<String, Object> update = new HashMap<>();
        update.put("decision", decision);
        update.put("actedBy", user);
        update.put("decidedAt", Instant.now());
        update.put("comment", comment);
        db.run(Update.entity(E_STEP).data(update).where(s -> s.get("ID").eq(stepId)));

        if ("REJECTED".equals(decision)) {
            closeInstance(instanceId, "REJECTED");
            return instance.get("objectDocNo") + " rejected at step " + step.get("stepNo") + ".";
        }

        if (remainingSteps(instanceId) == 0) {
            closeInstance(instanceId, "APPROVED");
            return instance.get("objectDocNo") + " fully approved.";
        }

        int next = nextPendingStepNo(instanceId);
        return "Step " + step.get("stepNo") + " approved. Now awaiting step " + next + ".";
    }

    /** Steps are ordered: a later approver cannot pre-empt an earlier one. */
    private void assertIsCurrentStep(String instanceId, int stepNo) {
        int current = nextPendingStepNo(instanceId);
        if (stepNo != current) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "Step " + current + " has not been decided yet.");
        }
    }

    /**
     * Only someone holding the step's approver persona may act. Without this,
     * an approval chain is decoration - anyone who can reach the inbox could
     * clear a step meant for a director.
     */
    private void assertMayAct(Row step, String user) {
        if (user.equals(step.get("delegatedTo"))) {
            return;   // the step was handed to this person on purpose
        }
        Object stepDefId = step.get("stepDef_ID");
        if (stepDefId == null) {
            return;
        }
        Optional<Row> def = db.run(Select.from(E_STEP_DEF)
                .where(d -> d.get("ID").eq(stepDefId.toString()))).first();
        if (def.isEmpty() || def.get().get("approver_ID") == null) {
            return;   // no persona configured: the step is open to any authorised user
        }
        String personaId = str(def.get().get("approver_ID"));
        LocalDate today = LocalDate.now();

        boolean holds = false;
        for (Row assignment : db.run(Select.from(E_ASSIGNMENT)
                .where(a -> a.get("user").eq(user).and(a.get("persona_ID").eq(personaId))))) {
            if (!Boolean.TRUE.equals(assignment.get("isActive"))) {
                continue;
            }
            LocalDate from = date(assignment.get("validFrom"));
            LocalDate to = date(assignment.get("validTo"));
            if ((from == null || !today.isBefore(from)) && (to == null || !today.isAfter(to))) {
                holds = true;
                break;
            }
        }
        if (!holds) {
            throw new ServiceException(ErrorStatuses.FORBIDDEN,
                    "This step is for a different approver. You do not hold the persona it requires.");
        }
    }

    /**
     * Separation of duties. A person who holds two personas would otherwise
     * clear both the review and the approval of the same document, and a
     * two-step scheme would mean nothing. allowChaining on the step definition
     * is the deliberate exception — a small company where one director genuinely
     * is both signatures.
     */
    private void assertNoSelfChaining(Row step, String instanceId, String user) {
        Object stepDefId = step.get("stepDef_ID");
        if (stepDefId != null) {
            Optional<Row> def = db.run(Select.from(E_STEP_DEF)
                    .where(d -> d.get("ID").eq(stepDefId.toString()))).first();
            if (def.isPresent() && Boolean.TRUE.equals(def.get().get("allowChaining"))) {
                return;
            }
        }
        for (Row other : db.run(Select.from(E_STEP).where(x -> x.get("instance_ID").eq(instanceId)))) {
            if (!"PENDING".equals(String.valueOf(other.get("decision")))
                    && user.equals(other.get("actedBy"))) {
                throw new ServiceException(ErrorStatuses.FORBIDDEN,
                        "You already decided step " + other.get("stepNo")
                                + " on this document. A second approval by the same person"
                                + " would make the step meaningless.");
            }
        }
    }

    // -------------------------------------------------------------- delegation

    /**
     * Hands a step to a named person without changing the scheme. Delegation is
     * recorded on the step rather than swapping the approver, so the audit trail
     * still shows who was originally asked.
     */
    public String delegate(String stepId, String to, String comment, String user) {
        Row step = db.run(Select.from(E_STEP).where(s -> s.get("ID").eq(stepId))).first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND, "Step not found."));

        if (!"PENDING".equals(String.valueOf(step.get("decision")))) {
            throw new ServiceException(ErrorStatuses.CONFLICT, "This step was already decided.");
        }
        if (to == null || to.isBlank()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, "Name the person to delegate to.");
        }
        if (to.equals(user)) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, "You cannot delegate to yourself.");
        }
        assertMayAct(step, user);

        Map<String, Object> update = new HashMap<>();
        update.put("delegatedTo", to);
        update.put("comment", comment);
        db.run(Update.entity(E_STEP).data(update).where(s -> s.get("ID").eq(stepId)));

        return "Step " + step.get("stepNo") + " delegated to " + to + ".";
    }

    /** Pulls a document back out of approval; the submitter's own escape. */
    public String withdraw(String instanceId, String reason, String user) {
        Row instance = db.run(Select.from(E_INSTANCE).where(i -> i.get("ID").eq(instanceId))).first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND, "Approval not found."));

        if (!"PENDING".equals(String.valueOf(instance.get("status")))) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "This approval is already " + String.valueOf(instance.get("status")).toLowerCase() + ".");
        }

        Map<String, Object> update = new HashMap<>();
        update.put("status", "WITHDRAWN");
        update.put("completedAt", Instant.now());
        db.run(Update.entity(E_INSTANCE).data(update).where(i -> i.get("ID").eq(instanceId)));
        reflectOutcome(instanceId, "WITHDRAWN");

        Map<String, Object> skip = new HashMap<>();
        skip.put("decision", "SKIPPED");
        skip.put("comment", reason);
        db.run(Update.entity(E_STEP).data(skip)
                .where(s -> s.get("instance_ID").eq(instanceId).and(s.get("decision").eq("PENDING"))));

        return instance.get("objectDocNo") + " withdrawn from approval.";
    }

    private int remainingSteps(String instanceId) {
        int pending = 0;
        for (Row s : db.run(Select.from(E_STEP).where(x -> x.get("instance_ID").eq(instanceId)))) {
            if ("PENDING".equals(String.valueOf(s.get("decision")))) {
                pending++;
            }
        }
        return pending;
    }

    private int nextPendingStepNo(String instanceId) {
        int lowest = Integer.MAX_VALUE;
        for (Row s : db.run(Select.from(E_STEP).where(x -> x.get("instance_ID").eq(instanceId)))) {
            if ("PENDING".equals(String.valueOf(s.get("decision")))) {
                lowest = Math.min(lowest, intOf(s.get("stepNo")));
            }
        }
        return lowest == Integer.MAX_VALUE ? 0 : lowest;
    }

    private void closeInstance(String instanceId, String status) {
        Map<String, Object> update = new HashMap<>();
        update.put("status", status);
        update.put("completedAt", Instant.now());
        db.run(Update.entity(E_INSTANCE).data(update).where(i -> i.get("ID").eq(instanceId)));
        reflectOutcome(instanceId, status);
    }

    /**
     * The outcome reaches the document itself. An approval that closes while
     * the request still reads "In Approval" leaves two systems of record, and
     * the person who re-keys the status is the person who mistypes it. Any
     * entity carrying a status element gets this for free; entities without
     * one are left alone.
     */
    private void reflectOutcome(String instanceId, String outcome) {
        Optional<Row> instance = db.run(Select.from(E_INSTANCE)
                .where(i -> i.get("ID").eq(instanceId))).first();
        if (instance.isEmpty()) {
            return;
        }
        String entityName = str(instance.get().get("entityName"));
        String objectID = str(instance.get().get("objectID"));
        if (entityName == null || objectID == null) {
            return;
        }
        boolean hasStatus = runtime.getCdsModel().findEntity(entityName)
                .map(e -> e.findElement("status").isPresent())
                .orElse(false);
        if (!hasStatus) {
            return;
        }
        String status = switch (outcome) {
            case "APPROVED" -> "Approved";
            case "REJECTED" -> "Rejected";
            case "WITHDRAWN" -> "Draft";
            default -> null;
        };
        if (status == null) {
            return;
        }
        Map<String, Object> update = new HashMap<>();
        update.put("status", status);
        db.run(Update.entity(entityName).data(update).where(e -> e.get("ID").eq(objectID)));
    }

    // ------------------------------------------------------------------ helpers

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static int intOf(Object v) {
        if (v instanceof Number n) {
            return n.intValue();
        }
        try { return v == null ? 0 : Integer.parseInt(v.toString()); }
        catch (NumberFormatException e) { return 0; }
    }

    private static BigDecimal dec(Object v) {
        if (v == null) { return null; }
        if (v instanceof BigDecimal b) { return b; }
        try { return new BigDecimal(v.toString()); }
        catch (NumberFormatException e) { return null; }
    }

    private static LocalDate date(Object v) {
        if (v == null) { return null; }
        if (v instanceof LocalDate d) { return d; }
        try { return LocalDate.parse(v.toString()); }
        catch (RuntimeException e) { return null; }
    }
}
