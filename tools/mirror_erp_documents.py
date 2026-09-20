"""Plays the ERP side of procurement, and the store, so the demo has both.

Everything prime_demo.py writes, KONSTRYX itself produces — press the same
button on the screen and you get the same record. Purchase orders are not like
that. KONSTRYX never raises one; ERP does, against a requisition we sent, and
all we ever hold is a mirror. So there is nothing on any KONSTRYX screen that
can bring a purchase order into being, and without one the commitment column on
every budget line reads zero and the goods receipt screen is empty.

This stands in for the ERP that would answer. It calls the same three inbound
entry points a real connector calls — recordRequisitionResult, then
recordPurchaseOrder, recordGoodsReceipt and recordSupplierInvoice — so nothing
here writes a row the integration would not have written. What it invents is only what ERP alone
decides: the document numbers.

Everything else is read from the requisition rather than made up.

    Quantity and value  the requisition's own lines. A stand-in has no
                        negotiation to report, so it orders what was asked for
                        at what was estimated, and the order is honest about
                        being an unnegotiated one.
    Vendor              whoever the resource's own rate names. A hired resource
                        carries its supplier in the rate master; a material or
                        an in-house resource does not, and the order is then
                        mirrored without a vendor rather than with a guessed one.
    Delivery            a line is received when its need-by date has passed.
                        That is why some orders are settled and some are still
                        open: the programme decides, not a coin toss.
    Billing             what has arrived and has not yet been billed, at the
                        order's rate. A bill that disagrees with its order is a
                        real event and a stand-in has no grounds to invent one,
                        so every bill here matches.

Every order is stamped with system DEMO, which is what tells it apart from one
mirrored from a connected tenant — those carry the tenant's own host.

The stock half alternates between the two sides rather than staying on one.
A draw is ours to raise, the movement that answers it is ERP's, and the count
on site and the day's consumption are ours again — four steps that only make
sense in that order. Splitting them across two tools by ownership would put an
ordering trap between them, which is exactly the trap that once left every cost
report a step behind its own invoices. So the sequence lives here, in order,
and each call says which side it belongs to.

Safe to repeat: each action refuses a document it has already mirrored, and the
stock half skips a reservation line that has already been drawn against.

    python tools/mirror_erp_documents.py [base-url] [user:pass]
"""
import base64
from decimal import Decimal as _D
import datetime as _dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8090") + "/odata/v4"
USER, PASSWORD = (sys.argv[2] if len(sys.argv) > 2 else "admin:admin").split(":", 1)
AUTH = "Basic " + base64.b64encode(("%s:%s" % (USER, PASSWORD)).encode()).decode()

SYSTEM = "DEMO"
# The plant every demo draw comes out of. One store, because the demo
# estate has one, and a second invented one would imply a stock split
# nothing else in the data knows about.
STORE = "1710"
TODAY = _dt.date.today()


def call(path, method="GET", body=None):
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
        except Exception:                                        # noqa: BLE001
            return error.code, raw.decode("utf-8", "replace")[:400]
    except Exception as error:                                   # noqa: BLE001
        return 0, str(error)


def message(payload):
    if isinstance(payload, dict):
        if isinstance(payload.get("value"), str):
            return payload["value"]
        error = payload.get("error")
        if isinstance(error, dict):
            return error.get("message", "")
    return str(payload)[:200] if payload else ""


def rows(path):
    status, payload = call(path)
    if status != 200 or not isinstance(payload, dict):
        raise SystemExit("cannot read %s: %s %s" % (path, status, message(payload)))
    return payload.get("value", [])


def run(label, path, body):
    status, payload = call(path, "POST", body)
    text = message(payload)
    ok = status in (200, 201, 204)
    # A document already mirrored is the ordinary result of a second run, not
    # a failure — it is exactly what the guard is there to do.
    settled = status == 409 and "already mirrored" in text
    mark = "ok " if ok else ("--  " if settled else str(status).ljust(3))
    print("  %-42s %s %s" % (label, mark, text[:105]))
    return ok


def bp_of(vendor_id, cache):
    if not vendor_id:
        return None
    if vendor_id not in cache:
        found = rows("/masterdata/Vendors?$filter=ID eq %s&$select=bpNumber" % vendor_id)
        cache[vendor_id] = found[0]["bpNumber"] if found else None
    return cache[vendor_id]


def _dec(value):
    try:
        return _D(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return _D("0")


def as_date(value):
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def main():
    requisitions = rows("/material/PurchaseRequisitions"
                        "?$select=ID,prNo,status,syncStatus,raisedOn&$orderby=createdAt")
    if not requisitions:
        raise SystemExit("No requisitions exist yet — run tools/prime_demo.py first.")

    print("\nRequisitions to answer: %d\n" % len(requisitions))

    rate_vendor = {}
    vendor_bp = {}
    ordered = 0
    received = 0
    billed = 0

    print("Accepting the requisitions — the number ERP issues on receipt")
    for index, pr in enumerate(requisitions, start=1):
        if pr.get("syncStatus") == "SENT":
            print("  %-42s --   already numbered %s"
                  % ("requisition %d" % index, pr.get("prNo")))
            continue
        prNo = "10%08d" % index
        run("requisition %d accepted as %s" % (index, prNo),
            "/material/PurchaseRequisitions(%s)"
            "/MaterialService.recordRequisitionResult" % pr["ID"],
            {"success": True, "prNo": prNo, "s4System": SYSTEM,
             "message": "Accepted and numbered."})

    print("\nOrdering what was asked for")
    for index, pr in enumerate(requisitions, start=1):
        lines = rows("/material/PurchaseRequisitionLines"
                     "?$filter=parent_ID eq %s"
                     "&$select=lineNo,qtyProcure,estTotal,needBy,resource_ID,status"
                     "&$orderby=lineNo" % pr["ID"])
        if not lines:
            print("  %-42s --   nothing to order" % ("requisition %d" % index))
            continue

        vendor = None
        for line in lines:
            resource = line.get("resource_ID")
            if resource not in rate_vendor:
                # Active rows only: Rates is draft-enabled, and a half-typed
                # draft naming a vendor would send the order to whoever
                # somebody was in the middle of considering.
                match = rows("/masterdata/Rates?$filter=IsActiveEntity eq true and "
                             "resource_ID eq %s"
                             "&$select=vendor_ID&$top=20" % resource) if resource else []
                rate_vendor[resource] = next(
                    (r["vendor_ID"] for r in match if r.get("vendor_ID")), None)
            vendor = vendor or bp_of(rate_vendor.get(resource), vendor_bp)

        poNo = "45%08d" % index
        body = {
            "requisitionId": pr["ID"],
            "poNo": poNo,
            "vendorBP": vendor or "",
            "s4System": SYSTEM,
            "orderedOn": str(TODAY),
            "lines": [{"prLineNo": line["lineNo"],
                       "qty": line.get("qtyProcure") or 0,
                       "netValue": line.get("estTotal") or 0,
                       "eta": line.get("needBy")} for line in lines],
        }
        if run("%s for requisition %d, %d line(s)" % (poNo, index, len(lines)),
               "/material/recordPurchaseOrder", body):
            ordered += 1

    print("\nDelivering what the programme says has arrived")
    for order in rows("/material/PurchaseOrders?$select=ID,poNo,status&$orderby=poNo"):
        if order.get("status") in ("Received", "Cancelled"):
            continue
        lines = rows("/material/PurchaseOrderLines?$filter=parent_ID eq %s"
                     "&$select=lineNo,openQty,eta&$orderby=lineNo" % order["ID"])
        due = [line for line in lines
               if (line.get("openQty") or 0) > 0
               and as_date(line.get("eta")) is not None
               and as_date(line["eta"]) <= TODAY]
        if not due:
            print("  %-42s --   nothing due yet" % order["poNo"])
            continue
        grDoc = "50" + order["poNo"][2:]
        if run("%s received against %s, %d line(s)" % (grDoc, order["poNo"], len(due)),
               "/material/recordGoodsReceipt",
               {"poNo": order["poNo"], "grDoc": grDoc, "s4System": SYSTEM,
                "datePosted": str(TODAY),
                "lines": [{"poLineNo": line["lineNo"], "grQty": line["openQty"]}
                          for line in due]}):
            received += 1

    print("\nBilling for what has been delivered")
    # A vendor bills after delivery, not before, so the invoice follows the
    # receipt exactly: what has arrived and has not yet been billed, priced at
    # the order's own rate. Nothing here is negotiated, so these match by
    # construction - a bill that disagrees with its order is a real event and
    # this stand-in has no grounds to invent one.
    for order in rows("/material/PurchaseOrders?$select=ID,poNo,status&$orderby=poNo"):
        lines = rows("/material/PurchaseOrderLines?$filter=parent_ID eq %s"
                     "&$select=lineNo,qty,receivedQty,invoicedQty,netValue"
                     "&$orderby=lineNo" % order["ID"])
        billable = []
        for line in lines:
            due = float(line.get("receivedQty") or 0) - float(line.get("invoicedQty") or 0)
            # Named for the line, not for the run. This was `ordered`, which is
            # also the count of orders placed, so the summary at the end
            # reported the last line's quantity as the number of orders — 20
            # placed on a run that placed none.
            lineQty = float(line.get("qty") or 0)
            if due <= 0 or lineQty <= 0:
                continue
            billable.append({
                "poLineNo": line["lineNo"], "qty": round(due, 3),
                "netAmount": round(float(line.get("netValue") or 0) * due / lineQty, 2)})
        if not billable:
            print("  %-42s --   nothing delivered to bill for" % order["poNo"])
            continue
        invoiceNo = "51" + order["poNo"][2:]
        if run("%s billed against %s, %d line(s)"
               % (invoiceNo, order["poNo"], len(billable)),
               "/material/recordSupplierInvoice",
               {"poNo": order["poNo"], "invoiceNo": invoiceNo, "s4System": SYSTEM,
                "postingDate": str(TODAY), "lines": billable}):
            billed += 1

    # ------------------------------------------------------ stock from a store
    #
    # The other half of a material request: what the company already owns and
    # does not have to buy. The goods issue is where the money moves — it
    # debits the project in ERP — so consumption below carries quantities and
    # no money at all, or the same concrete would be paid for twice.
    print("\nStock drawn from a store, against what was reserved for it")
    drawn = issued = 0
    verticals = {r["ID"]: r.get("verticalType") for r in
                 rows("/workflow/ResourceRequests?$filter=IsActiveEntity eq true"
                      "&$select=ID,verticalType")}
    for reservation in rows("/workflow/Reservations?$select=ID,docNo,project_ID,"
                            "rr_ID,executionFlow&$orderby=docNo"):
        # Only stock, and only stock we already own. A manpower or equipment
        # line is consumed by signing days against it, not by drawing it out of
        # a store, and a material line on the procurement flow is supplied by a
        # purchase order — drawing it here as well would spend for it twice.
        if verticals.get(reservation.get("rr_ID")) != "MR":
            continue
        if reservation.get("executionFlow") != "IN_HOUSE":
            continue
        for line in rows("/workflow/ReservationLines?$filter=reservation_ID eq %s"
                         "&$select=ID,qty,uom,lineStatus,rrLine_ID"
                         % reservation["ID"]):
            existing = rows("/material/PullRequests?$filter=reservationLine_ID eq %s"
                            "&$select=ID,docNo" % line["ID"])
            if existing:
                print("  %-42s --  already drawn as %s"
                      % (reservation["docNo"] + " draw", existing[0]["docNo"]))
                continue

            rr_lines = rows("/workflow/ResourceRequestLines?$filter=ID eq %s"
                            "&$select=lineNo,description,cbs_ID" % line["rrLine_ID"])
            if not rr_lines:
                continue
            rr_line = rr_lines[0]
            # A norm is keyed by cost node, so a line charging nothing has
            # nothing to measure against and is left alone rather than drawn
            # and then stuck at the consumption step.
            if not rr_line.get("cbs_ID"):
                continue

            reserved = _dec(line.get("qty"))
            if reserved <= 0:
                continue

            # Ours: the site asks the store for what the reservation covers.
            if not run("%s line %s draw" % (reservation["docNo"], rr_line["lineNo"]),
                       "/workflow/Reservations(%s)/WorkflowService.raisePullRequest"
                       % reservation["ID"],
                       {"lineNo": rr_line["lineNo"], "qty": float(reserved),
                        "storageLoc": STORE}):
                continue
            drawn += 1

            pull = rows("/material/PullRequests?$filter=reservationLine_ID eq %s"
                        "&$select=ID,docNo,qtyRequested" % line["ID"])[0]

            # ERP's: the movement. A store gives out what it has, and the
            # short delivery below is the programme's own arithmetic rather
            # than a coin toss — the last tenth of a reserved quantity is what
            # a plant holds back for the next pour.
            moved = (reserved * 9 / 10).quantize(_D("0.001"))
            gi_doc = "49%08d" % (drawn + 1000)
            if not run("%s goods issue" % pull["docNo"],
                       "/material/PullRequests(%s)/MaterialService.recordGoodsIssue"
                       % pull["ID"],
                       {"giDoc": gi_doc, "giDate": str(TODAY), "giQty": float(moved),
                        "s4System": SYSTEM, "message": ""}):
                continue
            issued += 1

            # Ours again: the site counts it in.
            run("%s site receipt" % pull["docNo"],
                "/material/PullRequests(%s)/MaterialService.confirmSiteReceipt"
                % pull["ID"],
                {"receivedQty": float(moved), "receivedBy": "Site store",
                 "receivedOn": str(TODAY),
                 "note": "Counted in against %s" % gi_doc})

            # And the day's work against the norm. Output is taken as equal to
            # what was issued, which is only right for a one-for-one norm —
            # a cubic metre of ready-mix places a cubic metre of concrete, and
            # that is what the demo's material carries. A norm that is not
            # one-for-one, rebar at 105 kg per m3 of structure, would need the
            # output derived from it rather than assumed. Whether the day is
            # over or under its allowance is then the norm's answer and not
            # this tool's.
            run("%s consumption" % reservation["docNo"],
                "/material/recordConsumption",
                {"reservationNo": reservation["docNo"],
                 "lineNo": rr_line["lineNo"], "recordDate": str(TODAY),
                 "diaryOutputQty": float(moved), "actualQty": float(moved),
                 "note": rr_line.get("description") or ""})

    print("\nRefreshing the budgets so the commitment lands")
    for budget in rows("/budget/Budgets?$filter=IsActiveEntity eq true"
                       "&$select=ID,docNo&$orderby=docNo"):
        run(budget["docNo"] + " refresh control",
            "/budget/Budgets(ID=%s,IsActiveEntity=true)"
            "/BudgetService.refreshControl" % budget["ID"], {})

    # Reconciled after the bills land, not before: the cost report reads the
    # invoices, and the one prime_demo produced ran before any of them
    # existed. Leaving it stale is how a screen comes to say procurement
    # contributes nothing on a project that has just been billed three
    # quarters of a million.
    print("\nReconciling, so the cost reports see the bills")
    for project in rows("/project/Projects?$filter=IsActiveEntity eq true"
                        "&$select=ID,code&$orderby=code"):
        run(project["code"] + " reconcile",
            "/project/Projects(ID=%s,IsActiveEntity=true)"
            "/ProjectService.reconcile" % project["ID"], {})

    print("\nWhat exists now")
    for label, path in [("Purchase orders", "/material/PurchaseOrders"),
                        ("Order lines", "/material/PurchaseOrderLines"),
                        ("Goods receipts", "/material/GoodsReceipts"),
                        ("Supplier invoices", "/material/SupplierInvoices"),
                        ("Stock draws", "/material/PullRequests"),
                        ("Consumption records", "/material/ConsumptionRecords")]:
        status, payload = call(path + "?$top=0&$count=true")
        count = payload.get("@count") if isinstance(payload, dict) else None
        print("  %-24s %s" % (label, count if count is not None else "unreadable"))
    print("  %d order(s) placed, %d delivery(ies) and %d bill(s) posted this run"
          % (ordered, received, billed))
    print("  %d stock draw(s) raised and %d goods issue(s) posted this run\n"
          % (drawn, issued))


main()
