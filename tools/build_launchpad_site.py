"""Generates the launchpad site: spaces, pages, sections and tiles.

Written rather than clicked, for the same reason the content packs are: a site
assembled by hand in the Content Manager exists only in that tenant, cannot be
reviewed, and has to be rebuilt from memory the next time a subaccount is set
up. This file is the site, and it is emitted twice from one definition:

  launchpad-content/CommonDataModel.json
      the Work Zone site, shipped by the MTA once the launchpad service is
      entitled on the subaccount.

  app/launchpad/appconfig/fioriSandboxConfig.json
      the same spaces and pages running locally. The UI server maps
      /appconfig/fioriSandboxConfig.json onto this file, which is where the
      sandbox bootstrap looks, and merges it over its
      own default site, which is the only hook it offers - _applyDefaultSiteData
      replaces whatever site the page supplies, so a site built in index.html
      was dead code and the four phases were being flattened into the sandbox's
      one "Sample Space".

The tiles are dynamic, not static. A tile that reads only its own name makes a
launchpad a menu; a tile that reads "6" over "Purchase Requisitions" is the
reason someone opens that app rather than another one. The number comes from
the app's own entity set through OData's $count, so it is the live figure and
not a cached one - and because it is the service's own count, a tile can never
disagree with the list it opens.

Titles, subtitles, icons and - most importantly - the inbound intent are read
from each app's manifest.json rather than restated here. A tile whose intent no
longer matches its app renders perfectly and opens nothing, and that is not a
mistake anyone catches by reading a launchpad definition.

The four spaces are Ziya's (2026-08-26): Planning, Execution, Commercial,
Master Data. Master sits last because it is a reference shelf, not a step in
the work.
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "app")
CDM_OUT = os.path.join(ROOT, "launchpad-content")
# Beside webapp rather than inside it. The sandbox bootstrap asks for
# appconfig/fioriSandboxConfig.json relative to the app root, not to the
# page - it fetched /launchpad/appconfig/... and got a 404, then fell back
# to its own "Sample Space", so the launchpad showed three demo tiles and
# none of the product's forty-seven.
LOCAL_OUT = os.path.join(APP_DIR, "launchpad", "appconfig")

# Every app, in the space and section it belongs to, with the count that goes
# on the face of its tile. Anything not listed is left out of the site
# deliberately rather than swept into a leftovers space - a tile nobody chose
# to place is a tile nobody wants.
#
# The count URL is the app's own entity set. Draft-enabled sets are filtered to
# the active rows: without it a tile counts drafts as documents and reads high
# by however many half-finished edits are open.
LAYOUT = [
    ("konstryx-planning", "Planning", "sap-icon://blueprint",
     "The project, what it is worth, and what it may spend", [
         ("Overview", {"id": "konstryx.dashboard",
                       "app": "konstryx-dashboard",
                       "semanticObject": "KonstryxDashboard",
                       "action": "display",
                       "title": "Project Controller Overview",
                       "subTitle": "KPIs, curves and what needs a human",
                       "icon": "sap-icon://business-objects-experience"},
          "/odata/v4/project/ProjectOverviews/$count", "projects"),
         ("Overview", "konstryx-project360",
          "/odata/v4/project/ProjectOverviews/$count", "projects"),
         ("Set up", "konstryx-project",
          "/odata/v4/project/Projects/$count?$filter=IsActiveEntity eq true",
          "projects"),
         ("Set up", "konstryx-boq",
          "/odata/v4/project/BOQs/$count?$filter=IsActiveEntity eq true",
          "bills"),
         ("Set up", "konstryx-budget",
          "/odata/v4/budget/Budgets/$count?$filter=IsActiveEntity eq true",
          "budgets"),
     ]),
    ("konstryx-execution", "Execution", "sap-icon://building",
     "Sourcing the work, and recording what was done", [
         ("Today", "konstryx-approval",
          "/odata/v4/collaboration/MyApprovals/$count", "waiting on you"),
         ("Today", "konstryx-gang",
          "/odata/v4/masterdata/Gangs/$count?$filter=IsActiveEntity eq true",
          "gangs"),
         ("Today", "konstryx-absence",
          "/odata/v4/masterdata/Absences/$count?$filter=IsActiveEntity eq true",
          "away"),
         ("Today", "konstryx-workfront",
          "/odata/v4/project/WorkFronts/$count", "fronts open"),
         ("Source resources", "konstryx-resource-request",
          "/odata/v4/workflow/ResourceRequests/$count?$filter=IsActiveEntity eq true",
          "requests"),
         ("Source resources", "konstryx-requisition",
          "/odata/v4/material/PurchaseRequisitions/$count", "requisitions"),
         # Separate from the two above, because the two above are ours to
         # raise and these two are ERP's to send back. One group you act in,
         # one you read.
         ("Bought and billed", "konstryx-po",
          "/odata/v4/material/PurchaseOrders/$count", "orders placed"),
         ("Bought and billed", "konstryx-invoice",
          "/odata/v4/material/SupplierInvoices/$count", "bills received"),
         ("On site", "konstryx-reservation",
          "/odata/v4/workflow/Reservations/$count", "reservations"),
         # Beside the reservation rather than under Change control: this varies
         # what a job has locked to build with, and the variation over there
         # varies a priced bill. Same word, different document, different
         # reader.
         ("On site", "konstryx-resvariation",
          "/odata/v4/workflow/ReservationVariations/$count", "variations"),
         ("On site", "konstryx-pull",
          "/odata/v4/material/PullRequests/$count", "stock draws"),
         ("On site", "konstryx-consumption",
          "/odata/v4/material/ConsumptionRecords/$count", "days measured"),
         ("On site", "konstryx-timesheet",
          "/odata/v4/workflow/Timesheets/$count?$filter=IsActiveEntity eq true",
          "days"),
         ("On site", "konstryx-productivity",
          "/odata/v4/workflow/ProductivitySnapshots/$count", "measured"),
     ]),
    ("konstryx-commercial", "Commercial", "sap-icon://money-bills",
     "Certifying and paying for the work, and what it is making", [
         ("Change control", "konstryx-variation",
          "/odata/v4/project/Variations/$count?$filter=IsActiveEntity eq true",
          "variations"),
         ("Certification", "konstryx-payment-certificate",
          "/odata/v4/subcontract/PaymentCertificates/$count", "certificates"),
         ("Certification", "konstryx-payment-application",
          "/odata/v4/billing/PaymentApplications/$count?$filter=IsActiveEntity eq true",
          "client claims"),
         ("Reports", "konstryx-report",
          "/odata/v4/project/PeriodReports/$count", "periods"),
         ("Reports", "konstryx-booklet",
          "/odata/v4/project/Booklet/$count", "projects"),
         ("Reports", "konstryx-cashflow",
          "/odata/v4/project/Cashflow/$count", "periods"),
     ]),
    ("konstryx-master", "Master Data", "sap-icon://course-book",
     "The catalogues every document draws on", [
         ("Catalogues", "konstryx-resource",
          "/odata/v4/masterdata/Resources/$count?$filter=IsActiveEntity eq true",
          "resources"),
         ("Catalogues", "konstryx-material",
          "/odata/v4/masterdata/Materials/$count", "materials"),
         ("Catalogues", "konstryx-vendor",
          "/odata/v4/masterdata/Vendors/$count", "vendors"),
         ("Catalogues", "konstryx-customer",
          "/odata/v4/masterdata/Customers/$count", "customers"),
         ("Structures", "konstryx-cbs",
          "/odata/v4/masterdata/CBSLibrary/$count?$filter=IsActiveEntity eq true",
          "nodes"),
         ("Norms & rates", "konstryx-productivity-rate",
          "/odata/v4/masterdata/ProductivityRates/$count?$filter=IsActiveEntity eq true",
          "norms"),
         ("Norms & rates", "konstryx-consumption-rate",
          "/odata/v4/masterdata/ConsumptionRates/$count?$filter=IsActiveEntity eq true",
          "norms"),
         ("Norms & rates", "konstryx-rate",
          "/odata/v4/masterdata/Rates/$count?$filter=IsActiveEntity eq true",
          "rates"),
         ("Configuration", "konstryx-exchange-rate",
          "/odata/v4/admin/ExchangeRates/$count", "rates"),
         ("Configuration", "konstryx-persona",
          "/odata/v4/authorization/Personas/$count?$filter=IsActiveEntity eq true",
          "personas"),
         ("Configuration", "konstryx-user-assignment",
          "/odata/v4/authorization/UserAssignments/$count", "assignments"),
         ("Configuration", "konstryx-approval-scheme",
          "/odata/v4/authorization/ApprovalSchemes/$count", "schemes"),
         ("Workforce", "konstryx-trade",
          "/odata/v4/masterdata/Trades/$count?$filter=IsActiveEntity eq true",
          "trades"),
         ("Workforce", "konstryx-shift-pattern",
          "/odata/v4/masterdata/ShiftPatterns/$count?$filter=IsActiveEntity eq true",
          "patterns"),
         ("Workforce", "konstryx-holiday-calendar",
          "/odata/v4/masterdata/HolidayCalendars/$count?$filter=IsActiveEntity eq true",
          "calendars"),
         ("Workforce", "konstryx-crew",
          "/odata/v4/masterdata/CrewTemplates/$count?$filter=IsActiveEntity eq true",
          "crews"),
         ("Workforce", "konstryx-absence-reason",
          "/odata/v4/masterdata/AbsenceReasons/$count?$filter=IsActiveEntity eq true",
          "reasons"),
         ("People", "konstryx-worker",
          "/odata/v4/masterdata/Workers/$count?$filter=IsActiveEntity eq true",
          "workers"),
         ("People", "konstryx-sc-worker",
          "/odata/v4/masterdata/SubcontractWorkers/$count?$filter=IsActiveEntity eq true",
          "workers"),
         ("People", "konstryx-engagement",
          "/odata/v4/masterdata/SubcontractEngagements/$count?$filter=IsActiveEntity eq true",
          "engagements"),
         ("People", "konstryx-roster",
          "/odata/v4/masterdata/RosterUploads/$count?$filter=IsActiveEntity eq true",
          "uploads"),
         ("People", "konstryx-worker-push",
          "/odata/v4/masterdata/WorkerPushQueue/$count", "waiting"),
     ]),
]


def manifest(app):
    path = os.path.join(APP_DIR, app, "webapp", "manifest.json")
    return json.load(io.open(path, encoding="utf-8"))


def inbound_of(app_manifest, app):
    """The app's own crossNavigation inbound, and the key it is filed under.

    Read rather than assumed. A tile pointing at an intent the app does not
    declare renders perfectly and opens nothing, and nothing in the deploy
    complains.
    """
    inbounds = (app_manifest.get("sap.app", {})
                .get("crossNavigation", {}).get("inbounds", {}))
    if not inbounds:
        raise SystemExit("%s declares no crossNavigation inbound; a tile "
                         "cannot target it." % app)
    key = next(iter(inbounds))
    return key, inbounds[key]


def build():
    """One pass over the layout, producing every part of the site."""
    pages, applications, visualizations, menu_entries = {}, {}, {}, []
    inbounds = {}

    for space_id, space_title, space_icon, space_note, entries in LAYOUT:
        page_id = space_id + "-page"
        sections, section_order = {}, []

        for section_title, app, count_url, unit in entries:
            # A page rather than a component: the overview dashboard is plain
            # HTML driving integration cards, so there is no manifest to read
            # an intent from and no Component for the launchpad to load. It is
            # declared here instead and resolved as a URL, which is what the
            # launchpad does for anything it cannot instantiate itself.
            is_url_app = isinstance(app, dict)
            if is_url_app:
                spec = app
                app = spec["app"]
                app_id = spec["id"]
                inbound_key = spec["action"]
                inbound = {"semanticObject": spec["semanticObject"],
                           "action": spec["action"],
                           "title": spec["title"],
                           "subTitle": spec.get("subTitle", ""),
                           "icon": spec.get("icon", "")}
            else:
                app_manifest = manifest(app)
                app_id = app_manifest["sap.app"]["id"]
                inbound_key, inbound = inbound_of(app_manifest, app)
            viz_id = "viz-" + app
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
                    "applicationVersion": {"version": "1.0.0"},
                    "crossNavigation": {"inbounds": {inbound_key: {
                        "semanticObject": inbound["semanticObject"],
                        "action": inbound["action"],
                        "signature": inbound.get(
                            "signature",
                            {"parameters": {}, "additionalParameters": "allowed"}),
                    }}},
                },
                "sap.flp": {"type": "application"},
                "sap.ui": {
                    "technology": "UI5",
                    "icons": {"icon": inbound.get("icon", "")},
                    "deviceTypes": {"desktop": True, "tablet": True, "phone": True},
                },
                "sap.ui5": {"componentName": app_id},
                # webapp, not the app folder. Component.js and manifest.json
                # are served one level down, so "/konstryx-project" pointed
                # the loader at a directory holding neither and every tile in
                # the launchpad opened "App could not be started because the
                # SAP UI5 component could not be loaded". The manifest is read
                # rather than skipped, which is how a Fiori Elements app finds
                # its own data source and targets.
                "sap.platform.runtime": {"componentProperties": {
                    "url": "/" + app + "/webapp",
                    "manifest": True,
                }},
                "sap.cloud": {"public": True, "service": "konstryx.app"},
            }

            visualizations[viz_id] = {
                "vizType": "sap.ushell.DynamicAppLauncher",
                "businessApp": app_id,
                "vizConfig": {
                    "sap.app": {
                        "title": inbound.get("title", app),
                        "subTitle": inbound.get("subTitle", ""),
                    },
                    "sap.ui": {
                        "icons": {"icon": inbound.get("icon", "")},
                        "deviceTypes": {"desktop": True, "tablet": True,
                                        "phone": True},
                    },
                    "sap.flp": {
                        # A plain page opens as a URL. Pointed at an appId the
                        # launchpad looks for a UI5 component that does not
                        # exist, and refuses to start it.
                        "target": ({"type": "URL",
                                    "url": "/" + app + "/webapp/index.html"}
                                   if is_url_app
                                   else {"appId": app_id,
                                         "inboundId": inbound_key}),
                        "numberUnit": unit,
                        # The service's own count, refreshed while the page is
                        # open. A tile that disagrees with the list it opens is
                        # worse than a tile with no number at all.
                        "indicatorDataSource": {"path": count_url,
                                                "refresh": 120},
                    },
                },
            }

            # A page has no component to register, and an application entry
            # claiming one would have the launchpad try to load it anyway.
            if is_url_app:
                applications.pop(app_id, None)

            inbounds[app_id + "-" + inbound_key] = {
                "semanticObject": inbound["semanticObject"],
                "action": inbound["action"],
                "title": inbound.get("title", app),
                "signature": inbound.get(
                    "signature",
                    {"parameters": {}, "additionalParameters": "allowed"}),
                "resolutionResult": ({
                    "applicationType": "URL",
                    "url": "/" + app + "/",
                } if is_url_app else {
                    "applicationType": "SAPUI5",
                    "additionalInformation": "SAPUI5.Component=" + app_id,
                    "url": "/" + app,
                }),
            }

        pages[page_id] = {
            "identification": {"id": page_id, "title": space_title,
                               "description": space_note},
            "payload": {"layout": {"sectionOrder": section_order},
                        "sections": sections},
        }

        # A space is a menu entry pointing at its page. This is what the shell
        # reads; a "spaces" key on its own renders nothing.
        menu_entries.append({
            "id": space_id,
            "title": space_title,
            "description": space_note,
            "icon": space_icon,
            "type": "IBN",
            "target": {
                "semanticObject": "Launchpad",
                "action": "openFLPPage",
                "parameters": [
                    {"name": "pageId", "value": page_id},
                    {"name": "spaceId", "value": space_id},
                ],
            },
        })

    return pages, applications, visualizations, menu_entries, inbounds


def spaces_of(menu_entries, pages):
    """The CDM spaces block, for the Work Zone site."""
    spaces = {}
    for entry in menu_entries:
        page_id = entry["target"]["parameters"][0]["value"]
        spaces[entry["id"]] = {
            "identification": {"id": entry["id"], "title": entry["title"],
                               "description": entry["description"],
                               "entityType": "space"},
            "payload": {"pages": [{"id": page_id}]},
        }
    return spaces


def main():
    pages, applications, visualizations, menu_entries, inbounds = build()

    # ---- the Work Zone site -------------------------------------------------
    os.makedirs(CDM_OUT, exist_ok=True)
    spaces = spaces_of(menu_entries, pages)
    cdm = {
        "_version": "3.1.0",
        "identification": {"id": "konstryx-site", "title": "KONSTRYX",
                           "entityType": "site"},
        "payload": {
            "site": {
                "identification": {"id": "konstryx-site", "title": "KONSTRYX"},
                "payload": {"spaceOrder": [e["id"] for e in menu_entries]},
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
    io.open(os.path.join(CDM_OUT, "CommonDataModel.json"), "w",
            encoding="utf-8").write(json.dumps(cdm, indent=2) + "\n")

    # ---- the same site, locally --------------------------------------------
    #
    # Merged over the sandbox's default rather than replacing it: the bootstrap
    # applies its own site first and only then reads this file, so the keys
    # here have to be the ones that matter. menuEntries is an array and is
    # replaced wholesale, which is what removes the sandbox's "Sample Space".
    os.makedirs(LOCAL_OUT, exist_ok=True)

    local = {
        # Spaces mode, and nothing else touched. Overriding rootIntent to
        # Launchpad-openFLPPage sent the shell to a page with no space and no
        # page id and it opened on an error; the default root intent resolves
        # to the first space in the menu, which is what a spaces launchpad is
        # supposed to do.
        "ushell": {"spaces": {"enabled": True}},
        "renderers": {"fiori2": {"componentData": {"config": {
            "enableSearch": False,
        }}}},
        "services": {
            # The sandbox's own siteData, in its own shape.
            #
            # This is not the Work Zone CDM above with a different indent. The
            # local adapter reads spaces out of menus.main.menuEntries and
            # never looks at a "spaces" entity, and it expects site.payload to
            # carry groupsOrder and the ushell config - written the Work Zone
            # way, with a spaces map and a spaceOrder, it threw on an undefined
            # string before the shell was drawn and the launchpad rendered a
            # blank page. The shape below is the sandbox's own default site,
            # with this product's spaces, pages and apps in place of the
            # samples.
            #
            # _version matters: the adapter branches on it, and without one it
            # cannot tell which CDM it was handed.
            "CommonDataModel": {"adapter": {"config": {"siteData": {
                "_version": "3.1.0",
                "site": {
                    "identification": {"id": "konstryx-site",
                                       "title": "KONSTRYX"},
                    "payload": {
                        "groupsOrder": [],
                        "config": {"ushellConfig": {"renderers": {"fiori2": {
                            "componentData": {"config": {
                                "enableSearch": False}}}}}},
                    },
                },
                "catalogs": {},
                "systemAliases": {},
                "pages": pages,
                "applications": applications,
                "visualizations": visualizations,
                "menus": {"main": {
                    "identification": {"id": "main"},
                    "payload": {"menuEntries": menu_entries},
                }},
            }}}},
            # No hand-built inbound table here. The sandbox derives its
            # navigation targets from the applications above -
            # crossNavigation.inbounds on each one - and a second copy of the
            # same intents under ClientSideTargetResolution made the shell
            # throw before it drew anything: a blank page, and in the console
            # only "Cannot read properties of undefined (reading 'replace')".
            # One source of truth for an intent, and it is the app's manifest.
        },
    }
    io.open(os.path.join(LOCAL_OUT, "fioriSandboxConfig.json"), "w",
            encoding="utf-8").write(json.dumps(local, indent=2) + "\n")

    for entry in menu_entries:
        page = pages[entry["target"]["parameters"][0]["value"]]
        tiles = sum(len(s["viz"]) for s in page["payload"]["sections"].values())
        titles = [s["title"] for s in page["payload"]["sections"].values()]
        print("  %-14s %d tile(s) in %s"
              % (entry["title"], tiles, ", ".join(titles)))
    print("\n  %d space(s), %d app(s)" % (len(menu_entries), len(applications)))
    print("  launchpad-content/CommonDataModel.json")
    print("  app/launchpad/appconfig/fioriSandboxConfig.json")


main()
