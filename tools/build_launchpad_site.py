"""Generates the Work Zone site: spaces, pages and tiles, from the app manifests.

Written rather than clicked, for the same reason the content packs are: a site
assembled by hand in the Content Manager exists only in that tenant, cannot be
reviewed, and has to be rebuilt from memory the next time a subaccount is set
up. This file is the site, and `mbt build` ships it.

Generated from the manifests rather than listed here, so the two cannot drift.
An app's title, subtitle, icon and — most importantly — its inbound intent are
read from its own manifest.json: a tile whose intent no longer matches its app
is a tile that opens nothing, and that is not a mistake anyone catches by
reading a launchpad definition.

The four spaces are Ziya's (2026-08-26): Master, Planning, Execution,
Commercial. Master sits last because it is a reference shelf, not a step in the
work.
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "app")
OUT_DIR = os.path.join(ROOT, "launchpad-content")

# Which space each app belongs in, and the order within it. Anything not
# listed is left out of the site deliberately rather than swept into a
# leftovers space - a tile nobody chose to place is a tile nobody wants.
LAYOUT = [
    ("planning", "Planning", "The project, what it is worth, and what it may spend", [
        ("konstryx-project", "Set up"),
        ("konstryx-boq", "Set up"),
        ("konstryx-budget", "Set up"),
    ]),
    ("execution", "Execution", "Sourcing the work, and recording what was done", [
        ("konstryx-resource-request", "Source resources"),
        ("konstryx-requisition", "Source resources"),
        ("konstryx-reservation", "On site"),
        ("konstryx-timesheet", "On site"),
        ("konstryx-productivity", "On site"),
    ]),
    ("commercial", "Commercial", "Certifying and paying for the work", [
        ("konstryx-payment-certificate", "Certification"),
    ]),
    ("master", "Master Data", "The catalogues every document draws on", [
        ("konstryx-resource", "Catalogues"),
        ("konstryx-material", "Catalogues"),
        ("konstryx-vendor", "Catalogues"),
        ("konstryx-exchange-rate", "Configuration"),
    ]),
]


def manifest(app):
    path = os.path.join(APP_DIR, app, "webapp", "manifest.json")
    return json.load(io.open(path, encoding="utf-8"))


def inbound_of(m, app):
    """The app's own crossNavigation inbound, and the intent it answers.

    Read rather than assumed. A tile pointing at an intent the app does not
    declare renders perfectly and opens nothing, and nothing in the deploy
    complains.
    """
    inbounds = m.get("sap.app", {}).get("crossNavigation", {}).get("inbounds", {})
    if not inbounds:
        raise SystemExit(f"{app} declares no crossNavigation inbound; a tile "
                         f"cannot target it.")
    key = next(iter(inbounds))
    return key, inbounds[key]


def site():
    spaces = {}
    pages = {}
    applications = {}
    visualizations = {}
    space_order = []

    for space_id, space_title, space_note, entries in LAYOUT:
        page_id = f"{space_id}-page"
        space_order.append(space_id)

        spaces[space_id] = {
            "identification": {
                "id": space_id,
                "title": space_title,
                "description": space_note,
                "entityType": "space",
            },
            "payload": {"pages": [{"id": page_id}]},
        }

        sections = {}
        section_order = []

        for app, section_title in entries:
            m = manifest(app)
            app_id = m["sap.app"]["id"]
            inbound_key, inbound = inbound_of(m, app)
            viz_id = f"viz-{app}"
            section_id = section_title.lower().replace(" ", "-")

            if section_id not in sections:
                sections[section_id] = {
                    "id": section_id,
                    "title": section_title,
                    "layout": {"vizOrder": []},
                    "viz": {},
                }
                section_order.append(section_id)

            sections[section_id]["layout"]["vizOrder"].append(viz_id)
            sections[section_id]["viz"][viz_id] = {"id": viz_id, "vizId": viz_id}

            applications[app_id] = {
                "sap.app": {
                    "id": app_id,
                    "title": inbound.get("title", app),
                    "subTitle": inbound.get("subTitle", ""),
                    "crossNavigation": {"inbounds": {inbound_key: inbound}},
                },
                "sap.ui": {"technology": "UI5", "icons": {"icon": inbound.get("icon", "")}},
                "sap.cloud": {"public": True, "service": "konstryx.app"},
                "sap.flp": {"type": "application"},
            }

            visualizations[viz_id] = {
                "vizType": "sap.ushell.StaticAppLauncher",
                "businessApp": app_id,
                "vizConfig": {
                    "sap.app": {
                        "title": inbound.get("title", app),
                        "subTitle": inbound.get("subTitle", ""),
                    },
                    "sap.ui": {"icons": {"icon": inbound.get("icon", "")}},
                    "sap.flp": {
                        "target": {"appId": app_id, "inboundId": inbound_key}
                    },
                },
            }

        pages[page_id] = {
            "identification": {
                "id": page_id,
                "title": space_title,
                "entityType": "page",
            },
            "payload": {
                "layout": {"sectionOrder": section_order},
                "sections": sections,
            },
        }

    return {
        "_version": "3.1.0",
        "identification": {
            "id": "konstryx-site",
            "title": "KONSTRYX",
            "entityType": "site",
        },
        "payload": {
            "site": {
                "identification": {"id": "konstryx-site", "title": "KONSTRYX"},
                "payload": {"spaceOrder": space_order},
            },
            "catalogs": {},
            "groups": {},
            "spaces": spaces,
            "pages": pages,
            "applications": applications,
            "visualizations": visualizations,
            "vizTypes": {},
        },
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    model = site()
    io.open(os.path.join(OUT_DIR, "CommonDataModel.json"), "w",
            encoding="utf-8").write(json.dumps(model, indent=2) + "\n")

    payload = model["payload"]
    for space_id in payload["site"]["payload"]["spaceOrder"]:
        page = payload["pages"][f"{space_id}-page"]
        tiles = sum(len(s["viz"]) for s in page["payload"]["sections"].values())
        titles = [s["title"] for s in page["payload"]["sections"].values()]
        print(f"  {payload['spaces'][space_id]['identification']['title']:<14} "
              f"{tiles} tile(s) in {', '.join(titles)}")
    print(f"\n  launchpad-content/CommonDataModel.json: "
          f"{len(payload['applications'])} app(s)")


main()
