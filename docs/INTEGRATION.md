# KONSTRYX — Integration Guide

How KONSTRYX connects to SAP S/4HANA Public Cloud, SuccessFactors, Ariba and
Primavera P6: which system owns what, which direction data flows, and what has
to be configured on each side.

> **Status.** The mirror entities and the sync-configuration model exist in the
> data model. **No connector is implemented yet** — there is no S/4 dev tenant
> to build or validate one against (tracker Q-09 / S-15). This document is the
> integration design and the configuration runbook, not a description of
> working code.

---

## 1. Ownership — who masters what

The founding rule was *KONSTRYX-as-reader*: process that S/4 owns stays in S/4,
and KONSTRYX reads it. That still holds for procurement and finance.

**It does not hold for the project itself.** Decision of 2026-08-15: a project
is **created in KONSTRYX** and synchronised outward to S/4, or brought in from
Primavera P6. This reverses the original assumption that `prj.Project` is a
read-only S/4 mirror, and it changes the direction of the first integration
built.

| Object | Master | Direction |
|---|---|---|
| **Project, WBS** | **KONSTRYX** | **KONSTRYX → S/4**, or **P6 → KONSTRYX** |
| BOQ, CBS, budget | KONSTRYX | none — KONSTRYX only |
| Resource Request, Advisory, Availability, Reservation | KONSTRYX | none |
| Mobilization, Operation Log, Variation, De-mob, Closure | KONSTRYX | none |
| Purchase Requisition | S/4 | KONSTRYX → S/4 (create), S/4 → KONSTRYX (status) |
| Purchase Order, Goods Receipt, Invoice | S/4 | S/4 → KONSTRYX |
| Budget commitment / encumbrance | S/4 PS | S/4 → KONSTRYX |
| Actual cost | S/4 FI | S/4 → KONSTRYX |
| Business Partner / vendor | S/4 | S/4 → KONSTRYX |
| Material / product | S/4 | S/4 → KONSTRYX |
| Stock and ATP | S/4 | S/4 → KONSTRYX, on demand |
| Employee | SuccessFactors | SF → KONSTRYX |
| RFQ, bid, award | Ariba | KONSTRYX ↔ Ariba |
| Bank guarantees | S/4 Treasury | display only — never authored in KONSTRYX |

Mirror entities carry the `s4mirror` aspect: `s4Key`, `s4System`,
`lastSyncedAt`, `syncStatus`. Anything mirrored renders read-only in the UI
with a sync indicator, so a user can see when they are looking at a copy.

---

## 2. Connecting to S/4HANA Public Cloud

### 2.1 On the S/4 side — communication setup

For each integration scenario:

1. **Communication User** — `Maintain Communication Users`. Create a user with
   a strong password, or upload a client certificate for mTLS. One user per
   scenario keeps the audit trail readable.
2. **Communication System** — `Communication Systems`. Point it at the BTP
   subaccount host; assign the communication user for inbound and outbound.
3. **Communication Arrangement** — `Communication Arrangements`. Choose the
   scenario, bind the system and user, and note the resulting service URLs.

Scenarios needed:

| Scenario | Covers |
|---|---|
| `SAP_COM_0308` | Enterprise Project — **outbound project creation from KONSTRYX** |
| `SAP_COM_0102` | Purchase Requisition |
| `SAP_COM_0053` | Purchase Order |
| `SAP_COM_0107` | Business Partner |
| `SAP_COM_0009` | Product / material master |
| `SAP_COM_0060` | Material stock and ATP |
| `SAP_COM_0002` | Journal entries / GL line items (actual cost) |

> Confirm each scenario ID against the client's S/4 release before configuring.
> Scenario numbers and the APIs bound to them change between releases, and this
> list is written from the design, not from a live tenant.

### 2.2 On the BTP side — destination

> **Credentials never leave the BTP cockpit.** KONSTRYX resolves them at
> runtime through the destination service; the code, this repository and
> anyone developing against it only ever reference the destination *by name*.
> A communication-user password is entered once, by whoever administers the
> subaccount, into the destination below — not shared with developers, not
> committed, not sent over chat or email. If one has been shared that way,
> rotate it rather than reuse it.
>
> Nothing secret belongs in this repository. `application.yaml` holds
> destination names only, and the mock users in the default profile exist for
> local development and have no meaning once deployed.

Create a destination named **`S4HANA_CLOUD`** (the name the service expects —
see `application.yaml`, cloud profile):

```
Name            S4HANA_CLOUD
Type            HTTP
URL             https://<tenant>-api.s4hana.cloud.sap
Proxy Type      Internet
Authentication  BasicAuthentication   (or ClientCertificateAuthentication)
User            <communication user>
Password        <communication user password>
```

Additional properties for the CAP remote service:

```
sap-client      100
HTML5.DynamicDestination   true
```

Prefer **client certificate** authentication for production. Basic
authentication is acceptable for a development tenant only.

### 2.3 Released APIs

| Purpose | API |
|---|---|
| Project & WBS | `API_ENTERPRISE_PROJECT_SRV_0002` |
| Purchase Requisition | `API_PURCHASEREQUISITION_2` |
| Purchase Order | `API_PURCHASEORDER_PROCESS_SRV` |
| Goods movements | `API_MATERIAL_DOCUMENT_SRV` |
| Business Partner | `API_BUSINESS_PARTNER` |
| Product master | `API_PRODUCT_SRV` |
| GL line items | `API_GLACCOUNTLINEITEM` |
| Supplier invoice | `API_SUPPLIERINVOICE_PROCESS_SRV` |

**Nothing is imported and `srv/external/` does not exist**, deliberately. An
earlier draft of this document told you to `cds import` each EDMX and declare
`cds.remote.services` in `application.yaml`; that declaration was removed after
it crash-looped the deployed service on `CdsDefinitionNotFoundException` — CAP
resolves a declared remote service at startup whether or not anything consumes
it, and nothing did.

The live connectors call the APIs as raw OData through `S4Connection`, which
owns the credentials, the cookie jar and the CSRF handshake a write needs.
Nothing above that class ever sees a password. Adding an API means adding a
connector next to `S4ProjectConnector` and `S4RequisitionConnector`, not
generating a projection. `cds import` remains available if a flow ever needs
typed remote entities rather than a document-shaped POST.

**The two connectors speak different OData versions, and that is not an
oversight.** `API_ENTERPRISE_PROJECT_SRV_0002` is V2, so the project connector
sends `/Date(millis)/` and reads its result from a `d` wrapper.
`API_PURCHASEREQUISITION_2` is V4, so the requisition connector sends ISO dates
and navigation properties and reads its result from the top level. Copying one
connector's serialisation into the other will fail in ways that look like
authorisation errors.

### 2.4 Project sync — the outbound case

Because the project is mastered in KONSTRYX, this is the one flow that pushes:

1. A project is created and structured in KONSTRYX (WBS, CBS from a template).
2. On release, KONSTRYX calls `API_ENTERPRISE_PROJECT_SRV_0002` to create the
   Enterprise Project and its WBS elements in S/4.
3. S/4 returns its project ID; KONSTRYX stores it in `s4Key` and stamps
   `lastSyncedAt`.
4. Thereafter S/4 owns commitments and actuals against those WBS elements, and
   KONSTRYX reads them back.

**Failure handling matters more here than on inbound flows.** A project that
exists in KONSTRYX but failed to reach S/4 will accept requests and budgets
that can never post. Failed calls go to `konstryx.int.ErrorQueueItem` with the
payload retained, and the project must show its unsynchronised state in the UI
rather than looking normal.

### 2.5 Purchase requisition sync — the second outbound case

The requisition is the other flow that pushes, and it pushes for a different
reason: KONSTRYX decides **what** to buy, S/4 owns the document from the moment
it accepts one (D-21). The requisition therefore carries no KONSTRYX number and
draws no number range — `prNo` stays empty until S/4 issues one.

1. A resource request's advisory decision sends some lines to `PROCURE`.
2. `raisePurchaseRequisition` builds the requisition from those lines, carrying
   each line's quantity, approved value, need-by, **its WBS/CBS account
   assignment**, and what S/4 is being asked to supply — which depends on the
   resource's class (see §2.6): a material if the leaf is bought, a service
   product if it is hired or subcontracted.
3. `MaterialService.syncToS4` posts the whole document to
   `API_PURCHASEREQUISITION_2` in one deep insert — header, items, and each
   item's account assignment. Not a style choice: an item posted separately
   would be a requisition of its own, and one posted without its account
   assignment would commit against nothing.
4. S/4 returns the requisition number; `recordRequisitionResult` stamps it.
   That action is also the manual entry point, so a connector run and a
   correction write identical state.

**Three things stop the push before a connection is opened**, because each is a
KONSTRYX fact about the document rather than something S/4 must be contacted to
discover: a line whose resource has no material mapped, a line whose WBS
element has no `s4Key` yet (the project was never synced), and a requisition
S/4 has already numbered. A refused push leaves the requisition `NOT_SENT` and
does not count as an attempt.

**Configuration.** `S4_PR_SERVICE` (the V4 service root), `S4_PR_TYPE`
(default `NB`), `S4_PLANT`, `S4_PURCH_ORG`, `S4_PURCH_GROUP`, and account
assignment category `P` for a project. Unlike the project connector's defaults —
which were read off the tenant's own projects — these are S/4 standard-content
values and have **not** been confirmed against a live tenant: `SAP_COM_0102` is
not activated yet, so the live POST has never run. Neither has the payload
shape: `API_PURCHASEREQUISITION_2` is the V4-generation API, so the connector
sends ISO dates and navigation properties rather than V2's `/Date(millis)/` and
`to_` sets. **Read the tenant's own `$metadata` before trusting any of it.**

> **Correction, 24 Aug 2026.** This section previously named
> `API_PURCHASEREQ_PROCESS_SRV` under `SAP_COM_0053`, and the scenario table
> above listed `SAP_COM_0193` for the purchase order. All three were wrong.
> The consolidated requirements §15.2 put the requisition on
> `API_PURCHASEREQUISITION_2` / `SAP_COM_0102` and the order on
> `API_PURCHASEORDER_PROCESS_SRV` / `SAP_COM_0053`; `SAP_COM_0193` appears
> nowhere in them. The connector was repointed to match.

### 2.6 Class routes the leaf to S/4

The consolidated requirements make the resource **class** a fixed top dimension
of the hierarchy (spec §8, principle P10) for one reason: it decides how the
leaf is mastered and priced in S/4.

| Class | Internal cost | External cost |
|---|---|---|
| MATERIAL | — | S/4 product · `ResourceNode.s4Material` |
| MANPOWER | activity type × timesheet quantity | service product |
| EQUIPMENT · VEHICLE | activity type × operating hours | service product |
| SUBCONTRACT | — | service product |

**A leaf that carries neither cannot be costed; one that carries both without
declaring which applies will be costed twice.** So the routing lives in two
places, deliberately:

- **`ResourceNode.s4Material` / `.s4ServiceProduct`** — what a *requisition*
  orders. A requisition is raised before a vendor exists, so this is the
  generic entry, not any one vendor's catalogue code.
- **`RateMaster.s4ActivityType` / `.s4ServiceProduct`, keyed by `source` and
  `vendor`** — what a *cost* posts against. `IN_HOUSE` carries an activity type
  and no vendor; `HIRED` / `LSC_HIRED` carry a vendor and that vendor's own
  service product. Enforced in `MasterValidationHandler` — a row carrying both
  is refused.

That split is what the wireframe's own masters already show: one trade listed
three times on the same day, at three rates — our payroll, and two labour
subcontractors — each routing somewhere different.

### 2.7 Primavera P6

P6 is the alternative source: where a client plans in P6, the project and its
activity structure come **into** KONSTRYX rather than being created there.

- Exchange by file (XER / P6 XML) through the upload framework, or by P6 EPPM
  REST API where the client has it exposed.
- The activity ID is the cross-system key; WBS is the shared backbone.
- KONSTRYX pulls progress weekly for earned value; it does not write schedule
  back. P6 remains the planning system of record where it is in use.

---

## 3. SuccessFactors Employee Central

Employees are mastered in SuccessFactors and mirrored into the Workforce
module. Subcontractor staff have no SF record and stay KONSTRYX-owned — the
employee master must tolerate both.

**Destination `SUCCESSFACTORS`:**

```
Name            SUCCESSFACTORS
Type            HTTP
URL             https://<api-server>/odata/v2
Proxy Type      Internet
Authentication  OAuth2SAMLBearerAssertion
Token Service URL   https://<api-server>/oauth/token
Client Key      <API key from SF>
audience        www.successfactors.com
apiKey          <API key>
nameIdFormat    urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified
```

In SuccessFactors: register an **OAuth client** under *Manage OAuth2 Client
Applications*, upload the BTP subaccount's signing certificate, and grant the
technical user permission to the OData API.

**Entities used:** `PerPerson`, `PerPersonal`, `EmpEmployment`, `EmpJob`,
`FOCompany`, `FOCostCenter`.

Sync is scheduled and delta-based on `lastModifiedDateTime`. Source priority
for the employee master is **SuccessFactors → S/4HC → manual**, so an SF record
wins over a locally keyed one.

---

## 4. Ariba

Used only for the subcontract sourcing workflow — RFQ event, vendor invitation,
sealed bids, award. Material, manpower, equipment and vehicle flows do not
touch Ariba.

**Destination `ARIBA`:** OAuth2 client credentials against the Ariba API
gateway; the realm and the API key come from the client's Ariba account.

Bid Analysis is the one procurement step KONSTRYX owns end to end. Awards
flow back as a purchase order in S/4, not as an Ariba document.

---

## 5. Sync configuration and monitoring

The model already carries the operational side:

| Entity | Purpose |
|---|---|
| `admin.S4SyncConfig` | Per company and object: direction, trigger, service, active |
| `int.SyncRun` | One execution — records read and written, result |
| `int.ErrorQueueItem` | A failed message, with payload, error and attempt count |
| `int.S4DocXref` | KONSTRYX document ↔ S/4 document registry |

Error queue items are reprocessable rather than logged and lost. An
integration that silently drops a failed goods receipt is worse than one that
stops.

---

## 6. What must be decided before building connectors

1. **S/4 dev tenant access** (Q-09). Four things, and only the first is
   information a developer needs:
   - the tenant API host, e.g. `https://myNNNNNN-api.s4hana.cloud.sap`
   - a communication user created in S/4 — **its password goes straight into
     the BTP destination**, not to the development team
   - communication arrangements activated, `SAP_COM_0308` first because the
     project now syncs outward
   - a named S/4 administrator who can maintain them and re-activate on expiry
2. **Project sync trigger** — on release, on save, or scheduled. This decides
   how long a project can exist in KONSTRYX without an S/4 counterpart.
3. **P6 or S/4 as the schedule source per client**, since both cannot own the
   activity structure.
4. **Certificate or basic authentication** for production destinations.
5. **Sync frequency** per object, balanced against S/4 API rate limits.
