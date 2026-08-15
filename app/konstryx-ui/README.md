# KONSTRYX — SAPUI5 application

A real SAPUI5 project, not a wireframe: `manifest.json` routing, XML views with
controllers, a `sap.tnt.ToolPage` shell, `sap.m` / `sap.f` / `sap.uxap` controls, and a
JSONModel holding the Marina Heights Tower data. Built against **SAPUI5 1.150.0**,
loaded from your local runtime at
`C:\Users\Ziya\Documents\Claude\sapui5-rt-1.150.0`.

## Run it

Double-click **`start-konstryx.bat`**. It starts a local server and opens
<http://localhost:8080/index.html>.

A SAPUI5 app **cannot** be opened as a file. The XML views, `manifest.json` and the i18n
bundle are fetched over XHR, and Chrome blocks that for `file://` pages — the app would
load the framework and then render an empty shell. That is why there is a launcher.

The launcher uses Python if it is installed and PowerShell otherwise. Neither needs admin
rights. To change the port or the runtime location, edit the two `set` lines at the top of
the `.bat`.

## What is built

The **EQR canonical thread `RR-2026-0188` · Site Plant Mobilization** — 5 lines,
18 instances, AED 716,044 — end to end across all ten steps of the chain:

```
RR → ADV → AVC → RES → CMT → MOB → OPL → VAR → DMB → CLS
```

Every step is its own route, its own document, and its own object page. The document-flow
strip at the top of each page is live: clicking a node navigates to that document *of this
thread*. Browser back/forward and deep links work — `#/doc/RR-2026-0188/7` opens the
Operation Log directly.

The other three threads (MR-0148, MPR-0162, VR-0205) appear in the worklists but are not
drilled yet.

## Navigation

The side navigation follows the process, not the module list:

| Group | Items |
|---|---|
| ① Request & Source | Resource Requests · Advisory Decisions · Availability Checks · Reservations |
| ② Commit & Execute | Budget Commitments · Mobilizations · Operation Logs |
| ③ Change & Close | Variation Orders · De-mobilizations · Closures |

Step 1 lists the requests themselves; steps 2–10 list the chain documents of that type,
each carrying the request it belongs to, so a click lands on the right document of the
right thread.

`CMT` (step 5) renders read-only with an explicit notice: S/4HANA Project System owns the
encumbrance. KONSTRYX reads it and never authors it.

## Project layout

```
KONSTRYX_UI5_App/
├── start-konstryx.bat        launcher — Python, else PowerShell
├── serve.py / serve.ps1      static server; maps /resources → your SAPUI5 runtime
├── ui5.yaml                  optional, for `npx ui5 serve` if you use UI5 Tooling
└── webapp/
    ├── index.html            bootstraps resources/sap-ui-core.js · sap_horizon · compact
    ├── Component.js          UIComponent · starts the router after the root view exists
    ├── manifest.json         routes, targets, models, libraries
    ├── controller/           App · Launchpad · Worklist · RequestDetail · ChainStep · Base
    ├── view/                 the XML views + ProcessChain.fragment.xml
    ├── model/                models.js + data.json (all sample data lives here)
    ├── i18n/  css/  img/
```

## Two things that will bite you if you extend this

**Start the router after the root view exists.** `Component.init()` runs before the async
root view is created. Calling `getRouter().initialize()` there fires the first route match
while the `NavContainer` it targets is still undefined — the shell renders and the content
area stays blank, with no error. Use `this.rootControlLoaded().then(...)`, as
`Component.js` does.

**`routing.config` needs `"type": "View"` and `"path"`.** Without `type`, UI5 skips the
entire load-and-place branch silently — no view, no error in the log. With `type: "View"`
the target reads `path` (not the legacy `viewPath`) to resolve the view module.

## Adding the next thread

The chain rendering is data-driven. To add the MR thread, extend `model/data.json`:
give `RR-2026-0148` its `lines` array and add its ten `chain` entries with a matching
`lineTexts` block. No new views or controllers are needed — `ChainStep` renders any step
from its `fields`, `lineExtra` and `actions`.

To add a genuinely different floorplan (the SF Plant Return 3-step wizard, say), add a view
plus controller and one route; the shell and navigation pick it up from `manifest.json`.

## Verified

Runs on SAPUI5 1.150.0. Launchpad, all ten chain steps, worklists for every document type,
row drill-down, the document-flow strip, breadcrumbs, browser back/forward and deep links
were all exercised in a headless browser with zero JavaScript errors.
