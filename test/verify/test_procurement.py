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


def price_every_bill(project_id):
    """Resolves the build-up on every bill the project carries.

    The budget gate is a statement about a project, not about one bill: VAL-04
    asks that every mapped line on the job has a complete, priced build-up.
    This test builds a bill of its own on PRJ-002 and then expects the gate to
    pass — which worked while PRJ-002 was a header with nothing under it, and
    stopped the moment it gained a bill of its own. Pricing the whole job is
    what a planner does before generating a budget, and it is what the gate is
    asking for.
    """
    _s, bills = call("/project/BOQs?$filter=IsActiveEntity eq true and "
                     f"project_ID eq {project_id}&$select=ID,boqId")
    for bill in (bills.get("value", []) if isinstance(bills, dict) else []):
        call(f"/project/BOQs(ID={bill['ID']},IsActiveEntity=true)"
             "/ProjectService.generateBuildUp", method="POST",
             body={"difficultyPct": 100})


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

price_every_bill(pid)

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
        "nothing is claimed for a resource with nothing registered — the "
        "vibrator kits have no service product mapped, and an invented code "
        "would push a real order",
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

# The requisition entered the flow before it had a number, linked by its own
# key. Now that ERP has issued one the flow has to follow it, or the chain
# names a document nobody can look up.
s, renamed = call(f"/workflow/DocumentLinks?$filter=fromDoc eq '{docno2}' and "
                  "linkType eq 'REQUISITION'&$select=toDoc")
assert_(renamed["value"] and renamed["value"][0]["toDoc"] == "1000004711",
        "the flow names the requisition by the number ERP issued, not by our key",
        renamed["value"][0]["toDoc"] if renamed["value"] else "no link")

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

head("10. A receipt turns commitment into delivery")
# The order was for 4 kits at 231.00. Taking one in has to move three numbers
# together: the line's open quantity, the order's open value, and the budget's
# commitment. If the commitment does not follow, the budget holds money against
# goods that are already on site — and it will hold it a second time when the
# invoice posts.
s, poLineNow = call(f"/material/PurchaseOrderLines?$filter=parent_ID eq {po['ID']}"
                    "&$select=lineNo,qty,openQty,receivedQty,netValue&$orderby=lineNo")
first = poLineNow["value"][0]
assert_(float(first.get("openQty") or 0) == float(first.get("qty") or 0),
        "an order that has delivered nothing is fully open", first.get("openQty"))

gr_body = {"poNo": "4500001234", "grDoc": "5000004711", "s4System": "S4H",
           "datePosted": "2026-09-21",
           "lines": [{"poLineNo": first["lineNo"], "grQty": 1}]}
check(400, "a receipt with no ERP document number",
      *call("/material/recordGoodsReceipt", method="POST", body=dict(gr_body, grDoc="")))
check(404, "a receipt against an order we do not hold",
      *call("/material/recordGoodsReceipt", method="POST",
            body=dict(gr_body, poNo="4599999999")))
check(400, "a receipt naming an order line that does not exist",
      *call("/material/recordGoodsReceipt", method="POST",
            body=dict(gr_body, lines=[{"poLineNo": 99, "grQty": 1}])))
check(409, "a receipt for more than the line has open",
      *call("/material/recordGoodsReceipt", method="POST",
            body=dict(gr_body, lines=[{"poLineNo": first["lineNo"], "grQty": 99}])))

s, stillOpen = call(f"/material/PurchaseOrderLines?$filter=parent_ID eq {po['ID']}"
                    "&$select=openQty,receivedQty&$orderby=lineNo")
assert_(float(stillOpen["value"][0].get("openQty") or 0) == float(first["qty"]),
        "a refused receipt left the line exactly as it was",
        stillOpen["value"][0].get("openQty"))

check(200, "5000004711 received, one of four",
      *call("/material/recordGoodsReceipt", method="POST", body=gr_body))
check(409, "mirroring the same receipt twice",
      *call("/material/recordGoodsReceipt", method="POST", body=gr_body))

s, grs = call("/material/GoodsReceipts?$filter=grDoc eq '5000004711'"
              "&$select=grQty,grValue,poLineNo,poLine_ID,po_ID")
gr = grs["value"][0]
assert_(gr.get("po_ID") == po["ID"] and gr.get("poLine_ID"),
        "the receipt names the order and the line it landed on")
assert_(abs(float(gr.get("grValue") or 0) - 57.75) < 0.01,
        "it is priced at the order line's own rate: 231.00 / 4",
        gr.get("grValue"))

s, after = call(f"/material/PurchaseOrderLines?$filter=parent_ID eq {po['ID']}"
                "&$select=openQty,receivedQty,status&$orderby=lineNo")
line_after = after["value"][0]
assert_(float(line_after.get("receivedQty") or 0) == 1
        and float(line_after.get("openQty") or 0) == 3,
        "one taken in, three still to come",
        (line_after.get("receivedQty"), line_after.get("openQty")))
assert_(line_after.get("status") == "Partly received",
        "the line says so", line_after.get("status"))

s, poAfter = call(f"/material/PurchaseOrders({po['ID']})"
                  "?$select=status,netValue,openValue")
assert_(abs(float(poAfter.get("netValue") or 0) - 231.0) < 0.01,
        "the order still cost what it cost", poAfter.get("netValue"))
assert_(abs(float(poAfter.get("openValue") or 0) - 173.25) < 0.01,
        "and owes three quarters of it", poAfter.get("openValue"))
assert_(poAfter.get("status") == "Partly received",
        "the order reads Partly received", poAfter.get("status"))

check(200, "control refreshed after the delivery", *call(
    f"/budget/Budgets(ID={budget_id},IsActiveEntity=true)/BudgetService.refreshControl",
    method="POST", body={}))
s, committed = call(f"/budget/BudgetLines?$filter=budget_ID eq {budget_id}"
                    "&$select=category,cbs_ID,committed")
eqr3 = [l for l in committed["value"]
        if l.get("category") == "EQR" and l.get("cbs_ID") == slab["ID"]]
assert_(eqr3 and abs(float(eqr3[0].get("committed") or 0) - 173.25) < 0.01,
        "commitment fell to what is still to be delivered, not what was ordered",
        eqr3[0].get("committed") if eqr3 else "no line")

check(200, "the rest delivered",
      *call("/material/recordGoodsReceipt", method="POST",
            body={"poNo": "4500001234", "grDoc": "5000004712", "s4System": "S4H",
                  "datePosted": "2026-10-05",
                  "lines": [{"poLineNo": first["lineNo"], "grQty": 3}]}))
s, settled = call(f"/material/PurchaseOrders({po['ID']})?$select=status,openValue")
assert_(settled.get("status") == "Received"
        and float(settled.get("openValue") or 0) == 0,
        "a fully delivered order is Received and owes nothing",
        (settled.get("status"), settled.get("openValue")))

call(f"/budget/Budgets(ID={budget_id},IsActiveEntity=true)/BudgetService.refreshControl",
     method="POST", body={})
s, none = call(f"/budget/BudgetLines?$filter=budget_ID eq {budget_id}"
               "&$select=category,cbs_ID,committed")
eqr4 = [l for l in none["value"]
        if l.get("category") == "EQR" and l.get("cbs_ID") == slab["ID"]]
assert_(eqr4 and float(eqr4[0].get("committed") or 0) == 0,
        "nothing is committed once everything has arrived — the cost is ERP FI's now",
        eqr4[0].get("committed") if eqr4 else "no line")

head("11. The invoice is matched three ways, and it decides what was spent")
# The last document, and the only source BudgetLine.actual has ever had. The
# order is fully received by now: 4 kits, 231.00, nothing open. So a clean bill
# for all four is the case that must match, and the two ways it can fail have
# to be recorded rather than refused — ERP FI posted the invoice either way,
# and an invoice we would not mirror is one nobody can see is wrong.
inv_body = {"poNo": "4500001234", "invoiceNo": "5100004711", "s4System": "S4H",
            "postingDate": "2026-10-08",
            "lines": [{"poLineNo": first["lineNo"], "qty": 4, "netAmount": 231.00}]}
check(400, "an invoice with no ERP number",
      *call("/material/recordSupplierInvoice", method="POST",
            body=dict(inv_body, invoiceNo="")))
check(404, "an invoice against an order we do not hold",
      *call("/material/recordSupplierInvoice", method="POST",
            body=dict(inv_body, poNo="4599999999")))
check(400, "an invoice billing a line that is not on the order",
      *call("/material/recordSupplierInvoice", method="POST",
            body=dict(inv_body, lines=[{"poLineNo": 99, "qty": 1, "netAmount": 10}])))

check(200, "5100004711 posted and matched",
      *call("/material/recordSupplierInvoice", method="POST", body=inv_body))
check(409, "mirroring the same invoice twice",
      *call("/material/recordSupplierInvoice", method="POST", body=inv_body))

s, invs = call("/material/SupplierInvoices?$filter=invoiceNo eq '5100004711'"
               "&$select=ID,matched,netAmount,orderNo,vendorName")
inv = invs["value"][0]
assert_(inv.get("matched") is True,
        "order, receipt and invoice agree, so the header says matched",
        inv.get("matched"))
assert_(abs(float(inv.get("netAmount") or 0) - 231.0) < 0.01,
        "and it is worth what the order was", inv.get("netAmount"))
assert_(inv.get("orderNo") == "4500001234",
        "the invoice names the order it bills", inv.get("orderNo"))

s, invLines = call(f"/material/SupplierInvoiceLines?$filter=parent_ID eq {inv['ID']}"
                   "&$select=matched,variance,goodsReceipt_ID,poLineNo")
assert_(invLines["value"][0].get("goodsReceipt_ID"),
        "and the line points at the receipt it bills against")

s, receipts = call(f"/material/GoodsReceipts?$filter=po_ID eq {po['ID']}"
                   "&$select=grDoc,threeWayMatch,matchVariance&$orderby=grDoc")
assert_(len(receipts["value"]) == 2
        and all(r.get("threeWayMatch") is True for r in receipts["value"]),
        "BOTH deliveries can finally answer the question their own column asks — "
        "one bill settles every load it covers, not just the last",
        [(r["grDoc"], r["threeWayMatch"]) for r in receipts["value"]])

head("11a. A bill that disagrees is recorded as disagreeing, not refused")
# Overbilling first: the line is fully received AND fully invoiced now, so any
# further quantity is billed against goods that never arrived.
check(200, "a second bill for the same four kits is accepted",
      *call("/material/recordSupplierInvoice", method="POST",
            body=dict(inv_body, invoiceNo="5100004712",
                      lines=[{"poLineNo": first["lineNo"], "qty": 4,
                              "netAmount": 231.00}])))
s, over = call("/material/SupplierInvoices?$filter=invoiceNo eq '5100004712'"
               "&$select=ID,matched")
assert_(over["value"][0].get("matched") is False,
        "and it is recorded as not matching", over["value"][0].get("matched"))
s, overLines = call("/material/SupplierInvoiceLines"
                    f"?$filter=parent_ID eq {over['value'][0]['ID']}"
                    "&$select=matched,variance")
variance = overLines["value"][0].get("variance") or ""
assert_("received" in variance,
        "naming the quantity billed against the quantity received", variance)

s, poNow = call(f"/material/PurchaseOrders({po['ID']})?$select=invoicedValue")
assert_(abs(float(poNow.get("invoicedValue") or 0) - 462.0) < 0.01,
        "the order has been billed twice over, and says so",
        poNow.get("invoicedValue"))

head("11b. Actual is what was billed, and it is derived like the rest")
check(200, "control refreshed after the invoices", *call(
    f"/budget/Budgets(ID={budget_id},IsActiveEntity=true)/BudgetService.refreshControl",
    method="POST", body={}))
s, spent = call(f"/budget/BudgetLines?$filter=budget_ID eq {budget_id}"
                "&$select=category,cbs_ID,amount,committed,encumbered,actual,available")
eqr5 = [l for l in spent["value"]
        if l.get("category") == "EQR" and l.get("cbs_ID") == slab["ID"]]
assert_(eqr5 and abs(float(eqr5[0].get("actual") or 0) - 462.0) < 0.01,
        "both bills land on the line the order charged — actual has a source at last",
        eqr5[0].get("actual") if eqr5 else "no line")
if eqr5:
    l = eqr5[0]
    expected = (float(l["amount"]) - float(l["committed"])
                - float(l["encumbered"]) - float(l["actual"]))
    assert_(abs(float(l["available"]) - expected) < 0.01,
            "and available still reads amount less all three",
            f"{l['available']} vs {expected:.2f}")

call(f"/budget/Budgets(ID={budget_id},IsActiveEntity=true)/BudgetService.refreshControl",
     method="POST", body={})
s, twice = call(f"/budget/BudgetLines?$filter=budget_ID eq {budget_id}"
                "&$select=category,cbs_ID,actual")
eqr6 = [l for l in twice["value"]
        if l.get("category") == "EQR" and l.get("cbs_ID") == slab["ID"]]
assert_(eqr6 and abs(float(eqr6[0].get("actual") or 0) - 462.0) < 0.01,
        "refreshing again leaves it at 462.00 — actual is derived, not accumulated",
        eqr6[0].get("actual") if eqr6 else "no line")

head("11e. One branch each, so nothing is counted twice")
# The report adds signed labour, stock issued, what was billed and what was
# certified, on the understanding that a scope goes down exactly one branch.
# It now measures whether that held rather than asserting it, and the measure
# has to be quiet here: every line on this request was decided PROCURE and
# travelled the purchase branch alone, so there is nothing on both.
check(200, "the project reconciles", *call(
    f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.reconcile",
    method="POST", body={}))
s, reports = call(f"/project/PeriodReports?$filter=project_ID eq {pid}"
                  "&$select=note,actualCost&$orderby=createdAt desc&$top=1")
report = reports["value"][0] if reports.get("value") else {}
note = " ".join((report.get("note") or "").split())
assert_("carries cost on both" not in note,
        "a line that went one way is not reported as having gone both",
        note[:110] or "(no note)")

# A caveat cut in half reads as a complete sentence that happens to end early,
# which is the one failure a reader cannot see. Every note the report writes is
# a sentence, so the last character settles it.
assert_(note.endswith("."),
        "and the note ends where a sentence ends, not mid-word",
        f"...{note[-60:]}" if note else "(no note)")
assert_("not shown here" not in note,
        "with nothing dropped for want of room",
        f"{len(note)} chars")

head("11d. The flow reads from the request to the bill")
# Four documents produced by four different actions. If any of them fails to
# join the chain, the flow stops there and the reader has no way to tell a
# document that was never raised from one that was raised and never linked.
s, flow = call("/workflow/DocumentLinks?$select=fromDoc,toDoc,linkType&$top=200")
edges = {}
for l in flow["value"]:
    edges.setdefault((l["fromDoc"], l["linkType"]), set()).add(l["toDoc"])
for frm, kind, to in [(docno2, "REQUISITION", "1000004711"),
                      ("1000004711", "ORDER", "4500001234"),
                      ("4500001234", "RECEIPT", "5000004711"),
                      ("4500001234", "RECEIPT", "5000004712"),
                      ("4500001234", "INVOICE", "5100004711")]:
    found = edges.get((frm, kind), set())
    assert_(to in found, f"{frm} -{kind}-> {to}", sorted(found) or "missing")

head("11c. Two lines of one invoice on one order line add up")
# Two lines of one invoice against one order line have to add up. The order
# rows are read before the loop, so without care the second line measures
# itself against what was billed before either of them landed, and the order
# ends up recording one of them rather than both.
s, before = call(f"/material/PurchaseOrderLines?$filter=parent_ID eq {po['ID']}"
                 "&$select=lineNo,invoicedQty&$orderby=lineNo")
was = float(before["value"][0].get("invoicedQty") or 0)
check(200, "one invoice, two lines, same order line",
      *call("/material/recordSupplierInvoice", method="POST",
            body={"poNo": "4500001234", "invoiceNo": "5100004713",
                  "s4System": "S4H", "postingDate": "2026-10-12",
                  "lines": [{"poLineNo": first["lineNo"], "qty": 1,
                             "netAmount": 57.75},
                            {"poLineNo": first["lineNo"], "qty": 1,
                             "netAmount": 57.75}]}))
s, after2 = call(f"/material/PurchaseOrderLines?$filter=parent_ID eq {po['ID']}"
                 "&$select=lineNo,invoicedQty&$orderby=lineNo")
assert_(abs(float(after2["value"][0].get("invoicedQty") or 0) - (was + 2)) < 0.001,
        "the order line records both lines, not the last one",
        f"{after2['value'][0].get('invoicedQty')} from {was}")

head("12. Nothing is procured until the line says where it charges")
# The account assignment is what the returning commitment lands on. A line
# without it raises an order that buys real scope and appears on no budget:
# the money is spent, the control record still reads fully available, and
# nothing anywhere says otherwise. Caught at the raise rather than at the push,
# because by the push the buyer has already been sent out to buy it.
rid_nc, docno_nc = new_request([
    {"resource_ID": vibro, "description": "Vibrator kits", "qty": 4, "uom": "kit",
     "wbs_ID": wbs_id, "needBy": "2026-09-15"},
])
print(f"      created {docno_nc}")
rr_action(rid_nc, "submit")
approve(docno_nc)
check(200, "the line goes to procurement", *rr_action(rid_nc, "decideLine",
    {"lineNo": 1, "decision": "PROCURE", "rationale": "Yard has none free."}))

s, refused = rr_action(rid_nc, "raisePurchaseRequisition")
check(400, "a line naming no cost node is refused", s, refused)
detail = (refused.get("error", {}).get("message", "")
          if isinstance(refused, dict) else str(refused))
assert_("cost node" in detail and "line 1" in detail,
        "and it names the line and what is missing, not just that it failed",
        detail[:120])

s, none = call(f"/material/PurchaseRequisitions?$filter=sourceRequest_ID eq {rid_nc}"
               "&$select=ID")
assert_(not none.get("value"),
        "nothing was written — a refused raise leaves no half-built requisition",
        len(none.get("value", [])))

head("13. A requisition line names what its resource is bought or hired as")
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

head("14. The push refuses what it cannot honestly order")
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

# A requisition that names nothing S/4 can order. The vibrator kits are hired
# and nothing is registered against them — the ask is valid, the order is not.
rid4, docno4 = new_request([
    {"resource_ID": vibro, "description": "Concrete vibrator kits", "qty": 4,
     "uom": "day", "wbs_ID": wbs_id, "cbs_ID": slab["ID"], "needBy": "2026-09-15"},
])
check(200, "submitted", *rr_action(rid4, "submit"))
approve(docno4)
check(200, "the kits are hired in", *rr_action(rid4, "decideLine",
    {"lineNo": 1, "decision": "PROCURE", "rationale": "No fleet unit free."}))
check(200, "requisition raised", *rr_action(rid4, "raisePurchaseRequisition"))
s, prs4 = call(f"/material/PurchaseRequisitions?$filter=sourceRequest_ID eq {rid4}"
               "&$select=ID,syncStatus")
s, msg4 = call(f"/material/PurchaseRequisitions({prs4['value'][0]['ID']})"
               "/MaterialService.syncToS4", method="POST", body={})
check(400, "a line with nothing registered is refused before anything is sent",
      s, msg4)
assert_("service product" in str(msg4).lower(),
        "and the buyer is told what to map, not handed a connection error", msg4)

head("15. A hired resource is ordered as a service, not as a material")
# Spec §8 / P10: class routes the leaf to S/4. A MATERIAL leaf is bought as a
# product; plant, labour and subcontract are hired as a service product. Both
# land in the same field on the requisition line because both are S/4
# product-master records — only the material type differs, and that is S/4's
# business. Before this, a crane could be requisitioned but never ordered,
# because the only thing a line could name was a material number.
s, craneRes = call("/masterdata/Resources?$filter=IsActiveEntity eq true and "
                   "code eq 'EQ-TWC-12T'&$select=ID,verticalType,s4Material_ID,"
                   "s4ServiceProduct_ID")
craneNode = craneRes["value"][0]
assert_(craneNode.get("s4ServiceProduct_ID") and not craneNode.get("s4Material_ID"),
        "the crane is hired as a service product and holds no material number — "
        "it is not a thing you buy")

s, svc = call("/masterdata/Materials?$filter=materialCode eq 'SVC-EQ-TWC-12T'"
              "&$select=ID,materialCode")
assert_(len(svc["value"]) == 1 and
        svc["value"][0]["ID"] == craneNode.get("s4ServiceProduct_ID"),
        "and it is the service product the wireframe's equipment master names")

rid5, docno5 = new_request([
    {"resource_ID": crane, "description": "Tower crane LB280", "qty": 1,
     "uom": "month", "wbs_ID": wbs_id, "cbs_ID": slab["ID"], "needBy": "2026-09-15"},
])
check(200, "submitted", *rr_action(rid5, "submit"))
approve(docno5)
check(200, "no fleet unit free, so it is hired", *rr_action(rid5, "decideLine",
    {"lineNo": 1, "decision": "PROCURE", "rationale": "Fleet fully committed."}))
check(200, "requisition raised", *rr_action(rid5, "raisePurchaseRequisition"))
s, prs5 = call(f"/material/PurchaseRequisitions?$filter=sourceRequest_ID eq {rid5}"
               "&$select=ID")
s, lines5 = call("/material/PurchaseRequisitionLines?$filter=parent_ID eq "
                 f"{prs5['value'][0]['ID']}&$select=lineNo,material_ID")
assert_(lines5["value"][0].get("material_ID") == craneNode.get("s4ServiceProduct_ID"),
        "the requisition line carries SVC-EQ-TWC-12T — a hired crane is now "
        "orderable, which it was not before",
        lines5["value"][0].get("material_ID"))

s, msg5b = call(f"/material/PurchaseRequisitions({prs5['value'][0]['ID']})"
                "/MaterialService.syncToS4", method="POST", body={})
check(400, "it still stops at the WBS gate, not at the material gate", s, msg5b)
assert_("WBS" in str(msg5b),
        "which is the proof the routing gate passed", msg5b)
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

head("16. Org data is a precondition, and it is not guessed")
# Plant, purchasing organisation and purchasing group come from the company
# that raised the requisition, never from a constant: they differ per legal
# entity, so one build-wide value would be wrong for every company but one.
# Missing org is REFUSED rather than defaulted — S/4 accepts a wrong-but-valid
# plant without complaint, and the requisition then lands in the wrong org,
# which nobody notices until somebody tries to receive against it.
s, comp = call(f"/admin/Companies?$filter=ID eq {project['company_ID']}"
               "&$select=code,defaultPlant,purchOrg,purchGroup,s4CoCode,ccy_code",
               user="admin")
if s == 200 and comp.get("value"):
    c = comp["value"][0]
    assert_(c.get("defaultPlant") == "3310" and c.get("purchOrg") == "3310"
            and c.get("purchGroup") == "001" and c.get("s4CoCode") == "3310",
            "INFC carries the org combination read off the tenant, not a "
            "placeholder — plant/purchOrg 3310, group 001, company code 3310",
            f"{c.get('defaultPlant')}/{c.get('purchOrg')}/"
            f"{c.get('purchGroup')}/{c.get('s4CoCode')}")
    assert_(c.get("ccy_code") == "AED",
            "and a currency, which the price rides with — the tenant's own "
            "requisitions are all AED", c.get("ccy_code"))
else:
    assert_(False, "company readable for org checks", f"status {s}")

# rid5's crane line clears both line gates (service product mapped), so this
# requisition reaches the org gate — which is the only way to exercise it.
s, msgOrg = call(f"/material/PurchaseRequisitions({prs5['value'][0]['ID']})"
                 "/MaterialService.syncToS4", method="POST", body={})
assert_("WBS" in str(msgOrg),
        "with org resolved, the crane requisition now stops only at the WBS "
        "gate — the last thing standing between it and S/4", msgOrg)

# The other three companies are deliberately empty: which S/4 org each legal
# entity maps to is a business decision, and a guess would land a real
# requisition in the wrong org rather than fail.
s, others = call("/admin/Companies?$filter=code ne 'INFC'"
                 "&$select=code,defaultPlant,purchOrg,purchGroup", user="admin")
if s == 200:
    blank = [o for o in others["value"] if not o.get("defaultPlant")]
    assert_(len(blank) == len(others["value"]),
            "the companies whose S/4 org nobody has decided carry nothing, so "
            "their requisitions are refused rather than misrouted",
            f"{len(blank)} of {len(others['value'])} empty")
else:
    assert_(False, "other companies readable", f"status {s}")

head("A document that changes state says so, and keeps saying it under one name")
# One class in the whole service used to write status history -- the one that
# drives the request chain. Everything else moved in silence: a requisition
# went to Ordered, an order went to Received, a budget went to Baselined, and
# nothing anywhere said when or on whose word. The status field answers "where
# is it now"; there was no answer at all to "how did it get there", which is
# the question asked when something is wrong.

s, hist = call("/workflow/StatusHistory?$select=docType,docId,fromState,toState,"
               "comment,changedBy&$top=500")
entries = hist.get("value", []) if s == 200 and isinstance(hist, dict) else []
kinds = sorted(set(e["docType"] for e in entries))
print(f"      {len(entries)} entries under {', '.join(kinds)}")


def trail(doc_no):
    return [(e.get("fromState"), e.get("toState"), e.get("comment"))
            for e in entries if e.get("docId") == doc_no]


assert_("PR" in kinds and "PO" in kinds,
        "the requisition and the order both keep a history now", ", ".join(kinds))

# Every kind is a kind, not a number. An ERP order numbered 4500001234 has no
# prefix to read, so deriving the kind from the number filed every order under
# a heading only it had -- which is the opposite of what a heading is for.
numeric = [k for k in kinds if k.isdigit() or k.startswith("PR:")]
assert_(not numeric, "and each is filed under its kind, not under its own number",
        ", ".join(numeric) if numeric else "none")

pr_no = "1000004711"
po_no = "4500001234"
pr_id = pr["ID"]
pr_moves = trail(pr_no)
assert_(any(t == "Requisitioned" for _, t, _ in pr_moves),
        f"{pr_no} records reaching ERP",
        " | ".join(f"{f}->{t}" for f, t, _ in pr_moves))
assert_(any(t in ("Ordered", "Partly ordered") for _, t, _ in pr_moves),
        "and records being ordered against",
        " | ".join(f"{f}->{t}" for f, t, _ in pr_moves))

# The requisition entered the flow identified by its own key, because that was
# the only identity it had. The chain moves its links across when ERP issues a
# number; without the same move here, everything that happened before it was
# requisitioned stays filed under a key nobody can look up, and the findable
# half of its history begins in the middle.
assert_(any(t == "Draft" for _, t, _ in pr_moves),
        "including what happened to it before ERP had ever heard of it",
        f"{len(pr_moves)} entries under {pr_no}")
orphan = [e for e in entries if str(e.get("docId", "")).startswith("PR:")
          and e.get("docId") == "PR:" + pr_id]
assert_(not orphan, "and nothing of its is left behind under the old key",
        f"{len(orphan)} left")

po_moves = trail(po_no)
assert_(any(t in ("Received", "Partly received") for _, t, _ in po_moves),
        f"{po_no} records what arrived against it",
        " | ".join(f"{f}->{t}" for f, t, _ in po_moves))
assert_(all(f is not None for f, _, _ in po_moves),
        "each entry naming the state it left, not just the one it reached",
        " | ".join(f"{f}->{t}" for f, t, _ in po_moves))
assert_(all(c for _, _, c in po_moves),
        "and why, so the entry is worth reading",
        " | ".join(str(c)[:40] for _, _, c in po_moves))


print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
