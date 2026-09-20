# app/

The KONSTRYX screens: Fiori Elements list report and object page over OData V4,
one app per document type, reached from the launchpad by intent.

## The shape of an app

Every app here is the same shape, and that is deliberate — a screen that is
only a list of rows with an object page behind it is a shape worth generating
rather than authoring:

```
konstryx-<thing>/
  annotations.cds          the screen — written by hand
  webapp/manifest.json     the intent, the tile, the OData source
  webapp/i18n/             the app's own name
  ui5.yaml, ui5-deploy.yaml, xs-app.json
```

New ones come from `tools/scaffold_app.py`, which copies an app already proven
in the launchpad rather than generating from a template — the new screen starts
from something known to run. It writes everything except `annotations.cds`:

```bash
python tools/scaffold_app.py konstryx-pull PullRequests material \
    KonstryxPullRequest "Stock Draws" "Material drawn from a store" \
    "sap-icon://shipping-status"
```

The third argument is the OData path rather than the CDS service name —
`material`, `workflow`, `project`, `masterdata` — because it is written
straight into the manifest's data source.

## What is written by hand, and why

**`annotations.cds`.** A screen is its columns — which ones, in what order,
under what names, and which of them carry colour. That is the part worth
deciding per entity, and the part a generator gets wrong.

Two things that are easy to miss:

- A **flattened projection column** (`project.code as projectCode`) is an
  element nothing else names, so without a `@title` the filter bar offers
  `projectCode` to the reader. Every app's annotations open with a `@title`
  block for exactly those.
- **Criticality is computed in the projection**, never in the annotation — a
  `case … end as xCriticality : Integer` in the service, referenced as
  `Criticality :` in the `UI.LineItem`. A threshold repeated in an annotation
  is a threshold that drifts between two screens showing the same figure.

## What is shared

**`value-helps.cds`** holds every value list and every cross-app link, once,
for all apps. Two rules it exists to keep:

- A value help must resolve **inside its own service**, which is why services
  carry read-only projections that exist only as value-list targets.
- **A screen must never semantic-link to itself.** Annotating a document's own
  number with its own semantic object turns the column that opens the object
  page into a popover offering nothing. Only cross-references carry
  `@Common.SemanticObject`, each with a `SemanticObjectMapping` so the jump
  lands on the document rather than an unfiltered list.

**`hierarchies.cds`** and **`services.cds`** are the model side: the tree
definitions, and the one file that pulls every app's annotations into the
build. `scaffold_app.py` registers a new app in both `services.cds` and the
root `package.json`.

## The launchpad

`launchpad/` is the shell, and its site is **generated** by
`tools/build_launchpad_site.py` — spaces, pages and tiles, each tile carrying a
live count read from the service. Register a screen there by **semantic object
and action**, never as a URL tile.

`konstryx-ui` holds the local static server (`serve.py`) that serves the apps
and the SAPUI5 runtime under one origin, and `router` is the approuter for
Cloud Foundry.

## Checking them

`tools/smoke_demo.py` walks the launchpad the way a browser does — every app in
the layout, its page, its component, and the entity set its list is bound to —
and fails if anything is unreachable. A tile can render, carry a number and
open an application that dies on its first request; the count comes from the
service and the app comes from the web server, and nothing joins the two until
someone clicks.
