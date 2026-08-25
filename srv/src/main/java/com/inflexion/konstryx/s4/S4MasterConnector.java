package com.inflexion.konstryx.s4;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sap.cds.Row;
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
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Reads master data from the connected S/4 system into the KONSTRYX mirrors.
 *
 * Which objects are read, and from which service, comes from S4SyncConfig so
 * a tenant can enable, disable or repoint a feed without a redeploy. Where a
 * tenant has no configuration the built-in defaults are used and the report
 * says so.
 *
 * Mirrors are read-only to the client, so a row that already exists is
 * updated in place from S/4 rather than skipped: S/4 is the author of these
 * records and a local edit is not something to preserve.
 */
@Component
public class S4MasterConnector {

    private static final Logger log = LoggerFactory.getLogger(S4MasterConnector.class);

    private static final String E_CONFIG = "konstryx.admin.S4SyncConfig";
    private static final String E_MATERIAL = "konstryx.master.Material";
    private static final String E_VENDOR = "konstryx.master.Vendor";

    static final String MATERIAL = "MATERIAL";
    static final String VENDOR = "VENDOR";

    private static final String PRODUCT_SRV = "/sap/opu/odata/sap/API_PRODUCT_SRV";
    private static final String BP_SRV = "/sap/opu/odata/sap/API_BUSINESS_PARTNER";

    /**
     * Rows fetched per request. The run continues until S/4 returns a short
     * page, so the whole catalogue is read; SAFETY_LIMIT only stops a runaway
     * loop if a service ever pages without end.
     */
    private static final int PAGE = 500;
    private static final int SAFETY_LIMIT = 200_000;

    private final ObjectMapper mapper = new ObjectMapper();

    @Autowired
    private S4Connection connection;

    @Autowired
    private PersistenceService db;

    public boolean isConfigured() {
        return connection.isConfigured();
    }

    /** One configured feed. */
    private static final class Feed {
        final String objectType;
        final String service;
        final boolean fromConfig;

        Feed(String objectType, String service, boolean fromConfig) {
            this.objectType = objectType;
            this.service = service;
            this.fromConfig = fromConfig;
        }
    }

    public String sync() {
        if (!connection.isConfigured()) {
            return "No S/4 connection is configured. The ITS_S4 destination must "
                    + "resolve before master data can be read.";
        }

        StringBuilder report = new StringBuilder("Read from ")
                .append(connection.host())
                .append(connection.usesDestination()
                        ? " via the ITS_S4 destination" : " via local configuration")
                .append(".\n\n");

        List<Feed> feeds = feeds();
        boolean configured = feeds.stream().anyMatch(f -> f.fromConfig);
        report.append(configured
                ? "Feeds from S4SyncConfig:\n"
                : "No inbound feeds configured, using defaults:\n");

        for (Feed feed : feeds) {
            report.append("  ").append(run(feed)).append('\n');
        }
        return report.toString();
    }

    /**
     * The inbound feeds to run: whatever S4SyncConfig holds, or the built-in
     * defaults when it holds nothing. A configured row wins on service path so
     * a tenant on a different API version can repoint it.
     */
    private List<Feed> feeds() {
        Map<String, Feed> byType = new LinkedHashMap<>();
        for (Row config : db.run(Select.from(E_CONFIG))) {
            if (!"IN".equals(str(config.get("direction")))
                    || !Boolean.TRUE.equals(config.get("active"))) {
                continue;
            }
            String type = upper(str(config.get("objectType")));
            if (!MATERIAL.equals(type) && !VENDOR.equals(type)) {
                continue;
            }
            String service = str(config.get("service"));
            byType.put(type, new Feed(type,
                    isBlank(service) ? defaultService(type) : service, true));
        }
        if (byType.isEmpty()) {
            byType.put(MATERIAL, new Feed(MATERIAL, PRODUCT_SRV, false));
            byType.put(VENDOR, new Feed(VENDOR, BP_SRV, false));
        }
        return new ArrayList<>(byType.values());
    }

    private static String defaultService(String objectType) {
        return MATERIAL.equals(objectType) ? PRODUCT_SRV : BP_SRV;
    }

    private String run(Feed feed) {
        try {
            return MATERIAL.equals(feed.objectType)
                    ? syncMaterials(feed) : syncVendors(feed);
        } catch (Exception e) {
            log.warn("Master sync failed for {}: {}", feed.objectType, e.toString());
            return feed.objectType + ": failed (" + e.getClass().getSimpleName() + ")";
        }
    }

    // --------------------------------------------------------------- material

    private String syncMaterials(Feed feed) throws Exception {
        Map<String, String> descriptions = productDescriptions(feed.service);

        int read = 0, created = 0, updated = 0;
        boolean truncated = false;

        for (int skip = 0; skip < SAFETY_LIMIT; skip += PAGE) {
            String url = feed.service + "/A_Product?%24format=json&%24top=" + PAGE
                    + "&%24skip=" + skip
                    + "&%24select=Product,BaseUnit,ProductGroup,ProductType";
            S4Connection.S4Response response = connection.get(url);
            if (response.status != 200) {
                return feed.objectType + ": not available (" + response.status + ")";
            }
            List<JsonNode> page = rowsOf(response.body);
            if (page.isEmpty()) {
                break;
            }
            for (JsonNode product : page) {
                String code = text(product, "Product");
                if (code == null) {
                    continue;
                }
                read++;
                Map<String, Object> data = new HashMap<>();
                data.put("materialCode", code);
                data.put("description", descriptions.get(code));
                data.put("baseUoM", text(product, "BaseUnit"));
                data.put("materialGroup", text(product, "ProductGroup"));
                if (upsert(E_MATERIAL, "materialCode", code, data)) {
                    created++;
                } else {
                    updated++;
                }
            }
            if (page.size() < PAGE) {
                break;
            }
            if (skip + PAGE >= SAFETY_LIMIT) {
                truncated = true;
            }
        }
        return feed.objectType + " <- A_Product" + source(feed) + ": " + read
                + " read, " + created + " new, " + updated + " updated"
                + (truncated ? ". Stopped at the " + SAFETY_LIMIT
                        + "-row safety limit, so this is not the whole catalogue." : "");
    }

    /**
     * Product descriptions, keyed by product. They live in their own entity
     * rather than on the product, and English is taken where a product has
     * several languages.
     */
    private Map<String, String> productDescriptions(String service) {
        Map<String, String> byProduct = new HashMap<>();
        try {
            for (int skip = 0; skip < SAFETY_LIMIT; skip += PAGE) {
                String url = service + "/A_ProductDescription?%24format=json&%24top="
                        + PAGE + "&%24skip=" + skip
                        + "&%24select=Product,Language,ProductDescription";
                S4Connection.S4Response response = connection.get(url);
                if (response.status != 200) {
                    return byProduct;
                }
                List<JsonNode> page = rowsOf(response.body);
                if (page.isEmpty()) {
                    return byProduct;
                }
                for (JsonNode row : page) {
                    String product = text(row, "Product");
                    String description = text(row, "ProductDescription");
                    if (product == null || description == null) {
                        continue;
                    }
                    boolean english = "EN".equalsIgnoreCase(text(row, "Language"));
                    if (english || !byProduct.containsKey(product)) {
                        byProduct.put(product, description);
                    }
                }
                if (page.size() < PAGE) {
                    return byProduct;
                }
            }
        } catch (Exception e) {
            log.info("Product descriptions unavailable ({}); products will carry a "
                    + "code and no text", e.getClass().getSimpleName());
        }
        return byProduct;
    }

    // ----------------------------------------------------------------- vendor

    private String syncVendors(Feed feed) throws Exception {
        int read = 0, created = 0, updated = 0;
        boolean truncated = false;

        for (int skip = 0; skip < SAFETY_LIMIT; skip += PAGE) {
            String url = feed.service + "/A_Supplier?%24format=json&%24top=" + PAGE
                    + "&%24skip=" + skip
                    + "&%24select=Supplier,SupplierName,SupplierFullName";
            S4Connection.S4Response response = connection.get(url);
            if (response.status != 200) {
                return feed.objectType + ": not available (" + response.status + ")";
            }
            List<JsonNode> page = rowsOf(response.body);
            if (page.isEmpty()) {
                break;
            }
            for (JsonNode supplier : page) {
                String bp = text(supplier, "Supplier");
                if (bp == null) {
                    continue;
                }
                read++;
                String name = text(supplier, "SupplierName");
                Map<String, Object> data = new HashMap<>();
                data.put("bpNumber", bp);
                data.put("name", name != null ? name : text(supplier, "SupplierFullName"));
                if (upsert(E_VENDOR, "bpNumber", bp, data)) {
                    created++;
                } else {
                    updated++;
                }
            }
            if (page.size() < PAGE) {
                break;
            }
            if (skip + PAGE >= SAFETY_LIMIT) {
                truncated = true;
            }
        }
        return feed.objectType + " <- A_Supplier" + source(feed) + ": " + read
                + " read, " + created + " new, " + updated + " updated"
                + (truncated ? ". Stopped at the " + SAFETY_LIMIT
                        + "-row safety limit, so this is not the whole list." : "");
    }

    // ---------------------------------------------------------------- helpers

    /** Inserts or updates one mirror row. Returns true when it was created. */
    private boolean upsert(String entity, String keyField, String keyValue,
                           Map<String, Object> data) {
        data.put("s4Key", keyValue);
        data.put("s4System", systemId());
        data.put("lastSyncedAt", Instant.now());
        data.put("syncStatus", "OK");

        Row existing = db.run(Select.from(entity)
                .where(e -> e.get(keyField).eq(keyValue))).first().orElse(null);
        if (existing == null) {
            data.put("ID", UUID.randomUUID().toString());
            db.run(Insert.into(entity).entry(data));
            return true;
        }
        String id = str(existing.get("ID"));
        db.run(Update.entity(entity).data(data).where(e -> e.get("ID").eq(id)));
        return false;
    }

    private static String source(Feed feed) {
        return feed.fromConfig ? " (configured)" : " (default)";
    }

    /** V2 answers under d.results, V4 under value. Accept either. */
    private List<JsonNode> rowsOf(String body) throws Exception {
        JsonNode root = mapper.readTree(body);
        JsonNode v4 = root.path("value");
        JsonNode array = v4.isArray() ? v4 : root.path("d").path("results");
        List<JsonNode> rows = new ArrayList<>();
        if (array.isArray()) {
            array.forEach(rows::add);
        }
        return rows;
    }

    private static String text(JsonNode row, String field) {
        String value = row.path(field).asText(null);
        return isBlank(value) ? null : value.trim();
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

    private static String upper(String s) {
        return s == null ? null : s.toUpperCase();
    }

    private static boolean isBlank(String s) {
        return s == null || s.isBlank();
    }

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }
}
