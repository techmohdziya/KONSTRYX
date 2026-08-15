#!/usr/bin/env python3
"""
KONSTRYX — tiny static server for the UI5 app.

A SAPUI5 application cannot run from file:// — XML views, manifest.json and the
i18n bundle are fetched over XHR, which Chrome blocks for local files. This
serves two folders under one origin:

    /resources/...  ->  <SAPUI5 runtime>/resources/...
    everything else ->  ./webapp/...

so the app's bootstrap `src="resources/sap-ui-core.js"` resolves against your
local SAPUI5 distribution without copying it.

Usage:  python serve.py [port] [path-to-sapui5-runtime]
"""
import base64
import http.server
import os
import socketserver
import sys
import urllib.error
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
WEBAPP = os.path.join(HERE, "webapp")

DEFAULT_RUNTIME = r"C:\Users\Ziya\Documents\Claude\sapui5-rt-1.150.0"

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
RUNTIME = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("UI5_RUNTIME", DEFAULT_RUNTIME)

# The CAP Java service. /odata/... is reverse-proxied there so the app and the
# service share one origin — no CORS, and relative URIs in manifest.json work
# unchanged when the app is later served by the approuter in Cloud Foundry.
BACKEND = os.environ.get("KX_BACKEND", "http://localhost:8090")

# Local development only: the CAP service runs with mocked auth, so the proxy
# signs requests as a mock user. In Cloud Foundry the approuter forwards the
# real XSUAA token and nothing here applies.
MOCK_USER = os.environ.get("KX_USER", "daud")
MOCK_PASS = os.environ.get("KX_PASS", "daud")

EXTRA_TYPES = {
    ".properties": "text/plain; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
}


class Handler(http.server.SimpleHTTPRequestHandler):

    # ---- OData reverse proxy ------------------------------------------------

    def _is_service(self):
        return self.path.split("?", 1)[0].startswith("/odata/")

    def _proxy(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        req = urllib.request.Request(BACKEND + self.path, data=body, method=method)

        # Forward everything except hop-by-hop headers and the ones we set
        # ourselves. An allowlist is wrong here: dropping OData-MaxVersion makes
        # CAP answer 4.01, which the UI5 V4 model rejects outright.
        skip = {"host", "connection", "content-length", "authorization",
                "accept-encoding", "keep-alive", "proxy-authorization",
                "te", "trailers", "transfer-encoding", "upgrade"}
        for name, value in self.headers.items():
            if name.lower() not in skip:
                req.add_header(name, value)

        token = base64.b64encode(("%s:%s" % (MOCK_USER, MOCK_PASS)).encode()).decode()
        req.add_header("Authorization", "Basic " + token)

        try:
            with urllib.request.urlopen(req) as res:
                payload, status, headers = res.read(), res.status, res.headers
        except urllib.error.HTTPError as err:
            payload, status, headers = err.read(), err.code, err.headers
        except urllib.error.URLError as err:
            payload = ('{"error":{"message":"KONSTRYX backend unreachable at %s — %s"}}'
                       % (BACKEND, err.reason)).encode()
            status, headers = 502, {}

        self.send_response(status)
        self.send_header("Content-Type", (headers.get("Content-Type") if headers else None)
                         or "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for header in ("OData-Version", "ETag", "X-CSRF-Token", "Preference-Applied",
                       "sap-messages", "Location"):
            value = headers.get(header) if headers else None
            if value:
                self.send_header(header, value)
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self._is_service():
            return self._proxy("GET")
        return super().do_GET()

    def do_HEAD(self):
        if self._is_service():
            return self._proxy("HEAD")
        return super().do_HEAD()

    def do_POST(self):
        return self._proxy("POST")

    def do_PATCH(self):
        return self._proxy("PATCH")

    def do_DELETE(self):
        return self._proxy("DELETE")

    # ---- static files -------------------------------------------------------

    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        parts = [p for p in clean.split("/") if p not in ("", ".", "..")]

        if parts and parts[0] == "resources":
            return os.path.join(RUNTIME, "resources", *parts[1:])

        if not parts:
            parts = ["index.html"]
        return os.path.join(WEBAPP, *parts)

    def guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in EXTRA_TYPES:
            return EXTRA_TYPES[ext]
        return super().guess_type(path)

    def end_headers(self):
        # the app is edited while the server runs — never cache
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if len(args) > 1 and str(args[1]) not in ("200", "304"):
            sys.stderr.write("  %s %s\n" % (args[1], args[0]))


def main():
    if not os.path.isdir(os.path.join(RUNTIME, "resources")):
        sys.stderr.write(
            "\n  Cannot find the SAPUI5 runtime.\n"
            "  Looked for: %s\\resources\n\n"
            "  Pass the correct path as the second argument:\n"
            "      python serve.py 8080 \"D:\\path\\to\\sapui5-rt-1.150.0\"\n\n" % RUNTIME
        )
        sys.exit(1)

    socketserver.TCPServer.allow_reuse_address = True
    url = "http://localhost:%d/index.html" % PORT
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print("\n  KONSTRYX is running at  %s" % url)
        print("  UI5 runtime            %s" % RUNTIME)
        print("  OData proxy            /odata/  ->  %s  (as %s)" % (BACKEND, MOCK_USER))
        print("  Press Ctrl+C to stop.\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Stopped.\n")


if __name__ == "__main__":
    main()
