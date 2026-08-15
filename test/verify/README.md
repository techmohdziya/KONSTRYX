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
