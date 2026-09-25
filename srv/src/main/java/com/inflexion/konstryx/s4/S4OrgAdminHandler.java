package com.inflexion.konstryx.s4;

import com.sap.cds.services.EventContext;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Exposes the organizational read as an administrator action.
 *
 * It sits on AdminService because that is where Companies live, and filling a
 * company's plant and profit centre is what the read is for. Deliberately an
 * action rather than a startup hook: an administrator who has just assigned a
 * company code needs to re-read without a restart, and on a multi-tenant
 * subscription a restart is not theirs to order.
 */
@Component
@ServiceName("AdminService")
public class S4OrgAdminHandler implements EventHandler {

    @Autowired
    private S4OrgConnector org;

    @Autowired
    private S4MasterConnector masters;

    @Autowired
    private S4ProcurementConnector procurement;

    @On(event = "syncOrgFromS4")
    public void onSyncOrgFromS4(EventContext context) {
        context.put("result", org.sync());
        context.setCompleted();
    }

    @On(event = "syncMastersFromS4")
    public void onSyncMastersFromS4(EventContext context) {
        context.put("result", masters.sync());
        context.setCompleted();
    }

    @On(event = "syncProcurementFromS4")
    public void onSyncProcurementFromS4(EventContext context) {
        context.put("result", procurement.sync());
        context.setCompleted();
    }
}
