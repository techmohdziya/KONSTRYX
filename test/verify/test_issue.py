"""Material leaving a store and becoming project cost.

A reservation locked the money and nothing spent it. Material could be
reserved, encumbered and reported on for the life of a project without a unit
ever being drawn, and the budget went on holding the full amount against work
already built. This is the missing half:

    pull request   the site asks a store for stock the reservation covers
    goods issue    ERP moves it, and that movement is the cost
    site receipt   the site counts what actually arrived
    consumption    what the work used, against the norm it should have used
    closure        what it consumed of what it locked, and what goes back

Cost is the goods issue and nothing else. A goods issue debits the project in
ERP, so charging it again at consumption would pay for the same concrete
twice — which is why consumption here carries quantities and no money at all.

The norm is the other thing worth pinning. A norm is not a property of the
material: the master keys it by material AND cost node, and the same ready-mix
is allowed 2.5% waste in a slab and 3% in a core wall because the pour is a
different job. Two lines of one request, same material, two cost nodes, and
the two must resolve differently.
"""
import json, urllib.request, base64, sys
from decimal import Decimal

BASE = "http://localhost:8090/odata/v4"
USER = "admin"          # raises the request, decides it, and draws against it


def call(path, user=USER, method="GET", body=None):
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


def assert_(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{('  — ' + str(detail)[:120]) if detail else ''}")
    results.append(bool(ok))
    return ok


def same(label, actual, expected):
    ok = actual is not None and Decimal(str(actual)) == Decimal(str(expected))
    print(f"  {'ok  ' if ok else 'FAIL'} {label} = {expected}"
          f"{'' if ok else '  (got ' + str(actual) + ')'}")
    results.append(ok)
    return ok


def head(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


def rows(path):
    st, body = call(path)
    return body.get("value", []) if st == 200 and isinstance(body, dict) else []


# ------------------------------------------------------------------ fixtures
project = rows("/project/Projects?$filter=IsActiveEntity eq true and code eq 'PRJ-001'"
               "&$select=ID,company_ID")
if not project:
    print("  PRJ-001 is not seeded; nothing to draw against")
    sys.exit(0)
project = project[0]

wbs = rows(f"/project/WBS?$filter=project_ID eq {project['ID']}&$select=ID,code&$top=1")[0]

cbs = {c["code"]: c for c in
       rows(f"/project/CBS?$filter=project_ID eq {project['ID']}&$select=ID,code,name")}
slab = cbs.get("02.30")        # Slabs — norm allows 2.5%
wall = cbs.get("02.40")        # Core & shear walls — norm allows 3%
if not (slab and wall):
    print("  the slab and core-wall cost nodes are not seeded; nothing to measure against")
    sys.exit(0)

rmc = rows("/masterdata/Resources?$filter=IsActiveEntity eq true "
           "and code eq 'MAT-CON-RMC-M40-001'&$select=ID,code")
if not rmc:
    print("  the ready-mix material is not seeded")
    sys.exit(0)
rmc = rmc[0]

rate = rows("/masterdata/Rates?$filter=IsActiveEntity eq true "
            f"and resource_ID eq {rmc['ID']}&$select=rateValue,basis")[0]
unit_rate = Decimal(str(rate["rateValue"]))
print(f"  fixtures: {rmc['code']} at {unit_rate}/{rate['basis']}, "
      f"charged to {slab['code']} ({slab['name']}) and {wall['code']} ({wall['name']})")


def rr_action(rid, action, body=None):
    return call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)"
                f"/WorkflowService.{action}", method="POST", body=body or {})


def stock_issued_now():
    """What the project reports as material cost at this moment.

    Taken as a baseline rather than assumed to be zero: PRJ-001 already carries
    a seeded material reservation with cost against it, and asserting the total
    would be asserting the fixture. What this suite is responsible for is the
    change, so the change is what gets measured.
    """
    call(f"/project/Projects(ID={project['ID']},IsActiveEntity=true)"
         "/ProjectService.reconcile", method="POST", body={})
    found = rows("/project/PeriodReports?$filter=project_ID eq "
                 f"{project['ID']}&$select=stockIssuedCost&$orderby=takenAt desc&$top=1")
    return Decimal(str(found[0]["stockIssuedCost"] or 0)) if found else Decimal("0")


baseline_stock = stock_issued_now()
print(f"  baseline: the project already reports {baseline_stock} of material cost")


head("1. A material request, decided in house — the stock is already ours")
st, draft = call("/workflow/ResourceRequests", method="POST", body={
    "verticalType": "MR", "project_ID": project["ID"],
    "company_ID": project["company_ID"], "wbs_ID": wbs["ID"],
    "needBy": "2026-10-01", "raisedBy": USER, "raisedOn": "2026-08-20"})
rid = draft["ID"]
for lineNo, node, qty in ((1, slab, 60), (2, wall, 25)):
    call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=false)/lines",
         method="POST", body={
             "lineNo": lineNo, "resource_ID": rmc["ID"],
             "description": f"Ready-mix M40 — {node['name']}",
             "qty": qty, "uom": "m3", "wbs_ID": wbs["ID"], "cbs_ID": node["ID"],
             "needBy": "2026-10-01"})
st, act = call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=false)"
               "/WorkflowService.draftActivate", method="POST", body={})
docno = act.get("docNo") if isinstance(act, dict) else None
assert_(docno and docno.startswith("RR-"), "the request drew a number", docno)

check(200, "submitted", *rr_action(rid, "submit"))
inst = rows(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{docno}'"
            "&$select=ID&$expand=steps($select=ID,stepNo;$orderby=stepNo)")
steps = inst[0]["steps"] if inst else []
for step in steps:
    call(f"/collaboration/ApprovalSteps({step['ID']})/CollaborationService.approve",
         method="POST", body={"comment": "Stock covers it."},
         user="daud" if step is steps[-1] and len(steps) > 1 else "demo")

for lineNo in (1, 2):
    check(200, f"line {lineNo} in house", *rr_action(rid, "decideLine", {
        "lineNo": lineNo, "decision": "IN_HOUSE",
        "rationale": "Batching plant on site; stock covers the pour."}))
check(200, "availability checked", *rr_action(rid, "runAvailabilityCheck"))
check(200, "reserved", *rr_action(rid, "createReservation"))

res = rows(f"/workflow/Reservations?$filter=rr_ID eq {rid}&$select=ID,docNo,status")[0]
lines = rows(f"/workflow/ReservationLines?$filter=reservation_ID eq {res['ID']}"
             "&$select=ID,qty,uom,dailyRate,encumberedAmount,consumedToDate,"
             "costToDate,burnPct,lineStatus,rrLine_ID")
rr_lines = {l["ID"]: l for l in rows(f"/workflow/ResourceRequestLines?$filter=parent_ID eq {rid}"
                                     "&$select=ID,lineNo,cbs_ID")}
for line in lines:
    line["cbs_ID"] = rr_lines[line["rrLine_ID"]]["cbs_ID"]
    line["lineNo"] = rr_lines[line["rrLine_ID"]]["lineNo"]
lines.sort(key=lambda l: l["lineNo"])
slab_line, wall_line = lines[0], lines[1]
for line in lines:
    print(f"      line {line['lineNo']}: {line['qty']} {line['uom']} @ "
          f"{line['dailyRate']} = {line['encumberedAmount']} [{line['lineStatus']}]")
assert_(len(lines) == 2, "both in-house lines were reserved")
same("the slab line encumbers 60 m3 at the rate master's price",
     slab_line["encumberedAmount"], (Decimal("60") * unit_rate).quantize(Decimal("0.01")))
same("nothing is spent before anything is drawn", slab_line["costToDate"], 0)

head("2. A pull request cannot draw more than the reservation holds")
check(409, "asking for more than is reserved", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.raisePullRequest",
    method="POST", body={"lineNo": 1, "qty": 500, "storageLoc": "1710"}))
check(400, "asking for nothing", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.raisePullRequest",
    method="POST", body={"lineNo": 1, "qty": 0, "storageLoc": "1710"}))

# Both lines carry the same material, so naming it says nothing about which
# one. This is the case that charged the core wall's concrete to the slab.
ambiguous = check(400, "two lines of one material need the line named", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.raisePullRequest",
    method="POST", body={"resourceCode": rmc["code"], "qty": 10, "storageLoc": "1710"}))
assert_(slab["code"] in str(ambiguous) and wall["code"] in str(ambiguous),
        "and the refusal names both cost nodes so the choice can be made",
        str(ambiguous)[:150])
check(404, "a line number that is not on the reservation", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.raisePullRequest",
    method="POST", body={"lineNo": 9, "qty": 10}))
check(400, "a line number and a material that disagree", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.raisePullRequest",
    method="POST", body={"lineNo": 1, "resourceCode": "MT-REB-16", "qty": 10}))

head("3. Drawing 40 of the 60 m3 reserved for the slabs")
msg = check(200, "raised", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.raisePullRequest",
    method="POST", body={"lineNo": 1, "qty": 40, "storageLoc": "1710"}))

pulls = rows(f"/material/PullRequests?$filter=reservationLine_ID eq {slab_line['ID']}"
             "&$select=ID,docNo,status,qtyRequested,qtyIssued,issuedValue,storageLoc,"
             "projectCode,reservationNo,resourceCode,statusCriticality")
assert_(len(pulls) >= 1, "the pull request exists")
pull = pulls[0]
assert_(pull["docNo"].startswith("PL-"), "it drew a KONSTRYX number", pull["docNo"])
assert_(pull["status"] == "Raised", "it starts raised, not issued", pull["status"])
same("nothing has been issued yet", pull["qtyIssued"], 0)
assert_(pull["reservationNo"] == res["docNo"],
        "the list names the reservation behind it", pull["reservationNo"])
assert_(pull["projectCode"] == "PRJ-001", "and the project", pull["projectCode"])

after = rows(f"/workflow/ReservationLines?$filter=ID eq {slab_line['ID']}"
             "&$select=lineStatus,costToDate")[0]
assert_(after["lineStatus"] == "Issuing", "the line is now issuing", after["lineStatus"])
same("asking for stock is not spending", after["costToDate"], 0)

pull_id = f"ID={pull['ID']},IsActiveEntity=true"


def pull_action(action, body):
    return call(f"/material/PullRequests({pull['ID']})/MaterialService.{action}",
                method="POST", body=body)


head("4. A site receipt before anything is issued is refused")
check(409, "confirming an unissued draw", *pull_action("confirmSiteReceipt", {
    "receivedQty": 40, "receivedBy": "Site store", "receivedOn": "2026-09-02"}))

head("5. ERP issues 40 m3, and that movement is the cost")
check(400, "an issue of nothing", *pull_action("recordGoodsIssue", {
    "giDoc": "4900000001", "giDate": "2026-09-01", "giQty": 0, "s4System": "TEST"}))
check(400, "more issued than asked for", *pull_action("recordGoodsIssue", {
    "giDoc": "4900000001", "giDate": "2026-09-01", "giQty": 90, "s4System": "TEST"}))
check(400, "neither a document nor a reason", *pull_action("recordGoodsIssue", {
    "giDoc": "", "giDate": "2026-09-01", "giQty": 40, "s4System": "TEST"}))

issue_msg = check(200, "issued", *pull_action("recordGoodsIssue", {
    "giDoc": "4900000001", "giDate": "2026-09-01", "giQty": 40,
    "s4System": "TEST", "message": ""}))
check(409, "recording the same issue twice", *pull_action("recordGoodsIssue", {
    "giDoc": "4900000002", "giDate": "2026-09-02", "giQty": 5, "s4System": "TEST"}))

issued_value = (Decimal("40") * unit_rate).quantize(Decimal("0.01"))
pull = rows(f"/material/PullRequests?$filter=ID eq {pull['ID']}"
            "&$select=ID,docNo,status,qtyIssued,issuedValue,s4GIDoc,s4System,"
            "statusCriticality")[0]
same("the issue is priced at the rate the line was encumbered at",
     pull["issuedValue"], issued_value)
assert_(pull["status"] == "Issued", "the pull request reads issued", pull["status"])
assert_(pull["s4GIDoc"] == "4900000001", "and names ERP's movement", pull["s4GIDoc"])

after = rows(f"/workflow/ReservationLines?$filter=ID eq {slab_line['ID']}"
             "&$select=consumedToDate,costToDate,burnPct,drift,lineStatus")[0]
same("cost to date is the goods issue", after["costToDate"], issued_value)
same("consumed to date is what left the store", after["consumedToDate"], 40)
expected_burn = (issued_value * 100 / Decimal(str(slab_line["encumberedAmount"]))
                 ).quantize(Decimal("0.01"))
same("burn is that against the encumbrance", after["burnPct"], expected_burn)
same("no drift — the issue was priced at the reserved rate", after["drift"], 0)
assert_(after["lineStatus"] == "Consuming", "the line is consuming", after["lineStatus"])

head("6. A refused draw, revived, still cannot spend past the reservation")
# The raise skips refusals when it counts what is asked for, because a draw ERP
# would not move is not spoken for. That leaves a way round: ask for the rest of
# the line, be refused, ask again, then have the first refusal revived. The gate
# on the movement is what closes it, and it is the one that matters — that is
# where the cost is written.
check(200, "a second draw for the remaining 20", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.raisePullRequest",
    method="POST", body={"lineNo": 1, "qty": 20, "storageLoc": "1710"}))
spare = [p for p in rows(f"/material/PullRequests?$filter=reservationLine_ID eq "
                         f"{slab_line['ID']}&$select=ID,docNo,status,qtyRequested")
         if p["status"] == "Raised"]
assert_(len(spare) == 1, "one draw still waiting on a movement")
check(200, "ERP refuses it", *call(
    f"/material/PullRequests({spare[0]['ID']})/MaterialService.recordGoodsIssue",
    method="POST", body={"giDoc": "", "giDate": "2026-09-03", "giQty": 0,
                         "s4System": "TEST", "message": "Batching plant down."}))
refused = rows(f"/material/PullRequests?$filter=ID eq {spare[0]['ID']}"
               "&$select=status,syncMessage,statusCriticality")[0]
assert_(refused["status"] == "Refused", "the refusal is on the document",
        refused["syncMessage"])
assert_(refused["statusCriticality"] == 1, "and reads red", refused["statusCriticality"])

check(200, "so the 20 can be asked for again", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.raisePullRequest",
    method="POST", body={"lineNo": 1, "qty": 20, "storageLoc": "1710"}))
again = [p for p in rows(f"/material/PullRequests?$filter=reservationLine_ID eq "
                         f"{slab_line['ID']}&$select=ID,docNo,status")
         if p["status"] == "Raised"]
check(200, "and issued", *call(
    f"/material/PullRequests({again[0]['ID']})/MaterialService.recordGoodsIssue",
    method="POST", body={"giDoc": "4900000005", "giDate": "2026-09-03",
                         "giQty": 20, "s4System": "TEST"}))
# Now the revived refusal: the line is fully drawn, so this must not go through.
check(409, "the revived refusal cannot spend past the reservation", *call(
    f"/material/PullRequests({spare[0]['ID']})/MaterialService.recordGoodsIssue",
    method="POST", body={"giDoc": "4900000006", "giDate": "2026-09-04",
                         "giQty": 20, "s4System": "TEST"}))

head("6a. The line has nothing left, and no more")
check(409, "drawing more than the line still holds", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.raisePullRequest",
    method="POST", body={"lineNo": 1, "qty": 25}))

# What the two lines end up having drawn, named once so the closure and the cost
# report are checked against the same arithmetic rather than against each other.
SLAB_ISSUED = (Decimal("60") * unit_rate).quantize(Decimal("0.01"))
WALL_ISSUED = (Decimal("20") * unit_rate).quantize(Decimal("0.01"))

head("7. The site counts what arrived — 38 of the 40 issued")
check(400, "confirming nothing", *pull_action("confirmSiteReceipt", {
    "receivedQty": 0, "receivedBy": "Site store", "receivedOn": "2026-09-02"}))
check(409, "confirming more than left the store", *pull_action("confirmSiteReceipt", {
    "receivedQty": 45, "receivedBy": "Site store", "receivedOn": "2026-09-02"}))
short_msg = check(200, "confirmed short", *pull_action("confirmSiteReceipt", {
    "receivedQty": 38, "receivedBy": "K. Fernandes — Site store",
    "receivedOn": "2026-09-02", "note": "Two loads rejected at the gate — slump."}))

receipts = rows(f"/material/SiteReceipts?$filter=pullRequest_ID eq {pull['ID']}"
                "&$select=receivedQty,shortQty,note,receivedBy,pullRequestNo,"
                "shortCriticality")
assert_(len(receipts) == 1, "one confirmation on file")
same("38 received", receipts[0]["receivedQty"], 38)
same("2 still unaccounted for", receipts[0]["shortQty"], 2)
assert_(receipts[0]["shortCriticality"] == 2,
        "a short delivery is flagged, not silent", receipts[0]["shortCriticality"])
assert_(receipts[0]["pullRequestNo"] == pull["docNo"],
        "the receipt names its pull request", receipts[0]["pullRequestNo"])

state = rows(f"/material/PullRequests?$filter=ID eq {pull['ID']}"
             "&$select=status,statusCriticality")[0]
assert_(state["status"] == "Part received",
        "part received, because 2 m3 never turned up", state["status"])

check(200, "the rest arrives later", *pull_action("confirmSiteReceipt", {
    "receivedQty": 2, "receivedBy": "K. Fernandes — Site store",
    "receivedOn": "2026-09-03", "note": "Replacement load."}))
state = rows(f"/material/PullRequests?$filter=ID eq {pull['ID']}"
             "&$select=status,statusCriticality")[0]
assert_(state["status"] == "Confirmed", "now confirmed in full", state["status"])
assert_(state["statusCriticality"] == 3, "and reads as settled", state["statusCriticality"])

head("8. Consumption is measured against the norm for THIS cost node")


def consume(body):
    return call("/material/recordConsumption", method="POST", body=body)


check(409, "using more than was issued", *consume({
    "reservationNo": res["docNo"], "lineNo": 1,
    "recordDate": "2026-09-04", "diaryOutputQty": 100, "actualQty": 100}))
check(400, "a day with no output", *consume({
    "reservationNo": res["docNo"], "lineNo": 1,
    "recordDate": "2026-09-04", "diaryOutputQty": 0, "actualQty": 10}))
check(404, "a reservation that does not exist", *consume({
    "reservationNo": "RES-9999-9999", "lineNo": 1,
    "recordDate": "2026-09-04", "diaryOutputQty": 10, "actualQty": 10}))

# 36 m3 placed, and 38 used. The slab norm is 1 m3 per m3 placed with 2.5%
# allowed, so 36 m3 of pour may consume 36.9 — and 38 is over it.
cons_msg = check(200, "recorded", *consume({
    "reservationNo": res["docNo"], "lineNo": 1,
    "recordDate": "2026-09-04", "diaryOutputQty": 36, "actualQty": 38,
    "note": "Slab pour L14 — two part loads."}))

record = rows(f"/material/ConsumptionRecords?$filter=reservationLine_ID eq {slab_line['ID']}"
              "&$select=theoreticalQty,wastageAllowance,actualQty,variance,variancePct,"
              "rateApplied,result,reservationNo,resourceCode,varianceCriticality")[0]
same("theoretical is the output at the norm", record["theoreticalQty"], 36)
same("the slab node allows 2.5%", record["wastageAllowance"], "0.900")
same("38 used against 36.9 allowed", record["variance"], "1.100")
assert_(record["result"] == "Over allowance", "and it says so", record["result"])
assert_(record["varianceCriticality"] == 1, "an overrun is red", record["varianceCriticality"])
same("the norm it was measured against is kept", record["rateApplied"], 1)

head("9. The same material on the core wall resolves the OTHER norm")
check(200, "drawn against the wall line", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.raisePullRequest",
    method="POST", body={"lineNo": 2, "qty": 20, "storageLoc": "1710"}))
wall_pulls = [p for p in rows(f"/material/PullRequests?$filter=reservationLine_ID eq "
                              f"{wall_line['ID']}&$select=ID,docNo")]
assert_(len(wall_pulls) == 1, "one draw against the wall line")
check(200, "issued", *call(
    f"/material/PullRequests({wall_pulls[0]['ID']})/MaterialService.recordGoodsIssue",
    method="POST", body={"giDoc": "4900000010", "giDate": "2026-09-05",
                         "giQty": 20, "s4System": "TEST"}))
check(200, "consumed", *consume({
    "reservationNo": res["docNo"], "lineNo": 2,
    "recordDate": "2026-09-06", "diaryOutputQty": 20, "actualQty": 20,
    "note": "Core wall lift 14."}))

wall_record = rows(f"/material/ConsumptionRecords?$filter=reservationLine_ID eq "
                   f"{wall_line['ID']}&$select=wastageAllowance,variance,result")[0]
same("the core wall allows 3%, not the slab's 2.5%", wall_record["wastageAllowance"], "0.600")
assert_(wall_record["result"] == "Within allowance",
        "20 of 20.6 allowed is within it", wall_record["result"])

head("10. The project's cost report calls it material, not manpower")
check(200, "reconciled", *call(
    f"/project/Projects(ID={project['ID']},IsActiveEntity=true)/ProjectService.reconcile",
    method="POST", body={}))
report = rows("/project/PeriodReports?$filter=project_ID eq "
              f"{project['ID']}&$select=costToDate,signedLabourCost,stockIssuedCost,"
              "note&$orderby=takenAt desc&$top=1")
if report:
    report = report[0]
    stock = Decimal(str(report["stockIssuedCost"] or 0))
    # 60 m3 into the slabs, in two draws, and 20 into the core wall.
    expected_stock = (SLAB_ISSUED + WALL_ISSUED).quantize(Decimal("0.01"))
    same("material cost rose by exactly the two goods issues",
         stock - baseline_stock, expected_stock)
    same("and cost to date carries it", Decimal(str(report["costToDate"] or 0))
         - Decimal(str(report["signedLabourCost"] or 0)), stock)
    note = str(report.get("note") or "")
    uncaptured = note.split(";")[-1] if ";" in note else ""
    assert_("material" not in uncaptured,
            "material is no longer listed as contributing nothing",
            uncaptured[:110] or "(no coverage caveat)")
else:
    assert_(False, "the project produced a period report")

head("11. Closing the reservation gives back what it never spent")
close_msg = check(200, "closed", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.close",
    method="POST", body={}))

closure = rows(f"/material/ReservationClosures?$filter=reservation_ID eq {res['ID']}"
               "&$select=finalActual,theoretical,variance,releasedAmount,result,"
               "reservationNo,projectCode,resultCriticality")
assert_(len(closure) == 1, "one closing account")
closure = closure[0]
same("58 m3 consumed across the two lines", closure["finalActual"], 58)
# Slab: 36 + 0.9 allowed. Wall: 20 + 0.6.
same("against an allowance of 57.5", closure["theoretical"], "57.500")
# Released per line, not on the totals: the slab line drew every cubic metre it
# reserved and gives back nothing, and only the core wall's 20 of 25 releases.
# Netting them would hand back money the slab line has already spent.
slab_back = max(Decimal(str(slab_line["encumberedAmount"])) - SLAB_ISSUED, Decimal("0"))
wall_back = max(Decimal(str(wall_line["encumberedAmount"])) - WALL_ISSUED, Decimal("0"))
same("the unspent encumbrance goes back, line by line",
     closure["releasedAmount"], (slab_back + wall_back).quantize(Decimal("0.01")))
assert_(closure["result"] == "Underrun",
        "it locked more than it spent", closure["result"])
assert_(closure["reservationNo"] == res["docNo"],
        "the closure names its reservation", closure["reservationNo"])

check(409, "closing twice", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.close",
    method="POST", body={}))
check(409, "drawing against a closed reservation", *call(
    f"/workflow/Reservations({res['ID']})/WorkflowService.raisePullRequest",
    method="POST", body={"lineNo": 1, "qty": 1}))

head("12. The chain records every step of it")
links = rows(f"/workflow/DocumentLinks?$filter=fromDoc eq '{res['docNo']}'"
             "&$select=toDoc,linkType")
assert_(any(l["linkType"] == "PULL" for l in links),
        "the reservation shows what was drawn from it",
        ", ".join(f"{l['linkType']}->{l['toDoc']}" for l in links))
gi_links = rows(f"/workflow/DocumentLinks?$filter=fromDoc eq '{pull['docNo']}'"
                "&$select=toDoc,linkType")
assert_(any(l["linkType"] == "GOODS ISSUE" and l["toDoc"] == "4900000001"
            for l in gi_links),
        "and the pull request shows ERP's movement",
        ", ".join(f"{l['linkType']}->{l['toDoc']}" for l in gi_links))

print()
print(f"  {sum(results)} of {len(results)} checks passed")
sys.exit(0 if all(results) else 1)
