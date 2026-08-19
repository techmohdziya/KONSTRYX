#!/usr/bin/env python3
"""Generates the delivered content packs from the canonical CSV fixtures.

Why this is generated rather than hand-written
----------------------------------------------
`test/data/*.csv` is the canonical demo dataset — the wireframe's own masters
and its one end-to-end transaction thread. It reaches the development database
because CAP loads those CSVs into H2, and it must never reach a client tenant
that way: the cloud profile sets `initialization-mode: never` precisely so a
fixture cannot be imported into somebody's production schema.

Content packs are the supported route for delivered rows, so the same dataset
has to exist in both forms. Transcribing ~330 rows by hand would guarantee the
two drift, and a drift here is invisible: the deployed tenant would simply hold
slightly different numbers from the ones every local test asserts. So the packs
are compiled from the CSVs, and regenerating them is how they stay equal.

    python tools/build_content_packs.py            # write the packs
    python tools/build_content_packs.py --check    # fail if they are stale

What it does not do
-------------------
It does not invent anything. Every row, every value and every key is whatever
the CSV says. Where the CSV has a gap, the pack has the same gap — a fixture
defect is fixed in the fixture, not silently patched on the way out.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = ROOT / "test" / "data"
OUT_DIR = ROOT / "srv" / "src" / "main" / "resources" / "content"

# ---------------------------------------------------------------------------
# Column types.
#
# Declared explicitly, never inferred. Inference reads "0001000211" as an
# integer and drops the leading zeros off a business partner number, and reads
# the CBS code "00" as zero. Only genuinely numeric and boolean columns appear
# here; everything absent stays a string, which is what dates, timestamps,
# enum values, codes and UUID foreign keys all want.
# ---------------------------------------------------------------------------
DECIMAL = "decimal"
INTEGER = "integer"
BOOLEAN = "boolean"

# konstryx.sys.ContentPack.description is String(255), and the audit row is
# written last — so an over-long description does not truncate, it throws after
# every data row has been inserted and takes the whole pack down with it on
# rollback. Cheap to assert here; confusing to diagnose from a tenant log.
MAX_DESCRIPTION = 255

# CAP stores a UUID lower-cased. Several fixtures spell theirs with upper-case
# hex — 4C000000-…-000000000016 — and the CSV loader quietly normalises them on
# the way in, so the database holds 4c000000-…. A pack that repeated the
# fixture's own casing would therefore never match what it had itself
# delivered: the idempotency check would miss, the insert would proceed, and the
# primary key would collide with the row already sitting there. It fails only on
# the second apply and only for the entities whose ids contain hex letters,
# which is about as narrow a window as a bug can hide in.
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")

TYPES: dict[str, dict[str, str]] = {
    "konstryx.admin.Company": {"isDefault": BOOLEAN},
    "konstryx.auth.Persona": {"isActive": BOOLEAN, "isDelivered": BOOLEAN},
    "konstryx.auth.PersonaPermission": {"granted": BOOLEAN},
    "konstryx.auth.UserAssignment": {"isActive": BOOLEAN},
    "konstryx.master.RateMaster": {"rateValue": DECIMAL, "netRate": DECIMAL},
    "konstryx.master.ProductivityRate": {
        "outputPerHr": DECIMAL,
        "outputPerManday8h": DECIMAL,
    },
    "konstryx.master.ConsumptionRate": {
        "consRate": DECIMAL,
        "wastageAllowancePct": DECIMAL,
        "netRate": DECIMAL,
    },
    "konstryx.prj.Project": {"contractValue": DECIMAL, "syncAttempts": INTEGER},
    "konstryx.prj.WBSElement": {"syncAttempts": INTEGER},
    "konstryx.prj.CBSInstance": {"budgetAmount": DECIMAL},
    "konstryx.prj.BOQ": {"contractValue": DECIMAL},
    "konstryx.prj.BOQItem": {
        "qty": DECIMAL,
        "budgetQty": DECIMAL,
        "rate": DECIMAL,
        "amount": DECIMAL,
        "billedToDate": DECIMAL,
        "cumDoneQty": DECIMAL,
        "cumDonePct": DECIMAL,
        "certifiedPct": DECIMAL,
    },
    "konstryx.prj.BOQItemResource": {
        "qtyPerUom": DECIMAL,
        "totalQty": DECIMAL,
        "unitRate": DECIMAL,
        "amountPerUnit": DECIMAL,
        "totalAmount": DECIMAL,
        "difficultyPct": DECIMAL,
    },
    "konstryx.wf.ResourceRequest": {"isSubstitution": BOOLEAN, "prFlag": BOOLEAN},
    "konstryx.wf.ResourceRequestLine": {
        "lineNo": INTEGER,
        "qty": DECIMAL,
        "estUnitCost": DECIMAL,
        "estTotal": DECIMAL,
    },
    "konstryx.wf.AvailabilityCheckLine": {
        "atpQty": DECIMAL,
        "stockQty": DECIMAL,
        "expectedQty": DECIMAL,
    },
    "konstryx.wf.ReservationLine": {
        "qty": DECIMAL,
        "dailyRate": DECIMAL,
        "encumberedAmount": DECIMAL,
        "consumedToDate": DECIMAL,
        "burnPct": DECIMAL,
        "costToDate": DECIMAL,
        "drift": DECIMAL,
    },
    "konstryx.eq.EquipmentRequestLine": {
        "instances": INTEGER,
        "durationDays": INTEGER,
        "operatorsReq": INTEGER,
    },
    "konstryx.mpr.ManpowerRequestLine": {
        "heads": INTEGER,
        "durationDays": INTEGER,
        "ratePerHeadDay": DECIMAL,
    },
    "konstryx.mpr.TimesheetEntry": {
        "headsPresent": INTEGER,
        "regularHrs": DECIMAL,
        "otHrs": DECIMAL,
        "costAmount": DECIMAL,
    },
}


def item(entity: str, csv_name: str, keys: list[str], selfref: str | None = None) -> dict:
    """One `items[]` entry: which entity, which fixture, and what identifies a row.

    `keys` is what makes the pack idempotent, so it has to be the row's real
    natural key rather than a convenient one. Scope columns belong in it for
    every scoped master: a company-local override of a group rate legitimately
    shares the group row's resource and effective date, and keying on those two
    alone would treat the override as already delivered and drop it.
    """
    return {
        "entity": entity,
        "csv": csv_name,
        "keys": keys,
        "selfref": selfref,
    }


# ---------------------------------------------------------------------------
# The packs.
#
# `sequence` is dependency order, and it is load-bearing: user assignments name
# a persona, a company and a project that three earlier packs deliver, and
# nothing in the pack ids implies that.
#
# The split is by what a client legitimately receives, which is not the same cut
# as "one file per module":
#   ORGANISATION / MASTER_DATA / DEMO_PROJECT  are the demo estate
#   PERSONAS                                   is product content — the role
#     vocabulary and its grants, which is what turns konstryx.auth from a schema
#     into an enforced control
#   DEMO_USERS                                 is separate from PERSONAS so a
#     client can take the persona model without inheriting demo logins
# ---------------------------------------------------------------------------
PACKS = [
    {
        "packId": "ORGANISATION",
        "version": "1.0.0",
        "sequence": 20,
        "description": (
            "Company group and legal entities. Everything else is scoped by "
            "these, so they are delivered first."
        ),
        "file": "organisation.json",
        "items": [
            item("konstryx.admin.CompanyGroup", "konstryx.admin-CompanyGroup.csv", ["code"]),
            item("konstryx.admin.Company", "konstryx.admin-Company.csv", ["code"]),
        ],
    },
    {
        "packId": "PERSONAS",
        "version": "1.0.0",
        "sequence": 30,
        "description": (
            "Persona vocabulary and its grants against the delivered "
            "authorization catalogue. Product content: with no rows here "
            "PermissionService resolves no grants and only the Admin scope "
            "bypass keeps a tenant usable. Clients rename and re-grant freely."
        ),
        "file": "personas.json",
        "items": [
            item("konstryx.auth.Persona", "konstryx.auth-Persona.csv", ["code"]),
            item(
                "konstryx.auth.PersonaPermission",
                "konstryx.auth-PersonaPermission.csv",
                ["persona_ID", "authObject_ID", "activity_code"],
            ),
        ],
    },
    {
        "packId": "MASTER_DATA",
        # 1.1.0 adds the mirrored S/4 materials the resource hierarchy now
        # references. A pack is applied once per version, so an installation
        # already holding 1.0.0 would never see the new rows under the old
        # number — the version has to move for an upgrade to carry them.
        "version": "1.1.0",
        "sequence": 40,
        "description": (
            "The wireframe's own masters: resource hierarchy, CBS library, "
            "rates, norms, templates and the mirrored vendors and materials."
        ),
        "file": "master-data.json",
        "items": [
            # Hierarchies first: a rate, a norm and a template all point into them.
            item(
                "konstryx.master.CBSNode",
                "konstryx.master-CBSNode.csv",
                ["code", "scope", "owningCompany_ID"],
                selfref="parent_ID",
            ),
            # Before ResourceNode: a resource names the S/4 material it buys as,
            # so the mirror rows have to exist for that reference to resolve.
            item("konstryx.master.Material", "konstryx.master-Material.csv", ["materialCode"]),
            item(
                "konstryx.master.ResourceNode",
                "konstryx.master-ResourceNode.csv",
                ["code", "scope", "owningCompany_ID"],
                selfref="parent_ID",
            ),
            item(
                "konstryx.master.RateMaster",
                "konstryx.master-RateMaster.csv",
                ["resource_ID", "effectiveFrom", "company_ID", "scope", "owningCompany_ID"],
            ),
            # Norms have no code of their own. What identifies one is the recipe
            # key it is filed under — resource, CBS leaf and basis — plus its
            # effective date and scope.
            item(
                "konstryx.master.ProductivityRate",
                "konstryx.master-ProductivityRate.csv",
                ["resource_ID", "linkedCBS_ID", "basis", "effectiveFrom",
                 "scope", "owningCompany_ID"],
            ),
            item(
                "konstryx.master.ConsumptionRate",
                "konstryx.master-ConsumptionRate.csv",
                ["material_ID", "linkedCBS_ID", "basis", "effectiveFrom",
                 "scope", "owningCompany_ID"],
            ),
            item("konstryx.master.Vendor", "konstryx.master-Vendor.csv", ["bpNumber"]),
            item(
                "konstryx.master.ProjectTemplate",
                "konstryx.master-ProjectTemplate.csv",
                ["code", "scope", "owningCompany_ID"],
            ),
            item(
                "konstryx.master.ProjectTemplateResource",
                "konstryx.master-ProjectTemplateResource.csv",
                ["template_ID", "resource_ID"],
            ),
        ],
    },
    {
        "packId": "DEMO_PROJECT",
        "version": "1.0.0",
        "sequence": 50,
        "description": (
            "Two projects and the canonical EQR thread end to end: RR-2026-0188, "
            "its five advisory decisions, AVC-2026-0188 and reservation "
            "RES-2026-0188 encumbering AED 685,080 over three WBS elements. "
            "Demo content; a client deployment omits this pack."
        ),
        "file": "demo-project.json",
        "items": [
            item("konstryx.prj.Project", "konstryx.prj-Project.csv", ["code"]),
            item(
                "konstryx.prj.WBSElement",
                "konstryx.prj-WBSElement.csv",
                ["project_ID", "code"],
                selfref="parent_ID",
            ),
            item(
                "konstryx.prj.CBSInstance",
                "konstryx.prj-CBSInstance.csv",
                ["project_ID", "code"],
                selfref="parent_ID",
            ),
            item("konstryx.prj.BOQ", "konstryx.prj-BOQ.csv", ["boqId"]),
            item("konstryx.prj.BOQItem", "konstryx.prj-BOQItem.csv", ["boq_ID", "itemNo"]),
            item(
                "konstryx.prj.BOQItemResource",
                "konstryx.prj-BOQItemResource.csv",
                ["boqItem_ID", "resource_ID"],
            ),
            # The request spine. Lines are inserted carrying the ids of their
            # advisory decision and availability result, which do not exist yet
            # — the reference is circular, and honouring the fixture's own ids
            # is what lets both sides be stated at once.
            item("konstryx.wf.ResourceRequest", "konstryx.wf-ResourceRequest.csv", ["docNo"]),
            item(
                "konstryx.wf.ResourceRequestLine",
                "konstryx.wf-ResourceRequestLine.csv",
                ["parent_ID", "lineNo"],
            ),
            item(
                "konstryx.wf.AdvisoryDecision",
                "konstryx.wf-AdvisoryDecision.csv",
                ["rr_ID", "line_ID"],
            ),
            item("konstryx.wf.AvailabilityCheck", "konstryx.wf-AvailabilityCheck.csv", ["docNo"]),
            item(
                "konstryx.wf.AvailabilityCheckLine",
                "konstryx.wf-AvailabilityCheckLine.csv",
                ["parent_ID", "rrLine_ID"],
            ),
            item("konstryx.wf.Reservation", "konstryx.wf-Reservation.csv", ["docNo"]),
            item(
                "konstryx.wf.ReservationLine",
                "konstryx.wf-ReservationLine.csv",
                ["reservation_ID", "rrLine_ID"],
            ),
            item(
                "konstryx.eq.EquipmentRequestLine",
                "konstryx.eq-EquipmentRequestLine.csv",
                ["line_ID"],
            ),
            # The manpower vertical extension, and its daily log. Both come after
            # the request lines they hang off, and the timesheet after the
            # manpower line it belongs to.
            item(
                "konstryx.mpr.ManpowerRequestLine",
                "konstryx.mpr-ManpowerRequestLine.csv",
                ["line_ID"],
            ),
            item(
                "konstryx.mpr.TimesheetEntry",
                "konstryx.mpr-TimesheetEntry.csv",
                ["manpowerLine_ID", "workDate"],
            ),
        ],
    },
    {
        "packId": "DEMO_USERS",
        "version": "1.0.0",
        "sequence": 60,
        "description": (
            "Who holds which persona, and over what. Last, because every row "
            "names a persona, a company and a project delivered above. Demo "
            "logins; a real deployment assigns its own users through "
            "AuthorizationService.UserAssignments."
        ),
        "file": "demo-users.json",
        "items": [
            item(
                "konstryx.auth.UserAssignment",
                "konstryx.auth-UserAssignment.csv",
                ["user", "persona_ID", "company_ID", "project_ID"],
            ),
        ],
    },
]


def coerce(entity: str, column: str, raw: str):
    """CSV text to the JSON type the pack loader will turn into a Java value.

    An empty cell becomes null rather than an empty string, matching how CAP
    reads the same file — and it matters beyond cosmetics, because the pack's
    idempotency check tests a null key column with IS NULL. A group-scoped rate
    whose owning company arrived as "" would never match itself and would be
    re-inserted on every upgrade.
    """
    if raw is None or raw == "":
        return None
    kind = TYPES.get(entity, {}).get(column)
    if kind == BOOLEAN:
        return raw.strip().lower() == "true"
    if kind == INTEGER:
        return int(raw)
    if kind == DECIMAL:
        return float(raw)
    if UUID_RE.match(raw):
        return raw.lower()
    return raw


def topo(rows: list[dict], selfref: str) -> list[dict]:
    """Orders a self-referencing entity so a parent is inserted before its child.

    The fixtures happen to be mostly in order already, but "happens to be" is
    not a property worth depending on: the CBS library declares its L1 phase 03
    after several L2 nodes, and one reordered fixture line would otherwise turn
    into a foreign-key failure on a tenant and nowhere else.
    """
    by_id = {r["ID"]: r for r in rows if r.get("ID")}
    ordered: list[dict] = []
    placed: set[str] = set()

    def place(row: dict, seen: frozenset) -> None:
        rid = row.get("ID")
        if rid in placed:
            return
        parent_id = row.get(selfref)
        # A parent outside this fixture (or a cycle) is not ours to resolve;
        # emit the row and let the pack fail loudly if the target is missing.
        if parent_id and parent_id in by_id and parent_id not in seen:
            place(by_id[parent_id], seen | {rid})
        placed.add(rid)
        ordered.append(row)

    for row in rows:
        place(row, frozenset({row.get("ID")}))
    return ordered


def read_rows(spec: dict) -> list[dict]:
    path = CSV_DIR / spec["csv"]
    if not path.exists():
        raise SystemExit(f"fixture missing: {path}")
    entity = spec["entity"]
    with path.open(newline="", encoding="utf-8-sig") as fh:
        raw_rows = list(csv.DictReader(fh, delimiter=";"))

    # A value containing an unquoted ';' silently shifts every later column left,
    # and the damage does not look like a parse error — it looks like data. The
    # DEMO_ALL persona shipped that way: a semicolon in its description pushed
    # " scope still applies" into the boolean isActive and left isDelivered
    # reading true when the fixture plainly says false. DictReader signals it by
    # collecting the surplus under a None key, which is worth failing on rather
    # than dropping, because a pack built from a misread row is wrong content
    # delivered confidently.
    for number, raw in enumerate(raw_rows, start=2):
        if None in raw:
            raise SystemExit(
                f"{path.name} line {number}: more values than columns "
                f"{raw[None]!r} — a ';' inside a value needs the value quoted"
            )
        if any(v is None for v in raw.values()):
            missing = sorted(k for k, v in raw.items() if v is None)
            raise SystemExit(
                f"{path.name} line {number}: fewer values than columns, "
                f"missing {missing}"
            )

    rows = []
    for raw in raw_rows:
        row = {}
        for column, value in raw.items():
            if column is None:
                continue
            coerced = coerce(entity, column, value)
            # Omit empty cells entirely rather than sending explicit nulls for
            # every unset column. The keys still carry null where the natural
            # key needs it, because those columns are re-added below.
            if coerced is not None:
                row[column] = coerced
        for key in spec["keys"]:
            row.setdefault(key, None)
        rows.append(row)

    if spec.get("selfref"):
        rows = topo(rows, spec["selfref"])
    return rows


def build(pack: dict) -> dict:
    if len(pack["description"]) > MAX_DESCRIPTION:
        raise SystemExit(
            f"{pack['packId']}: description is {len(pack['description'])} chars, "
            f"max {MAX_DESCRIPTION} — it would roll the whole pack back on apply"
        )
    items = []
    for spec in pack["items"]:
        rows = read_rows(spec)
        entry: dict = {"entity": spec["entity"]}
        keys = spec["keys"]
        if len(keys) == 1:
            entry["naturalKey"] = keys[0]
        else:
            entry["naturalKeys"] = keys
        entry["rows"] = rows
        items.append(entry)
    return {
        "packId": pack["packId"],
        "version": pack["version"],
        "sequence": pack["sequence"],
        "description": pack["description"],
        "//": (
            "GENERATED by tools/build_content_packs.py from test/data — do not "
            "edit by hand. Change the fixture and regenerate, or the delivered "
            "content and the dataset every local test asserts against diverge."
        ),
        "items": items,
    }


def main() -> int:
    check_only = "--check" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stale = []

    for pack in PACKS:
        target = OUT_DIR / pack["file"]
        text = json.dumps(build(pack), indent=2, ensure_ascii=False) + "\n"
        rows = sum(len(i["rows"]) for i in build(pack)["items"])
        if check_only:
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != text:
                stale.append(pack["file"])
            continue
        target.write_text(text, encoding="utf-8")
        print(f"  {pack['file']:<22} seq {pack['sequence']:>4}  {rows:>4} rows")

    if check_only:
        if stale:
            print("stale content packs (run tools/build_content_packs.py): "
                  + ", ".join(stale))
            return 1
        print("content packs are up to date with test/data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
