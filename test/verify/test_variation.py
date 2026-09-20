"""Varying a reservation that is already running.

The slab cycle slips and both cranes need thirty more days. Nothing about the
bill has changed and the client is not in the conversation — what has changed
is what the job needs to have locked. Until this existed the only way to record
that was to edit the reservation line, which left no trace that it had ever
said anything else.

    RVO-2026-nnnn   the document, with the before and the after on its line
    reservation     its quantity, rate and lock move together
    budget          the encumbrance it reads is derived, so it follows

Three figures make the lock and the reservation line stores only two. Its
quantity is heads or instances, its rate is per day, and the duration is
whatever the approved lock divided by the two comes to — eight steel fixers at
520 holding 416,000 is a hundred days. Reading that back is what lets a rate
correction leave the duration alone instead of collapsing the lock to one day.

Two rules carry the weight, and both are here.

A variation will not lock less than the line has already spent. The budget
reads the encumbrance as the lock less what has been consumed, so reducing the
lock beneath the spend quietly turns an overrun into free headroom. An overrun
is a cost to explain, not a lock to shrink.

And a variation that varies nothing is refused. It would take a document
number, sit in the chain and read as a change, and contain only a narrative.

This is the last step of the ten-step chain that was unbuilt outside the plant
block, so the overview is checked too: a reservation nobody varied is not one
with a step outstanding, and varying it makes the chain one step longer rather
than one step further behind.
"""
import json, urllib.request, base64, sys
from decimal import Decimal

BASE = "http://localhost:8090/odata/v4"
USER = "admin"

MPR_RES = "RES-2026-0162"    # steel fixers and carpenters, five lines, part spent
MR_RES = "RES-2026-0148"     # rebar and cement


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
    print(f"  {mark} [{status}] {label}: {str(payload)[:190]}")
    results.append(status == expected)
    return payload


def assert_(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{('  — ' + str(detail)[:130]) if detail else ''}")
    results.append(bool(ok))
    return ok


def same(label, actual, expected):
    try:
        ok = actual is not None and Decimal(str(actual)) == Decimal(str(expected))
    except Exception:
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


def rows(path):
    st, body = call(path)
    return body.get("value", []) if st == 200 and isinstance(body, dict) else []


def reservation_id(doc_no):
    got = rows(f"/workflow/Reservations?$filter=docNo eq '{doc_no}'&$select=ID")
    return got[0]["ID"] if got else None


def line_of(res_id, line_no):
    """The reservation line carrying that request line number."""
    for line in rows(f"/workflow/ReservationLines?$filter=reservation_ID eq {res_id}"
                     "&$expand=rrLine($select=lineNo)"):
        rr = line.get("rrLine") or {}
        if rr.get("lineNo") == line_no:
            return line
    return None


def overview_row(doc_no):
    st, body = call("/workflow/reservationOverview", method="POST", body={})
    if st != 200 or not isinstance(body, dict):
        return {}
    for row in body.get("value", []):
        if row.get("docNo") == doc_no:
            return row
    return {}


def vary(res_id, **body):
    return call(f"/workflow/Reservations({res_id})/WorkflowService.vary",
                method="POST", body=body)


PRJ1_BUDGET = "38000000-0000-0000-0000-000000000001"


def control_record():
    """What the budget is holding: encumbered, committed and actual, summed."""
    lines = rows(f"/budget/BudgetLines?$filter=budget_ID eq {PRJ1_BUDGET}"
                 "&$select=encumbered,committed,actual")
    total = lambda f: round(sum(float(r.get(f) or 0) for r in lines), 2)
    return total("encumbered"), total("committed"), total("actual"), len(lines)


# ============================================================================
head("1. The fixture, before anything moves")

res = reservation_id(MPR_RES)
assert_(res is not None, f"{MPR_RES} is addressable")
if res is None:
    print(f"\n  {sum(results)} of {len(results)} checks passed")
    sys.exit(1)

line1 = line_of(res, 1)
assert_(line1 is not None, "line 1 is the own-crew steel fixers")
same("and says how long it is reserved for", line1.get("reservedDays"), "100.00")
same("eight heads", line1.get("qty"), "8.000")
same("at 520 a head-day", line1.get("dailyRate"), "520.00")
same("locking 416,000", line1.get("encumberedAmount"), "416000.00")
same("of which 410,000 is spent", line1.get("costToDate"), "410000.00")
# 416,000 / (8 x 520) — the hundred days nobody stored.
assert_(True, "which is a hundred days at that quantity and rate",
        "416000 / (8 x 520) = 100")

# The control record as the fixture ships it: three columns of zero on
# twenty-one lines, against a project that has already spent three hundred
# thousand on signed hours. Derived figures, recomputed only when somebody
# pressed a button, and nobody had.
control_before = control_record()
assert_(control_before[3] > 0, "the project carries a budget",
        f"{control_before[3]} lines")
same("holding no encumbrance", control_before[0], 0)
same("and no actual at all", control_before[2], 0)

before = overview_row(MPR_RES)
same("and the chain is seven steps long", before.get("stepsTotal"), 7)
assert_("VAR" not in (before.get("pendingSteps") or ""),
        "a reservation nobody varied is not one with a variation outstanding",
        f"pending: {before.get('pendingSteps')}")

# ============================================================================
head("2. A variation that varies nothing is not a document")

check(400, "the same quantity at the same rate", *vary(
    res, lineNo=1, newQty=8, newRate=520, reason="DURATION",
    narrative="Nothing changed."))
check(400, "no figure given at all", *vary(
    res, lineNo=1, reason="DURATION", narrative="Nothing changed."))
check(400, "the same duration restated", *vary(
    res, lineNo=1, newDurationDays=100, reason="DURATION",
    narrative="Still a hundred days."))
check(400, "a reason nobody can act on", *vary(
    res, lineNo=1, newQty=10, reason="BECAUSE", narrative="Extend."))
check(400, "no reason at all", *vary(
    res, lineNo=1, newQty=10, narrative="Extend."))
check(400, "a negative quantity", *vary(
    res, lineNo=1, newQty=-2, reason="QUANTITY", narrative="Typo."))
check(400, "an extension of nothing", *vary(
    res, lineNo=1, extendByDays=0, reason="DURATION", narrative="No change."))
check(400, "the duration said twice", *vary(
    res, lineNo=1, newDurationDays=130, extendByDays=30, reason="DURATION",
    narrative="Both at once."))

# ============================================================================
head("3. A reservation cannot lock less than it has already spent")

# 410,000 is gone. Two heads at 520 for a hundred days locks 104,000.
check(409, "cutting the line under its own spend", *vary(
    res, lineNo=1, newQty=2, reason="SCOPE",
    narrative="Crew released early."))
check(409, "and cancelling it outright is the same act", *vary(
    res, lineNo=1, newQty=0, reason="CANCELLATION",
    narrative="Crew off the job."))
check(409, "shortening it past the spend, likewise", *vary(
    res, lineNo=1, newDurationDays=40, reason="DURATION",
    narrative="Crew off after week six."))

still = line_of(res, 1)
same("the line is untouched by a refusal", still.get("encumberedAmount"), "416000.00")
same("its rate too", still.get("dailyRate"), "520.00")

# ============================================================================
head("4. Extending the line: the lock moves and the history is kept")

msg = check(200, "ten heads instead of eight", *vary(
    res, lineNo=1, newQty=10, reason="QUANTITY",
    narrative="Slab cycle slipped; two more steel fixers to hold the pour date.",
    effectiveFrom="2026-08-24"))
assert_("RVO-" in str(msg), "it issued a variation number", msg)
assert_("100" in str(msg), "and the message names the duration it kept", msg)

after = line_of(res, 1)
same("the line now carries ten heads", after.get("qty"), "10.000")
same("at the rate it already had", after.get("dailyRate"), "520.00")
same("and locks 520,000 — the same hundred days", after.get("encumberedAmount"),
     "520000.00")
same("the spend is untouched", after.get("costToDate"), "410000.00")
# 410,000 of 520,000 — the same money against a bigger lock is a smaller share.
same("burn falls because the denominator grew", after.get("burnPct"), "78.85")

vars_ = rows(f"/workflow/ReservationVariations?$filter=reservationNo eq '{MPR_RES}'")
assert_(len(vars_) == 1, "one variation stands against the reservation", len(vars_))
v = vars_[0] if vars_ else {}
same("it is applied, not proposed", v.get("status"), "Applied")
same("its reason is the one given", v.get("reason"), "QUANTITY")
same("it asks the budget for 104,000 more", v.get("deltaAmount"), "104000.00")
same("effective from the date given", v.get("effectiveFrom"), "2026-08-24")
assert_(v.get("projectCode") == "PRJ-001", "it names its project", v.get("projectCode"))
assert_(v.get("verticalType") == "MPR", "and the vertical it varies",
        v.get("verticalType"))
same("an increase is coloured as one", v.get("deltaCriticality"), 1)

vl = rows(f"/workflow/ReservationVariationLines?$filter=variationNo eq '{v.get('docNo')}'")
assert_(len(vl) == 1, "with one line", len(vl))
l = vl[0] if vl else {}
same("the quantity it came from", l.get("qtyBefore"), "8.000")
same("and went to", l.get("qtyAfter"), "10.000")
same("the rate it came from", l.get("rateBefore"), "520.00")
same("the duration it kept", l.get("daysAfter"), "100.00")
same("the lock it came from", l.get("encumberedBefore"), "416000.00")
same("and went to", l.get("encumberedAfter"), "520000.00")
same("the difference between them", l.get("delta"), "104000.00")

# ============================================================================
head("5. The budget hears about it without being asked")

# The variation is a chain event, and the control record is derived from the
# chain. Nothing here presses refresh.
control_after = control_record()
assert_(control_after[2] > 0,
        "a chain event brings the control record current",
        f"actual {control_before[2]} -> {control_after[2]}")

# And what the event produced is exactly what the button produces. If these
# ever disagree, one of the two paths is computing the budget differently from
# the other, which is worse than the staleness this replaced.
check(200, "refreshing explicitly on top", *call(
    f"/budget/Budgets(ID={PRJ1_BUDGET},IsActiveEntity=true)"
    "/BudgetService.refreshControl", method="POST", body={}))
same("changes nothing", control_record(), control_after)

# The control record could not always place what a project had spent, and said
# nothing about it. Two different reasons, and the refresh now names both:
#
#   the budget has no line for that cost node and cost nature — adding one
#   would fix it, and the money is already gone while it reads available
#
#   certified subcontract value, which has nowhere to go at all: a subcontract
#   names a project and neither a WBS nor a CBS, so there is no assignment to
#   place it by. The period report counts it as actual cost regardless, so the
#   two screens disagree about what a project has spent by exactly this much
msg = str(check(200, "the refresh says what it could not place", *call(
    f"/budget/Budgets(ID={PRJ1_BUDGET},IsActiveEntity=true)"
    "/BudgetService.refreshControl", method="POST", body={})))

spent = 0.0
for line in rows("/workflow/ReservationLines?$select=costToDate"):
    spent += float(line.get("costToDate") or 0)
assert_(spent > 0, "the project has spent something on its reservations",
        f"{spent:,.2f}")

placed, _, actual, _ = control_record()
assert_(actual < spent,
        "and the control record carries less of it than was spent",
        f"{actual:,.2f} of {spent:,.2f}")
assert_("charged nowhere" in msg,
        "so the refusal to place the rest is stated, not silent",
        msg[-260:])

# ============================================================================
head("6. Reducing is allowed down to the spend, and no further")

# Line 2: four heads at 654.45 for a hundred days, locking 261,780, all spent.
line2 = line_of(res, 2)
same("line 2 has spent every fils it locked", line2.get("costToDate"), "261780.00")
check(409, "so it cannot be reduced at all", *vary(
    res, lineNo=2, newQty=3, reason="SCOPE", narrative="One head off."))

# Line 1 now locks 520,000 against 410,000 spent. Nine heads for the same
# hundred days locks 468,000, still above the spend, so it stands.
msg = check(200, "line 1 back to nine, which still covers what it spent", *vary(
    res, lineNo=1, newQty=9, reason="SCOPE",
    narrative="One of the two extra fixers reassigned to Level 4."))
assert_("returning" in str(msg) and "gets it back" in str(msg),
        "and the message says the budget gets money back", msg)

back = line_of(res, 1)
same("the line locks 468,000", back.get("encumberedAmount"), "468000.00")

vars_ = rows(f"/workflow/ReservationVariations?$filter=reservationNo eq '{MPR_RES}'"
             "&$orderby=docNo")
assert_(len(vars_) == 2, "two variations now stand against the reservation", len(vars_))
release = vars_[-1] if len(vars_) == 2 else {}
same("the second gives 52,000 back", release.get("deltaAmount"), "-52000.00")
same("and is coloured as a release", release.get("deltaCriticality"), 3)

# ============================================================================
head("7. A rate correction is a different event from a duration change")

# Line 2 is fully spent, so only an increase stands. 4 x 700 x 100 = 280,000.
check(200, "the LSC rate on line 2 was re-agreed upward", *vary(
    res, lineNo=2, newRate=700, reason="RATE",
    narrative="Alpha Civil rate re-agreed at 700 a head-day from 01 Aug."))
line2 = line_of(res, 2)
same("the quantity did not move", line2.get("qty"), "4.000")
same("the rate did", line2.get("dailyRate"), "700.00")
same("and the hundred days came through untouched",
     line2.get("encumberedAmount"), "280000.00")

# Same line, thirty more days at the rate it now has: 4 x 700 x 130. Asked as
# an extension, which is how the change actually arrives — nobody outside the
# handler knows the line is reserved for a hundred days to write 130.
check(200, "and thirty more days on top", *vary(
    res, lineNo=2, extendByDays=30, reason="DURATION",
    narrative="Slab cycle slipped; crew held to end November."))
line2 = line_of(res, 2)
same("the lock grows by the days alone", line2.get("encumberedAmount"), "364000.00")
same("the rate is where the correction left it", line2.get("dailyRate"), "700.00")
same("and the quantity never moved", line2.get("qty"), "4.000")

reasons = {r.get("reason") for r in rows(
    f"/workflow/ReservationVariations?$filter=reservationNo eq '{MPR_RES}'")}
assert_(reasons == {"QUANTITY", "SCOPE", "RATE", "DURATION"},
        "four variations, and each says which kind of event it was",
        ", ".join(sorted(reasons)))

# ============================================================================
head("8. A closed line holds nothing left to vary")

# Lines 3 to 5 were closed with the reservation still active.
line5 = line_of(res, 5)
same("line 5 is closed", line5.get("lineStatus"), "Closed")
check(409, "so it cannot be varied", *vary(
    res, lineNo=5, newRate=210, reason="RATE", narrative="Rate re-agreed."))

# ============================================================================
head("9. The chain counts a variation once it exists")

now = overview_row(MPR_RES)
same("the chain is one step longer than it was", now.get("stepsTotal"), 8)
same("and one step further on", now.get("stepsDone"), 6)
assert_("VAR" not in (now.get("pendingSteps") or ""),
        "the variation is not outstanding — it happened",
        f"pending: {now.get('pendingSteps')}")
assert_("VAR" not in (now.get("blockedSteps") or ""),
        "and it is no longer unbuilt", f"blocked: {now.get('blockedSteps')}")

links = rows(f"/workflow/DocumentLinks?$filter=fromDoc eq '{MPR_RES}'"
             "&$select=toDoc,linkType")
assert_(sum(1 for x in links if x["linkType"] == "VARIATION") == 4,
        "and the chain records every variation against the reservation",
        ", ".join(f"{x['linkType']}->{x['toDoc']}" for x in links))

# ============================================================================
head("10. A closed reservation holds nothing left to vary either")

mr = reservation_id(MR_RES)
check(200, f"closing {MR_RES}", *call(
    f"/workflow/Reservations({mr})/WorkflowService.close", method="POST", body={}))
check(409, "varying it afterwards", *vary(
    mr, lineNo=1, newQty=90, reason="QUANTITY", narrative="More rebar."))

check(404, "and a line that does not exist is named as such", *vary(
    res, lineNo=99, newQty=1, reason="SCOPE", narrative="Nowhere."))

head("11. The lock moves by variation, and by no other route")
# Everything above -- the floor at the spend, the before and after on every
# line, the budget hearing about it without being asked -- describes the only
# supported way to change what a reservation holds. It describes nothing at
# all if the amount can simply be written.
locked = rows("/workflow/ReservationLines?$select=ID,encumberedAmount")[0]
st, body = call(f"/workflow/ReservationLines({locked['ID']})", method="PATCH",
                body={"encumberedAmount": 1.0})
assert_(st >= 400, "the encumbrance cannot be written directly", str(st))
held = rows(f"/workflow/ReservationLines?$filter=ID eq {locked['ID']}"
            "&$select=encumberedAmount")[0]
assert_(abs(float(held["encumberedAmount"])
            - float(locked["encumberedAmount"])) < 0.01,
        "and it still holds what the variation left it at",
        str(held.get("encumberedAmount")))

head("12. One decision that moves two lines is one document")
# The slab cycle slips and both cranes stay thirty more days. That is one
# reason, one narrative and one delta against the budget. Moving a line per
# document made it two, and while each was complete and carried its own before
# and after, a reader counting variations counted the decision twice.

open_lines = [ln for ln in (line_of(res, 1), line_of(res, 2))
              if ln and ln.get("lineStatus") != "Closed"]
assert_(len(open_lines) == 2, "lines 1 and 2 are both still open",
        ", ".join(str(ln.get("lineStatus")) for ln in open_lines))

before = {ln["ID"]: (float(ln["encumberedAmount"]), float(ln["reservedDays"]))
          for ln in open_lines}
docs_before = len(rows(f"/workflow/ReservationVariations?$filter=reservation_ID eq {res}"
                       "&$select=ID"))
locked_before = round(sum(float(ln["encumberedAmount"]) for ln in rows(
    f"/workflow/ReservationLines?$filter=reservation_ID eq {res}"
    "&$select=encumberedAmount")), 2)

# A document that cannot be applied in full is not applied at all: every line
# is checked before any is written. Line 5 is closed, so the pair is refused
# and line 1 -- which on its own would have been accepted -- does not move.
check(409, "a list where one line is closed is refused whole", *vary(
    res, lines=[{"lineNo": 1, "extendByDays": 10},
                {"lineNo": 5, "extendByDays": 10}],
    reason="SCOPE", narrative="One good line and one closed one."))
still = line_of(res, 1)
assert_(abs(float(still["encumberedAmount"]) - before[still["ID"]][0]) < 0.01,
        "and the good line in it did not move either",
        f"{still.get('encumberedAmount')} still")
assert_(len(rows(f"/workflow/ReservationVariations?$filter=reservation_ID eq {res}"
                 "&$select=ID")) == docs_before,
        "nor was a document written for it", f"{docs_before} documents")

payload = check(200, "two lines extended by one document", *vary(
    res, lines=[{"lineNo": 1, "extendByDays": 30},
                {"lineNo": 2, "extendByDays": 30}],
    reason="SCOPE", narrative="Slab cycle slipped; both stay thirty more days."))

made = rows(f"/workflow/ReservationVariations?$filter=reservation_ID eq {res}"
            "&$select=docNo,reason,narrative,deltaAmount,createdAt"
            "&$expand=lines($select=daysBefore,daysAfter,encumberedBefore,"
            "encumberedAfter,delta)&$orderby=createdAt desc&$top=1")
assert_(len(rows(f"/workflow/ReservationVariations?$filter=reservation_ID eq {res}"
                 "&$select=ID")) == docs_before + 1,
        "which wrote one document, not two", str(payload)[:120])
doc = made[0] if made else {}
same("carrying both moves on it", len(doc.get("lines") or []), 2)
moved = sum(float(vl["delta"]) for vl in doc.get("lines") or [])
same("and a delta that is their sum", doc.get("deltaAmount"), round(moved, 2))
assert_(doc.get("docNo") and doc["docNo"] in str(payload),
        "the reply names the document it wrote", str(payload)[:150])

for ln in open_lines:
    now = rows(f"/workflow/ReservationLines?$filter=ID eq {ln['ID']}"
               "&$select=encumberedAmount,reservedDays")[0]
    was_amt, was_days = before[ln["ID"]]
    assert_(abs(float(now["reservedDays"]) - (was_days + 30)) < 0.01,
            "each line kept thirty more days", f"{was_days} -> {now['reservedDays']}")
    assert_(float(now["encumberedAmount"]) > was_amt,
            "and locks more for them", f"{was_amt} -> {now['encumberedAmount']}")

locked_after = round(sum(float(ln["encumberedAmount"]) for ln in rows(
    f"/workflow/ReservationLines?$filter=reservation_ID eq {res}"
    "&$select=encumberedAmount")), 2)
same("and what the reservation holds moved by the document's delta, once",
     round(locked_after - locked_before, 2),
     round(float(doc.get("deltaAmount") or 0), 2))

# Two ways of saying which lines move are two answers that can disagree.
check(400, "the list and the single set of figures together are refused", *vary(
    res, lineNo=1, extendByDays=5, lines=[{"lineNo": 2, "extendByDays": 5}],
    reason="SCOPE", narrative="Both shapes."))

check(400, "and one line moved twice in one document", *vary(
    res, lines=[{"lineNo": 1, "extendByDays": 5},
                {"lineNo": 1, "extendByDays": 9}],
    reason="SCOPE", narrative="Twice over."))

links = rows(f"/workflow/DocumentLinks?$filter=fromDoc eq '{MPR_RES}'"
             "&$select=toDoc,linkType")
assert_(sum(1 for x in links if x["linkType"] == "VARIATION") == 5,
        "and the chain gained one link, not one per line",
        ", ".join(x["toDoc"] for x in links if x["linkType"] == "VARIATION"))


print()
print(f"  {sum(results)} of {len(results)} checks passed")
sys.exit(0 if all(results) else 1)
