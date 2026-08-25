"""Certification of a payment application, checked against the arithmetic.

A certificate is worth what its own parts say it is worth:

    certified gross = claimed gross + adjustment
    retention       = certified gross x retention %
    back charges    = the sum of the back charge lines
    net certified   = certified gross - retention - LD - back charges

Every one of those was a stored number before, so a certificate could state a
net its own back charges contradicted. This asserts the derivation, including
the case where deductions exceed the gross and the certificate goes negative.
"""
import json, urllib.request, base64, sys
from decimal import Decimal

BASE = "http://localhost:8090/odata/v4"
USER = "rohan"          # BudgetController — SubcontractService requires it


def call(path, user=USER, method="GET", body=None):
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
    print(f"  {mark} [{status}] {label}: {str(payload)[:160]}")
    results.append(status == expected)
    return payload


def money(label, actual, expected):
    same = actual is not None and Decimal(str(actual)) == Decimal(expected)
    print(f"  {'ok  ' if same else 'FAIL'} {label} = {expected}"
          f"{'' if same else '  (got ' + str(actual) + ')'}")
    results.append(same)


def head(t):
    print()
    print("=" * 76)
    print(t)
    print("=" * 76)


head("1. An application to certify")
s, apps = call("/subcontract/PaymentApplications?$select=ID,paNo,claimedAmount&$top=1")
app = apps["value"][0]
aid = app["ID"]
print(f"      {app['paNo']} claiming {app['claimedAmount']}")

# The application already carries seeded certificates. Note the highest
# sequence now so the one raised below can be told apart from them - the
# first version of this test took the seeded certificate, which already had
# back charges and four sign-offs, and asserted against it as though it were
# empty.
s, before = call(f"/subcontract/PaymentCertificates?$filter=pa_ID eq {aid}"
                 "&$select=certSeq&$orderby=certSeq desc&$top=1")
prior_seq = before["value"][0]["certSeq"] if before["value"] else 0
print(f"      highest certificate sequence so far: {prior_seq}")

head("2. Raise a certificate at 10% retention")
check(200, "certified", *call(
    f"/subcontract/PaymentApplications({aid})/SubcontractService.certify",
    method="POST", body={"retentionPct": 10}))

s, certs = call(f"/subcontract/PaymentCertificates?$filter=pa_ID eq {aid} "
                f"and certSeq eq {prior_seq + 1}"
                "&$select=ID,certSeq,claimedGross,certifiedGross,retentionPct,"
                "retentionAmount,netCertified,status")
cert = certs["value"][0]
cid = cert["ID"]
claimed = Decimal(str(cert["claimedGross"]))
print(f"      certificate {cert['certSeq']}: gross {cert['certifiedGross']}, "
      f"retention {cert['retentionAmount']}, net {cert['netCertified']}, {cert['status']}")

expected_retention = (claimed * Decimal("10") / Decimal("100")).quantize(Decimal("0.01"))
money("retention at raise", cert["retentionAmount"], str(expected_retention))
money("net at raise", cert["netCertified"], str(claimed - expected_retention))

head("3. Adjustment, liquidated damages and two back charges")
check(200, "adjustment and LD entered", *call(
    f"/subcontract/PaymentCertificates({cid})", method="PATCH",
    body={"adjustment": -5000, "ldApplied": 12000}))

for description, amount in [("Rectification of blockwork", 8000),
                            ("Material supplied on their behalf", 4500)]:
    st, _ = call("/subcontract/BackChargeLines", method="POST", body={
        "pc_ID": cid, "description": description, "cause": "NCR-014",
        "rechargeType": "RCH-LAB-RECT", "amount": amount})
    results.append(st == 201)
    print(f"  {'ok  ' if st == 201 else 'FAIL'} [{st}] back charge {amount}")

head("4. Recalculate, and check every derived figure")
result = check(200, "recalculated", *call(
    f"/subcontract/PaymentCertificates({cid})/SubcontractService.recalculate",
    method="POST", body={}))

s, after = call(f"/subcontract/PaymentCertificates({cid})"
                "?$select=claimedGross,adjustment,certifiedGross,retentionPct,"
                "retentionAmount,ldApplied,backChargeTotal,netCertified")

# Expectations come from the certificate's own inputs and its own back charge
# lines rather than from numbers written here. That asserts the relationship,
# which is the thing that has to hold, and survives whatever the seed carries.
s, lines = call(f"/subcontract/BackChargeLines?$filter=pc_ID eq {cid}&$select=amount")
back = sum((Decimal(str(l["amount"] or 0)) for l in lines["value"]), Decimal("0")).quantize(Decimal("0.01"))

claimed_g = Decimal(str(after["claimedGross"]))
adjustment = Decimal(str(after["adjustment"]))
pct = Decimal(str(after["retentionPct"]))
ld = Decimal(str(after["ldApplied"]))

gross = (claimed_g + adjustment).quantize(Decimal("0.01"))
retention = (gross * pct / Decimal("100")).quantize(Decimal("0.01"))
net = (gross - retention - ld - back).quantize(Decimal("0.01"))

print(f"      claimed {claimed_g}  adjustment {adjustment}  retention {pct}%  "
      f"LD {ld}  back charges {back} over {len(lines['value'])} line(s)")
money("certified gross = claimed + adjustment", after["certifiedGross"], str(gross))
money("retention = certified gross x retention %", after["retentionAmount"], str(retention))
money("back charges = sum of the lines", after["backChargeTotal"], str(back))
money("net = gross - retention - LD - back charges", after["netCertified"], str(net))

head("5. The sign-off chain")
check(200, "quantity surveyor approves", *call(
    f"/subcontract/PaymentCertificates({cid})/SubcontractService.signOff",
    method="POST", body={"role": "Quantity Surveyor", "name": "R Menon",
                         "decision": "Approved"}))
s, c = call(f"/subcontract/PaymentCertificates({cid})?$select=status")
results.append(c.get("status") == "Certified")
print(f"  {'ok  ' if c.get('status') == 'Certified' else 'FAIL'} certificate is {c.get('status')}")

check(200, "commercial manager rejects", *call(
    f"/subcontract/PaymentCertificates({cid})/SubcontractService.signOff",
    method="POST", body={"role": "Commercial Manager", "decision": "Rejected"}))
s, c = call(f"/subcontract/PaymentCertificates({cid})?$select=status")
results.append(c.get("status") == "Rejected")
print(f"  {'ok  ' if c.get('status') == 'Rejected' else 'FAIL'} certificate is {c.get('status')}")

# A rejection is not undone by the next approval in the chain. Anyone can add
# their step, but one refusal holds the certificate until it is dealt with.
check(200, "a later approval does not clear the rejection", *call(
    f"/subcontract/PaymentCertificates({cid})/SubcontractService.signOff",
    method="POST", body={"role": "Project Director", "decision": "Approved"}))
s, c = call(f"/subcontract/PaymentCertificates({cid})?$select=status")
results.append(c.get("status") == "Rejected")
print(f"  {'ok  ' if c.get('status') == 'Rejected' else 'FAIL'} still {c.get('status')}")

s, signoffs = call(f"/subcontract/CertSignOffs?$filter=pc_ID eq {cid}"
                   "&$select=seq,role,name,decision&$orderby=seq")
print()
for so in signoffs["value"]:
    print(f"      {so['seq']}. {str(so['role'])[:24]:26} {str(so['name'])[:16]:18} {so['decision']}")
mine = [so for so in signoffs["value"]
        if so["role"] in ("Quantity Surveyor", "Commercial Manager", "Project Director")]
results.append(len(mine) == 3)
print(f"  {'ok  ' if len(mine) == 3 else 'FAIL'} three sign-offs recorded")

head("6. A certificate is refused what it cannot mean")
check(400, "retention above 100% is refused", *call(
    f"/subcontract/PaymentApplications({aid})/SubcontractService.certify",
    method="POST", body={"retentionPct": 150}))

print()
print("=" * 76)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 76)
sys.exit(0 if passed == len(results) else 1)
