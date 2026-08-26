"""Gives every Fiori app the three files a Cloud Foundry deploy needs.

Only konstryx-ui was ever packaged. Every Fiori Elements app built since - and
the launchpad - had no ui5-deploy.yaml, no xs-app.json and no module in
mta.yaml, so an mbt build produced an archive containing one app and the deploy
would have succeeded while shipping none of the new screens.

Three things per app, and each of them fails quietly if it is missing:

  ui5-deploy.yaml   the zipper task. `ui5 build` emits a directory and no
                    archive; mbt looks for <module>.zip inside the build
                    result, finds nothing, and reports "copying ... ok" anyway.
  webapp/xs-app.json  the approuter's routing for that app. Without it the
                    app 404s behind the login with "does not have xs-app.json".
  package.json      ui5-task-zipper as a devDependency, or the custom task
                    named in ui5-deploy.yaml cannot be resolved at build time.

The MTA modules are written by the same run, because a file on disk that no
module references ships nothing.
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "app")
MTA = os.path.join(ROOT, "mta.yaml")

# konstryx-ui already has all of this and is left alone.
SKIP = {"konstryx-ui"}

XS_APP = {
    "welcomeFile": "/index.html",
    "authenticationMethod": "route",
    "routes": [
        {
            "source": "^/odata/(.*)$",
            "target": "/odata/$1",
            "destination": "srv-api",
            "authenticationType": "xsuaa",
            "csrfProtection": True,
        },
        {
            "source": "^(.*)$",
            "target": "$1",
            "service": "html5-apps-repo-rt",
            "authenticationType": "xsuaa",
        },
    ],
}

# Fiori Elements needs its own libraries on top of what a freestyle app uses.
LIBRARIES = [
    "sap.ui.core", "sap.m", "sap.f", "sap.uxap", "sap.ui.layout",
    "sap.ui.table", "sap.ui.export", "sap.ui.unified", "sap.fe.templates",
    "sap.ushell", "themelib_sap_horizon",
]

DEPLOY_YAML = """specVersion: "3.0"
metadata:
  name: {name}
type: application

# The Cloud Foundry build: the ordinary ui5.yaml plus the task that zips the
# output. That zip is not packaging, it is what the deploy ships - mbt looks
# for an artifact named after the MTA module and `ui5 build` emits a directory
# and no archive, so without this it finds nothing, says "copying ... ok"
# anyway, and uploads an empty payload.
builder:
  customTasks:
    - name: ui5-task-zipper
      afterTask: generateVersionInfo
      configuration:
        # Must match the MTA module name: mbt looks for <module>.zip.
        archiveName: {module}
        keepResources: true

framework:
  # SAPUI5 rather than OpenUI5: sap.fe.templates and sap.ui.export exist only
  # in SAPUI5, and every one of these screens is Fiori Elements.
  name: SAPUI5
  version: "1.150.0"
  libraries:
{libraries}
"""

MODULE = """  - name: {module}
    type: html5
    path: app/{module}
    build-parameters:
      builder: custom
      commands:
        - npm install
        - npx ui5 build --clean-dest --dest dist --config ui5-deploy.yaml
      supported-platforms: []
      build-result: dist

"""

ARTIFACT = """        - name: {module}
          artifacts:
            - {module}.zip
          target-path: resources/
"""


def apps():
    """Every directory that is a UI5 app: it has a webapp with a manifest."""
    found = []
    for name in sorted(os.listdir(APP_DIR)):
        path = os.path.join(APP_DIR, name)
        if name in SKIP or not os.path.isdir(path):
            continue
        if os.path.exists(os.path.join(path, "webapp", "manifest.json")):
            found.append(name)
    return found


def ui5_name(app):
    """The metadata name ui5 build wants: the app's own component id."""
    manifest = json.load(io.open(
        os.path.join(APP_DIR, app, "webapp", "manifest.json"), encoding="utf-8"))
    return manifest["sap.app"]["id"]


def write_deploy_yaml(app):
    libraries = "\n".join("    - name: " + lib for lib in LIBRARIES)
    io.open(os.path.join(APP_DIR, app, "ui5-deploy.yaml"), "w",
            encoding="utf-8").write(DEPLOY_YAML.format(
                name=ui5_name(app), module=app, libraries=libraries))


def write_xs_app(app):
    io.open(os.path.join(APP_DIR, app, "webapp", "xs-app.json"), "w",
            encoding="utf-8").write(json.dumps(XS_APP, indent=2) + "\n")


def add_zipper(app):
    path = os.path.join(APP_DIR, app, "package.json")
    package = json.load(io.open(path, encoding="utf-8"))
    dev = package.setdefault("devDependencies", {})
    dev.setdefault("ui5-task-zipper", "^3.6.1")
    dev.setdefault("@ui5/cli", "^4")
    io.open(path, "w", encoding="utf-8").write(json.dumps(package, indent=2) + "\n")


def update_mta(found):
    source = io.open(MTA, encoding="utf-8").read()

    # One html5 module per app, inserted ahead of the deployer that collects
    # them - mbt does not care about order, but a reader does.
    anchor = "  # Building the app is not the same as shipping it."
    modules = "".join(MODULE.format(module=app) for app in found
                      if f"- name: {app}\n    type: html5" not in source)
    if modules:
        source = source.replace(anchor, modules + anchor, 1)

    # And one artifact entry each on the content module, or the zip is built
    # and never uploaded.
    marker = """        - name: konstryx-ui
          artifacts:
            - konstryx-ui.zip
          target-path: resources/
"""
    artifacts = "".join(ARTIFACT.format(module=app) for app in found
                        if f"- name: {app}\n          artifacts:" not in source)
    if artifacts:
        source = source.replace(marker, marker + artifacts, 1)

    io.open(MTA, "w", encoding="utf-8").write(source)


def main():
    found = apps()
    for app in found:
        write_deploy_yaml(app)
        write_xs_app(app)
        add_zipper(app)
        print(f"  {app:30} ui5-deploy.yaml, xs-app.json, zipper")
    update_mta(found)
    print(f"\n  mta.yaml: {len(found)} html5 module(s) and artifact entries")


main()
