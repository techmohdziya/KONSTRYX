"""Phase 1 financial framework: exchange rates, and the CBS roll-up.

Two stored numbers that derived from nothing are made to derive:

    approval band match  = the amount restated in the band's own currency
    CBSInstance budget   = the budget lines beneath the node, rolled upward

The currency half matters because a band carried a ccy that no code read, so a
scheme banded in dirhams matched a euro-denominated amount on the bare numbers.
The CBS half is the same defect as the payment certificate that stated a net
its own back charges contradicted.
"""
import json, urllib.request, base64, sys, uuid
from decimal import Decimal

BASE = "http://localhost:8090/odata/v4"
ADMIN = "admin"          # AdminService requires the Admin scope
# Structural CBS edits are not in the project manager's permission catalogue,
# so the tree is built as admin. What is under test here is the arithmetic;
# who may edit a CBS is test_foundations' question, not this suite's.
PM = "admin"


def call(path, user=ADMIN, method="GET", body=None):
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
    print(f"  {mark} [{status}] {label}: {str(payload)[:150]}")
    results.append(status == expected)
    return payload


def same(label, actual, expected):
    ok = actual is not None and Decimal(str(actual)) == Decimal(str(expected))
    print(f"  {'ok  ' if ok else 'FAIL'} {label} = {expected}"
          f"{'' if ok else '  (got ' + str(actual) + ')'}")
    results.append(ok)


def yes(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    results.append(bool(condition))


def head(t):
    print()
    print("=" * 76)
    print(t)
    print("=" * 76)


def rate(from_ccy, to_ccy, kind, value, valid_from="2026-01-01"):
    """Creates one rate.

    The rate goes over the wire as a bare JSON number. CAP's V4 deserializer
    refuses a quoted decimal outright - the same interop trap that made
    distributeToWBS fail from the UI5 client, met here from Python.
    """
    st, row = call("/admin/ExchangeRates", method="POST", body={
        "fromCcy_code": from_ccy, "toCcy_code": to_ccy, "rateType": kind,
        "validFrom": valid_from, "rate": float(value), "source": "verification"})
    return st, row


head("1. Rates go on file")
for f, t, k, v in [("EUR", "AED", "SPOT", "3.95"),
                   ("USD", "AED", "SPOT", "3.6725"),
                   ("USD", "AED", "BUDGET", "3.70")]:
    st, _ = rate(f, t, k, v)
    results.append(st == 201)
    print(f"  {'ok  ' if st == 201 else 'FAIL'} [{st}] {f}->{t} {k} at {v}")

head("2. Conversion, and it says which rate it used")
st, conv = call("/admin/convert", method="POST", body={
    "amount": 1000, "fromCcy": "EUR", "toCcy": "AED", "rateType": "SPOT",
    "asOf": "2026-06-01"})
results.append(st == 200)
print(f"  {'ok  ' if st == 200 else 'FAIL'} [{st}] 1000 EUR -> {conv}")
if st == 200:
    same("1000 EUR at 3.95", conv.get("amount"), "3950.00")
    same("the rate is reported", conv.get("rate"), "3.950000")
    yes("the rate type travels with the money",
        conv.get("rateType") == "SPOT")

head("3. The rate type is not decoration")
st, budget_rate = call("/admin/convert", method="POST", body={
    "amount": 1000, "fromCcy": "USD", "toCcy": "AED", "rateType": "BUDGET",
    "asOf": "2026-06-01"})
st2, spot_rate = call("/admin/convert", method="POST", body={
    "amount": 1000, "fromCcy": "USD", "toCcy": "AED", "rateType": "SPOT",
    "asOf": "2026-06-01"})
same("1000 USD at the budget rate", budget_rate.get("amount"), "3700.00")
same("1000 USD at the spot rate", spot_rate.get("amount"), "3672.50")
yes("the two rates give different money",
    budget_rate.get("amount") != spot_rate.get("amount"))

head("4. The inverse pair, and the identity")
# Nobody maintains AED->EUR as well as EUR->AED; the table has the answer.
st, back = call("/admin/convert", method="POST", body={
    "amount": 3950, "fromCcy": "AED", "toCcy": "EUR", "rateType": "SPOT",
    "asOf": "2026-06-01"})
results.append(st == 200)
same("3950 AED back to EUR", back.get("amount"), "1000.00")
yes("the inversion is declared in the source",
    "invert" in str(back.get("source", "")).lower())

st, ident = call("/admin/convert", method="POST", body={
    "amount": 500, "fromCcy": "AED", "toCcy": "AED", "rateType": "SPOT"})
same("AED to AED is the same money", ident.get("amount"), "500.00")
same("at rate 1", ident.get("rate"), "1.000000")

head("5. A pair with no rate is refused, not guessed")
check(400, "GBP has no rate on file", *call(
    "/admin/convert", method="POST", body={
        "amount": 1000, "fromCcy": "GBP", "toCcy": "AED", "rateType": "SPOT"}))

head("6. A CBS tree, built because the seeded one is flat")
s, projects = call("/project/Projects?$select=ID,code&$filter=IsActiveEntity eq true&$top=1",
                   user=PM)
if not projects.get("value"):
    print("  no project to build a CBS on")
    sys.exit(0)
project = projects["value"][0]
print(f"      on {project['code']}")

parent_id = str(uuid.uuid4())
child_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
st, _ = call("/project/CBS", method="POST", user=PM, body={
    "ID": parent_id, "code": "VER.PARENT", "project_ID": project["ID"],
    "level": "L1", "budgetAmount": 999999.0})
results.append(st == 201)
print(f"  {'ok  ' if st == 201 else 'FAIL'} [{st}] parent node created claiming 999,999")

for i, cid in enumerate(child_ids, start=1):
    st, _ = call("/project/CBS", method="POST", user=PM, body={
        "ID": cid, "code": f"VER.CHILD.{i}", "project_ID": project["ID"],
        "parent_ID": parent_id, "level": "L2", "budgetAmount": 0.0})
    results.append(st == 201)
    print(f"  {'ok  ' if st == 201 else 'FAIL'} [{st}] child {i} created")

head("7. A budget, and lines beneath the tree")
budget_id = str(uuid.uuid4())
st, _ = call("/budget/Budgets", method="POST", user=PM, body={
    "ID": budget_id, "docNo": "VER-BUD-001", "project_ID": project["ID"],
    "version": "V1", "status": "Draft"})
results.append(st == 201)
print(f"  {'ok  ' if st == 201 else 'FAIL'} [{st}] budget raised")

# parent carries 100,000 of its own; the children 250,000 and 400,000.
plan = [(parent_id, 100000), (child_ids[0], 250000), (child_ids[1], 400000)]
for cbs_id, amount in plan:
    st, _ = call("/budget/BudgetLines", method="POST", user=PM, body={
        "budget_ID": budget_id, "cbs_ID": cbs_id, "category": "MPR",
        "amount": amount})
    results.append(st == 201)
    print(f"  {'ok  ' if st == 201 else 'FAIL'} [{st}] line of {amount:,}")

head("8. A draft budget is not budget")
# The same rule the daily log obeys: a draft is a claim, not a fact. Rolling up
# now must leave the tree at zero, because nobody has stood behind these lines.
result = check(200, "rolled up while the budget is still a draft", *call(
    f"/project/CBS({parent_id})/ProjectService.rollUpBudget", method="POST",
    user=PM, body={}))
s, draft_parent = call(f"/project/CBS({parent_id})?$select=budgetAmount", user=PM)
same("the parent stays at nothing", draft_parent.get("budgetAmount"), "0.00")
yes("and the 999,999 it was created claiming is gone",
    Decimal(str(draft_parent.get("budgetAmount"))) != Decimal("999999"))

head("9. Activate the budget, and the tree follows")
check(200, "budget activated", *call(
    f"/budget/Budgets(ID={budget_id},IsActiveEntity=false)/BudgetService.draftActivate",
    method="POST", user=PM, body={}))

result = check(200, "rolled up", *call(
    f"/project/CBS({parent_id})/ProjectService.rollUpBudget", method="POST",
    user=PM, body={}))
yes("the action reports correcting what disagreed",
    "corrected" in str(result).lower())

s, parent = call(f"/project/CBS({parent_id})?$select=ownAmount,budgetAmount", user=PM)
s, c1 = call(f"/project/CBS({child_ids[0]})?$select=ownAmount,budgetAmount", user=PM)
s, c2 = call(f"/project/CBS({child_ids[1]})?$select=ownAmount,budgetAmount", user=PM)

same("child 1 is its own line", c1.get("budgetAmount"), "250000.00")
same("child 2 is its own line", c2.get("budgetAmount"), "400000.00")
same("the parent's own budget is its own line only", parent.get("ownAmount"), "100000.00")
same("the parent rolls up to itself plus both children",
     parent.get("budgetAmount"), "750000.00")
yes("the 999,999 it claimed on creation is gone",
    Decimal(str(parent.get("budgetAmount"))) != Decimal("999999"))

head("10. A line moved is a roll-up changed")
s, lines = call(f"/budget/BudgetLines?$filter=cbs_ID eq {child_ids[0]} "
                "and IsActiveEntity eq true&$select=ID", user=PM)
line_id = lines["value"][0]["ID"]
check(200, "child 1's line doubled", *call(
    f"/budget/BudgetLines(ID={line_id},IsActiveEntity=true)", method="PATCH",
    user=PM, body={"amount": 500000}))
check(200, "rolled up again", *call(
    f"/project/CBS({parent_id})/ProjectService.rollUpBudget", method="POST",
    user=PM, body={}))
s, parent2 = call(f"/project/CBS({parent_id})?$select=budgetAmount", user=PM)
same("the parent follows its lines", parent2.get("budgetAmount"), "1000000.00")

head("11. An approval band is read in its own currency")
# The discriminator is chosen so the converted and unconverted amounts land in
# different bands. 10,000 AED is 2,531.65 EUR, which sits under a 3,000 EUR
# threshold - while the bare number 10,000 sits well over it. Before the fix
# the engine compared the bare number and picked the wrong approver.
s, objs = call("/authorization/AuthObjects?$select=ID,entityName"
               "&$filter=entityName eq 'konstryx.wf.ResourceRequest'&$top=1", user=ADMIN)
s, companies = call("/admin/Companies?$select=ID,code,ccy_code"
                    "&$filter=ccy_code eq 'AED'&$top=1", user=ADMIN)
if not objs.get("value") or not companies.get("value"):
    print("  no auth object or AED company to band against")
else:
    auth_object = objs["value"][0]
    company = companies["value"][0]
    print(f"      banding in EUR, submitting from {company['code']} which trades in "
          f"{company['ccy_code']}")

    # Steps are nested in the one POST and the scheme is then activated.
    # Schemes are draft-enabled, so a scheme created and left alone is a draft
    # the engine cannot see - it reads the base table. Posting the steps
    # separately would leave them as drafts of their own, outside the scheme's
    # composition, and activating the scheme would not bring them with it.
    scheme_id = str(uuid.uuid4())
    st, _ = call("/authorization/ApprovalSchemes", method="POST", user=ADMIN, body={
        "ID": scheme_id, "code": "VER-EUR", "name": "Banded in euro",
        "authObject_ID": auth_object["ID"], "company_ID": company["ID"],
        "isActive": True,
        "steps": [
            {"stepNo": 1, "name": "Under three thousand euro",
             "minAmount": 0.0, "maxAmount": 3000.0, "ccy_code": "EUR",
             "isMandatory": True},
            {"stepNo": 2, "name": "Three thousand euro and over",
             "minAmount": 3000.0, "ccy_code": "EUR", "isMandatory": True},
        ]})
    results.append(st == 201)
    print(f"  {'ok  ' if st == 201 else 'FAIL'} [{st}] scheme banded in EUR, two steps")

    st, _ = call(f"/authorization/ApprovalSchemes(ID={scheme_id},IsActiveEntity=false)"
                 "/AuthorizationService.draftActivate", method="POST", user=ADMIN, body={})
    results.append(st in (200, 201))
    print(f"  {'ok  ' if st in (200, 201) else 'FAIL'} [{st}] scheme activated")

    s, rrs = call("/workflow/ResourceRequests?$select=ID,docNo"
                  "&$filter=IsActiveEntity eq true&$orderby=docNo desc&$top=1", user=ADMIN)
    rr = rrs["value"][0]
    st, msg = call("/collaboration/submitForApproval", method="POST", user=ADMIN, body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
        "docNo": rr["docNo"], "amount": 10000, "companyID": company["ID"]})
    print(f"  {'ok  ' if st == 200 else 'FAIL'} [{st}] {rr['docNo']} submitted at 10,000 AED")
    results.append(st == 200)

    s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{rr['docNo']}'"
                   "&$select=ID,ccy_code&$expand=steps($select=stepNo,name)", user=ADMIN)
    steps = inst["value"][0]["steps"] if inst.get("value") else []
    names = [x["name"] for x in steps]
    print(f"      matched: {names}")
    # Assert the step's NAME, not just its number. A delivered scheme also has
    # a step 1, so matching on the number alone passes whichever scheme won -
    # which is a test agreeing with the code for a reason other than the one
    # under test.
    yes("the euro-banded scheme is the one that was applied",
        len(steps) == 1 and steps[0]["name"] == "Under three thousand euro")
    yes("10,000 AED is read as 2,531 EUR and takes the lower band",
        len(steps) == 1 and steps[0]["stepNo"] == 1)
    yes("the instance records the currency the bands were matched in",
        inst["value"][0].get("ccy_code") == "AED" if inst.get("value") else False)


print()
print("=" * 76)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 76)
sys.exit(0 if passed == len(results) else 1)
