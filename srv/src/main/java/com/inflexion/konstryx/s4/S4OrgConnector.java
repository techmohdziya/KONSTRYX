package com.inflexion.konstryx.s4;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sap.cds.Row;
import com.sap.cds.ql.Delete;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.services.persistence.PersistenceService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Reads the connected S/4 system's organizational values and maps them onto
 * the KONSTRYX companies.
 *
 * **Why this exists at all.** KONSTRYX is multi-tenant, and plants, purchasing
 * organizations, profit centres and project profiles are configuration of each
 * customer's own S/4 system. There is no value that is correct for every
 * tenant, so none of them can be shipped: the content pack that seeded
 * my434396 carried values read off my401381, and S/4 refused a real project
 * push with "Profit Center 10001000 does not exist". The values were entirely
 * plausible. They simply belonged to a different system.
 *
 * Credentials come from the ITS_S4 destination, never from this build — see
 * {@link S4Connection}. That is what makes the same code correct on every
 * tenant: each subscriber's destination points at their own S/4.
 *
 * **Two kinds of evidence, kept apart.** A catalogue read (all company codes,
 * all plants) proves a value exists. A document read (what a live requisition
 * or project actually carries) proves a value *works*, and is the only source
 * that says which company code uses it — S/4's plant catalogue does not carry
 * that link. Both are recorded, and inUse marks the second kind, because when
 * the two disagree the document is the one to believe.
 *
 * **What it will not do.** It never invents a mapping. A KONSTRYX company with
 * no s4CoCode is reported as unmapped rather than guessed at from a name, and
 * an ambiguous value — three plants under one company code — is offered rather
 * than picked. Choosing between two real plants is a business decision, and
 * the last time this file held a guess it cost a live push.
 */
@Component
public class S4OrgConnector {

    private static final Logger log = LoggerFactory.getLogger(S4OrgConnector.class);

    private static final String E_ORG = "konstryx.admin.S4OrgValue";
    private static final String E_COMPANY = "konstryx.admin.Company";

    static final String COMPANY_CODE = "COMPANY_CODE";
    static final String PLANT = "PLANT";
    static final String PURCH_ORG = "PURCH_ORG";
    static final String PURCH_GROUP = "PURCH_GROUP";
    static final String PROFIT_CENTER = "PROFIT_CENTER";
    static final String COST_CENTER = "COST_CENTER";
    static final String PROJECT_PROFILE = "PROJECT_PROFILE";

    private static final String PROJECT_SRV =
            "/sap/opu/odata/sap/API_ENTERPRISE_PROJECT_SRV;v=0002";
    private static final String REQUISITION_SRV =
            "/sap/opu/odata4/sap/api_purchaserequisition_2/srvd_a2x/sap/purchaserequisition/0001";

    private final ObjectMapper mapper = new ObjectMapper();

    @Autowired
    private S4Connection connection;

    @Autowired
    private PersistenceService db;

    public boolean isConfigured() {
        return connection.isConfigured();
    }

    // ------------------------------------------------------------------ types

    /** One value read from S/4, before it is written. */
    private static final class OrgValue {
        final String kind, code, name, parentCode, ccy, source;
        final boolean inUse;

        OrgValue(String kind, String code, String name, String parentCode,
                 String ccy, String source, boolean inUse) {
            this.kind = kind;
            this.code = code;
            this.name = name;
            this.parentCode = parentCode;
            this.ccy = ccy;
            this.source = source;
            this.inUse = inUse;
        }

        String key() {
            return kind + "|" + code + "|" + (parentCode == null ? "" : parentCode);
        }
    }

    /**
     * A catalogue read to attempt. Several are tried because which APIs a
     * tenant has activated is a per-tenant decision — a scenario nobody
     * switched on answers 403 or 404, and that is information, not a failure.
     */
    private static final class Catalogue {
        final String kind, url, codeField, nameField, parentField, ccyField;

        Catalogue(String kind, String url, String codeField, String nameField,
                  String parentField, String ccyField) {
            this.kind = kind;
            this.url = url;
            this.codeField = codeField;
            this.nameField = nameField;
            this.parentField = parentField;
            this.ccyField = ccyField;
        }
    }

    private static final List<Catalogue> CATALOGUES = List.of(
            new Catalogue(COMPANY_CODE,
                    "/sap/opu/odata/sap/API_COMPANYCODE_SRV/A_CompanyCode"
                            + "?%24top=200&%24format=json",
                    "CompanyCode", "CompanyCodeName", null, "Currency"),
            new Catalogue(PLANT,
                    "/sap/opu/odata/sap/API_PLANT_SRV/A_Plant"
                            + "?%24top=500&%24format=json",
                    "Plant", "PlantName", null, null),
            new Catalogue(COST_CENTER,
                    "/sap/opu/odata/sap/API_COSTCENTER_SRV/A_CostCenter"
                            + "?%24top=500&%24format=json",
                    "CostCenter", "CostCenterName", "CompanyCode", null),
            new Catalogue(PROFIT_CENTER,
                    "/sap/opu/odata/sap/API_PROFITCENTER_SRV/A_ProfitCenter"
                            + "?%24top=500&%24format=json",
                    "ProfitCenter", "ProfitCenterName", null, null));

    // ------------------------------------------------------------------ public

    /**
     * Reads S/4, replaces the mirror, and fills what it safely can on each
     * company. Returns a report meant to be read by a person: which sources
     * answered, what was written, and — the part that matters — what could not
     * be decided and why.
     */
    public String sync() {
        if (!connection.isConfigured()) {
            return "No S/4 connection is configured. The ITS_S4 destination must "
                    + "resolve before organizational values can be read.";
        }

        StringBuilder report = new StringBuilder();
        report.append("Read from ").append(connection.host())
                .append(connection.usesDestination()
                        ? " via the ITS_S4 destination" : " via local configuration")
                .append(".\n\n");

        Map<String, OrgValue> values = new LinkedHashMap<>();

        report.append("Catalogues:\n");
        for (Catalogue catalogue : CATALOGUES) {
            report.append("  ").append(readCatalogue(catalogue, values)).append('\n');
        }

        report.append("\nIn use on live documents:\n");
        report.append("  ").append(readRequisitionUsage(values)).append('\n');
        report.append("  ").append(readProjectUsage(values)).append('\n');

        if (values.isEmpty()) {
            return report.append("\nNothing was read, so nothing was changed. The "
                    + "existing organizational values are untouched.").toString();
        }

        int written = replaceMirror(values.values());
        report.append("\nMirror: ").append(written)
                .append(" organizational value(s) recorded.\n");

        report.append('\n').append(applyToCompanies(values.values()));
        log.info("S4OrgConnector: org sync complete, {} value(s) mirrored", written);
        return report.toString();
    }

    // ----------------------------------------------------------------- reading

    private String readCatalogue(Catalogue catalogue, Map<String, OrgValue> into) {
        String label = catalogue.kind + " <- " + servicePartOf(catalogue.url);
        try {
            S4Connection.S4Response response = connection.get(catalogue.url);
            if (response.status != 200) {
                // Not an error worth failing over. A tenant that has not
                // activated a scenario says so with a 403 or a 404, and the
                // document reads below still produce the values that matter.
                return label + ": not available (" + response.status + ")";
            }
            int before = into.size();
            for (JsonNode row : rowsOf(response.body)) {
                String code = text(row, catalogue.codeField);
                if (code == null) {
                    continue;
                }
                add(into, new OrgValue(catalogue.kind, code,
                        text(row, catalogue.nameField),
                        text(row, catalogue.parentField),
                        text(row, catalogue.ccyField),
                        servicePartOf(catalogue.url), false));
            }
            return label + ": " + (into.size() - before) + " value(s)";
        } catch (Exception e) {
            return label + ": failed (" + e.getClass().getSimpleName() + ")";
        }
    }

    /**
     * What live requisitions actually carry. This is the only source that ties
     * a plant, a purchasing organization and a purchasing group to a company
     * code, and the only proof that the combination is accepted for a write.
     */
    private String readRequisitionUsage(Map<String, OrgValue> into) {
        String url = REQUISITION_SRV + "/PurchaseReqnItem?%24top=200&%24select="
                + "Plant,PurchasingOrganization,PurchasingGroup,"
                + "PurReqnItemCurrency,CompanyCode";
        String label = "purchase requisitions";
        try {
            S4Connection.S4Response response = connection.get(url);
            if (response.status != 200) {
                return label + ": not available (" + response.status + ")";
            }
            int before = into.size();
            int rows = 0;
            for (JsonNode row : rowsOf(response.body)) {
                rows++;
                String coCode = text(row, "CompanyCode");
                String ccy = text(row, "PurReqnItemCurrency");
                addUsed(into, PLANT, text(row, "Plant"), coCode, ccy, label);
                addUsed(into, PURCH_ORG, text(row, "PurchasingOrganization"),
                        coCode, null, label);
                addUsed(into, PURCH_GROUP, text(row, "PurchasingGroup"),
                        coCode, null, label);
            }
            if (rows == 0) {
                return label + ": none on this tenant, so nothing to learn from them";
            }
            return label + ": " + rows + " item(s) read, "
                    + (into.size() - before) + " value(s) in use";
        } catch (Exception e) {
            return label + ": failed (" + e.getClass().getSimpleName() + ")";
        }
    }

    /**
     * What live projects carry. The project profile has no catalogue API at
     * all, so an existing project is the only place it can be read from —
     * which is also why a tenant with no projects yet cannot have one derived.
     */
    private String readProjectUsage(Map<String, OrgValue> into) {
        String url = PROJECT_SRV + "/A_EnterpriseProject?%24top=200&%24format=json";
        String label = "enterprise projects";
        try {
            S4Connection.S4Response response = connection.get(url);
            if (response.status != 200) {
                return label + ": not available (" + response.status + ")";
            }
            int before = into.size();
            int rows = 0;
            for (JsonNode row : rowsOf(response.body)) {
                rows++;
                String coCode = text(row, "CompanyCode");
                String ccy = text(row, "ProjectCurrency");
                addUsed(into, PROJECT_PROFILE, text(row, "ProjectProfileCode"),
                        coCode, null, label);
                addUsed(into, PROFIT_CENTER, text(row, "ProfitCenter"),
                        coCode, null, label);
                addUsed(into, COST_CENTER, text(row, "ResponsibleCostCenter"),
                        coCode, ccy, label);
            }
            if (rows == 0) {
                return label + ": none on this tenant, so no project profile can be read";
            }
            return label + ": " + rows + " project(s) read, "
                    + (into.size() - before) + " value(s) in use";
        } catch (Exception e) {
            return label + ": failed (" + e.getClass().getSimpleName() + ")";
        }
    }

    // ----------------------------------------------------------------- writing

    /**
     * The mirror is replaced wholesale rather than merged. It is a picture of
     * what S/4 holds now, and a value deleted there must disappear here too —
     * a stale plant left behind is exactly the kind of plausible-but-wrong
     * value this whole class exists to eliminate.
     */
    private int replaceMirror(Iterable<OrgValue> values) {
        db.run(Delete.from(E_ORG));
        List<Map<String, Object>> rows = new ArrayList<>();
        Instant now = Instant.now();
        String system = systemId();
        for (OrgValue value : values) {
            Map<String, Object> row = new HashMap<>();
            row.put("ID", UUID.randomUUID().toString());
            row.put("kind", value.kind);
            row.put("code", value.code);
            row.put("name", value.name);
            row.put("parentCode", value.parentCode);
            row.put("ccy", value.ccy);
            row.put("source", value.source);
            row.put("inUse", value.inUse);
            row.put("s4System", system);
            row.put("readAt", now);
            rows.add(row);
        }
        if (!rows.isEmpty()) {
            db.run(Insert.into(E_ORG).entries(rows));
        }
        return rows.size();
    }

    /**
     * Fills each company from what S/4 answered.
     *
     * Two rules, and both are deliberate:
     *
     *  - A blank field is filled when exactly one value fits. Ambiguity is
     *    reported, never resolved by picking the first — three plants under one
     *    company code is a business choice.
     *  - A field that already holds a value is left alone *unless* S/4 has
     *    never heard of that value, which is precisely the "Profit Center
     *    10001000 does not exist" case. Overwriting a valid choice would
     *    silently undo an administrator's decision; leaving an invalid one
     *    would keep the push broken.
     */
    private String applyToCompanies(Iterable<OrgValue> values) {
        StringBuilder report = new StringBuilder("Companies:\n");
        for (Row company : db.run(Select.from(E_COMPANY))) {
            String code = str(company.get("code"));
            String coCode = str(company.get("s4CoCode"));
            if (isBlank(coCode)) {
                report.append("  ").append(code)
                        .append(": no S/4 company code assigned, so nothing can be "
                                + "read for it. Assign one from the ")
                        .append(count(values, COMPANY_CODE))
                        .append(" company code(s) now mirrored.\n");
                continue;
            }

            Map<String, Object> update = new LinkedHashMap<>();
            List<String> notes = new ArrayList<>();
            apply(values, PLANT, coCode, company, "defaultPlant", update, notes);
            apply(values, PURCH_ORG, coCode, company, "purchOrg", update, notes);
            apply(values, PURCH_GROUP, coCode, company, "purchGroup", update, notes);
            apply(values, PROFIT_CENTER, coCode, company, "profitCtr", update, notes);
            apply(values, COST_CENTER, coCode, company, "costCtr", update, notes);
            apply(values, PROJECT_PROFILE, coCode, company, "projectProfile", update, notes);
            applyCurrency(values, coCode, company, update, notes);

            if (!update.isEmpty()) {
                String id = str(company.get("ID"));
                db.run(Update.entity(E_COMPANY).data(update)
                        .where(c -> c.get("ID").eq(id)));
            }
            report.append("  ").append(code).append(" (").append(coCode).append("): ")
                    .append(notes.isEmpty() ? "already matches S/4" : String.join("; ", notes))
                    .append('\n');
        }
        return report.toString();
    }

    private void apply(Iterable<OrgValue> values, String kind, String coCode,
                       Row company, String field, Map<String, Object> update,
                       List<String> notes) {
        List<OrgValue> fitting = fitting(values, kind, coCode);
        String current = str(company.get(field));

        if (fitting.isEmpty()) {
            if (isBlank(current)) {
                notes.add(field + " still empty (S/4 offered none)");
            }
            return;
        }
        if (!isBlank(current)) {
            boolean known = false;
            boolean observed = false;
            for (OrgValue value : fitting) {
                if (current.equals(value.code)) {
                    known = true;
                }
                if (value.inUse) {
                    observed = true;
                }
            }
            if (known) {
                return;
            }
            // Only observed values can condemn one: a catalogue this tenant
            // never activated proves nothing about what does not exist.
            if (!observed) {
                return;
            }
            notes.add(field + " was " + current + ", which S/4 does not use here");
        }
        if (fitting.size() > 1) {
            notes.add(field + " needs a choice: " + codesOf(fitting));
            return;
        }
        OrgValue only = fitting.get(0);
        update.put(field, only.code);
        notes.add(field + " = " + only.code
                + (only.inUse ? " (in use)" : " (from the catalogue)"));
    }

    /**
     * Currency comes from the company code itself, which is what "company
     * currency" means — not from whatever a document happened to be raised in.
     */
    private void applyCurrency(Iterable<OrgValue> values, String coCode, Row company,
                               Map<String, Object> update, List<String> notes) {
        String current = str(company.get("ccy_code"));
        String fromS4 = null;
        for (OrgValue value : values) {
            if (COMPANY_CODE.equals(value.kind) && coCode.equals(value.code)
                    && !isBlank(value.ccy)) {
                fromS4 = value.ccy;
                break;
            }
        }
        if (fromS4 == null) {
            return;
        }
        if (isBlank(current)) {
            update.put("ccy_code", fromS4);
            notes.add("currency = " + fromS4);
        } else if (!fromS4.equals(current)) {
            update.put("ccy_code", fromS4);
            notes.add("currency was " + current + ", S/4 says " + fromS4);
        }
    }

    // ----------------------------------------------------------------- helpers

    /**
     * The values of one kind that could serve this company code: those S/4
     * scoped to it, and — only when none are — those it left unscoped. A
     * catalogue of every plant in the system says nothing about which company
     * uses them, so an unscoped value is a candidate, not an answer.
     */
    private static List<OrgValue> fitting(Iterable<OrgValue> values, String kind,
                                          String coCode) {
        List<OrgValue> scoped = new ArrayList<>();
        List<OrgValue> unscoped = new ArrayList<>();
        for (OrgValue value : values) {
            if (!kind.equals(value.kind)) {
                continue;
            }
            if (coCode.equals(value.parentCode)) {
                scoped.add(value);
            } else if (isBlank(value.parentCode)) {
                unscoped.add(value);
            }
        }
        return scoped.isEmpty() ? unscoped : scoped;
    }

    private static void add(Map<String, OrgValue> into, OrgValue value) {
        OrgValue existing = into.get(value.key());
        // A value seen in use outranks the same value from a catalogue: it
        // carries the proof, and usually the company code too.
        if (existing == null || (value.inUse && !existing.inUse)) {
            into.put(value.key(), value);
        }
    }

    private static void addUsed(Map<String, OrgValue> into, String kind, String code,
                                String parentCode, String ccy, String source) {
        if (isBlank(code)) {
            return;
        }
        add(into, new OrgValue(kind, code, null, parentCode, ccy,
                "in use on " + source, true));
    }

    /** V4 answers under value, V2 under d.results. Accept either. */
    private Iterable<JsonNode> rowsOf(String body) throws Exception {
        JsonNode root = mapper.readTree(body);
        JsonNode v4 = root.path("value");
        if (v4.isArray()) {
            return v4;
        }
        JsonNode v2 = root.path("d").path("results");
        return v2.isArray() ? v2 : List.of();
    }

    private static String text(JsonNode row, String field) {
        if (field == null) {
            return null;
        }
        String value = row.path(field).asText(null);
        return isBlank(value) ? null : value.trim();
    }

    private static String codesOf(List<OrgValue> values) {
        Set<String> codes = new LinkedHashSet<>();
        for (OrgValue value : values) {
            codes.add(value.code);
        }
        return String.join(", ", codes);
    }

    private static long count(Iterable<OrgValue> values, String kind) {
        long n = 0;
        for (OrgValue value : values) {
            if (kind.equals(value.kind)) {
                n++;
            }
        }
        return n;
    }

    /** The service name out of a URL, for a report a person has to read. */
    private static String servicePartOf(String url) {
        String path = url.split("\\?")[0];
        String[] parts = path.split("/");
        for (int i = parts.length - 1; i >= 0; i--) {
            if (parts[i].startsWith("API_")) {
                return parts[i].split(";")[0];
            }
        }
        return parts.length > 0 ? parts[parts.length - 1] : url;
    }

    private String systemId() {
        String host = connection.host();
        if (isBlank(host)) {
            return "S4";
        }
        String h = host.replaceFirst("^https?://", "");
        int dot = h.indexOf('.');
        return dot > 0 ? h.substring(0, dot) : h;
    }

    private static boolean isBlank(String s) { return s == null || s.isBlank(); }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }
}
