"""The PROCURE half of the advisory split: raising a purchase requisition.

createReservation consumes the IN_HOUSE lines; until raisePurchaseRequisition
existed, a PROCURE line stopped at "Advised" and nothing picked it up. The
requisition is deliberately NOT a KONSTRYX document — S/4 owns its number — so
these checks assert what it must NOT have (a docNo, a KONSTRYX number range) as
carefully as what it must."""
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
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{(': ' + str(detail)) if detail != '' else ''}")
    results.append(bool(ok))


def head(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


# ------------------------------------------------------------------- fixtures
# PRJ-002 with a real budget, because the point of this suite's last section is
# that an order commits against a budget line. Charging a CBS that no budget
# line covers would let the commitment checks pass by never running.
BILL = """itemNo;code;description;qty;uom;rate
2.01;CONC-C40;Ready-mix C40 to raft;1200;m3;385.00
"""

s, ps = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'PRJ-002'"
             "&$select=ID,company_ID")
project = ps["value"][0]
pid = project["ID"]

call(f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.instantiateCBS",
     method="POST", body={})
s, cbs = call(f"/project/CBS?$filter=project_ID eq {pid}&$select=ID,code,libraryNode_ID")
slab = [c for c in cbs["value"] if c["code"] == "02.10"][0]

call(f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.draftEdit",
     method="POST", body={"PreserveChanges": True})
call(f"/project/Projects(ID={pid},IsActiveEntity=false)/wbsElements",
     method="POST", body={"code": "PRJ-002.1", "description": "Substructure"})
call(f"/project/Projects(ID={pid},IsActiveEntity=false)/ProjectService.draftActivate",
     method="POST", body={})
s, wbs = call(f"/project/WBS?$filter=project_ID eq {pid}&$select=ID&$top=1")
wbs_id = wbs["value"][0]["ID"]

s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'MT-RMC-C40-20'"
              "&$select=ID")
concrete = res["value"][0]["ID"]
s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-VIB-KIT'"
              "&$select=ID")
vibro = res["value"][0]["ID"]
s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-TWC-12T'"
              "&$select=ID")
crane = res["value"][0]["ID"]


def make_master(entity, body, user="steward_infc"):
    s, d = call(f"/masterdata/{entity}", method="POST", body=body, user=user)
    if s != 201:
        return s, d
    return call(f"/masterdata/{entity}(ID={d['ID']},IsActiveEntity=false)"
                "/MasterDataService.draftActivate", method="POST", body={}, user=user)


# A priced build-up on the slab CBS, so a budget can generate lines for it.
s, d = call("/project/BOQs", method="POST", body={
    "boqId": "BOQ-PROC", "project_ID": pid, "version": "A", "status": "Draft"})
boq_id = d["ID"]
call(f"/project/BOQs(ID={boq_id},IsActiveEntity=false)/ProjectService.draftActivate",
     method="POST", body={})
call(f"/project/BOQs(ID={boq_id},IsActiveEntity=true)/ProjectService.importItems",
     method="POST", body={"fileName": "bill.csv", "content": BILL})
s, items = call(f"/project/BOQItems?$filter=boq_ID eq {boq_id}&$select=ID,itemNo")
call(f"/project/BOQItems(ID={items['value'][0]['ID']},IsActiveEntity=true)",
     method="PATCH", body={"cbs_ID": slab["ID"]})
make_master("ConsumptionRates", {
    "material_ID": concrete, "linkedCBS_ID": slab["libraryNode_ID"],
    "consRate": 1.0, "consUoM": "m3", "wastageAllowancePct": 2.5,
    "effectiveFrom": "2026-01-01", "scope": "GROUP"})
make_master("ProductivityRates", {
    "resource_ID": vibro, "linkedCBS_ID": slab["libraryNode_ID"],
    "outputPerHr": 12, "outputUoM": "m3", "effectiveFrom": "2026-01-01", "scope": "GROUP"})
make_master("Rates", {"resource_ID": concrete, "rateValue": 285.00, "basis": "m3",
                      "ccy_code": "AED", "effectiveFrom": "2026-01-01", "scope": "GROUP"})
call(f"/project/BOQs(ID={boq_id},IsActiveEntity=true)/ProjectService.generateBuildUp",
     method="POST", body={"difficultyPct": 110})
call(f"/project/BOQItems(ID={items['value'][0]['ID']},IsActiveEntity=true)"
     "/ProjectService.allocate", method="POST",
     body={"wbsCode": "PRJ-002.1", "cbsCode": "02.10", "qty": 1200})

s, d = call("/budget/Budgets", method="POST", body={
    "project_ID": pid, "company_ID": project["company_ID"], "version": "V1",
    "raisedBy": "demo", "raisedOn": "2026-08-17"})
budget_id = d["ID"]
call(f"/budget/Budgets(ID={budget_id},IsActiveEntity=false)/BudgetService.draftActivate",
     method="POST", body={})
s, gen = call(f"/budget/Budgets(ID={budget_id},IsActiveEntity=true)"
              "/BudgetService.generateLines", method="POST", body={})
print(f"  fixtures ready on PRJ-002 with a budget: {str(gen)[:80]}")


def new_request(lines):
    s, d = call("/workflow/ResourceRequests", method="POST", body={
        "verticalType": "EQR", "project_ID": project["ID"],
        "company_ID": project["company_ID"], "wbs_ID": wbs_id,
        "needBy": "2026-10-01", "raisedBy": "demo", "raisedOn": "2026-08-17"})
    rid = d["ID"]
    for i, line in enumerate(lines, start=1):
        line = dict(line)
        line["lineNo"] = i
        call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=false)/lines",
             method="POST", body=line)
    s, act = call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=false)"
                  "/WorkflowService.draftActivate", method="POST", body={})
    return rid, (act.get("docNo") if isinstance(act, dict) else None)


def rr_action(rid, action, body=None):
    return call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)"
                f"/WorkflowService.{action}", method="POST", body=body or {})


def approve(docno):
    s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{docno}'"
                   "&$select=ID&$expand=steps($select=ID,stepNo;$orderby=stepNo)")
    users = ["demo", "daud", "admin"]
    for i, st in enumerate(inst["value"][0]["steps"]):
        call(f"/collaboration/ApprovalSteps({st['ID']})/CollaborationService.approve",
             method="POST", body={"comment": "ok"}, user=users[i])


head("1. A requisition cannot be raised before the lines are decided")
rid, docno = new_request([
    {"resource_ID": crane, "description": "Tower crane", "qty": 1, "uom": "inst",
     "wbs_ID": wbs_id, "cbs_ID": slab["ID"], "needBy": "2026-10-01"},
    {"resource_ID": vibro, "description": "Vibrator kits", "qty": 4, "uom": "kit",
     "wbs_ID": wbs_id, "cbs_ID": slab["ID"], "needBy": "2026-09-15"},
])
print(f"      created {docno}")
check(409, "requisition on a Draft request", *rr_action(rid, "raisePurchaseRequisition"))
check(200, "submitted", *rr_action(rid, "submit"))
check(409, "requisition while still In Approval",
      *rr_action(rid, "raisePurchaseRequisition"))
approve(docno)

head("2. With every line IN_HOUSE there is nothing to procure")
check(200, "line 1 in-house", *rr_action(rid, "decideLine",
    {"lineNo": 1, "decision": "IN_HOUSE", "rationale": "Fleet crane available."}))
check(200, "line 2 in-house", *rr_action(rid, "decideLine",
    {"lineNo": 2, "decision": "IN_HOUSE", "rationale": "Yard has kits."}))
check(400, "requisition with no PROCURE line",
      *rr_action(rid, "raisePurchaseRequisition"))

head("3. The PROCURE lines raise a requisition — and only those lines")
rid2, docno2 = new_request([
    {"resource_ID": crane, "description": "Tower crane", "qty": 1, "uom": "inst",
     "wbs_ID": wbs_id, "cbs_ID": slab["ID"], "needBy": "2026-10-01"},
    {"resource_ID": vibro, "description": "Vibrator kits", "qty": 4, "uom": "kit",
     "wbs_ID": wbs_id, "cbs_ID": slab["ID"], "needBy": "2026-09-15"},
])
print(f"      created {docno2}")
rr_action(rid2, "submit")
approve(docno2)
check(200, "line 1 stays in-house", *rr_action(rid2, "decideLine",
    {"lineNo": 1, "decision": "IN_HOUSE", "rationale": "Fleet crane available."}))
check(200, "line 2 goes to procurement", *rr_action(rid2, "decideLine",
    {"lineNo": 2, "decision": "PROCURE", "rationale": "No kits free until November."}))

msg = check(200, "requisition raised", *rr_action(rid2, "raisePurchaseRequisition"))
check(409, "raising it twice", *rr_action(rid2, "raisePurchaseRequisition"))

s, prs = call(f"/material/PurchaseRequisitions?$filter=sourceRequest_ID eq {rid2}"
              "&$select=ID,prNo,status,syncStatus,project_ID,company_ID,raisedBy")
assert_(len(prs["value"]) == 1, "exactly one requisition exists for the request",
        len(prs["value"]))
pr = prs["value"][0]
print(f"        PR {pr['ID'][:8]}… status={pr['status']} sync={pr['syncStatus']}")

head("4. It is S/4's document, not ours")
assert_(pr.get("prNo") in (None, ""),
        "no requisition number was issued locally — S/4 assigns prNo", repr(pr.get("prNo")))
assert_("docNo" not in pr or pr.get("docNo") in (None, ""),
        "the requisition carries no KONSTRYX document number")
assert_(pr.get("syncStatus") == "NOT_SENT",
        "it starts NOT_SENT, so an unsent requisition cannot read as a good one",
        pr.get("syncStatus"))
assert_(pr.get("project_ID") == project["ID"] and pr.get("company_ID") == project["company_ID"],
        "project and company are carried for scoping without a join")

# The number range must not have been touched: no PR object is configured, and
# nothing should have quietly invented one. Assert the read worked before
# trusting its emptiness — an unauthorized or malformed query returns nothing
# too, and would pass this check without proving anything.
s, ranges = call("/authorization/NumberRangeObjects?$select=code", user="admin")
codes = {r["code"] for r in ranges["value"]} if s == 200 else None
assert_(codes is not None and len(codes) > 0,
        "the number-range catalogue is readable, so its contents mean something",
        f"[{s}] {sorted(codes) if codes else ranges}")
assert_(codes is not None and "PR" not in codes,
        "no PR number range exists or was created", sorted(codes or []))

head("5. Only the procured line travels, with its account assignment")
s, prLines = call(f"/material/PurchaseRequisitionLines?$filter=parent_ID eq {pr['ID']}"
                  "&$select=ID,lineNo,qtyProcure,uom,estUnitPrice,estTotal,description,"
                  "wbs_ID,cbs_ID,sourceLine_ID,resource_ID,material_ID,status&$orderby=lineNo")
lines = prLines["value"]
assert_(len(lines) == 1, "one line requisitioned, not both", len(lines))
line = lines[0]
print(f"        line {line['lineNo']}: {line['description']} "
      f"{line['qtyProcure']} {line['uom']} @ {line['estUnitPrice']} = {line['estTotal']}")
assert_(line.get("resource_ID") == vibro,
        "the requisitioned line is the vibrator kits, not the crane")
assert_(float(line.get("qtyProcure") or 0) == 4.0,
        "quantity carried from the request line", line.get("qtyProcure"))
assert_(line.get("wbs_ID") == wbs_id,
        "WBS travels — without it the commitment has no budget line to land on")
assert_(line.get("sourceLine_ID"), "the line points back at the request line it came from")
assert_(float(line.get("estTotal") or 0) > 0,
        "the approved value travels, not a fresh price", line.get("estTotal"))
assert_(line.get("material_ID") is None,
        "no material is claimed for a resource that has none registered — the "
        "vibrator kits are hired, and an invented number would push a real order",
        line.get("material_ID"))

s, rrLines = call(f"/workflow/ResourceRequestLines?$filter=parent_ID eq {rid2}"
                  "&$select=lineNo,lineStatus&$orderby=lineNo")
by_no = {l["lineNo"]: l["lineStatus"] for l in rrLines["value"]}
assert_(by_no.get(2) == "Requisitioned",
        "the procured request line reads Requisitioned", by_no.get(2))
assert_(by_no.get(1) != "Requisitioned",
        "the in-house line was left alone for the fleet to reserve", by_no.get(1))

head("6. The chain still reads end to end")
s, links = call(f"/workflow/DocumentLinks?$filter=fromDoc eq '{docno2}'"
                "&$select=fromDoc,toDoc,linkType")
types = {l["linkType"] for l in links.get("value", [])} if isinstance(links, dict) else set()
assert_("REQUISITION" in types,
        "a REQUISITION link ties the request to the requisition", sorted(types))

# The in-house half must still work after the procured half was split off.
check(200, "availability still runs for the in-house line",
      *rr_action(rid2, "runAvailabilityCheck"))
check(200, "and the in-house line still reserves",
      *rr_action(rid2, "createReservation"))

head("7. S/4 returns the requisition number — it never came from us")
pr_path = f"/material/PurchaseRequisitions({pr['ID']})/MaterialService.recordRequisitionResult"
check(400, "accepted but with no number", *call(pr_path, method="POST",
      body={"success": True, "prNo": "", "s4System": "S4H", "message": "ok"}))
check(200, "S/4 issued 1000004711", *call(pr_path, method="POST", body={
      "success": True, "prNo": "1000004711", "s4System": "S4H",
      "message": "Created with reference to the request."}))
s, pr2 = call(f"/material/PurchaseRequisitions({pr['ID']})"
              "?$select=prNo,s4Key,syncStatus,status,syncAttempts")
assert_(pr2.get("prNo") == "1000004711" and pr2.get("s4Key") == "1000004711",
        "the number S/4 issued is the requisition's identity", pr2.get("prNo"))
assert_(pr2.get("syncStatus") == "SENT", "it reads SENT once accepted", pr2.get("syncStatus"))

head("8. A purchase order is mirrored, never created here")
s, prLines2 = call(f"/material/PurchaseRequisitionLines?$filter=parent_ID eq {pr['ID']}"
                   "&$select=lineNo,estTotal&$orderby=lineNo")
pr_line_no = prLines2["value"][0]["lineNo"]

po_body = {"requisitionId": pr["ID"], "poNo": "4500001234", "vendorBP": "0001000211",
           "s4System": "S4H", "orderedOn": "2026-08-18",
           "lines": [{"prLineNo": pr_line_no, "qty": 4, "netValue": 231.00,
                      "eta": "2026-09-20"}]}
check(400, "an order with no S/4 number", *call("/material/recordPurchaseOrder",
      method="POST", body=dict(po_body, poNo="")))
check(400, "an order referencing a requisition line that does not exist",
      *call("/material/recordPurchaseOrder", method="POST",
            body=dict(po_body, lines=[{"prLineNo": 99, "qty": 1, "netValue": 10}])))
check(200, "4500001234 mirrored", *call("/material/recordPurchaseOrder",
      method="POST", body=po_body))
check(409, "mirroring the same order twice", *call("/material/recordPurchaseOrder",
      method="POST", body=po_body))

s, pos = call(f"/material/PurchaseOrders?$filter=poNo eq '4500001234'"
              "&$select=ID,poNo,status,sourceRequisition_ID,project_ID,vendor_ID")
po = pos["value"][0]
assert_(po.get("sourceRequisition_ID") == pr["ID"],
        "the order points back at the requisition it was raised against")
assert_(po.get("vendor_ID"), "the S/4 business partner resolved to our vendor mirror")

s, poLines = call(f"/material/PurchaseOrderLines?$filter=parent_ID eq {po['ID']}"
                  "&$select=lineNo,netValue,cbs_ID,wbs_ID,sourcePRLine_ID,resource_ID")
poLine = poLines["value"][0]
assert_(poLine.get("cbs_ID") and poLine.get("cbs_ID") == line.get("cbs_ID"),
        "account assignment was inherited from the requisition, not restated")
assert_(poLine.get("sourcePRLine_ID") == line.get("ID"),
        "the order line points back at the requisition line")

s, prAfter = call(f"/material/PurchaseRequisitions({pr['ID']})?$select=status")
assert_(prAfter.get("status") == "Ordered",
        "the requisition reads Ordered once every line is on an order",
        prAfter.get("status"))

head("9. The order commits against the budget line it charges")
# No conditional here on purpose. This is what the whole increment is for, and
# a skipped check reads as a passing one.
check(200, "control refreshed", *call(
    f"/budget/Budgets(ID={budget_id},IsActiveEntity=true)/BudgetService.refreshControl",
    method="POST", body={}))
s, blines = call(f"/budget/BudgetLines?$filter=budget_ID eq {budget_id}"
                 "&$select=category,cbs_ID,amount,committed,encumbered,actual,available")
for l in blines["value"]:
    print(f"        {l['category']:4} amount {str(l['amount']):>12}"
          f"  committed {str(l['committed']):>10}"
          f"  encumbered {str(l['encumbered']):>10}  available {str(l['available']):>12}")

assert_(len(blines["value"]) > 0, "the budget has lines to commit against",
        len(blines["value"]))

# The order was for the vibrator kits — an EQR resource on the slab CBS — so
# the EQR line for that CBS is the one that must carry the commitment.
eqr = [l for l in blines["value"]
       if l.get("category") == "EQR" and l.get("cbs_ID") == slab["ID"]]
assert_(len(eqr) == 1, "there is an EQR line on the charged CBS", len(eqr))
if eqr:
    l = eqr[0]
    assert_(abs(float(l.get("committed") or 0) - 231.0) < 0.01,
            "the ordered 231.00 lands as committed on that line", l.get("committed"))
    expected = (float(l["amount"]) - float(l["committed"])
                - float(l["encumbered"]) - float(l.get("actual") or 0))
    assert_(abs(float(l["available"]) - expected) < 0.01,
            "available = amount - committed - encumbered - actual",
            f"{l['available']} vs {expected:.2f}")

others = [l for l in blines["value"] if not (
    l.get("category") == "EQR" and l.get("cbs_ID") == slab["ID"])]
assert_(all(float(l.get("committed") or 0) == 0 for l in others),
        "no other budget line was committed against",
        [(l["category"], l["committed"]) for l in others])

# Derived, not accumulated: refreshing twice must not double the commitment.
call(f"/budget/Budgets(ID={budget_id},IsActiveEntity=true)/BudgetService.refreshControl",
     method="POST", body={})
s, again = call(f"/budget/BudgetLines?$filter=budget_ID eq {budget_id}"
                "&$select=category,cbs_ID,committed")
eqr2 = [l for l in again["value"]
        if l.get("category") == "EQR" and l.get("cbs_ID") == slab["ID"]]
assert_(eqr2 and abs(float(eqr2[0].get("committed") or 0) - 231.0) < 0.01,
        "refreshing again leaves it at 231.00 — commitment is derived, not accumulated",
        eqr2[0].get("committed") if eqr2 else "no line")

head("10. A requisition line names the S/4 material its resource buys as")
# The other half of check 5. A description is enough for the KONSTRYX side of the
# chain but not for API_PURCHASEREQ_PROCESS_SRV, which orders against a material
# number — so the resource has to carry one and the line has to pick it up (I-35).
s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and "
              "code eq 'MAT-CEM-OPC53-50'&$select=ID,s4Material_ID")
cement = res["value"][0]
assert_(cement.get("s4Material_ID"),
        "the cement resource records the S/4 material it is bought as")

s, mats = call("/masterdata/Materials?$filter=materialCode eq '100023451'"
               "&$select=ID,materialCode,description")
assert_(len(mats["value"]) == 1, "the S/4 mirror holds 100023451",
        len(mats["value"]))
assert_(cement.get("s4Material_ID") == mats["value"][0]["ID"],
        "and it is the material the wireframe maps that resource to")

rid3, docno3 = new_request([
    {"resource_ID": crane, "description": "Tower crane", "qty": 1, "uom": "inst",
     "wbs_ID": wbs_id, "cbs_ID": slab["ID"], "needBy": "2026-09-15"},
    {"resource_ID": cement["ID"], "description": "Cement OPC 53 grade 50 kg",
     "qty": 200, "uom": "bag", "wbs_ID": wbs_id, "cbs_ID": slab["ID"],
     "needBy": "2026-09-15"},
])
check(200, "submitted", *rr_action(rid3, "submit"))
approve(docno3)
check(200, "crane stays in-house", *rr_action(rid3, "decideLine",
    {"lineNo": 1, "decision": "IN_HOUSE", "rationale": "Own fleet."}))
check(200, "cement goes to procurement", *rr_action(rid3, "decideLine",
    {"lineNo": 2, "decision": "PROCURE", "rationale": "Bought in, not stocked."}))
check(200, "requisition raised", *rr_action(rid3, "raisePurchaseRequisition"))

s, prs3 = call(f"/material/PurchaseRequisitions?$filter=sourceRequest_ID eq {rid3}"
               "&$select=ID")
s, lines3 = call("/material/PurchaseRequisitionLines?$filter=parent_ID eq "
                 f"{prs3['value'][0]['ID']}&$select=lineNo,resource_ID,material_ID"
                 "&$orderby=lineNo")
assert_(len(lines3["value"]) == 1, "only the cement line was requisitioned",
        len(lines3["value"]))
cementLine = lines3["value"][0]
assert_(cementLine.get("material_ID") == cement.get("s4Material_ID"),
        "the requisition line carries 100023451, resolved from its resource — "
        "the push now has something to order",
        cementLine.get("material_ID"))

head("11. The push refuses what it cannot honestly order")
# Every case here stops at a gate BEFORE any connection is opened. That is
# deliberate and must stay that way: .env points at the live tenant, so a
# requisition that cleared every gate would post a real purchase requisition
# from a test run. The live POST is exercised by hand against a tenant with
# SAP_COM_0053 activated, never from this suite.
sync3 = (f"/material/PurchaseRequisitions({prs3['value'][0]['ID']})"
         "/MaterialService.syncToS4")
s, msg = call(sync3, method="POST", body={})
check(400, "cement is orderable but its WBS is not in S/4 yet", s, msg)
assert_("WBS" in str(msg) and "commit against nothing" in str(msg),
        "and it says which line and why, not just that the push failed", msg)

# A requisition that names nothing S/4 can order. The crane is hired, not
# bought, so its resource has no material — the ask is valid, the order is not.
rid4, docno4 = new_request([
    {"resource_ID": crane, "description": "Tower crane", "qty": 1, "uom": "inst",
     "wbs_ID": wbs_id, "cbs_ID": slab["ID"], "needBy": "2026-09-15"},
])
check(200, "submitted", *rr_action(rid4, "submit"))
approve(docno4)
check(200, "the crane is bought in this time", *rr_action(rid4, "decideLine",
    {"lineNo": 1, "decision": "PROCURE", "rationale": "No fleet unit free."}))
check(200, "requisition raised", *rr_action(rid4, "raisePurchaseRequisition"))
s, prs4 = call(f"/material/PurchaseRequisitions?$filter=sourceRequest_ID eq {rid4}"
               "&$select=ID,syncStatus")
s, msg4 = call(f"/material/PurchaseRequisitions({prs4['value'][0]['ID']})"
               "/MaterialService.syncToS4", method="POST", body={})
check(400, "a line with no material is refused before anything is sent", s, msg4)
assert_("material" in str(msg4).lower(),
        "and the buyer is told to map the resource, not handed a connection error",
        msg4)
s, pr4 = call(f"/material/PurchaseRequisitions({prs4['value'][0]['ID']})"
              "?$select=syncStatus,syncAttempts")
assert_(pr4.get("syncStatus") == "NOT_SENT",
        "a refused push leaves it NOT_SENT — nothing was attempted, so nothing "
        "may read as FAILED", pr4.get("syncStatus"))
assert_(not pr4.get("syncAttempts"),
        "and it does not count as an attempt", pr4.get("syncAttempts"))

# Section 7 already had S/4 number this one 1000004711.
s, msg5 = call(f"/material/PurchaseRequisitions({pr['ID']})"
               "/MaterialService.syncToS4", method="POST", body={})
check(409, "an already-numbered requisition will not be sent a second time",
      s, msg5)
assert_("1000004711" in str(msg5),
        "and the message names the number S/4 already gave it", msg5)

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
