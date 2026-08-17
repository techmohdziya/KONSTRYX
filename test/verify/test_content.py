"""Delivered content: the starter data a tenant actually receives.

A tenant gets its rows from content packs, never from the CSV fixtures — the
cloud profile sets `initialization-mode: never` so a fixture cannot be imported
into a client schema. That leaves the same dataset expressed twice, and the
failure mode is silent: the packs drift from the fixtures, the deployed tenant
holds slightly different numbers from the ones every other suite asserts, and
nothing anywhere complains.

So this suite pins the two together. The central check is that under the
development profile — where the fixtures are already loaded — every fixture-
derived pack inserts nothing and reports all of its rows as already present.
That can only happen if each pack row matches an existing row on its natural
key, which is a row-by-row equality proof rather than a count comparison.

It also checks the part that seeding exists to switch on: konstryx.auth is a
schema until somebody puts personas and grants in it, and until then
PermissionService resolves nothing and only the Admin scope bypass keeps the
application usable.
"""
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://localhost:8090/odata/v4"
ROOT = Path(__file__).resolve().parent.parent.parent


def call(path, user="demo", method="GET", body=None):
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
            return r.status, json.loads(out)
    except urllib.error.HTTPError as e:
        out = e.read().decode(errors="replace")
        try:
            msg = json.loads(out).get("error", {}).get("message", out)
        except Exception:
            msg = out[:300]
        return e.code, msg


results = []


def assert_(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{(': ' + detail) if detail else ''}")
    results.append(bool(ok))


def check(expected, label, status, payload):
    if isinstance(payload, dict):
        payload = payload.get("value", payload)
    ok = status == expected
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] {label}: {str(payload)[:120]}")
    results.append(ok)
    return payload


def head(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


def rows(path, user="demo"):
    status, payload = call(path, user)
    if status != 200 or not isinstance(payload, dict):
        return status, []
    return status, payload.get("value", [])


# ------------------------------------------------------- packs match the source
head("1. The packs are still the fixtures")

proc = subprocess.run([sys.executable, str(ROOT / "tools" / "build_content_packs.py"),
                       "--check"], capture_output=True, text=True)
assert_(proc.returncode == 0,
        "generated packs are up to date with test/data",
        (proc.stdout + proc.stderr).strip()[:160])

# What each fixture-derived pack must account for. Not a magic number: it is the
# fixture's own row count, and a fixture gaining a row without the packs being
# regenerated is exactly what this is here to catch.
FIXTURE_PACKS = {
    "ORGANISATION": 5,
    "PERSONAS": 139,
    "MASTER_DATA": 145,
    "DEMO_PROJECT": 116,
    "DEMO_USERS": 8,
}
# These two are authored, not generated, and have no fixture — so they insert.
AUTHORED_PACKS = {"NUMBER_RANGES", "APPROVAL_SCHEMES"}

status, packs = rows("/authorization/ContentPacks?$select=packId,version,"
                     "rowsInserted,rowsSkipped&$top=50", "admin")
assert_(status == 200, "the tenant records which packs it has received",
        f"status {status}")
applied = {p["packId"]: p for p in packs}

for pack_id in sorted(set(FIXTURE_PACKS) | AUTHORED_PACKS):
    assert_(pack_id in applied, f"pack {pack_id} applied",
            applied.get(pack_id, {}).get("version", "MISSING"))

for pack_id, expected in FIXTURE_PACKS.items():
    got = applied.get(pack_id, {})
    inserted, skipped = got.get("rowsInserted"), got.get("rowsSkipped")
    # The equality proof. Every row matched something already there, so the pack
    # and the fixture describe the same rows under the same natural keys.
    assert_(inserted == 0 and skipped == expected,
            f"{pack_id} recognised all {expected} fixture rows as already present",
            f"{inserted} inserted, {skipped} left untouched")

# ------------------------------------------------- konstryx.auth is populated
head("2. The persona model has content, so it can actually decide")

EXPECTED_PERSONAS = {
    "daud": {"SITE_ENGINEER", "RESOURCE_COORD"},
    "vikram": {"PROJECT_MANAGER"},
    "rohan": {"COST_ENGINEER"},
    "jin": {"RESOURCE_COORD"},
    "steward_infc": {"MD_STEWARD"},
    "steward_pmi": {"MD_STEWARD"},
    "demo": {"DEMO_ALL"},
}

for user, expected in EXPECTED_PERSONAS.items():
    status, grants = rows("/authorization/EffectivePermissions?$filter=user eq "
                          f"'{user}'&$select=personaCode,authObjectCode&$top=500", "admin")
    seen = {g["personaCode"] for g in grants}
    assert_(status == 200 and seen == expected and len(grants) > 0,
            f"{user} resolves grants through {'+'.join(sorted(expected))}",
            f"{len(grants)} grants via {sorted(seen)}")

status, personas = rows("/authorization/Personas?$select=code,isDelivered,isActive&$top=50",
                        "admin")
delivered = {p["code"] for p in personas if p.get("isDelivered")}
# Five product personas are delivered and protected from deletion; DEMO_ALL is
# demo scaffolding and must not be, or a client tidying up cannot remove it.
assert_(status == 200 and delivered == {"SITE_ENGINEER", "PROJECT_MANAGER",
                                        "COST_ENGINEER", "RESOURCE_COORD", "MD_STEWARD"},
        "the five product personas are flagged delivered, DEMO_ALL is not",
        f"{sorted(delivered)}")
assert_(all(p.get("isActive") is True for p in personas),
        "every seeded persona is active",
        f"{[p['code'] for p in personas if p.get('isActive') is not True]}")

# The bypass must remain a bootstrap route, not the thing holding the app up.
# If these grants resolve, a persona-only user is now decidable without it.
status, grants = rows("/authorization/EffectivePermissions?$select=user&$top=1000", "admin")
assert_(status == 200 and len(grants) > 100,
        "grants exist in bulk — an empty table would refuse every request",
        f"{len(grants)} effective grants across all users")

# ---------------------------------------------------- the grants are enforced
head("3. And the seeded grants are what govern access")

status, seen_all = rows("/workflow/ResourceRequests?$select=docNo,project_ID&$top=50", "demo")
status2, seen_daud = rows("/workflow/ResourceRequests?$select=docNo,project_ID&$top=50", "daud")
assert_(status == 200 and len(seen_all) == 5, "demo's persona reaches both projects",
        f"{len(seen_all)} requests")
assert_(status2 == 200 and len(seen_daud) == 4
        and len({r["project_ID"] for r in seen_daud}) == 1,
        "daud's assignment narrows the same read to one project",
        f"{len(seen_daud)} requests, "
        f"{len({r['project_ID'] for r in seen_daud})} project(s)")

check(403, "daud holds no grant on the rate master", *call("/masterdata/Rates?$top=1", "daud"))
check(200, "the master data steward does", *call("/masterdata/Rates?$top=1", "steward_infc"))

# Two masters share the code EQ-DUP in two legal entities. Each steward must see
# their own and not the other's, which is the company dimension of the grant
# doing the work rather than the code being unique.
for user, owner in [("steward_infc", "20000000-0000-0000-0000-000000000001"),
                    ("steward_pmi", "20000000-0000-0000-0000-000000000002")]:
    status, dup = rows("/masterdata/Resources?$filter=code eq 'EQ-DUP'"
                       "&$select=code,owningCompany_ID", user)
    assert_(status == 200 and len(dup) == 1 and dup[0]["owningCompany_ID"] == owner,
            f"{user} sees only their own company's EQ-DUP",
            f"{len(dup)} row(s)")

# ------------------------------------------------------- the demo thread itself
head("4. The demo thread is complete and reconciles")

status, projects = rows("/project/Projects?$select=code,name,contractValue&$top=10")
by_code = {p["code"]: p for p in projects}
assert_(status == 200 and set(by_code) == {"PRJ-001", "PRJ-002"},
        "both demo projects are present", f"{sorted(by_code)}")
assert_(by_code.get("PRJ-001", {}).get("contractValue") == 47300000.0,
        "Marina Heights carries its contract value",
        str(by_code.get("PRJ-001", {}).get("contractValue")))

for label, path, expected in [
    ("WBS elements", "/project/WBS?$select=code&$top=50", 4),
    ("project CBS nodes", "/project/CBS?$select=code&$top=50", 11),
    ("BOQ items", "/project/BOQItems?$select=itemNo&$top=50", 5),
    ("BOQ build-up lines", "/project/BOQItemResources?$select=category&$top=50", 7),
    ("resource requests", "/workflow/ResourceRequests?$select=docNo&$top=50", 5),
    ("request lines", "/workflow/ResourceRequestLines?$select=lineNo&$top=99", 15),
    ("advisory decisions", "/workflow/AdvisoryDecisions?$select=decision&$top=99", 15),
    ("availability checks", "/workflow/AvailabilityChecks?$select=docNo&$top=50", 3),
    ("reservations", "/workflow/Reservations?$select=docNo&$top=50", 3),
    ("reservation lines", "/workflow/ReservationLines?$select=qty&$top=99", 15),
    ("manpower line detail", "/workflow/ManpowerRequestLines?$select=heads&$top=50", 5),
    ("timesheet entries", "/workflow/Timesheets?$select=regularHrs&$top=50", 5),
]:
    status, got = rows(path)
    assert_(status == 200 and len(got) == expected, f"{expected} {label}",
            f"{len(got)} (status {status})")

# Every transaction now has more than one example, and the three verticals
# reconcile independently. Each figure is the wireframe's own.
THREADS = {
    "RES-2026-0188": (685080.00, "equipment"),
    "RES-2026-0148": (378404.00, "material"),
    "RES-2026-0162": (837380.00, "manpower"),
}
status, res_docs = rows("/workflow/Reservations?$select=ID,docNo&$top=50")
by_doc = {r["docNo"]: r["ID"] for r in res_docs} if status == 200 else {}
grand = 0.0
for doc, (expected, vertical) in THREADS.items():
    rid = by_doc.get(doc)
    st, lines = rows(f"/workflow/ReservationLines?$filter=reservation_ID eq {rid}"
                     f"&$select=encumberedAmount&$top=50") if rid else (0, [])
    got = sum(r["encumberedAmount"] for r in lines)
    grand += got
    assert_(st == 200 and len(lines) == 5 and abs(got - expected) < 0.005,
            f"{doc} ({vertical}) encumbers AED {expected:,.2f} over 5 lines",
            f"{len(lines)} lines, AED {got:,.2f}")
assert_(abs(grand - 1900864.00) < 0.005,
        "the three threads encumber AED 1,900,864.00 in total", f"AED {grand:,.2f}")

status, adv = rows("/workflow/AdvisoryDecisions?$select=decision&$top=99")
counts = {}
for a in (adv if status == 200 else []):
    counts[a["decision"]] = counts.get(a["decision"], 0) + 1
# Equipment routes 2 in-house / 3 procured, material 3 / 2, manpower 3 / 2 — so
# every vertical decides both ways rather than rubber-stamping one route, which
# is the whole point of having an advisory step to demonstrate.
assert_(counts == {"IN_HOUSE": 8, "PROCURE": 7},
        "advisory decides both ways in all three verticals", str(counts))

# The AVC lines are a composition, not an entity set of their own, so they are
# counted through their parent — five per check across the three checks.
status, checks = rows("/workflow/AvailabilityChecks?$expand=lines($select=atpQty)"
                      "&$select=docNo&$top=50")
avc_lines = sum(len(c.get("lines", [])) for c in checks) if status == 200 else 0
assert_(status == 200 and avc_lines == 15,
        "15 availability check lines across the three checks", f"{avc_lines}")

status, avc = rows("/workflow/AvailabilityChecks?$select=docNo,status&$top=50")
cleared = sorted(a["docNo"] for a in avc if a["status"] == "Cleared") if status == 200 else []
assert_(cleared == ["AVC-2026-0148", "AVC-2026-0162", "AVC-2026-0188"],
        "all three availability checks are cleared", str(cleared))

# ------------------------------------------------------- manpower & timesheet
head("4b. Manpower carries what the spine cannot express")

status, mp = rows("/workflow/ManpowerRequestLines?$select=heads,sourceType,ratePerHeadDay,"
                  "durationDays,crewId&$top=50")
if status == 200:
    heads = sum(m["heads"] for m in mp)
    own = [m for m in mp if m["sourceType"] == "OWN"]
    lsc = [m for m in mp if m["sourceType"] == "LSC"]
    assert_(heads == 24, "24 heads across the manpower lines", f"{heads}")
    assert_(len(own) == 3 and len(lsc) == 2,
            "sourced 3 lines from own payroll and 2 from labour subcontract",
            f"{len(own)} own, {len(lsc)} LSC")
    # heads x days x all-in rate must reproduce the encumbrance exactly, or the
    # vertical detail and the cost record are telling different stories.
    derived = sum(m["heads"] * m["durationDays"] * m["ratePerHeadDay"] for m in mp)
    assert_(abs(derived - 837380.00) < 0.005,
            "heads x days x rate reproduces the manpower encumbrance",
            f"AED {derived:,.2f}")
else:
    assert_(False, "manpower lines readable", f"status {status}")

status, tsh = rows("/workflow/Timesheets?$select=headsPresent,regularHrs,otHrs,"
                   "costAmount,logStatus&$top=50")
if status == 200:
    assert_(sum(t["headsPresent"] for t in tsh) == 24
            and sum(t["regularHrs"] for t in tsh) == 192.0
            and sum(t["otHrs"] for t in tsh) == 24.0,
            "the 14 Aug log is 24 heads, 192 regular hours and 24 overtime",
            f"{sum(t['headsPresent'] for t in tsh)} heads, "
            f"{sum(t['regularHrs'] for t in tsh)} + {sum(t['otHrs'] for t in tsh)} hrs")
    cost = sum(t["costAmount"] for t in tsh)
    assert_(abs(cost - 5464.00) < 0.005, "and costs AED 5,464.00", f"AED {cost:,.2f}")
    assert_(all(t["logStatus"] == "Signed" for t in tsh),
            "every logged day is signed, so it may reach S/4",
            str({t["logStatus"] for t in tsh}))
else:
    assert_(False, "timesheets readable", f"status {status}")

# ------------------------------------------------------------ material thread
head("4c. Material runs the same spine as equipment")

status, mr = rows("/workflow/ResourceRequestLines?$select=lineNo,uom,qty,lineStatus"
                  "&$filter=uom eq 't' or uom eq 'bag' or uom eq 'kg' or uom eq 'pc'&$top=50")
assert_(status == 200 and len(mr) == 5,
        "the material request has 5 lines in material units",
        f"{len(mr)} lines: {sorted({r['uom'] for r in mr})}")
# The demo has to show a partially-fulfilled line, not five tidy closed ones —
# that is the state the reservation overview and the GR chase actually exist for.
statuses = {r["lineStatus"] for r in mr} if status == 200 else set()
assert_({"Awaiting balance GR", "PO in transit", "Closed"} <= statuses,
        "and shows partial fulfilment, a PO in transit and closed lines",
        str(sorted(statuses)))

# Equipment is the vertical extension of the same lines; without it the EQR
# thread has no mob window and no vendor, and the demo reads as half a story.
status, eq = rows("/workflow/ResourceRequestLines?$expand=equipment($select=instances,"
                  "sourceType,sourceDetail)&$select=lineNo&$top=50")
with_eq = [line for line in eq if line.get("equipment")]
instances = sum(line["equipment"]["instances"] for line in with_eq)
assert_(status == 200 and len(with_eq) == 5 and instances == 18,
        "all five lines carry their equipment detail, 18 instances in total",
        f"{len(with_eq)} lines, {instances} instances")

# -------------------------------------------------------------- masters present
head("5. Masters are seeded, and still scope-isolated")

# These counts are lower than the seeded row counts by design, and the gap is
# the point: demo is assigned to INFC, so the company-scoped masters owned by
# PMI are filtered out of every read. 64 resource nodes seeded, 2 of them PMI's;
# 12 CBS library nodes seeded, 1 of them PMI's.
for label, path, expected in [
    ("resource nodes visible to an INFC user", "/masterdata/Resources/$count", "75"),
    ("rate master rows", "/masterdata/Rates/$count", "21"),
    ("CBS library nodes minus PMI's", "/masterdata/CBSLibrary/$count", "16"),
    ("vendors incl. the two LSC labour suppliers", "/masterdata/Vendors/$count", "5"),
]:
    status, got = call(path, "demo")
    assert_(status == 200 and str(got).strip() == expected, label,
            f"{str(got).strip()} (expected {expected}, status {status})")

print()
print(f"  {sum(results)} of {len(results)} checks passed")
sys.exit(0 if all(results) else 1)
