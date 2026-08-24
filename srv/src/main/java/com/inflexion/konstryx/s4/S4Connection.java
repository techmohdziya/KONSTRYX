package com.inflexion.konstryx.s4;

import com.sap.cloud.sdk.cloudplatform.connectivity.DestinationAccessor;
import com.sap.cloud.sdk.cloudplatform.connectivity.Header;
import com.sap.cloud.sdk.cloudplatform.connectivity.HttpDestination;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.CookieManager;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/**
 * The S/4HANA Public Cloud connection.
 *
 * **Deployed, credentials come from the BTP destination service** — destination
 * `ITS_S4` by default, overridable with `S4_DESTINATION`. The destination holds
 * the URL and the authentication, the Cloud SDK resolves it per request, and
 * nothing in this repository or this process ever holds a password. That is the
 * whole point of the seam: rotating the communication user is a change in the
 * BTP cockpit, not a redeploy.
 *
 * **Locally, it falls back to `S4_HOST` / `S4_USER` / `S4_PASSWORD`** from the
 * environment or the gitignored `./.env`, because there is no destination
 * service on a developer's machine. The fallback is a convenience, never a
 * production path — if a destination resolves, it wins.
 *
 * Callers get requests executed, not credentials. Neither connector above this
 * class can see how the connection was authenticated, and neither needs to.
 *
 * OData writes need a CSRF token fetched over the same session, so the client
 * carries a cookie store and the token is fetched per write. That holds for
 * both the V2 project API and the V4 requisition API.
 */
@Component
public class S4Connection {

    private static final Logger log = LoggerFactory.getLogger(S4Connection.class);

    /** The destination Ziya named for S/4. Override per environment, do not edit. */
    private static final String DEFAULT_DESTINATION = "ITS_S4";

    private final HttpClient http = HttpClient.newBuilder()
            .cookieHandler(new CookieManager())
            .connectTimeout(Duration.ofSeconds(20))
            .build();

    /**
     * Set when a destination resolves. Re-read on every request rather than
     * cached as a URL and a header, so a destination edited in the cockpit —
     * or an OAuth token that has expired — takes effect without a restart.
     */
    private String destinationName;

    // The local fallback. Null whenever a destination is in use.
    private String host;
    private String basicAuth;

    private boolean resolved;

    /**
     * Resolve at startup, not on first use. Which tenant a running instance is
     * pointed at — and whether it got there through a destination or through
     * someone's .env — is the first question asked when a sync misbehaves, and
     * a lazily-resolved connection answers it only after something has already
     * gone wrong. No network call is involved: a destination lookup without a
     * bound service fails immediately.
     */
    @PostConstruct
    void announce() {
        isConfigured();
    }

    /** True when a tenant is reachable; false leaves every sync queued. */
    public synchronized boolean isConfigured() {
        if (!resolved) {
            resolve();
        }
        return destinationName != null || (host != null && basicAuth != null);
    }

    /** Where this build points, for stamping `s4System` on a synced record. */
    public String host() {
        if (!isConfigured()) {
            return null;
        }
        if (destinationName != null) {
            try {
                return destination().getUri().toString().replaceAll("/+$", "");
            } catch (RuntimeException e) {
                // Resolved once at startup, gone now. Report it rather than
                // returning a stale URL that would mislabel the record.
                log.warn("Destination {} no longer resolves: {}", destinationName, e.toString());
                return null;
            }
        }
        return host;
    }

    /** True when the connection runs through the destination service. */
    public boolean usesDestination() {
        isConfigured();
        return destinationName != null;
    }

    private synchronized void resolve() {
        resolved = true;
        String name = envOr("S4_DESTINATION", DEFAULT_DESTINATION);
        try {
            HttpDestination d = DestinationAccessor.getDestination(name).asHttp();
            this.destinationName = name;
            log.info("S/4 connection uses destination {} -> {}", name, d.getUri());
            return;
        } catch (RuntimeException | LinkageError e) {
            // Expected on a developer machine: no destination service bound.
            // Not expected in Cloud Foundry, so say which name failed and why —
            // a silent fall through to an unset local variable would look
            // exactly like "no tenant configured".
            //
            // LinkageError is caught deliberately, and it is not defensive
            // padding. The Cloud SDK's destination loader drags in its own
            // security artifacts, and a version disagreement there surfaces as
            // NoSuchMethodError from inside the SDK — an Error, not an
            // Exception. Reaching S/4 is optional infrastructure: a classpath
            // problem in it must degrade this connection to unconfigured, not
            // take the whole service down with it (I-47).
            log.info("Destination {} did not resolve ({}); falling back to the local "
                    + "environment", name, e.getClass().getSimpleName());
        }
        resolveLocal();
    }

    private void resolveLocal() {
        Map<String, String> env = new HashMap<>(System.getenv());
        if (!env.containsKey("S4_HOST")) {
            // Local convenience: the gitignored .env two levels up from srv/.
            for (Path candidate : new Path[] { Path.of(".env"), Path.of("../.env") }) {
                if (Files.exists(candidate)) {
                    try {
                        for (String line : Files.readAllLines(candidate, StandardCharsets.UTF_8)) {
                            line = line.strip();
                            if (line.isEmpty() || line.startsWith("#") || !line.contains("=")) {
                                continue;
                            }
                            int eq = line.indexOf('=');
                            env.putIfAbsent(line.substring(0, eq).strip(),
                                    line.substring(eq + 1).strip());
                        }
                    } catch (IOException e) {
                        log.warn("Could not read {}: {}", candidate, e.getMessage());
                    }
                    break;
                }
            }
        }
        String h = env.get("S4_HOST");
        String user = env.get("S4_USER");
        String password = env.get("S4_PASSWORD");
        if (h == null || h.isBlank() || user == null || user.isBlank()
                || password == null || password.isBlank()) {
            log.info("S/4 connection not configured — outbound sync stays queued");
            return;
        }
        this.host = h.replaceAll("/+$", "");
        this.basicAuth = "Basic " + Base64.getEncoder()
                .encodeToString((user + ":" + password).getBytes(StandardCharsets.UTF_8));
        log.info("S/4 connection configured locally for {}", this.host);
    }

    private HttpDestination destination() {
        return DestinationAccessor.getDestination(destinationName).asHttp();
    }

    public static final class S4Response {
        public final int status;
        public final String body;

        S4Response(int status, String body) {
            this.status = status;
            this.body = body;
        }
    }

    public S4Response get(String path) throws IOException, InterruptedException {
        HttpRequest.Builder request = newRequest(path)
                .header("Accept", "application/json")
                .timeout(Duration.ofSeconds(45))
                .GET();
        HttpResponse<String> response = http.send(request.build(),
                HttpResponse.BodyHandlers.ofString());
        return new S4Response(response.statusCode(), response.body());
    }

    /** POST with the CSRF handshake an S/4 write requires. */
    public S4Response post(String servicePath, String entityPath, String json)
            throws IOException, InterruptedException {
        HttpRequest fetch = newRequest(servicePath)
                .header("Accept", "application/json")
                .header("x-csrf-token", "fetch")
                .timeout(Duration.ofSeconds(45))
                .GET().build();
        HttpResponse<String> tokenResponse = http.send(fetch, HttpResponse.BodyHandlers.ofString());
        Optional<String> token = tokenResponse.headers().firstValue("x-csrf-token");
        if (token.isEmpty()) {
            return new S4Response(tokenResponse.statusCode(),
                    "No CSRF token issued: " + tokenResponse.body());
        }

        HttpRequest write = newRequest(entityPath)
                .header("Accept", "application/json")
                .header("Content-Type", "application/json")
                .header("x-csrf-token", token.get())
                .timeout(Duration.ofSeconds(60))
                .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                .build();
        HttpResponse<String> response = http.send(write, HttpResponse.BodyHandlers.ofString());
        return new S4Response(response.statusCode(), response.body());
    }

    /**
     * A request against the configured tenant, already authenticated.
     *
     * Destination headers are asked for per request rather than once at
     * startup: for Basic authentication the answer never changes, but for
     * OAuth the Cloud SDK is minting and refreshing a token behind this call,
     * and caching it here would work until the first expiry.
     */
    private HttpRequest.Builder newRequest(String path) {
        if (!isConfigured()) {
            throw new IllegalStateException(
                    "No S/4 connection is configured — nothing should have called this.");
        }
        if (destinationName == null) {
            return HttpRequest.newBuilder(URI.create(host + path))
                    .header("Authorization", basicAuth);
        }
        HttpDestination d = destination();
        URI uri = URI.create(d.getUri().toString().replaceAll("/+$", "") + path);
        HttpRequest.Builder request = HttpRequest.newBuilder(uri);
        for (Header header : d.getHeaders(uri)) {
            request.header(header.getName(), header.getValue());
        }
        return request;
    }

    private static String envOr(String key, String fallback) {
        String value = System.getenv(key);
        return value == null || value.isBlank() ? fallback : value;
    }
}
