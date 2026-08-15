"""Phase 3: the resource build-up, generated from CBS recipes.

The join under test is the one the wireframe specifies: BOQ line -> its CBS
leaf -> every norm keyed to that leaf. Nobody keys resources per BOQ line."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"

BILL = """itemNo;code;description;qty;uom;rate
2.01;CONC-C40;Ready-mix C40 to raft;1200;m3;385.00
2.02;REBAR-HT;High tensile reinforcement;180;t;3150.00
3.01;FORM-WALL;Wall formwork;4400;m2;92.50
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
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] {label}: {str(payload)[:180]}")
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


def make_norm(entity, body, user="steward_infc"):
    s, d = call(f"/masterdata/{entity}", method="POST", body=body, user=user)
    if s != 201:
        return s, d
    return call(f"/masterdata/{entity}(ID={d['ID']},IsActiveEntity=false)"
                "/MasterDataService.draftActivate", method="POST", body={}, user=user)


# ------------------------------------------------------------------- fixtures
s, ps = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'PRJ-002'"
             "&$select=ID,code,company_ID")
project = ps["value"][0]
pid, company_id = project["ID"], project["company_ID"]

call(f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.instantiateCBS",
     method="POST", body={})
s, cbs = call(f"/project/CBS?$filter=project_ID eq {pid}&$select=ID,code,libraryNode_ID"
              "&$orderby=code")
leaves = {c["code"]: c for c in cbs["value"] if c["libraryNode_ID"]}
slab = leaves["02.10"]          # the leaf that will carry the recipe
bare = leaves["01.20"]          # a leaf with no recipe at all

s, d = call("/project/BOQs", method="POST", body={
    "boqId": "BOQ-PLN", "project_ID": pid, "version": "A", "status": "Draft"})
bid = d["ID"]
call(f"/project/BOQs(ID={bid},IsActiveEntity=false)/ProjectService.draftActivate",
     method="POST", body={})
call(f"/project/BOQs(ID={bid},IsActiveEntity=true)/ProjectService.importItems",
     method="POST", body={"fileName": "bill.csv", "content": BILL})
s, items = call(f"/project/BOQItems?$filter=boq_ID eq {bid}&$select=ID,itemNo,qty&$orderby=itemNo")
item = {i["itemNo"]: i for i in items["value"]}

# Map 2.01 to the recipe leaf and 2.02 to the bare one; 3.01 stays unmapped.
call(f"/project/BOQItems(ID={item['2.01']['ID']},IsActiveEntity=true)", method="PATCH",
     body={"cbs_ID": slab["ID"]})
call(f"/project/BOQItems(ID={item['2.02']['ID']},IsActiveEntity=true)", method="PATCH",
     body={"cbs_ID": bare["ID"]})

s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'MT-RMC-C40-20'"
              "&$select=ID")
concrete = res["value"][0]["ID"]
s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-VIB-KIT'"
              "&$select=ID")
vibro = res["value"][0]["ID"]
print(f"  fixtures: BOQ-PLN on {project['code']}, recipe leaf {slab['code']},"
      f" bare leaf {bare['code']}")

head("1. The recipe lives on the CBS leaf, not the BOQ line")
check(200, "group consumption norm on the leaf", *make_norm("ConsumptionRates", {
    "material_ID": concrete, "linkedCBS_ID": slab["libraryNode_ID"],
    "consRate": 1.0, "consUoM": "m3", "wastageAllowancePct": 2.5,
    "effectiveFrom": "2026-01-01", "scope": "GROUP"}))
check(200, "group productivity norm on the leaf", *make_norm("ProductivityRates", {
    "resource_ID": vibro, "linkedCBS_ID": slab["libraryNode_ID"],
    "outputPerHr": 12, "outputUoM": "m3", "crewComposition": "1 OP + 1 HLP",
    "effectiveFrom": "2026-01-01", "scope": "GROUP"}))

msg = check(200, "generated at difficulty 110%", *call(
    f"/project/BOQs(ID={bid},IsActiveEntity=true)/ProjectService.generateBuildUp",
    method="POST", body={"difficultyPct": 110}))
assert_("1 recipe-found" in str(msg) and "1 no-recipe" in str(msg)
        and "1 unmapped" in str(msg),
        "the coverage report matches the mapping", str(msg)[:120])

s, bu = call(f"/project/BOQItemResources?$filter=boqItem_ID eq {item['2.01']['ID']}"
             "&$select=category,qtyPerUom,totalQty,uom,source,basis&$orderby=category")
for r in bu["value"]:
    print(f"        {r['category']:4} {r['qtyPerUom']:>9}/uom  total {r['totalQty']:>10}"
          f" {r['uom']:3} [{r['source']}]  {r['basis']}")

mat = [r for r in bu["value"] if r["category"] == "MR"][0]
eq = [r for r in bu["value"] if r["category"] == "EQR"][0]
assert_(abs(float(mat["totalQty"]) - 1200 * 1.025) < 0.01,
        "material = 1200 x 1.0 x (1 + 2.5% wastage)", mat["totalQty"])
assert_(abs(float(eq["totalQty"]) - 1200 / 12 * 1.1) < 0.05,
        "hours = 1200 / 12 x 110% difficulty — the norm itself untouched",
        eq["totalQty"])
assert_("110%" in eq["basis"] and "crew" in eq["basis"],
        "the basis reads like the daily log: std x difficulty, crew named",
        eq["basis"])

head("2. A company norm overrides the group default")
check(200, "INFC consumption override, 1.05 + 5%", *make_norm("ConsumptionRates", {
    "material_ID": concrete, "linkedCBS_ID": slab["libraryNode_ID"],
    "consRate": 1.05, "consUoM": "m3", "wastageAllowancePct": 5,
    "effectiveFrom": "2026-01-01", "scope": "COMPANY", "owningCompany_ID": company_id}))

# A hand-added exception, before regenerating: it must survive. Created
# through the parent navigation — a composition child has no free-standing
# create of its own.
s, manual = call(f"/project/BOQItems(ID={item['2.01']['ID']},IsActiveEntity=true)/buildUp",
                 method="POST", body={
    "resource_ID": vibro, "category": "EQR",
    "qtyPerUom": 0.01, "totalQty": 12, "uom": "hr", "source": "MANUAL",
    "basis": "hand-added pending recipe"})
assert_(s == 201, "a MANUAL row was added by hand", str(manual)[:90] if s != 201 else "")

msg = check(200, "regenerated", *call(
    f"/project/BOQs(ID={bid},IsActiveEntity=true)/ProjectService.generateBuildUp",
    method="POST", body={"difficultyPct": 110}))
assert_("1 manual kept" in str(msg), "the manual exception is counted, not erased",
        str(msg)[:110])

s, bu = call(f"/project/BOQItemResources?$filter=boqItem_ID eq {item['2.01']['ID']}"
             "&$select=totalQty,source,basis&$orderby=totalQty")
mats = [r for r in bu["value"] if "cons" in (r["basis"] or "")]
assert_(any(abs(float(r["totalQty"]) - 1200 * 1.05 * 1.05) < 0.01 for r in mats),
        "the INFC override (1.05 x 1.05) replaced the group figure",
        str([r["totalQty"] for r in mats]))
assert_(any(r["source"] == "MANUAL" for r in bu["value"]),
        "the MANUAL row is still there after regeneration")

head("3. Two lines on one leaf share one recipe — the governance constraint")
call(f"/project/BOQItems(ID={item['2.02']['ID']},IsActiveEntity=true)", method="PATCH",
     body={"cbs_ID": slab["ID"]})
msg = check(200, "regenerated with 2.02 moved onto the same leaf", *call(
    f"/project/BOQs(ID={bid},IsActiveEntity=true)/ProjectService.generateBuildUp",
    method="POST", body={"difficultyPct": 110}))
assert_("2 recipe-found" in str(msg), "both lines now resolve", str(msg)[:100])

s, bu2 = call(f"/project/BOQItemResources?$filter=boqItem_ID eq {item['2.02']['ID']}"
              "&$select=totalQty,basis")
# 180 t of rebar getting a concrete recipe is exactly the spec-variance trap:
# same leaf, same recipe, wrong content. The system does what the model says;
# the governance rule (distinct leaf per spec) is what prevents nonsense.
assert_(len(bu2["value"]) == 2,
        "line 2.02 received the leaf's recipe — same leaf, same build-up")

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
