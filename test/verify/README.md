# Verification suites

Each suite drives the running service over HTTP and asserts what came back.
They are not unit tests: they exercise the product through the same OData
endpoints a screen uses, with the same authentication, which is the only way to
catch the things that have actually gone wrong here — a handler that silently
protected nothing, a projection whose annotation did not cover the draft path,
a read filter that replaced the caller's own filter instead of narrowing it.

## Running them

```bash
bash test/verify/run_all.sh
```

Each suite gets a **freshly started service**, so none inherits another's data.
H2 is in-memory, so a restart is a clean database. This matters more than it
sounds: the attachment suite makes a category mandatory, which would then block
every submission in the approval suite if they shared a database.

Results land in `test/verify/results.txt`, and each suite's full output in
`out_<suite>.txt`.

To run one on its own, start the service yourself and:

```bash
python test/verify/test_foundations.py
```

## What each one covers

| Suite | Covers |
|---|---|
| `test_foundations` | Authorization enforcement and instance filtering, scoped-master isolation between two stewards, master validation, number ranges, delivered content packs, CSV import in all three modes, promotion |
| `test_approval` | Value bands selecting steps, order enforcement, separation of duties, rejection closing the whole approval, withdrawal releasing the object |
| `test_persona_approver` | An approver persona configured entirely through the administration API, then enforced; delegation |
| `test_attachments` | Polymorphic target validation, versioning with the supersedes chain, binary round-trip, mandatory category blocking submission |
| `test_variants` | Per-user isolation of saved layouts, one default per table per person, administrator-published variants |
| `test_project` | Project mastered in KONSTRYX, validation, sync state protected on both the active record and the draft, release gating, connector callback |
| `test_p6` | Primavera XML import, WBS parenting despite file ordering, all-or-nothing on re-import, XXE refusal |
| `test_content` | The starter data a tenant receives: pack versions, insert-if-missing, and a client edit surviving an upgrade |
| `test_schedule` | Critical path over a network with a known answer, forward and backward pass, float |
| `test_rates` | Effective dating that something resolves: the rate in force on a date, company over group |
| `test_boq` | The bill of quantities, the project's own CBS, and the allocation between them |
| `test_chain` | The spine: request, approval, advisory, availability, reservation — and what each refuses |
| `test_planning` | The planning slice against its own specification |
| `test_budget` | The budget engine end to end: control, commitment, encumbrance, attribution, baseline |
| `test_distribution` | Distribution by WBS template: one decision covering many lines, and the split adding up |
| `test_procurement` | The PROCURE half of the advisory split — requisition, order, receipt, invoice, three-way match |
| `test_issue` | The IN_HOUSE half — stock drawn from a store, issued, counted on site, and measured against its norm |
| `test_overview` | How far a reservation has come, against the chain its vertical actually has — and what is waiting on somebody versus on a module that does not exist |
| `test_variation` | Varying a reservation that is already running — what it may move, what it may not, and what the move is written down as |
| `test_certification` | A payment application certified, checked against the arithmetic rather than against a stored total |
| `test_execution` | Signing a day's work and posting it against the reservation that paid for it |
| `test_finance` | Exchange rates and the CBS roll-up |
| `test_productivity` | Output per man-hour, per site location |
| `test_calendar` | The fiscal period grid, and which period a date falls in |

## Why these exist as files

Most of this was verified once when it was built and then never re-checked,
because the checks lived in a terminal session rather than in the repository.
The first time something regressed, nothing would have noticed. A check that is
not kept is not verification, it is a demonstration.

## Known gaps

- Nothing here covers the UI. The blank screen and the 83px tree table were both
  found by looking at the browser, and neither would have been caught by these.
- The suites assume the mock users in the development profile. They will need
  real users, or a seeded set, to run against a deployed tenant.
