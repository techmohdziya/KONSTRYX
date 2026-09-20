"""Attachments on any object, and the mandatory-category gate on submission."""
import json, urllib.request, base64, sys, os

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

head("6. A stored file knows how big it is")
# fileSize sat on the model unpopulated, so every file list showed a column of
# blanks. Two sizes rather than one: a handler that returned a constant, or
# that measured a drained stream and reported zero, would pass a single check.
for expected in (4096, 137):
    st, made = call("/collaboration/Attachments", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
        "objectDocNo": rr["docNo"], "fileName": f"size-{expected}.txt",
        "mimeType": "text/plain"})
    results.append(st == 201)
    aid = made["ID"]
    st2, _ = call(f"/collaboration/Attachments({aid})/content", method="PUT",
                  raw_body=b"x" * expected, content_type="text/plain")
    results.append(st2 in (200, 204))
    s3, meta = call(f"/collaboration/Attachments({aid})?$select=fileName,fileSize")
    got = meta.get("fileSize")
    ok = got == expected
    results.append(ok)
    print(f"  {'ok  ' if ok else 'FAIL'} {expected} bytes uploaded, "
          f"fileSize reads {got}")


head("7. What an attachment may not take with it when it goes")
# The drawing attached in section 4 is why that request could be submitted at
# all, and an approver is looking at it now. Deleting it would leave a decision
# recorded against a file nobody can produce.
s, evidence = call(f"/collaboration/Attachments?$filter=objectID eq {target['ID']}"
                   " and fileName eq 'GA-101-rev-C.pdf'&$select=ID,fileName")
drawing = evidence["value"][0]
status, refusal = call(f"/collaboration/Attachments({drawing['ID']})", method="DELETE")
ok = status == 409 and "in front of an approver" in str(refusal)
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} [{status}] the evidence under a live approval "
      f"stays: {str(refusal)[:120]}")

# A refusal with no way through is a rule people work around, so there is one.
check(200, "but a wrong upload can be withdrawn without being destroyed", *call(
    f"/collaboration/Attachments({drawing['ID']})", method="PATCH",
    body={"isObsolete": True}))
s, now = call(f"/collaboration/Attachments({drawing['ID']})?$select=fileName,isObsolete")
assert_ok = now.get("isObsolete") is True
results.append(assert_ok)
print(f"  {'ok  ' if assert_ok else 'FAIL'} and it is still there to produce, marked "
      f"obsolete: {now.get('fileName')}")

# Versions, on an object nobody has decided anything about.
made = []
for revision in ("first", "second", "third"):
    s, a = call("/collaboration/Attachments", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
        "fileName": "chain-test.pdf", "mimeType": "application/pdf",
        "note": revision})
    if s < 300:
        made.append(a)
results.append(len(made) == 3 and [a["version"] for a in made] == [1, 2, 3])
print(f"  {'ok  ' if len(made) == 3 else 'FAIL'} three uploads of one file are three "
      f"versions: {[a.get('version') for a in made]}")

# Deleting the middle one leaves its successor pointing at a row that is not
# there. Nothing reports that: the successor still reads fine and the history
# simply has a hole in it.
status, refusal = call(f"/collaboration/Attachments({made[1]['ID']})", method="DELETE")
ok = status == 409 and "pointing at nothing" in str(refusal)
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} [{status}] a superseded version cannot be deleted "
      f"out of the middle")

# The head is a different case and is allowed: nothing points at it, so nothing
# is left dangling. The rule is about what breaks, not about age.
check(204, "the latest version can go, because nothing points at it", *call(
    f"/collaboration/Attachments({made[2]['ID']})", method="DELETE"))
status, _ = call(f"/collaboration/Attachments({made[1]['ID']})", method="DELETE")
results.append(status == 204)
print(f"  {'ok  ' if status == 204 else 'FAIL'} [{status}] and then the one beneath it, "
      f"in order")
call(f"/collaboration/Attachments({made[0]['ID']})", method="DELETE")


head("8. The same rules through the other door")
# Attachments are exposed twice. Only one projection was handled, so uploading
# through the workflow service skipped the versioning entirely -- a second
# upload of the same file came out as version 1 again -- and skipped the check
# that the object exists at all. A polymorphic target has no foreign key to
# catch that; the handler is the foreign key, and one bound to one projection
# of two is half a constraint.
door = []
for revision in ("first", "second"):
    s, a = call("/workflow/RequestAttachments", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
        "fileName": "other-door.pdf", "mimeType": "application/pdf"})
    if s < 300:
        door.append(a)
ok = len(door) == 2 and [a["version"] for a in door] == [1, 2] \
    and door[1].get("supersedes_ID") == door[0]["ID"]
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} the workflow door versions too: "
      f"{[a.get('version') for a in door]}")

check(404, "and refuses a target that does not exist", *call(
    "/workflow/RequestAttachments", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest",
        "objectID": "00000000-0000-0000-0000-000000000000",
        "fileName": "orphan.pdf", "mimeType": "application/pdf"}))

status, refusal = call(f"/workflow/RequestAttachments({door[0]['ID']})", method="DELETE")
ok = status == 409
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} [{status}] and holds the chain on delete")
for a in reversed(door):
    call(f"/collaboration/Attachments({a['ID']})", method="DELETE")


head("9. A file has a size it may not exceed")
# There was no ceiling: any authenticated user could put a file of any size on
# any object, and the content lives in the database, so the cost is paid by
# every backup and restore of the tenant rather than by whoever uploaded it.
MAX_MB = int(os.environ.get("KX_ATTACHMENT_MAX_MB", "25"))
print(f"      ceiling is {MAX_MB} MB")

s, holder = call("/collaboration/Attachments", method="POST", body={
    "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
    "fileName": "GA-204-rev-B.pdf", "mimeType": "application/pdf"})
holder_id = holder["ID"]

under = b"x" * (256 * 1024)
check(204, "a file under the ceiling goes up", *call(
    f"/collaboration/Attachments({holder_id})/content", method="PUT",
    raw_body=under, content_type="application/pdf"))
s, sized = call(f"/collaboration/Attachments({holder_id})?$select=fileSize")
results.append(int(sized.get("fileSize") or 0) == len(under))
print(f"  {'ok  ' if int(sized.get('fileSize') or 0) == len(under) else 'FAIL'} and is "
      f"measured, not taken on trust: {sized.get('fileSize')} bytes")

over = b"x" * (MAX_MB * 1024 * 1024 + 64 * 1024)
status, refusal = call(f"/collaboration/Attachments({holder_id})/content", method="PUT",
                       raw_body=over, content_type="application/pdf")
ok = status == 400 and "GA-204-rev-B.pdf" in str(refusal) and "limit" in str(refusal)
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} [{status}] one over it is refused, by name: "
      f"{str(refusal)[:110]}")

# The check runs after the runtime has stored the bytes -- Content-Length is
# the client's own account of what it sent, and a cap that trusts it can be
# told any number. So the refusal has to unwind the write, not just report it.
s, after = call(f"/collaboration/Attachments({holder_id})?$select=fileSize")
kept = int(after.get("fileSize") or 0) == len(under)
results.append(kept)
print(f"  {'ok  ' if kept else 'FAIL'} and the refusal unwound it -- the file is still "
      f"the one that fitted: {after.get('fileSize')} bytes")

s, body = call(f"/collaboration/Attachments({holder_id})/content")
served = len(body) if isinstance(body, str) else -1
results.append(served == len(under))
print(f"  {'ok  ' if served == len(under) else 'FAIL'} including what it serves back: "
      f"{served} bytes")

call(f"/collaboration/Attachments({holder_id})", method="DELETE")


print()
print("=" * 74)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 74)
sys.exit(0 if passed == len(results) else 1)
