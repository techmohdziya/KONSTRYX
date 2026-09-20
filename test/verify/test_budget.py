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


def price_every_bill(project_id, except_bill=None):
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
        # Never the caller's own bill: it is priced at the difficulty this test
        # is asserting about, and re-resolving it at 100 would restate the very
        # figure being checked.
        if except_bill and bill["ID"] == except_bill:
            continue
        call(f"/project/BOQs(ID={bill['ID']},IsActiveEntity=true)"
             "/ProjectService.generateBuildUp", method="POST",
             body={"difficultyPct": 100})

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
    "outputPerHr": 12, "outputUoM": "m3",
    "effectiveFrom": "2026-01-01", "scope": "GROUP"})
call(f"/project/BOQs(ID={boq_id},IsActiveEntity=true)/ProjectService.generateBuildUp",
     method="POST", body={"difficultyPct": 110})
# Allocate the line fully so VAL-02 and VAL-03 pass at the gate: 1200 to the
# substructure WBS against the slab CBS.
call(f"/project/BOQItems(ID={items['value'][0]['ID']},IsActiveEntity=true)"
     "/ProjectService.allocate", method="POST",
     body={"wbsCode": "PRJ-002.1", "cbsCode": "02.10", "qty": 1200})
print(f"  fixtures ready on {project['code']}: build-up = 1230 m3 concrete + 110 hr vibro")

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

s, refusal = bud_action(bid, "generateLines")
ok = s == 409 and "GATE_FAILED" in str(refusal) and "VAL-04" in str(refusal)
print(f"  {'ok  ' if ok else 'FAIL'} [{s}] gate refuses while the recipe is unpriced:"
      f" {str(refusal)[:130]}")
results.append(ok)
check(200, "a rate for the concrete is maintained", *make_master("Rates", {
    "resource_ID": concrete, "rateValue": 285.00, "basis": "m3", "ccy_code": "AED",
    "effectiveFrom": "2026-01-01", "scope": "GROUP"}))
# A rate correction propagates by re-running the generation (IT-05).
check(200, "build-up regenerated with the rate in force", *call(
    f"/project/BOQs(ID={boq_id},IsActiveEntity=true)/ProjectService.generateBuildUp",
    method="POST", body={"difficultyPct": 110}))
price_every_bill(pid, boq_id)
msg = check(200, "generated — the gate passes", *bud_action(bid, "generateLines"))

s, lines = call(f"/budget/BudgetLines?$filter=budget_ID eq {bid}"
                "&$select=ID,category,amount,available,boqItem_ID&$orderby=category")
for l in lines["value"]:
    print(f"        {l['category']:4} amount {l['amount']:>12}  available {l['available']:>12}")
# The project carries a bill of its own as well as this one, so a line is
# picked by the bill item it was generated from rather than by cost nature
# alone — two MR lines on one budget is now the ordinary case.
own_item = items["value"][0]["ID"]
by_cat = {l["category"]: l for l in lines["value"]
          if str(l.get("boqItem_ID")) == own_item}
assert_(abs(float(by_cat["MR"]["amount"]) - 1230 * 285) < 0.01,
        "MR = 1230 m3 x 285", by_cat["MR"]["amount"])
assert_(abs(float(by_cat["EQR"]["amount"]) - 110 * 55) < 0.5,
        "EQR = 110 hr x 55", by_cat["EQR"]["amount"])

s, led = call(f"/budget/LedgerEntries?$filter=budget_ID eq {bid}&$select=category,amount")
# One entry per line, whatever the line count is. Asserting the count itself
# would be asserting how big the project's bill happens to be.
assert_(len(led["value"]) == len(lines["value"])
        and all(e["category"] == "ORIGINAL" for e in led["value"]),
        "every line opened with exactly one ORIGINAL entry",
        f"{len(led['value'])} entries for {len(lines['value'])} lines")

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

# And the guard above reads the status, so a writable status was worth exactly
# one call to get around: put the budget back to Draft and the amounts open up.
check(403, "and putting the budget back to Draft to get at them", *call(
    f"/budget/Budgets(ID={bid},IsActiveEntity=true)", method="PATCH",
    body={"status": "Draft"}))
s_now, budget_now = call(f"/budget/Budgets(ID={bid},IsActiveEntity=true)?$select=status")
assert_(budget_now.get("status") == "Baselined",
        "so it is still baselined", str(budget_now.get("status")))

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

head("3b. Risk Transfer and Variation feed their own ledger categories")
check(400, "a risk transfer without a risk reference", *bud_action(bid, "riskTransfer", {
    "fromCBS": "02.10", "fromCategory": "EQR", "toCBS": "02.10", "toCategory": "MR",
    "amount": 5000, "reason": "Vibro downtime covered from contingency."}))
check(200, "5,000 transferred EQR -> MR against a realized risk", *bud_action(bid, "riskTransfer", {
    "fromCBS": "02.10", "fromCategory": "EQR", "toCBS": "02.10", "toCategory": "MR",
    "amount": 5000, "riskReference": "RISK-2026-014",
    "reason": "Vibro downtime covered from contingency."}))
check(400, "a variation with a zero amount", *bud_action(bid, "variation", {
    "cbs": "02.10", "category": "EQR", "amount": 0,
    "variationRef": "VO-2026-003", "reason": "Client added a second pour bay."}))
check(200, "25,000 added to EQR by a client variation", *bud_action(bid, "variation", {
    "cbs": "02.10", "category": "EQR", "amount": 25000,
    "variationRef": "VO-2026-003", "reason": "Client added a second pour bay."}))

s, lines = call(f"/budget/BudgetLines?$filter=budget_ID eq {bid}"
                "&$select=ID,category,amount&$orderby=category")
by_cat = {l["category"]: l for l in lines["value"]}
line_sum = sum(float(l["amount"]) for l in lines["value"])
s, b = call(f"/budget/Budgets(ID={bid},IsActiveEntity=true)?$select=totalAmount")
new_total = float(b["totalAmount"])
assert_(abs(new_total - (total + 25000)) < 0.01,
        "the variation moved the budget's own total by its amount, unlike shift/risk transfer",
        f"{new_total:,.2f}")
assert_(abs(line_sum - new_total) < 0.01,
        "lines still sum to the (now larger) total", f"{line_sum:,.2f}")

s, led = call(f"/budget/LedgerEntries?$filter=budget_ID eq {bid}"
              "&$select=line_ID,category,amount,reference,pairKey&$orderby=category")
risk_entries = [e for e in led["value"] if e["category"] == "RISK_TRANSFER"]
assert_(len(risk_entries) == 2 and risk_entries[0]["pairKey"] == risk_entries[1]["pairKey"]
        and abs(sum(float(e["amount"]) for e in risk_entries)) < 0.01
        and all(e["reference"] == "RISK-2026-014" for e in risk_entries),
        "the risk transfer is two paired entries summing to zero, keyed to the risk")
var_entries = [e for e in led["value"] if e["category"] == "VARIATION"]
assert_(len(var_entries) == 1 and var_entries[0]["pairKey"] is None
        and abs(float(var_entries[0]["amount"]) - 25000) < 0.01
        and var_entries[0]["reference"] == "VO-2026-003",
        "the variation is one unpaired entry keyed to the variation order")

for l in lines["value"]:
    entry_sum = sum(float(e["amount"]) for e in led["value"] if e["line_ID"] == l["ID"])
    assert_(abs(entry_sum - float(l["amount"])) < 0.01,
            f"{l['category']} line amount still equals the sum of its ledger entries "
            "after risk transfer and variation", f"{entry_sum:,.2f}")

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

head("5. A lock the budget has no heading for is reported, not lost")
# Encumbrance is attributed by walking the budget's own lines and asking what
# is locked against each cost node and cost nature. A lock against a node the
# budget has no heading for is therefore never asked about: it does not fall
# out of a total, because it never reaches one. Nothing is wrong on any screen
# and the headroom above it reads as free.
#
# Commitment and actual have said so since they were built. This is the third
# of the three and it is the one that matters most: an order or an invoice is
# money somebody will present a demand for, and an unheld lock is a promise the
# job made itself that only the reservation remembers.

held_before = sum(float(l["encumbered"] or 0) for l in call(
    f"/budget/BudgetLines?$filter=budget_ID eq {bid}&$select=encumbered")[1]["value"])

s, cbs_all = call(f"/project/CBS?$filter=project_ID eq {pid}&$select=ID,code")
uncarried = [c for c in cbs_all["value"] if c["ID"] not in set(
    l.get("cbs_ID") for l in call(
        f"/budget/BudgetLines?$filter=budget_ID eq {bid}&$select=cbs_ID")[1]["value"])]
assert_(len(uncarried) > 0, "the project has a cost node the budget carries no line for",
        f"{len(uncarried)} of {len(cbs_all['value'])} nodes")
stray = uncarried[0]

s, d = call("/workflow/ResourceRequests", method="POST", body={
    "verticalType": "EQR", "project_ID": pid, "company_ID": company_id,
    "wbs_ID": wbs_id, "needBy": "2026-11-01", "raisedBy": "demo",
    "raisedOn": "2026-08-15"})
stray_rid = d["ID"]
call(f"/workflow/ResourceRequests(ID={stray_rid},IsActiveEntity=false)/lines",
     method="POST", body={"lineNo": 1, "resource_ID": vibro, "qty": 2, "uom": "kit",
                          "wbs_ID": wbs_id, "cbs_ID": stray["ID"]})
call(f"/workflow/ResourceRequests(ID={stray_rid},IsActiveEntity=false)"
     "/WorkflowService.draftActivate", method="POST", body={})
call(f"/workflow/ResourceRequests(ID={stray_rid},IsActiveEntity=true)"
     "/WorkflowService.submit", method="POST", body={})
s, inst = call("/collaboration/ApprovalInstances?$filter=entityName eq"
               " 'konstryx.wf.ResourceRequest' and status eq 'PENDING'"
               "&$select=ID,objectDocNo&$expand=steps($select=ID)")
for step in inst["value"][0]["steps"]:
    call(f"/collaboration/ApprovalSteps({step['ID']})/CollaborationService.approve",
         method="POST", body={"comment": "ok"})
call(f"/workflow/ResourceRequests(ID={stray_rid},IsActiveEntity=true)"
     "/WorkflowService.decideLine", method="POST",
     body={"lineNo": 1, "decision": "IN_HOUSE", "rationale": "Fleet."})
call(f"/workflow/ResourceRequests(ID={stray_rid},IsActiveEntity=true)"
     "/WorkflowService.runAvailabilityCheck", method="POST", body={})
stray_msg = call(f"/workflow/ResourceRequests(ID={stray_rid},IsActiveEntity=true)"
                 "/WorkflowService.createReservation", method="POST", body={})[1]
print(f"      {str(stray_msg)[:96]}")

stray_lock = sum(
    float(l["encumberedAmount"] or 0) - float(l["costToDate"] or 0)
    for r in call("/workflow/Reservations?$filter=rr_ID eq "
                  f"{stray_rid}&$select=ID")[1]["value"]
    for l in call(f"/workflow/ReservationLines?$filter=reservation_ID eq {r['ID']}"
                  "&$select=encumberedAmount,costToDate")[1]["value"])
assert_(stray_lock > 0, "which locks money against that node",
        f"{stray_lock:,.2f}")

msg = str(check(200, "control refreshed with the stray lock live",
                *bud_action(bid, "refreshControl")))
held_after = sum(float(l["encumbered"] or 0) for l in call(
    f"/budget/BudgetLines?$filter=budget_ID eq {bid}&$select=encumbered")[1]["value"])
assert_(abs(held_after - held_before) < 0.01,
        "no budget line holds it — that is the defect, and it is silent",
        f"{held_before:,.2f} -> {held_after:,.2f}")
assert_("held nowhere" in msg,
        "so the refresh says so instead of reporting a clean run",
        msg[msg.find("locked by open") - 12:][:150] if "locked by open" in msg
        else msg[:150])
assert_(f"{stray_lock:.2f}" in msg or f"{stray_lock:.1f}" in msg,
        "and names the amount, so it can be reconciled",
        f"looking for {stray_lock:.2f}")
assert_(msg.count("held nowhere") == 1
        and "committed nowhere" not in msg.split("held nowhere")[0],
        "the three are reported separately, not merged into one figure")


print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
