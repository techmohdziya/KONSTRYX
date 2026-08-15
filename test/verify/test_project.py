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
ok = all(p["syncStatus"] == "SENT" for p in ps["value"])
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} the two seeded projects came from S/4, so they read SENT")

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

head("7. Which projects are not in S/4 — the list that matters")
s, unsynced = call("/project/Projects?$filter=IsActiveEntity eq true and syncStatus ne 'SENT'"
                   "&$select=code,name,syncStatus")
for p in unsynced["value"]:
    print(f"      {p['code']:10} {p['syncStatus']:9} {p['name']}")
print(f"      ({len(unsynced['value'])} project(s) nothing should be posted against)")

print()
print("=" * 76)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 76)
sys.exit(0 if passed == len(results) else 1)
