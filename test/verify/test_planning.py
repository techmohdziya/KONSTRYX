"""Planning slice against SPEC-planning-budget.md.

CALC-01 netRate derived and inbound ignored; CALC-02 crew expansion, hours
never divided; CALC-03 difficulty once with its source recorded; CALC-05
budget qty vs contract qty never crossed; IT-08 rate-missing writes no line;
KX-GOV-002 gate including VAL-05, the rule that guards the whole design."""
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


def make_norm(entity, body, user="steward_infc"):
    s, d = call(f"/masterdata/{entity}", method="POST", body=body, user=user)
    if s != 201:
        return s, d
    return call(f"/masterdata/{entity}(ID={d['ID']},IsActiveEntity=false)"
                "/MasterDataService.draftActivate", method="POST", body={}, user=user)


def generate(bid, pct=110):
    return call(f"/project/BOQs(ID={bid},IsActiveEntity=true)/ProjectService.generateBuildUp",
                method="POST", body={"difficultyPct": pct})


def buildup_of(item_id):
    s, bu = call(f"/project/BOQItemResources?$filter=boqItem_ID eq {item_id}"
                 "&$select=ID,category,qtyPerUom,totalQty,uom,unitRate,amountPerUnit,"
                 "totalAmount,source,sourceNorm,difficultyPct,difficultySrc,basis"
                 "&$orderby=basis")
    return bu.get("value", []) if s == 200 else []


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
slab, bare = leaves["02.10"], leaves["01.20"]

s, d = call("/project/BOQs", method="POST", body={
    "boqId": "BOQ-PLN", "project_ID": pid, "version": "A", "status": "Draft"})
bid = d["ID"]
call(f"/project/BOQs(ID={bid},IsActiveEntity=false)/ProjectService.draftActivate",
     method="POST", body={})
call(f"/project/BOQs(ID={bid},IsActiveEntity=true)/ProjectService.importItems",
     method="POST", body={"fileName": "bill.csv", "content": BILL})
s, items = call(f"/project/BOQItems?$filter=boq_ID eq {bid}&$select=ID,itemNo,qty,amount"
                "&$orderby=itemNo")
item = {i["itemNo"]: i for i in items["value"]}
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
s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'MT-REB-16'"
              "&$select=ID")
rebar = res["value"][0]["ID"]
print(f"  fixtures: BOQ-PLN on {project['code']}, recipe leaf {slab['code']}")

head("1. netRate is derived and an inbound value is ignored (CALC-01 / UT-03)")
check(200, "consumption norm asserting netRate 9.999", *make_norm("ConsumptionRates", {
    "material_ID": concrete, "linkedCBS_ID": slab["libraryNode_ID"],
    "consRate": 1.0, "consUoM": "m3", "wastageAllowancePct": 2.5,
    "netRate": 9.999,
    "effectiveFrom": "2026-01-01", "scope": "GROUP"}))
# Filter on the recipe key, not just the material: seeded rows for the same
# material exist with no linkedCBS and a null netRate (they were CSV-loaded and
# never passed through the derivation), and list order is not deterministic.
s, norm = call("/masterdata/ConsumptionRates?$filter=IsActiveEntity eq true"
               f" and material_ID eq {concrete}"
               f" and linkedCBS_ID eq {slab['libraryNode_ID']}"
               "&$select=netRate,wastageAllowancePct",
               user="steward_infc")
stored = norm["value"][0]
assert_(abs(float(stored["netRate"]) - 1.0250) < 0.00005,
        "persisted netRate is 1.0250 — the inbound 9.999 was discarded",
        stored["netRate"])

check(200, "productivity norm with a crew", *make_norm("ProductivityRates", {
    "resource_ID": vibro, "linkedCBS_ID": slab["libraryNode_ID"],
    "outputPerHr": 12, "outputUoM": "m3", "crewComposition": "1 OP + 1 HLP",
    "effectiveFrom": "2026-01-01", "scope": "GROUP"}))

head("2. Rate-missing writes no line (IT-08); pricing rides on the row (B.4)")
msg = check(200, "generated — concrete has no money rate yet", *generate(bid))
assert_("rate-missing" in str(msg) and "1 recipe-found" in str(msg),
        "the gap is counted, not papered over", str(msg)[:120])
bu = buildup_of(item["2.01"]["ID"])
assert_(all(r["category"] != "MR" for r in bu),
        "no material row exists — a silent zero never entered the build-up",
        f"{len(bu)} row(s), categories {[r['category'] for r in bu]}")

check(200, "money rate for the concrete", *make_norm("Rates", {
    "resource_ID": concrete, "rateValue": 285.00, "basis": "m3", "ccy_code": "AED",
    "effectiveFrom": "2026-01-01", "scope": "GROUP"}))
check(200, "regenerated", *generate(bid))
bu = buildup_of(item["2.01"]["ID"])
for r in bu:
    print(f"        {r['category']:4} {r['qtyPerUom']:>8}/uom x {r['unitRate']:>7}"
          f" = {r['amountPerUnit']:>9}/uom  total {r['totalAmount']:>11}"
          f"  [{r['difficultySrc']}] {r['basis'][:44]}")
mr = [r for r in bu if r["category"] == "MR"]
assert_(len(mr) == 1 and abs(float(mr[0]["totalAmount"]) - 1230 * 285) < 0.01,
        "material priced on the row: 1230 x 285 = 350,550",
        mr[0]["totalAmount"] if mr else "no MR row")
assert_(mr and abs(float(mr[0]["amountPerUnit"]) - 1.025 * 285) < 0.001,
        "amountPerUnit = net consumption x unit rate", mr[0]["amountPerUnit"])
assert_(all(r["sourceNorm"] for r in bu),
        "every line names the norm it came from (IT-16)")

head("3. Crew expansion: hours multiplied across the crew, never divided (UT-09)")
eqr = [r for r in bu if r["category"] == "EQR"]
assert_(len(eqr) == 2, "the crew of two produced two demand lines", len(eqr))
hours = sorted(round(float(r["totalQty"]), 1) for r in eqr)
assert_(hours == [110.0, 110.0],
        "each role carries the full 110 crew-hours — expansion, not division",
        hours)
assert_(all(r["difficultySrc"] == "project" for r in eqr)
        and mr[0]["difficultySrc"] == "none",
        "difficulty source recorded: project on hours, none on material (CALC-03)")

head("4. Budget qty scales cost; contract qty keeps revenue (CALC-05)")
revenue_before = float(item["2.01"]["amount"])
check(200, "budgetQty 1250 entered", *call(
    f"/project/BOQItems(ID={item['2.01']['ID']},IsActiveEntity=true)", method="PATCH",
    body={"budgetQty": 1250}))
check(200, "regenerated", *generate(bid))
bu = buildup_of(item["2.01"]["ID"])
mr = [r for r in bu if r["category"] == "MR"][0]
assert_(abs(float(mr["totalQty"]) - 1250 * 1.025) < 0.01,
        "cost quantity now scales by the budget qty: 1250 x 1.025", mr["totalQty"])
s, after = call(f"/project/BOQItems(ID={item['2.01']['ID']},IsActiveEntity=true)"
                "?$select=amount,qty")
assert_(abs(float(after["amount"]) - revenue_before) < 0.01,
        "the revenue amount never moved — the two quantities were not crossed",
        after["amount"])

head("5. A MANUAL exception survives regeneration and is counted")
s, manual = call(f"/project/BOQItems(ID={item['2.01']['ID']},IsActiveEntity=true)/buildUp",
                 method="POST", body={
    "resource_ID": vibro, "category": "EQR", "qtyPerUom": 0.01, "totalQty": 12,
    "uom": "hr", "source": "MANUAL", "basis": "hand-added pending recipe"})
assert_(s == 201, "a MANUAL row was added by hand")
msg = check(200, "regenerated", *generate(bid))
assert_("1 manual kept" in str(msg), "counted every run — the defect list never shrinks",
        str(msg)[:110])

head("6. The gate (KX-GOV-002), including the rule that guards the design")
s, gate = call(f"/project/Projects(ID={pid},IsActiveEntity=true)"
               "/ProjectService.validateForBudget", method="POST", body={})
rows = gate.get("value") if isinstance(gate, dict) else gate
rules = {r["ruleId"]: r for r in rows}
for rid in sorted(rules):
    r = rules[rid]
    print(f"        {rid}  {r['result']:4}  {r['failing']}/{r['linesChecked']}"
          f"  {r['description'][:52]}")
assert_(rules["VAL-01"]["result"] == "Fail" and rules["VAL-01"]["failing"] == 1,
        "VAL-01 fails: 3.01 has no CBS")
assert_(rules["VAL-02"]["result"] == "Fail",
        "VAL-02 fails: nothing is allocated yet")
assert_(rules["VAL-05"]["result"] == "Pass",
        "VAL-05 passes: one material grade per leaf")

check(200, "a second material grade lands on the same leaf", *make_norm("ConsumptionRates", {
    "material_ID": rebar, "linkedCBS_ID": slab["libraryNode_ID"],
    "consRate": 0.11, "consUoM": "t", "wastageAllowancePct": 3,
    "effectiveFrom": "2026-01-01", "scope": "GROUP"}))
s, gate = call(f"/project/Projects(ID={pid},IsActiveEntity=true)"
               "/ProjectService.validateForBudget", method="POST", body={})
rows = gate.get("value") if isinstance(gate, dict) else gate
rules = {r["ruleId"]: r for r in rows}
assert_(rules["VAL-05"]["result"] == "Fail" and rules["VAL-05"]["failing"] == 1,
        "VAL-05 now fails: the leaf is unresolvable with two grades (Part A.3)",
        f"{rules['VAL-05']['failing']} conflicted leaf")

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
