"""Phase 2: the bill of quantities, the project's own CBS, and the allocation
that joins what was sold to where the cost lands."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"
USER = "demo"

BILL = """itemNo;code;description;qty;uom;rate
2.01;CONC-C40;Ready-mix C40 to raft;1200;m3;385.00
2.02;REBAR-HT;High tensile reinforcement;180;t;3150.00
3.01;FORM-WALL;Wall formwork;4400;m2;92.50
"""

BILL_BAD = """itemNo;code;description;qty;uom;rate
2.01;CONC-C40;Ready-mix C40 to raft;1200;m3;385.00
2.01;DUP;Duplicate item number;10;m3;100.00
3.01;FORM-WALL;Wall formwork;abc;m2;92.50
"""


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
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] {label}: {str(payload)[:165]}")
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


s, ps = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'PRJ-002'"
             "&$select=ID,code,company_ID")
project = ps["value"][0]
pid = project["ID"]
print(f"  using {project['code']} — a project with no CBS of its own yet")

head("1. The project gets its own CBS, copied from the library")
check(200, "instantiated", *call(
    f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.instantiateCBS",
    method="POST", body={}))
check(409, "a second time", *call(
    f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.instantiateCBS",
    method="POST", body={}))

s, cbs = call(f"/project/CBS?$filter=project_ID eq {pid}&$select=code,level,parent_ID,budgetAmount"
              "&$orderby=code")
by_code = {c["code"]: c for c in cbs["value"]}
print(f"      {len(cbs['value'])} nodes:")
for c in cbs["value"]:
    print(f"        {c['level']:3} {c['code']:10} budget {c['budgetAmount']}")
assert_(len(cbs["value"]) >= 3 and any(c["parent_ID"] for c in cbs["value"]),
        "the copy kept its parentage",
        f"{sum(1 for c in cbs['value'] if c['parent_ID'])} of {len(cbs['value'])} parented")

head("2. A bill of quantities, imported and totalled by the system")
d = check(201, "bill created", *call("/project/BOQs", method="POST", body={
    "boqId": "BOQ-001", "project_ID": pid, "version": "A", "status": "Draft",
    "source": "IMPORT"}))
bid = d["ID"]
check(200, "activated", *call(
    f"/project/BOQs(ID={bid},IsActiveEntity=false)/ProjectService.draftActivate",
    method="POST", body={}))

check(200, "dry run", *call(
    f"/project/BOQs(ID={bid},IsActiveEntity=true)/ProjectService.importItems",
    method="POST", body={"fileName": "bill.csv", "content": BILL, "validateOnly": True}))
s, items = call(f"/project/BOQItems?$filter=boq_ID eq {bid}&$select=itemNo")
assert_(len(items.get("value", [])) == 0, "the dry run changed nothing")

check(200, "imported", *call(
    f"/project/BOQs(ID={bid},IsActiveEntity=true)/ProjectService.importItems",
    method="POST", body={"fileName": "bill.csv", "content": BILL, "validateOnly": False}))

s, items = call(f"/project/BOQItems?$filter=boq_ID eq {bid}"
                "&$select=ID,itemNo,qty,uom,rate,amount&$orderby=itemNo")
for i in items["value"]:
    print(f"        {i['itemNo']:6} {str(i['qty']):>10} {str(i['uom'] or ''):4}"
          f" x {str(i['rate']):>10} = {i['amount']}")
expected_total = 1200 * 385.00 + 180 * 3150.00 + 4400 * 92.50
computed = sum(float(i["amount"]) for i in items["value"])
assert_(abs(computed - expected_total) < 0.01,
        "every line amount is qty x rate, computed by the system",
        f"{computed:,.2f}")

s, boq = call(f"/project/BOQs(ID={bid},IsActiveEntity=true)?$select=boqId,contractValue")
assert_(abs(float(boq["contractValue"]) - expected_total) < 0.01,
        "and the header equals the sum of the lines",
        f"{float(boq['contractValue']):,.2f}")

head("3. A bill that does not add up is refused whole")
check(400, "duplicate item number and a non-numeric quantity", *call(
    f"/project/BOQs(ID={bid},IsActiveEntity=true)/ProjectService.importItems",
    method="POST", body={"fileName": "bad.csv", "content": BILL_BAD, "validateOnly": False}))
s, still = call(f"/project/BOQItems?$filter=boq_ID eq {bid}&$select=itemNo")
assert_(len(still["value"]) == 3, "the good bill is untouched",
        f"{len(still['value'])} lines still there")

head("4. Allocation joins the bill to the WBS and the CBS")
s, wbs = call(f"/project/WBS?$filter=project_ID eq {pid}&$select=code&$top=3")
if not wbs.get("value"):
    # A new project has no WBS until someone builds one, which is the realistic
    # order: structure first, then allocate the bill onto it.
    print("      no WBS yet — adding two through the project draft")
    call(f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.draftEdit",
         method="POST", body={"PreserveChanges": True})
    for code, desc in [("PRJ-002.1", "Substructure"), ("PRJ-002.2", "Superstructure")]:
        call(f"/project/Projects(ID={pid},IsActiveEntity=false)/wbsElements",
             method="POST", body={"code": code, "description": desc})
    call(f"/project/Projects(ID={pid},IsActiveEntity=false)/ProjectService.draftActivate",
         method="POST", body={})
    s, wbs = call(f"/project/WBS?$filter=project_ID eq {pid}&$select=code&$top=3")

wbs_codes = [w["code"] for w in wbs["value"]]
assert_(len(wbs_codes) >= 2, "the project has a WBS to allocate onto", str(wbs_codes))
cbs_code = cbs["value"][-1]["code"]
item = [i for i in items["value"] if i["itemNo"] == "2.01"][0]
print(f"      allocating line 2.01 (qty {item['qty']}) to {wbs_codes[0]} / {cbs_code}")

check(200, "700 of 1200", *call(
    f"/project/BOQItems(ID={item['ID']},IsActiveEntity=true)/ProjectService.allocate",
    method="POST", body={"wbsCode": wbs_codes[0], "cbsCode": cbs_code, "qty": 700}))
check(409, "another 700 would over-allocate", *call(
    f"/project/BOQItems(ID={item['ID']},IsActiveEntity=true)/ProjectService.allocate",
    method="POST", body={"wbsCode": wbs_codes[0], "cbsCode": cbs_code, "qty": 700}))
check(200, "the remaining 500", *call(
    f"/project/BOQItems(ID={item['ID']},IsActiveEntity=true)/ProjectService.allocate",
    method="POST", body={"wbsCode": wbs_codes[min(1, len(wbs_codes)-1)],
                         "cbsCode": cbs_code, "qty": 500}))

check(404, "a WBS that is not this project's", *call(
    f"/project/BOQItems(ID={item['ID']},IsActiveEntity=true)/ProjectService.allocate",
    method="POST", body={"wbsCode": "NOT-A-WBS", "cbsCode": cbs_code, "qty": 1}))
check(404, "a CBS node that is not this project's", *call(
    f"/project/BOQItems(ID={item['ID']},IsActiveEntity=true)/ProjectService.allocate",
    method="POST", body={"wbsCode": wbs_codes[0], "cbsCode": "NOPE", "qty": 1}))

head("5. The CBS node carries what was allocated to it")
s, node = call(f"/project/CBS?$filter=project_ID eq {pid} and code eq '{cbs_code}'"
               "&$select=code,budgetAmount")
carried = float(node["value"][0]["budgetAmount"])
expected = 1200 * 385.00
assert_(abs(carried - expected) < 0.01,
        f"{cbs_code} carries the full line priced at the bill rate",
        f"{carried:,.2f} against an expected {expected:,.2f}")

s, allocs = call(f"/project/Allocations?$select=allocQty,allocPct,pctOfItem"
                 f"&$filter=boqItem_ID eq {item['ID']}&$orderby=allocQty")
for a in allocs["value"]:
    print(f"        {str(a['allocQty']):>8}  {a['allocPct']}% of the line"
          f"   cumulative {a['pctOfItem']}%")
assert_(len(allocs["value"]) == 2
        and abs(sum(float(a["allocPct"]) for a in allocs["value"]) - 100.0) < 0.01,
        "the two allocations account for exactly 100% of the line")

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
