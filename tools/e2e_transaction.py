"""Walks a job through the services the way a site does, and checks what follows.

Not a seed. Every row below is created by a request to the running service, so
what it proves is that the handlers derive what they are supposed to derive:
that a rate arrives from the bill item rather than being typed, that a claim
totals its own lines, that a prior quantity comes from the claims before it.
A CSV fixture proves none of that - it writes the answers straight into the
database and every check then passes by construction.

Run it against a service that is already up:

    python tools/e2e_transaction.py [base-url] [user] [password]

It leaves what it creates behind. The rows carry a run marker in their document
numbers so a second run does not collide with the first, and on a database in
"fresh" mode they are gone at the next restart anyway.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from base64 import b64encode
from datetime import date, timedelta

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8090/odata/v4"
USER = sys.argv[2] if len(sys.argv) > 2 else "demo"
PASS = sys.argv[3] if len(sys.argv) > 3 else "demo"
AUTH = "Basic " + b64encode(("%s:%s" % (USER, PASS)).encode()).decode()

MARK = uuid.uuid4().hex[:6].upper()
passed, failed, skipped = [], [], []


def call(method, path, body=None):
    # Spaces in a $filter have to be encoded. urllib refuses a URL with a raw
    # one rather than encoding it, and the refusal names a control character,
    # which sends a reader looking for the wrong problem.
    url = BASE + urllib.parse.quote(path, safe="/?$&=,()'*+:")
    req = urllib.request.Request(
        url, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": AUTH, "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw[:400]}


def why(payload):
    """The message a CAP error carries, without the stack around it."""
    if isinstance(payload, dict):
        err = payload.get("error") or {}
        return err.get("message") or payload.get("raw") or json.dumps(payload)[:200]
    return str(payload)[:200]


def check(label, got, want, tolerance=0.01):
    """One derived value against what it should be."""
    if got is None:
        failed.append("%s: nothing derived (expected %s)" % (label, want))
        return False
    if isinstance(want, (int, float)):
        ok = abs(float(got) - float(want)) <= tolerance
    else:
        ok = str(got) == str(want)
    (passed if ok else failed).append(
        "%s: %s%s" % (label, got, "" if ok else " (expected %s)" % want))
    return ok


def note(label, message):
    skipped.append("%s: %s" % (label, message))


def head(title):
    print("\n" + title)
    print("-" * len(title))



def draft_edit(collection, key):
    """Open a document for editing, the way the app does."""
    return call("POST", "/%s(ID=%s,IsActiveEntity=true)/%s"
                % (collection, key, DRAFT_EDIT[collection]), {"PreserveChanges": True})


def draft_activate(collection, key):
    """Save it."""
    return call("POST", "/%s(ID=%s,IsActiveEntity=false)/%s"
                % (collection, key, DRAFT_SAVE[collection]), {})


DRAFT_EDIT = {"billing/PaymentApplications": "BillingService.draftEdit",
              "project/Variations": "ProjectService.draftEdit"}
DRAFT_SAVE = {"billing/PaymentApplications": "BillingService.draftActivate",
              "project/Variations": "ProjectService.draftActivate"}


# ---------------------------------------------------------------- the bill
head("1  what the job is standing on")

status, projects = call("GET", "/project/Projects?$filter=IsActiveEntity eq true"
                               "&$select=ID,code,name&$orderby=code&$top=1")
if status != 200 or not projects.get("value"):
    print("  cannot read projects: %s" % why(projects))
    sys.exit(1)
project = projects["value"][0]
print("  project      %s  %s" % (project["code"], project["name"]))

status, boqs = call("GET", "/project/BOQs?$filter=project_ID eq %s and IsActiveEntity eq true"
                           "&$select=ID,boqId&$top=1" % project["ID"])
boq = (boqs.get("value") or [None])[0]
if not boq:
    print("  this project has no bill; nothing downstream can be created")
    sys.exit(1)
print("  bill         %s" % boq.get("boqId"))

# An item that already exists, rather than a new one. A bill item is a draft
# composition of its bill and cannot be posted on its own, and using one that
# has been claimed before makes the next check harder rather than easier: the
# prior quantity has real history to find.
status, items = call("GET", "/project/BOQItems?$filter=boq_ID eq %s and IsActiveEntity eq true"
                            "&$select=ID,itemNo,description,uom,qty,rate&$orderby=itemNo&$top=1"
                            % boq["ID"])
item = (items.get("value") or [None])[0]
if not item:
    print("  this bill has no items; nothing downstream can be claimed")
    sys.exit(1)
qty = float(item["qty"])
rate = float(item["rate"])
print("  bill item    %s  %s at %s per %s"
      % (item["itemNo"], item["qty"], item["rate"], item["uom"]))
check("the bill item is priced", float(item.get("qty")) * float(item.get("rate")) > 0, True)


# ------------------------------------------------------------- the claim
head("2  claiming for it")

status, apps = call("GET", "/billing/PaymentApplications?$filter=project_ID eq %s"
                           " and IsActiveEntity eq true&$select=ID,docNo,periodEnd,retentionPct"
                           "&$orderby=periodEnd desc&$top=1" % project["ID"])
app = (apps.get("value") or [None])[0]
if not app:
    note("claim", "this project has no payment application to add a line to")
else:
    print("  claim        %s" % app["docNo"])
    status, before = call("GET", "/billing/PaymentApplications(ID=%s,IsActiveEntity=true)"
                                 "?$select=proposedGross,approvedGross,netPayable" % app["ID"])
    gross_before = (before or {}).get("proposedGross") or 0

    # What the claims before this one already measured of this item. Worked out
    # here independently, so the handler and the test do not agree by sharing
    # the same arithmetic.
    expected_prior = 0.0
    status, earlier = call("GET",
        "/billing/PaymentApplications?$filter=project_ID eq %s and IsActiveEntity eq true"
        "&$select=ID,periodEnd&$top=200" % project["ID"])
    for other in (earlier.get("value") or []):
        if other["ID"] == app["ID"] or not other.get("periodEnd"):
            continue
        if other["periodEnd"] >= (app.get("periodEnd") or "9999-12-31"):
            continue
        status, ol = call("GET",
            "/billing/PaymentApplicationLines?$filter=parent_ID eq %s and boqItem_ID eq %s"
            "&$select=approvedQty,qsQty,proposedQty&$top=200" % (other["ID"], item["ID"]))
        for r in (ol.get("value") or []):
            q = r.get("approvedQty")
            if q is None: q = r.get("qsQty")
            if q is None: q = r.get("proposedQty")
            expected_prior += float(q or 0)
    print("  earlier claims measured %s of this item" % expected_prior)

    # The whole point: one quantity, nothing else.
    claim_qty = 60
    status, edit = call("POST", "/billing/PaymentApplications(ID=%s,IsActiveEntity=true)"
                                "/BillingService.draftEdit" % app["ID"],
                        {"PreserveChanges": True})
    if status >= 300:
        failed.append("opening the claim for editing: %s" % why(edit))
        line, status = {}, 500
    else:
        status, line = call("POST", "/billing/PaymentApplications(ID=%s,IsActiveEntity=false)"
                                    "/lines" % app["ID"],
                            {"lineNo": 99, "boqItem_ID": item["ID"],
                             "proposedQty": claim_qty})
    if status >= 300:
        failed.append("claim line: %s" % why(line))
    else:
        print("  claim line   created with a quantity and nothing else")
        check("rate came from the bill item", line.get("rate"), rate)
        check("unit came from the bill item", line.get("uom"), "m3")
        check("description came from the bill item",
              line.get("description"), item["description"])
        check("contract quantity came from the bill item", line.get("contractQty"), qty)
        check("value is quantity times rate", line.get("proposedValue"), claim_qty * rate)
        check("prior quantity read from earlier claims",
              line.get("priorQty"), expected_prior)
        check("cumulative quantity follows",
              line.get("cumQty"), expected_prior + claim_qty)
        check("cumulative percent follows",
              line.get("cumPct"), round((expected_prior + claim_qty) / qty * 100, 2))

        # Correct it before saving, which is what a surveyor does.
        status, patched = call("PATCH",
            "/billing/PaymentApplications(ID=%s,IsActiveEntity=false)/lines(ID=%s,"
            "IsActiveEntity=false)" % (app["ID"], line["ID"]), {"proposedQty": 75})
        if status >= 300:
            failed.append("correcting the quantity: %s" % why(patched))
        else:
            check("a corrected quantity reprices", patched.get("proposedValue"), 75 * rate)

        status, saved = call("POST", "/billing/PaymentApplications(ID=%s,IsActiveEntity=false)"
                                     "/BillingService.draftActivate" % app["ID"], {})
        if status >= 300:
            failed.append("saving the claim: %s" % why(saved))
        else:
            print("  claim saved")
            status, after = call("GET",
                "/billing/PaymentApplications(ID=%s,IsActiveEntity=true)"
                "?$select=proposedGross,retentionPct,retentionAmount,netPayable" % app["ID"])
            check("the claim totalled its own lines",
                  (after or {}).get("proposedGross"), gross_before + 75 * rate)



# --------------------------------------------------------- the variation
head("3  varying the contract")

status, vos = call("GET", "/project/Variations?$filter=project_ID eq %s and IsActiveEntity eq true"
                          "&$select=ID,docNo,revenueAmount,costAmount&$top=1" % project["ID"])
vo = (vos.get("value") or [None])[0]
if not vo:
    note("variation", "this project has no variation order to add a line to")
else:
    print("  variation    %s" % vo["docNo"])
    rev_before = vo.get("revenueAmount") or 0
    vqty, vrev, vcost = 40, 2180, 1685
    status, vedit = call("POST", "/project/Variations(ID=%s,IsActiveEntity=true)"
                                 "/ProjectService.draftEdit" % vo["ID"],
                         {"PreserveChanges": True})
    if status >= 300:
        failed.append("opening the variation for editing: %s" % why(vedit))
        vline, status = {}, 500
    else:
        status, vline = call("POST", "/project/Variations(ID=%s,IsActiveEntity=false)/lines"
                                     % vo["ID"],
                             {"lineNo": 99, "changeType": "ADD",
                              "description": "Extra blinding, run %s" % MARK,
                              "qty": vqty, "uom": "m3",
                              "revenueRate": vrev, "costRate": vcost})
    if status >= 300:
        failed.append("variation line: %s" % why(vline))
    else:
        check("variation revenue is quantity times rate",
              vline.get("revenueAmount"), vqty * vrev)
        check("variation cost is quantity times rate",
              vline.get("costAmount"), vqty * vcost)
        status, vsaved = call("POST", "/project/Variations(ID=%s,IsActiveEntity=false)"
                                      "/ProjectService.draftActivate" % vo["ID"], {})
        if status >= 300:
            failed.append("saving the variation: %s" % why(vsaved))
        else:
            status, vafter = call("GET", "/project/Variations(ID=%s,IsActiveEntity=true)"
                                         "?$select=revenueAmount,costAmount,marginAmount,"
                                         "marginPct" % vo["ID"])
            check("the variation totalled its own lines",
                  (vafter or {}).get("revenueAmount"), rev_before + vqty * vrev)


# ------------------------------------------------------------ the reports
head("4  what the reports make of it")

status, report = call("GET", "/project/PeriodReports?$filter=projectCode eq '%s'"
                             "&$select=projectCode,contractValue,earnedValue,actualCost"
                             % project["code"])
row = (report.get("value") or [None])[0]
if not row:
    note("reports", "no reconciliation for this project yet")
else:
    print("  contract     %s" % row.get("contractValue"))
    print("  earned       %s" % row.get("earnedValue"))
    print("  spent        %s" % row.get("actualCost"))
    note("reports", "a reconciliation is kept as at the period it measured; run "
                    "reconcile on the project to fold the rows above into it")


# ---------------------------------------------------------------- verdict
head("what happened")
for line in passed:
    print("  ok    %s" % line)
for line in skipped:
    print("  note  %s" % line)
for line in failed:
    print("  FAIL  %s" % line)

print("\n%d derived correctly, %d wrong, %d not reached" % (len(passed), len(failed), len(skipped)))
sys.exit(1 if failed else 0)
