package com.inflexion.konstryx.content;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.runtime.CdsRuntime;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.time.Instant;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.UUID;

/**
 * Applies delivered content packs to the tenant database.
 *
 * The rule this exists to enforce: content a client may edit never ships in
 * db/data, because HDI re-imports those rows on every deployment and would
 * revert the client's changes. Packs are applied once per version,
 * insert-if-missing, and never update a row that already exists.
 *
 * An upgrade that adds rows ships a new pack version. Rows the client has since
 * edited keep their edits; only genuinely new rows arrive.
 *
 * Runs at startup, which is correct for the current one-deployment-per-client
 * model. Under shared multitenancy this would move to the tenant subscription
 * callback so each new tenant gets the packs on provisioning.
 */
@Component
public class ContentDeploymentService {

    private static final Logger log = LoggerFactory.getLogger(ContentDeploymentService.class);

    private static final String E_PACK = "konstryx.sys.ContentPack";
    /**
     * Packs ship inside the jar. The filesystem location is also scanned so an
     * operator can apply a corrective pack to a running landscape without
     * rebuilding and redeploying the service.
     */
    private static final String[] CONTENT_LOCATIONS = {
            "classpath:content/*.json",
            "file:./content/*.json"
    };

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    private final ObjectMapper mapper = new ObjectMapper();

    @EventListener(ApplicationReadyEvent.class)
    public void applyDeliveredContent() {
        applyAll();
    }

    /** Returns a human-readable summary; also invoked by the admin action. */
    public String applyAll() {
        StringBuilder summary = new StringBuilder();
        try {
            PathMatchingResourcePatternResolver resolver = new PathMatchingResourcePatternResolver();
            java.util.List<Resource> found = new java.util.ArrayList<>();
            for (String location : CONTENT_LOCATIONS) {
                try {
                    found.addAll(java.util.Arrays.asList(resolver.getResources(location)));
                } catch (Exception ignored) {
                    // a location that does not exist is normal, not an error
                }
            }
            // Apply in version order, not filename order. Sorting by filename
            // put number-ranges-v2.json ('-' sorts before '.') ahead of
            // number-ranges.json, so 1.0.1 applied before 1.0.0 and the base
            // pack then reported rows as pre-existing. Upgrades must replay in
            // the order they were released.
            found.sort(java.util.Comparator
                    .comparing((Resource r) -> packIdOf(r))
                    .thenComparing(r -> versionKeyOf(r)));
            Resource[] packs = found.toArray(new Resource[0]);
            if (packs.length == 0) {
                return "No content packs found.";
            }
            // Privileged: content deployment is a platform action and must not
            // depend on whichever user happens to trigger it.
            runtime.requestContext().privilegedUser().run(ctx -> {
                for (Resource pack : packs) {
                    try {
                        summary.append(applyPack(pack)).append('\n');
                    } catch (Exception e) {
                        log.error("Content pack {} failed to apply", pack.getFilename(), e);
                        summary.append(pack.getFilename()).append(": FAILED — ")
                               .append(e.getMessage()).append('\n');
                    }
                }
            });
        } catch (Exception e) {
            log.error("Could not scan for delivered content packs", e);
            return "Scan failed: " + e.getMessage();
        }
        return summary.toString().trim();
    }

    private String applyPack(Resource resource) throws Exception {
        JsonNode pack;
        try (InputStream in = resource.getInputStream()) {
            pack = mapper.readTree(in);
        }

        String packId = pack.path("packId").asText();
        String version = pack.path("version").asText();

        boolean alreadyApplied = db.run(Select.from(E_PACK)
                .where(p -> p.get("packId").eq(packId).and(p.get("version").eq(version))))
                .first().isPresent();

        if (alreadyApplied) {
            log.debug("Content pack {} {} already applied — skipping", packId, version);
            return packId + " " + version + ": already applied";
        }

        int inserted = 0;
        int skipped = 0;

        for (JsonNode item : pack.path("items")) {
            String entity = item.path("entity").asText();
            String naturalKey = item.path("naturalKey").asText();

            for (JsonNode row : item.path("rows")) {
                String keyValue = row.path(naturalKey).asText();

                boolean exists = db.run(Select.from(entity)
                        .where(e -> e.get(naturalKey).eq(keyValue)))
                        .first().isPresent();

                if (exists) {
                    skipped++;    // the client owns this row now — leave it alone
                    continue;
                }

                Map<String, Object> data = new HashMap<>();
                data.put("ID", UUID.randomUUID().toString());
                Iterator<Map.Entry<String, JsonNode>> fields = row.fields();
                while (fields.hasNext()) {
                    Map.Entry<String, JsonNode> field = fields.next();
                    data.put(field.getKey(), toJavaValue(field.getValue()));
                }
                db.run(Insert.into(entity).entry(data));
                inserted++;
            }
        }

        Map<String, Object> record = new HashMap<>();
        record.put("ID", UUID.randomUUID().toString());
        record.put("packId", packId);
        record.put("version", version);
        record.put("description", pack.path("description").asText());
        record.put("appliedAt", Instant.now());
        record.put("appliedBy", "system");
        record.put("rowsInserted", inserted);
        record.put("rowsSkipped", skipped);
        db.run(Insert.into(E_PACK).entry(record));

        log.info("Content pack {} {} applied: {} inserted, {} left untouched",
                packId, version, inserted, skipped);
        return packId + " " + version + ": " + inserted + " inserted, " + skipped + " left untouched";
    }

    private String packIdOf(Resource resource) {
        try (InputStream in = resource.getInputStream()) {
            return mapper.readTree(in).path("packId").asText("");
        } catch (Exception e) {
            return "";
        }
    }

    /** Zero-pads each numeric segment so 1.0.10 sorts after 1.0.9, not before it. */
    private String versionKeyOf(Resource resource) {
        String version;
        try (InputStream in = resource.getInputStream()) {
            version = mapper.readTree(in).path("version").asText("0");
        } catch (Exception e) {
            return "0";
        }
        StringBuilder key = new StringBuilder();
        for (String part : version.split("\\.")) {
            try {
                key.append(String.format("%06d", Integer.parseInt(part.trim())));
            } catch (NumberFormatException e) {
                key.append(part);
            }
            key.append('.');
        }
        return key.toString();
    }

    private Object toJavaValue(JsonNode node) {
        if (node.isBoolean()) {
            return node.asBoolean();
        }
        if (node.isInt() || node.isLong()) {
            return node.asLong();
        }
        if (node.isDouble() || node.isFloat() || node.isBigDecimal()) {
            return node.decimalValue();
        }
        if (node.isNull()) {
            return null;
        }
        return node.asText();
    }
}
