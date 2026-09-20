"""Project Setup (D-17): a project is created in KONSTRYX and pushed to S/4,
and is visibly not in S/4 until the connector says otherwise."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"
PM = "demo"


def call(path, user=PM, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path.replace(" ", "%20"), data=data, method=method)
    req.add_header("Authorization", "Basic " + base64.b64encode(
        f"{user}:{user}".encode()).decode())
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            out = r.read().decode(errors="replace")
            return r.status, (json.loads(out) if out.strip().startswith(("{", "[")) else out)
    except urllib.error.HTTPError as e:
        out = e.read().decode(errors="replace")
        try:
            msg = json.loads(out).get("error", {}).get("message", out)
        except Exception:
            msg = out[:400]
        return e.code, msg


results = []


def check(expected, label, status, payload):
    if isinstance(payload, dict):
        payload = payload.get("value", payload)
    mark = "ok  " if status == expected else "FAIL"
    print(f"  {mark} [{status}] {label}: {str(payload)[:170]}")
    results.append(status == expected)
    return payload


def head(t):
    print()
    print("=" * 76)
    print(t)
    print("=" * 76)


def draft_create(fields):
    return call("/project/Projects", method="POST", body=fields)


def activate(pid):
    return call(f"/project/Projects(ID={pid},IsActiveEntity=false)"
                "/ProjectService.draftActivate", method="POST", body={})


head("1. Seeded projects now report their real sync state")
s, ps = call("/project/Projects?$select=code,name,syncStatus,s4Key"
             "&$filter=IsActiveEntity eq true&$orderby=code")
for p in ps["value"]:
    print(f"      {p['code']:10} {p['syncStatus']:9} {str(p['s4Key'] or '—'):22} {p['name']}")
# The seed used to ship these as SENT, with invented s4Keys and a system
# (S4HC_100) that exists nowhere — and syncAttempts 0 to prove no connector had
# ever run. That is a demo asserting something false, and it locked the project
# out of releaseToS4 forever, because release refuses anything already SENT.
# A seeded project has not been anywhere: it reads NOT_SENT and holds no key.
ok = all(p["syncStatus"] == "NOT_SENT" and not p["s4Key"] for p in ps["value"])
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} a seeded project claims no sync it has not had")

head("2. A new project is created here and is NOT in S/4")
s, co = call("/project/Projects?$filter=IsActiveEntity eq true&$select=company_ID&$top=1")
company_id = co["value"][0]["company_ID"]

d = check(201, "draft created", *draft_create({
    "code": "PRJ-900", "name": "Dubai Hills Villas Phase 2",
    "company_ID": company_id, "customerParent": "Meraas",
    "contractValue": 18500000.00, "ccy_code": "AED",
    "startDate": "2026-09-01", "endDate": "2028-03-31"}))
pid = d["ID"]
p = check(200, "activated", *activate(pid))
ok = p.get("syncStatus") == "NOT_SENT"
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} syncStatus is {p.get('syncStatus')} — not OK, which is the whole point")

head("3. What the validation refuses")
d2, = [draft_create({"code": "PRJ-001", "name": "Duplicate code",
                     "company_ID": company_id,
                     "startDate": "2026-01-01", "endDate": "2026-12-31"})[1]]
check(409, "duplicate project code", *activate(d2["ID"]))

d3 = draft_create({"code": "PRJ-901", "name": "Backwards",
                   "company_ID": company_id,
                   "startDate": "2026-12-31", "endDate": "2026-01-01"})[1]
check(400, "end date before start date", *activate(d3["ID"]))

d4 = draft_create({"code": "PRJ-902", "name": "No company"})[1]
check(400, "no company", *activate(d4["ID"]))

d5 = draft_create({"code": "", "name": "No code", "company_ID": company_id})[1]
check(400, "no code", *activate(d5["ID"]))

head("4. Sync status cannot be set by hand")
check(200, "project opened for editing", *call(
    f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.draftEdit",
    method="POST", body={"PreserveChanges": True}))
check(403, "editing sync status in the draft", *call(
    f"/project/Projects(ID={pid},IsActiveEntity=false)", method="PATCH",
    body={"syncStatus": "SENT", "s4Key": "FAKE-1"}))
# Whatever the protocol layer answers, the value must not have taken.
st2, drafted = call(f"/project/Projects(ID={pid},IsActiveEntity=false)"
                    "?$select=syncStatus,s4Key")
held = drafted.get("syncStatus") == "NOT_SENT" and not drafted.get("s4Key")
results.append(held)
print(f"  {'ok  ' if held else 'FAIL'} the draft still reads"
      f" {drafted.get('syncStatus')} / s4Key={drafted.get('s4Key')}")

head("5. Release refuses a project S/4 would reject")
# A WBS element is added through the project draft, which is where it belongs:
# a WBS element only means anything inside the project that owns it.
s, w = call(f"/project/Projects(ID={pid},IsActiveEntity=false)/wbsElements",
            method="POST", body={"code": "PRJ-900.1", "description": "Enabling works"})
print(f"      added a WBS element to the draft [{s}]")
results.append(s in (200, 201))
check(200, "project activated with its WBS", *call(
    f"/project/Projects(ID={pid},IsActiveEntity=false)/ProjectService.draftActivate",
    method="POST", body={}))

check(200, "release queues it", *call(
    f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.releaseToS4",
    method="POST", body={}))
check(409, "releasing twice", *call(
    f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.releaseToS4",
    method="POST", body={}))

s, p = call(f"/project/Projects(ID={pid},IsActiveEntity=true)?$select=code,syncStatus")
ok = p.get("syncStatus") == "PENDING"
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} now {p.get('syncStatus')} — queued, still not in S/4")

head("6. The connector reports back")
check(200, "S/4 refuses it", *call(
    f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.recordSyncResult",
    method="POST", body={"success": False, "message": "Profile YBPM01 not assigned to company 1010"}))
s, p = call(f"/project/Projects(ID={pid},IsActiveEntity=true)"
            "?$select=syncStatus,syncMessage,syncAttempts")
ok = p["syncStatus"] == "FAILED" and p["syncAttempts"] == 1
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} {p['syncStatus']}, attempt {p['syncAttempts']}: \"{p['syncMessage']}\"")

check(200, "retried and accepted", *call(
    f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.recordSyncResult",
    method="POST", body={"success": True, "s4Key": "D-900-2026",
                         "s4System": "S4HC_100", "message": "Created"}))
s, p = call(f"/project/Projects(ID={pid},IsActiveEntity=true)"
            "?$select=code,syncStatus,s4Key,syncAttempts,lastSyncedAt")
ok = p["syncStatus"] == "SENT" and p["s4Key"] == "D-900-2026" and p["syncAttempts"] == 2
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} {p['code']} is {p['syncStatus']} as {p['s4Key']}"
      f" after {p['syncAttempts']} attempts")

head("7. A project a person defines, header and WBS together")
# The header alone is refused. A project with no WBS element cannot be
# released - S/4 has nothing to post against - so a create that accepted one
# would manufacture the state PRJ-002 is stuck in: complete-looking and
# permanently unreleasable.
check(400, "header with no WBS is refused", *call(
    "/project/createProject", method="POST",
    body={"code": "PRJ-T90", "name": "Typed project", "companyCode": "INFC",
          "startDate": "2026-09-01", "endDate": "2027-03-31", "wbs": []}))

check(400, "an unknown company is refused", *call(
    "/project/createProject", method="POST",
    body={"code": "PRJ-T91", "name": "Typed project", "companyCode": "NOPE",
          "startDate": "2026-09-01", "endDate": "2027-03-31",
          "wbs": [{"code": "T91-1", "description": "Enabling"}]}))

check(200, "created with its WBS", *call(
    "/project/createProject", method="POST",
    body={"code": "PRJ-T90", "name": "Typed project", "companyCode": "INFC",
          "startDate": "2026-09-01", "endDate": "2027-03-31",
          "contractValue": 1250000,
          "wbs": [{"code": "T90-1", "description": "Enabling works"},
                  {"code": "T90-2", "description": "Structure"}]}))

s_, typed = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'PRJ-T90'"
                 "&$select=ID,code,syncStatus,s4Key,contractValue")
row = typed["value"][0] if typed.get("value") else {}
ok = row.get("syncStatus") == "NOT_SENT" and not row.get("s4Key")
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} {row.get('code')} is {row.get('syncStatus')} "
      f"with no S/4 key - creating a project does not put it in S/4")

tid = row.get("ID")
s_, wbs = call(f"/project/WBS?$filter=project_ID eq {tid}&$select=code,description")
ok = len(wbs.get("value", [])) == 2
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} {len(wbs.get('value', []))} WBS element(s) came with it")

check(409, "the same code twice is refused", *call(
    "/project/createProject", method="POST",
    body={"code": "PRJ-T90", "name": "Duplicate", "companyCode": "INFC",
          "startDate": "2026-09-01", "endDate": "2027-03-31",
          "wbs": [{"code": "T90-9", "description": "Dup"}]}))

# Release stops at PENDING because run_all.sh sets S4_OFFLINE. That is
# deliberate and not incidental: release posts to S/4 the moment it is called,
# so without the off switch a verification run writes real documents into
# whatever tenant a developer's .env happens to name - which is exactly what
# happened the first time this suite ran against the new behaviour.
check(200, "release queues it", *call(
    f"/project/Projects(ID={tid},IsActiveEntity=true)/ProjectService.releaseToS4",
    method="POST", body={}))
s_, after = call(f"/project/Projects(ID={tid},IsActiveEntity=true)?$select=syncStatus")
ok = after.get("syncStatus") == "PENDING"
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} {after.get('syncStatus')} - queued, and with no "
      f"connection configured that is where it stops")

head("8. Which projects are not in S/4 — the list that matters")
s, unsynced = call("/project/Projects?$filter=IsActiveEntity eq true and syncStatus ne 'SENT'"
                   "&$select=code,name,syncStatus")
for p in unsynced["value"]:
    print(f"      {p['code']:10} {p['syncStatus']:9} {p['name']}")
print(f"      ({len(unsynced['value'])} project(s) nothing should be posted against)")

head("9. And now nothing IS posted against them")
# The line above used to be a hope. A budget is the project's control figure,
# and until this gate existed one could be submitted, approved by three people
# and baselined against a project ERP had never heard of -- BUD-2026-0103 was,
# at 7,525,075.47.
s, drafts = call("/budget/Budgets?$filter=status eq 'Draft'&$select=ID,docNo,project_ID")
budget = drafts["value"][0]
bid, docno, pid = budget["ID"], budget["docNo"], budget["project_ID"]


def bud(action):
    return call(f"/budget/Budgets(ID={bid},IsActiveEntity=true)/BudgetService.{action}",
                method="POST", body={})


def sync(**body):
    return call(f"/project/Projects(ID={pid},IsActiveEntity=true)"
                "/ProjectService.recordSyncResult", method="POST", body=body)


# A tenant with no ERP is not out of step with anything -- it IS the record.
# Refusing here would make the product unusable without a live connection, and
# every suite in this run would fail, which is the point: the gate asks whether
# there is an ERP, not merely what the status says.
check(200, f"{docno} submits with no ERP configured at all", *bud("submit"))

# But a refusal is a fact about the project, and switching the connection off
# does not unsay it.
check(200, "ERP refuses the project mid-approval", *sync(
    success=False, s4Key=None, s4System="TEST",
    message="Profit Center 10001000 does not exist"))

s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{docno}'"
               "&$select=ID&$expand=steps($select=ID,stepNo;$orderby=stepNo)")
for i, st in enumerate(inst["value"][0]["steps"]):
    call(f"/collaboration/ApprovalSteps({st['ID']})/CollaborationService.approve",
         method="POST", body={"comment": "Within the tender allowance."},
         user=["demo", "daud", "admin"][i])

status, refusal = bud("baseline")
ok = status == 409 and "refused by ERP" in str(refusal)
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} [{status}] approved by three people and still "
      f"refused: {str(refusal)[:150]}")

# And the refusal carries what ERP actually said, so the fix is in the message
# rather than in a log somebody has to go and find.
ok = "Profit Center 10001000 does not exist" in str(refusal)
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} in ERP's own words, not a generic 'not synced'")

check(200, "ERP accepts the project", *sync(
    success=True, s4Key="P-000123", s4System="TEST", message="Created"))
check(200, "and the same budget baselines, unchanged", *bud("baseline"))
s, done = call(f"/budget/Budgets(ID={bid},IsActiveEntity=true)?$select=docNo,status")
ok = done.get("status") == "Baselined"
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} {done.get('docNo')} is {done.get('status')} - the "
      f"gate was the project, and it moved")

print()
print("=" * 76)
print("The cost mapping workbench, asked twice")
print("=" * 76)

# costMappingPortfolio and costMappingSummary answer the same question at two
# scales: which projects need a human, and what that human faces on one of
# them. Two implementations of one question is exactly the shape that drifts,
# and neither had ever been called by a test.

s, portfolio = call("/project/costMappingPortfolio", user="admin", method="POST", body={})
rows = {r["projectCode"]: r for r in portfolio.get("value", [])} if s == 200 else {}
results.append(s == 200 and bool(rows))
print(f"  {'ok  ' if rows else 'FAIL'} [{s}] the portfolio answers for every project "
      f"at once: {len(rows)} projects")

s, listed = call("/project/Projects?$select=ID,code&$orderby=code", user="admin")
projects = listed.get("value", []) if s == 200 else []
results.append(len(rows) == len(projects))
print(f"  {'ok  ' if len(rows) == len(projects) else 'FAIL'} and leaves none out: "
      f"{len(rows)} of {len(projects)}")

# A workbench that says a project needs attention while the project's own page
# says it does not is worse than either number alone.
drifted, compared = [], 0
for project in projects:
    s, one = call(f"/project/Projects(ID={project['ID']},IsActiveEntity=true)"
                  "/ProjectService.costMappingSummary", user="admin", method="POST", body={})
    if s != 200:
        drifted.append(f"{project['code']} summary [{s}]")
        continue
    summary = {k: v for k, v in one.items() if not k.startswith("@")}
    row = rows.get(project["code"], {})
    for field in sorted(set(summary) & set(row)):
        compared += 1
        if summary[field] != row[field]:
            drifted.append(f"{project['code']}.{field} {summary[field]} vs {row[field]}")
results.append(not drifted)
print(f"  {'ok  ' if not drifted else 'FAIL'} and agrees with each project's own "
      f"workbench on every count it shares ({compared} comparisons): "
      f"{'; '.join(drifted) if drifted else 'no disagreement'}")

# The point of the workbench is that it does not render the 1,127 lines that
# mapped themselves. A count of exceptions that exceeds the lines there are is
# the failure that would put every one of them on the screen.
overshoot = [f"{code}: {r.get('exceptionCount')} of {r.get('totalLines')}"
             for code, r in rows.items()
             if r.get("exceptionCount") is not None and r.get("totalLines") is not None
             and r["exceptionCount"] > r["totalLines"]]
results.append(not overshoot)
print(f"  {'ok  ' if not overshoot else 'FAIL'} and never claims more exceptions than "
      f"there are lines: {'; '.join(overshoot) if overshoot else 'none overshoot'}")

print()
print("=" * 76)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 76)
sys.exit(0 if passed == len(results) else 1)
