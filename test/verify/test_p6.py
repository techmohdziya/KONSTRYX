"""Primavera P6 import (PS-03): a project and its WBS tree arrive whole or not
at all, through the same validation an on-screen project gets."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"
USER = "demo"

# A P6 export, deliberately awkward in the ways real ones are:
#  - dates carry a time component
#  - WBS rows are ordered by P6's own object id, so 1002 (a child) precedes
#    1001 (its parent)
#  - one node uses <Id> rather than <Code>
P6_XML = """<?xml version="1.0" encoding="UTF-8"?>
<APIBusinessObjects>
  <Project>
    <Id>DHV-P3</Id>
    <Name>Dubai Hills Villas Phase 3</Name>
    <StartDate>2027-01-04T00:00:00</StartDate>
    <FinishDate>2029-06-29T00:00:00</FinishDate>
    <WBS>
      <ObjectId>1002</ObjectId>
      <ParentObjectId>1001</ParentObjectId>
      <Code>DHV-P3.1.1</Code>
      <Name>Piling</Name>
    </WBS>
    <WBS>
      <ObjectId>1001</ObjectId>
      <Code>DHV-P3.1</Code>
      <Name>Substructure</Name>
    </WBS>
    <WBS>
      <ObjectId>1003</ObjectId>
      <ParentObjectId>1001</ParentObjectId>
      <Id>DHV-P3.1.2</Id>
      <Name>Raft and pile caps</Name>
    </WBS>
    <WBS>
      <ObjectId>1004</ObjectId>
      <Code>DHV-P3.2</Code>
      <Name>Superstructure</Name>
    </WBS>
  </Project>
</APIBusinessObjects>
"""

# The reason DTDs are switched off. If the parser resolved this, the response
# would carry the contents of a file off the server.
XXE_XML = """<?xml version="1.0"?>
<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///c:/windows/win.ini"> ]>
<APIBusinessObjects>
  <Project><Id>&xxe;</Id><Name>Innocent looking</Name></Project>
</APIBusinessObjects>
"""


def call(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path.replace(" ", "%20"), data=data, method=method)
    req.add_header("Authorization", "Basic " + base64.b64encode(
        f"{USER}:{USER}".encode()).decode())
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


def head(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


s, ps = call("/project/Projects?$filter=IsActiveEntity eq true&$select=company_ID&$top=1")
company_id = ps["value"][0]["company_ID"]

head("1. Dry run changes nothing")
check(200, "validateOnly", *call("/project/importP6", method="POST", body={
    "fileName": "dhv-p3.xml", "content": P6_XML,
    "companyID": company_id, "validateOnly": True}))
s, after = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'DHV-P3'&$select=code")
ok = len(after["value"]) == 0
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} nothing was created")

head("2. The real import")
check(200, "imported", *call("/project/importP6", method="POST", body={
    "fileName": "dhv-p3.xml", "content": P6_XML,
    "companyID": company_id, "validateOnly": False}))

s, p = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'DHV-P3'"
            "&$select=ID,code,name,startDate,endDate,syncStatus,stage")
proj = p["value"][0]
print(f"      {proj['code']}  {proj['name']}")
print(f"      {proj['startDate']} to {proj['endDate']}   stage={proj['stage']}"
      f"   syncStatus={proj['syncStatus']}")
ok = (proj["startDate"] == "2027-01-04" and proj["endDate"] == "2029-06-29"
      and proj["syncStatus"] == "NOT_SENT")
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} dates stripped of their time component; imported project is NOT_SENT")

head("3. The WBS tree, with parents resolved despite the file's ordering")
s, w = call(f"/project/WBS?$filter=project_ID eq {proj['ID']}"
            "&$select=code,description,parent_ID&$orderby=code")
by_id = {}
s2, all_w = call(f"/project/WBS?$filter=project_ID eq {proj['ID']}&$select=ID,code")
for row in all_w["value"]:
    by_id[row["ID"]] = row["code"]
for row in w["value"]:
    parent = by_id.get(row["parent_ID"], "—")
    print(f"      {row['code']:14} {row['description']:22} parent: {parent}")

got = {row["code"]: by_id.get(row["parent_ID"]) for row in w["value"]}
expected = {"DHV-P3.1": None, "DHV-P3.1.1": "DHV-P3.1",
            "DHV-P3.1.2": "DHV-P3.1", "DHV-P3.2": None}
ok = got == expected
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} 4 elements, and Piling parents to Substructure"
      f" even though it appeared first in the file")

head("4. The same file again")
check(200, "re-import", *call("/project/importP6", method="POST", body={
    "fileName": "dhv-p3.xml", "content": P6_XML,
    "companyID": company_id, "validateOnly": False}))
s, p2 = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'DHV-P3'&$select=code")
ok = len(p2["value"]) == 1
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} still exactly one DHV-P3 — the duplicate code was refused"
      f" and nothing partial was left behind")
s, wbs2 = call(f"/project/WBS?$filter=project_ID eq {proj['ID']}&$select=code")
ok = len(wbs2["value"]) == 4
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} still exactly 4 WBS elements ({len(wbs2['value'])})")

head("5. What it refuses")
check(400, "not a P6 file", *call("/project/importP6", method="POST", body={
    "fileName": "notes.xml", "content": "<hello>there</hello>",
    "companyID": company_id}))
check(400, "not XML at all", *call("/project/importP6", method="POST", body={
    "fileName": "x.xml", "content": "code,name\nA,B", "companyID": company_id}))
check(400, "no company given", *call("/project/importP6", method="POST", body={
    "fileName": "dhv.xml", "content": P6_XML}))
check(400, "empty file", *call("/project/importP6", method="POST", body={
    "fileName": "empty.xml", "content": "", "companyID": company_id}))

head("6. An XML file that tries to read a file off the server")
st, msg = call("/project/importP6", method="POST", body={
    "fileName": "evil.xml", "content": XXE_XML, "companyID": company_id})
leaked = "for 16-bit app support" in str(msg).lower() or "[fonts]" in str(msg).lower()
ok = st == 400 and not leaked
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} [{st}] refused, nothing leaked: {str(msg)[:150]}")

head("7. The import runs, as an audit trail")
s, runs = call("/collaboration/MyImportRuns?$filter=target eq 'konstryx.prj.Project'"
               "&$select=ID,fileName,rowsAccepted,rowsRejected,status,message"
               "&$orderby=createdAt desc&$top=4")
ok = s == 200 and len(runs.get("value", [])) >= 3
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} [{s}] the person who ran the import can read it back")
for r in runs.get("value", []):
    print(f"      {r['fileName']:14} {r['status']:10} +{r['rowsAccepted']} -{r['rowsRejected']}"
          f"  {r['message'][:64]}")

rejected = [r for r in runs.get("value", []) if r["status"] == "REJECTED"]
if rejected:
    s, rows = call(f"/collaboration/MyImportRows?$filter=run_ID eq {rejected[0]['ID']}"
                   "&$select=lineNo,accepted,error,payload")
    ok = s == 200 and any(not x["accepted"] for x in rows.get("value", []))
    results.append(ok)
    print(f"  {'ok  ' if ok else 'FAIL'} and can see why each row failed:")
    for x in rows.get("value", []):
        if not x["accepted"]:
            print(f"          line {x['lineNo']}: {x['error']}")
            print(f"              {x['payload'][:70]}")

print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
