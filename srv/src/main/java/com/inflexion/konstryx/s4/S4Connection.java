package com.inflexion.konstryx.s4;

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
 * The S/4HANA Public Cloud connection for local development.
 *
 * Credentials come from the environment (S4_HOST / S4_USER / S4_PASSWORD),
 * falling back to the gitignored ./.env file so a locally started service
 * works without ceremony. In production this whole class is replaced by the
 * BTP destination service — the seam is deliberate, and nothing above it may
 * ever see a password: callers get requests executed, not credentials.
 *
 * OData V2 writes need a CSRF token fetched over the same session, so the
 * client carries a cookie store and the token is fetched per write.
 */
@Component
public class S4Connection {

    private static final Logger log = LoggerFactory.getLogger(S4Connection.class);

    private final HttpClient http = HttpClient.newBuilder()
            .cookieHandler(new CookieManager())
            .connectTimeout(Duration.ofSeconds(20))
            .build();

    private String host;
    private String basicAuth;
    private boolean resolved;

    /** True when a tenant is configured; false leaves every sync queued. */
    public synchronized boolean isConfigured() {
        if (!resolved) {
            resolve();
        }
        return host != null && basicAuth != null;
    }

    public String host() {
        isConfigured();
        return host;
    }

    private void resolve() {
        resolved = true;
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
        log.info("S/4 connection configured for {}", this.host);
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
        HttpRequest request = HttpRequest.newBuilder(URI.create(host + path))
                .header("Authorization", basicAuth)
                .header("Accept", "application/json")
                .timeout(Duration.ofSeconds(45))
                .GET().build();
        HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
        return new S4Response(response.statusCode(), response.body());
    }

    /** POST with the CSRF handshake OData V2 requires. */
    public S4Response post(String servicePath, String entityPath, String json)
            throws IOException, InterruptedException {
        HttpRequest fetch = HttpRequest.newBuilder(URI.create(host + servicePath))
                .header("Authorization", basicAuth)
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

        HttpRequest write = HttpRequest.newBuilder(URI.create(host + entityPath))
                .header("Authorization", basicAuth)
                .header("Accept", "application/json")
                .header("Content-Type", "application/json")
                .header("x-csrf-token", token.get())
                .timeout(Duration.ofSeconds(60))
                .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                .build();
        HttpResponse<String> response = http.send(write, HttpResponse.BodyHandlers.ofString());
        return new S4Response(response.statusCode(), response.body());
    }
}
