"""Critical path scheduling: a network with a known answer, checked against it.

    A(3) --FS--> B(2) --FS--> D(4)
    A(3) --FS--> C(5) --FS--> D(4)

Counting calendar days from the project's own start date, day 1 being the
start:

    A  day 1-3       C  day 4-8
    B  day 4-5       D  day 9-12

D waits on the later of B and C, so C drives it. Working back from a finish on
day 12: A, C and D have no float and B has three days of it. That is the whole
point of the calculation and it is what this asserts.

The expected dates are derived from the project rather than written down. A
fixed date here would only assert what the seed happens to hold today, and the
first version of this test failed for exactly that reason while the schedule
itself was correct.
"""
import json, urllib.request, base64, sys
from datetime import date, timedelta

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
    print(f"  {mark} [{status}] {label}: {str(payload)[:150]}")
    results.append(status == expected)
    return payload


def assert_that(label, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}{(' — ' + detail) if detail else ''}")
    results.append(bool(condition))


def head(t):
    print()
    print("=" * 76)
    print(t)
    print("=" * 76)


head("1. A project to schedule")
s, projects = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'PRJ-001'"
                   "&$select=ID,code,startDate")
project = projects["value"][0]
pid = project["ID"]
start = date.fromisoformat(project["startDate"])
day = lambda n: (start + timedelta(days=n - 1)).isoformat()
print(f"      {project['code']} starts {project['startDate']}")

s, wbs = call(f"/project/WBS?$filter=project_ID eq {pid}&$select=ID,code&$top=1")
wid = wbs["value"][0]["ID"]
print(f"      under WBS {wbs['value'][0]['code']}")

head("2. Four activities and the links between them")
made = {}
for code, duration in [("SCH-A", 3), ("SCH-B", 2), ("SCH-C", 5), ("SCH-D", 4)]:
    st, row = call("/project/Activities", method="POST", body={
        "code": code, "name": f"Activity {code}", "project_ID": pid,
        "wbs_ID": wid, "durationDays": duration})
    made[code] = row.get("ID") if isinstance(row, dict) else None
    results.append(st == 201)
    print(f"  {'ok  ' if st == 201 else 'FAIL'} [{st}] {code} ({duration}d)")

for a, b in [("SCH-A", "SCH-B"), ("SCH-A", "SCH-C"), ("SCH-B", "SCH-D"), ("SCH-C", "SCH-D")]:
    st, _ = call("/project/ActivityRelations", method="POST", body={
        "predecessor_ID": made[a], "successor_ID": made[b],
        "linkType": "FS", "lagDays": 0})
    results.append(st == 201)
    print(f"  {'ok  ' if st == 201 else 'FAIL'} [{st}] {a} -> {b}")

head("3. Run the critical path")
check(200, "scheduled", *call(
    f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.schedule",
    method="POST", body={}))

s, acts = call(f"/project/Activities?$filter=project_ID eq {pid}"
               "&$select=code,durationDays,earlyStart,earlyFinish,lateStart,lateFinish,"
               "totalFloat,freeFloat,isCritical&$orderby=code")
by_code = {a["code"]: a for a in acts["value"] if a["code"].startswith("SCH-")}
print()
for code in ["SCH-A", "SCH-B", "SCH-C", "SCH-D"]:
    a = by_code.get(code, {})
    print(f"      {code}  {a.get('durationDays')}d  ES {a.get('earlyStart')}  EF {a.get('earlyFinish')}"
          f"  LS {a.get('lateStart')}  LF {a.get('lateFinish')}"
          f"  TF {a.get('totalFloat')}  {'CRITICAL' if a.get('isCritical') else ''}")

head("4. The dates the network implies")
expected = {
    "SCH-A": (day(1), day(3),  0, True),
    "SCH-B": (day(4), day(5),  3, False),
    "SCH-C": (day(4), day(8),  0, True),
    "SCH-D": (day(9), day(12), 0, True),
}
for code, (es, ef, tf, critical) in expected.items():
    a = by_code.get(code, {})
    assert_that(f"{code} early start {es}", a.get("earlyStart") == es, str(a.get("earlyStart")))
    assert_that(f"{code} early finish {ef}", a.get("earlyFinish") == ef, str(a.get("earlyFinish")))
    assert_that(f"{code} total float {tf}", a.get("totalFloat") == tf, str(a.get("totalFloat")))
    assert_that(f"{code} {'is' if critical else 'is not'} critical",
                bool(a.get("isCritical")) == critical)

head("5. A loop is refused, not scheduled around")
st, _ = call("/project/ActivityRelations", method="POST", body={
    "predecessor_ID": made["SCH-D"], "successor_ID": made["SCH-A"],
    "linkType": "FS", "lagDays": 0})
results.append(st == 201)
status, message = call(
    f"/project/Projects(ID={pid},IsActiveEntity=true)/ProjectService.schedule",
    method="POST", body={})
assert_that("a cyclic network is rejected", status == 400, str(message)[:120])

print()
print("=" * 76)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 76)
sys.exit(0 if passed == len(results) else 1)
