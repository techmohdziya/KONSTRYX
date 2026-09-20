"""End-to-end check of the approval engine against the running service."""
import json, urllib.request, base64, sys

BASE = "http://localhost:8090/odata/v4"
ADMIN = ("admin", "admin")
USER = ("demo", "demo")
OTHER = ("daud", "daud")


def call(path, user=USER, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path.replace(" ", "%20"), data=data, method=method)
    req.add_header("Authorization", "Basic " + base64.b64encode(
        f"{user[0]}:{user[1]}".encode()).decode())
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            msg = json.loads(raw).get("error", {}).get("message", raw)
        except Exception:
            msg = raw[:300]
        return e.code, msg


def line(expected, label, status, payload):
    if isinstance(payload, dict):
        payload = payload.get("value", payload)
    mark = "ok  " if status == expected else "FAIL"
    print(f"  {mark} [{status}] {label}: {payload}")
    return status == expected


results = []


def head(n, title):
    print()
    print("=" * 74)
    print(f"{n}. {title}")
    print("=" * 74)


head(1, "Delivered schemes and their value bands")
s, schemes = call("/authorization/ApprovalSchemes?$select=ID,code,name"
                  "&$expand=steps($select=stepNo,name,minAmount;$orderby=stepNo)", user=ADMIN)
if s != 200:
    print("  FAILED:", schemes); sys.exit(1)
for sc in sorted(schemes["value"], key=lambda x: x["code"]):
    print(f"  {sc['code']:10} {sc['name']}")
    for st in sc["steps"]:
        band = f"   from {st['minAmount']:,.0f}" if st["minAmount"] is not None else "   any amount"
        print(f"      step {st['stepNo']}  {st['name']:26}{band}")

head(2, "Value bands select the steps at submission")
s, rrs = call("/workflow/ResourceRequests?$select=ID,docNo&$orderby=docNo&$top=6")
if s != 200 or not rrs.get("value"):
    print("  FAILED:", rrs); sys.exit(1)
requests = rrs["value"]

cases = [(requests[0], 50000, 1, "below every threshold"),
         (requests[1], 300000, 2, "over the commercial threshold"),
         (requests[2], 2000000, 3, "over the director threshold")]

for rr, amount, expected_steps, why in cases:
    s, msg = call("/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
        "docNo": rr["docNo"], "amount": amount})
    s2, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{rr['docNo']}'"
                    "&$select=ID&$expand=steps($select=stepNo)")
    got = len(inst["value"][0]["steps"]) if s2 == 200 and inst.get("value") else 0
    mark = "ok  " if got == expected_steps else "FAIL"
    print(f"  {mark} {rr['docNo']}  {amount:>10,}  {why:32} -> {got} step(s)")
    results.append(got == expected_steps)

head(3, "Submission refuses what it should")
rr = requests[0]
results.append(line(409, "same object submitted twice", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": rr["ID"],
        "docNo": rr["docNo"], "amount": 1})))
results.append(line(404, "object that does not exist", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest",
        "objectID": "00000000-0000-0000-0000-0000000000ff",
        "docNo": "GHOST", "amount": 1})))
s, wbs = call("/project/WBS?$select=ID,code&$top=1")
wbs_id = wbs["value"][0]["ID"] if s == 200 and wbs.get("value") else rr["ID"]
results.append(line(400, "a real object whose type has no scheme", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.prj.WBSElement", "objectID": wbs_id,
        "docNo": "X", "amount": 1})))
results.append(line(400, "entity not in the model", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.does.NotExist", "objectID": rr["ID"],
        "docNo": "X", "amount": 1})))

head(4, "A three-step approval, decided in order")
target = requests[2]
s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{target['docNo']}'"
               "&$select=ID,objectDocNo,status,amount"
               "&$expand=steps($select=ID,stepNo,name,decision;$orderby=stepNo)")
instance = inst["value"][0]
steps = sorted(instance["steps"], key=lambda x: x["stepNo"])
print(f"  {instance['objectDocNo']}  amount {float(instance['amount']):,.0f}  status {instance['status']}")

results.append(line(409, "approving step 3 before step 1", *call(
    f"/collaboration/ApprovalSteps({steps[2]['ID']})/CollaborationService.approve",
    method="POST", body={"comment": "jumping the queue"})))
results.append(line(400, "rejecting with no reason", *call(
    f"/collaboration/ApprovalSteps({steps[0]['ID']})/CollaborationService.reject",
    method="POST", body={"comment": ""})))
results.append(line(200, "step 1 approved", *call(
    f"/collaboration/ApprovalSteps({steps[0]['ID']})/CollaborationService.approve",
    method="POST", body={"comment": "Checked against the plan."})))
results.append(line(409, "approving step 1 twice", *call(
    f"/collaboration/ApprovalSteps({steps[0]['ID']})/CollaborationService.approve",
    method="POST", body={"comment": "again"})))
results.append(line(403, "same person taking step 2 (separation of duties)", *call(
    f"/collaboration/ApprovalSteps({steps[1]['ID']})/CollaborationService.approve",
    method="POST", body={"comment": "and again"})))
results.append(line(200, "step 2 approved by someone else", *call(
    f"/collaboration/ApprovalSteps({steps[1]['ID']})/CollaborationService.approve",
    user=OTHER, method="POST", body={"comment": "Commercially sound."})))

head(5, "Rejection ends the whole approval")
s, r = call(f"/collaboration/ApprovalSteps({steps[2]['ID']})/CollaborationService.reject",
            user=ADMIN, method="POST", body={"comment": "Scope not funded this quarter."})
results.append(line(200, "step 3 rejected", s, r))

s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{target['docNo']}'"
               "&$select=objectDocNo,status"
               "&$expand=steps($select=stepNo,decision,actedBy,comment;$orderby=stepNo)")
final = inst["value"][0]
print(f"\n  {final['objectDocNo']}  ->  {final['status']}")
for st in final["steps"]:
    print(f"      step {st['stepNo']}  {st['decision']:9} by {str(st['actedBy']):6} \"{st['comment']}\"")
results.append(final["status"] == "REJECTED")

head(6, "Withdrawal releases the object")
victim = requests[1]
s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq '{victim['docNo']}'&$select=ID")
iid = inst["value"][0]["ID"]
results.append(line(200, "withdrawn", *call(
    f"/collaboration/ApprovalInstances({iid})/CollaborationService.withdraw",
    method="POST", body={"reason": "Superseded by a revised request."})))
results.append(line(200, "the object can be submitted again", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": victim["ID"],
        "docNo": victim["docNo"], "amount": 90000})))

head(7, "The decision reaches the document, not only the approval")
# Every other transition a document makes is written to its status history --
# submitted, advised, reserved, closed -- so a reader takes that history as the
# account of how it got where it is. The approval was the one transition missing
# from it, and it is the one somebody signed for: the document went from In
# Approval to Approved and the history stopped at In Approval. The decision was
# never lost, it was on the approval instance; but that is a different table
# keyed on a different column, and nothing on the document said to go and look.


def history(doc_no):
    s, h = call(f"/workflow/StatusHistory?$filter=docId eq '{doc_no}'"
                "&$select=seq,docType,fromState,toState,comment,changedBy"
                "&$orderby=seq", user=ADMIN)
    return h.get("value", []) if s == 200 and isinstance(h, dict) else []


def status_of(rr_id):
    s, r = call(f"/workflow/ResourceRequests?$filter=ID eq {rr_id}&$select=status",
                user=ADMIN)
    rows = r.get("value", []) if isinstance(r, dict) else []
    return rows[0]["status"] if rows else None


def shows(doc_no, to_state, word):
    """One entry landing on that state, saying who and why."""
    for e in history(doc_no):
        if e.get("toState") == to_state and word in str(e.get("comment", "")):
            return e
    return None


# requests[0] carries the single-step approval raised in section 2 and never
# decided, so it is the only one left to take all the way through.
approved = requests[0]
s, inst = call(f"/collaboration/ApprovalInstances?$filter=objectDocNo eq"
               f" '{approved['docNo']}' and status eq 'PENDING'"
               "&$select=ID&$expand=steps($select=ID,stepNo;$orderby=stepNo)")
pending = inst["value"][0] if s == 200 and inst.get("value") else None
results.append(line(200, "the last step of the small request approved", *call(
    f"/collaboration/ApprovalSteps({pending['steps'][0]['ID']})"
    "/CollaborationService.approve", user=ADMIN,
    method="POST", body={"comment": "Within the delegation."})))

for doc, state, word, why, now_reads in (
        (approved, "Approved", "Approved by", "an approval", "Approved"),
        (target, "Rejected", "Rejected by", "a rejection", "Rejected"),
        # Section 6 withdrew this one and submitted it again, so what it reads
        # now is In Approval -- the release and the second submission are both
        # in the history, which is the point.
        (victim, "Draft", "Withdrawn from approval by", "a withdrawal", "In Approval")):
    entry = shows(doc["docNo"], state, word)
    ok = entry is not None
    results.append(ok)
    print(f"  {'ok  ' if ok else 'FAIL'} {why} is written to {doc['docNo']}'s own "
          f"history: {(entry or {}).get('fromState')} -> {(entry or {}).get('toState')}"
          f"  {str((entry or {}).get('comment'))[:60]}")
    results.append(status_of(doc["ID"]) == now_reads)
    print(f"  {'ok  ' if status_of(doc['ID']) == now_reads else 'FAIL'} and the document "
          f"itself reads {now_reads}: {status_of(doc['ID'])}")

# The withdrawal released it and the resubmission took it back, both on the
# record. A document that can be pulled out of approval and pushed back in
# without either showing is one whose history has been edited by omission.
entries = history(victim["docNo"])
trail = [(e.get("fromState"), e.get("toState")) for e in entries]
# Read in order, which the wall clock could not deliver: the withdrawal and
# the resubmission are written inside one request and tie on changedOn, so
# ordering on it returned them either way round on successive runs. Each entry
# carries its place in the document's own account instead.
both = ("In Approval", "Draft") in trail and ("Draft", "In Approval") in trail
results.append(both)
print(f"  {'ok  ' if both else 'FAIL'} and both the release and the second submission "
      f"are on it: {' | '.join(f'{a}->{b}' for a, b in trail)}")

seqs = [e.get("seq") for e in entries]
ordered = seqs == sorted(seqs) and seqs == list(range(1, len(seqs) + 1))
results.append(ordered)
print(f"  {'ok  ' if ordered else 'FAIL'} numbered from one without a gap: "
      f"{' '.join(str(n) for n in seqs)}")

# The states have to chain: each entry leaves where the one before it arrived.
chained = all(trail[i][0] == trail[i - 1][1] for i in range(1, len(trail)))
results.append(chained)
print(f"  {'ok  ' if chained else 'FAIL'} and read in that order they join up, so the "
      f"account can be followed: {' | '.join(f'{a}->{b}' for a, b in trail)}")

# The entry has to say what the document was actually leaving. A history that
# guesses the state it came from reads exactly like one that knows.
entry = shows(approved["docNo"], "Approved", "Approved by")
results.append(entry.get("fromState") == "In Approval")
print(f"  {'ok  ' if entry.get('fromState') == 'In Approval' else 'FAIL'} the entry "
      f"names the state it left, read before it was overwritten: {entry.get('fromState')}")
results.append(entry.get("changedBy") == "admin")
print(f"  {'ok  ' if entry.get('changedBy') == 'admin' else 'FAIL'} and who decided it: "
      f"{entry.get('changedBy')}")
results.append(entry.get("docType") == "RR")
print(f"  {'ok  ' if entry.get('docType') == 'RR' else 'FAIL'} filed under the same "
      f"heading as the document's other transitions: {entry.get('docType')}")

# The generic action takes any entity name, and used to mark nothing at all --
# a document submitted through it sat in whatever state it was already in while
# approvers worked on it. The engine opens the approval, so the engine marks it.
fresh = requests[3]
before = status_of(fresh["ID"])
results.append(line(200, "a fourth request submitted through the generic action", *call(
    "/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": fresh["ID"],
        "docNo": fresh["docNo"], "amount": 40000})))
now = status_of(fresh["ID"])
results.append(now == "In Approval")
print(f"  {'ok  ' if now == 'In Approval' else 'FAIL'} says so on the document without "
      f"the caller setting it: {before} -> {now}")
opened = shows(fresh["docNo"], "In Approval", "Submitted for approval")
results.append(opened is not None)
print(f"  {'ok  ' if opened else 'FAIL'} and in its history, with the scheme that "
      f"decides it: {str((opened or {}).get('comment'))[:80]}")
results.append(len([e for e in history(fresh["docNo"])
                    if e.get("toState") == "In Approval"]) == 1)
print(f"  {'ok  ' if len([e for e in history(fresh['docNo']) if e.get('toState') == 'In Approval']) == 1 else 'FAIL'} "
      f"once, not once per owner — the handlers no longer write it too")


head(8, "The work waiting on a person, and nothing else")

# An inbox built from a looser rule than the one that decides is a list of work
# that is refused when opened. So it is checked against the decide path itself,
# not against a query that resembles it.

USERS = ("admin", "demo", "daud", "jin", "vikram", "rohan", "steward_pmi")


def inbox(who):
    st, body = call("/collaboration/MyApprovals", user=(who, who))
    return body.get("value", []) if st == 200 and isinstance(body, dict) else []


def pending_steps():
    st, body = call("/collaboration/ApprovalSteps?$filter=decision eq 'PENDING'"
                    "&$select=ID,stepNo,instance_ID&$top=200", user=ADMIN)
    return body.get("value", []) if st == 200 else []


# Give the inbox something to hold that reaches every step of the scheme.
for spare in requests[4:]:
    call("/collaboration/submitForApproval", method="POST", body={
        "entityName": "konstryx.wf.ResourceRequest", "objectID": spare["ID"],
        "docNo": spare["docNo"], "amount": 2000000})

open_steps = pending_steps()
current = {}
for st in open_steps:
    key = st["instance_ID"]
    if key not in current or st["stepNo"] < current[key]:
        current[key] = st["stepNo"]

offered = inbox("admin")
results.append(len(offered) > 0)
print(f"  {'ok  ' if offered else 'FAIL'} there is work waiting: {len(offered)} of "
      f"{len(open_steps)} pending steps are offered to admin")

# A document waits on one step at a time. Offering step 3 while step 1 is open
# invites an approval that the engine will refuse for being out of turn.
premature = [r for r in offered if r["stepNo"] != current.get(r["instanceId"])]
results.append(not premature)
print(f"  {'ok  ' if not premature else 'FAIL'} each row is the step its document is "
      f"actually waiting on, never a later one: "
      f"{len(offered) - len(premature)} of {len(offered)} in turn")

# A row you must open to find out what it is has moved the work, not organised it.
complete = [r for r in offered if r.get("docNo") and r.get("docType")
            and r.get("amount") is not None and r.get("stepNo") and r.get("waitingSince")]
results.append(len(complete) == len(offered))
print(f"  {'ok  ' if len(complete) == len(offered) else 'FAIL'} and carries enough to "
      f"decide whether to open it: {len(complete)} of {len(offered)} name the document, "
      f"its kind, its value and how long it has waited")

# The worklist is a query, so the order it is read in is asked for rather than
# baked in. What matters is that the service can answer it: an approval queue
# read newest-first is one where the document that has waited longest is the
# one furthest from the eye, and the screen opens on this order.
st, body = call("/collaboration/MyApprovals?$orderby=waitingSince", user=ADMIN)
oldest = [str(r.get("waitingSince")) for r in body.get("value", [])] if st == 200 else []
results.append(st == 200 and oldest == sorted(oldest) and len(oldest) == len(offered))
print(f"  {'ok  ' if oldest == sorted(oldest) and len(oldest) == len(offered) else 'FAIL'} "
      f"[{st}] and answers for oldest first, which is how the screen opens it: "
      f"{len(oldest)} rows in order")

# A worklist is paged and counted. Narrowing the answer instead of the query
# would return everything while appearing to have applied them.
st, body = call("/collaboration/MyApprovals?$top=1&$count=true", user=ADMIN)
results.append(st == 200 and len(body.get("value", [])) == 1
               and body.get("@count") == len(offered))
print(f"  {'ok  ' if st == 200 and len(body.get('value', [])) == 1 and body.get('@count') == len(offered) else 'FAIL'} "
      f"[{st}] a page of it is a page, and the count counts what was narrowed: "
      f"1 of {body.get('@count')}")

# Now the narrowing itself. The delivered schemes name no approver, which leaves
# every step open to anyone; naming one has to close it to everyone else.
st, personas = call("/authorization/Personas?$select=ID,code", user=ADMIN)
persona = {row["code"]: row["ID"] for row in personas.get("value", [])}
st, assigned = call("/authorization/UserAssignments?$select=user,persona_ID,isActive", user=ADMIN)
holders = {a["user"] for a in assigned.get("value", [])
           if a.get("isActive") and a.get("persona_ID") == persona.get("PROJECT_MANAGER")}

st, schemes = call("/authorization/ApprovalSchemes?$filter=code eq 'RR-STD'&$select=ID", user=ADMIN)
scheme = schemes["value"][0]["ID"]
st, defs = call(f"/authorization/ApprovalStepDefs?$filter=scheme_ID eq {scheme} and stepNo eq 1"
                "&$select=ID", user=ADMIN)
step_one = defs["value"][0]["ID"]


def name_approver(persona_id):
    """Configure the step through the draft, the way an administrator would."""
    st, _ = call(f"/authorization/ApprovalSchemes(ID={scheme},IsActiveEntity=true)"
                 "/AuthorizationService.draftEdit", user=ADMIN, method="POST",
                 body={"PreserveChanges": True})
    if st not in (200, 201):
        return False
    st, _ = call(f"/authorization/ApprovalStepDefs(ID={step_one},IsActiveEntity=false)",
                 user=ADMIN, method="PATCH", body={"approver_ID": persona_id})
    if st not in (200, 204):
        return False
    st, _ = call(f"/authorization/ApprovalSchemes(ID={scheme},IsActiveEntity=false)"
                 "/AuthorizationService.draftActivate", user=ADMIN, method="POST", body={})
    return st in (200, 201)


everyone = {who: len(inbox(who)) for who in USERS}
results.append(len({n for n in everyone.values()}) == 1 and min(everyone.values()) > 0)
print(f"  {'ok  ' if len(set(everyone.values())) == 1 else 'FAIL'} a step that names no "
      f"approver is open to every authorised user, and says so: "
      f"{', '.join(f'{u} {n}' for u, n in everyone.items())}")

results.append(name_approver(persona["PROJECT_MANAGER"]))
print(f"  {'ok  ' if results[-1] else 'FAIL'} step 1 is configured to ask for Project "
      f"Manager, held by {', '.join(sorted(holders)) or 'nobody'}")

narrowed = {who: len(inbox(who)) for who in USERS}
strangers = [who for who in USERS if who not in holders and narrowed[who]]
results.append(not strangers)
print(f"  {'ok  ' if not strangers else 'FAIL'} and the step leaves every inbox that "
      f"cannot act on it: {', '.join(f'{u} {everyone[u]}->{narrowed[u]}' for u in USERS)}")
results.append(all(narrowed.get(who) for who in holders))
print(f"  {'ok  ' if all(narrowed.get(w) for w in holders) else 'FAIL'} while the person "
      f"it asks for still has it: {', '.join(f'{w} {narrowed.get(w)}' for w in sorted(holders))}")

# Measuring a queue must not empty it.
results.append(len(pending_steps()) == len(open_steps))
print(f"  {'ok  ' if len(pending_steps()) == len(open_steps) else 'FAIL'} and reading an "
      f"inbox decides nothing: {len(open_steps)} pending steps before, "
      f"{len(pending_steps())} after")

name_approver(None)

# What the inbox offers has to be what the decide path accepts. Approving from
# the inbox is the only check of that which cannot pass by coincidence.
# Separation of duties only exists where there is a later step to come back to,
# so the row is chosen from a document that has one. A single-step approval
# would pass both checks below by simply being finished.
depth = {}
for st in open_steps:
    depth[st["instance_ID"]] = depth.get(st["instance_ID"], 0) + 1
taken = next(r for r in inbox("daud") if depth.get(r["instanceId"], 0) > 1)
st, msg = call(f"/collaboration/ApprovalSteps({taken['stepId']})/CollaborationService.approve",
               user=OTHER, method="POST", body={"comment": "taken from the inbox"})
results.append(st == 200)
print(f"  {'ok  ' if st == 200 else 'FAIL'} [{st}] a row opened from the inbox is one the "
      f"engine accepts: {taken['docNo']} step {taken['stepNo']}")

# Separation of duties is a rule about who may decide. An inbox that ignores it
# offers a person the refusal it is about to give them.
after = inbox("daud")
results.append(not [r for r in after if r["instanceId"] == taken["instanceId"]])
print(f"  {'ok  ' if not [r for r in after if r['instanceId'] == taken['instanceId']] else 'FAIL'} "
      f"and its next step does not come back to the same person, who would be refused it")
elsewhere = [r for r in inbox("jin") if r["instanceId"] == taken["instanceId"]]
results.append(len(elsewhere) == 1)
print(f"  {'ok  ' if len(elsewhere) == 1 else 'FAIL'} it moves on to somebody who may "
      f"take it: step {elsewhere[0]['stepNo'] if elsewhere else '-'} is waiting for jin")

# An inbox you have to leave in order to act on is a list of links. Deciding
# from the row has to be the same decision, refusals included.
st, msg = call(f"/collaboration/MyApprovals({elsewhere[0]['stepId']})"
               "/CollaborationService.reject", user=("jin", "jin"),
               method="POST", body={"comment": ""})
results.append(st == 400)
print(f"  {'ok  ' if st == 400 else 'FAIL'} [{st}] a rejection sent from the row still "
      f"has to say why: {str(msg)[:60]}")

st, msg = call(f"/collaboration/MyApprovals({elsewhere[0]['stepId']})"
               "/CollaborationService.approve", user=OTHER, method="POST",
               body={"comment": "not mine to take"})
results.append(st == 403)
print(f"  {'ok  ' if st == 403 else 'FAIL'} [{st}] and separation of duties holds for a "
      f"row nobody offered: {str(msg)[:70]}")

st, msg = call(f"/collaboration/MyApprovals({elsewhere[0]['stepId']})"
               "/CollaborationService.approve", user=("jin", "jin"),
               method="POST", body={"comment": "decided from the inbox"})
results.append(st == 200)
print(f"  {'ok  ' if st == 200 else 'FAIL'} [{st}] while the person holding it decides "
      f"without leaving the list: {str(msg)[:70]}")
results.append(not [r for r in inbox("jin") if r["stepId"] == elsewhere[0]["stepId"]])
print(f"  {'ok  ' if not [r for r in inbox('jin') if r['stepId'] == elsewhere[0]['stepId']] else 'FAIL'} "
      f"and the row leaves the inbox it was decided from")


print()
print("=" * 74)
passed = sum(1 for r in results if r)
print(f"  {passed} of {len(results)} checks passed")
print("=" * 74)
sys.exit(0 if passed == len(results) else 1)
