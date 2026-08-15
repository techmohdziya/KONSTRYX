"""Attachments on any object, and the mandatory-category gate on submission."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"
ADMIN = ("admin", "admin")
USER = ("demo", "demo")


def call(path, user=USER, method="GET", body=None, raw_body=None, content_type=None):
    if raw_body is not None:
        data = raw_body
    else:
        data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path.replace(" ", "%20"), data=data, method=method)
    req.add_header("Authorization", "Basic " + base64.b64encode(
        f"{user[0]}:{user[1]}".encode()).decode())
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", content_type or "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            out = r.read().decode(errors="replace")
            return r.status, (json.loads(out) if out.strip().startswith(("{", "[")) else out)
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
    mark = "ok  " if status == expected else "FAIL"
    print(f"  {mark} [{status}] {label}: {str(payload)[:160]}")
    results.append(status == expected)
    return payload


def head(title):
    print()
    print("=" * 74)
    print(title)
    print("=" * 74)


head("1. Attaching to a real object")
s, rrs = call("/workflow/ResourceRequests?$select=ID,docNo&$orderby=docNo&$top=4")
requests = rrs["value"]
rr = requests[0]
print(f"  target {rr['docNo']}  {rr['ID']}")

a1 = check(201, "first upload", *call("/collaboration/Attachments", method="POST", body={
    "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
    "fileName": "site-layout.pdf", "mimeType": "application/pdf",
    "note": "Layout issued for construction."}))
print(f"       version={a1.get('version')}  objectDocNo={a1.get('objectDocNo')}")
results.append(a1.get("version") == 1)
results.append(a1.get("objectDocNo") == rr["docNo"])
print(f"  {'ok  ' if a1.get('version') == 1 else 'FAIL'} version 1, doc number denormalised from the target")

a2 = check(201, "same file name uploaded again", *call(
    "/collaboration/Attachments", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
        "fileName": "site-layout.pdf", "mimeType": "application/pdf",
        "note": "Revision B."}))
ok = a2.get("version") == 2 and str(a2.get("supersedes_ID", "")).lower() == str(a1["ID"]).lower()
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} became version {a2.get('version')}, superseding the first"
      f" (supersedes_ID set: {bool(a2.get('supersedes_ID'))})")

head("2. Attaching to something that is not there")
check(404, "object does not exist", *call("/collaboration/Attachments", method="POST", body={
    "entityName": "konstryx.wf.ResourceRequest",
    "objectID": "00000000-0000-0000-0000-0000000000ff",
    "fileName": "ghost.pdf", "mimeType": "application/pdf"}))
check(400, "entity not in the model", *call("/collaboration/Attachments", method="POST", body={
    "entityName": "konstryx.not.Real", "objectID": rr["ID"],
    "fileName": "x.pdf", "mimeType": "application/pdf"}))
check(400, "no file name", *call("/collaboration/Attachments", method="POST", body={
    "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
    "mimeType": "application/pdf"}))

head("3. Binary content streams in and back out")
pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"
s, r = call(f"/collaboration/Attachments({a1['ID']})/content", method="PUT",
            raw_body=pdf, content_type="application/pdf")
check(204, "content uploaded", s, r)
s, back = call(f"/collaboration/Attachments({a1['ID']})/content")
same = isinstance(back, str) and back.startswith("%PDF-1.4")
results.append(same)
print(f"  {'ok  ' if same else 'FAIL'} [{s}] content read back intact ({len(back) if isinstance(back, str) else '?'} bytes)")

head("4. A mandatory category blocks submission")
s, ao = call("/authorization/AuthObjects?$filter=entityName eq 'konstryx.wf.ResourceRequest'"
             "&$select=ID,code", user=ADMIN)
auth_object_id = ao["value"][0]["ID"]
print(f"  auth object {ao['value'][0]['code']}")

check(201, "category 'Approved drawing' made mandatory for resource requests", *call(
    "/authorization/AttachmentCategories", user=ADMIN, method="POST", body={
        "code": "APPR_DWG", "name": "Approved drawing",
        "authObject_ID": auth_object_id, "isMandatory": True, "isActive": True}))

s, cats = call("/authorization/AttachmentCategories?$filter=code eq 'APPR_DWG'&$select=ID",
               user=ADMIN)
cat_id = cats["value"][0]["ID"]

target = requests[3]
check(400, "submission refused with the reason", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": target["ID"],
        "docNo": target["docNo"], "amount": 10000}))

check(201, "the drawing is attached", *call("/collaboration/Attachments", method="POST", body={
    "entityName": "konstryx.wf.ResourceRequest", "objectID": target["ID"],
    "fileName": "GA-101-rev-C.pdf", "mimeType": "application/pdf",
    "category_ID": cat_id}))

check(200, "submission now goes through", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": target["ID"],
        "docNo": target["docNo"], "amount": 10000}))

head("5. The object's attachment history")
s, all_a = call(f"/collaboration/Attachments?$filter=objectID eq {rr['ID']}"
                "&$select=fileName,version,note&$orderby=version")
for a in all_a["value"]:
    print(f"      v{a['version']}  {a['fileName']:22} {a['note']}")

print()
print("=" * 74)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 74)
sys.exit(0 if passed == len(results) else 1)
