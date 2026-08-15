"""Phase 5: the budget engine, end to end.

Build-up -> priced lines by CBS x cost nature -> approval -> baseline ->
movement through the ledger only -> live encumbrance in the control record."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"

BILL = """itemNo;code;description;qty;uom;rate
2.01;CONC-C40;Ready-mix C40 to raft;1200;m3;385.00
"""


def call(path, method="GET", body=None, user="demo"):
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
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] {label}: {str(payload)[:175]}")
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


def make_master(entity, body, user="steward_infc"):
    s, d = call(f"/masterdata/{entity}", method="POST", body=body, user=user)
    if s != 201:
        return s, d
    return call(f"/masterdata/{entity}(ID={d['ID']},IsActiveEntity=false)"
                "/MasterDataService.draftActivate", method="POST", body={}, user=user)


def bud_action(bid, action, body=None):
    return call(f"/budget/Budgets(ID={bid},IsActiveEntity=true)/BudgetService.{action}",
                method="POST", body=body or {})


# ------------------------------------------------------------------- fixtures
s, ps = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'PRJ-002'"
             "&$select=ID,code,company_ID")
project = ps["value"][0]
pid, company_id = project["ID"], project["company_ID"]

call(f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.instantiateCBS",
     method="POST", body={})
s, cbs = call(f"/project/CBS?$filter=project_ID eq {pid}&$select=ID,code,libraryNode_ID")
slab = [c for c in cbs["value"] if c["code"] == "02.10"][0]

# WBS for the chain later.
call(f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.draftEdit",
     method="POST", body={"PreserveChanges": True})
call(f"/project/Projects(ID={pid},IsActiveEntity=false)/wbsElements",
     method="POST", body={"code": "PRJ-002.1", "description": "Substructure"})
call(f"/project/Projects(ID={pid},IsActiveEntity=false)/ProjectService.draftActivate",
     method="POST", body={})
s, wbs = call(f"/project/WBS?$filter=project_ID eq {pid}&$select=ID&$top=1")
wbs_id = wbs["value"][0]["ID"]

s, d = call("/project/BOQs", method="POST", body={
    "boqId": "BOQ-BUD", "project_ID": pid, "version": "A", "status": "Draft"})
boq_id = d["ID"]
call(f"/project/BOQs(ID={boq_id},IsActiveEntity=false)/ProjectService.draftActivate",
     method="POST", body={})
call(f"/project/BOQs(ID={boq_id},IsActiveEntity=true)/ProjectService.importItems",
     method="POST", body={"fileName": "bill.csv", "content": BILL})
s, items = call(f"/project/BOQItems?$filter=boq_ID eq {boq_id}&$select=ID,itemNo")
call(f"/project/BOQItems(ID={items['value'][0]['ID']},IsActiveEntity=true)",
     method="PATCH", body={"cbs_ID": slab["ID"]})

s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'MT-RMC-C40-20'"
              "&$select=ID")
concrete = res["value"][0]["ID"]
s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-VIB-KIT'"
              "&$select=ID")
vibro = res["value"][0]["ID"]

make_master("ConsumptionRates", {
    "material_ID": concrete, "linkedCBS_ID": slab["libraryNode_ID"],
    "consRate": 1.0, "consUoM": "m3", "wastageAllowancePct": 2.5,
    "effectiveFrom": "2026-01-01", "scope": "GROUP"})
make_master("ProductivityRates", {
    "resource_ID": vibro, "linkedCBS_ID": slab["libraryNode_ID"],
    "outputPerHr": 12, "outputUoM": "m3", "crewComposition": "1 OP + 1 HLP",
    "effectiveFrom": "2026-01-01", "scope": "GROUP"})
call(f"/project/BOQs(ID={boq_id},IsActiveEntity=true)/ProjectService.generateBuildUp",
     method="POST", body={"difficultyPct": 110})
print(f"  fixtures ready on {project['code']}: build-up = 1230 m3 concrete + 110 hr vibro crew")

head("1. A budget is generated from the build-up, or not at all")
s, d = call("/budget/Budgets", method="POST", body={
    "project_ID": pid, "company_ID": company_id, "version": "V1",
    "raisedBy": "demo", "raisedOn": "2026-08-15"})
bid = d["ID"]
act = check(200, "budget activated", *call(
    f"/budget/Budgets(ID={bid},IsActiveEntity=false)/BudgetService.draftActivate",
    method="POST", body={}))
docno = act.get("docNo") if isinstance(act, dict) else None
assert_(docno and docno.startswith("BUD-"), "drew a company-scoped number", docno)

check(400, "generation refused while a resource is unpriced", *bud_action(bid, "generateLines"))
check(200, "a rate for the concrete is maintained", *make_master("Rates", {
    "resource_ID": concrete, "rateValue": 285.00, "basis": "m3", "ccy_code": "AED",
    "effectiveFrom": "2026-01-01", "scope": "GROUP"}))
msg = check(200, "generated", *bud_action(bid, "generateLines"))

s, lines = call(f"/budget/BudgetLines?$filter=budget_ID eq {bid}"
                "&$select=ID,category,amount,available&$orderby=category")
for l in lines["value"]:
    print(f"        {l['category']:4} amount {l['amount']:>12}  available {l['available']:>12}")
by_cat = {l["category"]: l for l in lines["value"]}
assert_(abs(float(by_cat["MR"]["amount"]) - 1230 * 285) < 0.01,
        "MR = 1230 m3 x 285", by_cat["MR"]["amount"])
assert_(abs(float(by_cat["EQR"]["amount"]) - 110 * 55) < 0.5,
        "EQR = 110 hr x 55", by_cat["EQR"]["amount"])

s, led = call(f"/budget/LedgerEntries?$filter=budget_ID eq {bid}&$select=category,amount")
assert_(len(led["value"]) == 2 and all(e["category"] == "ORIGINAL" for e in led["value"]),
        "every line opened with exactly one ORIGINAL entry")

head("2. Approval moves the budget; baseline closes the door")
check(200, "submitted", *bud_action(bid, "submit"))
check(409, "baseline before approval", *bud_action(bid, "baseline"))

s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{docno}'"
               "&$select=ID&$expand=steps($select=ID,stepNo;$orderby=stepNo)")
steps = inst["value"][0]["steps"]
print(f"      {len(steps)} approval step(s) at this value band")
users = ["demo", "daud", "admin"]
for i, st in enumerate(steps):
    call(f"/collaboration/ApprovalSteps({st['ID']})/CollaborationService.approve",
         method="POST", body={"comment": "Within the tender allowance."}, user=users[i])

s, b = call(f"/budget/Budgets(ID={bid},IsActiveEntity=true)?$select=status,totalAmount")
assert_(b.get("status") == "Approved", "the approval closing set the budget itself",
        b.get("status"))
total = float(b["totalAmount"])

check(200, "baselined", *bud_action(bid, "baseline"))
check(409, "regeneration after baseline", *bud_action(bid, "generateLines"))
mr_line = by_cat["MR"]
s, patch = call(f"/budget/BudgetLines(ID={mr_line['ID']},IsActiveEntity=true)",
                method="PATCH", body={"amount": 999999})
if s == 400:  # non-draft child PATCH may be rejected at protocol level; try flat key
    s, patch = call(f"/budget/BudgetLines({mr_line['ID']})", method="PATCH",
                    body={"amount": 999999})
check(403, "editing a baselined amount by hand", s, patch)

head("3. Movement goes through the ledger, zero-sum and explained")
check(400, "a shift without a reason", *bud_action(bid, "shift", {
    "fromCBS": "02.10", "fromCategory": "MR", "toCBS": "02.10", "toCategory": "EQR",
    "amount": 50000}))
check(200, "50,000 shifted MR -> EQR", *bud_action(bid, "shift", {
    "fromCBS": "02.10", "fromCategory": "MR", "toCBS": "02.10", "toCategory": "EQR",
    "amount": 50000, "reason": "Pumping replaced by crane-and-skip; plant hours up."}))
check(409, "shifting more than is available", *bud_action(bid, "shift", {
    "fromCBS": "02.10", "fromCategory": "EQR", "toCBS": "02.10", "toCategory": "MR",
    "amount": 99999999, "reason": "x"}))

s, lines = call(f"/budget/BudgetLines?$filter=budget_ID eq {bid}"
                "&$select=ID,category,amount&$orderby=category")
by_cat = {l["category"]: l for l in lines["value"]}
line_sum = sum(float(l["amount"]) for l in lines["value"])
assert_(abs(line_sum - total) < 0.01, "the shift moved money, not the total",
        f"{line_sum:,.2f}")

s, led = call(f"/budget/LedgerEntries?$filter=budget_ID eq {bid}"
              "&$select=line_ID,category,amount,pairKey&$orderby=category")
shifts = [e for e in led["value"] if e["category"] == "SHIFT"]
assert_(len(shifts) == 2 and shifts[0]["pairKey"] == shifts[1]["pairKey"]
        and abs(sum(float(e["amount"]) for e in shifts)) < 0.01,
        "the shift is two paired entries summing to zero")

for l in lines["value"]:
    entry_sum = sum(float(e["amount"]) for e in led["value"] if e["line_ID"] == l["ID"])
    assert_(abs(entry_sum - float(l["amount"])) < 0.01,
            f"{l['category']} line amount equals the sum of its ledger entries",
            f"{entry_sum:,.2f}")

head("4. Live encumbrance lands in the control record")
s, d = call("/workflow/ResourceRequests", method="POST", body={
    "verticalType": "EQR", "project_ID": pid, "company_ID": company_id,
    "wbs_ID": wbs_id, "needBy": "2026-11-01", "raisedBy": "demo", "raisedOn": "2026-08-15"})
rid = d["ID"]
call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=false)/lines", method="POST",
     body={"lineNo": 1, "resource_ID": vibro, "qty": 2, "uom": "kit",
           "wbs_ID": wbs_id, "cbs_ID": slab["ID"]})
call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=false)"
     "/WorkflowService.draftActivate", method="POST", body={})
call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)/WorkflowService.submit",
     method="POST", body={})
s, inst = call(f"/collaboration/ApprovalInstances?$filter=entityName eq"
               f" 'konstryx.wf.ResourceRequest' and status eq 'PENDING'"
               "&$select=ID,objectDocNo&$expand=steps($select=ID)")
for st in inst["value"][0]["steps"]:
    call(f"/collaboration/ApprovalSteps({st['ID']})/CollaborationService.approve",
         method="POST", body={"comment": "ok"})
call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)/WorkflowService.decideLine",
     method="POST", body={"lineNo": 1, "decision": "IN_HOUSE", "rationale": "Fleet."})
call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)"
     "/WorkflowService.runAvailabilityCheck", method="POST", body={})
res_msg = call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)"
               "/WorkflowService.createReservation", method="POST", body={})[1]
print(f"      {str(res_msg)[:96]}")

msg = check(200, "control refreshed", *bud_action(bid, "refreshControl"))
s, lines = call(f"/budget/BudgetLines?$filter=budget_ID eq {bid}"
                "&$select=category,amount,encumbered,available&$orderby=category")
for l in lines["value"]:
    print(f"        {l['category']:4} amount {l['amount']:>12}  encumbered {l['encumbered']:>9}"
          f"  available {l['available']:>12}")
eqr = [l for l in lines["value"] if l["category"] == "EQR"][0]
assert_(abs(float(eqr["encumbered"]) - 110.0) < 0.01,
        "the reservation's 110 encumbers the EQR line and no other",
        eqr["encumbered"])
mr = [l for l in lines["value"] if l["category"] == "MR"][0]
assert_(float(mr["encumbered"]) == 0, "the MR line is untouched by an EQR reservation")
assert_(abs(float(eqr["available"]) - (float(eqr["amount"]) - 110.0)) < 0.01,
        "available = amount - encumbered on the control record")

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
