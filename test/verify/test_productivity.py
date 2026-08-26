"""Output per man-hour, per site location.

    labour hours    = (regular + overtime) x heads present
    output per hour = installed quantity / signed labour hours
    cost per unit   = signed labour cost / installed quantity

A daily log records a shift length and a headcount, not a crew total: 5 heads
for 8 hours is 40 man-hours, not 8. The first version of the handler summed the
raw hours and reported output per hour five times too good - caught because
this test asserts man-hours from what the log means rather than from what the
handler computed.

The metric existed in the spec and was not computable, because a daily log had
nowhere to say where the crew worked. Productivity for a whole project is a
number nobody can act on; per floor it is the one a site is run on.

Two rules this leans on. A draft day is not hours - the same rule signing and
consumption already obey. And a location with hours but nothing measured is
returned rather than hidden: it is work being paid for that nothing has yet
claimed, which is the most useful row on the screen.
"""
import json, urllib.request, base64, sys, uuid
from decimal import Decimal

BASE = "http://localhost:8090/odata/v4"
USER = "admin"          # structural edits across project + workflow


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


def new_day(manpower_id, day, heads, reg, ot, location_id):
    """Creates one day at a location, and activates it. Still a draft log."""
    st, row = call("/workflow/Timesheets", method="POST", body={
        "manpowerLine_ID": manpower_id, "workDate": day, "headsPresent": heads,
        "regularHrs": reg, "otHrs": ot, "location_ID": location_id})
    if st != 201 or not isinstance(row, dict):
        return st, None
    st, _ = call(f"/workflow/Timesheets(ID={row['ID']},IsActiveEntity=false)"
                 "/WorkflowService.draftActivate", method="POST", body={})
    return st, (row["ID"] if st in (200, 201) else None)


def rows_for(project_id):
    st, out = call("/workflow/productivity", method="POST",
                   body={"projectID": project_id})
    if st != 200:
        return st, []
    return st, (out.get("value", []) if isinstance(out, dict) else out)


head("1. A project, and a floor to work on")
s, projects = call("/project/Projects?$select=ID,code&$filter=IsActiveEntity eq true"
                   "&$orderby=code&$top=5")
project = projects["value"][0]
print(f"      {project['code']}")

# A project the demo data has not given floors to. The seeded tower is on the
# first project, so this has to be a different one rather than an assumption
# that nothing is seeded anywhere - which is what made the first version of
# this check pass only on an empty database.
bare = next((p for p in projects["value"]
             if not call(f"/project/SiteLocations?$filter=project_ID eq {p['ID']}"
                         "&$select=ID&$top=1")[1].get("value")), None)
if bare:
    print(f"      {bare['code']} has no locations")
    check(400, "a project with no locations cannot report productivity", *call(
        "/workflow/productivity", method="POST", body={"projectID": bare["ID"]}))
else:
    print("      every project already has locations; the refusal is untestable here")

tower = str(uuid.uuid4())
floor = str(uuid.uuid4())
st, _ = call("/project/SiteLocations", method="POST", body={
    "ID": tower, "code": "VER-T9", "name": "Verification tower", "project_ID": project["ID"],
    "level": "L1", "locationType": "BUILDING"})
results.append(st == 201)
st, _ = call("/project/SiteLocations", method="POST", body={
    "ID": floor, "code": "VER-T9-L09", "name": "Verification level 9", "project_ID": project["ID"],
    "parent_ID": tower, "level": "L2", "locationType": "FLOOR",
    "gfa": 1200.0, "uom": "M2"})
results.append(st == 201)
print(f"  {'ok  ' if st == 201 else 'FAIL'} verification tower and level created")

head("2. A crew works the floor, and one day is signed")
s, lines = call("/workflow/ManpowerRequestLines?$select=ID,heads,ratePerHeadDay"
                "&$filter=ratePerHeadDay gt 0&$top=1")
if not lines.get("value"):
    print("  no manpower line carries a rate")
    sys.exit(0)
mp = lines["value"][0]
rate = Decimal(str(mp["ratePerHeadDay"]))
print(f"      crew at {rate}/head-day")

st, signed_day = new_day(mp["ID"], "2026-04-06", 5, 8, 0, floor)
results.append(st in (200, 201))
st, draft_day = new_day(mp["ID"], "2026-04-07", 5, 8, 0, floor)
results.append(st in (200, 201))
print(f"  {'ok  ' if draft_day else 'FAIL'} two days logged on Level 3")

check(200, "the first day signed", *call(
    f"/workflow/Timesheets(ID={signed_day},IsActiveEntity=true)/WorkflowService.sign",
    method="POST", body={}))

head("3. Hours with nothing measured is a row, not a blank")
st, rows = rows_for(project["ID"])
results.append(st == 200)
level3 = next((r for r in rows if r["locationCode"] == "VER-T9-L09"), None)
yes("Level 3 appears", level3 is not None)
if level3:
    # 5 heads x 8 hours = 40 hours; only the signed day counts.
    same("labour hours are the signed day only", level3["labourHours"], "40.00")
    same("one signed day", level3["signedDays"], 1)
    yes("no rate is invented from nothing",
        level3.get("outputPerHour") is None)
    yes("and the screen says why",
        "nothing measured" in str(level3.get("note", "")).lower())
    print(f"      note: {level3.get('note')}")

head("4. Measure some work on that floor")
# An item the demo has not already split across floors, so this suite's
# allocation is the only one pointing at its own level.
s, items = call("/project/BOQItems?$select=ID,itemNo,uom,cumDoneQty"
                "&$filter=IsActiveEntity eq true&$orderby=itemNo&$top=5")
s, taken = call("/project/Allocations?$select=boqItem_ID")
used = {a["boqItem_ID"] for a in taken.get("value", [])}
item = next((i for i in items["value"] if i["ID"] not in used), items["value"][0])
check(200, f"{item['itemNo']} measured at 240 done", *call(
    f"/project/BOQItems(ID={item['ID']},IsActiveEntity=true)", method="PATCH",
    body={"cumDoneQty": 240.0, "uom": "M2"}))

st, _ = call("/project/Allocations", method="POST", body={
    "boqItem_ID": item["ID"], "location_ID": floor,
    "allocPct": 100.0, "template": "TPL-FLOORS",
    "splitBasis": "whole item on this floor"})
results.append(st == 201)
print(f"  {'ok  ' if st == 201 else 'FAIL'} [{st}] the item allocated wholly to Level 3")

head("5. Now it computes, and the draft day still does not count")
st, rows = rows_for(project["ID"])
level3 = next((r for r in rows if r["locationCode"] == "VER-T9-L09"), None)
yes("Level 3 still there", level3 is not None)
if level3:
    hours = Decimal(str(level3["labourHours"]))
    installed = Decimal(str(level3["installedQty"]))
    cost = Decimal(str(level3["labourCost"]))
    same("installed quantity is the allocated share", installed, "240.000")
    same("hours are still the one signed day", hours, "40.00")
    same("output per hour = installed / hours",
         level3["outputPerHour"], (installed / hours).quantize(Decimal("0.0001")))
    same("cost per unit = cost / installed",
         level3["costPerUnit"], (cost / installed).quantize(Decimal("0.01")))
    print(f"      {installed} M2 over {hours} hrs = {level3['outputPerHour']} M2/hr "
          f"at {level3['costPerUnit']}/M2")

head("6. Sign the second day and the rate falls")
before = Decimal(str(level3["outputPerHour"]))
check(200, "second day signed", *call(
    f"/workflow/Timesheets(ID={draft_day},IsActiveEntity=true)/WorkflowService.sign",
    method="POST", body={}))
st, rows = rows_for(project["ID"])
level3 = next((r for r in rows if r["locationCode"] == "VER-T9-L09"), None)
after = Decimal(str(level3["outputPerHour"]))
same("hours doubled", level3["labourHours"], "80.00")
yes(f"the same work over more hours is worse productivity ({before} -> {after})",
    after < before)

head("7. A floor nobody has worked is not reported")
yes("the verification tower carries no hours and no work, so it is left out",
    not any(r["locationCode"] == "VER-T9" for r in rows))

head("8. Every measurement is kept, so a trend exists")
s, snaps = call("/workflow/ProductivitySnapshots?$select=locationCode,takenAt,"
                "labourHours,installedQty,outputPerHour&$orderby=takenAt")
rows = [r for r in snaps.get("value", []) if r["locationCode"] == "VER-T9-L09"]
for r in rows:
    print(f"      {r['takenAt'][:19]}  {r['labourHours']:>6} hrs  "
          f"{r['installedQty']:>8} done  rate {r['outputPerHour']}")
yes("each run left a measurement behind", len(rows) >= 3)
# The whole reason the rows are stored rather than computed on demand: a rate
# on its own says far less than the same rate falling.
rates = [Decimal(str(r["outputPerHour"])) for r in rows if r["outputPerHour"] is not None]
yes("and the kept rates show the fall the live figure cannot",
    len(rates) >= 2 and rates[-1] < rates[0])


print()
print("=" * 76)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 76)
sys.exit(0 if passed == len(results) else 1)
