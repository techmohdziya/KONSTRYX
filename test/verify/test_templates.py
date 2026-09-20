"""Project templates: the library says what a high-rise usually looks like, the
project instance says what this one actually is.

The distinction is the whole point of the feature and the only thing that makes
it safe. A project being costed must not reshape itself because somebody edited
the library afterwards, so the structure is copied rather than referenced — and
a copy of a tree is only a tree if the children are rebuilt onto the copies. Get
that second pass wrong and every instance still points at the library node its
parent came from: the counts all look right, the parentage looks populated, and
the project's cost breakdown is a different shape from the one on screen.
"""
import base64
import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8090/odata/v4"


def call(path, user="admin", method="GET", body=None):
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
            msg = out[:400]
        return e.code, msg


results = []


def check(expected, label, status, payload):
    if isinstance(payload, dict):
        payload = payload.get("value", payload)
    ok = status in expected if isinstance(expected, tuple) else status == expected
    print(f"  {'ok  ' if ok else 'FAIL'} [{status}] {label}: {str(payload)[:150]}")
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


# ---------------------------------------------------------------- the template
head("1. What the library holds")

s, templates = call("/masterdata/ProjectTemplates?$select=ID,code,name,constructionType")
assert_(s == 200 and templates.get("value"), "templates are delivered",
        ", ".join(t["code"] for t in templates.get("value", [])))
template = templates["value"][0]
tpl_id, tpl_code, ctype = template["ID"], template["code"], template["constructionType"]

s, library = call(f"/masterdata/CBSLibrary?$filter=constructionType eq '{ctype}'"
                  "&$select=ID,code,name,level,parent_ID&$orderby=code")
library_nodes = library.get("value", [])
library_ids = {n["ID"] for n in library_nodes}
assert_(len(library_nodes) > 0, f"the {ctype} library has a structure to copy",
        f"{len(library_nodes)} node(s)")

s, planned = call(f"/masterdata/TemplateResources?$filter=template_ID eq {tpl_id}"
                  "&$select=ID,resource_ID")
template_resources = planned.get("value", [])
print(f"      {tpl_code} carries {len(template_resources)} default resource(s)")


# ------------------------------------------------------------- instantiating
head("2. A template instantiated into a project of its own")

check((200, 400, 409), "a project to instantiate into", *call(
    "/project/createProject", method="POST",
    body={"code": "PRJ-TPL1", "name": "Template target", "companyCode": "INFC",
          "startDate": "2026-09-01", "endDate": "2027-06-30",
          "wbs": [{"code": "TPL1-1", "description": "Enabling works"}]}))
s, made = call("/project/Projects?$filter=IsActiveEntity eq true and code eq 'PRJ-TPL1'"
               "&$select=ID,code")
pid = made["value"][0]["ID"]

check(404, "a template cannot be poured into a project that does not exist", *call(
    f"/masterdata/ProjectTemplates(ID={tpl_id},IsActiveEntity=true)"
    "/MasterDataService.instantiate", method="POST", body={"projectCode": "PRJ-NOPE"}))

check(200, f"{tpl_code} instantiated into PRJ-TPL1", *call(
    f"/masterdata/ProjectTemplates(ID={tpl_id},IsActiveEntity=true)"
    "/MasterDataService.instantiate", method="POST", body={"projectCode": "PRJ-TPL1"}))

# Instantiating twice would give the project two of every node and no way to
# tell them apart, which is unrecoverable rather than merely untidy.
check(409, "and refused a second time", *call(
    f"/masterdata/ProjectTemplates(ID={tpl_id},IsActiveEntity=true)"
    "/MasterDataService.instantiate", method="POST", body={"projectCode": "PRJ-TPL1"}))


# --------------------------------------------------------------- what arrived
head("3. The copy is the library's shape, not a count that happens to match")

s, instance = call(f"/project/CBS?$filter=project_ID eq {pid}"
                   "&$select=ID,code,level,parent_ID,libraryNode_ID&$orderby=code")
nodes = instance.get("value", [])
assert_(len(nodes) == len(library_nodes),
        "every library node of this construction type came across",
        f"{len(nodes)} instance node(s) for {len(library_nodes)} library node(s)")

assert_({n["code"] for n in nodes} == {n["code"] for n in library_nodes},
        "and they are the same nodes, by code rather than by count",
        str(sorted({n["code"] for n in library_nodes} ^ {n["code"] for n in nodes})
            or "identical"))

assert_(all(n.get("libraryNode_ID") in library_ids for n in nodes),
        "each one still says which library node it was copied from",
        f"{sum(1 for n in nodes if n.get('libraryNode_ID') in library_ids)} of {len(nodes)}")

# The one that matters. Copying a tree in one pass leaves every child pointing
# at the library node its parent came from -- the count is right, parent_ID is
# populated, and the project's structure is silently the library's.
instance_ids = {n["ID"] for n in nodes}
parented = [n for n in nodes if n.get("parent_ID")]
strays = [n for n in parented if n["parent_ID"] not in instance_ids]
assert_(parented and not strays,
        "and every child was rebuilt onto its parent's copy, not left pointing "
        "into the library",
        f"{len(parented)} parented, {len(strays)} still pointing at library nodes")

# A library that had no depth would make the check above pass on nothing.
assert_(len({n["level"] for n in library_nodes}) > 1,
        "the library has more than one level, so that was a real test",
        f"levels {sorted({n['level'] for n in library_nodes})}")


head("3b. A copy carries what the node is, not only where it sits")
# Both instantiation paths copied the code, the level and the parentage and
# neither copied the name or the cost nature, so a project arrived with
# twenty-five unnamed nodes all marked DIRECT. It survived because the
# delivered sample is seeded row by row rather than instantiated: the demo
# showed a correct tree while the code that builds a client's tree did not.
s, detailed = call(f"/project/CBS?$filter=project_ID eq {pid}"
                   "&$select=code,name,level,costNature,allocBasis&$orderby=code")
copied = {c["code"]: c for c in detailed.get("value", [])}
s, lib_detail = call(f"/masterdata/CBSLibrary?$filter=constructionType eq '{ctype}'"
                     "&$select=code,name,level,costNature,allocBasis&$orderby=code")
source = {c["code"]: c for c in lib_detail.get("value", [])}

unnamed = [c for c in copied.values() if not c.get("name")]
assert_(not unnamed, "every node came across with its name",
        f"{len(unnamed)} unnamed of {len(copied)}")

wrong = [code for code, node in copied.items()
         if node.get("name") != source.get(code, {}).get("name")]
assert_(not wrong, "and it is the library's name, not something like it",
        str(wrong[:4]) if wrong else f"{len(copied)} matched")

# The one that is not cosmetic. The allocation engine reads costNature to
# decide what is a pool and what absorbs, so an overhead arriving as direct
# cost is spread onto itself -- and the total still reconciles either way.
misclassified = [code for code, node in copied.items()
                 if node.get("costNature") != source.get(code, {}).get("costNature")]
assert_(not misclassified, "and its cost nature, which the allocation engine reads",
        str(misclassified[:4]) if misclassified
        else str(sorted({c["costNature"] for c in copied.values()})))

# If the library were DIRECT throughout, the check above would prove nothing.
assert_(len({c.get("costNature") for c in source.values()}) > 1,
        "the library distinguishes direct from indirect, so that was a real test",
        str(sorted({str(c.get("costNature")) for c in source.values()})))

assert_(all(copied[code].get("allocBasis") == source[code].get("allocBasis")
            for code in copied if code in source),
        "the allocation basis came too", "matched")


# ------------------------------------------------------------ planned resources
head("4. And the project starts with a resource list, before any request")

s, project_resources = call(f"/project/ProjectResources?$filter=project_ID eq {pid}"
                            "&$select=ID,resource_ID,buildUp")
got = project_resources.get("value", [])
assert_(len(got) == len(template_resources),
        "the template's default resources came with it",
        f"{len(got)} planned for {len(template_resources)} on the template")
assert_(all(r.get("buildUp") == "From template" for r in got) if got else True,
        "each saying where it came from, so a planner can tell it from their own",
        str({r.get("buildUp") for r in got}))
assert_({r["resource_ID"] for r in got} == {r["resource_ID"] for r in template_resources},
        "and they are the same resources the template named",
        f"{len(got)} matched")


# ------------------------------------------------------------------ the point
head("5. Editing the library afterwards does not reshape a project being costed")
# This is what the copy is for. The library is a master and editing it is
# ordinary; a project already being costed following that edit is not.
#
# It has to be an edit that actually takes. Moving a node's level is refused
# ("L2 needs a parent at L1"), so a check written that way would pass on a
# library that never moved -- green, and proving nothing. A rename is the
# ordinary library edit and it goes through.
node = library_nodes[0]
s, before = call(f"/project/CBS?$filter=project_ID eq {pid} and code eq '{node['code']}'"
                 "&$select=ID,code,name")
was = before["value"][0]["name"]

status, _ = call(f"/masterdata/CBSLibrary(ID={node['ID']},IsActiveEntity=true)",
                 method="PATCH", body={"name": "Renamed after instantiation"})
try:
    s, moved = call(f"/masterdata/CBSLibrary(ID={node['ID']},IsActiveEntity=true)"
                    "?$select=name")
    assert_(status < 300 and moved.get("name") == "Renamed after instantiation",
            "the library really did move, so the next check is a real one",
            f"[{status}] library now '{moved.get('name')}'")

    s, after = call(f"/project/CBS?$filter=project_ID eq {pid} and code eq '{node['code']}'"
                    "&$select=code,name")
    now = after["value"][0]["name"]
    assert_(now == was, f"and {node['code']} on the project did not follow it",
            f"project still '{now}' while the library reads '{moved.get('name')}'")
finally:
    call(f"/masterdata/CBSLibrary(ID={node['ID']},IsActiveEntity=true)",
         method="PATCH", body={"name": was})


print()
print("=" * 78)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 78)
sys.exit(0 if passed == len(results) else 1)
