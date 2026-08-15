# KONSTRYX — Deployment Guide

How to get KONSTRYX from this repository into an SAP BTP subaccount, and how it
appears inside the SAP S/4HANA Public Cloud launchpad with Spaces and Pages.

> **Status of this document.** The build steps are verified — `mbt build`
> produces a deployable archive on this machine. The Cloud Foundry and S/4
> registration steps are written from the project's own descriptors and SAP's
> documented procedure, but **have not yet been executed**, because no KONSTRYX
> subaccount was available. Treat sections 3 onward as the intended runbook, to
> be corrected on the first real deployment.

---

## 1. What gets deployed

`mta.yaml` describes four things:

| Module / resource | Type | Purpose |
|---|---|---|
| `konstryx-srv` | Java (Spring Boot) | The CAP service — all eight OData V4 services |
| `konstryx-approuter` | Node.js | Entry point: performs XSUAA login, forwards the token |
| `konstryx-db-deployer` | HDI | Creates the schema — 234 tables and views |
| `konstryx-db` | HANA Cloud (hdi-shared) | The tenant database |
| `konstryx-auth` | XSUAA | Scopes, role templates, role collections |
| `konstryx-destination` | Destination | Outbound connections to S/4, SuccessFactors, Ariba |

The UI is served by `konstryx-srv` as static content and routed through the
approuter. That is deliberate for the first deployment — one moving part. When
the app is split into several task-focused apps, move the UI to the HTML5
Application Repository (see §7).

---

## 2. Prerequisites

**In the BTP subaccount**, entitlements for:

- Cloud Foundry runtime (at least 2 GB — the service asks for 1 GB, the router 256 MB)
- SAP HANA Cloud, `hdi-shared` plan
- Authorization and Trust Management (XSUAA), `application` plan
- Destination service, `lite` plan

**On the machine doing the deploy:**

- Cloud Foundry CLI 8+ with the MultiApps plugin
  ```bash
  cf install-plugin multiapps
  ```
- JDK 17 and Maven 3.9+ (see the repository README)
- Node.js 20+ and the MTA build tool
  ```bash
  npm install -g mbt
  ```

**A HANA Cloud instance must exist and be running** in the target subaccount
before deploying. HDI containers are created against it; if the instance is
stopped, the database deployer fails.

---

## 3. Build the archive

```bash
mvn clean install -DskipTests
```

```bash
mbt build -p=cf
```

This produces `mta_archives/konstryx_0.1.0.mtar` (~69 MB).

> **Known trap.** `mbt build` runs `npm install --production` at the repository
> root, which prunes `devDependencies` and removes `@sap/cds-dk`. The next Maven
> build then fails with `'cds' is not recognized`. Always run `npm install`
> after an MTA build.

---

## 4. Deploy to Cloud Foundry

```bash
cf login -a https://api.cf.<region>.hana.ondemand.com
```

```bash
cf target -o <ORG> -s <SPACE>
```

Confirm the target is the KONSTRYX subaccount and not another customer's before
continuing — the deploy creates services and routes in whatever space is set.

```bash
cf deploy mta_archives/konstryx_0.1.0.mtar
```

The deployer creates the three services, runs the HDI deployment, then starts
the service and the router. First deployment takes roughly 10–15 minutes,
most of it HDI.

**Verify:**

```bash
cf apps
```

Both `konstryx-srv` and `konstryx-approuter` should be `started`. Open the
approuter route in a browser — you should be redirected to an IAS/XSUAA login,
and after signing in reach the application.

---

## 5. Assign roles

The deployment creates three role collections from `xs-security.json`:

| Role collection | Contains |
|---|---|
| `KONSTRYX_Administrator` | Admin, MasterDataSteward |
| `KONSTRYX_ProjectControls` | ProjectManager, BudgetController |
| `KONSTRYX_SiteOperations` | ResourceCoordinator, SiteEngineer |

Assign these in the BTP cockpit under **Security → Users**, or map them to
identity provider groups under **Security → Role Collections**.

> These are the coarse layer only. They decide which services a user may reach
> at all. Everything finer — which company, which project, which activity on
> which object — is configured inside the application under Authorization
> Administration, and must be set up per client. A user with a role collection
> but no persona assignment can sign in and will see nothing.

**Bootstrap:** the first administrator needs `KONSTRYX_Administrator`. The
XSUAA `Admin` scope bypasses the data-driven authorization layer precisely so
that a fresh deployment can be configured; treat it as a privileged account.

---

## 6. Register in the S/4HANA Public Cloud launchpad

This is where **Spaces and Pages** come from. They are launchpad configuration —
not part of the application — which is why the app shows no navigation shell
when run standalone.

The registration chain must be complete end to end, or the tile will not appear:

```
BTP HTML5 app / approuter route
   → Destination (in S/4, pointing at the approuter)
   → LADI  (Launchpad App Descriptor Item)
   → IAM App, type "External App"
   → Business Catalog
   → Business Role
   → User
   → placed on a Page inside a Space
```

**Step by step, in S/4HANA Public Cloud:**

1. **Maintain Launchpad App Descriptor Items** — create an item pointing at the
   approuter URL. Register it with a **semantic object and action**, not a URL
   tile. KONSTRYX declares two inbounds in `manifest.json`:
   `KonstryxResourceRequest-display` and `KonstryxReservation-display`.
   A URL tile launches the app as a foreign window; an intent makes it a
   first-class app in the shell.
2. **Custom Catalog Extensions / Maintain Business Catalogs** — add the app to
   a custom business catalogue.
3. **Maintain Business Roles** — add the catalogue to a business role and
   assign users.
4. **Manage Launchpad Spaces** and **Manage Launchpad Pages** — create or edit
   a space, add a page, and place the tile in a section.

The theme, header, search and user menu then come from S/4. The app must not
set its own theme, or it will fight a client who switches between Morning and
Evening Horizon.

**Single sign-on:** establish trust between the BTP subaccount and the same
identity provider S/4 uses, so a user already signed into S/4 is not challenged
again by the approuter.

### If SAP Build Work Zone is used instead

Work Zone is a BTP service; it is not deployed into S/4. It federates S/4
content as a *content provider* and renders S/4 apps and KONSTRYX in one set of
Spaces and Pages. Use it when a client needs a single entry point across S/4,
SuccessFactors and Ariba. The application-side work is identical — the intents
above are what matter — so the choice can be changed later without touching
the app.

---

## 7. After the first deployment

- **Move the UI to the HTML5 Application Repository** once the app is split into
  several task-focused apps. Serving UI from the Java runtime does not scale or
  cache well.
- **Apply delivered content.** The runtime applies content packs on startup;
  `applyContentPacks` on the Authorization service re-runs them after an upgrade
  without a restart.
- **Configure the client's authorization model** — personas, permissions, and
  user assignments scoped by company and project.
- **Set the number range scope** per document type (GLOBAL or COMPANY) before
  the first document is created. Changing it afterwards means renumbering live
  data.

---

## 8. Upgrades

```bash
mvn clean install -DskipTests && mbt build -p=cf
```

```bash
cf deploy mta_archives/konstryx_0.1.0.mtar
```

HDI applies schema changes incrementally. Additive changes — new fields, new
entities — deploy safely. Destructive changes (dropping a column, changing a
type) need an explicit migration or they fail, by design.

**Client configuration is not overwritten.** Delivered content ships as
versioned packs applied insert-if-missing, so a client who has changed a number
range, a persona or a rate keeps that change through an upgrade. Only
`db/data` is re-imported on every deployment, and it holds nothing a client can
edit.

Because KONSTRYX is deployed per client, an upgrade is one deployment per
client. See the tracker suggestion S-02 on when shared multitenancy becomes
worth the retrofit.
