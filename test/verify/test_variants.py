"""Per-user table personalization: isolation between users, one default per
table, and administrator-published variants everyone can read but not edit."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"


def call(path, user, method="GET", body=None):
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
            msg = out[:300]
        return e.code, msg


results = []


def check(expected, label, status, payload):
    if isinstance(payload, dict):
        payload = payload.get("value", payload)
    mark = "ok  " if status == expected else "FAIL"
    print(f"  {mark} [{status}] {label}: {str(payload)[:150]}")
    results.append(status == expected)
    return payload


def head(t):
    print()
    print("=" * 74)
    print(t)
    print("=" * 74)


TABLE = "worklist.requestTable"
LAYOUT = json.dumps({"columns": ["docNo", "status", "needBy"], "sort": [{"docNo": "asc"}]})

head("1. Two people save a variant with the same name on the same table")
v_demo = check(201, "demo saves 'My open requests'", *call(
    "/collaboration/UserVariants", "demo", "POST", {
        "target": TABLE, "variantName": "My open requests",
        "payload": LAYOUT, "isDefault": True}))
v_daud = check(201, "daud saves a variant of the same name", *call(
    "/collaboration/UserVariants", "daud", "POST", {
        "target": TABLE, "variantName": "My open requests",
        "payload": LAYOUT, "isDefault": True}))

owner_ok = v_demo.get("user") == "demo" and v_daud.get("user") == "daud"
results.append(owner_ok)
print(f"  {'ok  ' if owner_ok else 'FAIL'} owner taken from the session, not the payload"
      f" (demo->{v_demo.get('user')}, daud->{v_daud.get('user')})")

check(409, "demo cannot reuse the name on the same table", *call(
    "/collaboration/UserVariants", "demo", "POST", {
        "target": TABLE, "variantName": "My open requests", "payload": LAYOUT}))

head("2. Nobody sees anyone else's")
s, mine = call(f"/collaboration/UserVariants?$filter=target eq '{TABLE}'"
               "&$select=variantName,user,isDefault", "demo")
users_seen = {v["user"] for v in mine["value"]}
ok = users_seen == {"demo"}
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} demo's list contains only: {users_seen}")

s, theirs = call(f"/collaboration/UserVariants?$filter=target eq '{TABLE}'"
                 "&$select=variantName,user", "daud")
users_seen = {v["user"] for v in theirs["value"]}
ok = users_seen == {"daud"}
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} daud's list contains only: {users_seen}")

# 404, not 403: a row this person cannot see should be indistinguishable from
# one that is not there. 403 would confirm the key exists.
check(404, "demo cannot edit daud's variant", *call(
    f"/collaboration/UserVariants({v_daud['ID']})", "demo", "PATCH",
    {"variantName": "Hijacked"}))
check(404, "demo cannot delete daud's variant", *call(
    f"/collaboration/UserVariants({v_daud['ID']})", "demo", "DELETE"))

head("3. One default per table per person")
v2 = check(201, "demo saves a second variant as the default", *call(
    "/collaboration/UserVariants", "demo", "POST", {
        "target": TABLE, "variantName": "Late deliveries",
        "payload": LAYOUT, "isDefault": True}))

s, mine = call(f"/collaboration/UserVariants?$filter=target eq '{TABLE}'"
               "&$select=variantName,isDefault&$orderby=variantName", "demo")
defaults = [v["variantName"] for v in mine["value"] if v["isDefault"]]
ok = defaults == ["Late deliveries"]
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} exactly one default, and it is the new one: {defaults}")
for v in mine["value"]:
    print(f"        {'*' if v['isDefault'] else ' '} {v['variantName']}")

ok_daud = True
s, theirs = call(f"/collaboration/UserVariants?$filter=target eq '{TABLE}'"
                 "&$select=variantName,isDefault", "daud")
ok_daud = all(v["isDefault"] for v in theirs["value"])
results.append(ok_daud)
print(f"  {'ok  ' if ok_daud else 'FAIL'} daud's own default was not touched by demo's change")

head("4. A published variant is readable by everyone, editable by nobody but admin")
check(403, "demo cannot publish", *call(
    "/collaboration/UserVariants", "demo", "POST", {
        "target": TABLE, "variantName": "Company standard",
        "payload": LAYOUT, "isPublic": True}))

pub = check(201, "admin publishes a standard layout", *call(
    "/collaboration/UserVariants", "admin", "POST", {
        "target": TABLE, "variantName": "Company standard",
        "payload": LAYOUT, "isPublic": True}))

s, mine = call(f"/collaboration/UserVariants?$filter=target eq '{TABLE}'"
               "&$select=variantName,isPublic", "daud")
names = sorted(v["variantName"] for v in mine["value"])
ok = "Company standard" in names
results.append(ok)
print(f"  {'ok  ' if ok else 'FAIL'} daud now sees {names}")

check(403, "daud cannot change the published variant", *call(
    f"/collaboration/UserVariants({pub['ID']})", "daud", "PATCH",
    {"payload": json.dumps({"columns": ["docNo"]})}))
check(200, "admin can change it", *call(
    f"/collaboration/UserVariants({pub['ID']})", "admin", "PATCH",
    {"payload": json.dumps({"columns": ["docNo", "status"]})}))

head("5. Rubbish is refused")
check(400, "no table identifier", *call(
    "/collaboration/UserVariants", "demo", "POST",
    {"variantName": "Nowhere", "payload": LAYOUT}))
check(400, "no name", *call(
    "/collaboration/UserVariants", "demo", "POST",
    {"target": TABLE, "payload": LAYOUT}))

print()
print("=" * 74)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 74)
sys.exit(0 if passed == len(results) else 1)
