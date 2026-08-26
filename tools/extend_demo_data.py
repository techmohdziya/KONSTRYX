"""Extends the demo dataset, in both places it lives.

This writes the CSV fixtures only. tools/build_content_packs.py compiles those
same fixtures into the delivered content packs, and owns that translation -
natural keys, self-references and all. Writing the pack here as well produced a
second and weaker mechanism, which the content suite caught by noticing the
generated packs had gone stale.

What it adds, and why each was missing:

  CBS hierarchy   Every project CBS instance was a root. A "cost breakdown
                  structure" with nothing broken down cannot show a roll-up,
                  and the library it was instantiated from has had a proper
                  three-level tree all along.
  Budget          There was no budget document at all, so the CBS carried
                  figures that nothing underneath supported - exactly the
                  state rollUpBudget exists to expose.
  Site locations  Productivity cannot be computed without them.
  Exchange rates  The currency work has nothing to demonstrate without rates.
  Daily logs      Signed days across several floors, so productivity has a
                  spread to show rather than a single number.
  Allocations     Bill lines split across floors, which is what turns measured
                  work into a per-location quantity.

Codes and amounts follow the canonical set already in the seed: the CBS codes
come from the library, the floors from the wireframe's own L03-L06, and the
budget lines sum to the CBS figures that were already there.
"""
import csv
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = os.path.join(ROOT, "test", "data")
PACK = os.path.join(ROOT, "srv", "src", "main", "resources", "content",
                    "demo-project.json")

PROJECT = "30000000-0000-0000-0000-000000000001"

# ---------------------------------------------------------------- CBS tree

# The library's own L1 phases, instantiated for the project so its L2 nodes
# have something to roll up into.
CBS_ROOTS = [
    ("32000000-0000-0000-0000-000000000000", "00",
     "41000000-0000-0000-0000-000000000001"),
    ("32000000-0000-0000-0000-000000000100", "01",
     "41000000-0000-0000-0000-000000000002"),
    ("32000000-0000-0000-0000-000000000200", "02",
     "41000000-0000-0000-0000-000000000003"),
    ("32000000-0000-0000-0000-000000000300", "03",
     "41000000-0000-0000-0000-000000000030"),
]

# An L2 belongs to the L1 its code starts with.
CBS_PARENT_OF = {
    "00": "32000000-0000-0000-0000-000000000000",
    "01": "32000000-0000-0000-0000-000000000100",
    "02": "32000000-0000-0000-0000-000000000200",
    "03": "32000000-0000-0000-0000-000000000300",
}

# Which nodes are pools rather than absorbers. Site establishment and
# preliminaries are spread across the work that consumes them; everything
# else takes a share.
CBS_NATURE = {"00": "INDIRECT", "00.10": "INDIRECT"}
CBS_BASIS = {"00": "DIRECT_COST", "00.10": "DIRECT_COST"}

# ------------------------------------------------------------- site tower

LOCATIONS = [
    # ID, code, name, level, type, parent, gfa
    ("36000000-0000-0000-0000-000000000001", "T1", "Tower 1", "L1", "BUILDING", None, None),
    ("36000000-0000-0000-0000-000000000003", "T1-L03", "Level 3", "L2", "FLOOR",
     "36000000-0000-0000-0000-000000000001", 1200.000),
    ("36000000-0000-0000-0000-000000000004", "T1-L04", "Level 4", "L2", "FLOOR",
     "36000000-0000-0000-0000-000000000001", 1200.000),
    ("36000000-0000-0000-0000-000000000005", "T1-L05", "Level 5", "L2", "FLOOR",
     "36000000-0000-0000-0000-000000000001", 1150.000),
    ("36000000-0000-0000-0000-000000000006", "T1-L06", "Level 6", "L2", "FLOOR",
     "36000000-0000-0000-0000-000000000001", 1150.000),
    ("36000000-0000-0000-0000-000000000031", "T1-L03-ZA", "Level 3 Zone A", "L3", "ZONE",
     "36000000-0000-0000-0000-000000000003", 600.000),
    ("36000000-0000-0000-0000-000000000032", "T1-L03-ZB", "Level 3 Zone B", "L3", "ZONE",
     "36000000-0000-0000-0000-000000000003", 600.000),
]

# --------------------------------------------------------------- currency

# AED is pegged to USD at 3.6725. The euro and rupee rates are the ones a Gulf
# contractor actually meets - a European formwork supplier and an Indian
# labour subcontractor.
RATES = [
    ("37000000-0000-0000-0000-000000000001", "USD", "AED", "SPOT",    "2026-01-01", 3.672500, "Central bank peg"),
    ("37000000-0000-0000-0000-000000000002", "USD", "AED", "BUDGET",  "2026-01-01", 3.672500, "Baseline FY26"),
    ("37000000-0000-0000-0000-000000000003", "EUR", "AED", "SPOT",    "2026-01-01", 3.950000, "S/4 TCURR"),
    ("37000000-0000-0000-0000-000000000004", "EUR", "AED", "BUDGET",  "2026-01-01", 4.020000, "Baseline FY26"),
    ("37000000-0000-0000-0000-000000000005", "EUR", "AED", "CONTRACT", "2026-01-01", 3.980000, "Contract MH-2026"),
    ("37000000-0000-0000-0000-000000000006", "INR", "AED", "SPOT",    "2026-01-01", 0.044100, "S/4 TCURR"),
    ("37000000-0000-0000-0000-000000000007", "INR", "AED", "BUDGET",  "2026-01-01", 0.043500, "Baseline FY26"),
    ("37000000-0000-0000-0000-000000000008", "GBP", "AED", "SPOT",    "2026-01-01", 4.640000, "S/4 TCURR"),
]

# ----------------------------------------------------------------- budget

BUDGET_ID = "38000000-0000-0000-0000-000000000001"

# Lines that add up to the CBS figures already in the seed, so the roll-up
# reproduces them instead of contradicting them.
BUDGET_LINES = [
    # ID, cbs instance, category, amount
    ("38100000-0000-0000-0000-000000000001", "32000000-0000-0000-0000-000000000010", "MPR",  450000.00),
    ("38100000-0000-0000-0000-000000000002", "32000000-0000-0000-0000-000000000010", "MR",   500000.00),
    ("38100000-0000-0000-0000-000000000003", "32000000-0000-0000-0000-000000000010", "SC",   300000.00),
    ("38100000-0000-0000-0000-000000000004", "32000000-0000-0000-0000-000000000120", "MPR",  380000.00),
    ("38100000-0000-0000-0000-000000000005", "32000000-0000-0000-0000-000000000120", "MR",   600000.00),
    ("38100000-0000-0000-0000-000000000006", "32000000-0000-0000-0000-000000000210", "MPR", 1200000.00),
    ("38100000-0000-0000-0000-000000000007", "32000000-0000-0000-0000-000000000210", "MR",  1600000.00),
    ("38100000-0000-0000-0000-000000000008", "32000000-0000-0000-0000-000000000210", "SC",   600000.00),
    ("38100000-0000-0000-0000-000000000009", "32000000-0000-0000-0000-000000000230", "MR",   820000.00),
    ("38100000-0000-0000-0000-000000000010", "32000000-0000-0000-0000-000000000240", "MPR",  640000.00),
    ("38100000-0000-0000-0000-000000000011", "32000000-0000-0000-0000-000000000250", "SC",   910000.00),
    ("38100000-0000-0000-0000-000000000012", "32000000-0000-0000-0000-000000000260", "MPR",  475000.00),
    ("38100000-0000-0000-0000-000000000013", "32000000-0000-0000-0000-000000000310", "MR",   730000.00),
    ("38100000-0000-0000-0000-000000000014", "32000000-0000-0000-0000-000000000320", "MR",   960000.00),
    ("38100000-0000-0000-0000-000000000015", "32000000-0000-0000-0000-000000000330", "MR",   540000.00),
]


# ------------------------------------------------------------- execution

# The slab is poured floor by floor, which is what makes productivity worth
# reporting per location rather than per project. Measured quantities are
# cumulative to date against a 5,294 m3 contract quantity.
SLAB_ITEM = "34000000-0000-0000-0000-000000000005"
SLAB_DONE = 1180.000

# Each floor's share of the measured slab. They sum to 100.
SLAB_SPLIT = [
    ("39000000-0000-0000-0000-000000000001", "36000000-0000-0000-0000-000000000003", 40.00, "Level 3 poured out"),
    ("39000000-0000-0000-0000-000000000002", "36000000-0000-0000-0000-000000000004", 36.00, "Level 4 poured out"),
    ("39000000-0000-0000-0000-000000000005", "36000000-0000-0000-0000-000000000005", 24.00, "Level 5 in progress"),
]

# Crew, rate per head-day, and the floors each worked. Hours are per head.
CREWS = {
    "58000000-0000-0000-0000-000000000161": ("Steel Fixer G1", 8, 520.00),
    "58000000-0000-0000-0000-000000000163": ("Carpenter Formwork", 6, 280.00),
    "58000000-0000-0000-0000-000000000165": ("Mason/Helper", 4, 180.00),
}

# Deliberately uneven. Level 5 takes more hours for less pour because it is
# still in progress, so productivity has something to show rather than three
# identical rows.
SHIFTS = [
    # crew, floor, date, heads, regular, overtime
    ("58000000-0000-0000-0000-000000000163", "36000000-0000-0000-0000-000000000003", "2026-07-06", 6, 8, 2),
    ("58000000-0000-0000-0000-000000000163", "36000000-0000-0000-0000-000000000003", "2026-07-07", 6, 8, 0),
    ("58000000-0000-0000-0000-000000000163", "36000000-0000-0000-0000-000000000003", "2026-07-08", 5, 8, 0),
    ("58000000-0000-0000-0000-000000000161", "36000000-0000-0000-0000-000000000003", "2026-07-06", 8, 8, 2),
    ("58000000-0000-0000-0000-000000000161", "36000000-0000-0000-0000-000000000003", "2026-07-07", 8, 8, 0),
    ("58000000-0000-0000-0000-000000000165", "36000000-0000-0000-0000-000000000003", "2026-07-08", 4, 8, 0),

    ("58000000-0000-0000-0000-000000000163", "36000000-0000-0000-0000-000000000004", "2026-07-20", 6, 8, 0),
    ("58000000-0000-0000-0000-000000000163", "36000000-0000-0000-0000-000000000004", "2026-07-21", 6, 8, 0),
    ("58000000-0000-0000-0000-000000000161", "36000000-0000-0000-0000-000000000004", "2026-07-20", 8, 8, 0),
    ("58000000-0000-0000-0000-000000000161", "36000000-0000-0000-0000-000000000004", "2026-07-21", 7, 8, 2),

    ("58000000-0000-0000-0000-000000000163", "36000000-0000-0000-0000-000000000005", "2026-08-03", 6, 8, 2),
    ("58000000-0000-0000-0000-000000000163", "36000000-0000-0000-0000-000000000005", "2026-08-04", 6, 8, 2),
    ("58000000-0000-0000-0000-000000000163", "36000000-0000-0000-0000-000000000005", "2026-08-05", 6, 8, 0),
    ("58000000-0000-0000-0000-000000000161", "36000000-0000-0000-0000-000000000005", "2026-08-03", 8, 8, 2),
    ("58000000-0000-0000-0000-000000000161", "36000000-0000-0000-0000-000000000005", "2026-08-04", 8, 8, 2),
    ("58000000-0000-0000-0000-000000000165", "36000000-0000-0000-0000-000000000005", "2026-08-05", 4, 8, 0),
    # One day still unsigned, so a demo can show that a draft is not counted.
    ("58000000-0000-0000-0000-000000000165", "36000000-0000-0000-0000-000000000005", "2026-08-06", 4, 8, 0),
]

SIGNER = "Daud Patel - Site Engineer"
STANDARD_DAY = 8.0


def build_execution():
    """Daily logs on the floors, and the bill line split across them."""
    logs = []
    for index, (crew, floor, day, heads, regular, overtime) in enumerate(SHIFTS, start=200):
        _, _, rate = CREWS[crew]
        head_days = (regular + overtime) / STANDARD_DAY * heads
        cost = round(head_days * rate, 2)
        # The last row is left as a draft on purpose.
        draft = index == 199 + len(SHIFTS)
        logs.append([
            f"59000000-0000-0000-0000-0000000{index:05d}", crew, day,
            str(heads), f"{regular:.2f}", f"{overtime:.2f}",
            "31000000-0000-0000-0000-000000000102",
            "32000000-0000-0000-0000-000000000320", floor,
            "PRJ-001.03.20.STR-SLB",
            "" if draft else f"{cost:.2f}",
            "Draft" if draft else "Signed",
            "" if draft else SIGNER,
        ])

    allocations = [
        [aid, SLAB_ITEM, "31000000-0000-0000-0000-000000000102",
         "32000000-0000-0000-0000-000000000320", location,
         f"{SLAB_DONE * pct / 100:.3f}", f"{pct:.2f}", f"{pct:.2f}",
         "TPL-FLOORS", basis]
        for aid, location, pct, basis in SLAB_SPLIT
    ]
    return logs, allocations


def csv_path(entity):
    return os.path.join(CSV_DIR, f"{entity}.csv")


def read_csv(entity):
    path = csv_path(entity)
    if not os.path.exists(path):
        return [], []
    with io.open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=";"))
    return rows[0], rows[1:]


def write_csv(entity, header, rows):
    with io.open(csv_path(entity), "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=";", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def ensure_columns(header, rows, columns):
    """Adds columns the seed predates, filling existing rows with blanks."""
    for column in columns:
        if column not in header:
            header.append(column)
            for row in rows:
                row.append("")
    return header, rows


def fix_cbs_csv():
    entity = "konstryx.prj-CBSInstance"
    header, rows = read_csv(entity)
    header, rows = ensure_columns(header, rows, ["ownAmount", "costNature", "allocBasis"])
    index = {name: i for i, name in enumerate(header)}

    existing = {row[index["code"]] for row in rows}
    for node_id, code, library in CBS_ROOTS:
        if code in existing:
            continue
        row = [""] * len(header)
        row[index["ID"]] = node_id
        row[index["code"]] = code
        row[index["project_ID"]] = PROJECT
        row[index["libraryNode_ID"]] = library
        row[index["budgetAmount"]] = "0.00"
        row[index["ownAmount"]] = "0.00"
        row[index["level"]] = "L1"
        row[index["costNature"]] = CBS_NATURE.get(code, "DIRECT")
        row[index["allocBasis"]] = CBS_BASIS.get(code, "")
        rows.append(row)

    for row in rows:
        code = row[index["code"]]
        if row[index["level"]] == "L1":
            continue
        row[index["parent_ID"]] = CBS_PARENT_OF.get(code.split(".")[0], "")
        row[index["costNature"]] = CBS_NATURE.get(code, "DIRECT")
        row[index["allocBasis"]] = CBS_BASIS.get(code, "")

    # Seed the roll-up already correct rather than shipping the state it
    # exists to repair. A parent reading 0.00 while its child holds 1,250,000
    # is exactly the defect rollUpBudget was built for - but a customer
    # meeting it on the first screen reads it as a broken total, not as a
    # demonstration. The button still re-derives; it just starts from truth.
    own = {}
    for line_id, cbs_id, category, amount in BUDGET_LINES:
        own[cbs_id] = own.get(cbs_id, 0.0) + amount

    by_id = {row[index["ID"]]: row for row in rows}
    total = dict(own)
    for node_id, row in by_id.items():
        amount = own.get(node_id, 0.0)
        if not amount:
            continue
        parent = row[index["parent_ID"]]
        guard = 0
        while parent and parent in by_id and guard <= len(by_id):
            total[parent] = total.get(parent, 0.0) + amount
            parent = by_id[parent][index["parent_ID"]]
            guard += 1

    for node_id, row in by_id.items():
        row[index["ownAmount"]] = f"{own.get(node_id, 0.0):.2f}"
        row[index["budgetAmount"]] = f"{total.get(node_id, 0.0):.2f}"

    rows.sort(key=lambda r: r[index["code"]])
    write_csv(entity, header, rows)
    return len(rows)


def write_simple_csv(entity, header, rows):
    write_csv(entity, header, rows)
    return len(rows)


def build_rows():
    """The new tables, as (entity, header, rows) ready for both targets."""
    locations = [
        [lid, code, name, PROJECT, parent or "", level, kind,
         "" if gfa is None else f"{gfa:.3f}", "" if gfa is None else "M2"]
        for lid, code, name, level, kind, parent, gfa in LOCATIONS
    ]
    rates = [
        [rid, frm, to, kind, valid, f"{rate:.6f}", source]
        for rid, frm, to, kind, valid, rate, source in RATES
    ]
    budget = [[
        BUDGET_ID, "BUD-2026-0001", PROJECT,
        "20000000-0000-0000-0000-000000000001", "Baselined",
        "arjun.mehta@inflexion.ae", "2026-01-15", "V1", "30",
        f"{sum(a for _, _, _, a in BUDGET_LINES):.2f}",
    ]]
    lines = [
        [lid, BUDGET_ID, cbs, category, f"{amount:.2f}", f"{amount:.2f}",
         "0.00", "0.00", "0.00", f"{amount:.2f}", "100.00", "0.00"]
        for lid, cbs, category, amount in BUDGET_LINES
    ]
    logs, allocations = build_execution()
    return {
        "konstryx.prj-SiteLocation": (
            ["ID", "code", "name", "project_ID", "parent_ID", "level",
             "locationType", "gfa", "uom"], locations),
        "konstryx.fin-ExchangeRate": (
            ["ID", "fromCcy_code", "toCcy_code", "rateType", "validFrom",
             "rate", "source"], rates),
        "konstryx.bud-Budget": (
            ["ID", "docNo", "project_ID", "company_ID", "status", "raisedBy",
             "raisedOn", "version", "daysToLock", "totalAmount"], budget),
        "konstryx.bud-BudgetLine": (
            ["ID", "budget_ID", "cbs_ID", "category", "amount", "authorised",
             "committed", "encumbered", "actual", "available", "availPct",
             "usedPct"], lines),
        "konstryx.prj-Allocation": (
            ["ID", "boqItem_ID", "wbs_ID", "cbs_ID", "location_ID", "allocQty",
             "allocPct", "pctOfItem", "template", "splitBasis"], allocations),
    }, logs


def measure_slab():
    """Records what has actually been poured, so productivity has a numerator."""
    entity = "konstryx.prj-BOQItem"
    header, rows = read_csv(entity)
    header, rows = ensure_columns(header, rows, ["cumDoneQty", "cumDonePct"])
    index = {name: i for i, name in enumerate(header)}
    for row in rows:
        if row[index["ID"]] != SLAB_ITEM:
            continue
        contract = float(row[index["qty"]] or 0)
        row[index["cumDoneQty"]] = f"{SLAB_DONE:.3f}"
        row[index["cumDonePct"]] = (
            f"{SLAB_DONE / contract * 100:.2f}" if contract else "0.00")
    write_csv(entity, header, rows)


def append_logs(logs):
    """Adds the floor logs beside the five canonical EQR-thread rows."""
    entity = "konstryx.mpr-TimesheetEntry"
    header, rows = read_csv(entity)
    header, rows = ensure_columns(header, rows, ["location_ID"])
    index = {name: i for i, name in enumerate(header)}
    order = ["ID", "manpowerLine_ID", "workDate", "headsPresent", "regularHrs",
             "otHrs", "wbs_ID", "cbs_ID", "location_ID", "activity",
             "costAmount", "logStatus", "signedBy"]
    existing = {row[index["ID"]] for row in rows}
    for log in logs:
        if log[0] in existing:
            continue
        row = [""] * len(header)
        for name, value in zip(order, log):
            row[index[name]] = value
        rows.append(row)
    write_csv(entity, header, rows)
    return len(rows)


def main():
    count = fix_cbs_csv()
    print(f"  CBS instances now {count} rows, three levels")

    tables, logs = build_rows()
    for name, (header, rows) in tables.items():
        written = write_simple_csv(name, header, rows)
        print(f"  {name:34} {written:3} rows")

    measure_slab()
    total = append_logs(logs)
    print(f"  {'konstryx.mpr-TimesheetEntry':34} {total:3} rows "
          f"({len(logs)} on the Tower 1 floors)")

    print()
    print("  Now run tools/build_content_packs.py to regenerate the packs from")
    print("  these fixtures - it owns that translation, natural keys and all.")


main()
