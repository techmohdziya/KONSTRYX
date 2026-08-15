"""End-to-end check of the approval engine against the running service."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"
ADMIN = ("admin", "admin")
USER = ("demo", "demo")
OTHER = ("daud", "daud")


def call(path, user=USER, method="GET", body=None):
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


def line(expected, label, status, payload):
    if isinstance(payload, dict):
        payload = payload.get("value", payload)
    mark = "ok  " if status == expected else "FAIL"
    print(f"  {mark} [{status}] {label}: {payload}")
    return status == expected


results = []


def head(n, title):
    print()
    print("=" * 74)
    print(f"{n}. {title}")
    print("=" * 74)


head(1, "Delivered schemes and their value bands")
s, schemes = call("/authorization/ApprovalSchemes?$select=ID,code,name"
                  "&$expand=steps($select=stepNo,name,minAmount;$orderby=stepNo)", user=ADMIN)
if s != 200:
    print("  FAILED:", schemes); sys.exit(1)
for sc in sorted(schemes["value"], key=lambda x: x["code"]):
    print(f"  {sc['code']:10} {sc['name']}")
    for st in sc["steps"]:
        band = f"   from {st['minAmount']:,.0f}" if st["minAmount"] is not None else "   any amount"
        print(f"      step {st['stepNo']}  {st['name']:26}{band}")

head(2, "Value bands select the steps at submission")
s, rrs = call("/workflow/ResourceRequests?$select=ID,docNo&$orderby=docNo&$top=6")
if s != 200 or not rrs.get("value"):
    print("  FAILED:", rrs); sys.exit(1)
requests = rrs["value"]

cases = [(requests[0], 50000, 1, "below every threshold"),
         (requests[1], 300000, 2, "over the commercial threshold"),
         (requests[2], 2000000, 3, "over the director threshold")]

for rr, amount, expected_steps, why in cases:
    s, msg = call("/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
        "docNo": rr["docNo"], "amount": amount})
    s2, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{rr['docNo']}'"
                    "&$select=ID&$expand=steps($select=stepNo)")
    got = len(inst["value"][0]["steps"]) if s2 == 200 and inst.get("value") else 0
    mark = "ok  " if got == expected_steps else "FAIL"
    print(f"  {mark} {rr['docNo']}  {amount:>10,}  {why:32} -> {got} step(s)")
    results.append(got == expected_steps)

head(3, "Submission refuses what it should")
rr = requests[0]
results.append(line(409, "same object submitted twice", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
        "docNo": rr["docNo"], "amount": 1})))
results.append(line(404, "object that does not exist", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest",
        "objectID": "00000000-0000-0000-0000-0000000000ff",
        "docNo": "GHOST", "amount": 1})))
s, wbs = call("/project/WBS?$select=ID,code&$top=1")
wbs_id = wbs["value"][0]["ID"] if s == 200 and wbs.get("value") else rr["ID"]
results.append(line(400, "a real object whose type has no scheme", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.prj.WBSElement", "objectID": wbs_id,
        "docNo": "X", "amount": 1})))
results.append(line(400, "entity not in the model", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.does.NotExist", "objectID": rr["ID"],
        "docNo": "X", "amount": 1})))

head(4, "A three-step approval, decided in order")
target = requests[2]
s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{target['docNo']}'"
               "&$select=ID,objectDocNo,status,amount"
               "&$expand=steps($select=ID,stepNo,name,decision;$orderby=stepNo)")
instance = inst["value"][0]
steps = sorted(instance["steps"], key=lambda x: x["stepNo"])
print(f"  {instance['objectDocNo']}  amount {float(instance['amount']):,.0f}  status {instance['status']}")

results.append(line(409, "approving step 3 before step 1", *call(
    f"/collaboration/ApprovalSteps({steps[2]['ID']})/CollaborationService.approve",
    method="POST", body={"comment": "jumping the queue"})))
results.append(line(400, "rejecting with no reason", *call(
    f"/collaboration/ApprovalSteps({steps[0]['ID']})/CollaborationService.reject",
    method="POST", body={"comment": ""})))
results.append(line(200, "step 1 approved", *call(
    f"/collaboration/ApprovalSteps({steps[0]['ID']})/CollaborationService.approve",
    method="POST", body={"comment": "Checked against the plan."})))
results.append(line(409, "approving step 1 twice", *call(
    f"/collaboration/ApprovalSteps({steps[0]['ID']})/CollaborationService.approve",
    method="POST", body={"comment": "again"})))
results.append(line(403, "same person taking step 2 (separation of duties)", *call(
    f"/collaboration/ApprovalSteps({steps[1]['ID']})/CollaborationService.approve",
    method="POST", body={"comment": "and again"})))
results.append(line(200, "step 2 approved by someone else", *call(
    f"/collaboration/ApprovalSteps({steps[1]['ID']})/CollaborationService.approve",
    user=OTHER, method="POST", body={"comment": "Commercially sound."})))

head(5, "Rejection ends the whole approval")
s, r = call(f"/collaboration/ApprovalSteps({steps[2]['ID']})/CollaborationService.reject",
            user=ADMIN, method="POST", body={"comment": "Scope not funded this quarter."})
results.append(line(200, "step 3 rejected", s, r))

s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{target['docNo']}'"
               "&$select=objectDocNo,status"
               "&$expand=steps($select=stepNo,decision,actedBy,comment;$orderby=stepNo)")
final = inst["value"][0]
print(f"\n  {final['objectDocNo']}  ->  {final['status']}")
for st in final["steps"]:
    print(f"      step {st['stepNo']}  {st['decision']:9} by {str(st['actedBy']):6} \"{st['comment']}\"")
results.append(final["status"] == "REJECTED")

head(6, "Withdrawal releases the object")
victim = requests[1]
s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{victim['docNo']}'&$select=ID")
iid = inst["value"][0]["ID"]
results.append(line(200, "withdrawn", *call(
    f"/collaboration/ApprovalInstances({iid})/CollaborationService.withdraw",
    method="POST", body={"reason": "Superseded by a revised request."})))
results.append(line(200, "the object can be submitted again", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": victim["ID"],
        "docNo": victim["docNo"], "amount": 90000})))

print()
print("=" * 74)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 74)
sys.exit(0 if passed == len(results) else 1)
