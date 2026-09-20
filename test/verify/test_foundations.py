"""The foundations: authorization enforcement, master scope isolation, master
validation, number ranges, promotion, and CSV import/export.

These were each verified when built but never kept as a script, so nothing
re-checked them afterwards. This is that regression suite."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"


def call(path, user="demo", method="GET", body=None, pw=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path.replace(" ", "%20"), data=data, method=method)
    req.add_header("Authorization", "Basic " + base64.b64encode(
        f"{user}:{pw or user}".encode()).decode())
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            out = r.read().decode(errors="replace")
            if not out.strip().startswith(("{", "[")):
                return r.status, out
            parsed = json.loads(out)
            # An action returning a scalar comes back as {"value": "..."}.
            if (isinstance(parsed, dict) and "value" in parsed
                    and not isinstance(parsed.get("value"), (list, dict))
                    and all(k == "value" or k.startswith("@") for k in parsed)):
                return r.status, parsed.get("value")
            return r.status, parsed
    except urllib.error.HTTPError as e:
        out = e.read().decode(errors="replace")
        try:
            msg = json.loads(out).get("error", {}).get("message", out)
        except Exception:
            msg = out[:300]
        return e.code, msg


results = []


def check(expected, label, status, payload):
    if isinstance(payload, dict):
        payload = payload.get("value", payload)
    ok = status == expected
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] {label}: {str(payload)[:140]}")
    results.append(ok)
    return payload


def assert_(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{(': ' + detail) if detail else ''}")
    results.append(bool(ok))


def head(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


# ---------------------------------------------------------------- authorization
head("1. Authorization is enforced, and by the data model")

check(403, "rohan has no grant on resource requests", *call(
    "/workflow/ResourceRequests?$top=1", user="rohan"))
check(200, "daud does", *call("/workflow/ResourceRequests?$select=docNo&$top=1", user="daud"))

s, all_rr = call("/workflow/ResourceRequests?$select=docNo,project_ID&$top=200", user="demo")
s2, scoped = call("/workflow/ResourceRequests?$select=docNo,project_ID&$top=200", user="daud")
assert_(s == 200 and s2 == 200 and len(scoped["value"]) <= len(all_rr["value"]),
        "a project-scoped user sees no more than an unrestricted one",
        f"daud {len(scoped['value'])} of demo's {len(all_rr['value'])}")

projects_seen = {r["project_ID"] for r in scoped["value"]}
assert_(len(projects_seen) <= 1,
        "and only from the project they are assigned to",
        f"{len(projects_seen)} distinct project(s)")

# The caller's own filter must survive the instance restriction being ANDed on.
s, filtered = call("/workflow/ResourceRequests?$select=docNo&$filter=status eq 'Approved'"
                   "&$top=200", user="daud")
assert_(s == 200 and len(filtered["value"]) <= len(scoped["value"]),
        "the user's own $filter still applies on top",
        f"{len(filtered['value'])} approved of {len(scoped['value'])} visible")

# A refusal that says only "not authorized" is the same sentence for three
# different situations, and only one of them is the user's to act on. Drafts are
# private and not guarded — jin can scribble in one — but making it a document
# is a CREATE, and that is where the persona layer answers.
s, draft = call("/workflow/ResourceRequests", user="jin", method="POST", body={})
draft_id = draft.get("ID") if isinstance(draft, dict) else None
status, refusal = call(f"/workflow/ResourceRequests(ID={draft_id},IsActiveEntity=false)"
                       "/WorkflowService.draftActivate", user="jin", method="POST", body={})
ok = status == 403 and "grant it to one of your personas" in str(refusal)
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} [{status}] jin holds display and cannot make a "
      f"request real: {str(refusal)[:110]}")
if draft_id:
    call(f"/workflow/ResourceRequests(ID={draft_id},IsActiveEntity=false)",
         user="jin", method="DELETE")

# The same 403 for a different reason. A persona assigned under a different
# spelling of the user id looks exactly like this, and it is not a missing
# grant — nothing connects the identity to the model at all.
s, mine = call("/authorization/UserAssignments?$filter=user eq 'jin'&$select=ID",
               user="admin")
assignment = mine["value"][0]["ID"]
try:
    call(f"/authorization/UserAssignments({assignment})", user="admin",
         method="PATCH", body={"isActive": False})
    status, refusal = call("/workflow/ResourceRequests?$top=1", user="jin")
    ok = status == 403 and "not assigned to any persona" in str(refusal)
    results.append(ok)
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] and an unassigned user is told that, "
          f"not that a grant is missing")
finally:
    call(f"/authorization/UserAssignments({assignment})", user="admin",
         method="PATCH", body={"isActive": True})
check(200, "jin reads again once the assignment is back", *call(
    "/workflow/ResourceRequests?$select=docNo&$top=1", user="jin"))

# The third cause -- a tenant whose persona content never landed, where every
# request from everybody is refused identically -- cannot be reached from here
# without deleting all 150 delivered grants, and the delivered personas refuse
# deletion by design. The precondition is asserted instead.
s, granted = call("/authorization/PersonaPermissions?$filter=granted eq true"
                  "&$count=true&$top=0", user="admin")
assert_(s == 200 and granted.get("@count", 0) > 0,
        "this tenant has a persona layer, which is why the two above are the "
        "causes it reports", str(granted.get("@count")))

check(403, "the admin surface refuses a non-admin", *call(
    "/authorization/Personas?$top=1", user="daud"))
check(200, "and admits an admin", *call("/authorization/Personas?$select=code&$top=1", user="admin"))


# ------------------------------------------------------------------ master scope
head("1b. The scope is a rule about doing, not only about looking")
# Reads have been narrowed to the projects and companies a persona reaches
# since the control was built. Writes were checked for the activity alone --
# may this person create requests at all -- and never for where the request
# landed, so somebody scoped to one job could raise a document naming another
# and it would be kept.
#
# The check runs after the write, deliberately. The scope paths are expressions
# over the stored row (project.code, and four hops deep on some objects), and
# the only thing that can evaluate those is the database with the row in it.
# Reading the payload instead would mean a second implementation of what the
# read filter already does, and the two would disagree the first time a path
# changed. So the row is written, asked about through the same predicate, and
# a refusal unwinds it.

s, comps = call("/admin/Companies?$select=ID,code", user="admin", pw="admin")
company = {c["code"]: c["ID"] for c in comps.get("value", [])}
s, prjs = call("/project/Projects?$select=ID,code,company_ID", user="admin", pw="admin")
project = {p["code"]: p for p in prjs.get("value", [])}


def raise_request(user, project_code, company_code):
    """Draft a request and try to make it real. Returns (status, message, id)."""
    s, d = call("/workflow/ResourceRequests", user=user, method="POST", body={
        "verticalType": "MPR", "project_ID": project[project_code]["ID"],
        "company_ID": company[company_code], "needBy": "2026-11-01",
        "raisedBy": user, "raisedOn": "2026-08-30"})
    if s >= 400 or not isinstance(d, dict):
        return s, d, None
    rid = d["ID"]
    st, msg = call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=false)"
                   "/WorkflowService.draftActivate", user=user, method="POST", body={})
    return st, (msg.get("value") if isinstance(msg, dict) else msg), rid


def is_live(rid):
    s, got = call(f"/workflow/ResourceRequests?$filter=ID eq {rid}&$select=docNo",
                  user="admin", pw="admin")
    rows = got.get("value", []) if isinstance(got, dict) else []
    return rows[0]["docNo"] if rows else None


def drop(rid, active=True):
    call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity={str(active).lower()})",
         user="admin", pw="admin", method="DELETE")


# daud may create requests, and is assigned to one project.
st, msg, rid = raise_request("daud", "PRJ-001", "INFC")
assert_(st == 200, "daud raises a request on the project they are assigned to",
        f"[{st}] {str(msg)[:80]}")
if rid:
    drop(rid)

st, msg, rid = raise_request("daud", "PRJ-002", "INFC")
ok = st == 403 and "outside the projects and companies" in str(msg)
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} [{st}] and cannot raise one on a project they are "
      f"not: {str(msg)[:100]}")
kept = is_live(rid) if rid else None
results.append(kept is None)
print(f"  {'ok  ' if kept is None else 'FAIL'} and the refusal unwound it — nothing was "
      f"kept: {kept or 'nothing'}")
if rid:
    drop(rid, active=False)

# demo reaches every project of one company, so the same rule has to bite on
# the other dimension. PRJ-005 belongs to PMI.
st, msg, rid = raise_request("demo", "PRJ-005", "PMI")
ok = st == 403 and "outside the projects and companies" in str(msg)
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} [{st}] a company-scoped user cannot raise one in "
      f"another company either: {str(msg)[:90]}")
if rid:
    drop(rid, active=False)

# And a row already in scope cannot be moved out of it. This is the case the
# payload could not have answered on its own: what makes the write wrong is
# where the row ends up, not what the request said.
st, msg, rid = raise_request("demo", "PRJ-001", "INFC")
if st == 200 and rid:
    s, _ = call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)",
                user="demo", method="PATCH", body={"needBy": "2026-12-01"})
    assert_(s < 400, "demo changes a request inside their own company", f"[{s}]")

    s2, refusal = call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)",
                       user="demo", method="PATCH",
                       body={"company_ID": company["PMI"]})
    ok = s2 == 403 and "outside the projects and companies" in str(refusal)
    results.append(ok)
    print(f"  {'ok  ' if ok else 'FAIL'} [{s2}] and cannot move it out: "
          f"{str(refusal)[:95]}")

    s3, after = call(f"/workflow/ResourceRequests?$filter=ID eq {rid}"
                     "&$select=company_ID", user="admin", pw="admin")
    still = after["value"][0]["company_ID"] if after.get("value") else None
    results.append(still == company["INFC"])
    print(f"  {'ok  ' if still == company['INFC'] else 'FAIL'} and the row still belongs "
          f"where it did")
    drop(rid)
else:
    assert_(False, "demo could raise a request to move", f"[{st}] {str(msg)[:80]}")


head("2. Scoped masters: two stewards, two views of the catalogue")

s, infc = call("/masterdata/Resources?$select=ID,code,scope&$filter=IsActiveEntity eq true"
               "&$top=200", user="steward_infc")
s2, pmi = call("/masterdata/Resources?$select=ID,code,scope&$filter=IsActiveEntity eq true"
               "&$top=200", user="steward_pmi")
assert_(s == 200 and s2 == 200, "both stewards can read the catalogue")

infc_codes = {r["code"] for r in infc["value"]}
pmi_codes = {r["code"] for r in pmi["value"]}
group_infc = {r["code"] for r in infc["value"] if r["scope"] == "GROUP"}
group_pmi = {r["code"] for r in pmi["value"] if r["scope"] == "GROUP"}

assert_(group_infc == group_pmi and len(group_infc) > 0,
        "both see exactly the same GROUP masters", f"{len(group_infc)} shared")
assert_(infc_codes != pmi_codes,
        "but not the same catalogue overall",
        f"INFC-only {sorted(infc_codes - pmi_codes)}, PMI-only {sorted(pmi_codes - infc_codes)}")

# Compared by row, not by code: EQ-DUP is deliberately held locally by both
# companies as two different rows, which is the fixture the promotion collision
# check exists for. Comparing codes would call that a leak.
local_infc = {r["ID"] for r in infc["value"] if r["scope"] == "COMPANY"}
local_pmi = {r["ID"] for r in pmi["value"] if r["scope"] == "COMPANY"}
assert_(local_infc and local_pmi and not (local_infc & local_pmi),
        "neither steward sees the other's company-local rows",
        f"INFC {len(local_infc)}, PMI {len(local_pmi)}, shared {len(local_infc & local_pmi)}")


# -------------------------------------------------------------- master validation
head("3. Master validation refuses what the hierarchy forbids")

s, d = call("/masterdata/Resources", user="steward_infc", method="POST", body={
    "code": "EQ-VERIFY-ORPHAN", "level": "L5", "verticalType": "EQR",
    "description": "L5 with no parent", "scope": "COMPANY"})
if s == 201:
    check(400, "an L5 with no L4 parent", *call(
        f"/masterdata/Resources(ID={d['ID']},IsActiveEntity=false)"
        "/MasterDataService.draftActivate", user="steward_infc", method="POST", body={}))
else:
    check(400, "an L5 with no L4 parent (refused at create)", s, d)

s, existing = call("/masterdata/Resources?$select=code,level,parent_ID&$filter=IsActiveEntity eq true"
                   " and code eq 'EQ-TWC-12T'", user="steward_infc")
if existing.get("value"):
    row = existing["value"][0]
    s, d = call("/masterdata/Resources", user="steward_infc", method="POST", body={
        "code": "EQ-TWC-12T", "level": row["level"], "parent_ID": row["parent_ID"],
        "verticalType": "EQR", "description": "Duplicate code", "scope": "COMPANY"})
    if s == 201:
        check(409, "a code that already exists in this scope", *call(
            f"/masterdata/Resources(ID={d['ID']},IsActiveEntity=false)"
            "/MasterDataService.draftActivate", user="steward_infc", method="POST", body={}))
    else:
        check(409, "a code that already exists in this scope", s, d)


# ---------------------------------------------------------------- number ranges
head("4. Number ranges are configurable and issue on activation")

s, ranges = call("/authorization/NumberRangeObjects?$select=code,scope,pattern,entityName"
                 "&$orderby=code", user="admin")
for r in ranges.get("value", []):
    print(f"      {r['code']:5} {r['scope']:8} {r['pattern']}")
assert_(s == 200 and len(ranges["value"]) >= 5, "the delivered ranges are present",
        f"{len(ranges.get('value', []))} configured")
assert_(any(r["scope"] == "GLOBAL" for r in ranges["value"])
        and any(r["scope"] == "COMPANY" for r in ranges["value"]),
        "both GLOBAL and COMPANY scopes are in use")

s, rrs = call("/workflow/ResourceRequests?$select=docNo&$top=200", user="demo")
numbered = [r["docNo"] for r in rrs["value"] if r.get("docNo")]
assert_(len(numbered) == len(rrs["value"]) and all(n.startswith("RR-") for n in numbered),
        "every resource request carries a document number",
        f"{len(numbered)} numbered, e.g. {numbered[0] if numbered else '-'}")


# ----------------------------------------------------------------- content packs
head("5. Delivered content applied, once per version")

s, packs = call("/authorization/ContentPacks?$select=packId,version,rowsInserted,rowsSkipped"
                "&$orderby=packId", user="admin")
for p in packs.get("value", []):
    print(f"      {p['packId']:18} {p['version']:8} +{p['rowsInserted']} skipped {p['rowsSkipped']}")
assert_(s == 200 and len(packs["value"]) >= 2, "both packs recorded",
        f"{len(packs.get('value', []))}")

s, schemes = call("/authorization/ApprovalSchemes?$select=code"
                  "&$expand=steps($select=stepNo)", user="admin")
assert_(s == 200 and len(schemes["value"]) >= 2
        and all(len(x["steps"]) > 0 for x in schemes["value"]),
        "the approval schemes arrived with their steps resolved by reference")


# --------------------------------------------------------------- import / export
head("6. CSV export doubles as the upload template, and import validates")

s, template = call("/authorization/exportCsv", user="admin", method="POST", body={
    "target": "MasterDataService.Resources", "templateOnly": True})
assert_(s == 200 and isinstance(template, str) and "code" in template and "level" in template,
        "the template is the column set the importer accepts",
        (template or "")[:70])

good = template.strip().splitlines()[0]
header = good.split(";")

def row(values):
    return ";".join(values.get(c, "") for c in header)

s, parent = call("/masterdata/Resources?$select=ID&$filter=IsActiveEntity eq true"
                 " and code eq 'EQ-TOWER'", user="admin")
parent_id = parent["value"][0]["ID"] if parent.get("value") else ""

csv_ok = good + "\n" + row({"code": "EQ-VERIFY-A", "level": "L5", "parent_ID": parent_id,
                            "verticalType": "EQR", "description": "Verification row A",
                            "consUoM": "hr", "scope": "GROUP", "masterStatus": "ACTIVE"})
csv_bad = csv_ok + "\n" + row({"code": "EQ-VERIFY-ORPHAN2", "level": "L5",
                               "verticalType": "EQR", "description": "No parent",
                               "consUoM": "hr", "scope": "GROUP", "masterStatus": "ACTIVE"})

s, msg = call("/authorization/importCsv", user="admin", method="POST", body={
    "target": "MasterDataService.Resources", "fileName": "verify.csv",
    "content": csv_bad, "mode": "VALIDATE_ONLY"})
assert_(s == 200 and "Nothing was imported" in str(msg) or "would fail" in str(msg),
        "VALIDATE_ONLY reports without changing anything", str(msg)[:90])
s, check_a = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-VERIFY-A'"
                  "&$select=code", user="admin")
assert_(len(check_a.get("value", [])) == 0, "and really changed nothing")

s, msg = call("/authorization/importCsv", user="admin", method="POST", body={
    "target": "MasterDataService.Resources", "fileName": "verify.csv",
    "content": csv_bad, "mode": "ALL_OR_NOTHING"})
print(f"      ALL_OR_NOTHING: {str(msg)[:100]}")
s, check_a = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-VERIFY-A'"
                  "&$select=code", user="admin")
assert_(len(check_a.get("value", [])) == 0,
        "one bad row keeps the whole file out")

s, msg = call("/authorization/importCsv", user="admin", method="POST", body={
    "target": "MasterDataService.Resources", "fileName": "verify.csv",
    "content": csv_bad, "mode": "PARTIAL"})
print(f"      PARTIAL:        {str(msg)[:100]}")
s, check_a = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-VERIFY-A'"
                  "&$select=code", user="admin")
s, check_b = call("/masterdata/Resources?$filter=IsActiveEntity eq true"
                  " and code eq 'EQ-VERIFY-ORPHAN2'&$select=code", user="admin")
assert_(len(check_a.get("value", [])) == 1 and len(check_b.get("value", [])) == 0,
        "PARTIAL keeps the good row and rejects the bad one")

s, runs = call("/authorization/ImportRuns?$select=fileName,mode,rowsAccepted,rowsRejected,status"
               "&$orderby=createdAt desc&$top=3", user="admin")
for r in runs.get("value", []):
    print(f"      {r['mode']:15} {r['status']:10} +{r['rowsAccepted']} -{r['rowsRejected']}")
assert_(len(runs.get("value", [])) >= 3, "every run is recorded, including the rejected one")


# -------------------------------------------------------------------- promotion
head("7. Promotion of a company master to group scope")

s, local = call("/masterdata/Resources?$select=ID,code,scope&$filter=IsActiveEntity eq true"
                " and scope eq 'COMPANY'&$top=1", user="steward_infc")
if local.get("value"):
    node = local["value"][0]
    s, msg = call(f"/masterdata/Resources(ID={node['ID']},IsActiveEntity=true)"
                  "/MasterDataService.requestPromotion", user="steward_infc",
                  method="POST", body={"reason": "Verification run"})
    check(200, f"{node['code']} requested for promotion", s, msg)

    s, queue = call("/masterdata/PromotionRequests?$select=ID,status,requestedCode"
                    "&$orderby=createdAt desc&$top=1", user="steward_infc")
    if s != 200:
        s, queue = call("/masterdata/PromotionRequests?$select=ID,status&$top=1", user="admin")
    assert_(s == 200 and len(queue.get("value", [])) >= 1,
            "it lands in the promotion queue as PENDING",
            str(queue.get("value", [{}])[0].get("status", "?")))
else:
    assert_(False, "no company-scoped master available to promote")


# ------------------------------------------------------------------- the surface
head("8. Every service still answers")

for name, path in [("workflow", "/workflow/"), ("masterdata", "/masterdata/"),
                   ("project", "/project/"), ("collaboration", "/collaboration/"),
                   ("authorization", "/authorization/")]:
    s, body = call(path, user="admin")
    n = len(body.get("value", [])) if isinstance(body, dict) else 0
    assert_(s == 200 and n > 0, f"{name} exposes its entity sets", f"{n} sets")


head("9. One intent, one app, and it reads the service")
# A launchpad resolves by semantic object and action, so two deployed apps
# declaring the same pair leaves the resolution to chance. That is what was
# there: konstryx-ui declared KonstryxResourceRequest-display and
# KonstryxReservation-display, which konstryx-resource-request and
# konstryx-reservation also declare and actually serve from the workflow
# service. The freestyle pages behind those two intents read a JSON file
# shipped with the app, so half the time the answer to "show me the requests"
# was a fixture.
import glob
import os

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "app")
claims = {}
local_only = []
for manifest_path in sorted(glob.glob(os.path.join(APP_DIR, "*", "webapp",
                                                   "manifest.json"))):
    app_name = os.path.basename(os.path.dirname(os.path.dirname(manifest_path)))
    with open(manifest_path, encoding="utf-8") as fh:
        app = json.load(fh)
    sap_app = app.get("sap.app", {})
    for inbound in sap_app.get("crossNavigation", {}).get("inbounds", {}).values():
        key = (inbound.get("semanticObject"), inbound.get("action"))
        claims.setdefault(key, []).append(app_name)
    # The unnamed model is what an unprefixed binding reads. An app whose
    # default model is a JSON file shows a fixture wherever a view did not
    # name a service, and nothing on the screen says which it got.
    sources = sap_app.get("dataSources", {})
    default_model = app.get("sap.ui5", {}).get("models", {}).get("", {})
    behind = sources.get(default_model.get("dataSource"), {})
    if behind.get("type") == "JSON":
        local_only.append(f"{app_name} ({behind.get('uri')})")

contested = {k: v for k, v in claims.items() if len(v) > 1}
assert_(not contested, f"no intent is claimed by two apps ({len(claims)} claimed once)",
        "; ".join(f"{so}-{ac}: {', '.join(apps)}" for (so, ac), apps in contested.items())
        or "none contested")
# Reported, not asserted away. konstryx-ui is the freestyle shell the Fiori
# Elements apps replaced, and its default model is still the shipped fixture;
# what it no longer does is offer itself as the answer to an intent another app
# answers with data. Its one screen with no replacement is Manpower, below.
offered_apps = {app for apps in claims.values() for app in apps}
print(f"      apps whose default model is a file: {', '.join(local_only) or 'none'}")
assert_(all(not any(a.startswith(app + " ") for a in local_only)
            for (so, ac), apps in claims.items() for app in apps
            if so != "KonstryxManpower"),
        "no app answering a launchpad intent has a fixture for its default model",
        "the one that has is konstryx-ui, which now answers none")

# Every tile the launchpad shows has to resolve to something that declared it.
sandbox = os.path.join(APP_DIR, "launchpad", "webapp", "appconfig",
                       "fioriSandboxConfig.json")
with open(sandbox, encoding="utf-8") as fh:
    site = fh.read()
declared = {f"{so}" for so, _ in claims}
offered = {so for so in declared if f'"{so}"' in site}
missing = sorted(so for so in declared if so not in offered)
print(f"      {len(offered)} of {len(declared)} declared intents are on the launchpad")
assert_(len(offered) >= len(declared) - 1,
        "and the launchpad offers what the apps declare",
        f"not offered: {', '.join(missing) or 'none'}")

# A tile that is registered but not ordered is a tile nobody sees. The page
# lays out by vizOrder, so a visualization missing from it is present in the
# configuration and absent from the screen, which is the harder kind of gone.
with open(sandbox, encoding="utf-8") as fh:
    site_data = json.load(fh)["services"]["CommonDataModel"]["adapter"]["config"]["siteData"]
unplaced, orphaned = [], []
for page_id, page in site_data["pages"].items():
    for section_id, section in page["payload"]["sections"].items():
        ordered = set(section.get("layout", {}).get("vizOrder", []))
        for viz_id in section.get("viz", {}):
            if viz_id not in ordered:
                unplaced.append(f"{page_id}/{section_id}/{viz_id}")
for viz_id, viz in site_data["visualizations"].items():
    if viz.get("businessApp") not in site_data["applications"]:
        orphaned.append(viz_id)
assert_(not unplaced,
        f"every tile the launchpad holds is also laid out on its page "
        f"({len(site_data['visualizations'])} tiles)",
        "; ".join(unplaced) or "none")
assert_(not orphaned, "and each one has an application behind it",
        "; ".join(orphaned) or "none")

# An app that exists here and not in the deployment descriptor is an app only
# the developer can see: the launchpad still offers its tile, and the tile
# resolves to nothing. mta.yaml is read as text rather than parsed, so the
# suite stays on the standard library.
import re

mta = os.path.join(os.path.dirname(APP_DIR), "mta.yaml")
with open(mta, encoding="utf-8") as fh:
    descriptor = fh.read()
modules = set(re.findall(r"^  - name: (konstryx-[\w-]+)\n    type: html5\n",
                         descriptor, re.M))
artifacts = set(re.findall(r"^        - name: (konstryx-[\w-]+)\n          artifacts:\n",
                           descriptor, re.M))
on_disk = {os.path.basename(os.path.dirname(os.path.dirname(m)))
           for m in glob.glob(os.path.join(APP_DIR, "*", "webapp", "manifest.json"))}
undeployed = sorted(on_disk - modules)
assert_(not undeployed,
        f"every app that exists is one the deploy ships ({len(modules)} modules)",
        ", ".join(undeployed) or "none")
# The module builds the zip; the deployer uploads it. A module without its
# artifact entry builds and is never uploaded, and mbt reports that as ok.
unshipped = sorted(modules - artifacts)
assert_(not unshipped,
        f"and each is listed for the deployer that uploads it ({len(artifacts)} artifacts)",
        ", ".join(unshipped) or "none")

# An action in the service contract with nothing behind it compiles, appears in
# the metadata, renders as a button, and answers 500 when pressed. copyAs sat
# there with a doc comment describing what it would do; it was found by putting
# it on a screen and clicking it, which is the only way that shape shows itself.
SRV_DIR = os.path.join(os.path.dirname(APP_DIR), "srv")
declared = {}
for cds in glob.glob(os.path.join(SRV_DIR, "*.cds")):
    with open(cds, encoding="utf-8") as fh:
        for m in re.finditer(r"\b(?:action|function)\s+(\w+)\s*\(", fh.read()):
            declared.setdefault(m.group(1), set()).add(os.path.basename(cds))
handled = set()
for java in glob.glob(os.path.join(SRV_DIR, "src", "main", "java", "**", "*.java"),
                      recursive=True):
    with open(java, encoding="utf-8") as fh:
        body = fh.read()
    handled.update(re.findall(r'@(?:On|Before|After)\s*\(\s*event\s*=\s*"(\w+)"', body))
    for m in re.finditer(r'@(?:On|Before|After)\s*\(\s*event\s*=\s*\{([^}]*)\}', body):
        handled.update(re.findall(r'"(\w+)"', m.group(1)))
# A dynamic tile promises a number. One whose path does not answer renders as a
# blank square on the home page, and blank reads as zero rather than as broken.
# Checked against the running service, because the path is only a string until
# somebody asks it.
silent = []
for viz_id, viz in sorted(site_data["visualizations"].items()):
    source = viz.get("vizConfig", {}).get("sap.flp", {}).get("indicatorDataSource")
    if not source:
        silent.append(f"{viz_id} (promises no number)")
        continue
    status, body = call(source["path"].replace("/odata/v4", ""), user="admin")
    if status != 200 or not str(body).strip().lstrip("-").isdigit():
        silent.append(f"{viz_id} [{status}]")
assert_(not silent,
        f"every tile that promises a number can answer for it "
        f"({len(site_data['visualizations'])} tiles)",
        ", ".join(silent) or "none silent")

# A list a person cannot arrange to their own work is one they arrange again
# every morning. Whether the arrangement survives the session is a separate
# question and an open one; that it is offered at all is not.
bare = []
for manifest_path in sorted(glob.glob(os.path.join(APP_DIR, "*", "webapp",
                                                   "manifest.json"))):
    app_name = os.path.basename(os.path.dirname(os.path.dirname(manifest_path)))
    with open(manifest_path, encoding="utf-8") as fh:
        app = json.load(fh)
    ui5 = app.get("sap.ui5", {})
    for target, spec in ui5.get("routing", {}).get("targets", {}).items():
        if spec.get("name") != "sap.fe.templates.ListReport":
            continue
        settings = spec.get("options", {}).get("settings", {})
        if not settings.get("variantManagement") or not ui5.get("flexEnabled"):
            bare.append(f"{app_name}/{target}")
assert_(not bare,
        "every list report lets a person arrange it and keep the arrangement",
        ", ".join(bare) or "none bare")

# The third register. sapux is what the Fiori tooling reads to know these are
# its apps; services.cds is what compiles their annotations; mta.yaml is what
# deploys them. An app can be in any two and missing from the third, and each
# omission fails somewhere different and quietly.
with open(os.path.join(os.path.dirname(APP_DIR), "package.json"), encoding="utf-8") as fh:
    sapux = set(json.load(fh).get("sapux", []))
unregistered = []
for manifest_path in sorted(glob.glob(os.path.join(APP_DIR, "*", "webapp",
                                                   "manifest.json"))):
    app_name = os.path.basename(os.path.dirname(os.path.dirname(manifest_path)))
    with open(manifest_path, encoding="utf-8") as fh:
        targets = json.load(fh).get("sap.ui5", {}).get("routing", {}).get("targets", {})
    # The freestyle app is legitimately absent: it is not a Fiori tools app.
    if not any(str(t.get("name", "")).startswith("sap.fe.templates")
               for t in targets.values()):
        continue
    if f"app/{app_name}" not in sapux:
        unregistered.append(app_name)
assert_(not unregistered,
        f"every Fiori Elements app is one the tooling knows about ({len(sapux)} listed)",
        ", ".join(unregistered) or "none unregistered")

unbacked = sorted(k for k in declared if k not in handled)
assert_(not unbacked,
        f"every action the services declare has a handler behind it "
        f"({len(declared)} declared)",
        ", ".join(f"{k} ({', '.join(sorted(declared[k]))})" for k in unbacked) or "none")


head("10. The rules can be maintained, not only enforced")
# The authorization model was administrable only through hand-written OData:
# personas are draft-enabled and their grants are a composition, so adding one
# means a draft round trip that no screen was doing. These are the paths the
# two administration apps read and write.

personas = check(200, "the personas are readable, and say which are product content",
                 *call("/authorization/Personas?$select=code,name,isDelivered"
                       "&$orderby=code", user="admin"))
delivered = [p["code"] for p in personas if p.get("isDelivered")]
assert_(delivered, "delivered personas are marked as such, so editing one is never a "
        "surprise", ", ".join(delivered) or "none marked")

# A grant is a sentence: this persona may do this activity to this object. Read
# as three UUIDs it is unmaintainable, which is why the object page expands it.
s_, one = call("/authorization/Personas?$top=1&$filter=code eq 'SITE_ENGINEER'"
               "&$expand=permissions($expand=authObject($select=name),"
               "activity($select=name))", user="admin")
grants = one["value"][0]["permissions"] if s_ == 200 and one.get("value") else []
readable = [g for g in grants if (g.get("authObject") or {}).get("name")
            and (g.get("activity") or {}).get("name")]
assert_(grants and len(readable) == len(grants),
        f"and each grant reads as a sentence rather than three keys "
        f"({len(readable)} of {len(grants)})",
        "; ".join(f"{g['authObject']['name']} / {g['activity']['name']} / {g['granted']}"
                  for g in readable[:2]))

for label, path in (("objects", "/authorization/AuthObjects?$select=code,name&$top=1"),
                    ("activities", "/authorization/Activities?$select=code,name&$top=1")):
    s_, rows = call(path, user="admin")
    assert_(s_ == 200 and rows.get("value"),
            f"the {label} a grant is built from can be picked from a list",
            str((rows.get("value") or [{}])[0])[:70])

# Making one, the way the screen does it: a draft, a grant inside the draft,
# then activation. The composition is what used to refuse this outright.
s_, obj = call("/authorization/AuthObjects?$filter=code eq 'KX_BUDGET'&$select=ID", user="admin")
budget = obj["value"][0]["ID"]
new_id = check(201, "an administrator can start a new persona", *call(
    "/authorization/Personas", user="admin", method="POST",
    body={"code": "VERIFY_PERSONA", "name": "Verification", "description": "made by the suite"}))
new_id = new_id.get("ID") if isinstance(new_id, dict) else None
check(201, "and grant it something while it is still a draft", *call(
    f"/authorization/Personas(ID={new_id},IsActiveEntity=false)/permissions",
    user="admin", method="POST",
    body={"authObject_ID": budget, "activity_code": "03", "granted": True}))
check(200, "and make it a persona", *call(
    f"/authorization/Personas(ID={new_id},IsActiveEntity=false)"
    "/AuthorizationService.draftActivate", user="admin", method="POST", body={}))
s_, back = call(f"/authorization/Personas(ID={new_id},IsActiveEntity=true)"
                "?$expand=permissions($expand=authObject($select=name),"
                "activity($select=name))", user="admin")
kept = [f"{g['authObject']['name']} / {g['activity']['name']}"
        for g in (back.get("permissions") or [])] if s_ == 200 else []
assert_(len(kept) == 1, "which keeps what was granted in the draft", "; ".join(kept) or "nothing")

# Copying is how personas are actually made: one that differs from a delivered
# one by three grants should not be assembled from nothing, because an
# administrator who has to will either give up or grant too much.
source = one["value"][0]
count_before = len(grants)
s_, copied = call(f"/authorization/Personas(ID={source['ID']},IsActiveEntity=true)"
                  "/AuthorizationService.copyAs", user="admin", method="POST",
                  body={"code": "VERIFY_COPY", "name": "Verification copy"})
assert_(s_ == 200, "a persona can be copied as the start of a new one", str(copied)[:60])
s_, made = call("/authorization/Personas?$filter=code eq 'VERIFY_COPY'"
                "&$select=code,isDelivered,isActive&$expand=permissions($select=ID)", user="admin")
copy = (made.get("value") or [{}])[0] if s_ == 200 else {}
assert_(len(copy.get("permissions", [])) == count_before,
        f"carrying every grant the original had ({count_before})",
        f"the copy has {len(copy.get('permissions', []))}")
assert_(copy.get("isDelivered") is False,
        "and never as product content, whatever it was copied from",
        f"delivered={copy.get('isDelivered')}")

s_, dup = call(f"/authorization/Personas(ID={source['ID']},IsActiveEntity=true)"
               "/AuthorizationService.copyAs", user="admin", method="POST",
               body={"code": "VERIFY_COPY", "name": "again"})
assert_(s_ == 409, "two personas cannot answer to one code, which would make an "
        "assignment ambiguous", f"[{s_}] {str(dup)[:60]}")
s_, blank = call(f"/authorization/Personas(ID={source['ID']},IsActiveEntity=true)"
                 "/AuthorizationService.copyAs", user="admin", method="POST",
                 body={"code": "   ", "name": "no code"})
assert_(s_ == 400, "and a copy without a code is refused, since the code is what an "
        "assignment refers to", f"[{s_}] {str(blank)[:60]}")

# The scheme screen shows a step by who signs it. A step whose approver reads
# as empty is open to any authorised user, which is a legitimate configuration
# and a common mistake, so the screen has to show it either way.
s_, schemes = call("/authorization/ApprovalSchemes?$select=code,name"
                   "&$expand=steps($select=stepNo,name;$expand=approver($select=code))",
                   user="admin")
steps = [st for sc in schemes.get("value", []) for st in sc.get("steps", [])] if s_ == 200 else []
assert_(s_ == 200 and steps,
        f"every approval step can be read with the persona that signs it "
        f"({len(steps)} steps across {len(schemes.get('value', []))} schemes)",
        "; ".join(f"{st['name']}={(st.get('approver') or {}).get('code') or 'anyone'}"
                  for st in steps[:3]))

# The other half: who holds what, and where. Empty scope means everywhere, so
# the assignment screen has to show it rather than hide a blank column.
s_, assigns = call("/authorization/UserAssignments?$select=user,validFrom,isActive"
                   "&$expand=persona($select=code)&$top=50", user="admin")
rows = assigns.get("value", []) if s_ == 200 else []
named = [a for a in rows if (a.get("persona") or {}).get("code")]
assert_(rows and len(named) == len(rows),
        f"every assignment says which persona it grants ({len(named)})",
        ", ".join(f"{a['user']}={a['persona']['code']}" for a in named[:3]))

head("11. The numbers a home page would show")
# launchpadKpis computes thirteen tiles in one call, and until now nothing read
# it and nothing checked it. The launchpad shows plain counts from thirty-two
# separate calls instead, which is the round-tripping this action was written
# to avoid -- that gap is F-19. What follows checks the numbers themselves,
# because a wrong number on a home page is trusted longer than a wrong list.

kpis = check(200, "the launchpad numbers come in one call", *call(
    "/collaboration/launchpadKpis", user="admin", method="POST", body={}))
kpis = kpis if isinstance(kpis, list) else []

# A tile is a way into a screen. One computed for a screen nobody offers is a
# number with nowhere to go, and it survives the app being retired.
offered = {inbound.get("semanticObject")
           for manifest_path in glob.glob(os.path.join(APP_DIR, "*", "webapp",
                                                       "manifest.json"))
           for inbound in json.load(open(manifest_path, encoding="utf-8"))
           .get("sap.app", {}).get("crossNavigation", {}).get("inbounds", {}).values()}
homeless = sorted({k["tile"] for k in kpis} - offered)
assert_(kpis and not homeless,
        f"every number is computed for a screen an app actually offers "
        f"({len(kpis)} of them)",
        ", ".join(homeless) or "none homeless")

# A bare number on a home page is a riddle: 72 of what, and is that good?
bare = [k["tile"] for k in kpis
        if k.get("number") is None or not k.get("numberUnit") or not k.get("subtitle")]
assert_(not bare, "and each says what it counts and what it is about",
        ", ".join(bare) or "none bare")

states = {k.get("state") for k in kpis}
assert_(len(states) > 1,
        "the colour is computed from the number rather than fixed, so it tells "
        "somebody something the title did not",
        ", ".join(sorted(str(x) for x in states)))

# One anchor against the data itself. Without it the checks above would pass on
# thirteen well-formed numbers that were all wrong.
s_, projects = call("/project/Projects/$count", user="admin")
kpi = next((k for k in kpis if k["tile"] == "KonstryxProject"), {})
assert_(str(kpi.get("number", "")).split(".")[0] == str(projects).strip(),
        "and a number that is a count agrees with the list it would open",
        f"KonstryxProject says {kpi.get('number')}, the projects are {projects}")

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
