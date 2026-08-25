package com.inflexion.konstryx.auth;

import com.sap.cds.ql.Select;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.request.UserInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Answers "who am I?" with the id the platform actually saw.
 *
 * Everything the product records about a person — an approval, an import run,
 * a persona assignment — is keyed on the XSUAA logon name. Until now the
 * screens showed a name from the UI's own JSON fixture instead, so the name in
 * the corner had no relationship to the identity the service was enforcing
 * against. That is the failure mode this exists to close: an assignment keyed
 * on a different spelling of the same person refuses exactly like no
 * assignment at all, and from a browser the two are indistinguishable.
 *
 * `isAdmin` and `hasPersona` are reported separately on purpose. The `Admin`
 * scope bypasses the data-driven permission model rather than satisfying it,
 * so an administrator sees every row whether or not a persona was ever
 * assigned — and cannot tell the difference from the data.
 */
@Component
@ServiceName("CollaborationService")
public class WhoAmIHandler implements EventHandler {

    /** The scope that bypasses the permission model, as AuthorizationHandler reads it. */
    private static final String ADMIN_ROLE = "Admin";
    private static final String E_ASSIGNMENT = "konstryx.auth.UserAssignment";

    @Autowired
    private PersistenceService db;

    @On(event = "whoAmI")
    public void onWhoAmI(EventContext context) {
        UserInfo user = context.getUserInfo();
        String logon = logonOf(user);

        Map<String, Object> result = new HashMap<>();
        result.put("logon", logon);
        result.put("name", logon);
        result.put("initials", initialsOf(logon));
        result.put("isAdmin", user != null && user.hasRole(ADMIN_ROLE));
        result.put("hasPersona", hasPersona(logon));
        result.put("tenant", user == null ? null : user.getTenant());

        context.put("result", result);
        context.setCompleted();
    }

    /**
     * The logon name, never a fabricated stand-in. An unauthenticated session
     * is reported as such rather than given a plausible-looking id, because a
     * plausible id is what sent the last investigation down the wrong path.
     */
    private static String logonOf(UserInfo user) {
        if (user == null) {
            return "anonymous";
        }
        String name = user.getName();
        if (name != null && !name.isBlank()) {
            return name;
        }
        String id = user.getId();
        return id == null || id.isBlank() ? "anonymous" : id;
    }

    /**
     * Whether the authorization model knows this logon at all — which is the
     * one thing an administrator cannot infer from what the screens show them.
     */
    private boolean hasPersona(String logon) {
        try {
            return db.run(Select.from(E_ASSIGNMENT)
                    .where(a -> a.get("user").eq(logon)
                            .and(a.get("isActive").eq(true))))
                    .first().isPresent();
        } catch (RuntimeException e) {
            // Never fail the call over this. A person who cannot be identified
            // needs the id back more than they need this flag.
            return false;
        }
    }

    /**
     * Initials for the avatar. A logon is usually an email, so the local part
     * is the only human-shaped thing in it; `ziya@example.com` gives Z, and
     * `first.last@example.com` gives FL.
     */
    private static String initialsOf(String logon) {
        String local = logon;
        int at = local.indexOf('@');
        if (at > 0) {
            local = local.substring(0, at);
        }
        StringBuilder initials = new StringBuilder();
        for (String part : local.split("[^A-Za-z0-9]+")) {
            if (!part.isBlank() && initials.length() < 2) {
                initials.append(Character.toUpperCase(part.charAt(0)));
            }
        }
        return initials.length() == 0
                ? "?" : initials.toString().toUpperCase(Locale.ROOT);
    }
}
