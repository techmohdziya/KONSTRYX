# KONSTRYX — project context for Claude Code

Handoff from a Cowork session (2026-08-14). Read this before touching anything.

---

## 1 · What KONSTRYX is

A **multi-tenant SaaS product built and owned by Inflexion** — an SAP BTP, CAP-framework
(Java runtime) extension for the Engineering & Construction industry, sold to multiple E&C
customers. It is a **product, not a customer project**.

It integrates with exactly three SAP cloud systems:

- **S/4HANA Public Cloud** — transactional spine (PS/WBS, Sourcing, Procurement PR/PO/GR, Finance AR/AP, MM)
- **Ariba** — sourcing (RFQ, Bid Analysis, Award, LSC/SCR RFQs, supplier collaboration)
- **SuccessFactors Employee Central** — employee master for the Workforce module

SAP Private Cloud is out of scope.

### Brand spelling — non-negotiable

The product is **Konstryx** (with a **Y**); caps form **KONSTRYX**. Never write "Konstrux",
"konstrux" or "Konstrucx" in user-facing text, docs, code identifiers or headings. The
on-disk OneDrive folder is still named `Products/konstrux/Konstrucx/` — that is a stale
filesystem path, not the brand.

### The foundational rule: KONSTRYX-as-reader

Process that S/4HANA owns **stays in S/4**; KONSTRYX uses APIs to read and sync. KONSTRYX
is the extension layer adding construction-specific workflow on top; S/4 is the system of
record.

- **S/4-owned, render read-only** with Sync / Open-in-S4 / Last-sync indicators: PR, PO, GR,
  Invoice, S/4 Reservation, Equipment custody, Material ATP, Frame Agreements, Bank Guarantees.
- **KONSTRYX-owned, full create/edit workflow**: Resource Request, Advisory Decision,
  Availability Check, Reservation, Mobilization, Operation Log, Variation, De-mob, Closure.
- **Bid Analysis** is the only procurement step KONSTRYX owns end to end.
- **Out of scope, do not build**: Bank Guarantees (APG + Performance Bond + Retention BG) —
  owned by S/4HC Treasury. Display status read-only if needed; never author.

### The canonical process chain

Every resource vertical follows the same ten steps:

```
RR → ADV → AVC → RES → CMT → MOB/SI → OPL → VAR → DMB → CLS
```

| # | Doc | Owner | Meaning |
|---|---|---|---|
| 1 | RR · Resource Request | KONSTRYX | Site originator submits the need |
| 2 | ADV · Advisory Decision | KONSTRYX | Type-split committee decides routing (own vs procure) |
| 3 | AVC · Availability Check | KONSTRYX | Gate — re-validates pool / stock / vendor in real time |
| 4 | RES · Reservation | KONSTRYX | Operational reservation, state machine |
| 5 | CMT · Budget Commitment | **S/4 PS** | Per-line encumbrance on WBS via Universal Journal |
| 6 | MOB (equip) / SI (material) | KONSTRYX | Mobilization or stock issue |
| 7 | OPL · Operation Log | KONSTRYX | Daily logs / timesheet / consumption |
| 8 | VAR · Variation Order | KONSTRYX | Per-line change order, duration or scope |
| 9 | DMB · De-mobilization | KONSTRYX | Return to pool / final consumption |
| 10 | CLS · Closure | KONSTRYX | Reconciliation, residual encumbrance release |

**Multi-line model (since v5):** every RR is **header + N line items**. Each line carries one
resource/spec, one WBS/CBS, one qty + UoM, one need-by (or mob–demob) window, and one routing
decision. The chain repeats per line.

**Six verticals:** MR (Material) · EQR (Equipment) · MPR (Manpower) · VR (Vehicle) ·
SCR (Subcontract) · SF (Scaffold/Formwork).

### Other data-model facts worth holding

- **6 asset classes:** EQ, VH, LG (Lifting Gear), IN (Instrument), TL (Tool kit), TW (Temporary Works).
  Only EQ links the Resource Hierarchy. Sub-components live in a flat pool, bound to the parent
  at mobilization (S/4 `SuperiorEquipment`). Operators are Manpower Resource Codes.
- **Crews are ephemeral** per-reservation groupings (GNG-2026-A/B/C), 1 Foreman + N members.
  There is no Crew Master. Productivity is tracked at crew level.
- **Asset vs operator timesheet split:** the equipment operation log has two tabs feeding
  different SAP cost elements — asset utilization posts a Service Entry Sheet, operator
  timesheet posts CATS. **Never merge them.**
- **SF Plant Return is KONSTRYX-mastered** (S/4 sees finance only): 3-step PL-INS wizard,
  9 outcome states, R1–R4 reuse classes, custom-piece inventory with an aging clock, no S/4
  Material Master mirror.

### Canonical sample data — use these, never invent

All threads live on **PRJ-001 Marina Heights Tower**, client Emaar Marina LLC, contract
MHT-CON-2024-014 (AED 45.2 M → 47.3 M post-VO). Demo data date 22 Aug 2026.

| Thread | Vertical | Scope | Value |
|---|---|---|---|
| RES-2026-0188 | EQR | 5 lines · 18 instances (10 own + 8 rental) | AED 716,044 |
| RES-2026-0148 | MR | 5 lines · 2 WBS · rebar-dominant | AED 404,931 |
| RES-2026-0162 | MPR | 5 lines · 24 heads · 5 crews | AED 814,484 |
| RES-2026-0205 | VR | 5 lines · 15 units | AED 342,400 |
| RES-SF-2026-0188 | SF | 1,700 pcs Cuplock · 8 lots | — |

Insight/EVM subset: BAC AED 12.5 M · EV 4.18 M · AC 4.31 M · CPI 0.970 · SPI 1.032 · EAC 12.887 M.

Personas: Site Engineer (Daud Patel) · PM (Vikram Rao) · Material Buyer (Jin Lee) ·
Plant Allocation Lead (Sridhar Iyer) · HR Coordinator (Mariam Khoury) ·
Cost Engineer (Rohan Menon) · HSE Officer (Pravin Ahmed) · Site Logistics (Ahmed Hassan).

---

## 2 · What exists on disk

```
C:\Users\Ziya\Documents\Claude\sapui5-rt-1.150.0\      SAPUI5 1.150.0 runtime (full dist)

…\Products\konstrux\Konstrucx\
├── KONSTRYX_UI5_App\        ← THE ACTIVE WORK. Real SAPUI5 app. Start here.
├── KONSTRYX_Wireframe_v12\  ← the HTML wireframe · 41 modules · 434 screens
│   └── fiori\               ← a UI5-Web-Components re-render of v12 (see §5)
└── _to_delete\              ← transfer archives + the superseded fiori build, safe to delete
```

The wireframe v12 is the **content reference** — it holds the agreed screen designs and all
the sample data. The UI5 app is the **product reference** — how it should actually be built.

---

## 3 · The UI5 app — current state

`KONSTRYX_UI5_App/` is a real SAPUI5 project, not converted HTML.

```
├── start-konstryx.bat     launcher: Python if present, else PowerShell
├── serve.py / serve.ps1   static server; maps /resources → the 1.150.0 runtime
├── ui5.yaml               for `npx ui5 serve` (UI5 Tooling)
└── webapp/
    ├── index.html         bootstraps resources/sap-ui-core.js · sap_horizon · compact
    ├── Component.js       UIComponent · router started after root view exists
    ├── manifest.json      routes, targets, models, libraries
    ├── controller/        App · Launchpad · Worklist · RequestDetail · ChainStep · NotFound · Base
    ├── view/              XML views + ProcessChain.fragment.xml
    ├── model/             models.js + data.json  ← ALL sample data lives here
    └── i18n/ css/ img/
```

**Built:** the EQR thread `RR-2026-0188` end to end across all ten steps. Each step is its own
route (`#/doc/RR-2026-0188/7`) and object page. The document-flow strip is live — clicking a
node navigates to that document of that thread. Worklists exist for all ten document types.
Browser back/forward and deep links work.

**Not built:** MR / MPR / VR threads are listed in worklists but not drilled. SCR and SF are
absent. Procurement (Pass B) chains are absent. No CAP backend — JSONModel only.

**Navigation is grouped by process phase, not by module** — ① Request & Source, ② Commit &
Execute, ③ Change & Close. This was explicit feedback; do not revert to a module list.

### Running it

```
start-konstryx.bat            # or:
npx ui5 serve --port 8080     # UI5 Tooling; uses OpenUI5, compiles the theme on the fly
```

A SAPUI5 app **cannot** run from `file://` — XML views, `manifest.json` and i18n are fetched
over XHR, which Chrome blocks for local files. The framework loads and the shell renders
empty, with no error. Always serve it.

### Extending it — the cheap path

The chain rendering is data-driven. To add the MR thread, extend `webapp/model/data.json`:
give `RR-2026-0148` its `lines` array, add its ten `chain` entries, add a matching `lineTexts`
block. **No new views or controllers needed** — `ChainStep` renders any step from its
`fields`, `lineExtra` and `actions`. A genuinely different floorplan (the SF PL-INS 3-step
wizard, say) needs one view + controller + one route in `manifest.json`.

---

## 4 · Traps that cost real time — do not rediscover these

**UI5 · start the router after the root view exists.** `Component.init()` runs before the
async root view is created. `getRouter().initialize()` there fires the first route match while
the target `NavContainer` is still undefined; the shell renders, the content area stays blank,
and nothing is logged. Use `this.rootControlLoaded().then(...)` — see `Component.js`.

**UI5 · `routing.config` needs `"type": "View"` and `"path"`.** Without `type`,
`Target._place` skips the entire load-and-place branch silently — no view, no error anywhere
in the log. With `type: "View"` the target resolves the view from `path`, not the legacy
`viewPath`. Keep both keys; they are cheap.

**UI5 · a rootView with an explicit `id` breaks `controlId` resolution.** Leave `rootView.id`
out of the manifest.

**Testing without SAPUI5 · OpenUI5 npm packages ship sources, not built theme CSS.** A plain
static server renders unstyled. Use `npx ui5 serve`, which compiles the theme. UI5 Tooling
also refuses to start if `@openui5/*` packages are in `package.json` — "duplicate framework
dependency definition".

**Wireframe v12 HTML edits · section-bounded only.** Scope every patch to one
`<section class="page" data-page="X">`; greedy cross-section regex corrupted `operations.html`
once. Navigation there is `goRoute('route')`, never `navigate()`. Verify tag balance after
every patch.

---

## 5 · What was tried and rejected — don't repeat it

Two earlier attempts converted the 434 static wireframe screens into "Fiori":

1. **UI5 Web Components** (`v12/fiori/`) — genuine SAP components, offline bundle, all 41
   modules converted mechanically. Rejected: it is a re-skinned wireframe, not the product.
2. **The same, tuned** — compact density, content-sized table columns, single-row filter
   bars. Still rejected for the same reason.

The lesson, in Satish's words: he wants **"an exact replica of how it will look when we
developed"** — real routing, real drill-down, real object pages. Mechanical conversion of the
wireframe cannot produce that. Build the app; use the wireframe as the content spec.

`v12/fiori/` still works and is fine as a stakeholder walkthrough of all 434 screens. It is
not the direction of travel.

---

## 6 · Suggested next steps

1. Fill in MR, MPR and VR threads in `data.json` (data-only, per §3).
2. Add the procurement branch (Pass B): PR → Ariba RFQ → Bid Analysis → PO → GR, as its own
   route group hanging off a line's routing decision. Bid Analysis is the KONSTRYX-owned step.
3. Replace the JSONModel with a CAP OData V4 service — the CDS entities fall straight out of
   `data.json`'s shape. That is the point where this stops being a prototype.
4. SF Plant Return: the PL-INS 3-step wizard is the most distinctive screen in the product and
   the best test of whether the UI5 patterns hold up.

---

## 7 · Working preferences

- Satish is an SAP solution architect; write for that level. No hand-holding.
- Verify before claiming. Two rounds were lost to "it works" claims that were only true in a
  headless harness. Run the app, click the thing, then say it works.
- When a request is ambiguous, ask early rather than build the wrong thing thoroughly.
