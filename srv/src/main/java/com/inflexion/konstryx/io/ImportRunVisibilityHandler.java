package com.inflexion.konstryx.io;

import com.sap.cds.ql.CQL;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.cqn.CqnPredicate;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.services.cds.CdsReadEventContext;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.HandlerOrder;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.request.UserInfo;
import org.springframework.stereotype.Component;

/**
 * Narrows the import history to the person who ran it.
 *
 * An import run records what someone uploaded, and a rejected row keeps the
 * line they typed. That is their working material, not everyone's: a rate file
 * or a subcontractor list is exactly the sort of thing a colleague should not
 * be reading over their shoulder. Administrators still see everything through
 * AuthorizationService.ImportRuns, which is a different entity for that reason.
 */
@Component
@ServiceName("CollaborationService")
public class ImportRunVisibilityHandler implements EventHandler {

    @Before(event = CqnService.EVENT_READ, entity = "CollaborationService.MyImportRuns")
    @HandlerOrder(HandlerOrder.LATE)
    public void narrowRuns(CdsReadEventContext context) {
        narrow(context, "createdBy");
    }

    @Before(event = CqnService.EVENT_READ, entity = "CollaborationService.MyImportRows")
    @HandlerOrder(HandlerOrder.LATE)
    public void narrowRows(CdsReadEventContext context) {
        // A row is only reachable through its run, so the same test applied to
        // the parent keeps the two consistent.
        narrow(context, "run.createdBy");
    }

    private void narrow(CdsReadEventContext context, String path) {
        UserInfo user = context.getUserInfo();
        if (user == null || user.isPrivileged() || user.isSystemUser()) {
            return;
        }
        CqnPredicate mine = CQL.get(path).eq(user.getName());
        CqnSelect select = context.getCqn();
        CqnPredicate existing = select.where().orElse(null);
        context.setCqn(Select.copy(select)
                .where(existing == null ? mine : CQL.and(existing, mine)));
    }
}
