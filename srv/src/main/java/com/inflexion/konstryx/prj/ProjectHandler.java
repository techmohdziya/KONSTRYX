package com.inflexion.konstryx.prj;

import com.sap.cds.CdsData;
import com.sap.cds.Row;
import com.sap.cds.ql.CQL;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.ql.cqn.CqnPredicate;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.cds.CdsCreateEventContext;
import com.sap.cds.services.cds.CdsUpdateEventContext;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.draft.DraftService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.time.LocalDate;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * The project is mastered in KONSTRYX (D-17), which reverses the rule that held
 * everywhere else: it is created here and pushed to S/4, or imported from
 * Primavera, rather than mirrored inward.
 *
 * That reversal is why this handler exists. A mirrored row is only ever as
 * wrong as its source. A row mastered here can be wrong on its own, and can sit
 * in KONSTRYX looking perfectly normal while S/4 has never heard of it — and
 * everything downstream, every requisition and every budget, would post against
 * a project that does not exist.
 */
@Component
@ServiceName("ProjectService")
public class ProjectHandler implements EventHandler {

    private static final String E_PROJECT = "konstryx.prj.Project";
    private static final String ENTITY = "ProjectService.Projects";

    /** Written by the connector, never by a person. */
    private static final List<String> SYNC_FIELDS = List.of(
            "syncStatus", "s4Key", "s4System", "lastSyncedAt", "syncMessage", "syncAttempts");

    @Autowired
    private PersistenceService db;

    @Autowired
    private P6ImportService p6;

    @Autowired
    private com.inflexion.konstryx.s4.S4ProjectConnector s4Connector;

    // ------------------------------------------------------------- validation

    @Before(event = { CqnService.EVENT_CREATE, CqnService.EVENT_UPDATE }, entity = ENTITY)
    public void validate(EventContext context, List<CdsData> projects) {
        for (CdsData project : projects) {
            String id = str(project.get("ID"));
            Row stored = id == null ? null : db.run(Select.from(E_PROJECT)
                    .where(p -> p.get("ID").eq(id.toLowerCase()))).first().orElse(null);

            String code = coalesce(str(project.get("code")), stored == null ? null : str(stored.get("code")));
            if (isBlank(code)) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "A project needs a code.");
            }
            assertCodeIsFree(code, id);

            if (isBlank(coalesce(str(project.get("name")), stored == null ? null : str(stored.get("name"))))) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST, "A project needs a name.");
            }

            Object companyId = coalesce(project.get("company_ID"),
                    stored == null ? null : stored.get("company_ID"));
            if (companyId == null) {
                // Without a company there is no legal entity to post to, no
                // company-scoped number range, and no basis for authorization.
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "A project must belong to a company.");
            }

            assertDatesAgree(project, stored);
            assertHierarchyIsSane(project, stored, id);
            protectSyncFields(project, stored);
        }
    }

    private void assertDatesAgree(CdsData project, Row stored) {
        LocalDate start = date(coalesce(project.get("startDate"),
                stored == null ? null : stored.get("startDate")));
        LocalDate end = date(coalesce(project.get("endDate"),
                stored == null ? null : stored.get("endDate")));
        if (start != null && end != null && end.isBefore(start)) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The project ends before it starts.");
        }
    }

    /**
     * A project cannot be its own ancestor. Without this a two-project cycle
     * makes every hierarchy walk — roll-ups, authorization by project, the
     * project tree in the UI — run until something gives out.
     */
    private void assertHierarchyIsSane(CdsData project, Row stored, String id) {
        if (!project.containsKey("parentProject_ID")) {
            return;
        }
        Object parentId = project.get("parentProject_ID");
        if (parentId == null || id == null) {
            return;
        }
        String self = id.toLowerCase();
        if (self.equals(String.valueOf(parentId).toLowerCase())) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A project cannot be its own parent.");
        }

        Set<String> seen = new HashSet<>();
        String current = String.valueOf(parentId).toLowerCase();
        while (current != null && seen.add(current)) {
            if (current.equals(self)) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "That would make the project its own ancestor.");
            }
            String cursor = current;
            Optional<Row> parent = db.run(Select.from(E_PROJECT)
                    .where(p -> p.get("ID").eq(cursor))).first();
            current = parent.map(r -> r.get("parentProject_ID"))
                    .map(v -> String.valueOf(v).toLowerCase())
                    .orElse(null);
        }
    }

    /**
     * Sync state is the connector's to write, not the user's. Someone editing a
     * project header must not be able to mark it SENT and make an
     * unsynchronised project look settled.
     */
    private void protectSyncFields(CdsData project, Row stored) {
        // Stripped rather than rejected. The projection marks these @readonly,
        // so the protocol layer already refuses a user who tries to set them and
        // gives them the message. This is the second line: it guarantees the
        // invariant for any path that does not go through OData - an import, a
        // future connector, a handler written later - without risking a false
        // refusal when CAP echoes the unchanged values back during draft
        // activation.
        for (String field : SYNC_FIELDS) {
            project.remove(field);
        }
        if (stored == null) {
            project.put("syncStatus", "NOT_SENT");
            project.put("syncAttempts", 0);
        }
    }

    private void assertCodeIsFree(String code, String id) {
        String self = id == null ? null : id.toLowerCase();
        boolean taken = db.run(Select.from(E_PROJECT).where(p -> {
            CqnPredicate same = p.get("code").eq(code);
            return self == null ? same : CQL.and(same, CQL.get("ID").ne(self));
        })).first().isPresent();

        if (taken) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "Project code " + code + " already exists.");
        }
    }

    /**
     * The draft path needs its own guard. @readonly in the projection covers
     * the active entity, but CAP dispatches a draft edit as DRAFT_PATCH and
     * lets it through — so without this the draft would sit there displaying
     * SENT and an invented S/4 key. Activation strips them, so the stored
     * record was never wrong; the user was just being shown something untrue
     * until they saved.
     */
    @Before(event = DraftService.EVENT_DRAFT_PATCH, entity = ENTITY)
    public void refuseSyncEditsInDraft(List<CdsData> projects) {
        for (CdsData project : projects) {
            for (String field : SYNC_FIELDS) {
                if (project.containsKey(field)) {
                    throw new ServiceException(ErrorStatuses.FORBIDDEN,
                            "Synchronisation status is set by the S/4 connector, not by hand.");
                }
            }
        }
    }

    // ------------------------------------------------------------------- sync

    @On(event = "releaseToS4")
    public void onRelease(EventContext context) {
        Row project = targetOf(context);
        String status = str(project.get("syncStatus"));

        if ("SENT".equals(status)) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    project.get("code") + " is already in S/4 as " + project.get("s4Key") + ".");
        }
        if ("PENDING".equals(status)) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    project.get("code") + " is already queued to be sent.");
        }
        assertReadyToLeave(project);

        Map<String, Object> update = new HashMap<>();
        update.put("syncStatus", "PENDING");
        update.put("syncMessage", null);
        String id = str(project.get("ID"));
        db.run(Update.entity(E_PROJECT).data(update).where(p -> p.get("ID").eq(id)));

        return_(context, project.get("code")
                + " is queued for S/4. It will show as not yet in S/4 until the "
                + "connector confirms it — nothing downstream should be posted against "
                + "it before then.");
    }

    /**
     * The checks S/4 would fail on anyway, made here where the message can name
     * the field. A project rejected by the connector at three in the morning is
     * a support call; a project refused at release is a corrected form.
     */
    private void assertReadyToLeave(Row project) {
        if (project.get("company_ID") == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "S/4 needs the company code. Set the company before releasing.");
        }
        if (project.get("startDate") == null || project.get("endDate") == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "S/4 needs both start and end dates.");
        }
        boolean hasWbs = db.run(Select.from("konstryx.prj.WBSElement")
                .where(w -> w.get("project_ID").eq(str(project.get("ID")))))
                .first().isPresent();
        if (!hasWbs) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A project with no WBS has nothing to post against. Add at least one "
                            + "WBS element before releasing.");
        }
    }

    @On(event = "importP6")
    public void onImportP6(EventContext context) {
        Object content = context.get("content");
        if (content == null || String.valueOf(content).isBlank()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, "The file is empty.");
        }
        String companyId = str(context.get("companyID"));
        if (companyId == null) {
            // P6 has no notion of our legal entities, so the caller has to say
            // which one the project belongs to. Guessing would put a project in
            // the wrong company's books.
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Say which company the project belongs to — a P6 file does not carry that.");
        }

        Map<String, Object> result = p6.importXml(
                str(context.get("fileName")) == null ? "p6-export.xml" : str(context.get("fileName")),
                String.valueOf(content),
                companyId.toLowerCase(),
                Boolean.TRUE.equals(context.get("validateOnly")));

        return_(context, result.get("message") + " Import run " + result.get("runId")
                + " holds the detail.");
    }

    @On(event = "recordSyncResult")
    public void onSyncResult(EventContext context) {
        Row project = targetOf(context);
        boolean success = Boolean.TRUE.equals(context.get("success"));
        applySyncOutcome(project, success, str(context.get("s4Key")),
                str(context.get("s4System")), str(context.get("message")));
        return_(context, success
                ? project.get("code") + " is now in S/4 as " + context.get("s4Key") + "."
                : project.get("code") + " was refused by S/4: " + context.get("message"));
    }

    /**
     * The live push. Only a queued project syncs — release is the gate that
     * validated it, and skipping the queue would skip the gate. The connector
     * returns the outcome; recording it goes through the same method the
     * manual recordSyncResult uses, so both paths write identical state.
     */
    @On(event = "syncToS4")
    public void onSyncToS4(EventContext context) {
        return_(context, pushToS4(targetOf(context)));
    }

    /**
     * The push itself, callable without an OData request.
     *
     * Extracted so the action and any programmatic caller run the same gates
     * and the same writer. The alternative — a second caller reimplementing
     * "check PENDING, push, record" — is how two paths end up writing subtly
     * different state, which is the exact failure recordSyncResult exists to
     * avoid.
     */
    public String pushToS4(Row project) {
        if (!"PENDING".equals(str(project.get("syncStatus")))) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    project.get("code") + " is " + project.get("syncStatus")
                            + " — release it first; only a queued project syncs.");
        }
        if (!s4Connector.isConfigured()) {
            throw new ServiceException(ErrorStatuses.SERVER_ERROR,
                    "No S/4 connection is configured. The project stays queued.");
        }

        com.inflexion.konstryx.s4.S4ProjectConnector.SyncOutcome outcome =
                s4Connector.push(project);
        applySyncOutcome(project, outcome.success, outcome.s4Key,
                outcome.s4System, outcome.message);

        return outcome.success
                ? project.get("code") + " is now in S/4 as " + outcome.s4Key
                        + ". " + outcome.message
                : project.get("code") + " was refused by S/4: " + outcome.message;
    }

    /** One writer for sync state, whichever path produced the outcome. */
    private void applySyncOutcome(Row project, boolean success, String s4Key,
                                  String s4System, String message) {
        String id = str(project.get("ID"));
        Map<String, Object> update = new HashMap<>();
        update.put("syncAttempts", intOf(project.get("syncAttempts")) + 1);
        update.put("syncMessage", message);
        if (success) {
            update.put("syncStatus", "SENT");
            update.put("s4Key", s4Key);
            update.put("s4System", s4System);
            update.put("lastSyncedAt", Instant.now());
        } else {
            update.put("syncStatus", "FAILED");
        }
        db.run(Update.entity(E_PROJECT).data(update).where(p -> p.get("ID").eq(id)));
    }

    // ----------------------------------------------------------------- helpers

    private Row targetOf(EventContext context) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        return (select == null ? Optional.<Row>empty() : db.run(select).first())
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "Project not found."));
    }

    private static void return_(EventContext context, String message) {
        context.put("result", message);
        context.setCompleted();
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static boolean isBlank(String s) { return s == null || s.isBlank(); }

    private static Object coalesce(Object a, Object b) { return a != null ? a : b; }

    private static String coalesce(String a, String b) { return a != null ? a : b; }

    private static int intOf(Object v) {
        if (v instanceof Number n) {
            return n.intValue();
        }
        try { return v == null ? 0 : Integer.parseInt(v.toString()); }
        catch (NumberFormatException e) { return 0; }
    }

    private static LocalDate date(Object v) {
        if (v == null) { return null; }
        if (v instanceof LocalDate d) { return d; }
        try { return LocalDate.parse(v.toString()); }
        catch (RuntimeException e) { return null; }
    }
}
