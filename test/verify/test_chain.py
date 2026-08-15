"""Phase 4 spine: request -> approval -> advisory -> availability -> reservation.

The test walks one request through the whole chain and tries every shortcut on
the way, because the chain's value is precisely that the shortcuts fail."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"
USER = "demo"


def call(path, method="GET", body=None, user=USER):
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
            if not out.strip().startswith(("{", "[")):
                return r.status, out
            parsed = json.loads(out)
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
            msg = out[:400]
        return e.code, msg


results = []


def check(expected, label, status, payload):
    if isinstance(payload, dict):
        payload = payload.get("value", payload)
    ok = status == expected
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] {label}: {str(payload)[:170]}")
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


# ------------------------------------------------------------------- fixtures
s, ps = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'PRJ-001'"
             "&$select=ID,company_ID")
project = ps["value"][0]
s, wbs = call(f"/project/WBS?$filter=project_ID eq {project['ID']}&$select=ID,code&$top=1")
wbs_id = wbs["value"][0]["ID"]

s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-TWC-12T'"
              "&$select=ID")
crane = res["value"][0]["ID"]
s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-VIB-KIT'"
              "&$select=ID")
vibro = res["value"][0]["ID"]

# An L5 with no rate, found rather than assumed, to prove pricing refuses it.
s, rated = call("/masterdata/Rates?$filter=IsActiveEntity eq true&$select=resource_ID&$top=200")
rated_ids = {r["resource_ID"] for r in rated["value"]}
s, l5s = call("/masterdata/Resources?$filter=IsActiveEntity eq true and level eq 'L5'"
              "&$select=ID,code&$top=50")
unrated = [r for r in l5s["value"] if r["ID"] not in rated_ids]
print(f"  fixtures: crane rated, {len(unrated)} unrated L5(s) available"
      f" ({unrated[0]['code'] if unrated else '—'})")


def new_request(lines):
    s, d = call("/workflow/ResourceRequests", method="POST", body={
        "verticalType": "EQR", "project_ID": project["ID"],
        "company_ID": project["company_ID"], "wbs_ID": wbs_id,
        "needBy": "2026-10-01", "raisedBy": "demo", "raisedOn": "2026-08-15"})
    rid = d["ID"]
    for i, line in enumerate(lines, start=1):
        line = dict(line)
        line["lineNo"] = i
        call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=false)/lines",
             method="POST", body=line)
    s, act = call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=false)"
                  "/WorkflowService.draftActivate", method="POST", body={})
    return rid, act.get("docNo") if isinstance(act, dict) else None


def rr_action(rid, action, body=None):
    return call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)"
                f"/WorkflowService.{action}", method="POST", body=body or {})


head("1. Submit prices the lines and hands the request to approval")
rid, docno = new_request([
    {"resource_ID": crane, "description": "Tower crane", "qty": 1, "uom": "inst",
     "wbs_ID": wbs_id, "needBy": "2026-10-01"},
    {"resource_ID": vibro, "description": "Vibrator kits", "qty": 4, "uom": "kit",
     "wbs_ID": wbs_id, "needBy": "2026-09-15"},
])
print(f"      created {docno}")
assert_(docno and docno.startswith("RR-"), "the request drew a document number", docno)

check(409, "advisory before approval", *rr_action(rid, "decideLine",
    {"lineNo": 1, "decision": "IN_HOUSE", "rationale": "x"}))
check(200, "submitted", *rr_action(rid, "submit"))
check(409, "submitted twice", *rr_action(rid, "submit"))

s, lines = call(f"/workflow/ResourceRequestLines?$filter=parent_ID eq {rid}"
                "&$select=lineNo,estUnitCost,estTotal&$orderby=lineNo")
for l in lines["value"]:
    print(f"        line {l['lineNo']}: {l['estUnitCost']} x qty = {l['estTotal']}")
assert_(all(float(l["estTotal"] or 0) > 0 for l in lines["value"]),
        "every line was priced from the rate master at submit")

head("2. The approval outcome moves the request itself")
s, rr = call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)?$select=status,docNo")
assert_(rr.get("status") == "In Approval", "the request reads In Approval", rr.get("status"))

s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{docno}'"
               "&$select=ID&$expand=steps($select=ID,stepNo;$orderby=stepNo)")
steps = inst["value"][0]["steps"]
for st in steps:
    call(f"/collaboration/ApprovalSteps({st['ID']})/CollaborationService.approve",
         method="POST", body={"comment": "Within plan."},
         user="daud" if st is steps[-1] and len(steps) > 1 else "demo")

s, rr = call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)?$select=status")
assert_(rr.get("status") == "Approved",
        "no one re-keyed the status — the approval closing set it", rr.get("status"))

head("3. Advisory, line by line")
check(400, "REJECT without a rationale", *rr_action(rid, "decideLine",
    {"lineNo": 2, "decision": "REJECT"}))
check(400, "a decision that is not a decision", *rr_action(rid, "decideLine",
    {"lineNo": 1, "decision": "MAYBE"}))
check(200, "line 1 in-house", *rr_action(rid, "decideLine",
    {"lineNo": 1, "decision": "IN_HOUSE", "rationale": "Fleet has one in the yard."}))
check(409, "line 1 decided twice", *rr_action(rid, "decideLine",
    {"lineNo": 1, "decision": "PROCURE", "rationale": "changed my mind"}))
check(409, "availability before every line is decided", *rr_action(rid, "runAvailabilityCheck"))
check(200, "line 2 procured", *rr_action(rid, "decideLine",
    {"lineNo": 2, "decision": "PROCURE", "rationale": "Cheaper to hire."}))

s, rr = call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)?$select=status")
assert_(rr.get("status") == "Advised", "all lines decided moves the request", rr.get("status"))

head("4. Availability documents what KONSTRYX itself knows")
check(409, "reservation before availability", *rr_action(rid, "createReservation"))
avc_msg = check(200, "checked", *rr_action(rid, "runAvailabilityCheck"))
assert_("already reserved elsewhere" in str(avc_msg) or "committed elsewhere" in str(avc_msg),
        "the seeded reservation on the same crane is visible as competition",
        str(avc_msg)[:110])

head("5. Reservation encumbers the value the approval was shown")
res_msg = check(200, "reserved", *rr_action(rid, "createReservation"))
check(409, "reserved twice", *rr_action(rid, "createReservation"))

expected = sum(float(l["estTotal"]) for l in lines["value"][:1])   # only line 1 is in-house
assert_(f"{expected:.2f}".rstrip("0").rstrip(".") in str(res_msg)
        or f"{expected:.2f}" in str(res_msg),
        "the encumbrance equals line 1's approved value", f"{expected:.2f}")

s, resv = call(f"/workflow/Reservations?$filter=rr_ID eq {rid}"
               "&$select=ID,docNo,status,executionFlow")
resv = resv["value"][0]
assert_(resv["docNo"].startswith("RES-"), "the reservation drew its own number", resv["docNo"])

s, rl = call(f"/workflow/ReservationLines?$filter=reservation_ID eq {resv['ID']}"
             "&$select=qty,dailyRate,encumberedAmount,lineStatus")
for l in rl["value"]:
    print(f"        {l['qty']} @ {l['dailyRate']} -> encumbered {l['encumberedAmount']}"
          f" [{l['lineStatus']}]")
assert_(len(rl["value"]) == 1, "only the in-house line was reserved — the procured one was not")

head("6. Close, and the trail the chain left")
check(200, "closed", *call(f"/workflow/Reservations({resv['ID']})"
                           "/WorkflowService.close", method="POST", body={}))
check(409, "closed twice", *call(f"/workflow/Reservations({resv['ID']})"
                                 "/WorkflowService.close", method="POST", body={}))

s, hist = call(f"/workflow/StatusHistory?$filter=docId eq '{docno}'"
               "&$select=fromState,toState,comment&$orderby=changedOn")
trail = [f"{h['fromState'] or '·'}->{h['toState']}" for h in hist["value"]]
print(f"      {docno}: {' | '.join(trail)}")
assert_(any(h["toState"] == "In Approval" for h in hist["value"])
        and any(h["toState"] == "Reserved" for h in hist["value"]),
        "every transition was recorded")

s, links = call(f"/workflow/DocumentLinks?$filter=fromDoc eq '{docno}'&$select=toDoc,linkType")
for l in links["value"]:
    print(f"      {docno} -> {l['toDoc']} ({l['linkType']})")
assert_(len(links["value"]) == 2, "the request links to its AVC and its reservation")

head("7. A request that cannot be priced is refused at submit")
if unrated:
    rid2, docno2 = new_request([
        {"resource_ID": unrated[0]["ID"], "description": "Unrated resource",
         "qty": 2, "uom": "ea", "wbs_ID": wbs_id}])
    check(400, "no rate in force for the resource", *rr_action(rid2, "submit"))
else:
    assert_(False, "no unrated L5 available to test with")

rid3, docno3 = new_request([])
check(400, "a request with no lines", *rr_action(rid3, "submit"))

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
