"""The fiscal period grid, and the answer to "which period is this date in".

Every time-phased figure buckets into these periods - cashflow into months,
EVM's planned and earned value into a series, a payment certificate into a
cut-off. Ziya ruled on 2026-08-26 that the IPC follows the fiscal calendar
rather than the contract, so there is one grid per company and not a second
contract-defined one beside it.

Two rules carry the weight. Periods are generated, never keyed, and a set with
a gap in it is rejected whole rather than written - a gap is invisible until
something dated into it drops out of every report. And a closed period cannot
be regenerated over, because closing one is a statement that its numbers are
final.
"""
import json, urllib.request, base64, sys, uuid

BASE = "http://localhost:8090/odata/v4"
USER = "admin"


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
    print(f"  {mark} [{status}] {label}: {str(payload)[:140]}")
    results.append(status == expected)
    return payload


def yes(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    results.append(bool(condition))


def head(t):
    print()
    print("=" * 76)
    print(t)
    print("=" * 76)


head("1. A calendar, and a year generated onto it")
cal = str(uuid.uuid4())
st, _ = call("/admin/FiscalCalendars", method="POST", body={
    "ID": cal, "code": "VER-FY", "name": "Verification calendar",
    "variant": "CALENDAR_MONTH", "startMonth": 1, "isDefault": False})
results.append(st == 201)
print(f"  {'ok  ' if st == 201 else 'FAIL'} [{st}] calendar created")

check(200, "FY2026 generated", *call(
    f"/admin/FiscalCalendars({cal})/AdminService.generate",
    method="POST", body={"fiscalYear": 2026, "replace": False}))

s, periods = call(f"/admin/FiscalPeriods?$filter=calendar_ID eq {cal}"
                  "&$select=name,periodNo,startDate,endDate,status&$orderby=periodNo")
rows = periods.get("value", [])
yes("twelve periods", len(rows) == 12)
for r in rows[:2]:
    print(f"      {r['name']}  {r['startDate']} -> {r['endDate']}  {r['status']}")

head("2. Every day of the year is in exactly one period")
# The property the generator refuses to write without. A gap does not announce
# itself - it swallows whatever is dated into it and reports nothing.
gaps = []
for i in range(1, len(rows)):
    import datetime
    prev_end = datetime.date.fromisoformat(rows[i - 1]["endDate"])
    start = datetime.date.fromisoformat(rows[i]["startDate"])
    if start != prev_end + datetime.timedelta(days=1):
        gaps.append(f"{rows[i-1]['name']} ends {prev_end}, {rows[i]['name']} starts {start}")
yes("no gap and no overlap between consecutive periods", not gaps)
for g in gaps:
    print("      ", g)
yes("the year runs 1 Jan to 31 Dec",
    rows and rows[0]["startDate"] == "2026-01-01" and rows[-1]["endDate"] == "2026-12-31")

head("3. A generated year is not silently regenerated")
check(409, "regenerating without replace is refused", *call(
    f"/admin/FiscalCalendars({cal})/AdminService.generate",
    method="POST", body={"fiscalYear": 2026, "replace": False}))
check(200, "and goes through when it is asked for", *call(
    f"/admin/FiscalCalendars({cal})/AdminService.generate",
    method="POST", body={"fiscalYear": 2026, "replace": True}))

head("4. A closed period cannot be regenerated over")
s, again = call(f"/admin/FiscalPeriods?$filter=calendar_ID eq {cal}"
                "&$select=ID,name&$orderby=periodNo&$top=1")
first = again["value"][0]
check(200, f"{first['name']} closed", *call(
    f"/admin/FiscalPeriods({first['ID']})", method="PATCH",
    body={"status": "CLOSED"}))
# Closing a period says its figures are final. Regenerating would reopen it,
# and a reported month that changes after it was reported is the failure.
check(409, "the year now refuses to regenerate, even with replace", *call(
    f"/admin/FiscalCalendars({cal})/AdminService.generate",
    method="POST", body={"fiscalYear": 2026, "replace": True}))

head("5. A date resolves to its period")
s, co = call("/admin/Companies?$select=ID,code&$top=1")
company = co["value"][0]
# A date resolves against the calendar that governs the company — its own, or
# the group default — and this test's calendar is neither. So the year has to
# exist on the default before the question can be asked: otherwise this checks
# that some earlier suite happened to generate it, which is what it was doing.
s, defaults = call("/admin/FiscalCalendars?$filter=isDefault eq true&$select=ID&$top=1")
for row in defaults.get("value", []):
    call(f"/admin/FiscalCalendars({row['ID']})/AdminService.generate",
         method="POST", body={"fiscalYear": 2026, "replace": False})
st, july = call("/admin/periodFor", method="POST", body={
    "companyID": company["ID"], "onDate": "2026-07-06"})
results.append(st == 200)
if st == 200:
    print(f"      6 Jul 2026 on {company['code']} -> {july['name']} "
          f"({july['startDate']} to {july['endDate']}), {july['status']}")
    yes("July resolves to period 7", july.get("periodNo") == 7)
    yes("and the period brackets the date",
        july["startDate"] <= "2026-07-06" <= july["endDate"])
else:
    print(f"  FAIL [{st}] {july}")

head("6. A date no period covers is refused, not guessed")
check(400, "a date outside every generated year", *call(
    "/admin/periodFor", method="POST", body={
        "companyID": company["ID"], "onDate": "2031-04-01"}))

head("7. A fiscal year that does not start in January")
april = str(uuid.uuid4())
st, _ = call("/admin/FiscalCalendars", method="POST", body={
    "ID": april, "code": "VER-APR", "name": "April year",
    "variant": "CALENDAR_MONTH", "startMonth": 4})
results.append(st == 201)
check(200, "FY2027 generated from April", *call(
    f"/admin/FiscalCalendars({april})/AdminService.generate",
    method="POST", body={"fiscalYear": 2027, "replace": False}))
s, ap = call(f"/admin/FiscalPeriods?$filter=calendar_ID eq {april}"
             "&$select=name,startDate,endDate&$orderby=periodNo")
apr = ap.get("value", [])
if apr:
    print(f"      {apr[0]['name']} {apr[0]['startDate']} -> "
          f"{apr[-1]['name']} {apr[-1]['endDate']}")
# A fiscal year opening in April spans two calendar years and is named for the
# one it ends in, so FY2027 runs April 2026 to March 2027.
yes("FY2027 opens 1 Apr 2026", apr and apr[0]["startDate"] == "2026-04-01")
yes("and closes 31 Mar 2027", apr and apr[-1]["endDate"] == "2027-03-31")

print()
print("=" * 76)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 76)
sys.exit(0 if passed == len(results) else 1)
