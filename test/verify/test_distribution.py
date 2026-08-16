"""WBS distribution by template: one decision covers many lines, the split is
exact to the third decimal, and the last decision visibly wins."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"

BILL = """itemNo;code;description;qty;uom;rate
2.01;CONC-C40;Ready-mix C40 to raft;1200;m3;385.00
2.02;REBAR-HT;High tensile reinforcement;180;t;3150.00
3.01;FORM-WALL;Wall formwork;1000;m2;92.50
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
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] {label}: {str(payload)[:165]}")
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


def distribute(bid, body):
    return call(f"/project/BOQs(ID={bid},IsActiveEntity=true)/ProjectService.distributeToWBS",
                method="POST", body=body)


def allocations_of(item_id):
    s, a = call(f"/project/Allocations?$filter=boqItem_ID eq {item_id}"
                "&$select=allocQty,allocPct,template,splitBasis"
                "&$expand=wbs($select=code)&$orderby=allocQty desc")
    return a.get("value", []) if s == 200 else []


# ------------------------------------------------------------------- fixtures
s, ps = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'PRJ-002'"
             "&$select=ID,code,company_ID")
project = ps["value"][0]
pid = project["ID"]

call(f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.instantiateCBS",
     method="POST", body={})
s, cbs = call(f"/project/CBS?$filter=project_ID eq {pid}&$select=ID,code")
slab = [c for c in cbs["value"] if c["code"] == "02.10"][0]

# Three floors and a single element, through the project draft.
call(f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.draftEdit",
     method="POST", body={"PreserveChanges": True})
for code, desc in [("F1", "Floor 1"), ("F2", "Floor 2"), ("F3", "Floor 3"),
                   ("SUB", "Substructure")]:
    call(f"/project/Projects(ID={pid},IsActiveEntity=false)/wbsElements",
         method="POST", body={"code": code, "description": desc})
call(f"/project/Projects(ID={pid},IsActiveEntity=false)/ProjectService.draftActivate",
     method="POST", body={})

s, d = call("/project/BOQs", method="POST", body={
    "boqId": "BOQ-DST", "project_ID": pid, "version": "A", "status": "Draft"})
bid = d["ID"]
call(f"/project/BOQs(ID={bid},IsActiveEntity=false)/ProjectService.draftActivate",
     method="POST", body={})
call(f"/project/BOQs(ID={bid},IsActiveEntity=true)/ProjectService.importItems",
     method="POST", body={"fileName": "bill.csv", "content": BILL})
s, items = call(f"/project/BOQItems?$filter=boq_ID eq {bid}&$select=ID,itemNo&$orderby=itemNo")
item = {i["itemNo"]: i for i in items["value"]}
for no in ("2.01", "2.02", "3.01"):
    call(f"/project/BOQItems(ID={item[no]['ID']},IsActiveEntity=true)", method="PATCH",
         body={"cbs_ID": slab["ID"]})
print(f"  fixtures: BOQ-DST, 3 lines on {project['code']}, floors F1-F3 + SUB")

head("1. What the engine refuses")
check(400, "an unknown template", *distribute(bid, {
    "template": "TPL-MAGIC", "targets": [{"wbsCode": "SUB"}], "itemNos": []}))
check(400, "TPL-SINGLE with two targets", *distribute(bid, {
    "template": "TPL-SINGLE", "targets": [{"wbsCode": "F1"}, {"wbsCode": "F2"}],
    "itemNos": []}))
check(400, "TPL-FLOORS with one target", *distribute(bid, {
    "template": "TPL-FLOORS", "targets": [{"wbsCode": "F1"}], "itemNos": []}))
check(404, "a WBS that is not this project's", *distribute(bid, {
    "template": "TPL-SINGLE", "targets": [{"wbsCode": "NOT-HERE"}], "itemNos": []}))
check(400, "a zero weight", *distribute(bid, {
    "template": "TPL-FLOORS",
    "targets": [{"wbsCode": "F1", "weight": 0}, {"wbsCode": "F2", "weight": 1}],
    "itemNos": []}))

head("2. TPL-SINGLE: one decision, one line whole")
check(200, "2.02 onto SUB", *distribute(bid, {
    "template": "TPL-SINGLE", "targets": [{"wbsCode": "SUB"}], "itemNos": ["2.02"]}))
allocs = allocations_of(item["2.02"]["ID"])
assert_(len(allocs) == 1 and float(allocs[0]["allocQty"]) == 180.0
        and allocs[0]["wbs"]["code"] == "SUB",
        "180 t landed whole on SUB",
        f"{allocs[0]['allocQty']} on {allocs[0]['wbs']['code']}" if allocs else "none")

head("3. TPL-FLOORS: GFA-weighted, exact to the third decimal")
check(200, "2.01 across F1/F2/F3 at 40/35/25", *distribute(bid, {
    "template": "TPL-FLOORS",
    "targets": [{"wbsCode": "F1", "weight": 40}, {"wbsCode": "F2", "weight": 35},
                {"wbsCode": "F3", "weight": 25}],
    "itemNos": ["2.01"]}))
allocs = allocations_of(item["2.01"]["ID"])
for a in allocs:
    print(f"        {a['wbs']['code']:4} {a['allocQty']:>9}  {a['allocPct']}%  {a['splitBasis']}")
got = {a["wbs"]["code"]: float(a["allocQty"]) for a in allocs}
assert_(got == {"F1": 480.0, "F2": 420.0, "F3": 300.0},
        "1200 split 480/420/300 by the GFA weights", got)
assert_(abs(sum(got.values()) - 1200) < 0.0005, "the sum is the contract quantity exactly")
assert_(all(a["template"] == "TPL-FLOORS" for a in allocs)
        and "GFA-weighted" in allocs[0]["splitBasis"],
        "template and basis are on the rows for the QS to read back")

head("4. Rounding residue lands on the last target, never lost")
check(200, "3.01 (1000 m2) split into thirds", *distribute(bid, {
    "template": "TPL-ZONES",
    "targets": [{"wbsCode": "F1", "weight": 1}, {"wbsCode": "F2", "weight": 1},
                {"wbsCode": "F3", "weight": 1}],
    "itemNos": ["3.01"]}))
allocs = allocations_of(item["3.01"]["ID"])
qtys = sorted(float(a["allocQty"]) for a in allocs)
total = sum(qtys)
print(f"        thirds of 1000: {qtys}")
assert_(abs(total - 1000) < 0.0005,
        "333.333 + 333.333 + 333.334 = 1000.000 — VAL-02 passes to the millimetre",
        total)

head("5. The last decision wins, visibly")
check(200, "2.01 re-distributed 50/50 to F1/F2", *distribute(bid, {
    "template": "TPL-FLOORS",
    "targets": [{"wbsCode": "F1", "weight": 1}, {"wbsCode": "F2", "weight": 1}],
    "itemNos": ["2.01"]}))
allocs = allocations_of(item["2.01"]["ID"])
assert_(len(allocs) == 2 and all(float(a["allocQty"]) == 600.0 for a in allocs),
        "three allocations became two of 600 — replaced, not stacked",
        [float(a["allocQty"]) for a in allocs])

head("6. One decision, every line: the bulk path and the gate")
check(200, "whole bill onto SUB", *distribute(bid, {
    "template": "TPL-SINGLE", "targets": [{"wbsCode": "SUB"}], "itemNos": []}))
s, gate = call(f"/project/Projects(ID={pid},IsActiveEntity=true)"
               "/ProjectService.validateForBudget", method="POST", body={})
rules = {r["ruleId"]: r for r in (gate.get("value") if isinstance(gate, dict) else gate)}
assert_(rules["VAL-02"]["result"] == "Pass",
        "VAL-02 passes: every line's allocations sum to its contract quantity",
        f"{rules['VAL-02']['failing']}/{rules['VAL-02']['linesChecked']} failing")
assert_(rules["VAL-03"]["result"] == "Pass", "VAL-03 passes: every allocation has its WBS")

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
