package com.inflexion.konstryx.master;

import com.inflexion.konstryx.auth.PermissionService;
import com.sap.cds.ql.CQL;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.cqn.CqnPredicate;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.reflect.CdsEntity;
import com.sap.cds.services.cds.ApplicationService;
import com.sap.cds.services.cds.CdsReadEventContext;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.HandlerOrder;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.request.UserInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.Set;

/**
 * Enforces the hybrid scoped-master rule on read.
 *
 * A master carrying the `scoped` aspect is either GROUP — shared across the
 * company group — or COMPANY, belonging to one legal entity. Sister companies
 * must not see each other's local masters: two companies in the same group can
 * legitimately hold different rates for the same trade, and showing both would
 * make the rate picker ambiguous and the cost wrong.
 *
 * This is distinct from authorization. Authorization answers "which companies
 * may this user work in"; scope answers "which company does this record belong
 * to". Both narrow a read, and they compose: the user's companies come from
 * their assignments, and a record is visible if it is GROUP or belongs to one
 * of those companies.
 *
 * Runs after AuthorizationHandler so the activity check has already rejected
 * anyone with no grant at all.
 *
 * Scoped masters therefore declare no companyPath in the authorization
 * catalogue. A plain company equality there would test owningCompany.code =
 * 'INFC', which is null on every GROUP record and so hides exactly the shared
 * masters the group exists to share. The company dimension for these entities
 * is this handler's, and only this handler's.
 */
@Component
@ServiceName(value = "*", type = ApplicationService.class)
public class MasterScopeHandler implements EventHandler {

    /** The signature of the `scoped` aspect, duck-typed from the model. */
    private static final String EL_SCOPE = "scope";
    private static final String EL_OWNER = "owningCompany";

    @Autowired
    private PermissionService permissions;

    @Before(event = CqnService.EVENT_READ)
    @HandlerOrder(HandlerOrder.LATE)
    public void narrowToVisibleScope(CdsReadEventContext context) {
        UserInfo user = context.getUserInfo();
        if (user == null || user.isPrivileged() || user.isSystemUser()) {
            return;
        }

        CdsEntity target = context.getTarget();
        if (!isScopedMaster(target)) {
            return;
        }

        Set<String> companies = permissions.companiesFor(user.getName());
        if (companies.isEmpty()) {
            return;   // group-wide user: every company's masters are legitimately visible
        }

        CqnPredicate visible = CQL.get(EL_SCOPE).eq("GROUP");
        for (String company : companies) {
            visible = CQL.or(visible, CQL.get("owningCompany.code").eq(company));
        }

        CqnSelect select = context.getCqn();
        CqnPredicate existing = select.where().orElse(null);
        CqnPredicate combined = existing == null ? visible : CQL.and(existing, visible);
        context.setCqn(Select.copy(select).where(combined));
    }

    /**
     * Duck-typed rather than driven by a list of entity names: the aspect is
     * mixed into masters as the model grows, and a hard-coded list would
     * silently stop protecting whatever was added last.
     */
    private boolean isScopedMaster(CdsEntity entity) {
        return entity != null
                && entity.findElement(EL_SCOPE).isPresent()
                && entity.findElement(EL_OWNER).isPresent();
    }
}
