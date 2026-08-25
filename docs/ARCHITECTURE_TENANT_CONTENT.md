# Tenant content and the starter pack

**Status:** proposal, for decision. Raised by Ziya, 2026-08-25.
**Scope:** what KONSTRYX ships to a new tenant, what it reads, and what it refuses to assume.

---

## The question

> If the S/4 is a starter system, then we can deploy a starter content package and it
> can be synced with S/4 content to showcase a demo. If not, we should not have any
> starter pack — data has to be created by the user.

That is the right instinct, and this build has already paid for the lesson three times.

## Why shipping business data has hurt us

| What shipped | What happened |
|---|---|
| Org values (`YP05`, cost centre `10001000`, profit centre `10001000`) | Read off tenant my401381. On my434396 a live push came back **"Profit Center 10001000 does not exist"**. |
| Projects seeded `SENT`, with invented `s4Key` and system `S4HC_100` | `releaseToS4` refuses anything already `SENT`, so both demo projects were **permanently unreleasable**. `S4HC_100` exists nowhere. |
| Any of the above, once applied | Content packs are **insert-if-missing** and never update. A tenant seeded wrong **cannot be corrected by shipping a new pack** — which is why `konstryx-srv` still carries eight `S4_*` environment overrides. |

Three different symptoms, one disease: **the pack asserted a relationship with a system it had never seen.**

## Three tiers of content

The word "content pack" is currently doing three unrelated jobs. Separating them makes the decision obvious.

### Tier 0 — Framework content · *always ship*

Modules, authorization objects, activities, personas, approval schemes, number-range objects, attachment categories.

No S/4 dependency, no business meaning, no tenant-specific truth. Every tenant needs it and none of it can be wrong on a particular system. This is product, not data.

### Tier 1 — Organizational configuration · *never ship, always read*

Company codes, plants, purchasing organizations, purchasing groups, profit centres, cost centres, project profiles, company currency.

This is configuration of the **customer's own S/4**. No value is correct for every tenant, and a wrong one is undetectable until S/4 refuses a live document. It is now read through the `ITS_S4` destination by `AdminService.syncOrgFromS4()`, which mirrors what the system holds into `S4OrgValue` and fills each company from it.

One thing the sync deliberately does **not** do: map a KONSTRYX company to an S/4 company code. `INFC → 3310` is a business decision, not a fact discoverable by reading. It stays an explicit administrator step, and a company without one is reported as unmapped rather than guessed at.

### Tier 2 — Demo business data · *conditional — this is the decision*

Resource nodes, rates, norms, the CBS library, material and vendor mirrors, the sample project with its BOQ, and the canonical RR-2026-0188 thread.

Useful on an evaluation tenant sitting in front of a starter S/4. Actively harmful on a customer's own system, where it puts rows in their tenant that nothing can cleanly remove, and — now that release pushes immediately — could put **documents in their S/4**.

## How the tier-2 condition should be decided

| Option | Mechanism | Verdict |
|---|---|---|
| **(a) Detect** | Read S/4 and infer a starter system from company code `1710`, best-practice project profiles, standard plants | **Reject.** This is the same species of guess that produced the profit-centre bug. A customer who happens to use `1710` gets demo data in their books. |
| **(b) Declare** | A `contentProfile` parameter (`DEMO` \| `CLEAN`) on the tenant subscription | **Recommended.** Explicit, recorded, auditable, and set by whoever provisions the tenant — the one person who actually knows. |
| **(c) Ask** | First-run admin screen on an empty tenant | **Recommended as the safety net**, for a tenant provisioned before the parameter existed. |

**Default to `CLEAN`.** The two errors are not symmetrical: missing demo data costs one button click, while unwanted demo data in a customer system costs rows that cannot be cleanly removed, and possibly documents pushed into their S/4.

## What this needs built

1. **`ContentPack` gains a profile** (`FRAMEWORK` \| `DEMO`), and `ContentDeploymentService` applies only packs matching the tenant's profile. Today it applies everything at startup, unconditionally.
2. **A tenant `contentProfile` setting**, defaulting to `CLEAN`, settable at subscription and visible in Admin.
3. **Demo content must be removable.** Every demo row needs to record the pack that created it, and there needs to be a "remove demo content" action. This is currently impossible — nothing records a row's provenance, so demo and real data are indistinguishable the moment they land.
4. **Audit tier-2 content for false S/4 claims.** Fixed for projects (they now ship `NOT_SENT` with no key). The `Material` and `Vendor` mirrors still ship `s4Key` values that no connected system has ever confirmed.
5. **Order of operations on a new tenant** becomes: framework content → assign company codes → `syncOrgFromS4` → *then* optionally demo content. A demo project cannot be released before the org sync has run.

## Related: user-defined projects (item 3)

Built alongside this:

- **`ProjectService.createProject`** takes the header *and* its WBS elements in one call. Not a convenience — a project with no WBS element cannot be released, so a create that stopped at the header would manufacture exactly the state PRJ-002 is stuck in: complete-looking and permanently unreleasable.
- **`releaseToS4` now pushes immediately** instead of only queueing. It still writes `PENDING` first and the push still refuses anything that is not `PENDING`, so the release gate is walked rather than bypassed.

**Why synchronous rather than an outbound queue.** The person clicking is standing there, and a refusal they can read and act on beats a queue they have to go and inspect. A queue becomes the right answer when volume or S/4 downtime makes a blocking call unacceptable — worth revisiting, not needed at this scale.

**Open gap, not yet addressed:** a project edited *after* it has synced diverges from S/4 silently. There is no re-sync and no lock. That is the next real integrity problem, and it is bigger than it looks — the same question applies to WBS elements, which requisitions name by key.
