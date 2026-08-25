package com.inflexion.konstryx.s4;

import com.inflexion.konstryx.mat.ProcurementHandler;
import com.inflexion.konstryx.prj.ProjectHandler;
import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.runtime.CdsRuntime;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.util.Optional;

/**
 * A one-shot outbound push, triggered by an environment variable.
 *
 * **This WRITES to S/4.** It is not the read-only `S4Probe` and must not be
 * treated like it: a project push creates an Enterprise Project and its WBS
 * elements, and a requisition push creates a purchase requisition that S/4
 * numbers. Neither is trivially undone.
 *
 * It exists because there is no other way to trigger these from outside. The
 * credentials live in the `ITS_S4` destination on the deployed app, and every
 * OData endpoint there is behind XSUAA — so a push cannot be driven from a
 * developer machine or a script without an interactive login. Setting one
 * variable and restarting can:
 *
 *     cf set-env konstryx-srv S4_PUSH project:PRJ-001
 *     cf restart konstryx-srv
 *     cf logs konstryx-srv --recent | grep S4Push
 *     cf unset-env konstryx-srv S4_PUSH     &lt;- IMMEDIATELY
 *
 * **Unset it as soon as the log is read.** Left set, every restart — including
 * one Cloud Foundry performs on its own — attempts the push again. The
 * underlying gates make a repeat harmless (a project already SENT is not
 * PENDING; a requisition S/4 has numbered is refused with a 409), which is
 * exactly why those gates are in the handler and not in this class.
 *
 * Nothing here reimplements a push. It resolves one row and calls the same
 * method the OData action calls, so the gates, the connector and the writer
 * are shared and this cannot drift from them.
 */
@Component
public class S4Push {

    private static final Logger log = LoggerFactory.getLogger(S4Push.class);

    private static final String E_PROJECT = "konstryx.prj.Project";
    private static final String E_PR = "konstryx.mat.PurchaseRequisition";
    private static final String E_RR = "konstryx.wf.ResourceRequest";

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    @Autowired
    private ProjectHandler projects;

    @Autowired
    private ProcurementHandler procurement;

    @EventListener(ApplicationReadyEvent.class)
    public void pushIfAsked() {
        String what = System.getenv("S4_PUSH");
        if (what == null || what.isBlank()) {
            return;
        }
        log.warn("S4_PUSH={} — this creates REAL documents in S/4. Unset it once "
                + "the outcome below is read.", what);

        String[] parts = what.split(":", 2);
        if (parts.length != 2 || parts[1].isBlank()) {
            log.warn("S4Push: expected project:<code> or requisition:<requestDocNo>, got {}",
                    what);
            return;
        }
        String kind = parts[0].trim().toLowerCase();
        String key = parts[1].trim();

        try {
            // A privileged request context: this runs at startup with no user,
            // and the handlers below read and write through services that
            // expect one. Same idiom ContentDeploymentService uses at boot.
            runtime.requestContext().privilegedUser().run(rc -> {
                if ("project".equals(kind)) {
                    pushProject(key);
                } else if ("requisition".equals(kind)) {
                    pushRequisition(key);
                } else {
                    log.warn("S4Push: unknown push kind '{}'", kind);
                }
            });
        } catch (Exception e) {
            // Never take the service down over a push. The document is either
            // in S/4 or it is not, and the log says which.
            log.warn("S4Push: {} {} failed: {}", kind, key, e.toString());
        }
    }

    private void pushProject(String code) {
        Optional<Row> found = db.run(Select.from(E_PROJECT)
                .where(p -> p.get("code").eq(code))).first();
        if (found.isEmpty()) {
            log.warn("S4Push: no project {}", code);
            return;
        }
        Row project = found.get();
        log.warn("S4Push: pushing project {} (syncStatus {})", code, project.get("syncStatus"));
        log.warn("S4Push: RESULT {}", projects.pushToS4(project));
    }

    /**
     * Keyed by the resource request's document number rather than the
     * requisition's own id, because the requisition deliberately has no
     * human-readable number of its own until S/4 issues one (D-21) — the
     * request that raised it is the only thing a person can name.
     */
    private void pushRequisition(String requestDocNo) {
        Optional<Row> request = db.run(Select.from(E_RR)
                .where(r -> r.get("docNo").eq(requestDocNo))).first();
        if (request.isEmpty()) {
            log.warn("S4Push: no resource request {}", requestDocNo);
            return;
        }
        String rrId = String.valueOf(request.get().get("ID"));
        Optional<Row> found = db.run(Select.from(E_PR)
                .where(p -> p.get("sourceRequest_ID").eq(rrId))).first();
        if (found.isEmpty()) {
            log.warn("S4Push: {} has raised no requisition", requestDocNo);
            return;
        }
        Row pr = found.get();
        log.warn("S4Push: pushing the requisition from {} (syncStatus {})",
                requestDocNo, pr.get("syncStatus"));
        log.warn("S4Push: RESULT {}", procurement.pushToS4(pr));
    }
}
