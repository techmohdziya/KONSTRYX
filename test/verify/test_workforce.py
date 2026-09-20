"""The workforce masters: the working day, the crew, the gang, and the men.

Four of these are rules rather than fields, and a field-level check would pass
on all of them while every one was wrong: a crew rate that is typed rather than
summed, a gang that reports full manning with a lapsed card on it, a man
engaged twice over the same day, and the same passport on two payrolls."""
import json, urllib.request, urllib.error, base64, sys

BASE = "http://localhost:8090/odata/v4"
STEWARD = "steward_infc"


def call(path, user=STEWARD, method="GET", body=None, pw=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path.replace(" ", "%20"), data=data, method=method)
    req.add_header("Authorization", "Basic " + base64.b64encode(
        f"{user}:{pw or user}".encode()).decode())
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
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] {label}: {str(payload)[:140]}")
    results.append(ok)
    return payload


def assert_(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{(': ' + detail) if detail else ''}")
    results.append(bool(ok))


def head(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


def activate(entity, draft_id, user=STEWARD):
    return call(f"/masterdata/{entity}(ID={draft_id},IsActiveEntity=false)"
                "/MasterDataService.draftActivate", user=user, method="POST", body={})


def new(entity, body, user=STEWARD):
    """Creates a draft and returns its id, without activating it yet."""
    s, d = call(f"/masterdata/{entity}", user=user, method="POST", body=body)
    if s != 201:
        return None, (s, d)
    return d["ID"], None


def child(entity, draft_id, element, body, user=STEWARD):
    return call(f"/masterdata/{entity}(ID={draft_id},IsActiveEntity=false)/{element}",
                user=user, method="POST", body=body)


# A COMPANY-scoped master that names no company is invisible to everyone: the
# scope handler narrows on owningCompany, and null belongs to nobody. Every
# master raised here therefore names the steward's own company.
s_, _companies = call("/admin/Companies?$select=code&$filter=code eq 'INFC'", user="admin")
INFC = (_companies.get("value") or [{}])[0].get("ID") if isinstance(_companies, dict) else None


def owned(body):
    body = dict(body)
    body["scope"] = "COMPANY"
    body["owningCompany_ID"] = INFC
    return body


# --------------------------------------------------------------------------- 1

head("1. The working day, and one overtime ladder rather than four")

pattern_id, err = new("ShiftPatterns", owned({
    "code": "SP-VERIFY-95", "description": "Verification duty day",
    "dutyHours": 9.50, "mandayHours": 8.00, "breakMinutes": 60}))
assert_(pattern_id is not None, "a shift pattern can be raised", str(err))

LADDER = [
    ("OT1", "First overtime", 1.25, 1.40, 9.50, 1),
    ("NIGHT", "Night overtime", 1.50, 1.70, None, 2),
    ("RESTDAY", "Rest day", 1.50, 1.70, None, 3),
    ("HOLIDAY", "Public holiday", 2.50, 2.75, None, 4),
    ("BEYOND12", "Beyond twelve hours", 2.00, 2.20, 12.00, 5),
    ("STANDBY", "Standby", 0.70, 0.80, None, 6),
]
if pattern_id:
    for kind, desc, cost, charge, from_hour, seq in LADDER:
        body = {"kind": kind, "description": desc, "costFactor": cost,
                "chargeFactor": charge, "sequence": seq}
        if from_hour:
            body["fromHour"] = from_hour
        child("ShiftPatterns", pattern_id, "overtimeSteps", body)
    s, d = activate("ShiftPatterns", pattern_id)
    assert_(s in (200, 201), "and activated with its ladder attached", str(d)[:120])

    s, steps = call(f"/masterdata/ShiftPatterns(ID={pattern_id},IsActiveEntity=true)"
                    "/overtimeSteps?$orderby=sequence")
    rungs = steps.get("value", []) if isinstance(steps, dict) else []
    assert_(len(rungs) == 6, "the ladder has all six rungs", f"{len(rungs)} found")

    by_kind = {r["kind"]: r for r in rungs}
    assert_(str(by_kind.get("OT1", {}).get("costFactor")) .startswith("1.25")
            and str(by_kind.get("HOLIDAY", {}).get("costFactor")).startswith("2.5"),
            "first overtime is 1.25 and a public holiday 2.50",
            f"OT1 {by_kind.get('OT1', {}).get('costFactor')}, "
            f"HOLIDAY {by_kind.get('HOLIDAY', {}).get('costFactor')}")

    differing = [r for r in rungs if str(r.get("costFactor")) != str(r.get("chargeFactor"))]
    assert_(len(differing) == 6,
            "cost and charge are separate numbers on every rung, not one number twice",
            f"{len(differing)} of {len(rungs)} differ")

    assert_(str(by_kind.get("STANDBY", {}).get("costFactor")).startswith("0.7"),
            "and a rung may be below 1.0 — standby is paid at less than time",
            str(by_kind.get("STANDBY", {}).get("costFactor")))

# --------------------------------------------------------------------------- 2

head("2. A crew rate is summed from its slots, never typed")

trade_id, err = new("Trades", owned({
    "code": "TR-VERIFY-CON", "description": "Concretor (verification)",
    "discipline": "Civil"}))
assert_(trade_id is not None, "a trade can be raised", str(err))
if trade_id:
    for code, desc, seq in [("G1", "Grade 1", 1), ("G2", "Grade 2", 2)]:
        child("Trades", trade_id, "grades", {"code": code, "description": desc, "sequence": seq})
    child("Trades", trade_id, "certificates", {
        "code": "CRT-LIFT", "description": "Lifting card", "blocking": True})
    s, d = activate("Trades", trade_id)
    assert_(s in (200, 201), "with its grades and a blocking certificate", str(d)[:120])

SLOTS = [(30.00, True), (28.50, False), (28.50, False),
         (24.00, False), (15.50, False), (15.50, False)]
EXPECTED_CREW_RATE = 142.00

crew_id, err = new("CrewTemplates", owned({
    "code": "CRW-VERIFY-POUR", "description": "Concrete pour crew (verification)",
    "outputBasis": "MANDAY_8H", "outputPerDay": 42.200, "outputUoM": "M3",
    "minimumManning": 6, "foremanCountsToOutput": False,
    "mixedSourcingAllowed": True,
    # Typed deliberately, and wrong. The derivation has to overwrite it.
    "crewRatePerHr": 999.99}))
assert_(crew_id is not None, "a crew template can be raised", str(err))
if crew_id:
    for i, (rate, foreman) in enumerate(SLOTS, start=1):
        body = {"slotNo": i, "ratePerHr": rate, "isForeman": foreman}
        if trade_id:
            body["trade_ID"] = trade_id
        child("CrewTemplates", crew_id, "slots", body)
    s, d = activate("CrewTemplates", crew_id)
    assert_(s in (200, 201), "and activated with six slots", str(d)[:120])

    s, crew = call(f"/masterdata/CrewTemplates(ID={crew_id},IsActiveEntity=true)"
                   "?$select=code,crewRatePerHr,minimumManning")
    crew = crew if isinstance(crew, dict) else {}
    derived = float(crew.get("crewRatePerHr") or 0)
    assert_(abs(derived - EXPECTED_CREW_RATE) < 0.01,
            "the crew rate is the sum of its slots",
            f"{derived} against {EXPECTED_CREW_RATE}")
    assert_(abs(derived - 999.99) > 0.01,
            "and the typed 999.99 was replaced rather than kept", str(derived))

# --------------------------------------------------------------------------- 3

head("3. A gang is read against the template it came from")


def a_man(no, passport):
    """A worker who can actually stand in a slot, so manning is not a guess."""
    wid, _ = new("Workers", owned({
        "empNo": no, "fullName": "Gang Member " + no, "passportNo": passport,
        "source": "MAN"}))
    if wid:
        activate("Workers", wid)
    return wid


MEN = [a_man(f"EMP-GANG-{i}", f"PV-GANG-{i:04d}") for i in range(1, 7)]
assert_(all(MEN), "six workers exist to stand in the slots",
        f"{sum(1 for m in MEN if m)} of 6 created")

gang_id = None
if crew_id:
    gang_id, err = new("Gangs", owned({
        "code": "GNG-VERIFY-B", "description": "One short (verification)",
        "template_ID": crew_id}))
    assert_(gang_id is not None, "a gang can be raised on a template", str(err))

if gang_id:
    # Five of the six slots hold a man. The sixth is left empty on purpose.
    for i, (rate, _) in enumerate(SLOTS[:5], start=1):
        child("Gangs", gang_id, "slots",
              {"slotNo": i, "source": "OWN", "ratePerHr": rate,
               "employee_ID": MEN[i - 1]})
    s, d = activate("Gangs", gang_id)
    assert_(s in (200, 201), "and activated part-manned", str(d)[:120])

    s, gang = call(f"/masterdata/Gangs(ID={gang_id},IsActiveEntity=true)"
                   "?$select=code,manned,slotsRequired,actualRatePerHr,blockedReason")
    gang = gang if isinstance(gang, dict) else {}
    assert_(gang.get("slotsRequired") == 6,
            "the gang knows how many slots its template asks for",
            str(gang.get("slotsRequired")))
    assert_(gang.get("manned") == 5,
            "and counts the five men actually on it",
            f"{gang.get('manned')} manned")
    assert_("minimum" in str(gang.get("blockedReason") or "").lower()
            and "5 of 6" in str(gang.get("blockedReason") or ""),
            "so it says it is five of six and below the minimum",
            str(gang.get("blockedReason"))[:110])

    actual = float(gang.get("actualRatePerHr") or 0)
    assert_(0 < actual < EXPECTED_CREW_RATE,
            "an under-manned gang costs LESS per hour than its template — "
            "which is why a cost report alone reads it as a saving",
            f"gang {actual} against template {EXPECTED_CREW_RATE}")

# --------------------------------------------------------------------------- 4

head("4. A man on a slot with a lapsed card is not manning")

blocked_gang_id = None
if crew_id:
    blocked_gang_id, err = new("Gangs", owned({
        "code": "GNG-VERIFY-M", "description": "Fully staffed, one card expired",
        "template_ID": crew_id}))
if blocked_gang_id:
    for i, (rate, _) in enumerate(SLOTS, start=1):
        body = {"slotNo": i, "source": "OWN", "ratePerHr": rate,
                "employee_ID": MEN[i - 1]}
        if i == 6:
            body["blockedReason"] = "Lifting card expired"
        child("Gangs", blocked_gang_id, "slots", body)
    activate("Gangs", blocked_gang_id)

    s, gang = call(f"/masterdata/Gangs(ID={blocked_gang_id},IsActiveEntity=true)"
                   "?$select=code,manned,slotsRequired,blockedReason")
    gang = gang if isinstance(gang, dict) else {}
    assert_(gang.get("slotsRequired") == 6 and gang.get("manned") == 5,
            "six slots hold a man and only five of them count",
            f"{gang.get('manned')} of {gang.get('slotsRequired')}")
    assert_(str(gang.get("blockedReason") or "") != "",
            "so a gang that looks fully staffed is still blocked",
            str(gang.get("blockedReason"))[:110])

# --------------------------------------------------------------------------- 5

head("5. One man, one live engagement")

worker_id, err = new("SubcontractWorkers", owned({
    "workerNo": "SCW-VERIFY-1", "fullName": "Verification Worker",
    "passportNo": "PV-ENG-0001", "nationality": "IN"}))
assert_(worker_id is not None, "a subcontract worker can be raised", str(err))
if worker_id:
    activate("SubcontractWorkers", worker_id)

    first_id, err = new("SubcontractEngagements", owned({
        "worker_ID": worker_id, "poNo": "4500000901", "poItem": "10",
        "ratePerHr": 24.00, "fromDate": "2026-01-01", "toDate": "2026-12-31",
        "status": "Active"}))
    s, d = activate("SubcontractEngagements", first_id) if first_id else (0, "not raised")
    assert_(s in (200, 201), "a first engagement is accepted", str(d)[:120])

    second_id, err = new("SubcontractEngagements", owned({
        "worker_ID": worker_id, "poNo": "4500000902", "poItem": "20",
        "ratePerHr": 26.00, "fromDate": "2026-06-01", "toDate": "2027-05-31",
        "status": "Active"}))
    if second_id:
        check(409, "a second one overlapping it is refused", *activate(
            "SubcontractEngagements", second_id))
    else:
        check(409, "a second one overlapping it is refused", *err)

    third_id, err = new("SubcontractEngagements", owned({
        "worker_ID": worker_id, "poNo": "4500000903", "poItem": "30",
        "ratePerHr": 26.00, "fromDate": "2027-01-01", "toDate": "2027-06-30",
        "status": "Active"}))
    if third_id:
        s, d = activate("SubcontractEngagements", third_id)
        assert_(s in (200, 201),
                "and the same man returning after the first has ended is accepted, "
                "not created again", str(d)[:120])

    s, again = call("/masterdata/SubcontractWorkers?$filter=IsActiveEntity eq true"
                    " and passportNo eq 'PV-ENG-0001'&$select=workerNo")
    again = again if isinstance(again, dict) else {}
    assert_(len(again.get("value") or []) == 1,
            "one passport, one man, however many spells he has worked",
            f"{len(again.get('value') or [])} record(s)")

# --------------------------------------------------------------------------- 6

head("6. The same passport is not hired twice in the group")

first_worker, err = new("Workers", owned({
    "empNo": "EMP-VERIFY-1", "fullName": "Verification Employee",
    "passportNo": "PV-EMP-0001", "source": "MAN"}))
if first_worker:
    s, d = activate("Workers", first_worker)
    assert_(s in (200, 201), "a worker can be raised", str(d)[:120])

second_worker, err = new("Workers", owned({
    "empNo": "EMP-VERIFY-2", "fullName": "Same Man Again",
    "passportNo": "PV-EMP-0001", "source": "MAN"}))
if second_worker:
    check(409, "the same passport a second time is refused", *activate(
        "Workers", second_worker))
else:
    check(409, "the same passport a second time is refused", *err)

no_id, err = new("Workers", owned({
    "empNo": "EMP-VERIFY-3", "fullName": "No Papers", "source": "MAN"}))
if no_id:
    check(400, "and a worker with neither passport nor Emirates ID is refused", *activate(
        "Workers", no_id))
else:
    check(400, "and a worker with neither passport nor Emirates ID is refused", *err)

# --------------------------------------------------------------------------- 7

head("7. No work agreement, no timesheet")

if first_worker:
    s, said = call(f"/masterdata/Workers(ID={first_worker},IsActiveEntity=true)"
                   "/MasterDataService.releaseToErp", method="POST", body={})
    assert_("trade" in str(said).lower() and "cost centre" in str(said).lower(),
            "releasing a worker with no trade or cost centre says what is missing",
            str(said)[:110])

    s, w = call(f"/masterdata/Workers(ID={first_worker},IsActiveEntity=true)"
                "?$select=empNo,syncStatus,syncMessage")
    w = w if isinstance(w, dict) else {}
    assert_(w.get("syncStatus") == "FAILED",
            "and the refusal is recorded on the worker, not only in the reply",
            f"{w.get('syncStatus')}: {str(w.get('syncMessage'))[:70]}")

    s, queue = call("/masterdata/WorkerPushQueue?$select=empNo,syncStatus,syncMessage")
    queue = queue if isinstance(queue, dict) else {}
    waiting = queue.get("value") or []
    assert_(any(r.get("empNo") == "EMP-VERIFY-1" and r.get("syncStatus") == "FAILED"
                for r in waiting),
            "so he appears in the queue of men who cannot have time posted, with his reason",
            f"{len(waiting)} waiting")
    assert_(all(str(r.get("syncMessage") or "") != ""
                for r in waiting if r.get("syncStatus") == "FAILED"),
            "and every failure in that queue carries one",
            f"{sum(1 for r in waiting if r.get('syncStatus') == 'FAILED')} failed")

# --------------------------------------------------------------------------- 8

head("8. A code names one thing")

dup_crew, err = new("CrewTemplates", owned({
    "code": "CRW-VERIFY-POUR", "description": "The same code again",
    "outputBasis": "MANDAY_8H", "minimumManning": 6}))
if dup_crew:
    check(409, "a second crew template on the same code is refused", *activate(
        "CrewTemplates", dup_crew))
else:
    check(409, "a second crew template on the same code is refused", *err)

dup_pattern, err = new("ShiftPatterns", owned({
    "code": "SP-VERIFY-95", "description": "The same code again",
    "dutyHours": 8.00, "mandayHours": 8.00}))
if dup_pattern:
    check(409, "and so is a second shift pattern on one", *activate(
        "ShiftPatterns", dup_pattern))
else:
    check(409, "and so is a second shift pattern on one", *err)

blank, err = new("CrewTemplates", owned({
    "description": "No code at all", "minimumManning": 2}))
if blank:
    check(400, "a master with no code is refused outright", *activate(
        "CrewTemplates", blank))
else:
    check(400, "a master with no code is refused outright", *err)

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
