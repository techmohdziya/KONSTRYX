"""How far a reservation has come, against the chain it actually has.

The ten-step chain is drawn for plant. A request for cranes is routed to own
fleet or rental, mobilized onto site under a fifteen-item condition checklist
and taken off under the same one — and mobilization only means something for a
resource that arrives as an instance and leaves again. Ready-mix concrete is
poured. It has no other side, so scoring a material reservation out of ten
counts it against two steps it can never reach, and the more of the thread
that finishes the further behind the row reports itself.

The variation is conditional in the other direction: it joins the chain when
something changes, because a reservation nobody varied has no variation
outstanding.

So the scope is decided per vertical, and every step is read from data:

    RR ADV AVC RES    the thread, from the request forward
    CMT               ERP owns the encumbrance on the WBS
    MOB DMB           the asset steps, and only for asset verticals
    OPL               the daily record: consumption for material,
                      timesheets for manpower, nothing yet for plant
    VAR               a change order against the reservation
    CLS               the closing account

Three outcomes, kept apart. A step is done; or it applies and nobody has done
it; or it applies and nothing in this build can complete it. Only the first two
are anybody's work, and a screen that folds the third into "pending" asks a
coordinator to chase a connector.

The fixture carries one thread of each of the three verticals that have master
data, which is what makes the difference visible in a single payload: the
manpower thread has forty-six signed timesheets and its daily record is done,
the material thread has none and its daily record is waiting, and the plant
thread has no place to keep one at all.
"""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"
USER = "admin"

EQR_RES = "RES-2026-0188"    # tower cranes, generators, portacabins
MR_RES = "RES-2026-0148"     # rebar and cement, procured
MPR_RES = "RES-2026-0162"    # steel fixers and carpenters, own crews and LSC


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
    print(f"  {mark} [{status}] {label}: {str(payload)[:170]}")
    results.append(status == expected)
    return payload


def assert_(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{('  — ' + str(detail)[:130]) if detail else ''}")
    results.append(bool(ok))
    return ok


def same(label, actual, expected):
    ok = str(actual) == str(expected)
    print(f"  {'ok  ' if ok else 'FAIL'} {label} = {expected}"
          f"{'' if ok else '  (got ' + str(actual) + ')'}")
    results.append(ok)
    return ok


def head(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


def overview():
    st, body = call("/workflow/reservationOverview", method="POST", body={})
    if st != 200 or not isinstance(body, dict):
        print(f"  FAIL the overview could not be computed: [{st}] {str(body)[:200]}")
        results.append(False)
        return {}
    return {r["docNo"]: r for r in body.get("value", [])}


def pending_of(row):
    return [s for s in (row.get("pendingSteps") or "").split(" · ") if s]


def blocked_of(row):
    return [s.split(" (")[0] for s in (row.get("blockedSteps") or "").split(" · ") if s]


# ============================================================================
head("1. The overview answers, and every row knows what it is")

rows = overview()
assert_(len(rows) >= 3, "a row per reservation", f"{len(rows)} rows")
for doc in (EQR_RES, MR_RES, MPR_RES):
    assert_(doc in rows, f"{doc} is in the overview")

if not all(d in rows for d in (EQR_RES, MR_RES, MPR_RES)):
    print()
    print(f"  {sum(results)} of {len(results)} checks passed")
    sys.exit(1)

eqr, mr, mpr = rows[EQR_RES], rows[MR_RES], rows[MPR_RES]

same("the plant thread names its vertical", eqr.get("verticalType"), "EQR")
same("the material thread names its vertical", mr.get("verticalType"), "MR")
same("the manpower thread names its vertical", mpr.get("verticalType"), "MPR")

# ============================================================================
head("2. The chain a reservation is scored against is the one its vertical has")

same("plant runs every step but the one nothing triggered", eqr.get("stepsTotal"), 9)
same("and says so", eqr.get("chainScope"), "EQR · 9 of 10 steps apply")

same("material is scored out of seven", mr.get("stepsTotal"), 7)
same("and says how many do not apply", mr.get("chainScope"),
     "MR · 7 of 10 steps apply")
same("manpower likewise", mpr.get("stepsTotal"), 7)

# The variation is the one conditional step: a reservation nobody varied is not
# one with a step outstanding, so it joins the chain when it happens.
for doc, row in rows.items():
    assert_("VAR" not in pending_of(row) and "VAR" not in blocked_of(row),
            f"{doc}: an unvaried reservation is not waiting on a variation",
            row.get("chainScope"))

assert_("MOB" not in pending_of(mr) and "MOB" not in blocked_of(mr),
        "concrete is never mobilized", mr.get("chainScope"))
assert_("DMB" not in pending_of(mr) and "DMB" not in blocked_of(mr),
        "and never comes back off site")
assert_("MOB" in blocked_of(eqr) and "DMB" in blocked_of(eqr),
        "a crane does both, and neither is built",
        eqr.get("blockedSteps"))

# ============================================================================
head("3. The daily record is read, not assumed")

# Forty-six signed timesheets stand behind this reservation's lines. The
# overview called its operation log pending for as long as it was hardcoded.
assert_("OPL" not in pending_of(mpr) and "OPL" not in blocked_of(mpr),
        "manpower keeps its daily record and the overview credits it",
        f"pending: {mpr.get('pendingSteps')}")
assert_("OPL" in pending_of(mr),
        "material has a consumption record to keep and has not kept one",
        f"pending: {mr.get('pendingSteps')}")
assert_("OPL" in blocked_of(eqr),
        "plant has nowhere to keep one yet", eqr.get("blockedSteps"))
assert_("OPL (not built)" in (eqr.get("blockedSteps") or ""),
        "and the row says that is the reason")

# ============================================================================
head("4. What nobody can finish is not reported as work")

for doc, row in rows.items():
    assert_("CMT" in blocked_of(row), f"{doc}: the ERP commitment is blocked, not pending")
    assert_("CMT" not in pending_of(row), f"{doc}: and never appears as somebody's task")
assert_("CMT (ERP connector)" in (eqr.get("blockedSteps") or ""),
        "the reason given is the connector, not an omission",
        eqr.get("blockedSteps"))
assert_(all("MOB" not in pending_of(r) for r in rows.values()),
        "and nothing asks a coordinator to mobilize what cannot be mobilized")

# ============================================================================
head("5. The arithmetic holds on every row")

for doc, row in rows.items():
    done = row.get("stepsDone") or 0
    total = row.get("stepsTotal") or 0
    blocked = row.get("stepsBlocked") or 0
    pending = pending_of(row)
    assert_(done + blocked + len(pending) == total,
            f"{doc}: done + blocked + pending accounts for the whole scope",
            f"{done} + {blocked} + {len(pending)} vs {total}")
    assert_(done <= total, f"{doc}: progress never exceeds its own scope")
    assert_(not set(pending) & set(blocked_of(row)),
            f"{doc}: no step is both waiting and impossible")

same("the plant thread stands at four", eqr.get("stepsDone"), 4)
same("material likewise", mr.get("stepsDone"), 4)
same("manpower is one ahead, on its daily record", mpr.get("stepsDone"), 5)

# ============================================================================
head("6. Closure moves the last step, and the account is the evidence")

res = None
st, body = call(f"/workflow/Reservations?$filter=docNo eq '{MR_RES}'&$select=ID")
if st == 200 and isinstance(body, dict) and body.get("value"):
    res = body["value"][0]["ID"]
assert_(res is not None, "the material reservation is addressable")

assert_("CLS" in pending_of(mr), "its closure is outstanding before it closes")

check(200, "closing it", *call(
    f"/workflow/Reservations({res})/WorkflowService.close", method="POST", body={}))

after = overview().get(MR_RES, {})
same("the closed thread stands at five", after.get("stepsDone"), 5)
same("its scope has not moved", after.get("stepsTotal"), 7)
assert_("CLS" not in pending_of(after), "its closure is no longer outstanding",
        f"pending: '{after.get('pendingSteps')}'")
same("and nothing about the scope became impossible",
     after.get("stepsBlocked"), 1)

# Closing does not retire the day book. This reservation was settled without a
# single consumption record against it, and the overview goes on saying so —
# which is the honest reading, because the closure itself says the same thing.
assert_("OPL" in pending_of(after),
        "a reservation can close with its daily record never kept",
        f"pending: '{after.get('pendingSteps')}'")

closure = []
st, body = call(f"/material/ReservationClosures?$filter=reservationNo eq '{MR_RES}'")
if st == 200 and isinstance(body, dict):
    closure = body.get("value", [])
assert_(len(closure) == 1, "the closure wrote an account, which is what CLS means",
        closure[0] if closure else "none")

print()
print(f"  {sum(results)} of {len(results)} checks passed")
sys.exit(0 if all(results) else 1)
