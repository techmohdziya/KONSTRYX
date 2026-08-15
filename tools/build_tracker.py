"""KONSTRYX build tracker — status, decisions, open questions, sequence, issues."""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = r"C:\Users\Ziya\Documents\Claude\Projects\KONSTRYX DEV\KONSTRYX_Status_Tracker.xlsx"
FONT = "Arial"

NAVY = "1F3864"
BLUE = "2E5C8A"
GREY = "F2F2F2"
GREEN = "C6EFCE"
AMBER = "FFEB9C"
RED = "FFC7CE"

thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)


def header(ws, row, cols, fill=NAVY):
    for i, c in enumerate(cols, start=1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = 28


def title(ws, text, sub, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=text)
    c.font = Font(name=FONT, bold=True, size=14, color=NAVY)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    s = ws.cell(row=2, column=2 - 1, value=sub)
    s.font = Font(name=FONT, size=9, italic=True, color="595959")
    ws.row_dimensions[1].height = 20


def body(ws, start_row, rows, widths, status_col=None):
    for r, data in enumerate(rows, start=start_row):
        for i, v in enumerate(data, start=1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.font = Font(name=FONT, size=9)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = BORDER
        if status_col:
            s = ws.cell(row=r, column=status_col).value
            fill = {"Done": GREEN, "In progress": AMBER, "Not started": None,
                    "Blocked": RED, "At risk": RED, "Open": AMBER,
                    "Decided": GREEN, "Broken": RED, "Closed": GREY,
                    "YES": GREEN, "OPEN": AMBER}.get(s)
            if fill:
                ws.cell(row=r, column=status_col).fill = PatternFill("solid", fgColor=fill)
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


wb = Workbook()

# ------------------------------------------------------------------ 1. Status
ws = wb.active
ws.title = "Status Report"
title(ws, "KONSTRYX — Build Status Report",
      "Product: SAP BTP extension for EC&O · CAP Java + SAPUI5 · dedicated deployment per client", 6)

ws["A4"] = "Snapshot"
ws["A4"].font = Font(name=FONT, bold=True, size=11, color=NAVY)

header(ws, 5, ["Metric", "Count", "", "", "", ""])
metrics = [
    ("Work items total", '=COUNTA(\'Work Items\'!B6:B100)'),
    ("Done", '=COUNTIF(\'Work Items\'!E6:E100,"Done")'),
    ("In progress", '=COUNTIF(\'Work Items\'!E6:E100,"In progress")'),
    ("Not started", '=COUNTIF(\'Work Items\'!E6:E100,"Not started")'),
    ("Blocked / at risk", '=COUNTIF(\'Work Items\'!E6:E100,"Blocked")+COUNTIF(\'Work Items\'!E6:E100,"At risk")'),
    ("Decisions taken", '=COUNTA(Decisions!B6:B100)'),
    ("Decisions open (need you)", '=COUNTIF(\'Open Decisions\'!F6:F100,"Open")'),
    ("Known issues open", '=COUNTIF(Issues!F6:F100,"Open")+COUNTIF(Issues!F6:F100,"Broken")'),
]
for r, (label, formula) in enumerate(metrics, start=6):
    ws.cell(row=r, column=1, value=label).font = Font(name=FONT, size=10)
    c = ws.cell(row=r, column=2, value=formula)
    c.font = Font(name=FONT, size=10, bold=True)
    c.alignment = Alignment(horizontal="center")
    ws.cell(row=r, column=1).border = BORDER
    c.border = BORDER

ws["A16"] = "What is running right now"
ws["A16"].font = Font(name=FONT, bold=True, size=11, color=NAVY)
running = [
    ["CAP Java service", "http://localhost:8090", "8 OData V4 services, H2, seeded, auth enforced"],
    ["UI5 app", "http://localhost:8081", "serve.py proxies /odata to 8090 (same origin)"],
    ["Repository", r"C:\Users\Ziya\Documents\Claude\Projects\KONSTRYX DEV", "git, 9 commits"],
    ["Reference (read-only)", "OneDrive Products/konstrux/Konstrucx", "FTS, wireframe v12, requirements, backlog"],
]
header(ws, 17, ["Component", "Location", "Notes", "", "", ""])
body(ws, 18, running, [34, 46, 62, 20, 20, 20])

# -------------------------------------------------------------- 2. Work Items
ws = wb.create_sheet("Work Items")
title(ws, "Work Items — planned and completed",
      "Status: Done · In progress · Not started · Blocked · At risk", 7)
header(ws, 5, ["ID", "Workstream", "Item", "Detail", "Status", "Evidence / verification", "Next action"])

items = [
    ("P-01", "Platform", "JDK 17 + Maven toolchain", "SapMachine 17.0.20, Maven 3.9.16, JAVA_HOME set at user scope", "Done", "java -version / mvn -v both report expected versions", "—"),
    ("P-02", "Platform", "Build workspace + version control", "Repo outside OneDrive at Documents\\Claude\\Projects\\KONSTRYX DEV; git init; .gitignore", "Done", "9 commits on main", "—"),
    ("P-03", "Platform", "CAP Java service builds and runs", "Fixed 5 blocking defects in the Sprint 0 skeleton", "Done", "All 8 OData V4 services return metadata and data", "—"),
    ("P-04", "Platform", "Local DB + mock personas", "H2 embedded, 5 mock users mirroring xs-security role templates", "Done", "Persona-based 403s observed as designed", "—"),
    ("P-05", "Platform", "Test data separated from product data", "13 fixtures moved db/data -> test/data; both Node and Java config layers set", "Done", "cds build --production emits only currency code list; no PRJ-001/Emaar in output", "—"),
    ("P-06", "Platform", "Document number ranges", "Configurable per object: scope GLOBAL or COMPANY, and pattern, set independently", "Done", "GLOBAL issues RR-2026-0001/RES-2026-0001; COMPANY issues BUD-INFC-2026-0001 and BUD-PMI-2026-0001 advancing independently; numbers issued on draft activation, not draft creation", "—"),
    ("A-01", "Authorization", "Authorization model (S/4 style)", "AuthObject + Activity + Persona + PersonaPermission + UserAssignment scoped by company/project", "Done", "Catalogue: 7 modules, 21 objects, 6 activities", "—"),
    ("A-02", "Authorization", "EffectivePermission view", "Flattens assignments x grants to answer 'what can this person do'", "Done", "23 rows resolved for the 4 seeded personas", "—"),
    ("A-03", "Authorization", "Runtime enforcement handler", "Activity check + company/project instance filtering on every CRUD event", "Done", "Scoped user sees 4 of 5 requests; unrestricted sees 5; own $filter still ANDs; no grant = 403", "—"),
    ("A-04", "Authorization", "Write-path input-data check", "Reject CREATE/UPDATE carrying a project outside the user's scope", "Not started", "—", "Validate after Project Setup exists"),
    ("A-05", "Authorization", "Administration UI", "S/4-like screens to maintain personas, grants, assignments", "Not started", "—", "Part of Masters/Admin UI block"),
    ("F-01", "Frameworks", "Approval framework model", "Schemes per object type, ordered steps, approver persona, value bands, runtime instances", "Done", "Compiles; exposed on /collaboration", "Engine not built"),
    ("F-02", "Frameworks", "Approval engine", "Instantiate on submit, match value bands, advance steps, audit", "Not started", "—", "After Budgeting model"),
    ("F-03", "Frameworks", "Attachments model", "Polymorphic on entityName+objectID, media-type content, categories", "Done", "Compiles; exposed on /collaboration", "Upload handler + object store not built"),
    ("F-04", "Frameworks", "Attachment upload + storage", "Object store binding for Cloud Foundry vs HANA LOB", "Not started", "—", "Decision needed (see Open Decisions)"),
    ("F-05", "Frameworks", "Table personalization store", "UserVariant entity holding UI5 p13n state per user", "Done", "Compiles; exposed on /collaboration", "Not wired to any table yet"),
    ("F-06", "Frameworks", "Table personalization UI wiring", "p13n + VariantManagement on every list screen", "Not started", "—", "Apply as each screen is built"),
    ("M-01", "Data model", "Workflow spine RR->ADV->AVC->RES", "Vertical-agnostic, multi-line, seeded with canonical EQR thread", "Done", "Queryable over OData; 5 lines, AED 685,080", "—"),
    ("M-02", "Data model", "WBS on request line", "Spec section 6 requires one WBS per line; was missing", "Done", "3 distinct WBS across the 5 EQR lines", "—"),
    ("M-03", "Data model", "EQR vertical extension", "Instances, mob/demob window, own-vs-rental, vendor, operators", "Done", "$expand=equipment,wbs returns all 5 lines resolved", "—"),
    ("M-04", "Data model", "Chain steps CMT/MOB/OPL/VAR/DMB/CLS", "Steps 5-10 have no CDS entities at all", "Not started", "—", "Part of Project Execution block"),
    ("U-01", "UI", "RR worklist on live OData", "RequestOverview projection, server-side filters", "Done", "Verified in browser: 4 requests, EQR shows 5 lines / 685,080; EQR filter issues new $batch", "—"),
    ("U-02", "UI", "Request detail page on OData", "Still reads webapp/model/data.json", "Not started", "—", "Now unblocked by M-03"),
    ("U-03", "UI", "Chain step pages on OData", "Still read data.json", "Blocked", "—", "Blocked by M-04"),
    ("U-04", "UI", "Launchpad intents declared", "crossNavigation inbounds for KonstryxResourceRequest and KonstryxReservation", "Done", "manifest parses; two inbounds registered", "—"),
    ("U-05", "UI", "Launchpad-hosted shell (blend with S/4)", "App must render inside the Fiori launchpad shell; its own sap.tnt.ToolPage chrome duplicates launchpad header, search, user menu and side nav", "Not started", "—", "Strip app shell to content only"),
    ("U-06", "UI", "Spaces and Pages navigation", "S/4 Public Cloud style. Launchpad CONFIGURATION (CDM site / Work Zone), not CDS entities", "Not started", "sandbox2 confirmed present in the local 1.150.0 runtime, so this is reproducible locally", "Build FLP sandbox site"),
    ("U-07", "UI", "Morning Horizon theme", "sap_horizon is Morning Horizon; already the bootstrap theme", "Done", "index.html bootstraps data-sap-ui-theme=sap_horizon", "Must be inherited from the shell once launchpad-hosted, never hard-coded"),
    ("B-01", "Business", "Masters", "Resource hierarchy, CBS library, rates, vendors; scoped GROUP/COMPANY + promotion queue", "Not started", "—", "Start after P-06"),
    ("B-02", "Business", "Templates", "Project templates: CBS tree + default resources", "Not started", "—", "After Masters"),
    ("B-03", "Business", "Project Setup", "Project, WBS, CBS instance; S/4 Enterprise Project mirror", "Not started", "—", "After Templates"),
    ("B-04", "Business", "Uploads", "BOQ import, estimate import, versioning with progress carry-forward", "Not started", "—", "Highest-risk item in the sequence"),
    ("B-05", "Business", "Project Planning", "Activity layer, native entity + P6 adapter", "Not started", "—", "After Uploads"),
    ("B-06", "Business", "Budgeting", "Budget from BOQ/CBS, 4-category ledger, approval, baseline, encumbrance", "Not started", "—", "After Planning"),
    ("B-07", "Business", "Project Execution", "RR->CLS chain end to end, material + manpower", "Not started", "—", "After Budgeting"),
    ("B-08", "Business", "Project Commercial", "Client billing, variations, payment certificates", "Not started", "—", "After Execution"),
    ("B-09", "Business", "Plant Department", "Equipment, fleet, scaffolding/formwork", "Not started", "—", "Last per your sequence"),
    ("D-01", "Deployment", "mta.yaml completion", "No approuter module, no UI module", "At risk", "db-deployer path corrected to db/", "Fix before first CF deploy"),
    ("D-02", "Deployment", "S/4HANA Public Cloud connector", "Mirror entities exist; no connector, no destination wiring", "Not started", "—", "Needs S/4 dev tenant access"),
    ("D-03", "Deployment", "CI/CD pipeline", "Not started", "Not started", "—", "Decision needed"),
]
body(ws, 6, items, [8, 15, 30, 52, 13, 56, 30], status_col=5)
ws.freeze_panes = "A6"

# --------------------------------------------------------------- 3. Decisions
ws = wb.create_sheet("Decisions")
title(ws, "Decisions taken — for your review",
      "Everything here is currently binding. Tell me if any should be reopened.", 7)
header(ws, 5, ["ID", "Date", "Decision", "Rationale", "Decided by", "Impact if reversed", "Status"])

decisions = [
    ("D-01", "2026-08-15", "Runtime is CAP Java, not Node.js", "Skeleton, pom.xml, mta.yaml and generated EDMX are already Java; phase plan staffs 2 CAP Java devs; workload is integration-heavy and long-lived", "Claude (delegated by you)", "High — rewrites pom, mta, handlers and the staffing plan", "Decided"),
    ("D-02", "2026-08-15", "Dedicated deployment per client, not shared multitenancy", "Your instruction. tenant-mode stays dedicated; no MTX sidecar, no SaaS registry", "You", "High — MTX retrofit, HDI-per-tenant, subscription callbacks", "Decided"),
    ("D-03", "2026-08-15", "Code lists ship; business content is an optional import", "Your instruction. db/data holds only what every client legitimately receives", "You", "Medium — changes onboarding and what db/data contains", "Decided"),
    ("D-04", "2026-08-15", "Vertical-specific extension entity per request line", "Your instruction. Six verticals differ genuinely; one flat line entity would be mostly null", "You", "Medium — reshapes all six verticals", "Decided"),
    ("D-05", "2026-08-15", "Evolve the existing freestyle UI5 app to OData V4", "Preserves the app stakeholders already validated as 'how it will look when developed'", "You", "High — discards the validated app", "Decided"),
    ("D-06", "2026-08-15", "First increment is a vertical slice, not platform-first", "Proves CDS + handlers + auth + UI binding end to end before scaling", "You", "Low — sequencing only", "Decided"),
    ("D-07", "2026-08-15", "Build repo outside OneDrive, git-tracked", "OneDrive sync on node_modules/target/gen causes file locks and corrupted builds", "You", "Low", "Decided"),
    ("D-08", "2026-08-15", "CAP Java 4.9.3 + Spring Boot 3.5.6", "CAP Java 3.5.0 rejects cds-compiler 6 shipped by @sap/cds 9; every query returned 500", "Claude (technical)", "Low — but do not drop to 3.x without pinning cds-dk to 8", "Decided"),
    ("D-09", "2026-08-15", "Authorization is configured at runtime, not compiled into XSUAA scopes", "Your requirement for S/4-style in-app administration by project, company and module", "You", "High — the whole auth layer", "Decided"),
    ("D-10", "2026-08-15", "XSUAA Admin role bypasses the data-driven auth layer", "A fresh deployment has no personas or assignments; without it nobody could sign in to create the first one", "Claude (technical)", "Low — but it is a standing privileged path, worth a security review", "Decided"),
    ("D-11", "2026-08-15", "Seeded EQR line values at AED 685,080, not the 716,044 header", "The line values are self-consistent and reconcile exactly to the per-WBS commitment breakdown; the header does not", "Claude (flagged to you)", "Low technically, but the demo numbers must be settled", "Decided"),
    ("D-12", "2026-08-15", "CAP service listens on 8090 locally", "8080 is taken by the UI5 dev server", "Claude (technical)", "Trivial", "Decided"),
    ("D-13", "2026-08-15", "Number range scope is configurable per object, not a product-wide choice", "Your instruction. Scope (GLOBAL/COMPANY) and pattern are configured independently so a client can print the company code while running one group series, or vice versa", "You", "Low — configuration only", "Decided"),
    ("D-14", "2026-08-15", "Document numbers are issued on draft activation, not draft creation", "Abandoned drafts would otherwise burn numbers and leave gaps in the series", "Claude (technical)", "Low, but gap-free numbering is sometimes an audit requirement — confirm if so", "Decided"),
    ("D-15", "2026-08-15", "UI is launchpad-hosted; Spaces and Pages are launchpad configuration, not application data", "Your requirement to blend with S/4HANA. The shell, theme and navigation come from the launchpad; the app renders content only. Modelling spaces as CDS entities was started and abandoned as wrong for this target", "You", "High — supersedes part of D-05; the app's own ToolPage shell must be removed", "Decided"),
    ("D-16", "2026-08-15", "Option A — S/4HANA Public Cloud's own launchpad is the shell, not SAP Build Work Zone", "Users live in S/4 all day, so one shell is the strongest blend. Avoids a Work Zone dependency and licence per client. App registered as IAM External App via LADI -> Business Catalog -> Business Role", "You", "Medium — Work Zone remains available later; app-side work (intents, no own shell) is identical either way, so switching costs launchpad configuration only", "Decided"),
]
body(ws, 6, decisions, [8, 12, 44, 62, 22, 42, 12], status_col=7)
ws.freeze_panes = "A6"

# ---------------------------------------------------------- 4. Open Decisions
ws = wb.create_sheet("Open Decisions")
title(ws, "Open decisions — needed from you",
      "These block or shape work already in the sequence. Ordered by when I need the answer.", 7)
header(ws, 5, ["ID", "Question", "Why it matters", "Options", "Blocks", "Status", "Needed by"])

opens = [
    ("Q-01", "Document number ranges: per company or group-global?", "ANSWERED: configurable per object. Built and verified both scopes", "—", "—", "Closed", "Answered 2026-08-15"),
    ("Q-13", "Where does KONSTRYX surface — Work Zone or the S/4 launchpad?", "ANSWERED: Option A, S/4's own launchpad. See D-16", "—", "—", "Closed", "Answered 2026-08-15"),
    ("Q-14", "Does numbering need to be gap-free for audit?", "Numbers are issued on activation so abandoned drafts do not consume them, but a cancelled document still leaves a gap. Some jurisdictions require unbroken sequences for certain document types", "Gaps acceptable (current) / gap-free required for named document types", "P-06", "Open", "Before Budgeting"),
    ("Q-02", "What is in the EC&O starter content pack?", "You chose 'code lists ship, starter pack as optional import'. I need to know what the pack contains before building the import", "Resource hierarchy depth, CBS library, productivity/consumption norms, trade catalogue", "B-01 Masters, B-02 Templates", "Open", "Before Masters"),
    ("Q-03", "Approval schemes: who approves what, at which value bands?", "The framework is built but has no content. Needs real thresholds per object per company", "Per object type: steps, approver persona, amount bands", "F-02 Approval engine", "Open", "Before Budgeting"),
    ("Q-04", "Attachment storage: SAP Object Store or HANA LOB?", "Object Store needs a CF service instance and changes the upload path; HANA LOB is simpler but costlier at volume", "Object Store (recommended for drawings/photos) / HANA LOB", "F-04", "Open", "Before Uploads"),
    ("Q-05", "The canonical demo numbers do not reconcile", "Wireframe header says AED 716,044; the five line values sum to 685,080 and match the per-WBS commitment split exactly. L1 rate 320/day implies 115,200 not 276,480", "Correct the header to 685,080 / correct L1 rate to 768 / supply the intended figures", "Any stakeholder demo", "Open", "Before first demo"),
    ("Q-06", "BOQ import template — confirm the column set", "Named the highest-risk item in your own requirements register. The importer is built to the template, not the reverse", "Provide the actual client BOQ template(s) you must accept", "B-04 Uploads", "Open", "Before Uploads"),
    ("Q-07", "CBS instance versioning: copy-on-create or live reference to the library?", "Open item in Data Model Spec section 10. Affects whether library changes propagate into running projects", "Copy-on-create (proposed) / live reference", "B-01, B-03", "Open", "Before Project Setup"),
    ("Q-08", "Encumbrance currency: company currency or group reporting currency?", "Open item in Data Model Spec section 10", "Company ccy + group conversion in ins (proposed) / group ccy", "B-06 Budgeting", "Open", "Before Budgeting"),
    ("Q-09", "S/4HANA Public Cloud dev tenant access", "No connector can be built or validated without it. Named as a prerequisite in the phase plan", "Provide tenant + communication arrangements", "D-02", "Open", "Before Project Setup"),
    ("Q-10", "Scope re-baseline: personalization + attachments + approvals on every screen", "Wireframe v12 is 41 modules / 434 screens. The 22-week MVP plan with 1 UI5 developer does not carry this", "Re-baseline the plan / reduce MVP screen scope / add UI capacity", "Overall plan credibility", "Open", "Before committing a client date"),
    ("Q-11", "UI5 production delivery: how is the app served in Cloud Foundry?", "mta.yaml has no approuter and no UI module today, and the app bootstraps from a local runtime path", "Approuter + HTML5 repo (standard) / other", "D-01", "Open", "Before first CF deploy"),
    ("Q-12", "CI/CD tooling", "Prerequisite 4 in the phase plan, still undecided", "SAP CI/CD service / GitHub Actions / Azure DevOps", "D-03", "Open", "Before team scales up"),
]
body(ws, 6, opens, [8, 56, 58, 50, 26, 10, 22], status_col=6)
ws.freeze_panes = "A6"

# ----------------------------------------------------------------- 5. Sequence
ws = wb.create_sheet("Planned Sequence")
title(ws, "Planned build sequence",
      "Your order, with two platform items inserted first because every module inherits them", 6)
header(ws, 5, ["#", "Block", "Contents", "Why here", "Depends on", "Status"])

seq = [
    (1, "Authorization enforcement", "Runtime handler applying configured grants + instance filtering", "Every screen inherits it; retrofitting enforcement after screens exist is where products go wrong", "—", "Done"),
    (2, "Document number ranges", "Configurable scope (GLOBAL/COMPANY) and pattern per object; issued on activation", "Every document module needs it; changing the scheme later means renumbering live data", "Q-01 (answered)", "Done"),
    ("2b", "Launchpad-hosted shell", "Strip the app's own ToolPage chrome; FLP sandbox with Spaces and Pages for local dev", "Blend with S/4HANA. Doing this before the screen count grows avoids stripping the shell out of every screen later", "Q-13", "Not started"),
    (3, "Masters", "Resource hierarchy, CBS library, rates, vendors, scoped GROUP/COMPANY + promotion queue", "Your sequence. Everything downstream references master codes", "Q-01, Q-02", "Not started"),
    (4, "Templates", "Project templates: CBS tree + default resources", "Your sequence. Templates are composed of masters", "Masters", "Not started"),
    (5, "Project Setup", "Project, WBS, CBS instance, S/4 Enterprise Project mirror", "Your sequence. Instantiates a template", "Templates, Q-07, Q-09", "Not started"),
    (6, "Uploads", "BOQ import, estimate import, versioning with progress carry-forward", "Your sequence. Needs a project to import into. Highest-risk item in the plan", "Project Setup, Q-04, Q-06", "Not started"),
    (7, "Project Planning", "Activity layer, native entity + P6 adapter", "Your sequence. Activities hang off WBS", "Project Setup", "Not started"),
    (8, "Budgeting", "Budget from BOQ/CBS, 4-category ledger, approval, baseline, encumbrance", "Your sequence. Needs BOQ and CBS to exist", "Uploads, Q-03, Q-08", "Not started"),
    (9, "Project Execution", "RR->CLS chain end to end, material + manpower, chain steps 5-10", "Your sequence. Consumes budget; encumbrance must exist first", "Budgeting", "Not started"),
    (10, "Project Commercial", "Client billing, variations, payment certificates", "Your sequence. Bills against executed work", "Execution", "Not started"),
    (11, "Plant Department", "Equipment, fleet, scaffolding/formwork", "Your sequence — explicitly after the core", "Execution", "Not started"),
]
body(ws, 6, seq, [5, 30, 62, 66, 26, 13], status_col=6)
ws.freeze_panes = "A6"

# --------------------------------------------------------- 6. Options register
ws = wb.create_sheet("Options Considered")
title(ws, "Options register — what was on the table, and what switching would cost",
      "Kept so any decision can be reopened without re-deriving the alternatives. Chosen option marked.", 7)
header(ws, 5, ["Decision", "Question", "Option", "Chosen", "Trade-off", "Cost to switch to this later", "Reversibility"])

options = [
    ("D-01", "Backend runtime", "CAP Java", "YES", "Matches skeleton, staffing plan and integration-heavy workload; slower inner loop", "—", "Hard — rewrites pom, mta, handlers"),
    ("D-01", "", "CAP Node.js", "", "Fastest iteration, lower memory; contradicts every signed plan document", "Rewrite all service handlers and deployment descriptors", "Hard"),
    ("D-02", "Tenancy", "Dedicated — one deployment per client", "YES", "Simplest to build and certify; upgrade effort scales linearly with clients", "—", "Reversible now, costly per live client later"),
    ("D-02", "", "Shared multitenancy", "", "One upgrade serves all tenants; needs MTX sidecar, SaaS registry, subscription callbacks", "A few days now with zero clients. Per live client later: data copy into a tenant container, freeze window, rollback plan", "Model is tenancy-neutral, so no data reshaping"),
    ("D-03", "Delivered content", "Code lists ship; business content is an optional import", "YES", "Clean tenant databases, content versioned independently", "—", "Easy"),
    ("D-03", "", "Ship a starter EC&O pack in the database", "", "Faster onboarding; becomes product IP you must version and upgrade across tenants", "Move rows from the import into db/data", "Easy"),
    ("D-03", "", "Code lists only, nothing else ever", "", "Purest no-assumptions reading; slowest client onboarding", "Drop the import mechanism", "Easy"),
    ("D-04", "Vertical modelling", "Extension entity per vertical", "YES", "Fits six genuinely different verticals; more entities, polymorphic queries", "—", "Medium"),
    ("D-04", "", "Denormalise onto the request line", "", "Cheaper queries; routing decision then exists in two places and can drift", "Flatten extension entities into the spine", "Medium"),
    ("D-04", "", "Derive routing from AdvisoryDecision", "", "No duplication; cannot express re-sourcing by variation without reopening ADV", "Drop extension entities, add fields to ADV", "Medium"),
    ("D-16", "Launchpad / shell", "Option A — S/4's own Fiori launchpad", "YES", "Strongest blend for users who live in S/4; no Work Zone licence or dependency per client", "—", "Easy — app-side work is identical either way"),
    ("D-16", "", "Option B — SAP Build Work Zone", "", "One entry point across S/4 + SuccessFactors + Ariba + extensions; entitled at 1 user per FUE but another moving part per client", "Launchpad configuration only; no application change", "Easy"),
    ("D-16", "", "Standalone app with its own shell", "", "What exists today. Does not blend — duplicates launchpad chrome", "Keep the ToolPage shell", "Easy"),
    ("D-13", "Number ranges", "Configurable scope and pattern per object", "YES", "Serves both client styles from one build", "—", "Easy"),
    ("D-13", "", "Fixed per company, or fixed global", "", "Simpler; forces one convention on every client", "Remove the scope setting", "Easy"),
    ("D-05", "UI approach", "Evolve the existing freestyle UI5 app", "YES", "Keeps the app stakeholders validated; manual binding work per screen", "—", "Medium"),
    ("D-05", "", "Fiori Elements throughout", "", "Fastest across 434 screens; chain strip, wizards and mass-entry grids do not fit the floorplans", "Regenerate screens from annotations", "Medium"),
    ("D-05", "", "Hybrid — FE for masters, freestyle for chain", "", "Best effort/fidelity ratio at scale; two patterns to maintain", "Adopt incrementally, per module", "Easy"),
    ("Q-04", "Attachment storage", "SAP Object Store", "OPEN", "Right for drawings and photos at volume; needs a CF service instance", "—", "Medium once files exist"),
    ("Q-04", "", "HANA LOB", "OPEN", "Simpler, no extra service; costlier at volume and bloats the container", "—", "Medium once files exist"),
]
body(ws, 6, options, [10, 22, 44, 9, 60, 56, 34], status_col=4)
ws.freeze_panes = "A6"

# ------------------------------------------------------------------ 7. Issues
ws = wb.create_sheet("Issues")
title(ws, "Issues, risks and things that broke",
      "Defects found and fixed are listed too, so the history is visible", 7)
header(ws, 5, ["ID", "Area", "What happened", "Impact", "Resolution", "Status", "Raised"])

issues = [
    ("I-01", "CAP build", "BudgetServiceHandler imported com.sap.cds.services.cds.CdsService, which does not exist", "Service would not compile", "Replaced with EventContext", "Closed", "2026-08-15"),
    ("I-02", "CAP build", "pom used cds-starter-spring-boot, which carries no protocol adapter", "All 6 services registered but exposed ZERO HTTP endpoints, silently", "Switched to cds-starter-spring-boot-odata", "Closed", "2026-08-15"),
    ("I-03", "CAP build", ".cdsrc.json set build.target=gen (Node layout)", "Compiled model never reached srv resources; runtime started with an empty catalogue", "Removed; Java build now writes in place", "Closed", "2026-08-15"),
    ("I-04", "CAP build", "CAP Java 3.5.0 rejects cds-compiler 6 from @sap/cds 9", "Every query returned HTTP 500", "Upgraded to cds-services 4.9.3 / Spring Boot 3.5.6", "Closed", "2026-08-15"),
    ("I-05", "Deployment", "mta.yaml declared build-result target/*-exec.jar but build produced konstryx-srv.jar", "A Cloud Foundry deploy would have failed", "Added the exec classifier", "Closed", "2026-08-15"),
    ("I-06", "Deployment", "mta.yaml db-deployer pointed at gen/db, which the Java build does not produce", "HDI deploy would have failed", "Corrected path to db/", "Closed", "2026-08-15"),
    ("I-07", "Data safety", "Demo fixtures were in db/data, which CAP deploys to every environment", "PRJ-001 Marina Heights would have landed in client databases", "Moved 13 fixtures to test/data; both config layers set; cloud profile pins initialization-mode never", "Closed", "2026-08-15"),
    ("I-08", "UI", "Proxy dropped the OData-MaxVersion header", "CAP answered OData-Version 4.01; UI5 V4 model rejected the batch, table silently empty", "Proxy now forwards headers wholesale rather than by allowlist", "Closed", "2026-08-15"),
    ("I-09", "Authorization", "Handler matched the service projection name against the persistence entity name (plural vs singular)", "Handler silently protected NOTHING. Early 403s came from pre-existing service-level @requires, not from the handler", "Resolves the projection to its source entity via CDS model reflection", "Closed", "2026-08-15"),
    ("I-10", "Authorization", "CQL.copy with a Modifier only fires where() when a WHERE already exists", "Unfiltered list requests — the common case — passed through unrestricted", "Switched to Select.copy with an explicit predicate", "Closed", "2026-08-15"),
    ("I-11", "Authorization", "Select.where() replaced rather than ANDed the caller's filter", "User $filter was discarded; more rows returned than requested", "Existing predicate now combined explicitly with CQL.and", "Closed", "2026-08-15"),
    ("I-12", "Deployment", "mta.yaml has no approuter module and no UI module", "Cannot deploy to Cloud Foundry at all yet", "—", "Open", "2026-08-15"),
    ("I-13", "Demo data", "Wireframe request header (716,044) does not reconcile with its own line values (685,080)", "Any stakeholder demo shows inconsistent totals", "—", "Open", "2026-08-15"),
    ("I-14", "Plan", "Personalization, attachments and approvals on every object were not in the 22-week MVP estimate", "Plan credibility; 434 screens each inherit this layer", "—", "Open", "2026-08-15"),
    ("I-15", "Authorization", "Admin persona cannot read workflow/project services", "Service-level @requires still gates entry by XSUAA role; the Admin mock user lacks those roles", "By design today, but role collections need reviewing before go-live", "Open", "2026-08-15"),
    ("I-16", "Upgrade safety", "Client configuration in db/data is reset on every upgrade", "cds build --production generates konstryx.nr-NumberRangeObject.hdbtabledata. HDI re-imports managed rows on redeploy, so a client who changes a number range scope or pattern would silently have it reverted at the next upgrade. NumberRangeObjects is writable in the service, so this is reachable", "Move client-configurable rows out of db/data into the one-time onboarding import; keep db/data for immutable delivered catalogue only (Activity, Module, AuthObject, Currencies - all @readonly)", "Open", "2026-08-15"),
]
body(ws, 6, issues, [8, 16, 62, 50, 56, 10, 12], status_col=6)
ws.freeze_panes = "A6"

for sheet in wb.worksheets:
    sheet.sheet_view.showGridLines = False

wb.save(OUT)
print("written:", OUT)
