package com.inflexion.konstryx.handlers;

import com.sap.cds.services.EventContext;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import org.springframework.stereotype.Component;

/**
 * Custom handler stub for BudgetService.
 * Sprint 3 will implement submit/approve/baseline/lock + availability checks
 * (commitment-pipeline availability across all verticals).
 */
@Component
@ServiceName("BudgetService")
public class BudgetServiceHandler implements EventHandler {

    @On(event = "baseline")
    public void onBaseline(EventContext context) {
        // TODO Sprint 3: lock budget baseline, freeze BudgetLine.authorised,
        // start encumbrance tracking. Placeholder for Sprint 0 skeleton.
        context.setCompleted();
    }
}
