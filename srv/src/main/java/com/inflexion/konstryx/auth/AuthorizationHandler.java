package com.inflexion.konstryx.auth;

import com.sap.cds.ql.CQL;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.cqn.CqnPredicate;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.reflect.CdsEntity;
import com.sap.cds.reflect.CdsModel;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.cds.ApplicationService;
import com.sap.cds.services.cds.CdsCreateEventContext;
import com.sap.cds.services.cds.CdsDeleteEventContext;
import com.sap.cds.services.cds.CdsReadEventContext;
import com.sap.cds.services.cds.CdsUpdateEventContext;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.HandlerOrder;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.request.UserInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Turns konstryx.auth from a data model into an actual control.
 *
 * Runs before every CRUD event on every application service. Two things happen:
 *
 *   1. Activity check — does the user hold this activity on this entity at all?
 *      No grant means 403, not an empty list, because "you may not do this" and
 *      "there is nothing here" are different answers and conflating them makes
 *      misconfigured authorization impossible to diagnose.
 *
 *   2. Instance filter — on READ, the statement is narrowed to the companies
 *      and projects the grants actually cover, using the paths declared on the
 *      authorization object. A user with two assignments sees the union.
 *
 * Entities absent from the catalogue are not protected and pass through. That
 * is deliberate: drafts, code lists and framework entities have no business
 * meaning to restrict, and failing closed on them would break the application
 * without improving security.
 */
@Component
@ServiceName(value = "*", type = ApplicationService.class)
public class AuthorizationHandler implements EventHandler {

    /**
     * Bootstrap escape hatch. A fresh deployment has no personas and no
     * assignments, so without this nobody could log in to create the first one.
     * The XSUAA Admin scope is granted outside the application, in the identity
     * provider, which is the right place for the key to the empty building.
     */
    private static final String BOOTSTRAP_ROLE = "Admin";

    private static final String ACT_CREATE  = "01";
    private static final String ACT_CHANGE  = "02";
    private static final String ACT_DISPLAY = "03";
    private static final String ACT_DELETE  = "06";

    @Autowired
    private PermissionService permissions;

    @Before(event = CqnService.EVENT_READ)
    @HandlerOrder(HandlerOrder.EARLY)
    public void beforeRead(CdsReadEventContext context) {
        if (bypass(context.getUserInfo())) {
            return;
        }
        PermissionService.ProtectedEntity target =
                protectedTarget(context.getTarget(), context.getModel());
        if (target == null) {
            return;
        }
        List<Grant> grants = require(context.getUserInfo(), target, ACT_DISPLAY);
        applyInstanceFilter(context, target, grants);
    }

    @Before(event = CqnService.EVENT_CREATE)
    @HandlerOrder(HandlerOrder.EARLY)
    public void beforeCreate(CdsCreateEventContext context) {
        guard(context.getTarget(), context.getModel(), context.getUserInfo(), ACT_CREATE);
    }

    @Before(event = CqnService.EVENT_UPDATE)
    @HandlerOrder(HandlerOrder.EARLY)
    public void beforeUpdate(CdsUpdateEventContext context) {
        guard(context.getTarget(), context.getModel(), context.getUserInfo(), ACT_CHANGE);
    }

    @Before(event = CqnService.EVENT_DELETE)
    @HandlerOrder(HandlerOrder.EARLY)
    public void beforeDelete(CdsDeleteEventContext context) {
        guard(context.getTarget(), context.getModel(), context.getUserInfo(), ACT_DELETE);
    }

    // ------------------------------------------------------------------ core

    private void guard(CdsEntity target, CdsModel model, UserInfo user, String activity) {
        if (bypass(user)) {
            return;
        }
        PermissionService.ProtectedEntity protectedEntity = protectedTarget(target, model);
        if (protectedEntity == null) {
            return;
        }
        require(user, protectedEntity, activity);
    }

    /**
     * The event target is the service projection — WorkflowService.ResourceRequests
     * — while the catalogue is keyed by the persistence entity it projects,
     * konstryx.wf.ResourceRequest. Following the projection's own query back to
     * its source is the only reliable way across that gap: matching on the
     * simple name fails on the plural, and a security control that silently
     * fails to find its target is worse than no control at all.
     */
    private PermissionService.ProtectedEntity protectedTarget(CdsEntity target, CdsModel model) {
        if (target == null) {
            return null;
        }
        PermissionService.ProtectedEntity direct =
                permissions.catalogue().get(target.getQualifiedName());
        if (direct != null) {
            return direct;
        }
        String root = rootEntityOf(target, model);
        return root == null ? null : permissions.catalogue().get(root);
    }

    /** Walks projection -> source until an entity with no underlying query. */
    private String rootEntityOf(CdsEntity entity, CdsModel model) {
        CdsEntity current = entity;
        Set<String> seen = new HashSet<>();
        while (current != null && seen.add(current.getQualifiedName())) {
            Optional<CqnSelect> query = current.query();
            if (query.isEmpty()) {
                return current.getQualifiedName();
            }
            String source;
            try {
                source = query.get().ref().firstSegment();
            } catch (RuntimeException e) {
                return current.getQualifiedName();
            }
            CdsEntity next = model.findEntity(source).orElse(null);
            if (next == null) {
                return current.getQualifiedName();
            }
            current = next;
        }
        return current == null ? null : current.getQualifiedName();
    }

    private boolean bypass(UserInfo user) {
        return user == null
                || user.isPrivileged()
                || user.isSystemUser()
                || user.hasRole(BOOTSTRAP_ROLE);
    }

    private List<Grant> require(UserInfo user, PermissionService.ProtectedEntity target, String activity) {
        List<Grant> grants = permissions.grantsFor(user.getName(), target.entityName(), activity);
        if (grants.isEmpty()) {
            throw new ServiceException(ErrorStatuses.FORBIDDEN,
                    "Not authorized: activity " + activity + " on " + target.authObjectCode()
                            + ". Ask an administrator to grant it to one of your personas.");
        }
        return grants;
    }

    /**
     * Narrows a READ to the scope the grants cover. An unrestricted grant on a
     * dimension drops the filter for that dimension entirely — holding both a
     * group-wide persona and a project-scoped one means the group-wide one wins,
     * which is the additive behaviour users expect from role membership.
     */
    private void applyInstanceFilter(CdsReadEventContext context,
                                     PermissionService.ProtectedEntity target,
                                     List<Grant> grants) {

        CqnPredicate restriction = null;

        if (notBlank(target.companyPath()) && grants.stream().noneMatch(Grant::isCompanyUnrestricted)) {
            Set<String> companies = grants.stream()
                    .map(Grant::companyCode).filter(AuthorizationHandler::notBlank)
                    .collect(Collectors.toSet());
            restriction = anyOf(target.companyPath(), companies);
        }

        if (notBlank(target.projectPath()) && grants.stream().noneMatch(Grant::isProjectUnrestricted)) {
            Set<String> projects = grants.stream()
                    .map(Grant::projectCode).filter(AuthorizationHandler::notBlank)
                    .collect(Collectors.toSet());
            CqnPredicate byProject = anyOf(target.projectPath(), projects);
            if (byProject != null) {
                restriction = restriction == null ? byProject : CQL.and(restriction, byProject);
            }
        }

        if (restriction == null) {
            return;
        }

        // Two traps here, both silent:
        //   CQL.copy with a Modifier only invokes where() when the statement
        //   already has a WHERE, so unfiltered list requests — the common case
        //   — would pass through unrestricted.
        //   Select.where() then REPLACES rather than ANDs, which would discard
        //   the caller's own $filter and quietly return more than they asked for.
        // So the existing predicate is combined explicitly.
        CqnSelect select = context.getCqn();
        CqnPredicate existing = select.where().orElse(null);
        CqnPredicate combined = existing == null ? restriction : CQL.and(existing, restriction);
        context.setCqn(Select.copy(select).where(combined));
    }

    /**
     * path = a OR path = b ... rather than an IN list. Scopes are a handful of
     * codes, so the shape costs nothing, and it sidesteps the literal-typing
     * rules that IN applies to its value list.
     */
    private static CqnPredicate anyOf(String path, Set<String> values) {
        CqnPredicate combined = null;
        for (String value : values) {
            CqnPredicate eq = CQL.get(path).eq(value);
            combined = combined == null ? eq : CQL.or(combined, eq);
        }
        return combined;
    }

    private static boolean notBlank(String s) {
        return s != null && !s.isBlank();
    }
}
