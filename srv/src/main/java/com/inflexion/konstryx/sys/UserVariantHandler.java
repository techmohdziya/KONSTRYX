package com.inflexion.konstryx.sys;

import com.sap.cds.CdsData;
import com.sap.cds.Row;
import com.sap.cds.ql.CQL;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.ql.cqn.CqnPredicate;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.cds.CdsCreateEventContext;
import com.sap.cds.services.cds.CdsDeleteEventContext;
import com.sap.cds.services.cds.CdsReadEventContext;
import com.sap.cds.services.cds.CdsUpdateEventContext;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.HandlerOrder;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.request.UserInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Per-user table personalization: saved column sets, filters, sort orders and
 * groupings, stored against a stable control identifier.
 *
 * Two rules do all the work here. A person sees their own variants and the ones
 * an administrator published, never anyone else's — a saved filter can name a
 * confidential project or a counterparty, so someone else's variant list is a
 * genuine leak, not a cosmetic one. And the owner is taken from the session,
 * never from the payload, because a client that can name the owner can write
 * into another person's personalization.
 */
@Component
@ServiceName("CollaborationService")
public class UserVariantHandler implements EventHandler {

    private static final String E_VARIANT = "konstryx.sys.UserVariant";
    private static final String ENTITY = "CollaborationService.UserVariants";

    @Autowired
    private PersistenceService db;

    // -------------------------------------------------------------------- read

    @Before(event = CqnService.EVENT_READ, entity = ENTITY)
    @HandlerOrder(HandlerOrder.LATE)
    public void narrowToOwnAndPublic(CdsReadEventContext context) {
        UserInfo user = context.getUserInfo();
        if (user == null || user.isPrivileged() || user.isSystemUser()) {
            return;
        }

        CqnPredicate mine = CQL.get("user").eq(user.getName())
                .or(CQL.get("isPublic").eq(true));

        CqnSelect select = context.getCqn();
        CqnPredicate existing = select.where().orElse(null);
        context.setCqn(Select.copy(select)
                .where(existing == null ? mine : CQL.and(existing, mine)));
    }

    // ------------------------------------------------------------------ create

    @Before(event = CqnService.EVENT_CREATE, entity = ENTITY)
    public void beforeCreate(CdsCreateEventContext context, List<CdsData> variants) {
        String me = context.getUserInfo().getName();

        for (CdsData variant : variants) {
            // Never from the payload: a client that can name the owner can write
            // into someone else's personalization.
            variant.put("user", me);

            requireText(variant, "target", "A variant has to say which table it belongs to.");
            requireText(variant, "variantName", "Give the variant a name.");

            if (Boolean.TRUE.equals(variant.get("isPublic")) && !isAdmin(context.getUserInfo())) {
                throw new ServiceException(ErrorStatuses.FORBIDDEN,
                        "Only an administrator can publish a variant for everyone.");
            }

            assertNameIsFree(me, str(variant.get("target")), str(variant.get("variantName")), null);

            if (Boolean.TRUE.equals(variant.get("isDefault"))) {
                clearOtherDefaults(me, str(variant.get("target")), null);
            }
        }
    }

    // ------------------------------------------------------------------ update

    @Before(event = CqnService.EVENT_UPDATE, entity = ENTITY)
    public void beforeUpdate(CdsUpdateEventContext context, List<CdsData> variants) {
        UserInfo user = context.getUserInfo();
        String me = user.getName();

        // The key of a PATCH lives in the URL, not the payload, so the stored
        // rows are read from the statement's own target rather than from data.
        List<Row> stored = targetsOf(context);
        for (Row row : stored) {
            assertMayWrite(row, user);
        }

        for (CdsData variant : variants) {
            variant.remove("user");   // ownership is not transferable through an update

            if (Boolean.TRUE.equals(variant.get("isPublic")) && !isAdmin(user)) {
                throw new ServiceException(ErrorStatuses.FORBIDDEN,
                        "Only an administrator can publish a variant for everyone.");
            }

            String newName = str(variant.get("variantName"));
            for (Row row : stored) {
                String target = str(row.get("target"));
                if (newName != null) {
                    assertNameIsFree(me, target, newName, str(row.get("ID")));
                }
                if (Boolean.TRUE.equals(variant.get("isDefault"))) {
                    clearOtherDefaults(me, target, str(row.get("ID")));
                }
            }
        }
    }

    // ------------------------------------------------------------------ delete

    @Before(event = CqnService.EVENT_DELETE, entity = ENTITY)
    public void beforeDelete(CdsDeleteEventContext context) {
        UserInfo user = context.getUserInfo();
        if (user.isPrivileged() || user.isSystemUser()) {
            return;
        }
        for (Row stored : db.run(context.getCqn())) {
            assertMayWrite(stored, user);
        }
    }

    // ----------------------------------------------------------------- helpers

    /**
     * A public variant belongs to the administrator who published it. Letting
     * end users edit it would make one person's preference everyone's layout.
     */
    private void assertMayWrite(Row stored, UserInfo user) {
        if (user.isPrivileged() || user.isSystemUser()) {
            return;
        }
        if (Boolean.TRUE.equals(stored.get("isPublic")) && !isAdmin(user)) {
            // Legitimately visible, just not theirs to change — so say why.
            throw new ServiceException(ErrorStatuses.FORBIDDEN,
                    "This variant was published for everyone. Only an administrator can change it.");
        }
        if (!user.getName().equals(stored.get("user"))) {
            // Not visible to this person at all. "Belongs to someone else" would
            // confirm the key exists; a row you cannot see should be
            // indistinguishable from one that is not there. This also matches
            // what DELETE already answers, which resolves through the read filter.
            throw new ServiceException(ErrorStatuses.NOT_FOUND,
                    "That variant no longer exists.");
        }
    }

    /** One default per table per person, or the screen has to guess. */
    private void clearOtherDefaults(String user, String target, String exceptId) {
        Map<String, Object> clear = new HashMap<>();
        clear.put("isDefault", false);
        db.run(Update.entity(E_VARIANT).data(clear).where(v -> {
            CqnPredicate p = v.get("user").eq(user)
                    .and(v.get("target").eq(target))
                    .and(v.get("isDefault").eq(true));
            return exceptId == null ? p : CQL.and(p, CQL.get("ID").ne(exceptId));
        }));
    }

    private void assertNameIsFree(String user, String target, String name, String exceptId) {
        boolean taken = db.run(Select.from(E_VARIANT).where(v -> {
            CqnPredicate p = v.get("user").eq(user)
                    .and(v.get("target").eq(target))
                    .and(v.get("variantName").eq(name));
            return exceptId == null ? p : CQL.and(p, CQL.get("ID").ne(exceptId));
        })).first().isPresent();

        if (taken) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    "You already have a variant called \"" + name + "\" on this table.");
        }
    }

    /** The rows an UPDATE is about to change, read through the statement's own target. */
    private List<Row> targetsOf(CdsUpdateEventContext context) {
        Select<?> select = Select.from(context.getCqn().ref());
        context.getCqn().where().ifPresent(select::where);
        List<Row> rows = db.run(select).list();
        if (rows.isEmpty()) {
            throw new ServiceException(ErrorStatuses.NOT_FOUND, "That variant no longer exists.");
        }
        return rows;
    }

    private static boolean isAdmin(UserInfo user) {
        return user != null && user.hasRole("Admin");
    }

    private static void requireText(CdsData data, String field, String message) {
        Object value = data.get(field);
        if (value == null || String.valueOf(value).isBlank()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, message);
        }
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }
}
