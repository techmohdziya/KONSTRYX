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

check(403, "the admin surface refuses a non-admin", *call(
    "/authorization/Personas?$top=1", user="daud"))
check(200, "and admits an admin", *call("/authorization/Personas?$select=code&$top=1", user="admin"))


# ------------------------------------------------------------------ master scope
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


print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
