"""Checks that every screen in the launchpad actually opens, and has rows.

A tile can render, carry a number, and open an application that fails on its
first request — the count comes from the service and the app comes from the web
server, and nothing joins the two until someone clicks. This walks the site the
way the launchpad does: every app in the layout, its page, its component, and
the entity set its list is bound to.

    python tools/smoke_demo.py [ui-url] [service-url]

Exit code is non-zero if anything is unreachable, so this can gate a demo.

The counts go through the UI proxy rather than straight at the service, so
whoever the proxy authenticates as is who this runs as. That choice decides
what the run means:

    admin       "does every screen open" — the question this tool asks, and
                the one a demo needs answered. Admin bypasses the persona
                layer, so a missing grant is invisible.
    a persona   "may this persona open its own screens" — a sharper question,
                and worth running deliberately. It is how the site engineer
                was found holding no grant on the stock draw or the
                consumption record, the two screens that exist for it.

Set KX_USER / KX_PASS on the proxy to choose. A persona run will fail on the
administration screens by design: AdminService and AuthorizationService require
the Admin role, and no persona holds it.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 8081, the port run-local.bat starts the UI on. A wrong port does not read
# as a wrong port: every app fails index, component, manifest and data at
# once, which looks exactly like twenty-eight broken screens.
UI = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8081").rstrip("/")
SERVICE = (sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8090").rstrip("/")
AUTH = "Basic " + base64.b64encode(b"admin:admin").decode()

SITE = os.path.join(ROOT, "app", "launchpad", "webapp", "appconfig",
                    "fioriSandboxConfig.json")


def fetch(url, auth=False):
    request = urllib.request.Request(url)
    request.add_header("Accept", "*/*")
    if auth:
        request.add_header("Authorization", AUTH)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except Exception as error:                                   # noqa: BLE001
        return 0, str(error).encode()


def main():
    site = json.load(open(SITE, encoding="utf-8"))
    data = site["services"]["CommonDataModel"]["adapter"]["config"]["siteData"]
    visualizations = data["visualizations"]
    applications = data["applications"]

    failures = []

    print("\nLaunchpad")
    for name, path in [("site config", "/appconfig/fioriSandboxConfig.json"),
                       ("launchpad", "/launchpad/index.html")]:
        status, _ = fetch(UI + path)
        ok = status == 200
        print("  %-26s %s" % (name, "ok" if ok else status))
        if not ok:
            failures.append(name)

    print("\nApplications")
    for viz_id, viz in sorted(visualizations.items()):
        app_id = viz["businessApp"]
        folder = viz_id.replace("viz-", "")
        target = applications[app_id]["sap.platform.runtime"][
            "componentProperties"]["url"]

        checks = []
        for label, path in [("index", target + "/index.html"),
                            ("component", target + "/Component.js"),
                            ("manifest", target + "/manifest.json")]:
            status, _ = fetch(UI + path)
            checks.append((label, status))

        # And the collection the tile counts, through the same proxy the app
        # uses rather than straight at the service - a working service behind a
        # broken proxy is exactly the failure a demo hits.
        count_url = viz["vizConfig"]["sap.flp"]["indicatorDataSource"]["path"]
        status, body = fetch(UI + urllib.parse.quote(count_url,
                                                     safe="/?$&=(),'*+-"))
        rows = body.decode("utf-8", "replace").strip() if status == 200 else "-"
        checks.append(("data", status))

        bad = [label for label, code in checks if code != 200]
        print("  %-30s %-8s %s"
              % (folder, rows, "ok" if not bad else "FAILED: " + ", ".join(bad)))
        if bad:
            failures.append(folder)

    print("\nActions the demo presses")
    for label, path in [
        ("critical path", "/odata/v4/project/Projects?$top=1&$select=code"),
        ("cost mapping", "/odata/v4/project/Allocations?$top=1&$select=allocQty"),
        ("document flow", "/odata/v4/workflow/DocumentLinks?$top=1&$select=linkType"),
        ("dependencies", "/odata/v4/project/ActivityRelations?$top=1&$select=linkType"),
        ("period report", "/odata/v4/project/PeriodReports?$top=1&$select=periodName"),
    ]:
        status, _ = fetch(SERVICE + urllib.parse.quote(path, safe="/?$&=(),'*+-"),
                          auth=True)
        print("  %-26s %s" % (label, "ok" if status == 200 else status))
        if status != 200:
            failures.append(label)

    if failures:
        print("\n  %d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("\n  Every screen opens and every list has a source.")


main()
