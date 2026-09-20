"""Runs the actions that produce the derived records, against a running service.

Four of the things a demo needs to show are not data anyone types. A reservation
is what createReservation makes out of an approved request; a purchase
requisition is what raisePurchaseRequisition makes out of the PROCURE-decided
lines beside it; a productivity rate is what measureProductivity computes from
signed hours and measured quantity; a period report is what reconcile measures.
The variation that extends the cranes is the same kind of thing: the wireframe
chain describes the event, and what it costs is whatever those reservation lines
produce rather than a figure typed in to match the mockup.
Seeding those as CSV rows would put numbers on the screen that no calculation in
the product ever produced, which is the one kind of demo data that misleads
instead of illustrating — the figure looks right until someone presses the
button and it changes.

So they are produced the way they are produced in service: by calling the
actions. Everything this writes is reproducible by pressing the same buttons on
the screen, and a mismatch between the two is a bug rather than a data problem.

Safe to repeat. Every action here recomputes rather than accumulates; the two
that create documents refuse a second one for the same source, and the one that
cannot refuse — a variation is a document that may legitimately be raised twice
— is guarded by looking first.

    python tools/prime_demo.py [base-url] [user:pass]
"""
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8090") + "/odata/v4"
USER, PASSWORD = (sys.argv[2] if len(sys.argv) > 2 else "admin:admin").split(":", 1)
AUTH = "Basic " + base64.b64encode(("%s:%s" % (USER, PASSWORD)).encode()).decode()


def call(path, method="GET", body=None):
    # Filters are written readably above and encoded here. urllib refuses a URL
    # with a raw space rather than escaping it, and the failure reads as a
    # connection problem rather than as the quoting bug it is.
    url = BASE + urllib.parse.quote(path, safe="/?$&=(),'*:+-")
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", AUTH)
    request.add_header("Accept", "application/json")
    if data:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw)
        except Exception:
            return error.code, raw.decode("utf-8", "replace")[:400]
    except Exception as error:                                   # noqa: BLE001
        return 0, str(error)


def message(payload):
    if isinstance(payload, dict):
        if "value" in payload and isinstance(payload["value"], str):
            return payload["value"]
        error = payload.get("error")
        if isinstance(error, dict):
            return error.get("message", "")
        # An action that returns an entity - recalculate does, so the screen
        # can refresh from what the database now holds - hands back a whole
        # payload. Printing it buries the line in metadata, so the document is
        # named instead and the numbers that moved are shown.
        if "docNo" in payload:
            parts = [str(payload["docNo"])]
            for field, label in (("revenueAmount", "revenue"),
                                 ("costAmount", "cost"),
                                 ("marginAmount", "margin")):
                if payload.get(field) is not None:
                    parts.append("%s %s" % (label, payload[field]))
            return ", ".join(parts)
    return str(payload)[:200] if payload else ""


def rows(path):
    status, payload = call(path)
    if status != 200 or not isinstance(payload, dict):
        raise SystemExit("cannot read %s: %s %s" % (path, status, message(payload)))
    return payload.get("value", [])


def run(label, path, body=None):
    status, payload = call(path, "POST", body if body is not None else {})
    text = message(payload)
    ok = status in (200, 201, 204)
    print("  %-46s %s  %s" % (label, "ok " if ok else str(status).ljust(3),
                              text[:110]))
    return ok


def main():
    projects = rows("/project/Projects?$filter=IsActiveEntity eq true"
                    "&$select=ID,code,name&$orderby=code")
    print("\nProjects: %d\n" % len(projects))

    print("Schedule — forward and backward pass over the network")
    for project in projects:
        key = "(ID=%s,IsActiveEntity=true)" % project["ID"]
        run(project["code"] + " critical path",
            "/project/Projects%s/ProjectService.schedule" % key)

    print("\nCost breakdown — roll every node up from its own lines")
    for project in projects:
        nodes = rows("/project/CBS?$filter=project_ID eq %s&$top=1&$select=ID"
                     % project["ID"])
        if not nodes:
            print("  %-46s --   no CBS on this project" % (project["code"] + " roll up"))
            continue
        run(project["code"] + " roll up budget",
            "/project/CBS(%s)/ProjectService.rollUpBudget" % nodes[0]["ID"])

    print("\nSourcing — the chain the advisory decisions already point at")
    requests = rows("/workflow/ResourceRequests?$filter=IsActiveEntity eq true"
                    "&$select=ID,docNo,status&$orderby=docNo")
    for request in requests:
        key = "(ID=%s,IsActiveEntity=true)" % request["ID"]
        # Availability first: createReservation reserves against what the check
        # found free, and without one it has nothing to reserve against.
        run(request["docNo"] + " availability check",
            "/workflow/ResourceRequests%s/WorkflowService.runAvailabilityCheck"
            % key)
        run(request["docNo"] + " reserve in-house lines",
            "/workflow/ResourceRequests%s/WorkflowService.createReservation" % key)
        run(request["docNo"] + " raise requisition",
            "/workflow/ResourceRequests%s/WorkflowService.raisePurchaseRequisition"
            % key)

    # The extension the wireframe's own chain describes at step 8: the slab
    # cycle slipped on the super-structure and both cranes are held thirty days
    # longer. The event is the spec's; the money is not, because it is what
    # these reservation lines actually produce, and a figure typed in to match
    # a mockup is the one kind of demo number that misleads.
    #
    # Guarded rather than idempotent. Every other action here recomputes, but a
    # variation is a document and running this twice would extend the cranes
    # twice.
    print("\nReservation variations \u2014 what moved after the lock was set")
    crane_res = rows("/workflow/Reservations?$filter=rr/docNo eq 'RR-2026-0188'"
                     "&$select=ID,docNo")
    if not crane_res:
        print("  %-46s --   the plant reservation is not there to vary"
              % "RR-2026-0188 extension")
    else:
        reservation = crane_res[0]
        already = rows("/workflow/ReservationVariations?$filter=reservation_ID eq %s"
                       "&$select=ID" % reservation["ID"])
        if already:
            print("  %-46s --   already varied (%d)"
                  % (reservation["docNo"] + " slab cycle extension", len(already)))
        else:
            for line_no, what in ((1, "Tower crane LB280"),
                                  (2, "Mobile crane GMK3050")):
                run("%s line %d +30 days" % (reservation["docNo"], line_no),
                    "/workflow/Reservations(%s)/WorkflowService.vary"
                    % reservation["ID"],
                    {"lineNo": line_no,
                     "extendByDays": 30,
                     "reason": "DURATION",
                     "narrative": "Slab cycle slipped on the super-structure "
                                  "L12-L18. %s held thirty days beyond the "
                                  "mobilization window." % what,
                     "effectiveFrom": "2026-08-18"})

    print("\nVariations \u2014 priced from their own lines")
    for variation in rows("/project/Variations?$filter=IsActiveEntity eq true"
                          "&$select=ID,docNo&$orderby=docNo"):
        run(variation["docNo"] + " recalculate",
            "/project/Variations(ID=%s,IsActiveEntity=true)"
            "/ProjectService.recalculate" % variation["ID"])

    print("\nBills \u2014 build-up resolved, then costed from it")
    for boq in rows("/project/BOQs?$filter=IsActiveEntity eq true"
                    "&$select=ID,boqId&$orderby=boqId"):
        # The build-up has to exist before a line can be costed from it: cost is
        # the sum of the resources a line consumes, and a line without one has an
        # unknown cost rather than a zero.
        run(boq["boqId"] + " resolve build-up",
            "/project/BOQs(ID=%s,IsActiveEntity=true)"
            "/ProjectService.generateBuildUp" % boq["ID"], {"difficultyPct": 0})
        run(boq["boqId"] + " cost the lines",
            "/project/BOQs(ID=%s,IsActiveEntity=true)"
            "/ProjectService.recalculateCost" % boq["ID"])

    print("\nFiscal calendar \u2014 the periods everything else buckets into")
    calendars = rows("/admin/FiscalCalendars?$select=ID,code,name")
    if not calendars:
        print("  --   no calendar is defined, so nothing can be phased or "
              "bucketed by period")
    else:
        calendar = calendars[0]
        # The years the portfolio actually spans, not a fixed range. A project
        # starting outside the generated years phases into nothing, and the
        # only symptom is a curve that does not add up to its own budget.
        years = set()
        for row in rows("/project/Projects?$filter=IsActiveEntity eq true"
                        "&$select=startDate,endDate"):
            for field in ("startDate", "endDate"):
                if row.get(field):
                    years.add(int(str(row[field])[:4]))
        for year in sorted(years):
            run("%s %d" % (calendar["code"], year),
                "/admin/FiscalCalendars(%s)/AdminService.generate" % calendar["ID"],
                {"fiscalYear": year, "replace": False})

    print("\nBudget \u2014 spread across the periods its work falls in")
    for budget in rows("/budget/Budgets?$filter=IsActiveEntity eq true"
                       "&$select=ID,docNo&$orderby=docNo"):
        run(budget["docNo"] + " phase budget",
            "/budget/Budgets(ID=%s,IsActiveEntity=true)/BudgetService.phaseBudget"
            % budget["ID"])

    print("\nProductivity — output per signed man-hour, per location")
    for project in projects:
        key = "(ID=%s,IsActiveEntity=true)" % project["ID"]
        run(project["code"] + " measure productivity",
            "/project/Projects%s/ProjectService.measureProductivity" % key)

    print("\nCost value reconciliation — earned against spent, per period")
    for project in projects:
        key = "(ID=%s,IsActiveEntity=true)" % project["ID"]
        run(project["code"] + " reconcile",
            "/project/Projects%s/ProjectService.reconcile" % key, {})

    print("\nWhat exists now")
    for label, path in [
        ("Reservations", "/workflow/Reservations"),
        ("Purchase requisitions", "/material/PurchaseRequisitions"),
        ("Productivity snapshots", "/workflow/ProductivitySnapshots"),
        ("Period reports", "/project/PeriodReports"),
        ("Variations", "/project/Variations?$filter=IsActiveEntity eq true"),
        ("Reservation variations", "/workflow/ReservationVariations"),
        ("Budget phases", "/budget/BudgetPhases"),
        ("Cashflow periods", "/project/Cashflow"),
        ("Project overviews", "/project/ProjectOverviews"),
        ("Activities on the critical path",
         "/project/Activities?$filter=isCritical eq true and IsActiveEntity eq true"),
    ]:
        status, payload = call(path + ("&" if "?" in path else "?")
                               + "$top=0&$count=true")
        count = payload.get("@count") if isinstance(payload, dict) else None
        print("  %-34s %s" % (label, count if count is not None else "unreadable"))


main()
