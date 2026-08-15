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
import http.server
import os
import socketserver
import sys
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
WEBAPP = os.path.join(HERE, "webapp")

DEFAULT_RUNTIME = r"C:\Users\Ziya\Documents\Claude\sapui5-rt-1.150.0"

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
RUNTIME = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("UI5_RUNTIME", DEFAULT_RUNTIME)

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
