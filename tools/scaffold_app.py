"""Scaffolds a list-report app from the one that already works.

Every KONSTRYX master screen is the same shape: a list of rows, an object page
behind each, one OData service, one intent. Generating that shape from a
generator template means owning the generator's output; copying the app that is
already deployed, already has a working ui5-deploy.yaml and xs-app.json, and is
already proven in the launchpad means the new screen starts from something
known to run.

What this does NOT write is the annotations. A screen is its columns — which
ones, in what order, under what names — and that is the part worth deciding per
entity rather than templating. Each app's annotations.cds is written by hand
beside this.

    python tools/scaffold_app.py konstryx-cbs CBSLibrary masterdata \\
        KonstryxCBS "Cost Breakdown Library" "The CBS the projects instantiate" \\
        sap-icon://tree
"""
import io
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "app", "konstryx-vendor")
SKIP = {"node_modules", "dist", "package-lock.json"}


def scaffold(app, entity_set, service, semantic_object, title, subtitle, icon):
    target = os.path.join(ROOT, "app", app)
    if os.path.isdir(target):
        shutil.rmtree(target)
    os.makedirs(target)

    for name in os.listdir(TEMPLATE):
        if name in SKIP:
            continue
        src, dst = os.path.join(TEMPLATE, name), os.path.join(target, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*SKIP))
        else:
            shutil.copy2(src, dst)

    component = app.replace("-", "")
    pairs = [
        ("konstryxvendor", component),
        ("konstryx-vendor", app),
        ("KonstryxVendor", semantic_object),
        ("Vendors", entity_set),
        ("Vendor", entity_set.rstrip("s")),
        ("/odata/v4/masterdata/", "/odata/v4/%s/" % service),
    ]
    for folder, _dirs, files in os.walk(target):
        for name in files:
            if not name.endswith((".json", ".js", ".cds", ".html",
                                  ".properties", ".yaml", ".md", ".mjs")):
                continue
            path = os.path.join(folder, name)
            text = io.open(path, encoding="utf-8").read()
            for old, new in pairs:
                text = text.replace(old, new)
            io.open(path, "w", encoding="utf-8").write(text)

    # Names inside the files were rewritten above; the names ON the files were
    # not, and a journey called VendorsListJourney in the orders app is the
    # kind of thing that survives for years because nothing ever fails on it.
    for folder, _dirs, files in os.walk(target):
        for name in files:
            renamed = name
            for old_name, new_name in pairs:
                renamed = renamed.replace(old_name, new_name)
            if renamed != name:
                os.rename(os.path.join(folder, name), os.path.join(folder, renamed))

    # The annotations are written by hand; the copied ones belong to another
    # entity and would annotate fields this one does not have.
    io.open(os.path.join(target, "annotations.cds"), "w", encoding="utf-8").write(
        "using MasterDataService as service from '../../srv/masterdata-service';\n")

    # The tile title and the app title are the same words and were set in two
    # places, so copying an app carried the old one's name into the new one's
    # shell header and its i18n bundle. Three apps shipped reading
    # "PurchaseOrders" and "Supplier master mirrored from ERP" before anyone
    # noticed, because the tile — the part people look at — was right.
    i18n_path = os.path.join(target, "webapp", "i18n", "i18n.properties")
    io.open(i18n_path, "w", encoding="utf-8").write(
        "# This is the resource bundle for %s\n\n"
        "#Texts for manifest.json\n\n"
        "#XTIT: Application name\n"
        "appTitle=%s\n\n"
        "#YDES: Application description\n"
        "appDescription=%s\n" % (component, title, subtitle))

    manifest_path = os.path.join(target, "webapp", "manifest.json")
    manifest = json.load(io.open(manifest_path, encoding="utf-8"))
    inbounds = manifest["sap.app"]["crossNavigation"]["inbounds"]
    key = next(iter(inbounds))
    inbounds[key]["title"] = title
    inbounds[key]["subTitle"] = subtitle
    inbounds[key]["icon"] = icon
    io.open(manifest_path, "w", encoding="utf-8").write(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    register(app)
    print("  %-28s %-22s %s" % (app, entity_set, key))


def register(app):
    """Adds the app to every register that has to know about it."""
    package_path = os.path.join(ROOT, "package.json")
    package = json.load(io.open(package_path, encoding="utf-8"))
    if "app/" + app not in package.get("sapux", []):
        package.setdefault("sapux", []).append("app/" + app)
        io.open(package_path, "w", encoding="utf-8").write(
            json.dumps(package, indent=2) + "\n")

    services_path = os.path.join(ROOT, "app", "services.cds")
    services = io.open(services_path, encoding="utf-8").read()
    if app + "/annotations" not in services:
        services = services.rstrip("\n") + "\n\nusing from './%s/annotations';\n" % app
        io.open(services_path, "w", encoding="utf-8").write(services)

    deploy(app)


def deploy(app):
    """Adds the app where the deploy looks for apps, which is somewhere else.

    Registering the annotations and the sapux list is what makes a screen build
    locally; mta.yaml is what makes it exist in the cloud. Three apps scaffolded
    before this reached the launchpad with tiles and no module behind them, so a
    deploy would have shipped thirty of thirty-three and offered three tiles
    that resolve to nothing. Both halves are written here because both were
    always required and only one was ever remembered.
    """
    mta_path = os.path.join(ROOT, "mta.yaml")
    mta = io.open(mta_path, encoding="utf-8").read()

    module = ("  - name: %s\n"
              "    type: html5\n"
              "    path: app/%s\n"
              "    build-parameters:\n"
              "      builder: custom\n"
              "      commands:\n"
              "        - npm install\n"
              "        - npx ui5 build --clean-dest --dest dist --config ui5-deploy.yaml\n"
              "      supported-platforms: []\n"
              "      build-result: dist\n\n") % (app, app)
    artifact = ("        - name: %s\n"
                "          artifacts:\n"
                "            - %s.zip\n"
                "          target-path: resources/\n") % (app, app)

    # Both lists are kept in name order, so each entry goes before the first
    # that sorts after it rather than at the end.
    if ("path: app/%s\n" % app) not in mta:
        later = [m.start() for m in re.finditer(
            r"^  - name: (konstryx-[\w-]+)\n    type: html5\n", mta, re.M)
            if m.group(1) > app]
        at = min(later) if later else mta.index("\nresources:")
        mta = mta[:at] + module + mta[at:]
    if ("- name: %s\n          artifacts:\n" % app) not in mta:
        entries = [(m.group(1), m.start()) for m in re.finditer(
            r"^        - name: (konstryx-[\w-]+)\n          artifacts:\n", mta, re.M)]
        later = [pos for name, pos in entries if name > app]
        if later:
            at = min(later)
        else:
            last = max(pos for _, pos in entries)
            at = mta.index("target-path: resources/\n", last) + len("target-path: resources/\n")
        mta = mta[:at] + artifact + mta[at:]
    io.open(mta_path, "w", encoding="utf-8").write(mta)


def main():
    if len(sys.argv) != 8:
        raise SystemExit(__doc__)
    scaffold(*sys.argv[1:])


main()
