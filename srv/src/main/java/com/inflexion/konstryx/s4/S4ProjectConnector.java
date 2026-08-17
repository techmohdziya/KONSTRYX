package com.inflexion.konstryx.s4;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.persistence.PersistenceService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.Map;

/**
 * Pushes a KONSTRYX-mastered project to S/4 (D-17, SAP_COM_0308).
 *
 * The project header goes to API_ENTERPRISE_PROJECT_SRV v2, then each WBS
 * element as an EnterpriseProjectElement under it. Profile and org values are
 * tenant configuration — the defaults were read from the tenant's own
 * projects, not guessed — and can be overridden per environment (S4_PROJECT_
 * PROFILE / S4_COST_CENTER / S4_PROFIT_CENTER).
 *
 * The outcome is returned, never applied here: recording SENT or FAILED on the
 * project is ProjectHandler's job, so the manual recordSyncResult path and
 * this connector write the same status the same way.
 */
@Component
public class S4ProjectConnector {

    private static final Logger log = LoggerFactory.getLogger(S4ProjectConnector.class);

    private static final String SERVICE = "/sap/opu/odata/sap/API_ENTERPRISE_PROJECT_SRV;v=0002";
    private static final String E_WBS = "konstryx.prj.WBSElement";

    private final ObjectMapper mapper = new ObjectMapper();

    @Autowired
    private S4Connection connection;

    @Autowired
    private PersistenceService db;

    public boolean isConfigured() {
        return connection.isConfigured();
    }

    public static final class SyncOutcome {
        public final boolean success;
        public final String s4Key;
        public final String s4System;
        public final String message;

        SyncOutcome(boolean success, String s4Key, String s4System, String message) {
            this.success = success;
            this.s4Key = s4Key;
            this.s4System = s4System;
            this.message = message;
        }
    }

    public SyncOutcome push(Row project) {
        String code = str(project.get("code"));
        try {
            // S/4 project IDs are uppercase, max 24, no spaces. The KONSTRYX
            // code is the natural key; normalising rather than inventing keeps
            // the two systems' keys recognisably the same object.
            String s4Id = code.toUpperCase().replaceAll("[^A-Z0-9./-]", "-");
            if (s4Id.length() > 24) {
                s4Id = s4Id.substring(0, 24);
            }

            ObjectNode payload = mapper.createObjectNode();
            payload.put("Project", s4Id);
            payload.put("ProjectDescription", str(project.get("name")));
            payload.put("ProjectProfileCode", envOr("S4_PROJECT_PROFILE", "YP05"));
            payload.put("ResponsibleCostCenter", envOr("S4_COST_CENTER", "10001000"));
            payload.put("ProfitCenter", envOr("S4_PROFIT_CENTER", "10001000"));
            payload.put("EntProjectIsConfidential", false);
            putDate(payload, "ProjectStartDate", project.get("startDate"));
            putDate(payload, "ProjectEndDate", project.get("endDate"));

            S4Connection.S4Response response = connection.post(
                    SERVICE + "/A_EnterpriseProject?%24top=1",
                    SERVICE + "/A_EnterpriseProject",
                    mapper.writeValueAsString(payload));

            if (response.status != 201) {
                return new SyncOutcome(false, null, null,
                        "S/4 refused the project (" + response.status + "): "
                                + errorText(response.body));
            }
            JsonNode created = mapper.readTree(response.body).path("d");
            String projectUuid = created.path("ProjectUUID").asText(null);
            String s4Key = created.path("Project").asText(s4Id);

            int wbsSent = 0, wbsFailed = 0;
            StringBuilder wbsErrors = new StringBuilder();
            String projectId = str(project.get("ID"));
            for (Row wbs : db.run(Select.from(E_WBS)
                    .where(w -> w.get("project_ID").eq(projectId)))) {
                ObjectNode element = mapper.createObjectNode();
                String elementId = str(wbs.get("code")).toUpperCase()
                        .replaceAll("[^A-Z0-9./-]", "-");
                element.put("ProjectElement", elementId.length() > 24
                        ? elementId.substring(0, 24) : elementId);
                element.put("ProjectElementDescription", str(wbs.get("description")));
                element.put("ProjectUUID", projectUuid);

                S4Connection.S4Response wbsResponse = connection.post(
                        SERVICE + "/A_EnterpriseProject?%24top=1",
                        SERVICE + "/A_EnterpriseProjectElement",
                        mapper.writeValueAsString(element));
                if (wbsResponse.status == 201) {
                    wbsSent++;
                } else {
                    wbsFailed++;
                    if (wbsErrors.length() < 300) {
                        wbsErrors.append(" [").append(wbs.get("code")).append(": ")
                                .append(errorText(wbsResponse.body)).append("]");
                    }
                }
            }

            // A project whose WBS partly failed is SENT but says so: the header
            // exists in S/4 and repeating the whole push would duplicate it.
            String message = "Created in S/4 as " + s4Key
                    + " with " + wbsSent + " WBS element(s)"
                    + (wbsFailed == 0 ? "" : "; " + wbsFailed + " element(s) failed:"
                            + wbsErrors);
            return new SyncOutcome(true, s4Key, systemId(), message);

        } catch (Exception e) {
            log.warn("S/4 push failed for {}: {}", code, e.toString());
            return new SyncOutcome(false, null, null,
                    "Push failed: " + e.getMessage());
        }
    }

    // ----------------------------------------------------------------- helpers

    /**
     * The logical system recorded against a synced project, derived from the
     * configured host rather than named in source — which tenant this build
     * points at is deployment configuration, not a fact about the product.
     */
    private String systemId() {
        String host = connection.host();
        if (host == null || host.isBlank()) {
            return "S4";
        }
        String h = host.replaceFirst("^https?://", "");
        int dot = h.indexOf('.');
        return dot > 0 ? h.substring(0, dot) : h;
    }

    /** V2 JSON dates ride as /Date(epoch-millis)/. */
    private static void putDate(ObjectNode node, String field, Object value) {
        if (value == null) {
            return;
        }
        try {
            LocalDate date = value instanceof LocalDate d
                    ? d : LocalDate.parse(String.valueOf(value).substring(0, 10));
            node.put(field, "/Date(" + date.atStartOfDay(ZoneOffset.UTC)
                    .toInstant().toEpochMilli() + ")/");
        } catch (RuntimeException ignored) { }
    }

    private String errorText(String body) {
        try {
            JsonNode error = mapper.readTree(body).path("error").path("message").path("value");
            if (!error.isMissingNode()) {
                return error.asText();
            }
        } catch (Exception ignored) { }
        return body == null ? "?" : body.substring(0, Math.min(200, body.length()));
    }

    private static String envOr(String key, String fallback) {
        String value = System.getenv(key);
        return value == null || value.isBlank() ? fallback : value;
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }
}
