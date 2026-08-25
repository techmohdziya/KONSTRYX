package com.inflexion.konstryx.s4;

import com.fasterxml.jackson.databind.JsonNode;
import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.runtime.CdsRuntime;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.util.LinkedHashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * A read-only look at what an S/4 service actually exposes, run on demand.
 *
 * The requisition connector was written against SAP's documented shape for
 * `API_PURCHASEREQUISITION_2` without ever meeting the tenant: the service
 * path, the entity-set names and the navigation properties are all informed
 * assumptions. This resolves them from the tenant's own `$metadata`.
 *
 * **Why a startup probe and not an OData action.** The credentials that work
 * live in the `ITS_S4` destination, on the deployed app — not on a developer's
 * machine, which is the entire point of the destination. Reaching a new OData
 * action there would need an XSUAA token; setting an environment variable and
 * reading the log does not. Turn it on, restart, read, turn it off:
 *
 *     cf set-env konstryx-srv S4_PROBE requisition
 *     cf restart konstryx-srv
 *     cf logs konstryx-srv --recent | grep S4Probe
 *     cf unset-env konstryx-srv S4_PROBE
 *
 * **It only ever reads.** A GET of `$metadata` creates no business document.
 * Nothing here posts, and nothing here logs a credential — the destination
 * supplies the authentication and this class never sees it.
 */
@Component
public class S4Probe {

    private static final Logger log = LoggerFactory.getLogger(S4Probe.class);

    private static final Pattern ENTITY_SET =
            Pattern.compile("<EntitySet\\s+Name=\"([^\"]+)\"");
    private static final Pattern NAV_PROPERTY =
            Pattern.compile("<NavigationProperty\\s+Name=\"([^\"]+)\"");
    private static final Pattern ENTITY_TYPE =
            Pattern.compile("<EntityType\\s+Name=\"([^\"]+)\"");

    @Autowired
    private S4Connection connection;

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    @EventListener(ApplicationReadyEvent.class)
    public void probeIfAsked() {
        String what = System.getenv("S4_PROBE");
        if (what == null || what.isBlank()) {
            return;
        }
        if (!connection.isConfigured()) {
            log.warn("S4_PROBE={} but no S/4 connection is configured — nothing to probe.", what);
            return;
        }
        String service = System.getenv().getOrDefault("S4_PR_SERVICE",
                "/sap/opu/odata4/sap/api_purchaserequisition_2/srvd_a2x/sap/purchaserequisition/0001");
        if ("requisition".equalsIgnoreCase(what)) {
            probe(service);
        } else if ("org".equalsIgnoreCase(what)) {
            probeOrg(service);
        } else if ("data".equalsIgnoreCase(what)) {
            // Braces, not an expression lambda: run() is overloaded for
            // Consumer and Function, and a one-expression body is ambiguous.
            runtime.requestContext().privilegedUser().run(rc -> { probeData(); });
        } else {
            // Anything else is treated as a literal service path, so a wrong
            // guess above can be corrected without another build.
            probe(what);
        }
    }

    /**
     * The org values this tenant actually uses, read off requisitions it has
     * already raised.
     *
     * Plant, purchasing organisation and purchasing group are not things to
     * reason about — SAP standard content ships several plausible sets and only
     * the tenant knows which one is configured. This is the same method that
     * produced the project connector's known-good defaults: look at what is
     * already there rather than pick a number that looks right.
     */
    private void probeOrg(String servicePath) {
        String url = servicePath + "/PurchaseReqnItem?%24top=25&%24select="
                + "Plant,PurchasingOrganization,PurchasingGroup,PurReqnItemCurrency,CompanyCode";
        log.info("S4Probe: GET {} on {}", url, connection.host());
        try {
            S4Connection.S4Response response = connection.get(url);
            if (response.status != 200) {
                log.warn("S4Probe: org read returned {} — {}", response.status,
                        excerpt(response.body));
                return;
            }
            // Distinct combinations, not every row: twenty-five items from one
            // requisition would otherwise print the same values twenty-five
            // times and say nothing about which are in use across the tenant.
            // Parsed properly here, unlike $metadata above — this is JSON we
            // asked for and a field we intend to read, not a diagnostic
            // scrape of a document that might be malformed.
            Set<String> combos = new LinkedHashSet<>();
            for (JsonNode row : new ObjectMapper().readTree(response.body).path("value")) {
                combos.add(String.format(
                        "plant=%s  purchOrg=%s  purchGroup=%s  currency=%s  coCode=%s",
                        row.path("Plant").asText("-"),
                        row.path("PurchasingOrganization").asText("-"),
                        row.path("PurchasingGroup").asText("-"),
                        row.path("PurReqnItemCurrency").asText("-"),
                        row.path("CompanyCode").asText("-")));
            }
            if (combos.isEmpty()) {
                log.warn("S4Probe: no requisition items on this tenant to read org values "
                        + "from. Body starts: {}", excerpt(response.body));
                return;
            }
            log.info("S4Probe: org combinations in use ({}):", combos.size());
            for (String combo : combos) {
                log.info("S4Probe:   {}", combo);
            }
        } catch (Exception e) {
            log.warn("S4Probe: org read failed: {}", e.toString());
        }
    }

    /**
     * What the tenant actually holds, by row count.
     *
     * A deployed tenant has no other way to answer "is there any data?" — the
     * UI needs a login, OData needs a token, and the content-deployment log
     * lines have usually rolled out of the buffer by the time anyone asks.
     * Counting through the persistence service sidesteps all three, and
     * distinguishes the two cases that look identical in a browser: no rows,
     * versus rows the signed-in user has no permission to see.
     */
    private void probeData() {
        for (String entity : new String[] {
                "konstryx.admin.Company", "konstryx.master.ResourceNode",
                "konstryx.master.Material", "konstryx.master.RateMaster",
                "konstryx.prj.Project", "konstryx.prj.WBSElement",
                "konstryx.prj.BOQItem", "konstryx.bud.Budget",
                "konstryx.wf.ResourceRequest", "konstryx.wf.ResourceRequestLine",
                "konstryx.mat.PurchaseRequisition",
                "konstryx.auth.Persona", "konstryx.auth.PersonaPermission",
                "konstryx.auth.UserAssignment", "konstryx.sys.ContentPack" }) {
            try {
                int n = 0;
                for (Row ignored : db.run(Select.from(entity))) {
                    n++;
                }
                log.info("S4Probe: {} rows in {}", n, entity);
            } catch (Exception e) {
                log.warn("S4Probe: could not count {}: {}", entity, e.toString());
            }
        }
        try {
            for (Row pack : db.run(Select.from("konstryx.sys.ContentPack"))) {
                log.info("S4Probe: pack {} {} — {} inserted",
                        pack.get("packId"), pack.get("version"), pack.get("rowsInserted"));
            }
        } catch (Exception e) {
            log.warn("S4Probe: could not list packs: {}", e.toString());
        }
    }

    private void probe(String servicePath) {
        String url = servicePath + "/$metadata";
        log.info("S4Probe: GET {} on {}", url, connection.host());
        try {
            S4Connection.S4Response response = connection.get(url, "application/xml");
            if (response.status != 200) {
                // A 404 means the path is wrong, which is the most likely
                // single mistake; a 403 means the communication arrangement
                // does not cover this user. They need different fixes, so the
                // status is reported rather than flattened into "failed".
                log.warn("S4Probe: {} returned {} — body starts: {}", url, response.status,
                        excerpt(response.body));
                return;
            }
            log.info("S4Probe: {} OK. Entity sets: {}", url,
                    String.join(", ", matches(ENTITY_SET, response.body, 40)));
            log.info("S4Probe: navigation properties: {}",
                    String.join(", ", matches(NAV_PROPERTY, response.body, 40)));
            // The properties are where the remaining guesswork lives — the
            // connector names about a dozen of them and every one was taken
            // from documentation rather than from this tenant.
            //
            // Discover the EntityType names rather than assume them. An
            // EntitySet and its EntityType do not share a name in these
            // services, and guessing the suffix once already cost a
            // deployment: every lookup came back "EntityType not found".
            Set<String> types = matches(ENTITY_TYPE, response.body, 40);
            log.info("S4Probe: entity types: {}", String.join(", ", types));
            for (String type : types) {
                log.info("S4Probe: {} properties: {}", type,
                        String.join(", ", propertiesOf(response.body, type)));
            }
        } catch (Exception e) {
            log.warn("S4Probe: {} failed: {}", url, e.toString());
        }
    }

    /**
     * The property names declared on one EntityType. Parsed with a regex
     * rather than an XML parser on purpose: this is a diagnostic that must
     * survive a malformed or unexpected document and still say something
     * useful, not a consumer of the model.
     */
    private static Set<String> propertiesOf(String body, String typeName) {
        Set<String> found = new LinkedHashSet<>();
        if (body == null) {
            return found;
        }
        Matcher start = Pattern.compile(
                "<EntityType\s+Name=\"" + Pattern.quote(typeName) + "\"").matcher(body);
        if (!start.find()) {
            found.add("(EntityType not found)");
            return found;
        }
        int from = start.end();
        int to = body.indexOf("</EntityType>", from);
        String block = to < 0 ? body.substring(from) : body.substring(from, to);
        Matcher m = Pattern.compile("<Property\s+Name=\"([^\"]+)\"").matcher(block);
        while (m.find() && found.size() < 60) {
            found.add(m.group(1));
        }
        return found;
    }

    /** Distinct matches, capped — a full $metadata is far too big for a log line. */
    private static Set<String> matches(Pattern pattern, String body, int limit) {
        Set<String> found = new LinkedHashSet<>();
        if (body == null) {
            return found;
        }
        Matcher m = pattern.matcher(body);
        while (m.find() && found.size() < limit) {
            found.add(m.group(1));
        }
        return found;
    }

    private static String excerpt(String body) {
        if (body == null) {
            return "(empty)";
        }
        String flat = body.replaceAll("\\s+", " ").strip();
        return flat.length() <= 300 ? flat : flat.substring(0, 300) + "…";
    }
}
