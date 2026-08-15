package com.inflexion.konstryx.auth;

import com.sap.cds.Result;
import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.runtime.CdsRuntime;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Resolves what a user may actually do, from the configuration an administrator
 * maintains rather than from anything compiled in.
 *
 * Reads run as a privileged user deliberately: resolving permissions must not
 * itself require permission, or the first request would recurse forever.
 */
@Component
public class PermissionService {

    /** Catalogue of protected entities, keyed by CDS qualified name. */
    public record ProtectedEntity(String authObjectCode, String entityName,
                                  String projectPath, String companyPath) {}

    private static final String V_PERMISSION = "konstryx.auth.EffectivePermission";
    private static final String E_AUTH_OBJECT = "konstryx.auth.AuthObject";

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    /**
     * The catalogue changes only when the product ships new objects, so it is
     * cached for the life of the process. Grants are not cached: an
     * administrator revoking access expects that to take effect now, and a
     * stale permission cache is a security bug rather than a performance one.
     */
    private volatile Map<String, ProtectedEntity> catalogue;

    public Map<String, ProtectedEntity> catalogue() {
        if (catalogue == null) {
            synchronized (this) {
                if (catalogue == null) {
                    catalogue = loadCatalogue();
                }
            }
        }
        return catalogue;
    }

    private Map<String, ProtectedEntity> loadCatalogue() {
        Map<String, ProtectedEntity> map = new ConcurrentHashMap<>();
        runtime.requestContext().privilegedUser().run(ctx -> {
            Result rows = db.run(Select.from(E_AUTH_OBJECT));
            for (Row r : rows) {
                String entityName = str(r, "entityName");
                if (entityName == null || entityName.isBlank()) {
                    continue;
                }
                map.put(entityName, new ProtectedEntity(
                        str(r, "code"), entityName,
                        str(r, "projectPath"), str(r, "companyPath")));
            }
        });
        return map;
    }

    /** All currently valid grants for a user, across every persona assignment. */
    public List<Grant> grantsFor(String user, String entityName, String activity) {
        List<Grant> grants = new ArrayList<>();
        if (user == null) {
            return grants;
        }
        LocalDate today = LocalDate.now();

        runtime.requestContext().privilegedUser().run(ctx -> {
            Result rows = db.run(Select.from(V_PERMISSION)
                    .where(p -> p.get("user").eq(user)
                            .and(p.get("entityName").eq(entityName))
                            .and(p.get("activityCode").eq(activity))));
            for (Row r : rows) {
                if (!withinValidity(r, today)) {
                    continue;
                }
                grants.add(new Grant(
                        str(r, "entityName"),
                        str(r, "authObjectCode"),
                        str(r, "activityCode"),
                        str(r, "companyCode"),
                        str(r, "projectCode")));
            }
        });
        return grants;
    }

    /**
     * The company codes a user is assigned to, across all their personas.
     *
     * An empty set means unrestricted — at least one assignment carries no
     * company, so the user works group-wide. Callers must treat empty as "all",
     * not as "none", or a group-wide steward would see nothing.
     */
    public java.util.Set<String> companiesFor(String user) {
        java.util.Set<String> companies = new java.util.HashSet<>();
        if (user == null) {
            return companies;
        }
        LocalDate today = LocalDate.now();
        boolean[] unrestricted = { false };

        runtime.requestContext().privilegedUser().run(ctx -> {
            Result rows = db.run(Select.from(V_PERMISSION)
                    .where(p -> p.get("user").eq(user)));
            for (Row r : rows) {
                if (!withinValidity(r, today)) {
                    continue;
                }
                String code = str(r, "companyCode");
                if (code == null || code.isBlank()) {
                    unrestricted[0] = true;
                } else {
                    companies.add(code);
                }
            }
        });
        return unrestricted[0] ? java.util.Collections.emptySet() : companies;
    }

    /**
     * Validity is filtered here rather than in the view's WHERE clause because
     * the view is also the administration UI's answer to "what does this person
     * have?", where an assignment that starts next month must still be visible.
     */
    private boolean withinValidity(Row r, LocalDate today) {
        LocalDate from = date(r, "validFrom");
        LocalDate to = date(r, "validTo");
        if (from != null && today.isBefore(from)) {
            return false;
        }
        return to == null || !today.isAfter(to);
    }

    private static String str(Row r, String key) {
        Object v = r.get(key);
        return v == null ? null : v.toString();
    }

    private static LocalDate date(Row r, String key) {
        Object v = r.get(key);
        if (v == null) {
            return null;
        }
        if (v instanceof LocalDate d) {
            return d;
        }
        try {
            return LocalDate.parse(v.toString());
        } catch (RuntimeException e) {
            return null;
        }
    }
}
