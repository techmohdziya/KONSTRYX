"""Site execution: signing a day's work, and posting it against the reservation.

Consumption, cost, burn and drift were stored on the reservation line and
derived from nothing, so a line could report a burn its own timesheets
contradicted. Now:

    cost of a day = heads x (regular + overtime) / standard day x head-day rate
    consumed      = the head-days signed for
    burn %        = cost against what was encumbered
    drift         = cost, less those head-days priced at the reserved rate

A draft day is not consumption. That is the rule this leans on hardest, and
it is now literal: Timesheets are draft-enabled so a foreman can correct a day
before standing behind it, so a day has to be activated before it exists as
anything, and only then can it be signed.

Drift is asserted against the reserved rate rather than against a prorated
encumbrance. The first version prorated by consumed/qty, comparing hours to a
quantity measured in heads, and reported a drift of minus four million on a
line worth four hundred thousand - and the test agreed with it, because the
test had been written from the same formula rather than from the meaning.
"""
import json, urllib.request, base64, sys
from decimal import Decimal

BASE = "http://localhost:8090/odata/v4"
USER = "daud"       # SiteEngineer / ResourceCoordinator


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


def new_day(manpower_id, day, heads, reg, ot):
    """Creates one day and activates it.

    Draft creation is two calls, not one: the POST makes the foreman's working
    copy and draftActivate makes it a day. logStatus is not sent - it is
    read-only and defaults to Draft, because what a day's status is follows
    from signing it rather than from what anyone typed.
    """
    st, row = call("/workflow/Timesheets", method="POST", body={
        "manpowerLine_ID": manpower_id, "workDate": day,
        "headsPresent": heads, "regularHrs": reg, "otHrs": ot})
    if st != 201 or not isinstance(row, dict):
        return st, None
    ident = f"ID={row['ID']},IsActiveEntity=false"
    st, active = call(f"/workflow/Timesheets({ident})/WorkflowService.draftActivate",
                      method="POST", body={})
    return st, (row["ID"] if st in (200, 201) else None)


def active(ts_id, select):
    s, row = call(f"/workflow/Timesheets(ID={ts_id},IsActiveEntity=true)?$select={select}")
    return row


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


def head(t):
    print()
    print("=" * 76)
    print(t)
    print("=" * 76)


head("1. A manpower line with a rate, and the reservation behind it")
s, lines = call("/workflow/ManpowerRequestLines?$select=ID,line_ID,heads,ratePerHeadDay"
                "&$filter=ratePerHeadDay gt 0&$top=1")
if not lines.get("value"):
    print("  no manpower line carries a rate; nothing to execute against")
    sys.exit(0)
mp = lines["value"][0]
rate = Decimal(str(mp["ratePerHeadDay"]))
print(f"      manpower line for RR line {mp['line_ID']}, {mp['heads']} heads at {rate}/head-day")

s, rls = call(f"/workflow/ReservationLines?$filter=rrLine_ID eq {mp['line_ID']}"
              "&$select=ID,reservation_ID,qty,uom,dailyRate,encumberedAmount,"
              "consumedToDate,costToDate,burnPct,drift,lineStatus")
if not rls.get("value"):
    print("  that line has no reservation; nothing to post against")
    sys.exit(0)
rl = rls["value"][0]
encumbered = Decimal(str(rl["encumberedAmount"] or 0))
qty = Decimal(str(rl["qty"] or 0))
reserved_rate = Decimal(str(rl["dailyRate"] or 0))
print(f"      reservation line: {qty} {rl['uom']} encumbered at {encumbered}, "
      f"reserved rate {reserved_rate}, currently {rl['lineStatus']}")

head("2. Two days logged, only one signed")
made = []
for day, heads, reg, ot in [("2026-03-02", 6, 8, 2), ("2026-03-03", 6, 8, 0)]:
    st, ident = new_day(mp["ID"], day, heads, reg, ot)
    ok = st in (200, 201) and ident is not None
    results.append(ok)
    made.append(ident)
    print(f"  {'ok  ' if ok else 'FAIL'} [{st}] {day}: {heads} heads, {reg}+{ot} hrs")

# A day arrives as a draft and nothing else. Status is not something the
# creator gets to assert.
first = active(made[0], "logStatus,costAmount")
results.append(first.get("logStatus") == "Draft")
print(f"  {'ok  ' if first.get('logStatus') == 'Draft' else 'FAIL'} "
      f"a new day starts {first.get('logStatus')}, costing {first.get('costAmount')}")

result = check(200, "first day signed", *call(
    f"/workflow/Timesheets(ID={made[0]},IsActiveEntity=true)/WorkflowService.sign",
    method="POST", body={}))

signed = active(made[0], "costAmount,logStatus,signedBy,statusCriticality")
# 6 heads x 10 hours / 8 = 7.5 head-days at the line rate
expected_cost = (Decimal("6") * Decimal("10") / Decimal("8") * rate).quantize(Decimal("0.01"))
same("cost of the signed day", signed["costAmount"], expected_cost)
results.append(signed["logStatus"] == "Signed")
print(f"  {'ok  ' if signed['logStatus'] == 'Signed' else 'FAIL'} status is {signed['logStatus']}, "
      f"signed by {signed['signedBy']}")
results.append(signed.get("statusCriticality") == 3)
print(f"  {'ok  ' if signed.get('statusCriticality') == 3 else 'FAIL'} "
      f"a signed day reads as settled ({signed.get('statusCriticality')})")

head("3. A day cannot be signed twice, nor signed empty")
check(409, "signing twice is refused", *call(
    f"/workflow/Timesheets(ID={made[0]},IsActiveEntity=true)/WorkflowService.sign",
    method="POST", body={}))

st, empty = new_day(mp["ID"], "2026-03-04", 0, 0, 0)
results.append(st in (200, 201) and empty is not None)
check(400, "a day with nobody on it is refused", *call(
    f"/workflow/Timesheets(ID={empty},IsActiveEntity=true)/WorkflowService.sign",
    method="POST", body={}))

# Hours logged against nobody present is the state the screen colours red
# before anyone tries to sign it.
flagged = active(empty, "statusCriticality")
st2, hours_no_heads = new_day(mp["ID"], "2026-03-05", 0, 8, 0)
results.append(st2 in (200, 201))
red = active(hours_no_heads, "statusCriticality")
ok = red.get("statusCriticality") == 1 and flagged.get("statusCriticality") == 0
print(f"  {'ok  ' if ok else 'FAIL'} an empty day is neutral "
      f"({flagged.get('statusCriticality')}), hours against nobody is flagged "
      f"({red.get('statusCriticality')})")
results.append(ok)

head("4. Post consumption — the unsigned day must not count")
check(200, "posted", *call(
    f"/workflow/Reservations({rl['reservation_ID']})/WorkflowService.postConsumption",
    method="POST", body={}))

s, after = call(f"/workflow/ReservationLines({rl['ID']})"
                "?$select=consumedToDate,costToDate,burnPct,drift,lineStatus")

# Only the signed days count.
s, days = call(f"/workflow/Timesheets?$filter=manpowerLine_ID eq {mp['ID']} "
               "and IsActiveEntity eq true"
               "&$select=regularHrs,otHrs,costAmount,logStatus")
signed_days = [d for d in days["value"] if d["logStatus"] in ("Signed", "Posted")]
hours = sum((Decimal(str(d["regularHrs"] or 0)) + Decimal(str(d["otHrs"] or 0))
             for d in signed_days), Decimal("0"))
cost = sum((Decimal(str(d["costAmount"] or 0)) for d in signed_days), Decimal("0")).quantize(Decimal("0.01"))
head_days = (cost / rate).quantize(Decimal("0.001"))
print(f"      {len(signed_days)} signed day(s) of {len(days['value'])} logged: "
      f"{hours} hrs = {head_days} head-days, {cost}")

same("consumed = the signed head-days", after["consumedToDate"], head_days)
same("cost to date = the signed days", after["costToDate"], cost)

burn = Decimal("0") if encumbered == 0 else (cost * Decimal("100") / encumbered).quantize(Decimal("0.01"))
same("burn % = cost against encumbered", after["burnPct"], burn)

# Zero whenever the rate paid equals the rate reserved, which is the point:
# drift reports a rate difference, not progress.
expected_drift = (Decimal("0") if reserved_rate == 0
                  else (cost - head_days * reserved_rate).quantize(Decimal("0.01")))
same("drift = cost less head-days at the reserved rate", after["drift"], expected_drift)
sane = abs(Decimal(str(after["drift"]))) <= max(encumbered, cost)
print(f"  {'ok  ' if sane else 'FAIL'} drift {after['drift']} is within the size of the line")
results.append(sane)
print(f"      line is now {after['lineStatus']}")

head("5. Sign the second day and the numbers move")
check(200, "second day signed", *call(
    f"/workflow/Timesheets(ID={made[1]},IsActiveEntity=true)/WorkflowService.sign",
    method="POST", body={}))
check(200, "posted again", *call(
    f"/workflow/Reservations({rl['reservation_ID']})/WorkflowService.postConsumption",
    method="POST", body={}))
s, second = call(f"/workflow/ReservationLines({rl['ID']})?$select=consumedToDate,costToDate")
moved = Decimal(str(second["consumedToDate"])) > head_days
print(f"  {'ok  ' if moved else 'FAIL'} consumed rose from {head_days} to {second['consumedToDate']} head-days")
results.append(moved)

print()
print("=" * 76)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 76)
sys.exit(0 if passed == len(results) else 1)
