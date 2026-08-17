"""The PROCURE half of the advisory split: raising a purchase requisition.

createReservation consumes the IN_HOUSE lines; until raisePurchaseRequisition
existed, a PROCURE line stopped at "Advised" and nothing picked it up. The
requisition is deliberately NOT a KONSTRYX document — S/4 owns its number — so
these checks assert what it must NOT have (a docNo, a KONSTRYX number range) as
carefully as what it must."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"
USER = "demo"


def call(path, method="GET", body=None, user=USER):
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
            msg = out[:400]
        return e.code, msg


results = []


def check(expected, label, status, payload):
    if isinstance(payload, dict):
        payload = payload.get("value", payload)
    ok = status == expected
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] {label}: {str(payload)[:170]}")
    results.append(ok)
    return payload


def assert_(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{(': ' + str(detail)) if detail != '' else ''}")
    results.append(bool(ok))


def head(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


# ------------------------------------------------------------------- fixtures
s, ps = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'PRJ-001'"
             "&$select=ID,company_ID")
project = ps["value"][0]
s, wbs = call(f"/project/WBS?$filter=project_ID eq {project['ID']}&$select=ID,code&$top=1")
wbs_id = wbs["value"][0]["ID"]

s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-TWC-12T'"
              "&$select=ID")
crane = res["value"][0]["ID"]
s, res = call("/masterdata/Resources?$filter=IsActiveEntity eq true and code eq 'EQ-VIB-KIT'"
              "&$select=ID")
vibro = res["value"][0]["ID"]
print(f"  fixtures ready on PRJ-001")


def new_request(lines):
    s, d = call("/workflow/ResourceRequests", method="POST", body={
        "verticalType": "EQR", "project_ID": project["ID"],
        "company_ID": project["company_ID"], "wbs_ID": wbs_id,
        "needBy": "2026-10-01", "raisedBy": "demo", "raisedOn": "2026-08-17"})
    rid = d["ID"]
    for i, line in enumerate(lines, start=1):
        line = dict(line)
        line["lineNo"] = i
        call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=false)/lines",
             method="POST", body=line)
    s, act = call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=false)"
                  "/WorkflowService.draftActivate", method="POST", body={})
    return rid, (act.get("docNo") if isinstance(act, dict) else None)


def rr_action(rid, action, body=None):
    return call(f"/workflow/ResourceRequests(ID={rid},IsActiveEntity=true)"
                f"/WorkflowService.{action}", method="POST", body=body or {})


def approve(docno):
    s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{docno}'"
                   "&$select=ID&$expand=steps($select=ID,stepNo;$orderby=stepNo)")
    users = ["demo", "daud", "admin"]
    for i, st in enumerate(inst["value"][0]["steps"]):
        call(f"/collaboration/ApprovalSteps({st['ID']})/CollaborationService.approve",
             method="POST", body={"comment": "ok"}, user=users[i])


head("1. A requisition cannot be raised before the lines are decided")
rid, docno = new_request([
    {"resource_ID": crane, "description": "Tower crane", "qty": 1, "uom": "inst",
     "wbs_ID": wbs_id, "needBy": "2026-10-01"},
    {"resource_ID": vibro, "description": "Vibrator kits", "qty": 4, "uom": "kit",
     "wbs_ID": wbs_id, "needBy": "2026-09-15"},
])
print(f"      created {docno}")
check(409, "requisition on a Draft request", *rr_action(rid, "raisePurchaseRequisition"))
check(200, "submitted", *rr_action(rid, "submit"))
check(409, "requisition while still In Approval",
      *rr_action(rid, "raisePurchaseRequisition"))
approve(docno)

head("2. With every line IN_HOUSE there is nothing to procure")
check(200, "line 1 in-house", *rr_action(rid, "decideLine",
    {"lineNo": 1, "decision": "IN_HOUSE", "rationale": "Fleet crane available."}))
check(200, "line 2 in-house", *rr_action(rid, "decideLine",
    {"lineNo": 2, "decision": "IN_HOUSE", "rationale": "Yard has kits."}))
check(400, "requisition with no PROCURE line",
      *rr_action(rid, "raisePurchaseRequisition"))

head("3. The PROCURE lines raise a requisition — and only those lines")
rid2, docno2 = new_request([
    {"resource_ID": crane, "description": "Tower crane", "qty": 1, "uom": "inst",
     "wbs_ID": wbs_id, "needBy": "2026-10-01"},
    {"resource_ID": vibro, "description": "Vibrator kits", "qty": 4, "uom": "kit",
     "wbs_ID": wbs_id, "needBy": "2026-09-15"},
])
print(f"      created {docno2}")
rr_action(rid2, "submit")
approve(docno2)
check(200, "line 1 stays in-house", *rr_action(rid2, "decideLine",
    {"lineNo": 1, "decision": "IN_HOUSE", "rationale": "Fleet crane available."}))
check(200, "line 2 goes to procurement", *rr_action(rid2, "decideLine",
    {"lineNo": 2, "decision": "PROCURE", "rationale": "No kits free until November."}))

msg = check(200, "requisition raised", *rr_action(rid2, "raisePurchaseRequisition"))
check(409, "raising it twice", *rr_action(rid2, "raisePurchaseRequisition"))

s, prs = call(f"/material/PurchaseRequisitions?$filter=sourceRequest_ID eq {rid2}"
              "&$select=ID,prNo,status,syncStatus,project_ID,company_ID,raisedBy")
assert_(len(prs["value"]) == 1, "exactly one requisition exists for the request",
        len(prs["value"]))
pr = prs["value"][0]
print(f"        PR {pr['ID'][:8]}… status={pr['status']} sync={pr['syncStatus']}")

head("4. It is S/4's document, not ours")
assert_(pr.get("prNo") in (None, ""),
        "no requisition number was issued locally — S/4 assigns prNo", repr(pr.get("prNo")))
assert_("docNo" not in pr or pr.get("docNo") in (None, ""),
        "the requisition carries no KONSTRYX document number")
assert_(pr.get("syncStatus") == "NOT_SENT",
        "it starts NOT_SENT, so an unsent requisition cannot read as a good one",
        pr.get("syncStatus"))
assert_(pr.get("project_ID") == project["ID"] and pr.get("company_ID") == project["company_ID"],
        "project and company are carried for scoping without a join")

# The number range must not have been touched: no PR object is configured, and
# nothing should have quietly invented one. Assert the read worked before
# trusting its emptiness — an unauthorized or malformed query returns nothing
# too, and would pass this check without proving anything.
s, ranges = call("/authorization/NumberRangeObjects?$select=code", user="admin")
codes = {r["code"] for r in ranges["value"]} if s == 200 else None
assert_(codes is not None and len(codes) > 0,
        "the number-range catalogue is readable, so its contents mean something",
        f"[{s}] {sorted(codes) if codes else ranges}")
assert_(codes is not None and "PR" not in codes,
        "no PR number range exists or was created", sorted(codes or []))

head("5. Only the procured line travels, with its account assignment")
s, prLines = call(f"/material/PurchaseRequisitionLines?$filter=parent_ID eq {pr['ID']}"
                  "&$select=lineNo,qtyProcure,uom,estUnitPrice,estTotal,description,"
                  "wbs_ID,cbs_ID,sourceLine_ID,resource_ID,status&$orderby=lineNo")
lines = prLines["value"]
assert_(len(lines) == 1, "one line requisitioned, not both", len(lines))
line = lines[0]
print(f"        line {line['lineNo']}: {line['description']} "
      f"{line['qtyProcure']} {line['uom']} @ {line['estUnitPrice']} = {line['estTotal']}")
assert_(line.get("resource_ID") == vibro,
        "the requisitioned line is the vibrator kits, not the crane")
assert_(float(line.get("qtyProcure") or 0) == 4.0,
        "quantity carried from the request line", line.get("qtyProcure"))
assert_(line.get("wbs_ID") == wbs_id,
        "WBS travels — without it the commitment has no budget line to land on")
assert_(line.get("sourceLine_ID"), "the line points back at the request line it came from")
assert_(float(line.get("estTotal") or 0) > 0,
        "the approved value travels, not a fresh price", line.get("estTotal"))

s, rrLines = call(f"/workflow/ResourceRequestLines?$filter=parent_ID eq {rid2}"
                  "&$select=lineNo,lineStatus&$orderby=lineNo")
by_no = {l["lineNo"]: l["lineStatus"] for l in rrLines["value"]}
assert_(by_no.get(2) == "Requisitioned",
        "the procured request line reads Requisitioned", by_no.get(2))
assert_(by_no.get(1) != "Requisitioned",
        "the in-house line was left alone for the fleet to reserve", by_no.get(1))

head("6. The chain still reads end to end")
s, links = call(f"/workflow/DocumentLinks?$filter=fromDoc eq '{docno2}'"
                "&$select=fromDoc,toDoc,linkType")
types = {l["linkType"] for l in links.get("value", [])} if isinstance(links, dict) else set()
assert_("REQUISITION" in types,
        "a REQUISITION link ties the request to the requisition", sorted(types))

# The in-house half must still work after the procured half was split off.
check(200, "availability still runs for the in-house line",
      *rr_action(rid2, "runAvailabilityCheck"))
check(200, "and the in-house line still reserves",
      *rr_action(rid2, "createReservation"))

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
