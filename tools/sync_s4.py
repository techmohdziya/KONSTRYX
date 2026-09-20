"""Runs the S/4 syncs against the connected system, and reports what happened.

Kept apart from tools/prime_demo.py deliberately. Priming only recomputes
KONSTRYX's own derived records and can be re-run at will; this reaches the
customer's S/4 tenant, and two of its steps CREATE DOCUMENTS THERE — a project
in SAP_COM_0308 and a purchase requisition in SAP_COM_0053. Those are not
undone by running this again.

    python tools/sync_s4.py            read the masters only
    python tools/sync_s4.py --push     also push projects and requisitions

Read and push are separated for that reason: reading materials, suppliers and
customers is safe to repeat as often as you like, and pushing is not.

Numbers come back from S/4 rather than being issued here. A purchase
requisition draws no KONSTRYX number range and gets no docNo — S/4 owns the
requisition number, and the requisition sits at NOT_SENT until S/4 answers with
one. The same is true of the project key. That is why a push failure leaves a
document that is visibly unsent rather than one that looks numbered and is not.
"""
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:8090/odata/v4"
AUTH = "Basic " + base64.b64encode(b"admin:admin").decode()
PUSH = "--push" in sys.argv


def call(path, method="GET", body=None):
    url = BASE + urllib.parse.quote(path, safe="/?$&=(),'*:+-")
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", AUTH)
    request.add_header("Accept", "application/json")
    if data:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
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


def text(payload):
    if isinstance(payload, dict):
        if isinstance(payload.get("value"), str):
            return payload["value"]
        error = payload.get("error")
        if isinstance(error, dict):
            return error.get("message", "")
    return str(payload)[:300] if payload else ""


def rows(path):
    status, payload = call(path)
    if status != 200 or not isinstance(payload, dict):
        raise SystemExit("cannot read %s: %s %s" % (path, status, text(payload)))
    return payload.get("value", [])


def main():
    print("\nMasters — read from S/4 into the mirrors")
    status, payload = call("/admin/syncMastersFromS4", "POST", {})
    print("  " + text(payload).replace("\n", "\n  ") if status == 200
          else "  failed %s: %s" % (status, text(payload)))

    if not PUSH:
        print("\nProjects and requisitions were NOT pushed. Re-run with --push to\n"
              "create them in S/4; every push writes a document to the tenant.")
        return

    print("\nProjects — pushed outward through SAP_COM_0308")
    for project in rows("/project/Projects?$filter=IsActiveEntity eq true"
                        "&$select=ID,code,syncStatus&$orderby=code"):
        key = "(ID=%s,IsActiveEntity=true)" % project["ID"]
        status, payload = call(
            "/project/Projects%s/ProjectService.releaseToS4" % key, "POST", {})
        print("  %-10s %-4s %s" % (project["code"],
                                   "ok" if status == 200 else status,
                                   text(payload)[:130]))

    print("\nPurchase requisitions — pushed through SAP_COM_0053")
    for requisition in rows("/material/PurchaseRequisitions"
                            "?$select=ID,prNo,syncStatus,raisedOn&$orderby=raisedOn"):
        key = "(%s)" % requisition["ID"]
        status, payload = call(
            "/material/PurchaseRequisitions%s/MaterialService.syncToS4" % key,
            "POST", {})
        print("  %-38s %-4s %s" % (requisition["ID"][:36],
                                   "ok" if status == 200 else status,
                                   text(payload)[:120]))

    print("\nWhat carries an S/4 number now")
    for label, path, field in [
        ("Projects", "/project/Projects?$filter=IsActiveEntity eq true"
                     "&$select=code,s4Key,syncStatus", "s4Key"),
        ("Requisitions", "/material/PurchaseRequisitions"
                         "?$select=prNo,syncStatus,syncMessage", "prNo"),
    ]:
        print("  " + label)
        for row in rows(path):
            print("    %-14s %-12s %s"
                  % (row.get("code") or row.get("prNo") or "-",
                     row.get("syncStatus"), (row.get("syncMessage") or "")[:70]))


main()
