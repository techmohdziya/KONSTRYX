package com.inflexion.konstryx.ins;

import com.inflexion.konstryx.bud.BudgetPhasingHandler;
import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.runtime.CdsRuntime;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.annotation.Profile;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.time.LocalDate;

/**
 * Phases the budgets and reconciles the projects once, on an empty database.
 *
 * Two kinds of data live in this service and they survive a restart
 * differently. Seeded rows are read from db/data and test/data every time the
 * service boots, so they are always there. Phases and period reports are
 * neither seeded nor recomputed on read - they are written by phaseBudget and
 * reconcile and then kept, because a measurement that is recomputed later can
 * no longer be compared with what was reported at the time. On the in-memory
 * H2 database that local development uses, "kept" lasts until the process
 * stops, so every restart left the cost value reconciliation and the whole
 * planned-value column empty until somebody remembered to run two actions.
 *
 * Nobody should have to remember. This runs them, and the guards below are
 * what keep it from becoming something worse than the problem it solves.
 *
 * Development only, by profile. On a real tenant this would be wrong twice
 * over: it would write period reports nobody asked for, and it would date them
 * to whenever the service happened to restart.
 *
 * Only on an empty database. A service that re-reconciled every project on
 * every boot would overwrite the measurements somebody had taken deliberately,
 * which is the one thing a kept report must never do.
 */
@Component
@Profile("default")
public class ReportWarmUp {

    private static final Logger log = LoggerFactory.getLogger(ReportWarmUp.class);

    private static final String E_BUDGET = "konstryx.bud.Budget";
    private static final String E_PROJECT = "konstryx.prj.Project";
    private static final String E_PHASE = "konstryx.bud.BudgetPhase";
    private static final String E_REPORT = "konstryx.ins.ProjectPeriodReport";

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    @Autowired
    private BudgetPhasingHandler phasing;

    @Autowired
    private ReconcileHandler reconcile;

    @EventListener(ApplicationReadyEvent.class)
    public void warmUp() {
        if (!isEmpty(E_PHASE) || !isEmpty(E_REPORT)) {
            log.debug("Phases or period reports already present; leaving them alone.");
            return;
        }
        // Privileged, like the content deployment: this is the platform warming
        // itself up, not an action somebody invoked, and it must not depend on
        // whichever user happens to make the first request.
        runtime.requestContext().privilegedUser().run(ctx -> {
            int phased = 0;
            int reconciled = 0;
            LocalDate today = LocalDate.now();

            for (Row budget : db.run(Select.from(E_BUDGET))) {
                try {
                    phasing.phase(budget);
                    phased++;
                } catch (Exception e) {
                    // One budget that cannot be phased - no project dates, no
                    // periods for its year - must not stop the others, and must
                    // certainly not stop the service starting.
                    log.warn("Could not phase {}: {}", budget.get("docNo"), e.getMessage());
                }
            }
            for (Row project : db.run(Select.from(E_PROJECT))) {
                try {
                    reconcile.reconcile(project, today);
                    reconciled++;
                } catch (Exception e) {
                    log.warn("Could not reconcile {}: {}", project.get("code"), e.getMessage());
                }
            }
            log.info("Warm-up: phased {} budget(s), reconciled {} project(s) as at {}.",
                    phased, reconciled, today);
        });
    }

    private boolean isEmpty(String entity) {
        return db.run(Select.from(entity)).first().isEmpty();
    }
}
