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
               "&$select=fromState,toState,comment&$orderby=seq")
trail = [f"{h['fromState'] or '·'}->{h['toState']}" for h in hist["value"]]
print(f"      {docno}: {' | '.join(trail)}")
assert_(any(h["toState"] == "In Approval" for h in hist["value"])
        and any(h["toState"] == "Reserved" for h in hist["value"]),
        "every transition was recorded")

# The account has to start somewhere. A request used to carry no status at all
# between being activated and being submitted -- it had a number, lines and
# prices and said nothing about where it was -- so the first entry read "from
# nothing", every screen that groups by status dropped it, and each guard that
# allowed a submit had to spell out that null meant the same as Draft. An
# accommodation every new document type would have had to remember to repeat.
first = hist["value"][0] if hist["value"] else {}
assert_(first.get("fromState") == "Draft",
        "and the first of them names the state the document actually started in",
        f"{first.get('fromState')} -> {first.get('toState')}")
assert_(all(h.get("fromState") for h in hist["value"]),
        "with no entry coming from nowhere",
        " | ".join(str(h.get("fromState")) for h in hist["value"]))

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

head("8. A line priced per day is priced for the days it is wanted")
# Quantity times rate answers "how many, at what each". For a resource hired
# by the day it answers a different question from the one the money asks: one
# crane at 320 a day is 320, which is what a single day costs and never what
# the request meant. The period is the third figure, and until it existed the
# only way to get a duration into a request was to type the total by hand.
s, prj = call(f"/project/Projects(ID={project['ID']},IsActiveEntity=true)"
              "?$select=startDate,endDate")

rid8, docno8 = new_request([
    # 1st to the 10th, both ends counted: ten days, not nine. The day a crane
    # arrives is a day it is paid for.
    {"resource_ID": crane, "description": "Tower crane, ten days", "qty": 2,
     "uom": "inst", "wbs_ID": wbs_id, "needBy": "2026-10-01",
     "periodFrom": "2026-10-01", "periodTo": "2026-10-10"},
    # No period, so nothing about duration has been said and the old
    # arithmetic stands. Multiplying this by a duration would invent one.
    {"resource_ID": vibro, "description": "Vibrator kits, no period", "qty": 4,
     "uom": "kit", "wbs_ID": wbs_id, "needBy": "2026-09-15"},
])
check(200, "submitted", *rr_action(rid8, "submit"))

s, lines8 = call(f"/workflow/ResourceRequestLines?$filter=parent_ID eq {rid8}"
                 "&$select=lineNo,qty,estUnitCost,estTotal,periodFrom,periodTo"
                 "&$orderby=lineNo")
hired, bare = lines8["value"][0], lines8["value"][1]

want = float(hired["estUnitCost"]) * float(hired["qty"]) * 10
assert_(abs(float(hired["estTotal"]) - want) < 0.01,
        "the hired line is rate x quantity x ten days, both ends counted",
        f"{hired['estTotal']} vs {want:.2f}")
assert_(abs(float(bare["estTotal"])
            - float(bare["estUnitCost"]) * float(bare["qty"])) < 0.01,
        "and a line with no period is priced exactly as it always was",
        str(bare["estTotal"]))

# The two lines carry the same shape of figures, so the only thing separating
# them is the period. If duration were being applied to everything, this is
# the check that would fail.
assert_(float(hired["estTotal"]) > float(hired["estUnitCost"]) * float(hired["qty"]),
        "duration is what makes the difference between them",
        f"{hired['estTotal']} > {float(hired['estUnitCost']) * float(hired['qty']):.2f}")

head("9. Half a period is not a period, and neither is a negative one")
rid9a, _ = new_request([
    {"resource_ID": crane, "description": "One end only", "qty": 1, "uom": "inst",
     "wbs_ID": wbs_id, "periodFrom": "2026-10-01"}])
check(400, "a start with no end is refused", *rr_action(rid9a, "submit"))

rid9b, _ = new_request([
    {"resource_ID": crane, "description": "Ends before it starts", "qty": 1,
     "uom": "inst", "wbs_ID": wbs_id,
     "periodFrom": "2026-10-10", "periodTo": "2026-10-01"}])
check(400, "a period that ends before it starts is refused", *rr_action(rid9b, "submit"))

# One day, not none. The boundary is the case a duration gets wrong most often.
rid9c, _ = new_request([
    {"resource_ID": crane, "description": "Single day", "qty": 1, "uom": "inst",
     "wbs_ID": wbs_id, "periodFrom": "2026-10-01", "periodTo": "2026-10-01"}])
check(200, "a period of one day is a period", *rr_action(rid9c, "submit"))
s, one = call(f"/workflow/ResourceRequestLines?$filter=parent_ID eq {rid9c}"
              "&$select=qty,estUnitCost,estTotal")
one = one["value"][0]
assert_(abs(float(one["estTotal"]) - float(one["estUnitCost"])) < 0.01,
        "and it costs one day, not zero",
        str(one["estTotal"]))

head("10. A hire the programme has no room for is said, not refused")
# Refusing would be wrong. A project's dates move, and a request running past
# them is often the reason they are about to. What must not happen is an
# approver signing for it without being told.
if prj.get("endDate"):
    end = str(prj["endDate"])[:10]
    after = f"{int(end[:4]) + 2}{end[4:]}"
    rid10, docno10 = new_request([
        {"resource_ID": crane, "description": "Hire past the end of the job",
         "qty": 1, "uom": "inst", "wbs_ID": wbs_id,
         "periodFrom": after, "periodTo": after}])
    check(200, "it submits", *rr_action(rid10, "submit"))
    s, hist = call(f"/workflow/StatusHistory?$filter=docId eq '{docno10}'"
                   "&$select=comment&$orderby=seq desc&$top=5")
    said = any("outside the project" in (h.get("comment") or "")
               for h in hist["value"])
    assert_(said, "and the trail says the period falls outside the project's dates",
            "; ".join((h.get("comment") or "")[:60] for h in hist["value"]) or "(no history)")
else:
    assert_(False, "PRJ-001 has no end date to test the window against")

head("11. The reservation records the duration it locked for")
# Reading the days back out of the lock works only while the lock was built
# the way it reads. A line that locked nothing divides to nothing, and every
# variation on it would then lock nothing too.
s, inst8 = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{docno8}'"
                "&$select=ID&$expand=steps($select=ID,stepNo;$orderby=stepNo)")
steps8 = inst8["value"][0]["steps"]
for i, stp in enumerate(steps8):
    call(f"/collaboration/ApprovalSteps({stp['ID']})/CollaborationService.approve",
         method="POST", body={"comment": "Within plan."},
         user="daud" if i == len(steps8) - 1 and len(steps8) > 1 else "demo")

rr_action(rid8, "decideLine",
          {"lineNo": 1, "decision": "IN_HOUSE", "rationale": "Fleet has one."})
rr_action(rid8, "decideLine",
          {"lineNo": 2, "decision": "IN_HOUSE", "rationale": "Kits in the store."})
rr_action(rid8, "runAvailabilityCheck")
check(200, "reserved", *rr_action(rid8, "createReservation"))

s, resv8 = call(f"/workflow/Reservations?$filter=rr_ID eq {rid8}&$select=ID")
s, rl8 = call(f"/workflow/ReservationLines?$filter=reservation_ID eq {resv8['value'][0]['ID']}"
              "&$select=qty,dailyRate,encumberedAmount,reservedDays,rrLine_ID")
hired_res = [l for l in rl8["value"]
             if abs(float(l["encumberedAmount"]) - want) < 0.01]
assert_(hired_res and abs(float(hired_res[0]["reservedDays"]) - 10) < 0.01,
        "the reservation carries the ten days rather than implying them",
        str(hired_res[0]["reservedDays"]) if hired_res else "line not found")

if hired_res:
    l = hired_res[0]
    implied = float(l["encumberedAmount"]) / (float(l["qty"]) * float(l["dailyRate"]))
    assert_(abs(implied - float(l["reservedDays"])) < 0.01,
            "and it agrees with what the lock implies, which is why the old "
            "reservations can still be read",
            f"{implied:.2f} vs {l['reservedDays']}")

    # The line with no period reserved too, and it must not have invented one.
    bare_res = [r for r in rl8["value"] if r["rrLine_ID"] != l["rrLine_ID"]]
    assert_(bare_res and bare_res[0].get("reservedDays") is None,
            "a line that said nothing about duration still says nothing",
            str(bare_res[0].get("reservedDays")) if bare_res else "line not found")

head("12. What was approved is what stays on the request")
# The approval records the value it judged and nothing re-checked it, so a
# request approved at one quantity could be raised tenfold afterwards. Worse
# than the amount drifting: the value is stored rather than recomputed, so the
# line ends up carrying a quantity and a total describing different requests,
# and the reservation has already locked money against the old one.
rid12, docno12 = new_request([
    {"resource_ID": crane, "description": "Crane, to be edited", "qty": 1,
     "uom": "inst", "wbs_ID": wbs_id, "needBy": "2026-10-01"}])
s, l12 = call(f"/workflow/ResourceRequestLines?$filter=parent_ID eq {rid12}"
              "&$select=ID,lineNo,qty")
line12 = l12["value"][0]
key12 = f"ID={line12['ID']},IsActiveEntity=true"

# While it is being written, it is being written. The rule must not reach here.
check(200, "a line on a draft request takes an edit", *call(
    f"/workflow/ResourceRequestLines({key12})", method="PATCH", body={"qty": 3}))

check(200, "submitted", *rr_action(rid12, "submit"))
check(403, "and then the same edit is refused", *call(
    f"/workflow/ResourceRequestLines({key12})", method="PATCH", body={"qty": 30}))
check(403, "as is deleting the line out from under it", *call(
    f"/workflow/ResourceRequestLines({key12})", method="DELETE"))

# Guarding the lines alone was worth exactly one call to get around: put the
# request back to Draft and they are editable again. Forward is refused too --
# a status nobody can write is the only kind the chain can rely on.
head12 = f"ID={rid12},IsActiveEntity=true"
check(403, "the status cannot be written back to Draft", *call(
    f"/workflow/ResourceRequests({head12})", method="PATCH", body={"status": "Draft"}))
check(403, "nor forward past the steps that set it", *call(
    f"/workflow/ResourceRequests({head12})", method="PATCH", body={"status": "Reserved"}))
check(403, "and the header itself is closed to edits", *call(
    f"/workflow/ResourceRequests({head12})", method="PATCH",
    body={"needBy": "2027-01-01"}))

s, hdr12 = call(f"/workflow/ResourceRequests({head12})?$select=status")
assert_(hdr12.get("status") == "In Approval",
        "so it is still where submit left it",
        str(hdr12.get("status")))

s, after12 = call(f"/workflow/ResourceRequestLines({key12})"
                  "?$select=qty,estUnitCost,estTotal")
assert_(abs(float(after12["qty"]) - 3) < 0.001,
        "the quantity is the one the approval was given",
        str(after12["qty"]))
# The check that would have caught this in the first place: a stored total and
# a quantity that no longer agree is the shape of the defect, not the refusal.
assert_(abs(float(after12["estTotal"])
            - float(after12["estUnitCost"]) * float(after12["qty"])) < 0.01,
        "and the value still describes that quantity",
        f"{after12['estTotal']} vs {float(after12['estUnitCost']) * float(after12['qty']):.2f}")

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
