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
| `SAP_COM_0053` | Purchase Requisition |
| `SAP_COM_0193` | Purchase Order |
| `SAP_COM_0107` | Business Partner |
| `SAP_COM_0009` | Product / material master |
| `SAP_COM_0060` | Material stock and ATP |
| `SAP_COM_0002` | Journal entries / GL line items (actual cost) |

> Confirm each scenario ID against the client's S/4 release before configuring.
> Scenario numbers and the APIs bound to them change between releases, and this
> list is written from the design, not from a live tenant.

### 2.2 On the BTP side — destination

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
| Purchase Requisition | `API_PURCHASEREQ_PROCESS_SRV` |
| Purchase Order | `API_PURCHASEORDER_PROCESS_SRV` |
| Goods movements | `API_MATERIAL_DOCUMENT_SRV` |
| Business Partner | `API_BUSINESS_PARTNER` |
| Product master | `API_PRODUCT_SRV` |
| GL line items | `API_GLACCOUNTLINEITEM` |
| Supplier invoice | `API_SUPPLIERINVOICE_PROCESS_SRV` |

The CAP service already declares the remote service in `application.yaml`:

```yaml
cds:
  remote.services:
    - name: "S4"
      destination:
        name: "S4HANA_CLOUD"
```

To consume an API, import its EDMX into `srv/external/` and generate a CDS
projection — `cds import`. Nothing is imported yet.

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

### 2.5 Primavera P6

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

1. **S/4 dev tenant access**, with communication arrangements for the scenarios
   above. Nothing can be built or validated without it (Q-09).
2. **Project sync trigger** — on release, on save, or scheduled. This decides
   how long a project can exist in KONSTRYX without an S/4 counterpart.
3. **P6 or S/4 as the schedule source per client**, since both cannot own the
   activity structure.
4. **Certificate or basic authentication** for production destinations.
5. **Sync frequency** per object, balanced against S/4 API rate limits.
