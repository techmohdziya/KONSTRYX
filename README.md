# KONSTRYX — build workspace

SAP BTP extension for the Engineering & Construction industry, built on
**SAP CAP (Java)** with a **freestyle SAPUI5** front end, integrating with
SAP S/4HANA Public Cloud (and SAP Ariba / SuccessFactors where available).

The functional source of record — FTS documents, wireframe v12, requirements
register, backlog — stays in the read-only OneDrive folder
`Products/konstrux/Konstrucx/`. This repository is the build.

## Layout

```
KONSTRYX DEV/
├─ db/                  CDS domain model, one file per namespace
│  ├─ common.cds        aspects: scoped · s4mirror · documented
│  ├─ admin.cds         group, companies, roles, mdg-queue, sync config
│  ├─ master.cds        resource hierarchy, CBS library, rates, mirrors
│  ├─ prj.cds           project/WBS mirrors, BOQ, project CBS, allocations
│  ├─ bud.cds           budget header/lines, mobilization, approvals
│  ├─ wf.cds            RR → ADV → AVC → RES spine (all verticals)
│  ├─ mat.cds           MR vertical execution + S/4 PR/PO/GR mirrors
│  ├─ int.cds           sync runs, error queue, S/4 doc cross-reference
│  ├─ ins.cds           cost-revenue snapshots (EVM partial)
│  └─ data/             CSV fixtures — the canonical PRJ-001 threads
├─ srv/                 OData V4 services + Java handlers
│  └─ src/main/java/com/inflexion/konstryx/
├─ app/konstryx-ui/     freestyle SAPUI5 app (sap.tnt shell, 10-step chain)
├─ xs-security.json     XSUAA scopes / role templates / role collections
├─ mta.yaml             Cloud Foundry multitarget descriptor
└─ pom.xml              Maven parent
```

## Prerequisites

| Tool | Version here | Notes |
|---|---|---|
| JDK | SapMachine 17.0.20 | `JAVA_HOME` is set at user scope |
| Maven | 3.9.16 | `C:\Users\Ziya\Documents\Claude\tools\apache-maven-3.9.16` |
| Node | 24.16 | for `@sap/cds-dk` tooling only |
| SAPUI5 runtime | 1.150.0 | `C:\Users\Ziya\Documents\Claude\sapui5-rt-1.150.0` |

**Version pairing matters.** CAP Java 4.x is the line that accepts
cds-compiler 6 (shipped by `@sap/cds-dk` 9). Pinning CAP Java back to 3.x
without also pinning cds-dk to 8 fails at runtime with
*"CDS Compiler version 6 is not supported"* — the services start and expose
metadata, but every query 500s.

## Run it

Two tiers, two ports.

```bash
mvn clean install -DskipTests
```

```bash
java -jar srv/target/konstryx-srv-exec.jar
```

The service listens on **8090** — 8080 belongs to the UI5 dev server. Browse
`http://localhost:8090/` for the service index, or `/odata/v4/<service>/`
for admin · masterdata · project · budget · workflow · material.

```bash
python app/konstryx-ui/serve.py 8081
```

The app is then at `http://localhost:8081/index.html`. `serve.py` maps
`/resources` to the local SAPUI5 runtime and reverse-proxies `/odata` to the
CAP service, so both share one origin — no CORS, and the relative URIs in
`manifest.json` keep working when the approuter serves the app in Cloud
Foundry.

### Local users

The service runs with mocked auth. Personas mirror the `xs-security.json`
role templates one-for-one:

| User | Password | Roles |
|---|---|---|
| `admin` | `admin` | Admin, MasterDataSteward |
| `vikram` | `vikram` | ProjectManager |
| `rohan` | `rohan` | BudgetController, ProjectManager |
| `daud` | `daud` | SiteEngineer, ResourceCoordinator |
| `jin` | `jin` | ResourceCoordinator |

A 403 from a service is usually correct behaviour, not a bug — check the
`@requires` annotation on the service before assuming otherwise.

## What is wired to CAP, and what is not

| Area | State |
|---|---|
| RR worklist | **Live** on `WorkflowService.RequestOverview`, filters pushed to the service |
| RR → ADV → AVC → RES | Modelled and seeded; queryable over OData |
| Request detail page | Still reads `webapp/model/data.json` |
| Chain steps 2–10 | Still read `data.json`; MOB/OPL/VAR/DMB/CLS have no CDS entities |
| S/4 integration | Mirror entities exist; no connector implemented |
| Handlers | Stub only — no submit/approve/baseline, no encumbrance logic |

## Seed data

`db/data/` carries PRJ-001 Marina Heights Tower, the four-company group,
three WBS elements and CBS instances, five EQR resource codes, and
RR-2026-0188 walked through RR → ADV → AVC → RES with all five lines. The
MR/MPR/VR request headers are seeded without lines, matching what the
wireframe worklists show.

> The five EQR line values sum to **AED 685,080** and reconcile exactly
> against the per-WBS commitment breakdown in the wireframe. The wireframe's
> request header states **716,044**, and its L1 rate of 320/day implies
> 115,200 rather than the stated 276,480. The line-level figures are seeded
> as the self-consistent set; the header figure is not reproduced. This needs
> a decision before the numbers reach a demo.

## Deploy

```bash
mbt build
```

```bash
cf deploy mta_archives/konstryx_0.1.0.mtar
```

`mta.yaml` still has gaps: no approuter module, no UI module, and the
`konstryx-db-deployer` points at `gen/db`, which the Java build does not
produce. Fix those before the first Cloud Foundry deployment.
