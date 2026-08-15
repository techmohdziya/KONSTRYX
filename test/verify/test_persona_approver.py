"""Proves the approver persona on a step is enforced, configured entirely through
the administration API — no redeploy, which is the point of the framework."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"
ADMIN = ("admin", "admin")


def call(path, user=ADMIN, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path.replace(" ", "%20"), data=data, method=method)
    req.add_header("Authorization", "Basic " + base64.b64encode(
        f"{user[0]}:{user[1]}".encode()).decode())
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            msg = json.loads(raw).get("error", {}).get("message", raw)
        except Exception:
            msg = raw[:300]
        return e.code, msg


results = []


def check(expected, label, status, payload):
    if isinstance(payload, dict):
        payload = payload.get("value", payload)
    mark = "ok  " if status == expected else "FAIL"
    print(f"  {mark} [{status}] {label}: {str(payload)[:150]}")
    results.append(status == expected)
    return payload


print("=" * 74)
print("Configuring an approver persona through the administration API")
print("=" * 74)

# Personas are draft-enabled, so this is create-draft then activate — the same
# path the administrator's screen takes.
s, draft = call("/authorization/Personas", method="POST", body={
    "code": "COMMERCIAL_MGR", "name": "Commercial Manager",
    "description": "Signs off resource requests above the commercial threshold.",
    "isActive": True})
if s not in (200, 201):
    print("  FAILED to create persona draft:", draft); sys.exit(1)
pid = draft["ID"]
print(f"  persona draft created: {pid}")

s, act = call(f"/authorization/Personas(ID={pid},IsActiveEntity=false)"
              "/AuthorizationService.draftActivate", method="POST", body={})
check(200, "persona activated", s, {"code": act.get("code") if isinstance(act, dict) else act})

# Assign it to jin only.
s, ua = call("/authorization/UserAssignments", method="POST", body={
    "user": "jin", "persona_ID": pid, "isActive": True})
check(201, "persona assigned to jin", s, {"user": "jin"})

# Point step 2 of the resource request scheme at it. Steps are a composition of
# a draft-enabled scheme, so they are edited through the draft — the same path
# the administrator's screen takes, not a shortcut around it.
s, scheme = call("/authorization/ApprovalSchemes?$filter=code eq 'RR-STD'&$select=ID")
scheme_id = scheme["value"][0]["ID"]
s, defs = call(f"/authorization/ApprovalStepDefs?$filter=scheme_ID eq {scheme_id} and stepNo eq 2"
               "&$select=ID,name")
step_def_id = defs["value"][0]["ID"]

check(200, "scheme opened for editing", *call(
    f"/authorization/ApprovalSchemes(ID={scheme_id},IsActiveEntity=true)"
    "/AuthorizationService.draftEdit", method="POST", body={"PreserveChanges": True}))
check(200, "step 2 set to require Commercial Manager", *call(
    f"/authorization/ApprovalStepDefs(ID={step_def_id},IsActiveEntity=false)",
    method="PATCH", body={"approver_ID": pid}))
check(200, "scheme change activated", *call(
    f"/authorization/ApprovalSchemes(ID={scheme_id},IsActiveEntity=false)"
    "/AuthorizationService.draftActivate", method="POST", body={}))

print()
print("=" * 74)
print("The step now refuses anyone without that persona")
print("=" * 74)

s, rrs = call("/workflow/ResourceRequests?$select=ID,docNo&$orderby=docNo desc&$top=1",
              user=("demo", "demo"))
rr = rrs["value"][0]

s, r = call("/collaboration/submitForApproval", user=("demo", "demo"), method="POST", body={
    "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
    "docNo": rr["docNo"], "amount": 400000})
check(200, f"{rr['docNo']} submitted at 400,000", s, r)

s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{rr['docNo']}'"
               "&$select=ID&$expand=steps($select=ID,stepNo,name;$orderby=stepNo)",
               user=("demo", "demo"))
steps = sorted(inst["value"][0]["steps"], key=lambda x: x["stepNo"])
print(f"  raised {len(steps)} steps: " + ", ".join(f"{s['stepNo']}={s['name']}" for s in steps))

check(200, "step 1 approved by demo", *call(
    f"/collaboration/ApprovalSteps({steps[0]['ID']})/CollaborationService.approve",
    user=("demo", "demo"), method="POST", body={"comment": "Needed on site."}))

check(403, "step 2 refused for daud (no persona)", *call(
    f"/collaboration/ApprovalSteps({steps[1]['ID']})/CollaborationService.approve",
    user=("daud", "daud"), method="POST", body={"comment": "trying"}))

check(200, "step 2 delegated by jin to rohan", *call(
    f"/collaboration/ApprovalSteps({steps[1]['ID']})/CollaborationService.delegate",
    user=("jin", "jin"), method="POST", body={"to": "rohan", "comment": "On leave this week."}))

check(200, "step 2 approved by rohan as delegate", *call(
    f"/collaboration/ApprovalSteps({steps[1]['ID']})/CollaborationService.approve",
    user=("rohan", "rohan"), method="POST", body={"comment": "Within the commercial plan."}))

s, final = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{rr['docNo']}'"
                "&$select=objectDocNo,status"
                "&$expand=steps($select=stepNo,decision,actedBy,delegatedTo;$orderby=stepNo)",
                user=("demo", "demo"))
f = final["value"][0]
print()
print(f"  {f['objectDocNo']}  ->  {f['status']}")
for st in f["steps"]:
    via = f"  (delegated from the persona holder to {st['delegatedTo']})" if st["delegatedTo"] else ""
    print(f"      step {st['stepNo']}  {st['decision']:9} by {st['actedBy']}{via}")
results.append(f["status"] == "APPROVED")
print(f"  {'ok  ' if f['status'] == 'APPROVED' else 'FAIL'} instance closed as APPROVED")

print()
print("=" * 74)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 74)
sys.exit(0 if passed == len(results) else 1)
