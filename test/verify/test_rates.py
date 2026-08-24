"""Rate master and norms: effective dating that something actually resolves,
company rates beating group rates, and norms that cannot be zero."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"


def call(path, user="steward_infc", method="GET", body=None):
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
            msg = out[:300]
        return e.code, msg


results = []


def check(expected, label, status, payload):
    if isinstance(payload, dict):
        payload = payload.get("value", payload)
    ok = status == expected
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] {label}: {str(payload)[:150]}")
    results.append(ok)
    return payload


def assert_(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}"
          f"{(': ' + str(detail)) if detail != '' else ''}")
    results.append(bool(ok))


def head(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


def activate(entity, eid, user="steward_infc"):
    return call(f"/masterdata/{entity}(ID={eid},IsActiveEntity=false)"
                "/MasterDataService.draftActivate", user=user, method="POST", body={})


head("1. Rates are maintainable — draft, edit, activate")
s, existing = call("/masterdata/Rates?$filter=IsActiveEntity eq true"
                   "&$select=ID,rateValue,effectiveFrom&$expand=resource($select=code)&$top=200")
print(f"      {len(existing['value'])} rates seeded")
for r in existing["value"][:4]:
    print(f"        {r['resource']['code']:14} {r['rateValue']:>12} from {r['effectiveFrom']}")

s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-TWC-12T'"
              "&$select=ID,code")
resource_id = res["value"][0]["ID"]

d = check(201, "a new rate draft", *call("/masterdata/Rates", method="POST", body={
    "resource_ID": resource_id, "rateValue": 1450.00, "netRate": 1400.00,
    "basis": "day", "ccy_code": "AED", "effectiveFrom": "2028-03-01", "scope": "GROUP"}))
check(200, "activated", *activate("Rates", d["ID"]))

head("2. Effective dating is enforced")
d2 = call("/masterdata/Rates", method="POST", body={
    "resource_ID": resource_id, "rateValue": 9999.00, "basis": "day",
    "ccy_code": "AED", "effectiveFrom": "2028-03-01", "scope": "GROUP"})[1]
check(409, "a second rate on the same date in the same scope", *activate("Rates", d2["ID"]))

head("3. Which rate applies on a date — the whole point of effective dating")
s, r = call("/masterdata/rateOn(resourceCode='EQ-TWC-12T',onDate=2026-06-01,companyCode='')")
if s != 200:
    s, r = call("/masterdata/rateOn(resourceCode='EQ-TWC-12T',onDate=2026-06-01)")
check(200, "mid-2026", s, r)
if isinstance(r, dict):
    print(f"        {r.get('rateValue')} {r.get('currency')}/{r.get('basis')}"
          f"  ({r.get('source')})")
    before = r.get("effectiveFrom")

s, r2 = call("/masterdata/rateOn(resourceCode='EQ-TWC-12T',onDate=2028-06-01)")
check(200, "mid-2028, after the rate just entered starts", s, r2)
if isinstance(r2, dict):
    print(f"        {r2.get('rateValue')} {r2.get('currency')}/{r2.get('basis')}"
          f"  ({r2.get('source')})")
    assert_(float(r2.get("rateValue") or 0) == 1450.0
            and str(r2.get("effectiveFrom")) == "2028-03-01",
            "the newly entered rate is the one in force after its start date",
            f"{r2.get('rateValue')} from {r2.get('effectiveFrom')}")

s, r3 = call("/masterdata/rateOn(resourceCode='EQ-TWC-12T',onDate=1999-01-01)")
check(404, "before any rate existed", s, r3)

s, r4 = call("/masterdata/rateOn(resourceCode='NO-SUCH-THING',onDate=2026-06-01)")
check(404, "a resource that does not exist", s, r4)

head("4. A company rate beats a group rate")
s, comp = call("/masterdata/Rates?$filter=IsActiveEntity eq true&$select=ID"
               "&$expand=owningCompany($select=code)&$top=200")
d3 = call("/masterdata/Rates", method="POST", body={
    "resource_ID": resource_id, "rateValue": 1200.00, "basis": "day",
    "ccy_code": "AED", "effectiveFrom": "2028-03-01", "scope": "COMPANY"})[1]
s, msg = activate("Rates", d3["ID"])
print(f"      company-scoped rate activated [{s}]")

s, group = call("/masterdata/rateOn(resourceCode='EQ-TWC-12T',onDate=2028-06-01)")
s2, mine = call("/masterdata/rateOn(resourceCode='EQ-TWC-12T',onDate=2028-06-01,companyCode='INFC')")
if isinstance(group, dict) and isinstance(mine, dict):
    print(f"        no company : {group.get('rateValue')}  ({group.get('scope')})")
    print(f"        INFC       : {mine.get('rateValue')}  ({mine.get('scope')})")
    assert_(group.get("scope") == "GROUP" and mine.get("scope") == "COMPANY",
            "the group rate is returned without a company, the local one with it")
else:
    assert_(False, "company-scoped resolution", f"{group} / {mine}")

head("5. Norms could previously hold anything at all")
s, prod = call("/masterdata/ProductivityRates?$filter=IsActiveEntity eq true"
               "&$select=ID,outputPerHr,effectiveFrom&$top=10")
print(f"      {len(prod.get('value', []))} productivity norms seeded")

d = call("/masterdata/ProductivityRates", method="POST", body={
    "resource_ID": resource_id, "outputPerHr": 0, "outputUoM": "m3",
    "effectiveFrom": "2027-01-01", "scope": "GROUP"})[1]
check(400, "an output of zero", *activate("ProductivityRates", d["ID"]))

d = call("/masterdata/ProductivityRates", method="POST", body={
    "resource_ID": resource_id, "outputPerHr": 12, "outputUoM": "m3", "scope": "GROUP"})[1]
check(400, "a norm with no effective date", *activate("ProductivityRates", d["ID"]))

d = call("/masterdata/ProductivityRates", method="POST", body={
    "outputPerHr": 12, "outputUoM": "m3", "effectiveFrom": "2027-01-01", "scope": "GROUP"})[1]
check(400, "a norm with no resource", *activate("ProductivityRates", d["ID"]))

d = call("/masterdata/ProductivityRates", method="POST", body={
    "resource_ID": resource_id, "outputPerHr": 12, "outputUoM": "m3",
    "effectiveFrom": "2027-01-01", "scope": "GROUP"})[1]
check(200, "a well-formed productivity norm", *activate("ProductivityRates", d["ID"]))

d = call("/masterdata/ProductivityRates", method="POST", body={
    "resource_ID": resource_id, "outputPerHr": 15, "outputUoM": "m3",
    "effectiveFrom": "2027-01-01", "scope": "GROUP"})[1]
check(409, "two norms effective the same day", *activate("ProductivityRates", d["ID"]))

head("6. Consumption norms, and wastage that means something")
s, mat = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'MT-REB-16'"
              "&$select=ID")
material_id = mat["value"][0]["ID"] if mat.get("value") else resource_id

d = call("/masterdata/ConsumptionRates", method="POST", body={
    "material_ID": material_id, "consRate": 1.05, "consUoM": "t",
    "wastageAllowancePct": 140, "effectiveFrom": "2027-01-01", "scope": "GROUP"})[1]
check(400, "140% wastage", *activate("ConsumptionRates", d["ID"]))

d = call("/masterdata/ConsumptionRates", method="POST", body={
    "material_ID": material_id, "consRate": -2, "consUoM": "t",
    "wastageAllowancePct": 5, "effectiveFrom": "2027-01-01", "scope": "GROUP"})[1]
check(400, "a negative consumption rate", *activate("ConsumptionRates", d["ID"]))

d = call("/masterdata/ConsumptionRates", method="POST", body={
    "material_ID": material_id, "consRate": 1.05, "consUoM": "t",
    "wastageAllowancePct": 5, "effectiveFrom": "2027-01-01", "scope": "GROUP"})[1]
check(200, "a well-formed consumption norm", *activate("ConsumptionRates", d["ID"]))

head("7. Class routes the leaf to S/4 — one route per rate, never two")
# Spec §8 / principle P10. Internal cost is quantity x the S/4 activity price
# and posts a journal; external cost is procured and posts through PR -> PO ->
# invoice. A rate carrying both would be costed twice; one carrying neither
# cannot be costed at all. Source is what declares which applies.
s, carp = call("/masterdata/Resources?$filter=IsActiveEntity eq true and "
               "code eq 'MP-CIV-CAR-SK-G1'&$select=ID,code")
carpenter = carp["value"][0]["ID"]

s, carpRates = call(f"/masterdata/Rates?$filter=IsActiveEntity eq true and "
                    f"resource_ID eq {carpenter}&$select=rateValue,source,"
                    "s4ActivityType,effectiveFrom&$expand=vendor($select=name)"
                    "&$orderby=rateValue")
seeded = carpRates["value"]
assert_(len(seeded) == 2,
        "the carpenter is rated twice on the same day — our payroll and Alpha "
        "Civil's — which is the case a resource-only key called a duplicate",
        len(seeded))
hired = [r for r in seeded if r.get("source") == "LSC_HIRED"]
inhouse = [r for r in seeded if r.get("source") == "IN_HOUSE"]
assert_(len(inhouse) == 1 and inhouse[0].get("s4ActivityType") == "LAB-CAR-SK",
        "the in-house row posts against activity type LAB-CAR-SK",
        inhouse[0].get("s4ActivityType") if inhouse else "none")
assert_(len(inhouse) == 1 and float(inhouse[0]["rateValue"]) == 28.50,
        "at AED 28.50/hr, the figure the wireframe's own master carries",
        inhouse[0]["rateValue"] if inhouse else "none")
assert_(len(hired) == 1 and (hired[0].get("vendor") or {}).get("name") == "Alpha Civil LLC",
        "the hired row names the vendor whose contract the rate belongs to",
        (hired[0].get("vendor") or {}).get("name") if hired else "none")
assert_(len(hired) == 1 and not hired[0].get("s4ActivityType"),
        "and carries no activity type — the work is not ours to post internally")


def rate_draft(**over):
    body = {"resource_ID": carpenter, "rateValue": 31.00, "basis": "hr",
            "ccy_code": "AED", "effectiveFrom": "2029-01-01", "scope": "GROUP"}
    body.update(over)
    return call("/masterdata/Rates", method="POST", body=body)[1]


s, alpha = call("/masterdata/Vendors?$filter=bpNumber eq '0002000044'&$select=ID,name")
alpha_id = alpha["value"][0]["ID"]
s, svc = call("/masterdata/Materials?$filter=materialCode eq 'SVC-LAB-STF-G1'&$select=ID")
svc_id = svc["value"][0]["ID"]

d = rate_draft(source="IN_HOUSE", s4ActivityType="LAB-CAR-SK",
               s4ServiceProduct_ID=svc_id)
check(400, "a rate carrying both an activity type and a service product",
      *activate("Rates", d["ID"]))

d = rate_draft(source="IN_HOUSE", s4ActivityType="LAB-CAR-SK", vendor_ID=alpha_id)
check(400, "an in-house rate with a vendor — we are the supplier",
      *activate("Rates", d["ID"]))

d = rate_draft(source="LSC_HIRED", s4ServiceProduct_ID=svc_id)
check(400, "a hired rate that does not say who supplies it",
      *activate("Rates", d["ID"]))

d = rate_draft(source="LSC_HIRED", vendor_ID=alpha_id, s4ActivityType="LAB-CAR-SK")
check(400, "a hired rate costed against an activity type",
      *activate("Rates", d["ID"]))

d = rate_draft(source="LSC_HIRED", vendor_ID=alpha_id, s4ServiceProduct_ID=svc_id)
check(200, "the same rate, routed correctly", *activate("Rates", d["ID"]))
d = rate_draft(source="LSC_HIRED", vendor_ID=alpha_id, s4ServiceProduct_ID=svc_id,
               rateValue=32.00)
check(409, "but not twice from the same vendor on the same day",
      *activate("Rates", d["ID"]))
d = rate_draft(source="IN_HOUSE", s4ActivityType="LAB-CAR-SK", rateValue=33.00)
check(200, "while the in-house rate for that same day is a different row",
      *activate("Rates", d["ID"]))

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
