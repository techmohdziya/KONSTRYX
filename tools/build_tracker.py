"""KONSTRYX build tracker — status, decisions, open questions, sequence, issues."""
import io
import os
import subprocess

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
    # A row with one field too many does not fail, it slides. Everything past
    # the extra field moves a column right: Status lands under the next header,
    # takes no colour because the value there is prose rather than a state, and
    # the last field spills into a column with no header at all. The sheet still
    # opens and still looks like a sheet. Two rows had been sitting like that.
    #
    # widths is per-column, so it already knows how wide the table is.
    for r, data in enumerate(rows, start=start_row):
        # Overflow only. A short row leaves its trailing cells empty, which is
        # how the small fixed blocks on the summary sheet are written and is
        # visibly a gap. A long one is the silent case.
        if len(data) > len(widths):
            raise SystemExit(
                f"Row {data[0]!r} has {len(data)} fields for {len(widths)} columns. "
                f"A row that overflows its sheet reports the wrong thing in the "
                f"right-looking place, so this refuses rather than writes it.")
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
                    "YES": GREEN, "OPEN": AMBER, "Adopted": GREEN}.get(s)
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
    ("Suggestions open", '=COUNTIF(Suggestions!F6:F100,"Open")'),
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
# Counted, not typed. This block said "8 OData V4 services" against nine and
# "48 commits" against a hundred and thirty-nine — both true once, and a figure
# that is only true once is worse than no figure, because it is read as current.
def _service_count(repo):
    try:
        import glob
        import re
        names = set()
        for path in glob.glob(os.path.join(repo, "srv", "*.cds")):
            with io.open(path, encoding="utf-8") as f:
                names.update(re.findall(r"^service\s+(\w+)", f.read(), re.M))
        return len(names)
    except Exception:
        return None


def _git(repo, *args):
    try:
        out = subprocess.run(["git", "-C", repo, *args], capture_output=True,
                             text=True, timeout=20)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_services = _service_count(REPO)
_commits = _git(REPO, "rev-list", "--count", "HEAD")
_dirty = _git(REPO, "status", "--porcelain")
_last = _git(REPO, "log", "-1", "--date=short", "--format=%ad")

_repo_state = "git" + (f", {_commits} commits" if _commits else "")
if _last:
    _repo_state += f", last {_last}"
if _dirty is not None:
    changed = len([line for line in _dirty.splitlines() if line.strip()])
    # A commit count on its own reads as "this is what is saved". It is not,
    # while a working tree is this far ahead of it.
    _repo_state += (f", {changed} file(s) uncommitted" if changed
                    else ", working tree clean")

running = [
    ["CAP Java service", "http://localhost:8090",
     (f"{_services} OData V4 services" if _services else "OData V4 services")
     + ", H2, seeded, auth enforced"],
    ["UI5 app", "http://localhost:8081", "serve.py proxies /odata to 8090 (same origin)"],
    ["Repository", r"C:\Users\Ziya\Documents\Claude\Projects\KONSTRYX DEV", _repo_state],
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
    ("P-07", "Platform", "Delivered content pack mechanism", "Versioned packs applied insert-if-missing, in version order; ships in the jar and readable from ./content; applyContentPacks admin action for upgrades without restart", "Done", "Client edit survived an upgrade pack that contained the same row: 1 inserted, 1 left untouched, client scope preserved", "Reuse for the EC&O starter pack (Q-02)"),
    ("P-06", "Platform", "Document number ranges", "Configurable per object: scope GLOBAL or COMPANY, and pattern, set independently", "Done", "GLOBAL issues RR-2026-0001/RES-2026-0001; COMPANY issues BUD-INFC-2026-0001 and BUD-PMI-2026-0001 advancing independently; numbers issued on draft activation, not draft creation", "—"),
    ("A-01", "Authorization", "Authorization model (S/4 style)", "AuthObject + Activity + Persona + PersonaPermission + UserAssignment scoped by company/project", "Done", "Catalogue: 7 modules, 21 objects, 6 activities", "—"),
    ("A-02", "Authorization", "EffectivePermission view", "Flattens assignments x grants to answer 'what can this person do'", "Done", "23 rows resolved for the 4 seeded personas", "—"),
    ("A-03", "Authorization", "Runtime enforcement handler", "Activity check + company/project instance filtering on every CRUD event", "Done", "Scoped user sees 4 of 5 requests; unrestricted sees 5; own $filter still ANDs; no grant = 403", "—"),
    ("PS-01", "Project Setup", "Projects and WBS mastered in KONSTRYX", "Draft-enabled and writable; code uniqueness, date agreement, company required, hierarchy cycle guard; sync state protected from hand-editing on both the active record and the draft", "Done", "20 checks: a new project activates NOT_SENT; release refuses a project with no WBS, queues one that has it, refuses a second release; the connector callback moves it FAILED then SENT with the refusal text and attempt count kept", "Primavera import (PS-03)"),
    ("PS-02", "Project Setup", "Outbound sync aspect", "s4outbound, separate from s4mirror because the two directions need opposite defaults — a project created here starts NOT_SENT, not OK", "Done", "Seeded projects read SENT; a new one reads NOT_SENT", "The connector itself needs Q-09"),
    ("PS-03", "Project Setup", "Primavera P6 project import", "P6 XML export creates the project and its WBS tree in one file, through ProjectService so the same validation applies. No PARTIAL mode: a tree only means anything whole. DTDs and external entities switched off on the parser", "Done", "15 checks: dry run changes nothing; a child WBS parents correctly despite preceding its parent in the file; re-import leaves exactly one project and four elements; an XXE attempt is refused and leaks nothing", "P6 activities and the schedule itself are not imported — see S-31"),
    ("PL-02", "Planning", "WBS distribution by template", "TPL-SINGLE / TPL-FLOORS / TPL-ZONES: one decision covers many lines; weighted split with the rounding residue on the last target so VAL-02 passes to the third decimal; re-running replaces rather than stacks; template and splitBasis on every allocation row", "Done", "18 checks: 40/35/25 gives 480/420/300 exactly; thirds of 1000 keep the millimetre; the bulk path takes the whole bill in one decision and the gate flips to Pass", "Distribute dialog on the workbench UI"),
    ("PL-03", "Planning", "Cost Mapping workbench", "Four step tiles (CBS / WBS / Resources / Gate) and an exceptions-only queue with reasons and modest CBS suggestions; Generate Budget Lines disabled while the gate fails, tooltip names why (UI-04). The queue names unrated resources as work items instead of a generate treadmill", "Done", "Browser-verified: 9 honest exceptions across three reasons on the canonical fixture; console clean", "Distribute + rate-fix flows from the queue rows"),
    ("UI-01", "UI", "Projects, BOQ and assigned-CBS screens", "Projects worklist (workplace group, not Masters); BOQ with the canonical F.1 lines, contract vs budget qty side by side, build-up drill, Generate Build-up and Check Gate actions; assigned-CBS screen showing the node, its recipe norms with company variants, and its bill lines", "Done", "Browser-verified: pile-cap shows all 7 published lines summing 1,198.95/m3; the 03.20 link popover leads with the assigned node; console clean", "Cost Mapping workbench (exceptions only, UI-01 of the spec) is next"),
    ("UI-02", "UI", "S/4-style object links, per-user configurable", "An object key is a hyperlink; one target navigates, several open a popover; which targets appear is each user's own choice, persisted through UserVariants. Transaction targets lead; masters are secondary", "Done", "PRJ-001 offers BOQ + Resource Requests; 03.20 offers Assigned CBS + Library", "Roll the registry across every remaining screen with task #12"),
    ("D-23x", "Data", "Canonical mockup data seeded (spec F.1)", "03.10/03.20/03.30 leaves with grade on the attached material row; MP-CIV-CAR-SK-G1 with ALL 1.13 / INFC 1.25 / PMI 0.95; the pile-cap 7-line build-up as IMPORTED at the published figures", "Done", "Per-m3 sum 1,198.95 matches the wireframe to the fils; OPEN-05 residual seeded as published, not invented into agreement", "—"),
    ("F-11", "Frameworks", "A person can read their own import history", "MyImportRuns and MyImportRows, narrowed to what that person uploaded", "Done", "The importing user reads back three runs including 'line 1: Project code DHV-P3 already exists'", "—"),
    ("A-04", "Authorization", "The scope was a rule about looking, not about doing",
     "Reads have been narrowed to the projects and companies a persona reaches since the control was built. Writes were checked for the activity alone -- may this person create requests at all -- and never for where the write landed, so somebody assigned to one job could raise a document naming another, or move one they already had onto a project they have no part in, and it would be kept. Verified before building: a user scoped to PRJ-001 raised and activated a request on PRJ-002 and the row stood",
     "Done",
     "The same predicate the read filter uses, extracted so there is one owner of what a grant reaches. Written twice it would drift, and drift silently in the direction that matters. Checked AFTER the write rather than on the payload: the scope paths are expressions over the stored row -- project.code, and four hops on some objects -- and the only thing that can evaluate those is the database with the row in it. Reading the payload would mean walking associations by hand in a second implementation of the read filter, and the two would disagree the first time a path changed. So the row is written, asked about through the same predicate, and the refusal unwinds the change set. Delete is checked before instead, because afterwards there is nothing left to ask about. The boundary is activation, not the draft: a draft is private and not yet a document, which is what the suite already said about the activity check", "test_foundations 1b: a project-scoped user refused on another project and nothing kept, a company-scoped user refused in another company, and a row already in scope refused when moved out of it -- the case no payload check could have answered, because what makes the write wrong is where the row ends up"),

        ("A-05", "Administration", "Administration UI",
     "S/4-like screens to maintain personas, grants, assignments",
     "Done",
     "Three Fiori Elements apps on the authorization service, on Master Data / "
     "Configuration: Personas with their grants as a facet, User Assignments, and "
     "Approval Schemes with the steps beneath them. The catalogue is pickable rather "
     "than typed -- a grant was three UUIDs and is now object, activity, granted, with "
     "value helps living once on the service. 16 checks: a persona is started, granted "
     "in its draft and activated, and reads back with what was granted; copyAs carries "
     "every grant, never marks the copy as delivered, and refuses a duplicate or blank "
     "code",
     "The scheme screen is what makes F-16 answerable without hand-written OData"),
    ("F-01", "Frameworks", "Approval framework model", "Schemes per object type, ordered steps, approver persona, value bands, runtime instances", "Done", "Compiles; exposed on /collaboration", "—"),
    ("F-02", "Frameworks", "Approval engine", "Instantiate on submit, match value bands, advance steps, enforce approver persona and separation of duties, delegate, withdraw, audit", "Done", "28 checks against the running service: bands select 1/2/3 steps at 50k/300k/2m; out-of-order, double, reasonless and same-person decisions all refused; persona configured through the admin API then enforced", "Inbox screen (F-04) and per-object wiring (F-05)"),
    ("F-04", "Frameworks", "Approval inbox screen",
     "The steps awaiting the signed-in user, with approve and reject",
     "Done",
     "MyApprovals is a projection narrowed as it is read by the same three rules the "
     "decide path enforces, so filtering, sorting, paging and $count all run over the "
     "rows the reader is entitled to; list report on Execution / Today with a dynamic "
     "tile reading the person's own count. 17 checks: a step naming no approver is open "
     "to all seven demo users, naming Project Manager leaves every inbox but its "
     "holder's, reading decides nothing, and a row opened from the list is one the "
     "engine accepts — including its refusals",
     "Opening the document from a row needs a semantic object per document kind (U-18)"),
    ("D-05", "Deployment", "An app has three registers and the scaffold wrote two",
     "konstryx-pull, konstryx-consumption and konstryx-resvariation had manifests, "
     "annotations and launchpad tiles, and no module in mta.yaml -- a deploy would "
     "build 30 of 33 and offer three tiles that resolve to nothing. The cause was not "
     "the apps: tools/scaffold_app.py registers annotations in services.cds and the "
     "app in package.json sapux, and its own docstring says it adds the app 'where the "
     "build looks for apps' -- but the deploy looks in mta.yaml, which it never wrote. "
     "Every app scaffolded by it inherited the same hole. Separately, seven Fiori "
     "Elements apps were missing from sapux, so the tooling did not count them as its "
     "own. The freestyle konstryx-ui is legitimately absent from that list, having no "
     "Fiori Elements target at all",
     "Done",
     "All 33 apps are modules with matching deployer artifacts and all 32 Fiori "
     "Elements apps are in sapux; the scaffold now writes mta.yaml as well, so the "
     "next one cannot repeat it; test_foundations refuses an app missing from any of "
     "the three registers",
     "Still unverified against a real Cloud Foundry deploy, which is D-04"),

    ("A-08", "Administration", "copyAs was declared and had no handler",
     "The action was in the service contract with a doc comment describing it, and "
     "nothing implemented it -- calling it returned 500 \"No ON handler completed the "
     "processing\". Found by exercising the button the new persona screen puts on the "
     "list, which is the only way a declared-but-absent surface shows itself. Now "
     "copies the persona and all its grants, clears isDelivered because a copy is not "
     "product content whatever it was copied from, and refuses a duplicate code -- two "
     "personas answering to one code make an assignment ambiguous",
     "Done", "Verified end to end: 10 grants copied, 409 on a duplicate, 400 on a blank code", "—"),

    ("F-19", "Frameworks", "The launchpad computes rich numbers and shows plain ones",
     "launchpadKpis returns thirteen tiles with a number, a unit, a subtitle and a "
     "state computed from the number — its own doc comment argues that a tile reading "
     "only its name makes the launchpad a menu, and that one call exists so a home "
     "page does not make a dozen. Nothing reads it. The launchpad instead makes 32 "
     "separate $count calls, and for five screens shows the less informative of the "
     "two numbers it could: BOQ shows 5 bills where the KPI has 72.04 M AED of "
     "contract value, and the payment certificates show 5 where the KPI has 2442 K AED "
     "net. Not a contradiction — different quantities, each labelled — but the tiles "
     "took the weaker one",
     "Raised",
     "Now covered either way: the numbers are checked for a screen that exists, a unit "
     "and subtitle, states that vary, and agreement with the list a tile would open",
     "Needs a ruling: an FLP dynamic tile GETs a path and expects a count or the FLP "
     "number shape, so consuming this action means exposing it in a shape the launcher "
     "understands. Which shape is a design decision"),

    ("P-08", "Project", "syncWBSFromP6 had never been called by a test",
     "The action reconciles a live project against a later P6 export and makes four "
     "promises in its own doc comment: match by code rather than create a second "
     "project, leave elements the export has dropped in place because they can carry "
     "budget and signed work, refuse an export naming somebody else's project, and "
     "never touch the programme. All four held when finally exercised — but nothing "
     "had exercised them, and it is the one action in the services that appeared in no "
     "suite, no tool and not even the tracker",
     "Done",
     "test_p6 7: a rename, an addition and a re-parent all land; the dropped branch is "
     "left standing and named in the message so removing it stays a person's decision; "
     "a stranger's export is refused and changes nothing; one project, not two",
     "—"),

    ("P-09", "Project", "The cost mapping workbench is two implementations of one question",
     "costMappingPortfolio answers for every project and costMappingSummary for one, "
     "and the second is documented as the counterpart of the first. Neither had ever "
     "been called by a test, which is how two answers to the same question drift apart "
     "without anyone noticing — a workbench saying a project needs a human while the "
     "project's own page says it does not is worse than either number alone",
     "Done",
     "test_project: 42 comparisons across 7 projects on every count the two share, no "
     "disagreement, and the exception count never exceeds the lines there are",
     "—"),

    ("F-20", "Frameworks", "A derived document is less protected than the one it came from",
     "Measured across the demo tenant: daud sees 5 resource requests, all on PRJ-001, "
     "and all 6 purchase requisitions -- spanning PRJ-001, 002, 004 and 005, three of "
     "them projects whose requests he is refused. So the requisition raised from a "
     "request he cannot read is fully readable to him, with its project, its value and "
     "its vendor. The cause is structural rather than a bug in the enforcement: 70 of "
     "the 101 entities the services project are named by no auth object, so "
     "AuthorizationHandler has no scope path to narrow them by. Persona grants still "
     "gate the entity as a whole -- jin, vikram, rohan and steward_pmi are refused "
     "outright -- but among those who may read at all there is no project or company "
     "scoping. The catalogue itself is clean: no auth object names an entity nobody "
     "projects. Many of the 70 are legitimately open (activities, modules, the auth "
     "catalogue, value-help lists); the ones that are not are documents",
     "Raised", "—",
     "Needs a ruling on which of the 70 become auth objects and with what projectPath "
     "and companyPath -- the mechanism is data-driven and already there, so this is "
     "policy rather than code. Purchase requisitions and orders are the ones in your "
     "stated priority. The invariant worth adopting: a document is never more readable "
     "than the document it derives from"),

    ("U-19", "UI", "Every action dialog asked for its parameter by its variable name",
     "Fiori Elements builds an action dialog from the parameter list and labels each "
     "field with the parameter's own name when nothing else does, so approving a "
     "document asked for 'comment' in lower case, rejecting one asked for 'comment' "
     "again with no hint that the engine refuses a blank, and the P6 sync asked for "
     "'validateOnly'. No @title existed on any action parameter anywhere in the "
     "services. Found by opening the screen -- the metadata, the manifest and the "
     "suites were all correct and none of them could show it",
     "Done",
     "All seven dialogs a screen can open are titled; verified in the browser: the "
     "approve dialog now reads Comment and the reject dialog Reason for rejecting, "
     "which is also the rule the engine enforces",
     "The other 61 actions take no parameters or are not on a button"),

    ("U-20", "UI", "The screens had never been seen, only inferred",
     "Everything built this session was verified through the service and the "
     "annotations, and the standing rule is that a UI claim needs a browser. The "
     "service requires an authenticated user for every entity, so a browser gets a "
     "password box; the way through was a scratch proxy that forwards to 8090 adding "
     "the same basic-auth header the suites already use, with the mock credentials "
     "that live in those suites. Nothing added to the repo",
     "Done",
     "My Approvals renders four rows with Document, Type from the catalogue, Value, "
     "Step and Waiting since carrying the ascending sort the PresentationVariant "
     "declares; selecting a row enables Approve, the dialog takes a comment, the "
     "decision reaches the step with that comment on it, and the row leaves the list "
     "4 -> 3. Personas renders six with their grants, Copy as new, and draft editing",
     "The remaining 31 apps are still unseen; U-19 was the defect one screen produced"),

    ("W-01", "Masters", "The workforce domain the wireframe specifies did not exist",
     "Wireframe v13 grew 20 screens between 26 Aug and 2 Sep, all in Masters, and the "
     "build had four one-line stubs where they belong: WorkforceCatalog, TradeCatalogue, "
     "ShiftPattern and AssetRegister, each carrying a code and a description and nothing "
     "else. Built out in db/wfm.cds -- the working day and its overtime ladder, holiday "
     "calendars, trades with grades and blocking certificates, own workers with their "
     "documents, crew templates with slots, live gangs, absence reasons and an "
     "availability register, the subcontract man held separately from his engagements, "
     "and roster upload. Twenty entities, one namespace, exposed on MasterDataService",
     "Done",
     "test_workforce 33/33: the ladder reads back with cost and charge separate on all "
     "six rungs, a crew rate of 142.00 summed from six slots overwrites a typed 999.99, "
     "a gang of five on a six-slot template reports 5 of 6 and 126.50 against 142.00, a "
     "man on a slot with a lapsed card does not count toward manning, an overlapping "
     "engagement is refused 409 and the same passport twice is refused 409. A "
     "duplicate crew code was possible until a screen showed the same template "
     "listed twice -- the workforce masters now carry the same code-uniqueness "
     "rule the resource hierarchy and rate masters already had",
     "Asset sub-categories (Fix 63) are not built -- they are Equipment Masters, which "
     "your stated priority holds"),

    ("W-02", "Masters", "There was no overtime ladder anywhere in the build",
     "workflow-service.cds said it plainly: overtime is costed at the same all-in hourly "
     "rate as regular time, because an overtime multiplier would be a number invented "
     "here rather than agreed commercially. Wireframe Fix 36 supplies the agreement -- "
     "OT-1 x1.25, night x1.50, rest day x1.50, public holiday x2.50, beyond twelve hours "
     "x2.00, standby x0.70 -- and puts it on the shift pattern as the single place the "
     "four consumers read. Built as a composition on ShiftPattern, with cost and charge "
     "as separate factors on each rung because they are two agreements",
     "Done",
     "Six rungs read back under one pattern; every rung has a charge factor that differs "
     "from its cost factor; standby is below 1.0, so the ladder is not assumed to be a "
     "premium",
     "The timesheet still costs at a flat rate. Wiring sign() to read the pattern is the "
     "next step and changes what a day costs, so it wants your word first"),

    ("W-03", "Masters", "A push that failed left no trace of having failed",
     "releaseToErp recorded FAILED with the reason and then threw, and the throw unwound "
     "the write -- the worker came back NOT_SENT with no message. The wireframe asks for "
     "the opposite: a monitor showing six failed and forty queued, each with a reason, "
     "which only exists if a failure persists. The action now records and returns rather "
     "than throwing",
     "Done",
     "A worker with no trade, shift pattern or cost centre comes back FAILED carrying "
     "'The agreement needs a trade, a shift pattern, a cost centre' and appears in "
     "WorkerPushQueue with it",
     "The push itself is still local -- it sets PENDING and no connector sends it"),

    ("W-04", "UI", "The launchpad rendered a blank page",
     "Three faults. index.html loaded the shell bootstrap from /resources/sap/ushell/"
     "bootstrap/sandbox2.js, a path only the CDS dev server proxies, so the jar and the "
     "UI server both 404 and the page died at 'Missing renderer name'. Then the site "
     "config was not found and the sandbox fell back to its own demo site -- three sample "
     "tiles under 'Sample Space'. Then every tile failed to open its app. Only the first "
     "was real: the second and third I diagnosed against my own proxy onto the CAP "
     "service, where apps sit under /webapp, rather than app/konstryx-ui/serve.py on 8081 "
     "which run-local.bat starts and which already maps /appconfig and /<app> correctly. "
     "Both of those changes were reverted",
     "Done",
     "The bootstrap now loads from the pinned runtime, the same reasoning the file already "
     "gave for sap-ui-core.js. Verified on 8081: the launchpad renders Planning, "
     "Execution, Commercial and Master Data with their real tiles, and a tile opens its "
     "app inside the shell",
     "Nothing outstanding"),

    ("W-05", "UI", "Tile counts read Error, and the product was not at fault",
     "Every dynamic tile showed 'Error' where its number belongs. I recorded it as F-19 -- "
     "the tile wanting an FLP number shape that a bare $count does not give. It was not: "
     "the requests were being aborted by my own scratch proxy, which held connections open "
     "under HTTP/1.1 while a launchpad opened four counts at once",
     "Done",
     "One request per connection in tools/dev_proxy.py, and all 11 Execution tiles answer "
     "with real numbers -- 12 fronts open, 9 requests, 6 requisitions, 6 orders placed, 3 "
     "bills received, 45 days, 2 stock draws",
     "F-19 as originally written is wrong and should be struck: launchpadKpis is still "
     "unconsumed, but the tiles do not need it"),

    ("W-06", "UI", "Twelve screens for the workforce masters",
     "Scaffolded from the app that already deploys, with the columns chosen per entity "
     "rather than templated: trades, shift patterns, holiday calendars, crew templates, "
     "absence reasons, workers, subcontract workers, engagements, roster upload, the work "
     "agreement queue, gangs and availability. Two new sections on Master Data -- "
     "Workforce and People -- and gangs and availability on Execution / Today, because "
     "they are read on site rather than maintained",
     "Done",
     "40 apps across 4 spaces in the generated site; every new app is in mta.yaml, in "
     "sapux and on a page, so none of them is registered without being reachable",
     "Unseen in a browser. The screens compile and the service answers them; nobody has "
     "looked at them"),

    ("F-18", "Frameworks", "A saved list arrangement has nowhere to go",
     "The 32 Fiori Elements list reports use the template's own VariantManagement, "
     "which writes through SAPUI5 flexibility. Nothing configures a flex backend: no "
     "flexibilityServices in any bootstrap, no flex resource in mta.yaml, no route for "
     "/sap/bc/lrep, and the service 404s the default flex path. So a person arranges a "
     "list, saves it, and arranges it again tomorrow. The freestyle konstryx-ui has a "
     "working store for exactly this — CollaborationService.UserVariants, wired in "
     "ListPersonalization.js — which the apps that replaced it do not use",
     "Raised", "—",
     "Needs a ruling between three: bind BTP key-user adaptation (an entitlement, so "
     "it waits on the subaccount with D-04); register a custom flexibilityServices "
     "connector onto the UserVariant store that already exists; or accept that "
     "arrangements do not survive. The connector is buildable now and reuses what is "
     "there, but it cannot be verified without a browser session"),

    ("F-16", "Frameworks", "The delivered approval schemes name no approver",
     "Every step of RR-STD and BUD-STD carries a null approver, which the engine reads "
     "as open to any authorised user. Measured: all seven demo users hold identical "
     "inboxes of the same six steps, and any of them can conclude a two-million "
     "resource request. Naming a persona narrows it correctly, so the engine is right "
     "and the content is empty. Which persona decides each step is an organisational "
     "ruling, and the catalogue has no Director persona for step 3 at all",
     "Raised", "—", "Needs a ruling: the persona per step, and whether a Director persona exists"),

    ("F-17", "Frameworks", "Every user can read every approval instance and step",
     "ApprovalInstances and ApprovalSteps are not in the persona catalogue, so the "
     "authorization handler never narrows them. Measured: rohan, who is refused the "
     "resource requests themselves, still reads the approvals carrying their numbers "
     "and values. MyApprovals is narrowed, but the entities behind it are not",
     "Raised", "—", "Needs a ruling: which auth object governs approval visibility"),

    ("F-05", "Frameworks", "The approval owned neither end of the document it approved",
     "Two halves and both were real. At the front, the caller marked the document In Approval: BudgetHandler and ChainHandler each did it in their own code after calling submit, and the generic submitForApproval action -- which takes any entity name -- marked nothing at all, so a document submitted through it sat in whatever state it was already in while approvers worked on it. Two owners of one fact and a third path with no owner. At the back, the decision reached the status field and nothing else: every other transition a document makes is written to its status history, so a reader takes that history as the account of how it got where it is, and the approval was the one transition missing from it -- the one somebody signed for. Measured on a request driven live: the document read Approved and its history stopped at In Approval",
     "Done",
     "The engine owns both ends, because a caller cannot forget what it does not do. It marks the document on submit and writes the transition, naming the scheme and the value that selected the steps; the two handlers stopped doing it themselves, so the entry is written once rather than once per owner. On close it reads the state it is leaving BEFORE overwriting it -- an entry that guesses where a document came from reads exactly like one that knows -- and files who decided, and what they said. The docType comes off the document number it already carries rather than a table mapping entity names, so a scheme configured for a document this class has never heard of still files under the same heading as that document own transitions", "test_approval 7: approval, rejection and withdrawal each on the document own history, the state it left read not guessed, and the generic action marking it without a caller"),
    ("F-14", "Frameworks", "Two transitions in one request could not be told apart in a status history",
     "StatusHistory ordered on changedOn, stamped from the wall clock. Two moves made inside one request tie on it, and what comes back first is then whatever the store feels like. Found by a check that read the last entry of a withdrawal followed by a resubmission and got the two either way round on successive runs. Measured after building the fix, on a document driven in and out of approval twice: ordering on the clock returned the four entries as 3 2 4 1. On a record whose whole purpose is to say how a document got where it is, that reads as the opposite of what happened",
     "Done",
     "A sequence per document, counted from what is already filed under that number rather than held in a counter, so a document renumbered by ERP carries its numbering across and keeps counting. Per document rather than global for the same reason. The backfill worry in the original note did not apply: nothing is deployed, so there are no rows anywhere that predate the column. Every reader now orders on it, and the check that had to be written as a set can be written as a sequence again -- it asserts the entries are numbered from one without a gap AND that each leaves where the one before it arrived, which is the property that makes an account followable and which no timestamp ordering could have tested", "test_approval 7: the trail reads Approved -> In Approval -> Draft -> In Approval in that order and joins up"),
    ("F-15", "Frameworks", "Only one document type kept a history of how it got where it is",
     "Counted after the approval work: one class in the service wrote status history, ChainHandler, for the three documents it drives. Nineteen other status writes across six handlers wrote none. A variation order went Draft to Submitted to Approved, a budget went to Baselined, a requisition went to Requisitioned and then Ordered, an order to Partly received and then Received, a pull request to Issued or Refused -- and nothing anywhere recorded when, or on whose word. The status field answers where is it now; there was no answer at all to how did it get there, which is the question asked when something is wrong. It was silent because keeping the history was each handler own business, and a thing that is everyone business is nobody",
     "Done",
     "One StatusLog that every handler calls, so a reader sees the same shape whichever document they are reading. Two things the build found by running it rather than by reasoning: deriving the document kind from its number looked right and was wrong -- an ERP order numbered 4500001234 carries no prefix, so every order was filed under a heading only it had, which is the opposite of what a heading is for; the kind is now passed, because the caller always knows and the number does not always say. And a requisition enters the flow under its own key because that is its only identity before ERP issues one: the chain already moved its links across on renumbering and the history did not, so the findable half of its history began in the middle. StatusLog.rename now follows it, called where chain.rename already was. Line-level statuses are deliberately not logged: the history keys on a document number and a line has none", "test_procurement: PR and PO both keep a history, each filed under its kind rather than its own number, the requisition carrying its pre-ERP entries across the renumbering with nothing left behind under the old key"),
    ("F-12", "Frameworks", "An approval whose outcome cannot reach its document is still accepted",
     "reflectOutcome writes the lifecycle field only where the entity has an element literally named status, and returns quietly where it does not. Project is the case: its lifecycle field is stage, so an approval configured against it would be submitted, worked, signed and closed while the project never moved -- silently, which is the same defect as S-26 one module over. Latent rather than live: only RR and Budget have schemes today and both carry status, and a scheme for anything else is refused for having no scheme at all rather than for being unreflectable",
     "Raised",
     "Two candidate answers and they are not equivalent. Widening the field search to stage is the wrong one: a project stage is where the job is in its life, not whether a document was signed, and writing Approved into it would be inventing a vocabulary nobody asked for. The right one is to refuse at the point of configuration -- an administrator saving a scheme for an object the engine cannot conclude should be told then, not have the first signer find out. That needs a view on what each document type calls its approval state, which is a modelling decision", "2026-08-29"),
    ("F-13", "Frameworks", "A document that had been activated had no status at all",
     "A ResourceRequest created and draft-activated through the API carried a null status until something submitted it -- seen directly while driving one through approval, where the first history entry read null -> In Approval. The document existed, had a number, had lines and had priced them, and said nothing about where it was. Every screen that groups or filters by status dropped it, its history began by saying it came from nowhere, and both submit guards had to spell out that null meant the same as Draft -- an accommodation every new document type would have had to remember to repeat",
     "Done",
     "Answered once for every document type rather than per vertical, which is what the note said had to happen: the default sits on common.documented, so RR, Budget, Variation Order, Pull Request and every other documented header start as a Draft from one line. BOQ carries its own status and got the same. Project already had it. With null impossible, the two guards that spelled out null-means-Draft say Draft, so there is one meaning of the first state instead of one per reader. Checked first that no shipped content pack seeds a blank status, so the default cannot overwrite anything somebody decided", "test_chain 6: the request trail reads Draft -> In Approval -> Approved -> In Advisory -> Advised -> AVC Done -> Reserved, with no entry coming from nowhere"),

    ("F-06", "Frameworks", "Content pack references", "Packs can name another row instead of its UUID, and match on composite natural keys; each pack applies atomically", "Done", "APPROVAL_SCHEMES resolves auth objects and its own schemes at deploy time: 6 rows inserted", "—"),
    ("F-07", "Frameworks", "Attachments on every object", "One polymorphic attachment table for all modules; automatic versioning with a supersedes chain; client-configurable categories; a mandatory category blocks approval submission", "Done", "14 checks: v1 then v2 superseding it, PDF streamed in and read back byte-identical, 404 for a missing target, and submission refused until the mandatory drawing was attached", "fileSize (F-08) and the UI upload control"),
    ("F-08", "Frameworks", "Attachment file size, and a ceiling on it", "Two things, and the item only described the first. Measuring the stream in an After handler reports zero — the runtime has already consumed it to persist the content — so the size is read back off the stored blob instead, which is also the only number that describes what is actually there. That half had been done and the item never said so. The second half was missing entirely: no ceiling, so any authenticated user could put a file of any size on any object", "Done", "test_attachments 9: a file under the ceiling is stored and measured, one over it is refused by name, and the refusal unwinds the write so the file that fitted is still the one served back", "25 MB default, KX_ATTACHMENT_MAX_MB to override"),
    ("M-10", "Masters", "Rate master complete", "Draft-maintainable rates and norms; rateOn(resource, date, company) resolves which rate is in force — latest start on or before the date, company beating group; norms validated (no zero output, no 140% wastage, effective-date clashes on the full recipe key)", "Done", "17 checks", "—"),
    ("PS-04", "Project Setup", "BOQ import and arithmetic", "amount always qty x rate, never accepted from the caller; header equals sum of lines; all-or-nothing import that also catches duplicates within the file; re-import replaces", "Done", "20 checks incl. a bad bill refused whole", "—"),
    ("PS-05", "Project Setup", "Project CBS and allocation", "instantiateCBS copies the library (refuses a second run); allocate joins bill to WBS+CBS with an over-allocation guard and cross-project refusal; CBS nodes carry allocated value at bill rate", "Done", "700+500 of a 1200 line to exactly 100%; the repeated 700 refused", "—"),
    ("PL-01", "Planning", "Resource build-up from CBS recipes", "Norms carry the wireframe key (Resource x Linked CBS x Activity x Company); a BOQ line resolves through its CBS leaf; difficulty on top of productivity only, never the master norm (KX-BUD-014); MANUAL rows survive regeneration and are counted as defects; coverage report: recipe-found / manual / no-recipe / unmapped / rate-missing", "Done", "16 checks: 1230 m3 (2.5% wastage), 110 hr (std 12/hr x 110%), INFC override wins", "Activity Code Library difficulty resolution deferred — difficulty is a call parameter today"),
    ("EX-01", "Execution", "RR to RES chain engine", "submit prices lines from the rate master and refuses unpriced resources; approval outcome moves the document (F-05, generic); advisory line-by-line with rationale; AVC documents KONSTRYX-side commitments honestly, S/4 ATP slots in later; reservation encumbers the approved value; StatusHistory + DocumentLinks throughout", "Done", "28 checks; every shortcut refused with the missing step named", "S/4 ATP behind the same document (Q-09)"),
    ("B-06x", "Commercial", "Budget engine", "Generated from the priced build-up by CBS x cost nature (six); refuses unpriced resources whole; approval via BUD-STD; baseline makes the ledger the only door (PATCH on a baselined amount answers 403); zero-sum paired SHIFT with mandatory reason; refreshControl pulls open reservation encumbrance into the control record; riskTransfer (zero-sum, keyed to a risk reference) and variation (not zero-sum — the one category that moves the budget's own total, keyed to a variation order reference) complete all four KX-BUD-004 categories", "Done", "36 checks; line amount == sum of its ledger entries asserted per line across all four categories; a variation's delta is asserted against the budget's own totalAmount", "No standalone Variation Order / Risk register document objects yet — riskTransfer/variation are actions on the budget, referenced by a free-text ID; a formal document with its own approval and number range is a later increment if the business wants one"),
    ("F-10", "Frameworks", "Per-user table personalization", "Saved column sets, filters, sorts and groupings per user per table; one default each; administrator-published variants readable by all", "Done", "18 checks: two users hold the same variant name on the same table and see only their own; a new default clears the previous one and leaves other users alone; writing to someone else's answers 404, not 403, so the key is not confirmed", "UI wiring comes with the screen rebuild"),
    ("F-09", "Frameworks", "Attachment storage", "Content sits in the database as LargeBinary. Fine for drawings and permits; a project's photo library is a different question", "Not started", "—", "Decide before go-live — see S-24"),
    ("F-03", "Frameworks", "Attachments model", "Polymorphic on entityName+objectID, media-type content, categories", "Done", "Compiles; exposed on /collaboration", "Upload handler + object store not built"),
    ("F-04", "Frameworks", "Attachment upload + storage", "Object store binding for Cloud Foundry vs HANA LOB", "Not started", "—", "Decision needed (see Open Decisions)"),
    ("U-18", "UI", "An inbox row cannot open the document it is about",
     "The worklist names the document and its value but does not navigate to it, "
     "because the semantic object differs by document kind and nothing records which "
     "one belongs to which. The auth catalogue already maps entity to name and would "
     "be the place to carry it",
     "Raised", "—", "Needs a ruling: a semanticObject column on AuthObject, or a fixed map"),

    ("F-05", "Frameworks", "Table personalization store", "UserVariant entity holding UI5 p13n state per user", "Done", "Compiles; exposed on /collaboration", "Not wired to any table yet"),
    ("F-06", "Frameworks", "Table personalization UI wiring",
     "p13n + VariantManagement on every list screen",
     "Part done",
     "Measured rather than assumed: all 32 Fiori Elements list reports already declare "
     "variantManagement Page with flexEnabled, and personalization is the template "
     "default, so the arrangement is offered everywhere. test_foundations now refuses "
     "a list report that ships without it",
     "Where a saved arrangement goes is unanswered — see F-18"),
    ("M-01", "Data model", "Workflow spine RR->ADV->AVC->RES", "Vertical-agnostic, multi-line, seeded with canonical EQR thread", "Done", "Queryable over OData; 5 lines, AED 685,080", "—"),
    ("M-02", "Data model", "WBS on request line", "Spec section 6 requires one WBS per line; was missing", "Done", "3 distinct WBS across the 5 EQR lines", "—"),
    ("M-03", "Data model", "EQR vertical extension", "Instances, mob/demob window, own-vs-rental, vendor, operators", "Done", "$expand=equipment,wbs returns all 5 lines resolved", "—"),
    ("M-04", "Data model", "Chain steps CMT/MOB/OPL/VAR/DMB/CLS", "Recorded as six steps with no entities at all. Three of the six now have them: CLS writes a ReservationClosure, OPL is kept as a TimesheetEntry for manpower and a ConsumptionRecord for material, and VAR is the ReservationVariation built the same day. CMT is ERP's to own. MOB and DMB are the asset steps and belong to the plant block you are holding", "Part done", "reservationOverview reads all ten from data: RES-2026-0162 (MPR) reports its daily record done off 46 signed timesheets, RES-2026-0148 (MR) reports it outstanding, RES-2026-0188 (EQR) reports it unbuilt. test_overview and test_variation", "What is left: an operation log for plant, and mobilization and de-mobilization — all three held with B-09. VAR was built the same day (B-17). CMT stays ERP's"),
    ("U-01", "UI", "RR worklist on live OData", "RequestOverview projection, server-side filters", "Done", "Verified in browser: 4 requests, EQR shows 5 lines / 685,080; EQR filter issues new $batch", "—"),
    ("U-02", "UI", "Two deployed apps claimed the same launchpad intent, and one of them showed a file",
     "The item said the request detail page still reads webapp/model/data.json, and it does -- but the page it describes was replaced. konstryx-resource-request and konstryx-reservation are Fiori Elements apps on the workflow service, and the freestyle konstryx-ui declared the SAME semantic object and action for both. A launchpad resolves by that pair, both apps are in mta.yaml, so which one answered \"show me the requests\" was left to resolution order -- and one of the two candidates reads a fixture shipped inside the app. The sandbox happens to resolve to the Fiori Elements components, so this would have surfaced on a real launchpad and not before",
     "Done",
     "The freestyle app stops claiming what a live-data app already serves. Removed by brace depth rather than by rewriting the manifest, so the diff is those two blocks and nothing else. Its screens stay reachable in-app; what it no longer does is offer itself as the answer to a question another app answers with data. Not a rewiring of the freestyle pages to OData, because the standing ruling is that screens are rebuilt in Fiori Elements and freestyle survives only by requirement, never by sunk cost -- and for these two the rebuild already exists", "test_foundations 9: no intent is claimed by two apps, and no app answering a launchpad intent has a fixture for its default model"),
    ("U-17", "UI", "One screen exists only in the freestyle app, and nothing offers it",
     "KonstryxManpower is declared by konstryx-ui and by nothing else, and the launchpad site does not carry a tile for it -- 28 of the 29 declared intents are offered, and this is the one that is not. So the manpower overview is deployed, unreachable except by direct URL, and reading the same shipped fixture as the rest of that app. It is also the only screen in konstryx-ui with no Fiori Elements replacement, which is why removing its intent alongside the other two would have been the wrong move",
     "Raised",
     "Two answers and the choice is yours. Build a Fiori Elements manpower app, which is what the architecture ruling implies and which retires konstryx-ui entirely; or keep the freestyle screen deliberately and wire it to the workflow service and the launchpad, which is freestyle by requirement rather than by sunk cost and needs the requirement stated. Raised rather than picked because the two differ in what happens to the rest of that app, and that is a product decision", "2026-08-30"),

    ("U-03", "UI", "Chain step pages on OData", "Still read data.json", "Blocked", "—", "Five of the ten now have data behind them — RES, OPL for two verticals, VAR, CLS, and the chain links between them. MOB, DMB and CMT still do not"),
    ("U-04", "UI", "Launchpad intents declared", "crossNavigation inbounds for KonstryxResourceRequest and KonstryxReservation", "Done", "manifest parses; two inbounds registered", "—"),
    ("U-05", "UI", "Launchpad-hosted shell (blend with S/4)", "App shell removed: root view is now the NavContainer alone. Launchpad supplies header, search, user menu, theme", "Done", "Verified in browser as daud: worklist renders with no app chrome, 4 of 5 requests correctly scoped, EQR at AED 685,080", "—"),
    ("U-06", "UI", "Spaces and Pages navigation", "flp.html + flpSite.json written: CDM 3.1 site, one space, one page, two intent tiles", "At risk", "Site JSON authored against the runtime's own sandboxSite.json schema", "Sandbox bootstrap fails reading a null script element; finish or verify on real BTP instead"),
    ("U-08", "UI", "Split into task-focused apps per document type", "S/4 pattern is one app per task, reached from a tile. Currently one app with in-app routing across ten document types", "Not started", "—", "Register more intents as screens are built"),
    ("U-09", "UI", "Reservation overview — chain progress + honest S/4 status", "You flagged the old screen as poorly designed with no visible chain progress or S/4 truth. Rebuilt: reservationOverview action computes steps-done/steps-pending across the full ten-step chain from live documents (RR, advisory, AVC, RES, closure); the header states per integration path what is actually connected — project sync LIVE, CMT/procurement/BP mirror not wired — and every row carries its own project's sync state", "Done", "Verified in browser: RES-2026-0188 reads 4 of 10 steps, pending CMT/MOB/OPL/VAR/DMB/CLS listed explicitly; full regression 13 suites / 261 checks green", "CMT connector, once S/4 PS commitment posting is in scope"),
    ("U-10", "UI", "Variant management, adapt filters, table settings and Excel export on the remaining list screens", "Rolled out ListPersonalization (already proven on the RR worklist) to Rate Master, Productivity/Consumption Norms (two independent targets, one screen), Project Templates, and the Promotion Queue. Deliberately NOT applied to Resource Hierarchy or CBS Library — those are TreeTables showing an L1-L5 hierarchy, and generic Sorter/Group panels fight the tree rather than help it; their existing tree-specific search stays. Cost Mapping's exception queue got Export only, no variant management or filter dialog — it is already pre-filtered to \"only what needs a decision\", so there is nothing left to filter", "Done", "Verified in browser (fresh tab per screen, zero console errors): each table's p13n dialog opens with fields matching its columns exactly, OData row counts intact (Rates 14, Productivity norms 8, Consumption norms 7). Two real bugs found and fixed while wiring this: (1) VariantManagement's showSetAsDefault is not a real property (correct one is supportDefault) — was already wrong on the RR worklist from an earlier session and copied forward before being caught; (2) MasterNorms' two tables collided on duplicate column ids (basis, scope) — XML view ids must be unique across the whole view, not just per control aggregation", "Roll the same treatment to RequestDetail/ChainStep/ResourceDetail if/when those grow list sections; today they are single-object detail pages with nothing to personalize"),
    ("U-11", "UI", "Distribute-to-WBS dialog on the Cost Mapping workbench", "UNALLOCATED exception rows had no action — a coordinator could see \"0 of 1840 distributed\" but had nowhere to act on it. Added a Distribute button opening a dialog over the existing distributeToWBS action: choose TPL-SINGLE (whole line, one element) or TPL-FLOORS/TPL-ZONES (weighted split across several), pick the target WBS element(s), submit. costMappingSummary's exception payload gained boqId (it only carried boqItemId before) so the dialog can address the right BOQ without an extra round trip", "Done", "Verified live end to end for all three templates. TPL-SINGLE: item 1.E.1.1.01 (0 of 1840) onto WBS-0.10. TPL-ZONES: item 1.E.2.2.01 (0 of 682) split 30/70 across WBS-0.10/WBS-1.02, landing at exactly 204.6/477.4 (682.0 to the tenth) with template and splitBasis recorded on the allocation rows. Full regression unaffected throughout: 13 suites / 271 checks green each time", "Two real bugs found and fixed while building this. (1) `class` is not a valid constructor setting in JS-built controls (only in XML) — silently no-ops with a console warning; fixed here and on MasterTemplates' pre-existing instantiate dialog, both now use addStyleClass(). (2) A genuine SAPUI5-vs-CAP encoding mismatch: the v4 ODataModel serialises a Decimal nested inside an array-of-complex-type action parameter (targets: array of WBSTarget) as a JSON string, and CAP's OData V4 deserialiser refuses a quoted decimal on that property (\"Invalid value for property 'weight'\") — confirmed by direct curl: the identical payload succeeds the moment weight is a bare JSON number, fails identically whether sent as a JS number or a JS string through the typed model API. Worked around by posting distributeToWBS as a raw authenticated fetch instead of the model's typed action-parameter path; template/itemNos still round-trip fine through the model elsewhere since they are not complex-type array members"),
    ("U-12", "UI", "Resource hyperlinks on Rate Master and Norms", "The resource/material column on Rate Master and both Norms tables (Productivity, Consumption) was plain text — no way to jump to the resource's master record from a rate or a norm. Wired the existing ObjectLinks \"resource\" registry (Resource Master / Rate Master / Norms) onto all three columns; no registry changes needed since material is modelled as ResourceNode (same entity resource points to)", "Done", "Verified in browser (fresh tab, zero console errors) on all three tables: link press opens the popover with all three targets, Resource Master target navigates to #/masters/resource/{code} correctly", "PromotionQueue's objectKey could link to its underlying master too, but objectType there is a free-text label (Resource/CBS/Rate/...), not a typed reference the registry can resolve without new backend support — left alone rather than guessing a mapping"),
    ("B-07", "Business", "Purchase requisition from the PROCURE branch", "The advisory decision splits a request four ways, but only IN_HOUSE was ever consumed — createReservation picked those lines up and a PROCURE line dead-ended at lineStatus Advised with nothing behind it (the code said so: \"procured lines are the buyer's problem, not the fleet's\"). raisePurchaseRequisition closes that seam: it raises one requisition from the PROCURE-decided lines, carrying each line's quantity, approved value, need-by and — critically — its WBS and CBS account assignment, without which the commitment S/4 returns would have no budget line to land on. Per D-21 it is not a KONSTRYX document: inserted straight through the persistence service rather than an ApplicationService precisely because there is no number to stamp", "Done", "28 checks in test_procurement.py. Asserts what it must NOT have as carefully as what it must: no prNo issued locally, no docNo, syncStatus NOT_SENT, and no PR number range in the catalogue (that last check was caught passing vacuously on a malformed query and rewritten to prove the catalogue is readable first). Also asserts only the procured line travels, the in-house line is left at Advised for the fleet, and that availability and reservation still run for the in-house half afterwards", "The S/4 push landed next, as B-09. It needs no EDMX and srv/external/ still does not exist — API_PURCHASEREQ_PROCESS_SRV is called as raw OData V2 through S4Connection, the same seam S4ProjectConnector uses, so nothing is imported and nothing is generated. The material it orders against arrived first (I-35: ResourceNode.s4Material, resolved onto the line when the requisition is raised), and the open question this entry ended on — what to do with a PROCURE line whose resource has no material — is answered: the push refuses the whole requisition by line number and tells the buyer to map the resource, rather than sending an order that names nothing"),
    ("B-08", "Business", "Purchase order mirror, and the commitment it lands on the budget", "Per the ownership table, KONSTRYX never creates a purchase order — S/4 raises it and we mirror it back, so recordPurchaseOrder is inbound only and PurchaseOrder correctly keeps the s4mirror aspect (unlike the requisition, which moved to s4outbound under D-21). The mirrored order links to the requisition it was raised against, and each line INHERITS that requisition line's WBS/CBS rather than restating it — an order that charged somewhere other than its requisition would commit against the wrong budget line. Also adds recordRequisitionResult, the requisition's return leg, which stamps the number S/4 issued. Both follow the ProjectService.recordSyncResult pattern: the connector calls them, and so does a test, so every path writes identical state and none of it needs a live tenant", "Done", "48 checks in test_procurement.py (up from 28). The commitment section is deliberately unconditional — an earlier draft skipped it when the project had no budget, which reads as passing; the fixture now builds a real budget on PRJ-002 so it must run. End state verified: the EQR line reads amount 6,050, committed 231 (the order), encumbered 320 (the reservation), available 5,499 — and refreshing twice leaves it at 231, proving commitment is derived rather than accumulated", "BudgetLine.committed has been documented as 'S/4 PO/SO' since the model was written and never carried a value until now. It is computed at refreshControl the same way encumbrance is — a sum over the orders that exist, not a counter, so a cancelled or re-mirrored order cannot drift it. NOTE this is the procurement branch's commitment, NOT the reservation chain's step 5 (CMT), which is an S/4 PS commitment against the reservation itself and remains unwired; ReservationOverviewHandler still reports that one as pending, correctly"),
    ("B-09", "Business", "The requisition push to S/4 — the outbound half of D-21", "raisePurchaseRequisition built the document and recordRequisitionResult stamped the number S/4 issued, but nothing carried the document ACROSS: the requisition sat NOT_SENT until somebody called the return leg by hand. S4RequisitionConnector closes that, following S4ProjectConnector exactly — it talks to S/4, returns an outcome, and writes nothing; recording goes through the same applyOutcome the manual recordRequisitionResult uses, so a connector run and a correction leave identical state. API_PURCHASEREQ_PROCESS_SRV takes the whole document in one deep insert (header, items, each item's account assignment), which is not a style choice: an item posted separately would be a requisition of its own, and one posted without its account assignment would commit against nothing — the very thing the WBS/CBS on the line exists to prevent. Also fixed a gap this exposed upstream: S4ProjectConnector created WBS elements in S/4 and never recorded what they were called, so WBSElement.s4Key was empty on every row and the account assignment had nothing to name. It now records each element's key from S/4's own response rather than re-deriving it from the KONSTRYX code, which would have put the same normalising rule in two places", "Done — the gates; the live POST is unverified", "69 checks in test_procurement.py (up from 58). Three refusals verified live, each stopping BEFORE any connection is opened: a line whose resource has no material (the buyer is told to map the resource, not handed a connection error), a line whose WBS is not in S/4 yet, and a requisition S/4 has already numbered (409, naming 1000004711). A refused push leaves the requisition NOT_SENT with syncAttempts still 0 — nothing was attempted, so nothing may read as FAILED. Full regression green", "THE LIVE POST HAS NOT RUN. SAP_COM_0102 is not activated on the tenant (Q-09), so the payload shape, the org defaults (S4_PR_SERVICE/S4_PR_TYPE/S4_PLANT/S4_PURCH_ORG/S4_PURCH_GROUP) and the account-assignment category 'P' are S/4 standard content, NOT read off the tenant the way the project connector's defaults were. Expect them to need setting per tenant. The test suite deliberately never constructs a pushable requisition: .env points at the live tenant, so a case that cleared every gate would post a real purchase requisition from a test run — the live path is exercised by hand, once the scenario is activated. NOTE the API and scenario were both corrected on 2026-08-19 under I-43; this entry originally shipped against the wrong ones"),
    ("U-13", "UI", "Budget screens — the engine finally has a front end", "The whole budget engine (generateLines / submit / baseline / shift / riskTransfer / variation / refreshControl) was backend-only, exercised solely by test_budget.py. Built against the wireframe at KONSTRYX_Wireframe_v12/modules/budget.html — which existed all along and was missed by the previous session's search, not genuinely absent. Shipped: a per-project Budget worklist with a New Budget dialog (draft create then draftActivate for the company-scoped BUD- number); a Budget detail page with a five-KPI header (total/committed/encumbered/actual/available), header actions for the four parameterless engine actions gated on lifecycle status, and three tabs — Budget Lines (the CBS x cost-nature control record), Ledger & History (every movement, its category, signed delta, reference and reason) and Approvals (the live CollaborationService chain, since bud.cds's own BudgetApproval composition is unwritten); and Shift / Risk Transfer / Variation dialogs enabled only once Baselined, each enforcing the engine's own mandatory fields client-side before posting", "Done", "Verified in browser against a live baselined budget end to end (fresh tab per pass, zero console errors): BUD-INFC-2026-0001 reads 381,600 across 2 lines, the ledger shows all four categories with the paired SHIFT and RISK_TRANSFER entries summing to zero and the VARIATION unpaired, and the approval chain shows both steps APPROVED with actor and comment. Shift posted through the real dialog moved 1,000 MR->EQR and the tables refreshed to match. Full regression 13 suites / 271 checks green", "Cost Mapping's Generate Budget Lines placeholder now navigates here; budget added to the ObjectLinks project registry. The wireframe's Resources / Time Phasing / BOQ Analysis / Reconciliation tabs are not built — they need entities that do not exist yet (time-phased BCWS, reconciliation adjustments)"),
    ("U-14", "UI", "Cross-project worklists and tiles for BOQ and Budget", "Both objects could only be reached by opening a project first. Added portfolio-wide BOQ and Budget worklists with full personalization (variant management, adapt filters, column/sort/group settings, Excel export) and launchpad tiles in the Setup & Budget group, matching the way Resource Requests already works", "Done", "Verified in browser: BOQ worklist lists both projects' bills with project code and name resolved, row press opens the right project's BOQ; Budget worklist lists every project's budget, row press opens its detail page", "Cost Mapping and Allocations still have no portfolio-wide entry point — the user asked for those too"),
    ("U-16", "UI", "Cost Mapping — both views, per project and across the portfolio", "Your call: provide both. The per-project workbench is untouched; a portfolio list sits alongside it answering the different question a multi-project reader has — which projects still need a human at all. Counts only, no exception rows, because the point of the list is which project to open and the workbench handles what to do inside it. A 'Needs attention' filter deliberately excludes projects with no bill yet: nothing to map is not the same as work outstanding", "Done", "Verified in browser: the portfolio's numbers reconcile exactly with the workbench it links to (PRJ-001 reads CBS 0 open, WBS 5, resources 4, 9 exceptions, 2 gate rules failing on both screens), the filter drops PRJ-002 which has no bill, and row press opens the right project's workbench. Console clean", "Backed by a new unbound action costMappingPortfolio, which reuses the existing per-project computation rather than duplicating it (onSummary was refactored to delegate to the same summaryOf method). It reads Projects through the ApplicationService, not the PersistenceService, so the authorization layer's instance filter applies — verified live: demo sees both projects, vikram sees only PRJ-001, and users without project rights are refused"),
    ("B-16", "Business", "Stock we already own becomes project cost",
     "A reservation locked the money and nothing ever spent it. Material could be reserved, encumbered and reported on for the whole life of a project without one unit being drawn, and the budget went on holding the full amount against work that had already been built. Cost came from signed daily logs and from supplier invoices - labour, and what was bought - so the concrete out of our own batching plant was free. Four steps now close it: the site raises a pull request against the reservation, ERP posts the goods issue, the site counts what arrived, and the day's work is measured against the norm",
     "Done",
     "82 checks in test_issue.py, which builds its own thread end to end rather than leaning on a fixture. Verified live on the flagship: 123,372 of concrete drawn from store 1710 against RES-2026-0003, PRJ-001 now reports 3,113,423.84 spent with no coverage caveat left on any category. Two new screens, both opening with rows. Full regression green at 735",
     "The goods issue is the cost and nothing after it is charged again - a goods issue debits the project in ERP, so costing consumption as well would pay for the same concrete twice. Consumption therefore carries quantities and no money: it answers whether a crew is wasting material, which is a different question from what the project has spent. There is deliberately NO outbound push: KONSTRYX does not post movements into ERP, and recordGoodsIssue is the only way one enters"),
    ("B-17", "Business", "Reservation variation — step 8 of the chain", "A change to a reservation that is already running: the slab cycle slips and both cranes need thirty more days. Nothing about the bill changed and the client is not in the conversation. Until now the only way to record it was to edit the reservation line, which left no trace it had ever said anything else. RVO document, before and after on every figure it moves, and the encumbrance the budget reads follows because it is derived from the line", "Done", "test_variation, 71 checks. Two rules carry it: a variation will not lock less than the line has already spent (the budget reads the lock less the spend, so reducing it under the spend turns an overrun into free headroom), and a variation that varies nothing is refused. The duration is read back from the lock — the line stores heads and a daily rate, not days — so a rate correction leaves the hundred days alone instead of collapsing the lock to one day", "Not the BOQ variation (B-08). Same word, different document: that one varies a priced bill and argues with the client about revenue. vary() takes extendByDays as well as an absolute duration, because nobody outside the handler knows what the current one is — the wireframe itself asks for \"+30 days on both lines\" — and ReservationLines now exposes reservedDays so the third figure of the lock is readable on the screen"),
    ("B-15", "Business", "Certified subcontract work counts as cost",
     "The reconciliation stated in its own notes that subcontract contributes nothing and the margin therefore flatters. It was right, and it stayed right for as long as nothing carried a certificate into project cost - certificates were raised, adjusted, signed off and read on screen, and no report ever counted one. Certified value now joins consumed hours and billed invoices as the third branch of a spend: they cannot overlap, because a scope goes down exactly one of them",
     "Done",
     "24 checks in test_certification.py (up from 20). Verified live on the flagship: 1,041,660 of certified work sits inside the 2,229,071.84 the report calls spent, and the coverage note no longer lists subcontract among what contributes nothing. Full regression green",
     "Cost is the certified gross less what is RECOVERED from the subcontractor - liquidated damages and back charges - and not less retention, which is money withheld rather than money saved: the work was done and the retention is released later. That is netCertified + retentionAmount under the formula Ziya ruled on, which is why it is read back from the stored figures rather than recomputed. NOT placed on a budget line: SubcontractRequest carries a project and no WBS or CBS, and whether a package assigns to one cost node or allocates across several is a modelling decision, not something to guess. It lands in project cost and stops there"),
    ("B-14", "Business", "The document flow reads from the request to the bill",
     "The flow stopped at the requisition. ChainHandler wrote AVAILABILITY, RESERVATION and REQUISITION links and nothing downstream did, so an order, a delivery and a bill could all exist against a request and the flow showed none of them - and the reader had no way to tell a document that was never raised from one raised and never linked. Worse, the requisition was linked as PR:<uuid> because it enters the flow before ERP has numbered it, and the comment saying the link carries our key UNTIL a number comes back described an intention nothing implemented: the number arrived and the link kept the key",
     "Done",
     "ORDER, RECEIPT and INVOICE links written by ProcurementHandler, and recordRequisitionResult renames the requisition in the flow the moment ERP numbers it. Verified live end to end: RR-2026-0002 -REQUISITION-> 1000004711 -ORDER-> 4500001234 -RECEIPT-> both deliveries -INVOICE-> the bills. Full regression green",
     "The link writer moved to a shared DocumentChain component rather than being copied into a second handler. Four handlers write this table now, and copied ten lines at a time the types drift - one writes INVOICE and the next SUPPLIER_INVOICE, and a flow that reads end to end on one project stops on another for no reason anybody can see"),
    ("B-13", "Business", "One answer to what the work has cost, on every screen that asks",
     "The control record and the cost-value reconciliation gave different answers to the same question, and both were defensible in isolation. BudgetLine.actual counted the bought half only, so a job running on own labour read as fully available while the reconciliation on the next screen reported real money spent; and the reconciliation reached that figure by adding reservation cost to the budget lines' actual, which made a project's reported cost depend on somebody having pressed Refresh Control, and reported nothing at all for a project with no budget yet. Both now read the documents. actual is the invoices placed on the line plus the signed hours consumed against its reservations - the two halves the two branches of the chain produce, which cannot overlap because a line is decided PROCURE or IN_HOUSE and only one branch ever runs. The reconciliation reads the invoices directly rather than through the budget",
     "Done",
     "Full regression green. The category-coverage note was corrected with it: it claimed material and subcontract contribute nothing, which stopped being true for material the moment invoices existed - it now names manpower and procurement as captured when they are, and subcontract as the one that genuinely still contributes nothing",
     "The reconciliation's actualCost and the sum of its budget's actual now agree by construction rather than by coincidence, which is what makes a disagreement between the two screens a bug rather than a question about which one to believe"),
    ("B-12", "Business", "The supplier invoice, and the first source BudgetLine.actual has ever had",
     "Three of the four columns on the control record were live and the fourth was a constant. amount came from the budget, encumbered from open reservations, committed from what the orders still had to deliver — and actual was written as zero at generateLines and never touched again, with refreshControl's own message saying so. It is the column a project manager reads first, and it was the one that could not be wrong because it never moved. SupplierInvoice and SupplierInvoiceLine close it: the vendor bill mirrored from ERP FI, each line matched three ways as it lands (quantity against what the receipts actually brought in, value against the order's own rate for that quantity), and actual then summed from the invoice lines and placed on budget lines by the same attribution the other two figures use. The match also stamps GoodsReceipt.threeWayMatch, which had been modelled since the model was written and was permanently null because the third document did not exist",
     "Done",
     "123 checks in test_procurement.py (up from 101). The kit order verified through all four documents: requisitioned, ordered at 231.00, received in two loads, billed at 231.00 and matched — BOTH receipts stamped, not just the one the invoice was booked to. A second bill for the same four kits is accepted and recorded as failing, naming the reason (billed 8.000 against 4.000 received), and the order reads invoicedValue 462.00. The budget line then reads actual 462.00, available = amount less committed less encumbered less actual, and refreshing twice leaves it at 462.00. Full regression green",
     "The invoice is the only leg that RECORDS a failure rather than refusing it, and that asymmetry is deliberate: the other two refuse what they cannot honestly write, but ERP FI posted the invoice whether or not it agrees with the order, and an invoice we declined to mirror is one nobody can see is wrong. Refusal is kept for what makes the document unreadable — no number, no order, a line that is not on it. Screen: konstryx-invoice, a list report sorted by match state because the reason a clerk opens it is to find the bills that disagree; the failing line carries the reason, since the header only says something failed. Also added as a facet on the order. NO CONNECTOR PULLS IT: API_SUPPLIERINVOICE_PROCESS_SRV is named in INTEGRATION.md and unimplemented"),
    ("B-11", "Business", "The delivery half of procurement, and the commitment it releases",
     "B-08 mirrored a purchase order and landed its value on a budget line as committed, and there it stopped: nothing ever took delivery. GoodsReceipt had been modelled since the model was written and had no writer at all, so openQty on every order line stayed where the order left it, the receipts screen did not exist, and commitment was the whole order for as long as the order lived. Three things shipped together. recordGoodsReceipt is the receipt mirror, the counterpart of recordPurchaseOrder: it validates the whole document before writing any of it (ERP posted it whole, so a receipt that over-delivers on its third line must not leave the first two posted), prices each line from the ORDER rather than from anything the receipt carries, moves openQty and receivedQty, and rolls both the line and the header through Partly received to Received. The order header gained netValue and openValue, summed from its lines rather than counted up as documents arrive. And commitment became the OPEN part of an order rather than the ordered part - a delivered line is cost, which ERP FI posts as actual, so counting it as commitment holds budget against goods already on site and doubles it when the invoice lands",
     "Done",
     "101 checks in test_procurement.py (up from 81). The order of 4 kits at 231.00 verified through its whole life: fully open at 231.00 committed, then one taken in leaves the line Partly received with 3 open, the receipt priced at 57.75 (231.00 / 4), the header owing 173.25, and the budget line committed at exactly 173.25; the remaining 3 settle the order to Received, openValue 0, and commitment 0. Four refusals verified, each leaving the order untouched: no ERP document number, an order we do not hold, a line number that is not on the order, and a quantity larger than the line has open. Full regression green",
     "Screen: konstryx-po, a Fiori Elements list and object page over the mirror, with the lines and the receipts as facets and the ERP fields (number, system, mirror state, mirrored at) in their own group, because an order whose mirror state is not OK is showing figures that may already have moved. Registered in the Execution space under Source resources. NO CONNECTOR PULLS EITHER DOCUMENT: API_PURCHASEORDER_PROCESS_SRV and API_MATERIAL_DOCUMENT_SRV are named in INTEGRATION.md and unimplemented, so the entry points are reached by a test, a manual correction, or tools/mirror_erp_documents.py, which stands in for ERP so the demo has orders at all. That tool stamps system DEMO on everything it writes - a real mirror carries the tenant host - so the two are told apart on the screen rather than by trusting the number"),
    ("U-15", "UI", "PromotionQueue object links", "Previously left alone on the belief that objectType was a free-text label. It is not: PromotionHandler stamps it server-side from the target entity's qualified name (MasterDataService.Resources) and reuses that exact string on approval, so it is a closed set equal to the entities exposing requestPromotion. Wired objectKey as a link with a small type->route map in the controller", "Done", "Confirmed the stored value by triggering a real promotion against EQ-LOC-INFC and reading the queue row back: objectType is MasterDataService.Resources", "Deliberately not routed through ObjectLinks: every row here is master data by definition, so there is exactly one correct target and no picker is warranted"),
    ("U-07", "UI", "Morning Horizon theme", "sap_horizon is Morning Horizon; already the bootstrap theme", "Done", "index.html bootstraps data-sap-ui-theme=sap_horizon", "Must be inherited from the shell once launchpad-hosted, never hard-coded"),
    ("B-01a", "Business", "Masters — hybrid scope enforcement", "Reads on any entity carrying the scoped aspect narrow to GROUP or the user's own companies; aspect duck-typed from the model, not a name list", "Done", "Two stewards in different legal entities each see 5 group masters + their own local one, and neither sees the other's", "—"),
    ("B-01b", "Business", "Masters — promotion queue (mdg)", "requestPromotion on the master, approve/reject on the queue; scope is never edited directly", "Done", "EQ-LOC-INFC invisible to PMI, requested, approved, then visible — reason, decider and outcome recorded", "—"),
    ("B-01c", "Business", "Masters — validation rules", "Level/parent agreement, code uniqueness per scope, rate effective-date clashes, promotion collision check", "Done", "Valid L1 accepted; L5 with no parent, L1 given a parent, L3 under an L5, duplicate code and group-vs-local clash all rejected with 409 and a specific message; promotion blocked while INFC and PMI both hold EQ-DUP, naming both", "—"),
    ("B-01d", "Business", "Masters — remaining entities catalogued", "CBS library, productivity and consumption norms, templates, material mirror added to the authorization catalogue", "Done", "CBS library picked up isolation, promotion and L1-L3 depth checks with no CBS-specific code — both handlers duck-type the scoped aspect", "—"),
    ("B-01e", "Business", "Masters — list screens", "Resource hierarchy, CBS library, rate master and promotion queue, all on live OData with server-side filters", "Done", "Verified by screenshot: 7 resources (PMI's local one correctly absent from an INFC session), 7 CBS nodes, 8 rates, 1 pending promotion", "—"),
    ("B-01f", "Business", "Masters — object page", "Header facts, attributes, rate history and hierarchy children; route carries the code, not the UUID", "Done", "EQ-TWC-12T shows all three of its rates together; EQ-TOWER shows parent EQ-CRANE and child EQ-TWC-12T", "—"),
    ("B-01h", "Business", "Masters — draft editing", "CAP draft: private copy on edit, stored record untouched until activation, resumes an abandoned draft", "Done", "Edit that was previously rejected now activates and persists; validation still fires on activation", "Edit is on the resource page only; the other masters reuse the same pattern"),
    ("B-01g", "Business", "Masters — productivity and consumption norms", "One screen, two tabs; plus a material branch in the resource tree so consumption norms attach to materials rather than equipment", "Done", "4 productivity norms with crew composition, 3 consumption norms with wastage; group 105 kg/m3 rebar against INFC's own 112 kg for coastal detailing", "—"),
    ("B-02a", "Business", "Templates — model and instantiation", "Template carries construction type, CBS structure and default resources; instantiate copies them into a project, two-pass so children parent to their new instances", "Done", "TPL-HIGHRISE into PRJ-002: 7 CBS nodes (3 roots, 4 correctly parented, all traced to library) and 6 planned resources; second run refused", "—"),
    ("B-02b", "Business", "Templates — screen", "List plus an instantiate dialog offering the projects the user may see; refusal surfaces the service's own message", "Done", "Driven through the UI: TPL-HIGHRISE into PRJ-002 created 7 CBS nodes and 6 planned resources; a second run raised the refusal", "Object page for a template still to do"),
    ("B-03a", "Business", "Project Setup", "Project master, WBS, CBS instance; S/4 Enterprise Project mirror", "Done", "Superseded by B-10 and D-02: the project is KONSTRYX-mastered, released and pushed live to the tenant through the ITS_S4 destination. test_project, 28 checks", "Phase-plan placeholder; the evidence is on the items that replaced it"),
    ("B-02", "Business", "Templates", "Project templates: CBS tree + default resources", "Done", "Superseded by B-02a and B-02b", "Phase-plan placeholder"),
    ("B-03", "Business", "Project Setup", "Project, WBS, CBS instance; S/4 Enterprise Project mirror", "Done", "Superseded by B-03a", "Phase-plan placeholder"),
    ("B-04", "Business", "Uploads", "BOQ import, estimate import, versioning with progress carry-forward", "Done", "The BOQ import engine and its file picker are built; test_boq covers the bill, the project CBS and the allocation between them", "Phase-plan placeholder. Estimate import and version carry-forward are NOT built — the bill is"),
    ("B-05", "Business", "Project Planning", "Activity layer, native entity + P6 adapter", "Done", "Activities, the forward and backward pass and the P6 adapter all exist; test_schedule, test_planning and test_p6 cover them", "Phase-plan placeholder. The Gantt is still parked as GanttChart.fragment.xml.wip"),
    ("B-06", "Business", "Budgeting", "Budget from BOQ/CBS, 4-category ledger, approval, baseline, encumbrance", "Done", "Superseded by B-06x and the control items after it; test_budget and test_distribution", "Phase-plan placeholder"),
    ("B-07", "Business", "Project Execution", "RR->CLS chain end to end, material + manpower", "Done", "Superseded by B-11 to B-16: request, advisory, availability, reservation, requisition, order, receipt, invoice, stock draw, goods issue, consumption and closure. test_chain, test_execution, test_procurement and test_issue", "Phase-plan placeholder. Of the six later chain steps, CLS, OPL and VAR now have entities and the overview reads all ten from data; CMT is ERP's and MOB/DMB belong to the held plant block — see M-04"),
    ("B-08", "Business", "Project Commercial", "Client billing, variations, payment certificates", "Done", "Variations and payment certificates are built and certified value now reaches project cost (B-15); test_certification", "Phase-plan placeholder. Client billing itself is NOT built — variations and certificates are"),
    ("B-09", "Business", "Plant Department", "Equipment, fleet, scaffolding/formwork", "Not started", "—", "Held by your own priority ruling — konstryx.eq stays wired into the RR spine and dormant. The one genuinely unstarted block of the eight"),
    ("D-01", "Deployment", "MTA builds a deployable archive", "Approuter + srv + db-deployer; XSUAA, HANA, Destination resources", "Done", "konstryx_0.1.0.mtar 68.9 MB; 234 HDI artifacts and .hdiconfig verified inside the db-deployer", "—"),
    ("D-04", "Deployment", "First Cloud Foundry deployment", "Push the archive, bind services, verify the app end to end in the cloud", "Blocked", "—", "Blocked by I-24: needs a KONSTRYX subaccount and cf login"),
    ("D-02", "Deployment", "S/4HANA Public Cloud connector", "S4Connection (credentials, CSRF handshake) + S4ProjectConnector (project + WBS push to API_ENTERPRISE_PROJECT_SRV) built and run live against S4-SANDBOX: KX-S4-001 created via release -> sync, confirmed by independent read-back (profile YP05)", "Done", "D-17 loop ran live on the tenant; see Q-09p", "Scoped to the project scenario only — procurement, finance and BP mirror connectors are not built; BTP destination replaces S4Connection at deployment"),
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
    ("D-17", "2026-08-15", "The project is mastered in KONSTRYX, not in S/4", "Your instruction. A project is created in KONSTRYX and synchronised outward to S/4, or brought in from Primavera P6. This reverses the KONSTRYX-as-reader assumption for the project object specifically; procurement and finance stay S/4-owned", "You", "High — prj.Project is currently @readonly as an S/4 mirror and must become writable with outbound sync and an unsynchronised state visible in the UI", "Decided"),
    ("D-18", "2026-08-15", "Every master and transaction gets upload and download", "Your instruction. Excel import/export as a first-class capability rather than per-screen bespoke work, and the route by which projects arrive from P6", "You", "High — a shared import/export framework touching every module; needs template definition, validation, error reporting and a staging area", "Decided"),
    ("D-22", "2026-08-15", "SPEC-planning-budget.md adopted as the planning/budget contract", "Your handover of the full spec. Deltas implemented: derived netRate with inbound ignored (CALC-01), crew expansion with hours multiplied not divided (CALC-02/UT-09), rate-missing writes no build-up line (IT-08), budgetQty vs contractQty never crossed (CALC-05), difficultySrc recorded, resourceAffinity removed (RG-02), and the KX-GOV-002 gate with VAL-01..07 wired into budget generation as 409 GATE_FAILED", "You", "Deliberately deferred, per the spec's own open items: CALC-03 activity tiers (no Activity entity yet), the four-class roll-up (OPEN-01/02 unpinned), budgetQty derivation (OPEN-04), crew role-to-resource mapping (undefined in the spec)", "Decided"),
    ("D-21", "2026-08-17", "The resource request is ours; the purchase requisition is S/4's", "Your ruling: \"Resource request is KONSTRYX doc, Purchase request is S/4 number not internal.\" RR keeps its KONSTRYX number range, documented aspect, status model and approval. PR draws no number range and gets no docNo — its identity is the S/4 requisition number, and prNo stays empty until S/4 accepts it. This resolves a real contradiction that would have been built the wrong way: the procurement wireframes render the PR as \"Read-only from S/4\" while INTEGRATION.md says KONSTRYX creates it. Both are right about different halves — KONSTRYX initiates, S/4 numbers and owns", "You", "Implemented: PurchaseRequisition moved from the s4mirror aspect to s4outbound (a mirror defaults syncStatus to OK, which would call a requisition that never reached S/4 a good one; outbound defaults to NOT_SENT and keeps what S/4 said when it refused). A regression check asserts no PR number range exists and none was invented", "Decided"),
    ("D-20", "2026-08-15", "Cost nature is six, the ledger is four, and they never meet", "Your wireframe answer: cost nature = the six verticals (MR, MPR, EQR, VR, SF, SC), computed from the resource build-up; the Budget Ledger four (Original / Shift / Risk Transfer / Variation, KX-BUD-004) is a movement taxonomy computed from ledger entries. My earlier four-category cost framing was wrong and is retired", "You", "Both implemented: budget lines carry the six; every movement is one ledger entry in one of the four", "Decided"),
    ("D-21", "2026-08-15", "Build-up recipes are keyed on the CBS leaf", "Your wireframe answer: Resource x Linked CBS x Activity x Company. A BOQ line resolves through its CBS leaf; nobody keys resources per line; MANUAL build-up is a flagged exception awaiting a recipe, not a way of working", "You", "Implemented, incl. the governance consequence: two lines on one leaf share one recipe, so spec variance needs a distinct leaf or activity code", "Decided"),
    ("D-19", "2026-08-15", "Flexible approval workflow on every object", "Your instruction. Extends the approval framework already modelled from budgets to all masters and transactions, with the workflow configurable rather than coded", "You", "Engine built and verified. Value bands, approver personas, separation of duties, delegation and withdrawal are all configuration. Remaining: the inbox screen and wiring submit into each object's lifecycle", "Decided — engine done"),
]
body(ws, 6, decisions, [8, 12, 44, 62, 22, 42, 12], status_col=7)
ws.freeze_panes = "A6"

# ---------------------------------------------------------- 4. Open Decisions
ws = wb.create_sheet("Open Decisions")
title(ws, "Open decisions — needed from you",
      "These block or shape work already in the sequence. Ordered by when I need the answer.", 7)
header(ws, 5, ["ID", "Question", "Why it matters", "Options", "Blocks", "Status", "Needed by"])

opens = [
    ("Q-16", "Which verticals actually mobilize and de-mobilize?",
     "The overview now scores a reservation against the chain its vertical has, and MOB/DMB are the two steps that vary. I ruled them in for EQR, VR and the two scaffolding/formwork verticals — a resource that arrives as an instance and leaves again — and out for MR and MPR. MR is safe: concrete is poured. MPR and SCR are a judgement I made without evidence: a crew is mobilized to site in ordinary usage, but there is no instance and no condition checklist, which is what the chain's mobilization step actually is. If manpower mobilization is a step you want tracked, it is a different document from the plant one and the chain for MPR is nine steps, not eight. Same question for subcontract",
     "Confirm the split as built (MOB/DMB for asset verticals only) / add a manpower mobilization step / treat SCR separately",
     "The denominator every manpower and subcontract reservation is reported against",
     "Open", "Before the manpower chain screens"),
    ("Q-15", "Starter content pack: ship it, or only on a demo tenant?",
     "KONSTRYX ships masters, a sample project and the canonical RR thread to every tenant. Useful on an evaluation tenant in front of a starter S/4; actively harmful on a customer system, where it puts rows nothing can cleanly remove and - now that release pushes on its own - possibly documents in their S/4. Three shipped-data failures this build all reduce to the same disease: the pack asserted a relationship with a system it had never seen",
     "Detect a starter system / declare a contentProfile at subscription (recommended, default CLEAN) / ask on first run. Detection rejected: inferring it from company code 1710 is the same species of guess that produced the profit-centre bug. See docs/ARCHITECTURE_TENANT_CONTENT.md",
     "Content pack strategy; whether demo content needs to be removable at all",
     "Open", "Before the first customer tenant"),
    ("Q-01", "Document number ranges: per company or group-global?", "ANSWERED: configurable per object. Built and verified both scopes", "—", "—", "Closed", "Answered 2026-08-15"),
    ("Q-13", "Where does KONSTRYX surface — Work Zone or the S/4 launchpad?", "ANSWERED: Option A, S/4's own launchpad. See D-16", "—", "—", "Closed", "Answered 2026-08-15"),
    ("Q-14", "Does numbering need to be gap-free for audit?", "ANSWERED 2026-08-17: gaps are acceptable provided a valid audit log is available — a cancelled document leaving a gap is fine. Current behaviour (numbers issued on activation, abandoned drafts consume nothing) therefore stands; the audit log is the control, not the sequence", "—", "—", "Closed", "Answered 2026-08-17"),
    ("Q-02", "What is in the EC&O starter content pack?", "ANSWERED 2026-08-17: the masters and a sample transaction exactly as they appear in the wireframe today, end to end and demo-ready — not a curated subset. The wireframe's own data is the pack", "—", "—", "Closed", "Answered 2026-08-17"),
    ("Q-03", "Approval schemes: who approves what, at which value bands?", "ANSWERED 2026-08-17: confirmed — keep the shipped thresholds (Budget 100k/1m, Resource Request 250k/1m) as they stand. Approver personas remain unnamed and configurable in-app", "—", "—", "Closed", "Answered 2026-08-17"),
    ("Q-04", "Attachment storage: SAP Object Store or HANA LOB?", "ANSWERED 2026-08-17: neither as a fixed choice — attachments get a configuration that can point at any DMS. Storage becomes a per-tenant setting rather than a build-time decision, which supersedes the Object Store vs HANA LOB framing", "—", "F-04 — needs rework to a configurable DMS target", "Closed", "Answered 2026-08-17"),
    ("Q-05", "The canonical demo numbers do not reconcile", "ANSWERED 2026-08-17: correct the header to 685,080 — the line values and the per-WBS commitment split are right, the header was wrong. The L1 rate question falls away with it", "—", "—", "Closed", "Answered 2026-08-17"),
    ("Q-06", "BOQ import template — confirm the column set", "ANSWERED 2026-08-17: there is no single template to build to. Bills arrive from different estimating tools — Candy, RAI and others — so the importer must be flexible: a mappable column set per source rather than one fixed contract. This changes the shape of B-04, which was scoped to import a known template", "—", "B-04 Uploads — needs rescoping to a per-source column mapping", "Closed", "Answered 2026-08-17"),
    ("Q-07", "CBS instance versioning: copy-on-create or live reference to the library?", "Open item in Data Model Spec section 10. Affects whether library changes propagate into running projects", "Copy-on-create (proposed) / live reference", "B-01, B-03", "Open", "Before Project Setup"),
    ("Q-08", "Encumbrance currency: company currency or group reporting currency?", "ANSWERED 2026-08-17: both — the encumbrance is held in company currency and also carried at group reporting currency, not one or the other. Budget lines and ledger entries are single-currency today, so this needs a second amount (or a conversion at read) before group-level budget reporting is honest", "—", "B-06 Budgeting — the budget ledger carries one amount today; dual currency is not built", "Closed", "Answered 2026-08-17"),
    ("Q-09p", "S/4 sandbox tenant - RESOLVED for projects", "Communication user + arrangements SAP_COM_0308/0008 active. The connector ran live: KX-S4-001 created in the tenant from KONSTRYX through release -> sync, confirmed by an independent read (profile YP05). WBS element read-back also confirmed: A_EnterpriseProject is keyed by ProjectUUID (a GUID), not the Project string — once read with the correct key, to_EnterpriseProjectElement returns both elements (the auto-created root KX-S4-001 and the pushed KX-S4-001.1 'Enabling works'). Remaining: the other scenarios (procurement, finance) as their modules need them", "Rotate the credential that transited chat transcripts when convenient; move to a BTP destination at deployment", "S/4 connector - project scenario DONE, incl. WBS read-back", "Closed", "2026-08-16"),
    ("Q-09", "S/4 dev tenant — what is actually needed (merges the old S-15)", "ANSWERED 2026-08-17: already shared — the sandbox tenant with its communication user, and SAP_COM_0308/0008 active. Proven live by the project connector (see Q-09p). What remains is per-scenario, not per-tenant: the procurement arrangements (SAP_COM_0053 for the requisition, SAP_COM_0193 for the order) need activating before the PR push can be tested", "—", "Project sync done; procurement arrangements still to activate", "Closed", "Answered 2026-08-17"),
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
    (3, "Masters", "Resource hierarchy, CBS library, rates, vendors, scoped GROUP/COMPANY + promotion queue", "Resource hierarchy, CBS library, rates, vendors and the promotion queue all run; covered by test_rates, test_variants and test_foundations", "Q-01, Q-02", "Done"),
    (4, "Templates", "Project templates: CBS tree + default resources", "Instantiation copies the CBS tree and the default resources; covered by test_templates, which did not exist until 2026-08-29 and found on its first run that neither name nor cost nature was being copied", "Masters", "Done"),
    (5, "Project Setup", "Project, WBS, CBS instance, S/4 Enterprise Project mirror", "Project, WBS, CBS instance and the outbound ERP push; covered by test_project", "Templates, Q-07, Q-09", "Done"),
    (6, "Uploads", "BOQ import, estimate import, versioning with progress carry-forward", "BOQ import and allocation run (test_boq). Estimate import and version carry-forward are not built, which is what keeps this in progress", "Project Setup, Q-04, Q-06", "In progress"),
    (7, "Project Planning", "Activity layer, native entity + P6 adapter", "Activity layer, critical path and the P6 adapter; covered by test_schedule and test_p6", "Project Setup", "Done"),
    (8, "Budgeting", "Budget from BOQ/CBS, 4-category ledger, approval, baseline, encumbrance", "Build-up, ledger, approval, baseline and encumbrance; covered by test_budget and test_distribution", "Uploads, Q-03, Q-08", "Done"),
    (9, "Project Execution", "RR->CLS chain end to end, material + manpower, chain steps 5-10", "RR to reservation to requisition runs end to end (test_chain, test_procurement, test_execution, test_issue). CMT is unwired and the chain-step pages still read a local file, so not finished", "Budgeting", "In progress"),
    (10, "Project Commercial", "Client billing, variations, payment certificates", "Client billing, variations and payment certificates; covered by test_certification, test_variation and test_finance", "Execution", "Done"),
    (11, "Plant Department", "Equipment, fleet, scaffolding/formwork", "Your sequence — explicitly after the core", "Execution", "Not started"),
]
body(ws, 6, seq, [5, 30, 62, 66, 26, 13], status_col=6)
ws.freeze_panes = "A6"

# ------------------------------------------------------ 5b. Suggestions & flags
ws = wb.create_sheet("Suggestions")
title(ws, "Suggestions and flags raised during the build",
      "Everything recommended or warned about, kept in one place for review. Nothing here is decided.", 7)
header(ws, 5, ["ID", "Area", "Suggestion or flag", "Why it matters", "My recommendation", "Status", "Raised"])

suggestions = [
    ("S-01", "Plan", "Re-baseline the MVP estimate", "Personalization, attachments and approvals apply to every object. Wireframe v12 is 41 modules / 434 screens; the 22-week plan with one UI5 developer does not carry that layer", "Re-baseline before any client date is committed, or cut MVP screen scope", "Open", "2026-08-15"),
    ("S-02", "Architecture", "Revisit tenancy once client count grows", "Dedicated deployment means N upgrades for N clients. The model is tenancy-neutral so the switch is cheap now and costly per live client later", "Revisit at 5-10 clients; decide before the first go-live, not after", "Open", "2026-08-15"),
    ("S-03", "UI", "Split into task-focused apps per document type", "S/4 surfaces one app per task, reached from a tile. KONSTRYX is currently one app with in-app routing across ten document types", "Split as screens are built; register an intent per app", "Open", "2026-08-15"),
    ("S-04", "Deployment", "Move the UI to the HTML5 application repository", "The approuter currently routes the UI through the Java service, which is fine for one app but wrong for scaling and caching", "Move when the app splits into several apps", "Open", "2026-08-15"),
    ("S-05", "Authorization", "A declared path that does not resolve failed per request, not at boot",
     "A 500 on somebody\u2019s screen, and only on the screens of users whose grants are scoped, which is how the RequestOverview outage went unnoticed until it was in front of someone. The check now walks each path step by step through its associations at boot and on demand",
     "Closed with S-26, which is the same check. The remaining difference is that it resolves against the persisted entity rather than each service projection over it \u2014 a projection that omits an association a scope path uses would still fail per request. Recorded as S-45 rather than left implied",
     "Closed", "2026-08-29"),
    ("S-45", "Authorization", "The path is now checked where it is used, not only where it is declared",
     "The instance filter is applied to whichever projection is being read, so a path can resolve perfectly on the persisted entity and not on a projection that trims the association it walks -- and the entity is then fine through one service and 500s through another, for scoped users only. Checking the entity alone answered a question next to the one that is asked",
     "Every projection whose root is the protected entity is resolved as well, naming the service in the message. The walk that finds those roots is the enforcement handler\u2019s own, moved rather than copied -- two walks that agree today are two walks that can stop agreeing. Proved by adding a projection that trims the association, watching both paths fail on it by name, and removing it: nothing in the delivered model is broken, which is exactly why it needed proving "
     "that way",
     "Closed", "2026-08-29"),
    ("I-81", "Reporting", "Two rows overflowed their sheet, and the sheet still looked like a sheet",
     "Q-16 and B-10 each carried one field more than their table has columns. A row like that does not fail, it slides: everything past the extra field moves a column right, so Status was rendered under the Needed by heading, took no colour because the value sitting there was prose rather than a state, and the last field spilled into a column with no header. B-10 read Done - the fallback path; the destination path is unverified in a cell meant to hold one word. Found by checking tuple arity after I noticed my own new row might have gained a field",
     "Both rows repaired with nothing dropped -- the extra text folded into the field it was continuing. The durable half is a guard in body(): widths is already per-column, so it knows the table width, and a row wider than that now refuses to be written. Overflow only: a short row leaves trailing cells empty, which is how the small fixed blocks are written and is visibly a gap rather than a silent shift",
     "Closed", "2026-08-29"),
    ("I-82", "Reporting", "The summary block carried figures that were true once",
     "It said 8 OData V4 services against nine, and git, 48 commits against a hundred and thirty-nine. Both were right when typed. A figure that is only right once is worse than no figure, because it is read as current -- and this is the block somebody reads first",
     "Counted at generation time: services from the service declarations, commits and the last commit date from git. It also now says how many files are uncommitted, because a commit count alone reads as this is what is saved, and today it is a hundred and seventy-eight files short of that",
     "Closed", "2026-08-29"),
    ("I-80", "Modelling", "Two projections of one entity in one service is a compile error, not a runtime surprise",
     "Learned while trying to build the probe above. CDS refuses a second projection over the same entity within a service unless one carries @cds.redirection.target, because it cannot decide where the associations pointing at that entity should redirect. The probe had to go in a different service",
     "No change -- recorded because it is the compiler catching, at build time, a near neighbour of the collision S-44 describes at runtime. The runtime one is across services, where the compiler has nothing to say",
     "Closed", "2026-08-29"),
    ("I-78", "Project Setup", "An instantiated cost breakdown arrived unnamed and all direct",
     "Both ways a project gets its breakdown \u2014 from a template, and from the library directly \u2014 built the instance row themselves, and both copied the code, the level and the parentage while copying neither the name nor the cost nature. A client instantiating a template got twenty-five unnamed nodes, every one DIRECT, when Preliminaries, site establishment, temporary works and supervision are INDIRECT in the library. Not cosmetic: the allocation engine reads costNature to decide what is a pool and what absorbs, so an overhead arriving as direct cost is spread onto itself and the total still reconciles",
     "One copier, in prj.CbsInstantiation, called by both. The field list existing twice is what let them agree on everything except the two fields that mattered. Found by writing the first test the template path has ever had \u2014 it survived because the delivered sample is seeded row by row rather than instantiated, so the demo showed a correct tree while the code that builds a client\u2019s tree did not",
     "Closed", "2026-08-29"),
    ("I-79", "Reporting", "The phase sheet said Not started against five phases that run",
     "Masters, Project Setup, Budgeting, Project Execution and Project Commercial all read Not started while the regression exercises every one of them end to end. The sheet was written as a plan and never updated as the work landed, so any percentage read off it was wrong \u2014 and it is the sheet somebody would read to answer how far along this is",
     "Set from what the suites actually cover, and each row now names the evidence so it cannot rot silently again. Uploads and Project Execution are In progress rather than Done, because estimate import and CMT are genuinely not built",
     "Closed", "2026-08-29"),

    ("S-06", "Local dev", "H2 is in-memory - nothing survives a restart", "Promotion requests, drafts and anything created during a demo are lost when the service restarts. Seed fixtures reload; transactional work does not", "Make H2 file-backed, or point local dev at HANA Cloud, before any live demo", "Open", "2026-08-15"),
    ("S-07", "Build", "Run npm install after every mbt build", "The MTA build prunes devDependencies at the root, removing @sap/cds-dk, and the next Maven build fails with 'cds' is not recognized", "Add it to the build script or CI pipeline", "Open", "2026-08-15"),
    ("S-08", "Quality", "Verify UI work visually, not through the DOM", "DOM text, network traces and per-element geometry all reported success while the screen was blank for an hour. Only a screenshot and an ancestor-chain walk found it", "Screenshot every UI change; measure ancestors, not the element", "Adopted", "2026-08-15"),
    ("S-09", "Demo data", "Settle the canonical figures", "The wireframe header says AED 716,044 while its own line values sum to 685,080 and reconcile to the per-WBS commitment split", "Correct the header, or supply the intended numbers", "Open", "2026-08-15"),
    ("S-10", "Compliance", "Confirm whether numbering must be gap-free", "Numbers are issued on activation so abandoned drafts do not consume them, but a cancelled document still leaves a gap", "Confirm per document type; some jurisdictions require unbroken sequences", "Open", "2026-08-15"),
    ("S-11", "Masters", "Promotion collision currently blocks", "When two companies hold the same code locally, promotion is refused and names both. Merge or force-rename are the alternatives", "Keep blocking unless the business prefers a merge; it is a one-method change", "Open", "2026-08-15"),
    ("S-12", "Security", "Review role collections before go-live", "The XSUAA Admin role bypasses the data-driven authorization layer as a bootstrap path, and service-level @requires still gates entry independently of the persona model", "Security review of both layers before the first client", "Open", "2026-08-15"),
    ("S-13", "Masters", "Reuse the content pack mechanism for the starter pack", "Versioned, insert-if-missing, never overwrites client edits - already built and proven for number ranges", "Ship the EC&O starter pack the same way", "Open", "2026-08-15"),
    ("S-14", "Masters", "Master editing needs draft handling", "A master screen that cannot be maintained is half a screen, and the draft pattern is inherited by every later module", "Build it before Templates so the pattern is settled once", "In progress", "2026-08-15"),
    ("S-15", "Integration", "Merged into Q-09", "Was a duplicate of the S/4 tenant question; the concrete list of what is needed now lives on Q-09", "See Q-09", "Merged", "2026-08-15"),
    ("S-37", "Content", "The demo pack charges cost to reservation lines for resources that were bought",
     "createReservation consumes only the lines decided IN_HOUSE and createRequisition only those decided PROCURE, both reading the same advisory field, so the two branches are disjoint and no action can put cost on both. Five seeded reservation lines have it anyway: RR-2026-0188 lines 2, 4 and 5 (96,422.40), RR-2026-0162 lines 2 and 5 (283,180.00) and RR-2026-0148 line 3 (3,600.00). Every one is also requisitioned, ordered and invoiced, and on RR-2026-0162 line 2 the reserved and invoiced figures are identical at 261,780.00, which is the same money twice rather than a part-stock part-bought split. The pack contradicts itself: RR-2026-0148 line 2 is decided PROCURE and carries costToDate 0.0, which is the shape the other five should have",
     "The narrow correction is to zero costToDate on those five and leave the lines themselves alone, so a hired-in crane still shows on the reservation for allocation while its cost stays on the invoice where it belongs. Not done unilaterally for two reasons. It moves the headline figures on the project most likely to be demonstrated, and it removes the only seeded example of a line with spend to floor a reduction against, which test_variation reads. And it would not repair a tenant already seeded: packs insert what is missing and never update, so a version bump reaches new tenants only. Until it is ruled on, I-72 states the overstatement on the report itself",
     "Open", "2026-08-29"),
    ("S-31", "Data model", "A subcontract has no WBS and no CBS, so its cost lands nowhere",
     "SubcontractRequest carries a project, a vendor and a contract value. Certified value therefore cannot be placed on a budget line, cannot be compared against a budgeted amount, and cannot be rolled into a cost node — while the period report already counts it as actual cost. On the seeded portfolio that is 2,678,260 of certified work the control record cannot see (I-71). Subcontract is one of the six cost natures the budget taxonomy is built on, so this is a hole in the middle of the model rather than at its edge",
     "Two shapes, and the second subsumes the first: a WBS and CBS on the SR header, or scope lines each carrying its own assignment and value with the certified amount apportioned across them pro rata. Packages that span several parts of a job need the second. Either way the seeded subcontracts need assignments, which is fixture data I should not invent — the question is yours before the build, not after",
     "Open", "2026-08-29"),
    ("S-30", "Performance", "The control refresh rescans every reservation line",
     "encumbranceByWbs selects all reservation lines and filters in Java, once per cost node and cost nature on the budget — and now that the refresh runs on the chain rather than on a button, that happens on every goods issue rather than when somebody asks. Correct, and quadratic in the wrong two things",
     "Filter the select by project, and read the request line in the same query rather than one lookup per row. Left as it is for now because the shape is right and the cost is not yet felt — worth doing before a tenant with real volume, not before",
     "Open", "2026-08-29"),
    ("S-29", "Authorization", "The persona layer governs 32 of 107 entities",
     "AuthorizationHandler.guard() returns early when an entity is absent from the persona catalogue, so an entity with no auth object has no control at all — not a default-deny, no control. Counted against the model today, three quarters of the persisted entities are in that state. Many are rightly global (number ranges, the fiscal calendar, the trade catalogue), but the list also holds documents that carry money and belong to one project: PaymentCertificate, SubcontractRequest, PurchaseOrder, SupplierInvoice, GoodsReceipt, VariationOrder, ReservationClosure, SiteReceipt, ReservationLine, BOQItem, Allocation. A persona scoped to one project can read another project's certificates and invoices straight off OData",
     "Two halves. Decide per entity whether it is global or project-scoped — the ones above answer themselves — then add the object and its grants together, because adding the object alone turns a control on and locks people out (that is I-64 and I-65, twice). The line-level entities can follow their header rather than be decided separately, which is how KX_RES_VARIATION_LINE was done",
     "Open", "2026-08-29"),
    ("S-28", "Data model", "A variation moves one reservation line per document",
     "ReservationVariation carried a composition of lines and vary() only ever wrote one of them, so the slab-cycle extension that holds both cranes thirty days was two documents rather than one with two lines. Each was complete and carried its own before and after, so nothing was lost -- but a reader counting variations counted the decision twice, and the narrative was the only thing tying the pair together",
     "vary() takes a list of line moves. Chosen over letting a second call append to a same-day variation, which would have made the document boundary implicit -- what belongs on one document is the decision, not the date. Planned in full before anything is written: every line is validated first and a document that cannot be applied whole is not applied at all, so a list carrying one closed line moves neither of them. Both shapes at once is refused, and so is the same line twice: two ways of saying where a line ends up are two answers that can disagree. One header with the summed delta, one line per move, one chain link and one budget refresh",
     "Done", "test_variation 12: two lines by one document, the whole-or-nothing refusal, and both ambiguous shapes"),
    ("S-48", "Budget", "A reservation lock the budget has no heading for was held nowhere, silently",
     "Found while checking that a multi-line variation reached the budget once: it reached it never. Encumbrance is attributed by walking the budget own lines and asking what is locked against each cost node and cost nature, so a lock against a node the budget has no line for is not asked about, and a manpower lock on a node carrying only a materials line is filtered out on the way past. Neither falls out of a total -- the total is never reached -- so the control record reads fully available while over a million sits locked. The shipped sample shows it: PRJ-001 holds 204,990 of lock in its control record and 583,880.16 more that no budget line carries a heading for, so the record is not wrong by a rounding -- it is right about a quarter of what is locked",
     "Reported, exactly as its two twins already were. uncoveredCommitment and unplacedActual have said this about orders and invoices since they were built and the encumbrance third was simply never written; it is now unheldEncumbrance, same walk, same coverage test, its own sentence in the refresh message. Reported rather than corrected because where the lock should land is a budget line or a corrected assignment, and both are somebody decision -- the same reason the other two report. It is the worst of the three to leave silent: an order or an invoice is money somebody will present a demand for, an unheld lock is a promise the job made itself "
     "that only the reservation remembers",
     "Done", "test_budget 5: a lock on an uncarried node moves no budget line, and the refresh names it and its amount"),
    ("S-27", "Authorization", "Actions are outside the persona layer entirely",
     "AuthorizationHandler guards CREATE, READ, UPDATE and DELETE. An action is none of those, so nothing a document actually DOES passes through it - raisePullRequest, recordGoodsIssue, vary, sign, approve, close, release, refreshControl. What gates them is the service-level @requires alone, which is a role check and not the data-driven control the persona model exists to be. The practical effect: a persona with READ on an object can drive every action on that service, and a persona with no grant at all on the object can still fire the action that writes it",
     "Map each action to an activity on its object - a raise is 01, a correction 02, a state change probably its own code - and guard them the way the four events are. Roughly forty actions across eight services, so this is a decision about the mapping as much as a change to the handler, and worth taking before the first client rather than after",
     "Open", "2026-08-29"),
    ("S-26", "Authorization", "A control that cannot find its target enforces nothing, quietly",
     "KX_COST governed an entity deleted some releases ago and nothing noticed: an object whose entity cannot be found is skipped rather than refused, so the control reads as configured and enforces nothing. The catalogue is data and the model it points at is code, and the two drift apart the first time either is renamed with neither side complaining",
     "Checked at boot and on demand, against the model, in four ways: the entity resolves; each scope path resolves step by step through its associations; a path does not stop on an association instead of a value; and no two objects claim the same entity. Each finding says what it costs rather than that it is wrong -- no control at all, or every scoped read of that entity failing. Reported, not fatal: a tenant that will not start is a tenant nobody can correct. The catalogue is sound today, so the check was proved by breaking it four ways rather than by passing",
     "Closed", "2026-08-29"),
    ("I-77", "Authorization", "The boot check pinned the permission catalogue to the pre-seed state",
     "Caught by my own probe reporting 31 objects when the database held 34. Spring gives an unordered ApplicationReadyEvent listener lowest precedence, so two of them run in registration order, which is not an order -- the new check read the database before content deployment had written to it. Worse than a useless check: catalogue() caches for the life of the process, so priming it at boot would have fixed every enforcement decision to whatever existed before the seed. Entities silently unprotected, for the life of the process, caused by the check meant to find exactly that",
     "Two fixes, because either alone leaves it fragile. Content deployment is now explicitly ordered first and the check 100 after it; and the check reads a fresh catalogue rather than the shared cached one, so even a future ordering mistake can only make the report wrong, never the enforcement",
     "Closed", "2026-08-29"),
    ("S-44", "Authorization", "Two objects on one entity is a silent loss, now reported",
     "Found while probing: the catalogue is a map keyed by the entity an object protects, so a second object naming the same entity replaces the first. The loser is still in the table, still looks delivered, and governs nothing -- and which one survives is load order. The delivered 31 are distinct, so it does not bite today",
     "The boot check counts the rows rather than the map, because the map is where the evidence was lost. Whether the model should instead allow several objects per entity is a separate question and not one worth opening while nothing needs it",
     "Closed", "2026-08-29"),
    ("S-16", "Architecture", "The reader principle now has an exception", "D-17 makes the project KONSTRYX-mastered while procurement and finance stay S/4-owned. The principle is no longer 'S/4 owns transactions'; it is object by object", "Restate the rule in the product documentation so the exception is deliberate rather than remembered", "Open", "2026-08-15"),
    ("S-17", "Integration", "A project ERP had never accepted still took commitments",
     "Both halves are now done. The state has been visible for a while; the block was not. Demonstrated rather than argued: BUD-2026-0103 was submitted, approved by three people and baselined at 7,525,075.47 against PRJ-003, which ERP had never heard of",
     "The budget is the project control figure, so submit and baseline both ask whether the project is in ERP. Asked at submit because that is where it is cheap to fix, and again at baseline because a budget submitted while the connection was down can be approved days later and would otherwise pass through a gate that closed behind it",
     "Closed", "2026-08-29"),

    ("S-18", "Architecture", "Build upload/download once, not per screen", "D-18 applies to every master and transaction. Bespoke import per screen is how 40 modules end up with 40 different error behaviours", "One framework: template definition, staging, validation against the same service rules, and an error report the user can correct and re-upload", "Done", "2026-08-15"),
    ("S-19", "Approvals", "The delivered value bands are mine, not yours", "The engine ships with Budget at 100k/1m and Resource Request at 250k/1m so it works out of the box. Nobody at Inflexion or a client has agreed those figures, and a demo will show them as if they were policy", "Replace them before any client sees the product. See Q-03", "Open", "2026-08-15"),
    ("S-20", "Approvals", "Separation of duties is on by default", "Someone who cleared step 1 cannot clear step 2 of the same document. In a small contractor one director genuinely is both signatures, so allowChaining exists per step to permit it", "Confirm the default is right for EC&O clients; it is a per-step switch either way", "Open", "2026-08-15"),
    ("S-21", "Approvals", "An approved document could still be edited underneath its approval",
     "Worse than the note said, and checked rather than assumed: a PATCH took a line on RR-2026-0310 -- a request already through approval, advisory, availability and reservation -- from 24 to 240, and because the value is stored rather than recomputed the line was left carrying a quantity and a total describing different requests, with the reservation still locking money against the old one. The header was worse: a PATCH moved an Advised request back to Draft, which alone would have made any line guard a formality",
     "Lines refuse edits and deletes once the request leaves Draft or Rejected -- exactly the states submit accepts, so the editable window and the approvable window are one window. The status refuses to be written at all, forward as well as back: every legitimate move is made by an action, and actions write through the persistence layer where the guard does not sit, which is what makes it enforceable rather than a comment. The rule already existed for a baselined budget; this is the same rule, kept in the same way",
     "Closed", "2026-08-29"),
    ("I-75", "Integrity", "Three more documents took writes that only an action should make",
     "Having found one, I probed the rest rather than assume it was the only one. ReservationLine.encumberedAmount was writable -- the lock a variation exists to move, and which the budget reads as encumbrance, editable by PATCH with no before-and-after and no ledger entry. Budget.status was writable, and the baselined-amount guard reads it, so one call reopened every amount on a baselined budget. PaymentCertificate.status was writable, and Certified is what makes a certificate count as cost in the period report. Purchase requisitions and orders were already closed, being read-only projections",
     "The reservation line is read-only outright: nothing on it is typed. The two statuses are refused by a guard rather than an annotation, which is a deliberate choice -- a read-only element is stripped from the payload before handlers run, so the write is answered 200 and quietly dropped, and a caller is told its change took when it did not. The guard says which door the status moves through",
     "Closed", "2026-08-29"),

    ("S-22", "Approvals", "Editing a scheme mid-flight", "Instances freeze the step number and name at submission, so an in-flight approval survives a scheme edit. It still points at the step definition for the approver persona, and CAP draft activation can renumber those rows", "Confirm the intended behaviour: should a scheme edit affect approvals already running? Today it partly does", "Open", "2026-08-15"),
    ("S-35", "Planning", "Four-class budget roll-up blocked on OPEN-01/OPEN-02", "The spec itself flags that the budget-detail label conflates Class (L1) with control level (L3), and that the six verticals do not map 1:1 onto four classes — SF could be Equipment or Subcontract depending on pool vs vendor-supplied. Every scaffold project's split is wrong until pinned", "Answer OPEN-01 and OPEN-02 in the spec; the roll-up is a one-day build once pinned", "Open", "2026-08-15"),
    ("S-36", "Planning", "Crew roles have no resource mapping master", "Crew composition strings carry role tokens (SK, HLP) that no master resolves to a resource. Unmapped roles fall back to the norm resource, visibly labelled, so demand lands on the wrong resource in plain sight rather than invisibly", "Decide where the role-to-resource mapping lives — the Trade Catalogue is the natural home per the wireframe audit", "Open", "2026-08-15"),
    ("S-32", "Commercial", "Encumbrance lands in the budget on demand, not on event", "refreshControl summed open reservations into the control record only when called, so a reservation raised in the morning was invisible in the budget until somebody pressed refresh in the afternoon. Worse than staleness: on the seeded project all three derived columns read zero against work that had already spent 316,932 on signed hours, and a column that never moves never looks wrong", "Closed: BudgetHandler.refreshProject runs on the five events that move a control figure — reservation created, varied, closed, goods issued, signed days posted. Whole budget rather than the lines touched, because encumbrance is apportioned across every line sharing a cost node. test_variation asserts the event-driven result equals what the button produces, which is the invariant that matters: two paths computing the budget differently would be worse than the staleness this replaced", "Closed", "2026-08-29"),
    ("S-33", "Planning", "Spec variance needs a distinct CBS leaf — now ENFORCED as VAL-05", "The gate fails any CBS leaf carrying two material grades, exactly as spec Part A.3 demands, and budget generation refuses GATE_FAILED while it stands", "Closed by implementation; the stewardship guidance should still cite VAL-05", "Closed", "2026-08-15"),
    ("S-34", "Execution", "Reservation encumbrance had no duration dimension",
     "estTotal was unit rate x quantity, which answers how many at what each and not what a hire costs. One crane at 320 a day priced to 320 is a single day, never what the request meant, so the only way to get a duration into a request was to type the total by hand -- which is how the seeded thread carries 2 cranes x 320 x 432 days with nothing in the model saying 432",
     "ResourceRequestLine carries periodFrom and periodTo, and submit prices a line as qty x rate x days with both ends counted -- a hire from the 1st to the 1st is one day, because the day a crane arrives is a day it is paid for. Both dates or neither, and a period that ends before it starts is refused. ReservationLine records the duration it locked for, so the variation reads it rather than recovering it by division. A line with no period keeps the old arithmetic exactly: multiplying a per-tonne price by a duration would be inventing one",
     "Closed", "2026-08-29"),
    ("I-74", "Execution", "The reservation list reported a duration for resources that have none",
     "ReservationLines derived reservedDays as encumberedAmount / (qty x dailyRate), which is exact for a crane at 320 a day and meaningless for rebar priced by the tonne -- every material line in the portfolio read 1.00 days. Nothing on a reservation line says whether its rate is a daily one: the column is called dailyRate and holds a per-tonne price on material, so the division could not know what it was dividing",
     "The projection stops deriving it and shows what was recorded. The derivation survives in one place where it is provably safe -- inside the variation, where it reconstructs the same lock it came from and only when no duration was recorded, because a line reserved before the period existed would otherwise vary to zero. The ten seeded daily-rated lines now carry their duration in the fixture, transcribed from the locks they were already built from and only where the division lands on a whole number of days. The dates were not invented: the encumbrance says how many days, not which",
     "Closed", "2026-08-29"),
    ("S-38", "Execution", "One column carries a daily rate and a unit price",
     "ReservationLine.dailyRate holds 320 a day for a crane and 3,422 a tonne for rebar, and ResourceRequestLine.estUnitCost does the same upstream. Every reader has to know which it is looking at from context, and I-74 is what happens when one does not. The period now tells them apart in practice -- a line with a period is priced by the day -- but that is a convention holding a model gap shut, not the model saying so",
     "Either a rate basis on the resource (per day / per unit) that pricing reads, or two columns. The first is the smaller change and the one the rate master is already shaped for. Not urgent while the period carries the distinction, and worth doing before a second reader needs it",
     "Open", "2026-08-29"),

    ("S-30", "Project Setup", "P6 import matches on project code, so a re-import is refused rather than merged", "Sending a revised P6 file is the normal way a planner works — the schedule changes weekly. Today the second file is rejected as a duplicate code, which is safe but not useful", "Decide what a re-import should mean: refuse, update the header, or reconcile the WBS tree adding and flagging removals. Reconciliation is the one planners will expect and the one that can silently orphan budget lines", "Open", "2026-08-15"),
    ("S-31", "Project Setup", "Only the project header and WBS come across from P6", "Activities, logic, durations, resource assignments and the baseline are all in the file and all ignored. That is the right first cut - KONSTRYX is not a scheduling tool - but it is worth being explicit that P6 remains the schedule of record", "Confirm the boundary: does KONSTRYX ever need activity-level data, or does it stop at WBS?", "Open", "2026-08-15"),
    ("S-27", "Seed data", "A half-seeded tenant left nothing behind to find",
     "The note is half out of date and its remedy was aimed at the wrong thing. There is no CSV loader at runtime -- no fixture reaches the jar -- and the content pack path already logs at ERROR naming the pack, the entity and the offending row by its natural key. What was missing was durability: the rows roll back, no registry row was written, and a tenant missing its personas looked identical to one that was never given any. The only trace was a boot log, and by the time anyone doubts the seed the container has restarted and taken it",
     "The attempt is recorded whether or not it worked -- ContentPack carries an outcome and the message, and a failure is written outside the cancelled change set so it survives the rollback that caused it. One WARN at boot counts the failures rather than leaving them one ERROR among hundreds. The service still serves: an operator pack failing is not a reason to take a tenant down, and there would be no way in to fix it",
     "Closed", "2026-08-29"),
    ("S-41", "Seed data", "Recording failures in the applied-check table is the load-bearing line",
     "The applied check reads the same table the failures now go in, so matching on packId and version alone would skip a pack that failed once for the life of the tenant -- turning a transient failure into a permanent one, which is worse than the problem it was fixing. Verified in one database rather than across a restart, because H2 is in-memory and a restart would have thrown the FAILED row away and proved nothing: the pack was broken, booted, corrected on disk and re-applied through the admin action with the FAILED row still present",
     "Only an APPLIED row counts as applied, and a row written before the field existed has no outcome and got there by succeeding, so it counts too. Both attempts are kept, the way ImportRun keeps every load",
     "Closed", "2026-08-29"),
    ("S-42", "Seed data", "One refusal was doing the work of three",
     "Not authorized on X said the same thing whether the user lacked a grant, was connected to no persona at all, or the tenant had no persona content -- and only the first is the user's to act on. The last denies every request from everybody, which reads as an authorization problem and sends whoever is looking into the persona model, where they find nothing wrong because there is nothing there",
     "The refusal path asks which of the three it is and says so. Two counting queries, and only on a request that has already been refused, which is exceptional and where the cost is nothing against being sent to the wrong place. The no-persona-layer message points at a content pack whose outcome is FAILED, which is what S-27 made there to find",
     "Closed", "2026-08-29"),
    ("I-76", "Authorization", "The guard does not cover draft events, and does not need to",
     "Checked while proving the refusal above is reachable, because a display-only user creating anything looked wrong. jin holds activity 03 on KX_RESOURCE_REQ and a POST to ResourceRequests succeeds -- a draft is not a CREATE, so the guard does not see it. Making it a document is, and that is refused. So a display-only user can scribble in a draft only they can see and cannot make it real",
     "No change. Recorded because it looks like a hole from the outside and is not one, so the next person to notice does not spend the afternoon I nearly did",
     "Closed", "2026-08-29"),
    ("S-43", "Authorization", "One branch of the diagnosis cannot be reached from a test",
     "The empty-persona-layer branch needs a tenant with no grants at all. Producing one means deleting 150 delivered grants, and delivered personas refuse deletion by design -- correctly. The other two branches are asserted end to end; this one is asserted only by its precondition, that the tenant does have a layer",
     "Left as it is. A fixture tenant seeded without the personas pack would cover it, and that is a larger thing than the branch is worth today. Same shape as the project gate, whose not-in-ERP-with-a-live-connection branch is equally out of reach offline",
     "Raised", "2026-08-29"),

    ("S-28", "Project Setup", "Which documents an unsynchronised project stops, and which it does not",
     "Answered per document type as the note asked. Creation is never blocked: a job is planned before it is registered anywhere, and refusing to let people plan would be refusing the normal case. What is blocked is commitment -- the two places where a project stops being a plan. Requests and reservations sit in between and are left alone: a reservation locks KONSTRYX money and posts nothing, so it is a plan with a number on it",
     "The budget at submit and baseline, and the requisition at push -- the latter was already refused by the WBS check, but it reported the first line rather than the project, which sent the buyer to a line that was not what was wrong. The project is now asked about first, so the message names the cause. One decision in S4ProjectConnector.blocker, shared, so the two callers cannot drift apart",
     "Closed", "2026-08-29"),
    ("S-39", "Project Setup", "The gate reads the connection as well as the status, and it has to",
     "NOT_SENT means two different things. On a tenant with no ERP configured there is nowhere to send the project, KONSTRYX is the system of record, and a status gate alone would make the product unusable offline -- every one of the 24 suites runs that way, as does any evaluation before a connector is wired. So NOT_SENT and PENDING refuse only where a connection exists. FAILED refuses either way: it is not a project waiting to be sent, it is one that was sent and turned down, and switching the connection off does not unsay that",
     "Recorded rather than remedied. The consequence worth knowing is that the rule means something different on a connected tenant than on a standalone one, and that is the intended reading, not a gap. The branch that cannot be exercised offline -- NOT_SENT with a live connection -- is the one branch of four the suite cannot assert",
     "Raised", "2026-08-29"),
    ("S-40", "Content packs", "The shipped sample arrives with budgets already baselined on projects no ERP has",
     "A content pack inserts rows rather than pressing buttons, so the two budgets it ships arrive Baselined without passing the gate above. Harmless as it stands -- the requisition side still refuses to post, so no money escapes -- and the alternative would be shipping a sample whose budgets cannot be shown, which is a demonstration of nothing",
     "Left as it is, deliberately, and recorded so it is not later mistaken for the gate leaking. Worth revisiting only if a tenant is ever expected to promote the sample project into real work",
     "Raised", "2026-08-29"),

    ("S-29", "Project Setup", "Project numbering is manual", "A project code is typed in and checked for uniqueness. Number ranges exist and are configurable, and other documents use them, but projects do not — partly because clients often carry an existing code from the contract", "Confirm whether project codes should be issued by a number range, typed, or either depending on the client", "Open", "2026-08-15"),
    ("S-24", "Attachments", "Attachment content is stored in the database", "LargeBinary in HANA is right for the documents that carry legal weight — drawings, permits, signed variations — because they are backed up and restored with the data they belong to. It is the wrong home for thousands of site photographs", "Decide whether photo-heavy objects go to an object store instead. It is a per-category switch if decided before volume builds up, and a migration afterwards", "Open", "2026-08-15"),
    ("S-25", "Attachments", "Any authenticated user could upload any file of any size",
     "The storage half. Content lives in the database, so an unbounded upload is paid for by every backup and restore of the tenant rather than by whoever made it, and nothing anywhere said no",
     "A ceiling, measured on the bytes that landed rather than on Content-Length -- that header is the client account of what it sent, and a cap that trusts it can be told any number. The check therefore runs after the runtime has stored the content and throws, which unwinds the change set: verified that the previous file is still the one served back afterwards, rather than assuming the rollback. 25 MB by default because that clears a marked-up drawing or a scanned permit and stops what this is not for; KX_ATTACHMENT_MAX_MB where a client genuinely needs more, so they are not told their file is wrong. The malware half is separately raised",
     "Closed", "2026-08-29"),
    ("S-47", "Attachments", "Nothing scans an upload for malware",
     "The other half of S-25 and the one I cannot build here. KONSTRYX accepts arbitrary bytes from any authenticated user and hands them back to anybody who can read the object, which on a client tenant is a distribution route. The size cap narrows the target and does nothing about the content",
     "SAP BTP Malware Scanning, called on the upload path before the content is kept -- the same place the size ceiling sits, so the shape is already there. It needs a service instance and a subscription, which is a provisioning decision rather than a code one, and it belongs before the first client upload rather than before the first client",
     "Raised", "2026-08-29"),

    ("S-26", "Attachments", "A delete could take the history or the evidence with it",
     "Both halves confirmed by doing them. Three uploads of one file made versions 1, 2 and 3; deleting version 2 was accepted and left version 3 pointing at a row that is not there -- no error anywhere, the successor still reads fine, and the history simply has a hole in it. The second half is worse: an attachment on a document in front of an approver could be deleted, leaving a decision recorded against a file nobody can produce",
     "A version another version supersedes cannot be deleted; the head can, because nothing points at it and the rule is about what breaks rather than about age. An attachment on a document that has been put up for a decision cannot be deleted either -- approved, rejected, or pending, because evidence pulled from under a live decision is the worst of the three. A withdrawn submission does not count: nothing was decided on it, and the usual reason to withdraw is that the wrong thing was attached. isObsolete is the way through, because a refusal with no alternative is a rule people work around",
     "Closed", "2026-08-29"),
    ("I-83", "Attachments", "The attachment rules applied to one door of two",
     "Found while deciding where to put the delete guard. sys.Attachment is exposed as CollaborationService.Attachments and WorkflowService.RequestAttachments, and the handler was bound to the first only. Uploading through the workflow door skipped the versioning outright -- a second upload of the same file came back as version 1 again rather than version 2 superseding the first -- and skipped the existence check, so an attachment was accepted against a resource request that had never been created. The target is polymorphic, an entity name and a key, so no foreign key catches that: the handler IS the foreign key, and one bound to one projection of two is half a constraint",
     "Every handler now names both projections, and the delete guard was written for both from the start rather than added to one and copied. The suite exercises the second door on its own -- versioning, the bogus target, and the chain guard -- because a rule that is only tested through the door it was written for is a rule that is only true there",
     "Closed", "2026-08-29"),
    ("S-46", "Attachments", "A third projection is declared and reaches nothing",
     "AuthorizationService.Attachments is declared over sys.Attachment but no such EntitySet appears in that service metadata, and a request to it returns 404. Not a leak -- there is nothing there to reach -- but a declared door that does not open is either a mistake or a leftover, and while it reads as a door somebody will eventually write against it",
     "Work out whether it was meant to be reachable. If it was, it needs the same handlers as the other two; if it was not, delete the line. Not urgent: it exposes nothing today",
     "Raised", "2026-08-29"),

    ("S-23", "Frameworks", "Content packs now carry references", "Delivered content could previously only hold flat rows, which is why the approval schemes could not ship as content. Packs now resolve a row by natural key at deploy time and match on composite keys", "Use the same mechanism for the EC&O starter pack (S-13) and for delivered personas", "Open", "2026-08-15"),
]
body(ws, 6, suggestions, [8, 16, 44, 62, 52, 12, 12], status_col=6)
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
    ("I-49", "UI", "Every user on every tenant was greeted as the same fictional person",
     "The screens read the signed-in user out of the UI's own JSON fixture, where it was the wireframe persona Sridhar Iyer / Plant Allocation Lead / INFC. It had no relationship to the identity the service enforces against. That is worse than showing nothing in a multi-tenant product: it invites someone to believe they are looking at their own authorization when they are looking at a mock-up, and it hid the fact that no persona is assigned to any real user",
     "CollaborationService.whoAmI() returns the XSUAA logon name, and the screens display that string rather than a prettier one - it is what the approval trail, the import history and every persona assignment are keyed on, so a friendlier name would mean the identity a person reads is not the identity their actions are filed under. It also reports isAdmin and hasPersona separately, because the Admin scope bypasses the permission model rather than satisfying it and no screen can infer that from the data it is shown",
     "Closed", "2026-08-25"),
    ("I-50", "Integration", "Organizational values were shipped in a content pack, which cannot be right on more than one tenant",
     "Plants, purchasing organizations, profit centres, cost centres and project profiles are configuration of the customer's own S/4. The pack that seeded my434396 carried values read off my401381, and a live push came back Profit Center 10001000 does not exist - plausible values that belonged to a different system. Because packs are insert-if-missing, the tenant could not be corrected by shipping a new pack either, which is why konstryx-srv still carries eight S4_* environment overrides",
     "AdminService.syncOrgFromS4() reads them from the tenant's own S/4 through the ITS_S4 destination into an S4OrgValue mirror, and fills each company from what it finds. Catalogue reads and document reads are kept apart and marked: a catalogue proves a value exists, a live document proves it works and is the only source that says which company code uses it. It fills a blank only when exactly one value fits, overwrites only a value S/4 has never used, and reports an unmapped company rather than guessing INFC -> 3310, which is a business decision and not readable",
     "Closed", "2026-08-25"),
    ("I-51", "Project Setup", "A project could not be created in the product at all",
     "The Projects screen was a read-only list. Every project on every tenant arrived in a content pack or a P6 file, which makes the product a demo rather than a product - and it is why the starter-pack question could not be answered without also answering this one",
     "ProjectService.createProject takes the header and its WBS elements in one call, with a New project dialog behind it. Together deliberately: a project with no WBS element cannot be released, so a create that stopped at the header would manufacture exactly the state PRJ-002 is stuck in - complete-looking and permanently unreleasable. releaseToS4 now pushes immediately instead of only queueing, so a project a person types reaches S/4 on one click; it still writes PENDING first and the push still refuses anything not PENDING, so the release gate is walked rather than bypassed",
     "Closed", "2026-08-25"),
    ("I-52", "Testing", "The verification suite reached a live S/4 and started creating real projects",
     "Surfaced by I-51 rather than pre-existing: once release pushed on its own, the regression run began posting Enterprise Projects into whatever tenant the developer's .env named. S4Connection falls back to a gitignored .env when no destination resolves, and that file still held live my401381 credentials. Nothing was created only because the org data is now my434396's and S/4 refused with Profit Center YB101 does not exist - luck, not design",
     "S4Connection honours an S4_OFFLINE switch that short-circuits resolution before either the destination or the .env is consulted, and run_all.sh sets it. A verification run can no longer reach a tenant regardless of whose machine it runs on. The my401381 communication user still needs rotating - it transited chat transcripts (Q-09p) and is evidently still live",
     "Closed", "2026-08-25"),
    ("I-72", "Commercial", "The period report added three branches that were assumed never to overlap",
     "Actual cost is signed labour plus stock issued, plus what was bought and billed, plus certified subcontract value. Both the reconciliation and the budget stated in comments that these cannot overlap, because a request line is decided PROCURE or IN_HOUSE and travels one way. Nothing measured it. On the seeded portfolio 383,202.40 of scope carries cost on both branches at once, so PRJ-001 reports 3,113,423.84 spent when at most 2,730,221.44 of it is distinct money, and margin, cost to complete and both performance indices inherit the error",
     "The reconciliation measures the overlap per request line as the smaller of the two figures, which is the most of it that can be the same money, and says so on the face of the report. Measured rather than subtracted: a material line part drawn from store and part bought is genuine cost on both sides, and telling that apart from a line counted twice is a reading of the data rather than a rule. The budget comment no longer claims the overlap is impossible",
     "Closed", "2026-08-29"),
    ("I-73", "Insight", "Every period report note was cut off at 254 characters, mid-word",
     "The note is where the report says what it could not compute and which figures carry a caveat, and it is the one part a reader has to trust. The field was String(255) and the assembly cut the joined text with substring, so every report on the portfolio came out at exactly 254 characters ending mid-word, and any note after the second was dropped without trace. A caveat cut in half is worse than one left out: it reads as a complete sentence that happens to end early",
     "The field holds 2000, which fits every note a report currently produces with room to spare, and the assembly puts whole notes in while they fit and never splits one. If it ever has to drop any, the count of them is the last thing the note says",
     "Closed", "2026-08-29"),
    ("I-71", "Commercial", "Two live figures for what a project has cost disagreed, silently",
     "The period report counts actual cost as signed labour plus stock issued plus invoiced plus certified subcontract. The budget control record counts invoiced plus what the reservations consumed, and places it by cost node. Neither is wrong on its own terms and they disagree by a large number: PRJ-001 reads 550,704 on the control record and 3,113,423.84 on the period report — 1,521,059.84 spent against cost nodes the budget has no line for, and 1,041,660 of certified subcontract value that cannot be placed at all. PRJ-002 and PRJ-004 are worse in shape: the control record reads zero actual against 638,000 and 998,600 of certified work",
     "refreshControl now reports both, separately, because the fixes differ. Cost on an uncovered node needs a budget line or a corrected assignment. Certified subcontract value needs the model to carry an assignment at all — see S-31. Reported rather than corrected: inventing where a subcontract charges is exactly the guess this product exists to prevent, and the alternative is a control record that looks complete",
     "Closed", "2026-08-29"),
    ("I-69", "Tooling", "The smoke test looked for the UI on a port nothing serves",
     "run-local.bat starts the UI on 8081 and passes it explicitly, and serve.py's own default was 8080 — so the port depended on how it was started, and starting it by hand put it somewhere the smoke test does not look. The failure does not read as a wrong port: every application fails index, component, manifest and data at once, which is indistinguishable from twenty-eight broken screens",
     "serve.py defaults to 8081, matching the entry point that is actually supported. One number moved rather than two, and nothing that already works changes",
     "Closed", "2026-08-29"),
    ("I-70", "Demo data", "The plant reservation is priced for 432 days inside a six-month window",
     "RR-2026-0188 line 1 is two tower cranes at 320 a day with an approved total of 276,480, and the mobilization window runs 14 Jun to 14 Dec — about 184 days. The approved value implies 432. Invisible until the variation made the duration a figure the product reads back and prints: the demo now says \"2 at 320 for 432 day(s)\" on a six-month hire. Line 2 is consistent at 90 days, so it is this line rather than the convention",
     "Reported rather than corrected. estTotal is what the approval was shown and what the encumbrance was set from, so changing it moves budget, encumbrance and reconciliation figures across several suites — that is your call on the fixture, not a silent edit",
     "Open", "2026-08-29"),
    ("I-66", "Reporting", "The overview scored every reservation against the plant chain",
     "The ten-step chain is drawn for equipment: a request for cranes, routed to own fleet or rental, mobilized under a fifteen-item condition checklist and taken off under the same one. Material is poured and never comes back, so mobilization and de-mobilization are steps a concrete reservation can never reach — and it was being counted against them. Every material and manpower thread therefore reported a ceiling of 8 of 10 no matter how completely it finished",
     "The scope is decided by the vertical. Asset verticals run all ten; the rest are scored against the eight that apply, and the row says which chain it is being read against",
     "Closed", "2026-08-29"),
    ("I-67", "Reporting", "Six of the ten steps were hardcoded as pending",
     "The overview asserted CMT, MOB, OPL, VAR, DMB pending on every row regardless of what stood behind it. That was true when written and had quietly stopped being true: RES-2026-0162 carries 46 signed timesheets, which is exactly what the operation-log step is, and the screen called it outstanding. The same understating would have grown with every module built, because nothing in the code had to change for the statement to go stale",
     "Every step is read from data. The daily record resolves per vertical — consumption records for material, timesheets for manpower — and the closure step is evidenced by the closure account rather than a status field",
     "Closed", "2026-08-29"),
    ("I-68", "Reporting", "A step nobody can do read as a step nobody had done",
     "Pending listed the unwired ERP commitment beside the closure somebody actually owes. A coordinator reading the row could not tell which of the six was work and which was a connector, so the screen asked them to chase things that do not exist",
     "Three outcomes reported apart: done, pending, blocked — the last carrying its reason (ERP connector / not built). Only pending is anybody's work, and the progress bar divides by the steps in scope",
     "Closed", "2026-08-29"),
    ("I-65", "Authorization", "The site engineer could not open the two site screens",
     "The persona's own description is \"raises resource requests and confirms execution on site\", and it held create, change and read on the timesheet - the manpower half of confirming execution - and nothing at all on the stock draw or the consumption record. Only DEMO_ALL held those, so the two screens built for the site engineer were openable by the demo superuser and nobody else. Found by the launchpad smoke test, which reads every tile's count through the proxy as a real persona rather than as admin",
     "READ on both objects for the site engineer and for the resource coordinator, who owns the reservation the draw is made against. Delivered as PERSONAS 1.3.0, insert-if-missing",
     "Closed", "2026-08-29"),
    ("I-64", "Authorization", "The cost object governed an entity that had been deleted",
     "KX_COST named konstryx.ins.CostRevenueSnapshot, which does not exist in the model - it was replaced by ProjectPeriodReport and the catalogue was never repointed. The authorization handler skips any entity it cannot find in the catalogue, so every period report was governed by NO object at all: the margin, the forecast, the cost against value of every project in the estate, readable by anyone the service-level check let in. The grants held against KX_COST meanwhile granted access to nothing. Both halves silent - a dead pointer looks exactly like a working one from the persona screen. Found while filling the blank scope paths on the two site objects (I-61)",
     "KX_COST points at konstryx.ins.ProjectPeriodReport with both scope paths filled, so the reports are project- and company-scoped like everything else. The project manager gains READ, on the rule that a persona already trusted with the budget is trusted with the same figures arranged as a cost report - COST_ENGINEER and DEMO_ALL already held it and PROJECT_MANAGER was the only holder of budget READ without it",
     "Closed", "2026-08-29"),
    ("I-60", "Procurement", "A draw named its material, and the material named two lines",
     "One request routinely orders the same material for several parts of a job - the same ready-mix into a slab and into a core wall - and those are separate lines, on separate cost nodes, with separate norms and separate budgets. The draw matched on the material code and took the first line it found, so the core wall's twenty cubic metres were charged to the slab. Both lines look identical from outside, which is why nothing on any screen would have shown it. Found by the suite, on the first thread wide enough to contain the case",
     "The line number identifies the line. The material only decides when it is unambiguous on its own, and when it is not the refusal spells out the choice - line number, material and cost node for each candidate - rather than guessing",
     "Closed", "2026-08-29"),
    ("I-61", "Authorization", "Two site objects were declared project-scoped and could not be scoped",
     "KX_PULL_REQUEST and KX_CONSUMPTION carried projectScoped = true with no project path and no company path. A blank path is skipped rather than refused, so the objects were declared as controlled and enforced nothing: a site engineer scoped to one project could read every project's draws. Silent by construction - the flag says the control is on",
     "The pull request carries a project and a company of its own now that it is a document, so the paths are direct; consumption reaches them through its reservation line. Both filled in the delivered catalogue",
     "Closed", "2026-08-29"),
    ("I-62", "UI", "Every scaffolded app inherited the template's name",
     "scaffold_app rewrote the tile title and the tile subtitle in the manifest and left the i18n bundle alone, so a new app's shell header and its gallery entry read PurchaseOrders and \"Supplier master mirrored from ERP\". Corrected by hand three times on three different apps before the pattern was obvious - the tile, which is the part people look at, was right every time",
     "The scaffolder writes the bundle from the same title and subtitle it already writes into the manifest. An app is named once",
     "Closed", "2026-08-29"),
    ("I-63", "Demo", "The stand-in reported orders it had not placed",
     "The invoicing loop reused the name that holds the count of orders placed for a line quantity, so the closing summary reported the last order line's quantity as the run's work: 20 orders placed on a run that placed none",
     "The line quantity has its own name. The summary counts orders again",
     "Closed", "2026-08-29"),
    ("I-58", "Reporting", "The cost report's coverage note read as a broken sentence",
     "The note names what contributed to the cost and what did not. Built from two lists and printed unconditionally, it produced \"Cost captured from  only; manpower, procurement, subcontract contribute nothing\" on a project with no cost at all, and \"procurement contribute nothing\" once the missing list could hold a single item. Both are the right fact in a sentence a reader learns to skip",
     "An empty captured list says so outright instead: nothing has been spent from any source, so the margin is the whole budget and not a measurement. The verb agrees with the list length",
     "Closed", "2026-08-29"),
    ("I-59", "Demo", "The cost reports were produced before the invoices existed",
     "prime_demo reconciles, then mirror_erp_documents posts the bills. The reports were therefore always one step behind: PRJ-001 read 2,229,071.84 spent with a note saying procurement contributes nothing, on a project that had just been billed 760,980",
     "The stand-in reconciles after billing, the same way it already refreshed the budgets. PRJ-001 now reads 2,990,051.84 with no coverage caveat left",
     "Closed", "2026-08-29"),
    ("I-56", "Budget", "A half-consumed reservation held the budget twice",
     "Encumbrance was the whole reserved amount until the line closed, and actual had just gained the consumed cost off the same line. So a reservation 60% consumed locked 100% of its value as encumbered AND reported 60% of it as spent, against the same hours - available understated by the consumed portion on every line still running. Exactly the relief rule already applied to commitment, missing on the other branch",
     "Encumbrance is now what the reservation still has to consume: encumbered less cost to date, floored at zero. A line that overran cost more than it reserved, and that overrun is an actual rather than a negative lock on the budget",
     "Closed", "2026-08-29"),
    ("I-57", "Procurement", "Two lines of one invoice on one order line recorded only one of them",
     "The order rows were read into a map before the loop, so a second invoice line against the same order line measured itself against what was billed before either of them landed and wrote invoicedQty from that stale figure. The header total was right and the line total was short",
     "The match takes what this document has already billed each line as a separate argument, and the order line is re-read before it is updated",
     "Closed", "2026-08-29"),
    ("I-55", "Procurement", "An invoice settled only the last delivery on the line it billed",
     "A line delivered in two loads and billed once stamped threeWayMatch on the later receipt and left the earlier one null - permanently unanswered, and indistinguishable on screen from a delivery nobody has billed for yet. Found on the fixture that delivers 1 of 4 kits and then the remaining 3",
     "The invoice now walks the line's unanswered receipts oldest first and consumes its quantity across them, stamping each one it covers; the invoice line names the first. Receipts already answered by an earlier bill are skipped, so two invoices against one line settle two different loads rather than both claiming the first",
     "Closed", "2026-08-29"),
    ("I-53", "Budget", "A charge on one element was copied onto every budget line carrying that element",
     "The multiplication fixed earlier the same day was fixed one level too shallow. Charges were grouped by cost node and cost nature, and what the group could not place was apportioned correctly - but a charge that DID name an element was handed in full to every line carrying it. The budget is kept per bill item as well as per element, so two or three lines routinely share one element under one cost node, and each of them then reported the whole commitment. Found on the demo portfolio, where one 3,060 order showed as 3,060 twice on the same budget",
     "Both branches now go through one spread(): a charge on an element is divided across the lines carrying it in proportion to what each was budgeted, with the last absorbing the rounding, exactly as the unplaceable remainder already was",
     "Closed", "2026-08-29"),
    ("I-54", "Procurement", "A requisition could be raised for work that charges nowhere",
     "PurchaseRequisitionLine's own model comment said a line without WBS and CBS cannot commit against the right budget line, and nothing enforced it. Six lines in the demo portfolio carried an element and no cost node; the orders raised from them bought 713,080 of real scope, and every budget line involved still read fully available. The failure is silent by construction - refreshControl walks budget lines, so an order charging a node the budget has no heading for is simply not seen",
     "raisePurchaseRequisition refuses unless every PROCURE line names both, saying which line and which half is missing, and refuses at the raise rather than at the push - by the push the buyer has already been sent out to buy it. Separately, refreshControl now reports what it could not place: open order value on the project that no line of the budget covers. Reported rather than corrected, because the answer is a new budget line or a corrected assignment and both are someone's decision",
     "Closed", "2026-08-29"),
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
    ("I-12", "Deployment", "mta.yaml had no approuter, so nothing a browser could reach", "The project had never produced a deployable archive", "Approuter added with XSUAA login and token forwarding; mbt build now produces konstryx_0.1.0.mtar (68.9 MB) with the exec jar, router, 234 HDI artifacts and xs-security.json", "Closed", "2026-08-15"),
    ("I-24", "Deployment", "No BTP target available for KONSTRYX", "The CF CLI is targeted at an unrelated client subaccount (LAND MARK INTERNATIONAL) and its token has expired. The archive is built but cannot be pushed", "Needs a KONSTRYX subaccount with Cloud Foundry, HANA Cloud and XSUAA entitlements, and a fresh cf login", "Open", "2026-08-15"),
    ("I-13", "Demo data", "Wireframe request header (716,044) does not reconcile with its own line values (685,080)", "Any stakeholder demo shows inconsistent totals", "—", "Open", "2026-08-15"),
    ("I-14", "Plan", "Personalization, attachments and approvals on every object were not in the 22-week MVP estimate", "Plan credibility; 434 screens each inherit this layer", "—", "Open", "2026-08-15"),
    ("I-15", "Authorization", "Admin persona cannot read workflow/project services", "Service-level @requires still gates entry by XSUAA role; the Admin mock user lacks those roles", "By design today, but role collections need reviewing before go-live", "Open", "2026-08-15"),
    ("I-17", "Authorization", "Enforcement broke every worklist request with HTTP 500", "The handler filters on catalogue paths project.code and company.code, but RequestOverview is a grouped projection that exposed projectCode as a flat string and dropped both associations. Missed because enforcement was verified against the service directly and the UI was not re-tested after", "View now exposes the project and company associations. Worth adding a startup check that every declared path resolves on every projection, so this fails at boot rather than per request", "Closed", "2026-08-15"),
    ("I-18", "UI", "Local FLP sandbox does not boot", "flp.html fails with 'Cannot read properties of null (reading src)'. sandbox2 is deprecated since 1.136 and the newer sap/ushell/sandbox boot contract differs", "Open — either finish the sandbox boot or verify launchpad integration directly on BTP", "Open", "2026-08-15"),
    ("I-16", "Upgrade safety", "Client configuration in db/data is reset on every upgrade", "cds build --production generates konstryx.nr-NumberRangeObject.hdbtabledata. HDI re-imports managed rows on redeploy, so a client who changes a number range scope or pattern would silently have it reverted at the next upgrade", "Fixed: configurable content moved to versioned packs applied insert-if-missing. Proven — client re-scoped RR to COMPANY, an upgrade pack containing an RR row was applied, RR kept the client's scope and only the new row arrived", "Closed", "2026-08-15"),
    ("I-19", "Content packs", "Packs applied in filename order, not version order", "number-ranges-v2.json sorted before number-ranges.json because '-' precedes '.', so 1.0.1 applied before 1.0.0 and the base pack reported its own rows as pre-existing", "Sort by packId then zero-padded version segments, so 1.0.10 follows 1.0.9", "Closed", "2026-08-15"),
    ("I-29", "Services", "ProjectService dropped associations to master data", "CAP omits an association whose target is not exposed in the same service, so a project CBS node could not say which library node it came from and a planned resource could not name its resource. ProjectResources was unusable in a UI", "Expose ResourceCatalog and CBSLibrary read-only in ProjectService for resolution; maintenance stays in MasterDataService", "Closed", "2026-08-15"),
    ("I-27", "Test data", "Seed data violated the model's own hierarchy rule", "Every resource was an L5 with no parent, so activation failed with 'L5 needs a parent at L4' and no seeded master could be edited or saved. 'Below this node' was empty on every page", "Replaced with a real L1-L5 tree of 28 nodes, leaf IDs preserved so rates and request lines still resolve", "Closed", "2026-08-15"),
    ("I-40", "Deployment", "The first real Cloud Foundry deployment: six blockers, none reachable by the test suite", "KONSTRYX had never been deployed. mta.yaml, the db module and the cloud Spring profile were all written ahead of ever being run, and each was wrong in a way only execution could expose. In order: (1) the subaccount lacked the SAP HANA Schemas & HDI Containers entitlement, so service plan hdi-shared did not exist - you added it; (2) db/ had no package.json at all, so the HDI deployer task died on npm ENOENT every attempt; (3) that same missing file made mbt's npm install --production walk UP to the repo root and prune it, deleting @sap/cds-dk and breaking the NEXT maven build with 'cds is not recognized' in a module nobody had touched; (4) the start script carried --use-hdb-container-key, a 4.x-only flag removed in hdi-deploy 5; (5) hdi-deploy 5 needs @sap/hana-client as a peer where 4.x bundled a driver; (6) the cloud profile declared cds.remote.services for S4/ARIBA/SF with no EDMX imported and no consumer, so the Java service crash-looped on CdsDefinitionNotFoundException", "All fixed and committed. Deployment succeeds: HDI reports 243 files deployed / 0 warnings, konstryx-srv connects to HANA and starts in 5.5s, srv and approuter both 1/1, OData returns 401 unauthenticated and the approuter 302s into the XSUAA login", "Closed", "2026-08-17"),
    ("B-10", "Business", "The S/4 connection runs through the ITS_S4 destination", "S4Connection read S4_HOST / S4_USER / S4_PASSWORD straight from the environment on EVERY environment, Cloud Foundry included. Its own class comment claimed the destination service would replace it in production - the seam was described but never built, so a deployed instance would have needed a communication-user password in its environment, and rotating that user meant a redeploy. Ziya named ITS_S4 as the destination on 2026-08-17 and it had stayed open since", "Resolves the destination by name through the Cloud SDK (DestinationAccessor), overridable per environment with S4_DESTINATION, falling back to the .env path only where no destination service is bound. Destination headers are asked for PER REQUEST rather than cached: for Basic authentication that changes nothing, but for OAuth the SDK is minting and refreshing a token behind the call and a cached header would work exactly until the first expiry. Resolution moved to startup so the log states which mode an instance is in - the first question anyone asks when a sync misbehaves, and a lazily-resolved connection only answers it after something has already gone wrong. Both connectors are untouched: they get requests executed, never credentials. THE FALLBACK PATH IS DONE AND VERIFIED; THE DESTINATION PATH IS BUILT AND UNVERIFIED. Both branches of the resolver were seen live at startup: the local run logs 'Destination ITS_S4 did not resolve (DestinationNotFoundException); falling back to the local environment' followed by 'S/4 connection configured locally for https://my401381-api.s4hana.cloud.sap', which is the expected pair on a machine with no destination service. Full regression 15 suites / 424 checks green. THE DESTINATION BRANCH HAS NOT RUN. It cannot be exercised locally - there is no destination service to bind - and deployment is paused, so the first real test is the next deploy. mta.yaml already binds konstryx-srv to konstryx-destination, so no descriptor change was needed; the destination itself must be created in the SUBACCOUNT, never in mta.yaml, because a destination declared in the descriptor would put a communication-user password in the repository", "In progress", "2026-08-17"),
    ("I-47", "Deployment", "The MTA build shipped a week-old database schema, and HDI deployed it happily", "The konstryx-db-deployer module had no build step, so mbt packaged whatever db/src/gen already contained. That directory was last generated on 17 Aug. Five days of model changes - s4Material on ResourceNode (I-35), then s4ServiceProduct and the RateMaster routing columns (I-44) - never reached HANA. HDI deployed the stale artifacts, reported the task SUCCEEDED, and the service then failed every read of konstryx.master.ResourceNode with 'invalid column name: T0.S4MATERIAL_ID', which took down the whole MASTER_DATA content pack. Nothing in the build or the deploy said anything was wrong: a stale generated artifact deploys perfectly, and it is the application that breaks, later, somewhere else", "mta.yaml now runs `npx cds build --production` as the db module's build command, so the HDI artifacts are regenerated from the current model on every build and cannot drift again. Verified by extracting the hdbtable out of the built mtar before deploying, not by trusting the build log", "Closed", "2026-08-24"),
    ("I-48", "Deployment", "Wiring the destination loader crash-looped the service on a version clash", "connectivity-destination-service is genuinely required - cloudplatform-connectivity gives you the DestinationAccessor API but registers only EnvVarDestinationLoader, so ITS_S4 could never resolve however well the subaccount was configured. Adding it dragged com.sap.cloud.security java-security / java-api / env from 3.7.4 to 4.0.7 by nearest-wins, while CAP's own spring-security stayed at 3.7.4 and calls JwtValidatorBuilder.withHttpClient(CloseableHttpClient), which 4.0.7 removed. The failure named neither the dependency nor the destination: it was a NoSuchMethodError during Spring Security bean creation, and it crash-looped konstryx-srv on a live space", "Reverted first to restore service, diagnosed with `mvn -pl srv dependency:tree`, then fixed forward: dependencyManagement pins those three artifacts to the 3.7.4 line CAP is built against. Also widened S4Connection's resolver to catch LinkageError as well as RuntimeException - reaching S/4 is optional infrastructure and a classpath fault in it must degrade the connection to unconfigured, never take the service down. The crash was not a total loss: before dying, that build logged 'S/4 connection uses destination ITS_S4 -> https://my434396-api.s4hana.cloud.sap', which is how we know the destination exists and the loader works", "Closed", "2026-08-24"),
    ("I-49", "Integration", "The requisition payload named three things S/4 does not call by those names", "Once SAP_COM_0102 was activated, the connector was checked against the tenant's own $metadata instead of against documentation. The V4 shape was right - ISO dates, navigation properties, a top-level response - and so was the service path, every header property and all eleven item properties. Three names were wrong: the entity set is PurchaseReqn not PurchaseRequisition, the item-to-account navigation is _PurchaseReqnAcctAssgmt not _PurReqnAcctAssgmt, and the account property is PurchaseReqnAcctAssgmtNumber not PurReqnAcctAssgmtNumber. Note the trap: the header-to-item navigation really IS spelled out as _PurchaseRequisitionItem while its sibling is abbreviated, so guessing consistently would have got one of the two wrong whichever way it guessed", "Corrected. Read via S4Probe, a read-only startup probe added for the purpose: the credentials that work live in the ITS_S4 destination on the deployed app, not on a developer machine, so the metadata had to be read from there. It is gated on the S4_PROBE environment variable - set it, restart, read the log, unset it - and only ever issues a GET. Two things it taught along the way: S/4 answers $metadata with 406 if the Accept header asks for JSON only, which reads exactly like a wrong service path; and an EntitySet and its EntityType do not share a name (PurchaseReqn vs PurchaseReqnType), so the probe now discovers the type names rather than assuming them", "Closed", "2026-08-24"),
    ("I-43", "Integration", "The requisition push targeted the wrong API and the wrong communication scenario", "Built on 2026-08-19 against API_PURCHASEREQ_PROCESS_SRV under SAP_COM_0053, both carried forward from an older working note rather than checked. The consolidated requirements V02 §15.2 row 9 and RB-145 put the requisition on API_PURCHASEREQUISITION_2 under SAP_COM_0102. SAP_COM_0053 appears 22 times in V02 and is attached to the PURCHASE ORDER every single time, never to a requisition — so the connector would have been pointed at the order scenario. Worse for the record, SAP_COM_0193, which the tracker and the project memory both cited for the order, appears NOWHERE in V02; it was invented somewhere upstream and repeated", "Connector repointed. The API change is not just a rename: API_PURCHASEREQUISITION_2 is the V4-generation API, so the payload moved from V2 conventions (/Date(millis)/ dates, to_ navigation sets, a d-wrapped response) to V4 (ISO dates, _-prefixed navigation properties, a top-level response), and the error reader now handles both shapes. The service root is env-overridable via S4_PR_SERVICE because it is the single most likely thing still to be wrong. Docs corrected in the same pass, including the scenario table that carried SAP_COM_0193", "Closed", "2026-08-24"),
    ("I-44", "Master data", "Only a material could be ordered, so nothing hired could be", "ResourceNode carried s4Material and nothing else, which meant a requisition line could name a product to buy and nothing else. Every non-material class was therefore unorderable: a hired crane, labour supplied by an LSC, a subcontracted package. The consolidated requirements make this a first-class rule — spec §8 / principle P10, class routes the leaf to S/4 — and state the consequence plainly: a leaf that carries neither an activity type nor a service product cannot be costed, and one carrying both without declaring which applies will be costed twice. The 2026-08-17 ruling of material-number-only predates V02 and was made against the v12 masters screen, which does not show this", "Split across the two places the wireframe itself splits it, which turns out to preserve the original ruling rather than overturn it — one material per resource still holds, because a material is source-independent. (1) ResourceNode.s4ServiceProduct: the GENERIC service product, what a requisition orders, because a requisition is raised before a vendor exists and naming one vendor catalogue code on a pre-award document would pre-decide the award. (2) RateMaster gains source (IN_HOUSE / HIRED / LSC_HIRED), vendor, s4ActivityType and s4ServiceProduct: what a COST posts against. Source is the declaration that stops double-costing — in-house carries an activity type and no vendor, hired carries a vendor and that vendor own service product, and a row carrying both is refused. raisePurchaseRequisition now resolves by class: MR takes the material, everything else takes the service product", "Closed", "2026-08-24"),
    ("I-45", "Master data", "The rate uniqueness rule would have refused the product's own specified data", "Rates were unique on resource + effectiveFrom + scope. The wireframe's manpower master lists MP-CIV-CAR-SK-G1 three times on the same day at three rates — our payroll at AED 28.50/hr, Alpha Civil at 24.00, Beta Labour at 23.50 — because a rate is not a property of the resource alone. Keying on resource would have called two of those a duplicate and refused them. Found while adding source and vendor, not by a failing test: nothing had ever tried to seed the second row", "Key widened to resource + source + vendor + effectiveFrom + scope. The seeded fixture now carries the in-house and Alpha Civil rows on the same day, which is the case the old rule rejected, and test_rates asserts both survive as well as asserting the narrow duplicate is still a 409", "Closed", "2026-08-24"),
    ("I-46", "Authorization", "The persona that maintains rates could not see what a rate now names", "A consequence of I-44 rather than a pre-existing defect. Once a rate names the vendor whose contract it belongs to and the S/4 service product it is procured against, the master-data steward has to be able to read both to maintain one — and MD_STEWARD had full CRUD on KX_RATE but no grant at all on KX_VENDOR or KX_MATERIAL. Surfaced as a 403 in the new test, not by inspection", "Granted activity 03 (display) on both, and only 03: they are S/4 mirrors, and DM-01 says a mirror is not ours to edit. PERSONAS content pack bumped 1.0.0 to 1.1.0 so an existing installation picks the grants up", "Closed", "2026-08-24"),
    ("I-42", "Integration", "Every WBS element pushed to S/4 forgot what S/4 called it", "S4ProjectConnector created each WBS element under the project and threw the response away, counting successes and failures but recording neither key. WBSElement carries the s4outbound aspect, so it HAS an s4Key field - it was simply never written, on any row, since the connector was built. Nothing noticed because the only consumer until now was the project header, which does record its own key. It surfaced the moment the requisition push needed to name the account assignment: the WBS element as S/4 knows it", "The connector now records each element's key from S/4's own response body, plus SENT/FAILED and the refusal text, incrementing that element's own syncAttempts. Deliberately NOT re-derived from the KONSTRYX code by repeating the connector's normalising rule - a second copy of that rule would be a guess the moment S/4 truncated or renamed anything. The requisition push refuses a line whose WBS has no key rather than inventing one", "Closed", "2026-08-19"),
    ("I-41", "UI", "The deployed app serves no UI - the jar carries none", "Confirmed against the built artifact rather than inferred: jar tf konstryx-srv-exec.jar lists 57 service classes and zero UI assets. mta.yaml's comment claims konstryx-srv already serves the SAPUI5 app as static content, which is not true - there is no srv/src/main/resources/static and no copy step in srv/pom.xml. Separately index.html bootstraps UI5 from a relative resources/sap-ui-core.js, which serve.py proxies to a runtime on the developer's local disk and which nothing serves in CF. The approuter's /konstryx-ui/* route forwards to a service with nothing behind it", "Open - this is Q-11. html5-apps-repo IS entitled in this space, which is the clean answer: build the UI as its own MTA module into the HTML5 application repository rather than packaging it into the Java jar. The launchpad tile (semantic object + action, per your ruling) needs this finished behind it or the tile launches a 404", "Open", "2026-08-17"),
    ("I-35", "Integration", "A resource has no S/4 material number, so a requisition cannot name what to buy", "master.ResourceNode is the KONSTRYX resource code (L1-L5) and master.Material is the separate S/4 product mirror, but nothing links them — ResourceNode has no material field and Material has no resource field. The requisition therefore carries the resource and its description, which is enough for the KONSTRYX side but not enough to POST to API_PURCHASEREQ_PROCESS_SRV, which needs the S/4 material number. The wireframe already shows this mapping existing (masters.html renders resource rows with an S/4 material column, e.g. MAT-STL-SS316-12 against 100024780), so the intent is there and only the model is missing", "Parked by you 2026-08-17 so PO work could continue, then answered the same day: ONE MATERIAL PER RESOURCE, not one per company. The group is on a single S/4 client, where a material number is client-level — every company code sees the same number and only the plant and valuation extensions differ — and where a company genuinely buys a different item, that item is already its own COMPANY-scoped leaf, so the hierarchy carries the company dimension without repeating it. Built: ResourceNode.s4Material, an association to the Material mirror (a reference, never a master — materials are created in S/4 and registered here). raisePurchaseRequisition resolves it onto the line when the requisition is raised rather than at push, so remapping a resource later cannot silently change what an already-open requisition buys; a resource with no material leaves the line empty rather than guessing. Scope held to the material number — the wireframe's CO activity type, SAP material type and material group are not modelled until something consumes them", "Closed", "2026-08-17"),
    ("I-36", "UI", "Every Decimal action parameter was unpostable from the UI — including on already-shipped buttons", "Previously recorded as a narrow quirk of Decimals nested inside array-of-complex-type parameters (I found it on distributeToWBS's weight). It is far broader: SAPUI5's v4 ODataModel always negotiates IEEE754Compatible=true and sends Decimals as bare JSON numbers, while CAP Java's action-parameter deserialiser does the opposite of what that flag promises — it accepts a Decimal only as a quoted string when the flag is set, and only as a bare number when it is absent. So the typed setParameter path fails for ANY Decimal parameter. Confirmed by curl in all three combinations. This was silently breaking the Generate Build-up button on both Cost Mapping and Project BOQ (difficultyPct) — shipped, believed working, and never exercised through the UI", "All Decimal-carrying actions now post as a raw authenticated fetch with a plain application/json content type (no IEEE754Compatible), which is why the original distributeToWBS workaround worked — not because it avoided array nesting", "Closed", "2026-08-17"),
    ("I-37", "UI", "Four list-binding traps that silently showed stale or wrong data", "Found while building the Budget screens, each verified live rather than reasoned about. (1) OData v4 cannot expand or dot-navigate an association whose target is not exposed in the SAME service — Budgets.project and BudgetLine.cbs both cross a service boundary, and the failed expand poisoned the whole $batch so unrelated tables rendered empty. (2) A formatter that reads external JS state never re-runs when that state loads later; the CBS column stuck on raw GUIDs and neither refresh() nor checkUpdate fixed it. (3) oBinding.filter() with an unchanged filter array is a no-op that skips the server round trip entirely, so tables did not pick up rows an action had just created. (4) attachEventOnce('dataReceived') attached AFTER filter/refresh gets fired by an in-flight earlier response while the new rows are still empty, leaving counts and KPIs stuck at 0", "(1) resolve cross-service references client-side from the foreign key; (2) put the lookup map on a JSONModel and bind it as a real second binding part; (3) always pair filter() with an explicit refresh(); (4) attach the handler before filter/refresh and read getAllCurrentContexts()", "Closed", "2026-08-17"),
    ("I-38", "UI", "KPI tiles truncated real money to four characters", "sap.m.NumericContent truncates its value at 4 chars by default (truncateValueTo), so a budget total of 381,600 rendered as '3816' with no ellipsis or any other sign that anything had been cut — a wrong number presented as a confident one", "Set truncateValueTo explicitly and format the value with thousands separators before setting it", "Closed", "2026-08-17"),
    ("I-28", "UI", "Draft editing failed three ways", "draftActivate bound against the draftEdit operation context produced nested deferred bindings; expanding associations on a draft failed with 'invalid segment' and swallowed the edit-mode switch; draftEdit refused a second draft, making a master permanently uneditable after a mid-edit tab close", "Re-resolve the draft as an ordinary context, expand only the stored record, and resume an existing draft rather than erroring", "Closed", "2026-08-15"),
    ("I-25", "UI", "Blank screen after the app shell was removed", "Stripping sap.tnt.ToolPage removed the control establishing layout height. UI5 injects a UIArea div that takes no height of its own, and the NavContainer below sets overflow:hidden - so every control was clipped to nothing while still reporting a correct size. DOM text, network and per-element geometry checks all passed while the screen was empty", "Declared the full height chain in style.css. Found by painting a test div (which showed) and then walking the ancestor chain to #container-uiarea", "Closed", "2026-08-15"),
    ("I-26", "Build", "mbt build silently removes cds-dk", "The MTA build runs npm install --production at the root, pruning devDependencies. @sap/cds-dk goes with them and the next Maven build fails with 'cds' is not recognized", "Run npm install after an MTA build", "Closed", "2026-08-15"),
    ("I-23", "Data model", "Self-referencing compositions crashed draft activation", "ResourceNode, CBSNode and CBSInstance each declared children as a Composition of themselves. CAP expands compositions recursively on draft activation, so activating any hierarchy master died with a stack overflow in DraftActionsHandler. Composition also implies cascade-delete, so removing an L2 would have taken its subtree with it", "Changed to Association to many; the hierarchy is owned by parent and children are the inverse", "Closed", "2026-08-15"),
    ("I-21", "Masters", "Company-scoped authorization hid every group-scoped master", "Scoped masters declared companyPath in the authorization catalogue, so the handler added owningCompany.code = 'INFC', which is null on every GROUP row. Each steward saw only their own local master and none of the five shared ones", "The company dimension for scoped entities now belongs to MasterScopeHandler alone; the catalogue declares no companyPath for them", "Closed", "2026-08-15"),
    ("I-22", "Masters", "Promotion approval threw NullPointerException", "Map.of rejects null values and clearing owningCompany_ID is precisely a null", "Use a HashMap for update payloads that clear fields", "Closed", "2026-08-15"),
    ("I-20", "Number ranges", "A range configured on an entity without docNo would fail every create", "konstryx.wf.AdvisoryDecision has no document number; the handler would have written the field regardless", "Handler now skips targets with no docNo element, so a misconfiguration is ignored rather than breaking creates", "Closed", "2026-08-15"),
    ("I-39", "Approvals", "An approval could be raised against an object that does not exist", "The target is polymorphic - an entity name and a key, not a typed association - so no foreign key would ever object. The approval would sit in an inbox indefinitely pointing at nothing", "Submission now checks the entity is in the model and the row is really there", "Closed", "2026-08-15"),
    ("I-30", "Content", "A failing content pack left rows behind that nothing recorded as applied", "Rows were inserted one at a time and the pack's own record written last. When that record failed - a description longer than its column - the rows stayed and the pack looked unapplied", "Each pack now applies in its own change set and is abandoned whole on failure", "Closed", "2026-08-15"),
    ("I-33", "Seed data", "One duplicate key in a seed CSV loads zero rows for that entity, and only logs it at INFO", "The CSV loader cancels the whole entity's change set on a unique-constraint violation. A duplicated PersonaPermission key therefore loaded no permissions at all and every request returned 403, with nothing at WARN or ERROR explaining why", "Duplicate removed. The behaviour itself is unchanged and will recur — see S-27", "Closed", "2026-08-15"),
    ("I-34", "Project Setup", "@readonly on a projection element does not cover the draft path", "CAP dispatches a draft edit as DRAFT_PATCH, which the annotation does not gate. The draft displayed syncStatus SENT and an invented S/4 key. Activation stripped them so the stored record was never wrong, but the user was shown something untrue until they saved", "Guarded on the draft event as well as the active one", "Closed", "2026-08-15"),
    ("I-32", "Personalization", "Every user could read and write every other user's saved layouts", "UserVariant was modelled with a user column and no handler behind it, so nothing filtered reads and nothing stopped the payload naming a different owner. A saved filter names projects, counterparties and cost codes, so another person's variant list tells you what they work on", "Owner is taken from the session; reads are narrowed to own plus published; writes to someone else's answer 404 rather than 403 so the key is not confirmed", "Closed", "2026-08-15"),
    ("I-31", "Approvals", "withdraw and delegate returned 501 Not Implemented", "Both actions were declared in CDS without a return type while their handlers set one, which CAP rejects at the protocol layer rather than at build time. Only reachable by calling them - the build was clean", "Declared returns String on both", "Closed", "2026-08-15"),
]
body(ws, 6, issues, [8, 16, 62, 50, 56, 10, 12], status_col=6)
ws.freeze_panes = "A6"

for sheet in wb.worksheets:
    sheet.sheet_view.showGridLines = False

wb.save(OUT)
print("written:", OUT)

# An id that names two work items makes a status ambiguous: "F-04 is done" is
# true of one of them and not the other. Reported rather than renumbered,
# because the ids are what the answers in this workbook are written against.
# The header names the fifth column Status. A row that puts its remedy there
# and its status in the evidence column still renders, and the Status column
# then reads as prose -- which is how eight of these went unnoticed.
KNOWN_STATUS = ("Done", "Not started", "Raised", "Blocked", "Part done",
                "At risk", "In progress", "Deferred")
misfiled = [r[0] for r in items
            if not str(r[4]).split(" —")[0].strip() in KNOWN_STATUS]
if misfiled:
    print("\nrows whose status column does not hold a status:")
    for key in misfiled:
        print("   %s" % key)

seen = {}
for row in items:
    seen.setdefault(row[0], []).append(row[2])
shared = {k: v for k, v in seen.items() if len(v) > 1}
if shared:
    print("\nids naming more than one item:")
    for key in sorted(shared):
        print("   %-6s %s" % (key, " | ".join(str(t)[:44] for t in shared[key])))
