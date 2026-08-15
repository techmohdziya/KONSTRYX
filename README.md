# KONSTRYX — CAP (Java) Application

SAP BTP extension for the Engineering & Construction industry, integrating with
SAP S/4HANA Public Cloud (and SAP Ariba / SuccessFactors where available).

**Status:** Sprint 0 skeleton (Realization Plan V01). Data model materialised
from `Development_Phase/KONSTRYX_Data_Model_Spec_v0.1.md` (MVP scope:
core chain + master data + MR vertical + integration platform).

## Layout

```
konstryx-cap/
├─ db/                     CDS domain model (one file per namespace)
│  ├─ common.cds           reusable aspects: scoped · s4mirror · documented
│  ├─ admin.cds            group, companies, roles, mdg-queue, sync config
│  ├─ master.cds           resource hierarchy, CBS library, rates, mirrors
│  ├─ prj.cds              project/WBS mirrors, BOQ, project CBS, allocations
│  ├─ bud.cds              budget header/lines, mobilization, approvals
│  ├─ wf.cds               RR → ADV → AVC → RES spine (all verticals)
│  ├─ mat.cds              MR vertical execution + S/4 PR/PO/GR mirrors
│  ├─ int.cds              sync runs, error queue, S/4 doc cross-reference
│  └─ ins.cds              cost-revenue snapshots (EVM partial)
├─ srv/                    OData V4 services + Java handlers
│  ├─ admin-service.cds        @path:/admin
│  ├─ masterdata-service.cds   @path:/masterdata
│  ├─ project-service.cds      @path:/project
│  ├─ budget-service.cds       @path:/budget
│  ├─ workflow-service.cds     @path:/workflow
│  ├─ material-service.cds     @path:/material
│  ├─ pom.xml
│  └─ src/main/java/com/inflexion/konstryx/   Spring Boot app + handlers
├─ app/                    Fiori / SAPUI5 UIs (placeholder)
├─ xs-security.json        XSUAA scopes / role templates / role collections
├─ mta.yaml               Cloud Foundry multitarget deployment descriptor
├─ pom.xml                Maven parent
├─ package.json           CAP tooling (@sap/cds)
└─ .cdsrc.json            OData V4, build target
```

## Modeling principles (from the spec)

- **Konstryx-as-reader** — S/4 objects are read-only mirror entities (`s4mirror`
  aspect); Konstryx never re-masters S/4 data.
- **Hybrid scoped masters** — `scoped` aspect carries GROUP / COMPANY scope and a
  promotion path (mdg-queue).
- **One workflow spine, six verticals** — RR→ADV→AVC→RES are vertical-agnostic
  with a `verticalType` discriminator (MVP wires MR; EQR/MPR/VR/SCR/SF are stubs).
- **Encumbrance model** — reservation lines lock budget on create; availability =
  budget − committed (S/4 PO) − encumbered (Konstryx RES) − actual (S/4 FI).

## Run locally

```bash
npm install            # CAP tooling
mvn spring-boot:run -pl srv     # Spring Boot, mocked auth, in-memory/H2 db
# OData service docs at http://localhost:8080/odata/v4/<service>/
```

## Deploy to Cloud Foundry

```bash
mbt build              # produces mta_archives/konstryx_0.1.0.mtar
cf deploy mta_archives/konstryx_0.1.0.mtar
```

## Sprint 0 open items (decide before S1)

Tenancy (single vs multitenant), CBS instance versioning, encumbrance currency,
BOQ import template columns, MSR substitution modelling, number-range scheme —
see spec §10.
