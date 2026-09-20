"""Widens the demo from one project into a portfolio, and gives it a shape.

Three things were wrong with the dataset for anyone looking at the product
rather than testing it.

  One project carried everything.  PRJ-002 existed as a header with no bill, no
  budget and no work, and every other list had a single row in it. A list report
  with one row demonstrates nothing: no sorting, no filtering, no comparison,
  and no sense of what the screen looks like on a real job.

  The WBS was flat.  Four elements, no parents, so a "work breakdown structure"
  broke nothing down. The tree annotations in app/hierarchies.cds have nothing
  to show unless the data actually nests.

  There was no programme at all.  Zero activities and zero dependencies, which
  means the critical path had nothing to run over and the float column could
  only ever have been empty.

What this does NOT write is anything derived. Productivity snapshots, period
reports and purchase requisitions are outputs of measureProductivity, reconcile
and raisePurchaseRequisition — they are produced by running those actions
against the facts below (tools/prime_demo.py), never typed in. A measurement
nobody measured is the one kind of demo data that misleads rather than
illustrates.

Rates, codes and structures follow what the seed already establishes: the CBS
library nodes are the ones PRJ-001 instantiates, the bill codes keep the
3-Cx-x-xx-x pattern, and the AED rates sit in the same band as the existing
priced lines.
"""
import csv
import datetime as _dt
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "test", "data")

# The ID blocks the seed already uses, continued rather than reinvented so a
# row's prefix still says what it is at a glance.
PRJ = "30000000-0000-0000-0000-0000000000%02d"
WBS = "31000000-0000-0000-0000-%012d"
CBS = "32000000-0000-0000-0000-%012d"
BOQ = "33000000-0000-0000-0000-%012d"
ITEM = "34000000-0000-0000-0000-%012d"
LOC = "36000000-0000-0000-0000-%012d"
BUD = "38000000-0000-0000-0000-%012d"
BUDL = "38100000-0000-0000-0000-%012d"
# The second and further parts of a heading that divides across the works.
# Recognisable on sight so a re-run can drop them and derive them again.
SPLIT_PREFIX = "38190000-0000-0000-0000-"
ALLOC = "39000000-0000-0000-0000-%012d"
ACT = "3a000000-0000-0000-0000-%012d"
REL = "3b000000-0000-0000-0000-%012d"
RR = "50000000-0000-0000-0000-%012d"
RRL = "51000000-0000-0000-0000-%012d"
ADV = "52000000-0000-0000-0000-%012d"
RES = "55000000-0000-0000-0000-%012d"
RESL = "56000000-0000-0000-0000-%012d"
SCR = "70000000-0000-0000-0000-%012d"
PA = "71000000-0000-0000-0000-%012d"
PC = "72000000-0000-0000-0000-%012d"

INFC = "20000000-0000-0000-0000-000000000001"
PMI = "20000000-0000-0000-0000-000000000002"
IFO = "20000000-0000-0000-0000-000000000003"

# Library nodes PRJ-001 already instantiates; a new project's CBS points at the
# same library rather than inventing one.
# Kept in step with tools/restructure_cbs.py, which owns the structure. Three
# of these codes moved when the library was rebuilt - 02.30 is now Slabs rather
# than the raft, 03.10 is blockwork rather than columns - so a stale map here
# would seed a project's breakdown against the wrong nodes and nothing would
# look wrong until the costs landed.
LIB = {
    "00": "41000000-0000-0000-0000-000000000001",
    "00.10": "41000000-0000-0000-0000-000000000010",
    "01": "41000000-0000-0000-0000-000000000002",
    "01.20": "41000000-0000-0000-0000-000000000011",
    "01.30": "41000000-0000-0000-0000-000000000040",
    "02": "41000000-0000-0000-0000-000000000003",
    "02.10": "41000000-0000-0000-0000-000000000012",
    "02.20": "41000000-0000-0000-0000-000000000031",
    "02.30": "41000000-0000-0000-0000-000000000032",
    "03": "41000000-0000-0000-0000-000000000030",
    "03.10": "41000000-0000-0000-0000-000000000044",
    "04": "41000000-0000-0000-0000-000000000050",
    "04.10": "41000000-0000-0000-0000-000000000043",
}


# --------------------------------------------------------------------- files

def path(entity):
    return os.path.join(DATA, "konstryx.%s.csv" % entity)


# A fixture file only exists once something has been seeded into it, and two of
# these entities have never had a row. The header is the contract with the CSV
# loader — a column the model does not have makes CAP refuse the whole file at
# startup — so it is stated here rather than guessed at write time.
HEADERS = {
    "vo-VariationOrder": ["ID", "docNo", "project_ID", "company_ID", "boq_ID",
                          "clientRef", "title", "origin", "instructionRef",
                          "instructedOn", "submittedOn", "decidedOn",
                          "decidedBy", "decisionNote", "status",
                          "timeExtensionDays", "ccy_code", "revenueAmount",
                          "costAmount", "marginAmount", "marginPct",
                          "raisedBy", "raisedOn"],
    "vo-VariationLine": ["ID", "variation_ID", "lineNo", "boqItem_ID",
                         "changeType", "description", "qty", "uom",
                         "revenueRate", "costRate", "revenueAmount",
                         "costAmount", "wbs_ID", "cbs_ID"],
    "prj-Activity": ["ID", "code", "name", "project_ID", "wbs_ID",
                     "durationDays", "plannedStart", "plannedFinish",
                     "earlyStart", "earlyFinish", "lateStart", "lateFinish",
                     "totalFloat", "freeFloat", "isCritical", "actualStart",
                     "actualFinish", "percentDone", "status"],
    "prj-ActivityRelation": ["ID", "predecessor_ID", "successor_ID",
                             "linkType", "lagDays"],
}

# Columns added to the model after a fixture was written. Appending them keeps
# the existing rows and lets the new ones carry the value.
ADDED_COLUMNS = {
    "prj-Allocation": ["project_ID"],
    # A budget line is controlled at three keys at once, not one: what work it
    # pays for, who builds it, what absorbs it.
    "bud-BudgetLine": ["wbs_ID", "boqItem_ID"],
}


def read(entity):
    target = path(entity)
    if not os.path.exists(target) and entity in HEADERS:
        with io.open(target, "w", encoding="utf-8", newline="") as handle:
            handle.write(";".join(HEADERS[entity]) + "\n")
    with io.open(target, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        fields = list(reader.fieldnames)
        rows = [dict(row) for row in reader]
    for column in ADDED_COLUMNS.get(entity, []):
        if column not in fields:
            fields.append(column)
            for row in rows:
                row.setdefault(column, "")
    return fields, rows


def write(entity, fields, rows):
    with io.open(path(entity), "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";",
                                extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({f: row.get(f, "") for f in fields})


def upsert(entity, new_rows, key="ID"):
    """Replaces rows with the same key, appends the rest.

    Re-running has to be safe: this tool is how the demo dataset is rebuilt, and
    a second run that doubled every project would be discovered by someone
    demonstrating it rather than by anyone running it.
    """
    fields, rows = read(entity)
    by_key = {row[key]: index for index, row in enumerate(rows)}
    added = 0
    for row in new_rows:
        missing = [f for f in row if f not in fields]
        if missing:
            raise SystemExit("%s has no column(s) %s" % (entity, missing))
        if row[key] in by_key:
            rows[by_key[row[key]]].update(row)
        else:
            rows.append(row)
            added += 1
    write(entity, fields, rows)
    return added, len(rows)


def patch(entity, key_value, changes, key="ID"):
    fields, rows = read(entity)
    for row in rows:
        if row[key] == key_value:
            row.update(changes)
            write(entity, fields, rows)
            return True
    return False


# ------------------------------------------------------- PRJ-001: a real WBS

PRJ1 = PRJ % 1
PRJ2 = PRJ % 2

# The four elements the seed carries were all roots. They become the second
# level of a structure that reads the way their own codes always implied: 0.x
# preliminaries, 1.x substructure and first fix, 2.x superstructure.
WBS1_ROOTS = [
    dict(ID=WBS % 1000, code="WBS-0", project_ID=PRJ1, parent_ID="",
         activityType="EQ-SETUP", description="Preliminaries & Enabling Works"),
    dict(ID=WBS % 1001, code="WBS-1", project_ID=PRJ1, parent_ID="",
         activityType="EQ-CIVIL", description="Substructure & First Fix"),
    dict(ID=WBS % 1002, code="WBS-2", project_ID=PRJ1, parent_ID="",
         activityType="EQ-STRUCT", description="Superstructure"),
]

WBS1_ADDED = [
    dict(ID=WBS % 1010, code="WBS-0.20", project_ID=PRJ1, parent_ID=WBS % 1000,
         activityType="EQ-SETUP", description="Temporary Works & Hoarding"),
    dict(ID=WBS % 1020, code="WBS-1.05", project_ID=PRJ1, parent_ID=WBS % 1001,
         activityType="EQ-CIVIL", description="Piling & Shoring"),
    dict(ID=WBS % 1030, code="WBS-1.02.1", project_ID=PRJ1,
         parent_ID="31000000-0000-0000-0000-000000000102",
         activityType="EQ-CIVIL", description="Pile caps"),
    dict(ID=WBS % 1031, code="WBS-1.02.2", project_ID=PRJ1,
         parent_ID="31000000-0000-0000-0000-000000000102",
         activityType="EQ-CIVIL", description="Raft slab"),
    dict(ID=WBS % 1032, code="WBS-1.02.3", project_ID=PRJ1,
         parent_ID="31000000-0000-0000-0000-000000000102",
         activityType="EQ-CIVIL", description="Basement retaining walls"),
    dict(ID=WBS % 1040, code="WBS-2.06", project_ID=PRJ1, parent_ID=WBS % 1002,
         activityType="EQ-STRUCT", description="Cores & Shear Walls"),
    dict(ID=WBS % 1041, code="WBS-2.04.1", project_ID=PRJ1,
         parent_ID="31000000-0000-0000-0000-000000000204",
         activityType="EQ-STRUCT", description="Columns L01-L10"),
    dict(ID=WBS % 1042, code="WBS-2.04.2", project_ID=PRJ1,
         parent_ID="31000000-0000-0000-0000-000000000204",
         activityType="EQ-STRUCT", description="Slabs L03-L06"),
]

# Which existing element goes under which new root.
WBS1_REPARENT = {
    "31000000-0000-0000-0000-000000000010": WBS % 1000,   # WBS-0.10
    "31000000-0000-0000-0000-000000000102": WBS % 1001,   # WBS-1.02
    "31000000-0000-0000-0000-000000000103": WBS % 1001,   # WBS-1.03
    "31000000-0000-0000-0000-000000000204": WBS % 1002,   # WBS-2.04
}

# --------------------------------------------------------- PRJ-001 programme
#
# Durations and the network are the ones the bill implies: piling before pile
# caps, caps before the raft, the raft before the cores, and the slabs trailing
# the cores by a floor cycle rather than waiting for the whole core to top out
# (SS with a lag), which is how a tower is actually built.

ACTS1 = [
    ("A1000", "Site establishment & hoarding", WBS % 1000, 30,
     "2024-11-01", "2024-11-30", "Completed", 100),
    ("A1010", "Piling - 214 nr bored piles", WBS % 1020, 75,
     "2024-12-01", "2025-02-13", "Completed", 100),
    ("A1020", "Pile caps", WBS % 1030, 45,
     "2025-02-14", "2025-03-30", "Completed", 100),
    ("A1030", "Raft slab pour", WBS % 1031, 35,
     "2025-03-31", "2025-05-04", "Completed", 100),
    ("A1040", "Basement retaining walls", WBS % 1032, 60,
     "2025-05-05", "2025-07-03", "Completed", 100),
    ("A2000", "Cores & shear walls to L10", WBS % 1040, 140,
     "2025-07-04", "2025-11-20", "In progress", 82),
    ("A2010", "Columns L01-L10", WBS % 1041, 120,
     "2025-08-15", "2025-12-12", "In progress", 74),
    ("A2020", "Slabs L03-L06", WBS % 1042, 96,
     "2025-09-15", "2025-12-19", "In progress", 41),
    ("A3000", "MEP first fix L03-L06", "31000000-0000-0000-0000-000000000103", 80,
     "2025-11-01", "2026-01-19", "Planned", 0),
    ("A4000", "Facade & cladding to L10", WBS % 1002, 110,
     "2026-01-20", "2026-05-10", "Planned", 0),
]

# predecessor code, successor code, link type, lag
RELS1 = [
    ("A1000", "A1010", "FS", 0),
    ("A1010", "A1020", "FS", 0),
    ("A1020", "A1030", "FS", 0),
    ("A1030", "A1040", "FS", 0),
    ("A1040", "A2000", "FS", 0),
    ("A2000", "A2010", "SS", 42),
    ("A2010", "A2020", "SS", 30),
    ("A2020", "A3000", "SS", 47),
    ("A2020", "A4000", "FS", 32),
    ("A3000", "A4000", "SS", 80),
]

# ------------------------------------------------------------ new projects
#
# Three more jobs at different stages, so a list report shows a portfolio
# rather than a row: one being tendered, one just awarded, one in execution.

PROJECTS = [
    # PRJ-002 already existed as a header and nothing else — no bill, no
    # budget, no structure and no work. Its values are its own; what it gains
    # here is everything that was supposed to hang off it.
    dict(no=2, code="PRJ-002", name="Al Reem Business Bay",
         company=INFC, customer="Aldar Properties PJSC",
         value="31800000.00", start="2025-06-01", end="2027-12-31",
         stage="Execution"),
    dict(no=3, code="PRJ-003", name="Sharjah Logistics Park - Phase 2",
         company=INFC, customer="Sharjah Asset Management",
         value="18400000.00", start="2026-09-01", end="2028-02-29",
         stage="Tender"),
    dict(no=4, code="PRJ-004", name="Dubai South Warehouse 7",
         company=IFO, customer="Dubai South Properties",
         value="26750000.00", start="2025-03-01", end="2027-03-31",
         stage="Execution"),
    dict(no=5, code="PRJ-005", name="Yas Island Retail Podium",
         company=PMI, customer="Miral Asset Management",
         value="12900000.00", start="2026-07-01", end="2027-10-31",
         stage="Award"),
]

# The structure every new project gets: three roots, two or three children
# each. Offsets are per project so the IDs never collide.
WBS_TEMPLATE = [
    (0, "", "0", "EQ-SETUP", "Preliminaries & Enabling Works"),
    (1, 0, "0.10", "EQ-SETUP", "Site establishment"),
    (2, 0, "0.20", "EQ-SETUP", "Temporary works"),
    (3, "", "1", "EQ-CIVIL", "Substructure"),
    (4, 3, "1.10", "EQ-CIVIL", "Excavation & shoring"),
    (5, 3, "1.20", "EQ-CIVIL", "Foundations"),
    (6, 3, "1.30", "EQ-CIVIL", "Ground slab"),
    (7, "", "2", "EQ-STRUCT", "Superstructure & Envelope"),
    (8, 7, "2.10", "EQ-STRUCT", "Frame"),
    (9, 7, "2.20", "EQ-MEP", "Services first fix"),
]

# The spine a new project starts with. restructure_cbs.py instantiates the rest
# of the library afterwards, so this only has to cover the nodes the seeded
# budget and bills actually post against.
CBS_TEMPLATE = [
    (0, "", "00", "L1", "INDIRECT", "DIRECT_COST"),
    (1, 0, "00.10", "L2", "INDIRECT", "DIRECT_COST"),
    (2, "", "01", "L1", "DIRECT", ""),
    (3, 2, "01.30", "L2", "DIRECT", ""),
    (4, "", "02", "L1", "DIRECT", ""),
    (5, 4, "02.20", "L2", "DIRECT", ""),
    (6, 4, "02.30", "L2", "DIRECT", ""),
    (7, "", "03", "L1", "DIRECT", ""),
]

# Bill lines per project: item no, code, description, qty, uom, rate, cbs slot.
ITEM_TEMPLATE = [
    ("1.E.1.1.01", "3-C2-1-00-Q", "RCC Pile cap M40 incl. shutter, rebar, pour",
     "620.000", "m3", "2150.00", 3),
    ("1.E.1.2.01", "3-C2-1-00-F", "RCC Raft M40 incl. waterproofing",
     "1180.000", "m3", "2420.00", 3),
    ("1.E.2.2.01", "3-C7-3-00-D5", "Reinforcement bar 16-32 mm BS4449",
     "244.000", "t", "3420.00", 4),
    ("2.E.1.4.01", "3-C2-1-00-R", "RCC Columns M50 incl. shutter, rebar",
     "710.000", "m3", "2720.00", 6),
    ("2.E.1.3.01", "3-C2-1-00-H", "RCC Slab M40, 250 mm", "1640.000", "m3",
     "2180.00", 7),
    ("2.M.3.1.01", "3-M4-2-00-B", "Blockwork 200 mm incl. plaster",
     "8400.000", "m2", "132.00", 7),
]

# Which part of the structure builds each bill line. The budget does not read
# this: it reads the splits the allocation writes from it, so the two cannot
# drift apart.
ITEM_WBS = {3: 5, 4: 5, 6: 8, 7: 8}


# PRJ-001's own budget, as its headings stood before anything was split off
# them. Restated here because the split rewrites the rows it divides, and a
# heading whose full amount exists nowhere but in the row being rewritten can
# only be divided once — the second run would divide the first part again.
BUDGET1 = [
    (1, "010", "MPR", 450000.00),
    (2, "010", "MR", 500000.00),
    (3, "010", "SC", 300000.00),
    (4, "120", "MPR", 380000.00),
    (5, "120", "MR", 600000.00),
    (6, "210", "MPR", 1200000.00),
    (7, "210", "MR", 1600000.00),
    (8, "210", "SC", 600000.00),
    (9, "230", "MR", 820000.00),
    (10, "240", "MPR", 640000.00),
    (11, "250", "SC", 910000.00),
    (12, "260", "MPR", 475000.00),
    (13, "310", "MR", 730000.00),
    (14, "320", "MR", 960000.00),
    (15, "330", "MR", 540000.00),
]

BUD1 = BUD % 1


def budget1_lines():
    return [budget_line(BUDL % slot, BUD1, CBS % int(node), category, amount)
            for slot, node, category, amount in BUDGET1]


def budget_line(line_id, budget_id, cbs_id, category, amount):
    """One heading's share, before it is put on the works that spend it.

    The WBS element and the bill line are left to explode_budget_lines, which
    reads them off the splits. Deciding them twice — once here from a template
    and once there from the data — is how the two answers start to differ.
    """
    return dict(
        ID=line_id, budget_ID=budget_id, wbs_ID="", cbs_ID=cbs_id,
        boqItem_ID="", category=category,
        amount="%.2f" % amount, authorised="%.2f" % amount,
        committed="0.00", encumbered="0.00", actual="0.00",
        available="%.2f" % amount, availPct="100.00", usedPct="0.00")


BUDGET_TEMPLATE = [
    (1, "MPR", "0.14"),
    (3, "MR", "0.31"),
    (4, "MR", "0.11"),
    (6, "SCR", "0.22"),
    (7, "MPR", "0.16"),
]

ACT_TEMPLATE = [
    ("A100", "Site establishment", 0, 25),
    ("A110", "Excavation & shoring", 4, 55),
    ("A120", "Foundations", 5, 70),
    ("A130", "Ground slab", 6, 40),
    ("A200", "Frame to roof", 8, 130),
    ("A210", "Services first fix", 9, 85),
]

REL_TEMPLATE = [
    ("A100", "A110", "FS", 0),
    ("A110", "A120", "FS", 0),
    ("A120", "A130", "FS", 0),
    ("A130", "A200", "FS", 5),
    ("A200", "A210", "SS", 45),
]


# The MEP first fix element, as ACTS1 names it.
WBS_MEP = "31000000-0000-0000-0000-000000000103"

# The demo is generated against the day it is generated on, so the work
# front is a work front rather than a snapshot of some past Tuesday.
TODAY = _dt.date.today().isoformat()


def days_between(start, end):
    """Whole days from one ISO date to another. Negative when end is earlier."""
    return (_dt.date.fromisoformat(end) - _dt.date.fromisoformat(start)).days


def add_days(date, days):
    import datetime
    y, m, d = (int(part) for part in date.split("-"))
    moved = datetime.date(y, m, d) + datetime.timedelta(days=days)
    return moved.isoformat()


def build():
    projects, wbs, cbs, boqs, items, budgets, budget_lines = [], [], [], [], [], [], []
    locations, activities, relations, allocations = [], [], [], []

    # ---- PRJ-001 gets its tree, its programme and a project on its splits ---
    wbs.extend(WBS1_ROOTS)
    wbs.extend(WBS1_ADDED)

    act_ids = {}
    for index, (code, name, wbs_id, duration, start, finish, status,
                done) in enumerate(ACTS1):
        act_id = ACT % (1000 + index)
        act_ids[code] = act_id
        activities.append(dict(
            ID=act_id, code=code, name=name, project_ID=PRJ1, wbs_ID=wbs_id,
            durationDays=str(duration), plannedStart=start, plannedFinish=finish,
            status=status, percentDone="%.2f" % done,
            actualStart=start if done else "",
            actualFinish=finish if done >= 100 else ""))
    for index, (pre, suc, link, lag) in enumerate(RELS1):
        relations.append(dict(
            ID=REL % (1000 + index), predecessor_ID=act_ids[pre],
            successor_ID=act_ids[suc], linkType=link, lagDays=str(lag)))

    # ---- three more jobs ---------------------------------------------------
    for spec in PROJECTS:
        no = spec["no"]
        base = no * 1000
        pid = PRJ % no
        projects.append(dict(
            ID=pid, code=spec["code"], name=spec["name"],
            company_ID=spec["company"], customerParent=spec["customer"],
            contractValue=spec["value"], ccy_code="AED",
            startDate=spec["start"], endDate=spec["end"], stage=spec["stage"],
            executingCompany_ID=spec["company"], syncStatus="NOT_SENT",
            syncAttempts="0"))

        wbs_ids = {}
        for slot, parent, code, kind, description in WBS_TEMPLATE:
            wid = WBS % (base + slot)
            wbs_ids[slot] = wid
            wbs.append(dict(
                ID=wid, code="%s.%s" % (spec["code"], code), project_ID=pid,
                parent_ID="" if parent == "" else wbs_ids[parent],
                activityType=kind, description=description,
                syncStatus="NOT_SENT", syncAttempts="0"))

        cbs_ids = {}
        for slot, parent, code, level, nature, basis in CBS_TEMPLATE:
            cid = CBS % (base + slot)
            cbs_ids[slot] = cid
            cbs.append(dict(
                ID=cid, code=code, project_ID=pid,
                parent_ID="" if parent == "" else cbs_ids[parent],
                libraryNode_ID=LIB.get(code, ""), level=level,
                budgetAmount="0.00", ownAmount="0.00", costNature=nature,
                allocBasis=basis))

        # One building and three floors, so a location filter has something to
        # separate and productivity can be reported per floor rather than per
        # job.
        building = LOC % (base + 0)
        locations.append(dict(
            ID=building, code="%s-B1" % spec["code"], name="Building 1",
            project_ID=pid, parent_ID="", level="L1", locationType="BUILDING"))
        for floor in range(1, 4):
            locations.append(dict(
                ID=LOC % (base + floor),
                code="%s-B1-L%02d" % (spec["code"], floor),
                name="Level %d" % floor, project_ID=pid, parent_ID=building,
                level="L2", locationType="FLOOR", gfa="1400.000", uom="M2"))

        # The bill, priced. The header value is the sum of its lines rather
        # than the contract value: they differ by preliminaries and provisional
        # sums, and a bill that silently equals the contract hides that.
        boq_id = BOQ % (base + 0)
        total = 0.0
        # The template is a shape, not a bill. Quantities scale with the
        # contract, so a 12.9M podium does not arrive with the same 1,640 m3 of
        # slab as a 31.8M tower - four identical bills read as a copy rather
        # than a portfolio, and no filter or sort on the list would separate
        # them.
        scale = float(spec["value"]) / 26750000.0
        for index, (item_no, code, description, qty, uom, rate,
                    cbs_slot) in enumerate(ITEM_TEMPLATE):
            scaled = round(float(qty) * scale, 3)
            amount = scaled * float(rate)
            total += amount
            items.append(dict(
                ID=ITEM % (base + index), boq_ID=boq_id, itemNo=item_no,
                code=code, description=description, qty="%.3f" % scaled,
                uom=uom, rate=rate, amount="%.2f" % amount,
                cbs_ID=cbs_ids[cbs_slot]))
        boqs.append(dict(
            ID=boq_id, boqId="BOQ-%03d" % no, project_ID=pid, version="v1.0",
            status="Approved" if spec["stage"] != "Tender" else "Draft",
            contractValue="%.2f" % total, source="IMPORT"))

        # The budget, at a margin the stage makes plausible: a tender is
        # costed tighter than a job already running.
        budget_id = BUD % (base + 0)
        budget_total = 0.0
        for index, (cbs_slot, category, share) in enumerate(BUDGET_TEMPLATE):
            amount = total * float(share)
            budget_total += amount
            budget_lines.append(budget_line(
                BUDL % (base + index), budget_id, cbs_ids[cbs_slot], category,
                amount))
        budgets.append(dict(
            ID=budget_id, docNo="BUD-2026-%04d" % (100 + no), project_ID=pid,
            company_ID=spec["company"],
            status="Baselined" if spec["stage"] == "Execution" else "Draft",
            raisedBy="arjun.mehta@inflexion.ae", raisedOn="2026-02-10",
            version="V1", daysToLock="30", totalAmount="%.2f" % budget_total))

        # The programme, stretched to fill the job rather than the template.
        #
        # The template is six activities adding up to 405 days, and these jobs
        # run for two and a half years. Laid end to end from the start date
        # they finished eighteen months before the project did, which left
        # every one of them either complete or overdue and no screen able to
        # answer what the site is building this week. Scaling the durations to
        # the contract period is the difference between a programme and a list
        # of activities that happen to have dates.
        #
        # Progress follows the same line: an activity the calendar has already
        # passed is complete, the one today falls inside is part done, and the
        # ones after it are planned. Not a forecast — a job in execution whose
        # every activity sits at zero is a job nobody has ever reported on.
        local_acts = {}
        template_days = sum(row[3] for row in ACT_TEMPLATE)
        span = days_between(spec["start"], spec["end"]) + 1
        stretch = max(1.0, float(span) / float(template_days))
        cursor = spec["start"]
        running = spec["stage"] in ("Execution", "Award")
        for index, (code, name, wbs_slot, duration) in enumerate(ACT_TEMPLATE):
            act_id = ACT % (base + index)
            local_acts[code] = act_id
            scaled = max(1, int(round(duration * stretch)))
            finish = add_days(cursor, scaled - 1)
            elapsed = days_between(cursor, TODAY) + 1
            if not running or elapsed <= 0:
                done, status = 0.0, "Planned"
            elif elapsed >= scaled:
                done, status = 100.0, "Completed"
            else:
                # Behind its own straight line, by a margin that differs per
                # activity so the board has something to sort by.
                done = round(min(97.0, 100.0 * elapsed / scaled
                                 * (0.72 + 0.06 * index)), 2)
                status = "In progress"
            activities.append(dict(
                ID=act_id, code="%s-%s" % (spec["code"], code), name=name,
                project_ID=pid, wbs_ID=wbs_ids[wbs_slot],
                durationDays=str(scaled), plannedStart=cursor,
                plannedFinish=finish, status=status, percentDone="%.2f" % done,
                actualStart=cursor if done else "",
                actualFinish=finish if done >= 100 else ""))
            cursor = add_days(finish, 1)
        for index, (pre, suc, link, lag) in enumerate(REL_TEMPLATE):
            relations.append(dict(
                ID=REL % (base + index), predecessor_ID=local_acts[pre],
                successor_ID=local_acts[suc], linkType=link, lagDays=str(lag)))

        # And the mapping that joins the three: bill line, who builds it, what
        # absorbs it. Whole lines rather than splits — TPL-SINGLE is the
        # decision that covers most of a bill, and PRJ-001 already demonstrates
        # the weighted split.
        for index, (item_no, _c, _d, qty, _u, _r, cbs_slot) in enumerate(
                ITEM_TEMPLATE):
            wbs_slot = ITEM_WBS.get(cbs_slot, 1)
            allocations.append(dict(
                ID=ALLOC % (base + index), project_ID=pid,
                boqItem_ID=ITEM % (base + index), wbs_ID=wbs_ids[wbs_slot],
                cbs_ID=cbs_ids[cbs_slot], location_ID="",
                allocQty="%.3f" % round(float(qty) * scale, 3),
                allocPct="100.00", pctOfItem="100.00",
                template="TPL-SINGLE", splitBasis="Whole line to one element"))

    return dict(projects=projects, wbs=wbs, cbs=cbs, boqs=boqs, items=items,
                budgets=budgets, budget_lines=budget_lines,
                locations=locations, activities=activities,
                relations=relations, allocations=allocations)


# ----------------------------------------------------------- sourcing chain
#
# Two more requests, each with its advisory already decided, so the chain has
# something to run over. The reservations and requisitions they lead to are NOT
# written here — createReservation and raisePurchaseRequisition produce those,
# and a reservation that appeared without one is a reservation whose
# encumbrance nothing supports.

# Each line carries the cost node it charges as well as the element, by slot in
# CBS_TEMPLATE. Both, because they answer different questions: the element is
# where in the job the work sits, the cost node is what kind of cost it is, and
# a requisition raised without the second commits against no budget line at all.
REQUESTS = [
    dict(no=310, doc="RR-2026-0310", vertical="MPR", project=PRJ2,
         company=INFC, wbs=WBS % 2008, need="2026-09-30",
         by="R. Sundaram - Manpower Coordinator", on="2026-08-14",
         lines=[
             ("Carpenter skilled grade 1 - shutter gang",
              "4C000000-0000-0000-0000-000000000005", "24.000", "head",
              "185.00", 4, "IN_HOUSE", "Own labour - Camp 2 released from L02"),
             ("Mason skilled - blockwork gang",
              "4C000000-0000-0000-0000-000000000007", "18.000", "head",
              "170.00", 7, "PROCURE", "Supply labour - no own gang free in window"),
         ]),
    dict(no=320, doc="RR-2026-0320", vertical="MR", project=PRJ % 4,
         company=IFO, wbs=WBS % 4008, need="2026-10-15",
         by="Jin Lee - Material Buyer", on="2026-08-18",
         lines=[
             ("Ready-mix C40/20mm - frame pours",
              "4B000000-0000-0000-0000-000000000041", "1450.000", "m3",
              "268.00", 4, "PROCURE", "No batching plant on site - buy in"),
             ("Rebar 16 mm BS4449",
              "4B000000-0000-0000-0000-000000000042", "96.000", "t",
              "3380.00", 4, "PROCURE", "Stock covers 4 t of 96 t"),
         ]),
    # The one material request that is NOT bought. Every other MR in the
    # portfolio ends at a purchase order, so the store, the goods issue and the
    # consumption norms had nothing on any screen behind them. Charged to the
    # two cost nodes that carry a real norm — a slab is allowed 2.5% waste and
    # a core wall 3%, because the pour is a different job — so the same
    # material measures differently on the two lines, which is the whole point
    # of keying a norm by cost node.
    dict(no=340, doc="RR-2026-0340", vertical="MR", project=PRJ1,
         company=INFC, wbs="31000000-0000-0000-0000-000000000102",
         need="2026-10-05", by="Jin Lee - Material Buyer", on="2026-08-22",
         lines=[
             ("Ready-mix M40 - Tower 1 slabs L12 to L15",
              "4C000000-0000-0000-0000-000000000010", "320.000", "m3",
              "298.00", "32000000-0000-0000-0000-000000000320", "IN_HOUSE",
              "Own batching plant at Al Qudra - no need to buy in"),
             ("Ready-mix M40 - Tower 1 core walls L12 to L15",
              "4C000000-0000-0000-0000-000000000010", "140.000", "m3",
              "298.00", "32000000-0000-0000-0000-000000000330", "IN_HOUSE",
              "Same plant, same week - core lifts follow the slabs"),
         ]),
    dict(no=330, doc="RR-2026-0330", vertical="MPR", project=PRJ % 5,
         company=PMI, wbs=WBS % 5008, need="2026-11-01",
         by="R. Sundaram - Manpower Coordinator", on="2026-08-20",
         lines=[
             ("Mason skilled - podium blockwork",
              "4C000000-0000-0000-0000-000000000007", "14.000", "head",
              "170.00", 7, "IN_HOUSE", "Own gang free from Marina from 20 Oct"),
             ("Carpenter skilled grade 1 - podium shutters",
              "4C000000-0000-0000-0000-000000000005", "20.000", "head",
              "185.00", 4, "PROCURE", "Supply labour - peak overlaps Marina"),
         ]),
]

# ------------------------------------------------------------- subcontracts
#
# Four more packages with a certificate each, so the certification screen shows
# a run of certificates at different points in their contracts rather than one.
# Every net figure is its own arithmetic: certified gross less retention, less
# any liquidated damages, less back charges.

PACKAGES = [
    dict(no=221, project=PRJ1, company=INFC, vendor="0001000221",
         vendor_name="Vendor-BW", scope="Blockwork & Plaster - Towers 1",
         value="2870000.00", seq=3, of=10, claimed="412000.00",
         adjustment="-8500.00", retention="10.00", ld="0.00",
         backcharge="6200.00", raised="2026-06-05",
         by="V. Rao - Project Engineer"),
    dict(no=232, project=PRJ2, company=INFC, vendor="0001000232",
         vendor_name="Vendor-MEP", scope="MEP First Fix - Levels 1 to 8",
         value="5240000.00", seq=2, of=12, claimed="638000.00",
         adjustment="0.00", retention="10.00", ld="0.00",
         backcharge="0.00", raised="2026-07-02",
         by="A. Kurian - MEP Coordinator"),
    dict(no=244, project=PRJ % 4, company=IFO, vendor="0001000244",
         vendor_name="Vendor-STL", scope="Structural Steel - Warehouse frame",
         value="7150000.00", seq=5, of=8, claimed="1120000.00",
         adjustment="-24000.00", retention="5.00", ld="86000.00",
         backcharge="11400.00", raised="2026-07-20",
         by="S. Fernandes - Package Manager"),
    dict(no=251, project=PRJ1, company=INFC, vendor="0001000251",
         vendor_name="Vendor-WP", scope="Waterproofing - Basement & podium",
         value="1340000.00", seq=1, of=6, claimed="196000.00",
         adjustment="0.00", retention="10.00", ld="0.00",
         backcharge="0.00", raised="2026-05-28",
         by="V. Rao - Project Engineer"),
]


# ------------------------------------------------------ measurable locations
#
# Productivity is measured per location, and a location only produces a rate
# when it has both signed hours against it and measured work allocated to it.
# Three of Marina Heights' seven locations had both; the columns line had never
# been split across the building at all, and the two Level 3 zones existed with
# nothing charged to them. The columns package below closes that: a measured
# quantity on the bill line, the split that says where it was built, and the
# formwork gang's signed days on each of those locations.

COLUMNS_ITEM = ITEM % 4                              # 2.E.1.4.01 RCC Columns M50
CARPENTER = "58000000-0000-0000-0000-000000000163"   # 6 heads at AED 280/head-day
COLUMNS_CBS = "32000000-0000-0000-0000-000000000310"
COLUMNS_WBS = "31000000-0000-0000-0000-000000000204"
COLUMNS_QTY = 2460.0
COLUMNS_DONE = "610.000"                             # of 2,460 m3 measured built
TS = "59000000-0000-0000-0000-%012d"

# location, share of the columns line, the basis, the days worked there
COLUMNS_SPLIT = [
    ("36000000-0000-0000-0000-000000000006", "45.00", "Level 6 columns poured",
     ["2026-07-13", "2026-07-14", "2026-07-27", "2026-08-10", "2026-08-11"]),
    ("36000000-0000-0000-0000-000000000031", "30.00", "Level 3 Zone A columns",
     ["2026-06-15", "2026-06-16", "2026-06-29"]),
    ("36000000-0000-0000-0000-000000000032", "25.00", "Level 3 Zone B columns",
     ["2026-06-22", "2026-06-23", "2026-07-06"]),
]


def build_measured_locations():
    """The columns package: where it was built, and who built it."""
    share_total = sum(float(row[1]) for row in COLUMNS_SPLIT)
    if abs(share_total - 100.0) > 0.001:
        raise SystemExit("the columns split accounts for %.2f%% of the line, "
                         "not all of it" % share_total)

    allocations, timesheets = [], []
    for index, (location, share, basis, days) in enumerate(COLUMNS_SPLIT):
        allocations.append(dict(
            ID=ALLOC % (900 + index), project_ID=PRJ1, boqItem_ID=COLUMNS_ITEM,
            wbs_ID=WBS % 1041, cbs_ID=COLUMNS_CBS, location_ID=location,
            allocQty="%.3f" % (COLUMNS_QTY * float(share) / 100.0),
            allocPct=share, pctOfItem=share, template="TPL-ZONES",
            splitBasis=basis))
        for day_index, work_date in enumerate(days):
            # Six heads at eight hours, priced at the gang's own head-day rate.
            # Hours are per head - that is what the sign message states and what
            # the man-hour calculation multiplies by heads.
            timesheets.append(dict(
                ID=TS % (900 + index * 10 + day_index),
                manpowerLine_ID=CARPENTER, workDate=work_date,
                headsPresent="6", regularHrs="8.00", otHrs="0.00",
                wbs_ID=COLUMNS_WBS, cbs_ID=COLUMNS_CBS,
                activity="PRJ-001.03.10.STR-COL",
                costAmount="%.2f" % (6 * 280.0), logStatus="Signed",
                signedBy="Daud Patel - Site Engineer", location_ID=location))
    return allocations, timesheets


# ------------------------------------------------------ what a deduction is
#
# A certificate states a claimed gross, an adjustment, retention, liquidated
# damages and back charges, and arrives at a net. Every one of those except
# retention is the total of lines that say why, and a header figure with no
# lines behind it is the thing the certification screen was built to make
# impossible: press Recalculate and the deduction disappears, because nothing
# supports it.
#
# Keyed by the package number so each certificate's detail sits with it.

ADJ = "73000000-0000-0000-0000-%012d"
LD = "74000000-0000-0000-0000-%012d"
BC = "75000000-0000-0000-0000-%012d"
SIGN = "76000000-0000-0000-0000-%012d"

# package -> the measure the QS cut back, and why
ADJUSTMENTS = {
    221: [("BW-04.2", "Blockwork 200mm - Level 4 zone B", "1180.000", "1140.000",
           "m2", "40 m2 rejected at inspection: joint thickness outside "
                 "tolerance. Remeasured on the certified area: 40 m2 at "
                 "AED 212.50 = AED 8,500 off the claim.")],
    244: [("ST-11", "Structural steel - roof trusses T7 to T9", "84.000",
           "78.000", "t", "Three trusses delivered but not erected at cut-off. "
                          "Certified on erected weight, not delivered: 6 t at "
                          "AED 4,000 = AED 24,000 off the claim.")],
}

# package -> the steps that reach the liquidated damages figure
LD_STEPS = {
    244: [
        (1, "Contract completion", "Subcontract clause 9.2", "2026-05-31", False),
        (2, "Extension of time granted", "EOT-02, 14 days, exceptional rain",
         "14 days", False),
        (3, "Revised completion", "Contract completion plus EOT", "2026-06-14", True),
        (4, "Actual completion", "Handover certificate HC-244", "2026-07-05", False),
        (5, "Delay", "Actual less revised completion", "21 days", False),
        (6, "Chargeable delay", "Delay less 0 days concession", "21 days", True),
        (7, "LD rate", "0.5% of subcontract value per day, capped at 10%",
         "AED 35,750/day", False),
        (8, "LD before cap", "21 days at the daily rate", "AED 750,750", False),
        (9, "Cap", "10% of AED 7,150,000", "AED 715,000", False),
        (10, "LD applied this certificate", "Cap reached; recovered over "
             "certificates 5 to 8", "AED 86,000", True),
    ],
}

# package -> what was recharged, and what caused it
BACK_CHARGES = {
    221: [("Rectification of out-of-tolerance blockwork joints",
           "NCR-221-07", "RCH-LAB-RECT", "48 hr", "AED 95/hr", "4560.00"),
          ("Scaffold left standing beyond agreed date",
           "SI-221-03", "RCH-PLT-HIRE", "8 days", "AED 205/day", "1640.00")],
    244: [("Grinding and re-coating of damaged galvanising",
           "NCR-244-02", "RCH-LAB-RECT", "60 hr", "AED 110/hr", "6600.00"),
          ("Consumables drawn from main contractor stores",
           "SI-244-05", "RCH-MAT-SUP", "1 lot", "AED 4,800", "4800.00")],
}

# Who signed each certificate off. A certificate nobody signed is a draft, and
# four of these were reading as Certified with an empty sign-off list.
SIGNERS = [
    (1, "Quantity Surveyor", "N. Fernandes", "Approved"),
    (2, "Project Manager", "V. Rao", "Approved"),
    (3, "Commercial Manager", "A. Haddad", "Approved"),
]


def build_certificate_detail():
    """The lines behind every certificate's deductions, and its sign-offs."""
    adjustments, ld_steps, back_charges, sign_offs = [], [], [], []

    for spec in PACKAGES:
        no = spec["no"]
        pc_id = PC % no

        for index, (line, description, claimed, certified, uom,
                    reason) in enumerate(ADJUSTMENTS.get(no, [])):
            adjustments.append(dict(
                ID=ADJ % (no * 10 + index), pc_ID=pc_id, subBoqLine=line,
                description=description, claimedQty=claimed,
                certifiedQty=certified,
                deltaQty="%.3f" % (float(certified) - float(claimed)),
                uom=uom, reason=reason))

        for step_no, step, basis, value, emphasis in LD_STEPS.get(no, []):
            ld_steps.append(dict(
                ID=LD % (no * 100 + step_no), pc_ID=pc_id, stepNo=str(step_no),
                step=step, basis=basis, value=value,
                emphasis="true" if emphasis else "false"))

        for index, (description, cause, kind, qty, rate,
                    amount) in enumerate(BACK_CHARGES.get(no, [])):
            back_charges.append(dict(
                ID=BC % (no * 10 + index), pc_ID=pc_id, description=description,
                cause=cause, rechargeType=kind, qtyBasis=qty, rate=rate,
                amount=amount))

        for seq, role, name, decision in SIGNERS:
            sign_offs.append(dict(
                ID=SIGN % (no * 10 + seq), pc_ID=pc_id, seq=str(seq), role=role,
                name=name, decision=decision,
                decidedOn=spec["raised"] + "T11:00:00Z"))

    return adjustments, ld_steps, back_charges, sign_offs


# ---------------------------------------------------------------- variations
#
# Three changes on Marina Heights, at three points in the chain, because a
# variation account with everything approved shows none of the argument that
# makes one worth having.
#
# The middle one is the point of the screen: a client-instructed remeasure that
# adds revenue and loses money, which is invisible on any report that shows a
# single "value" column.

VO = "3c000000-0000-0000-0000-%012d"
VOL = "3d000000-0000-0000-0000-%012d"
BOQ1 = "33000000-0000-0000-0000-000000000001"
SLAB_ITEM = ITEM % 5
COLUMN_ITEM = ITEM % 4
WBS_SLABS = WBS % 1042

# The three level splits on the slab line, written before the slab had an
# element of its own.
SLAB_SPLITS = {ALLOC % 1, ALLOC % 2, ALLOC % 5}
WBS_COLUMNS = WBS % 1041
CBS_SLABS = "32000000-0000-0000-0000-000000000320"
CBS_COLUMNS = "32000000-0000-0000-0000-000000000310"

VARIATIONS = [
    dict(no=1, doc="VO-2026-0001", client="EM-VO-014",
         title="Level 5 and 6 slab thickness increased to 300 mm",
         origin="CLIENT_INSTRUCTION", instruction="AI-114", instructed="2026-04-18",
         submitted="2026-04-29", decided="2026-05-12", status="Approved",
         by="Emaar Marina LLC - N. Al Suwaidi", eot=12,
         note="Approved at submitted rates. Extension of time agreed at 12 days "
              "against the 18 claimed.",
         lines=[
             ("ADD", "Additional 50 mm slab depth, levels 5 and 6",
              SLAB_ITEM, "512.000", "m3", "2180.00", "1685.00",
              WBS_SLABS, CBS_SLABS),
             ("ADD", "Additional reinforcement to suit increased depth",
              None, "44.000", "t", "3420.00", "2760.00",
              WBS_SLABS, CBS_SLABS),
         ]),
    dict(no=2, doc="VO-2026-0002", client="EM-VO-021",
         title="Column remeasure - levels 1 to 10 as built",
         origin="CLIENT_INSTRUCTION", instruction="AI-127", instructed="2026-06-02",
         submitted="2026-06-20", decided="2026-07-01", status="Approved",
         by="Emaar Marina LLC - N. Al Suwaidi", eot=0,
         note="Remeasure agreed at contract rates. No extension of time: the "
              "work was within the original sequence.",
         lines=[
             # Contract rate, actual cost. The columns as built are more
             # congested than the ones priced, so the same rate no longer covers
             # the work - which is exactly the variation worth finding.
             ("REMEASURE", "Columns as built, levels 1 to 10 - net increase",
              COLUMN_ITEM, "186.000", "m3", "2720.00", "3140.00",
              WBS_COLUMNS, CBS_COLUMNS),
         ]),
    dict(no=3, doc="VO-2026-0003", client="",
         title="Basement pump room relocation",
         origin="DESIGN_CHANGE", instruction="RFI-208", instructed="2026-08-05",
         submitted="2026-08-18", decided="", status="Submitted",
         by="", eot=9,
         note="",
         lines=[
             ("ADD", "Relocate pump room, form new plinths and penetrations",
              None, "1.000", "item", "184000.00", "142500.00",
              WBS % 1032, "32000000-0000-0000-0000-000000000230"),
             ("OMIT", "Original pump room plinths, not built",
              None, "1.000", "item", "46000.00", "35200.00",
              WBS % 1032, "32000000-0000-0000-0000-000000000230"),
         ]),
]


def build_variations():
    """The changes, and the lines that price them.

    The header amounts are left empty on purpose. recalculate derives revenue,
    cost and margin from the lines, and a seeded total would be a figure the
    product never computed - which is the one thing demo data must not be.
    """
    variations, lines = [], []
    for spec in VARIATIONS:
        vo_id = VO % spec["no"]
        variations.append(dict(
            ID=vo_id, docNo=spec["doc"], project_ID=PRJ1, company_ID=INFC,
            boq_ID=BOQ1, clientRef=spec["client"], title=spec["title"],
            origin=spec["origin"], instructionRef=spec["instruction"],
            instructedOn=spec["instructed"], submittedOn=spec["submitted"],
            decidedOn=spec["decided"], decidedBy=spec["by"],
            decisionNote=spec["note"], status=spec["status"],
            timeExtensionDays=str(spec["eot"]), ccy_code="AED",
            raisedBy="N. Fernandes - Quantity Surveyor",
            raisedOn=spec["instructed"]))
        for index, (kind, description, item, qty, uom, revenue_rate,
                    cost_rate, wbs, cbs) in enumerate(spec["lines"], start=1):
            lines.append(dict(
                ID=VOL % (spec["no"] * 10 + index), variation_ID=vo_id,
                lineNo=str(index), changeType=kind, description=description,
                boqItem_ID=item or "", qty=qty, uom=uom,
                revenueRate=revenue_rate, costRate=cost_rate,
                wbs_ID=wbs, cbs_ID=cbs))
    return variations, lines


def money(text):
    return round(float(text), 2)


def build_commercial():
    requests, request_lines, advisories = [], [], []
    for spec in REQUESTS:
        rr_id = RR % spec["no"]
        requests.append(dict(
            ID=rr_id, docNo=spec["doc"], verticalType=spec["vertical"],
            project_ID=spec["project"], company_ID=spec["company"],
            wbs_ID=spec["wbs"], needBy=spec["need"], isSubstitution="false",
            # Advised, not Approved: the advisory decisions below have been
            # taken, and availability is the next step. Seeding these as
            # Approved left them one state behind their own decisions, so
            # runAvailabilityCheck refused and the reservation after it never
            # happened.
            prFlag="false", status="Advised", raisedBy=spec["by"],
            raisedOn=spec["on"]))
        base = int(spec["project"][-2:]) * 1000
        for index, (description, resource, qty, uom, rate, cbs_slot, decision,
                    rationale) in enumerate(spec["lines"], start=1):
            line_id = RRL % (spec["no"] * 10 + index)
            advisory_id = ADV % (spec["no"] * 10 + index)
            request_lines.append(dict(
                ID=line_id, parent_ID=rr_id, lineNo=str(index),
                resource_ID=resource, description=description, qty=qty,
                uom=uom, wbs_ID=spec["wbs"],
                # A slot for the generated projects, whose CBS this file
                # instantiates from one template, and a full key for the
                # flagship, whose CBS came from elsewhere and does not follow
                # the arithmetic.
                cbs_ID=(cbs_slot if isinstance(cbs_slot, str)
                        else CBS % (base + cbs_slot)),
                estUnitCost=rate,
                estTotal="%.2f" % (float(qty) * float(rate)),
                needBy=spec["need"], lineStatus="Advised",
                # The line points at its decision. Without this the decision
                # exists and the line cannot find it, so every line reads as
                # undecided and nothing downstream consumes it.
                advisory_ID=advisory_id))
            advisories.append(dict(
                ID=advisory_id, rr_ID=rr_id,
                line_ID=line_id, decision=decision,
                decidedBy="Resource Advisory Desk",
                decidedOn=spec["on"] + "T09:00:00Z", rationale=rationale))
    return requests, request_lines, advisories


def build_certificates():
    packages, applications, certificates = [], [], []
    for spec in PACKAGES:
        scr_id = SCR % spec["no"]
        packages.append(dict(
            ID=scr_id, docNo="SR-2026-%04d" % spec["no"],
            project_ID=spec["project"], company_ID=spec["company"],
            status="Active", raisedBy=spec["by"], raisedOn=spec["raised"],
            scopeDescription=spec["scope"], vendorBPNo=spec["vendor"],
            vendorName=spec["vendor_name"], isGroupCompany="false",
            contractValue=spec["value"], ccy="AED"))

        pa_id = PA % spec["no"]
        applications.append(dict(
            ID=pa_id, scr_ID=scr_id, paNo="PA-%03d" % spec["seq"],
            claimedAmount=spec["claimed"], status="Certified"))

        certified = money(spec["claimed"]) + money(spec["adjustment"])
        retention = round(certified * float(spec["retention"]) / 100.0, 2)
        net = round(certified - retention - money(spec["ld"])
                    - money(spec["backcharge"]), 2)
        certificates.append(dict(
            ID=PC % spec["no"],
            docNo="PC-2026-%04d-%02d" % (spec["no"], spec["seq"]),
            project_ID=spec["project"], company_ID=spec["company"],
            status="Certified", raisedBy=spec["by"], raisedOn=spec["raised"],
            pa_ID=pa_id, scr_ID=scr_id, certSeq=str(spec["seq"]),
            certOf=str(spec["of"]), claimedGross=spec["claimed"],
            adjustment=spec["adjustment"], certifiedGross="%.2f" % certified,
            retentionPct=spec["retention"], retentionAmount="%.2f" % retention,
            netCertified="%.2f" % net, ldApplied=spec["ld"],
            backChargeTotal=spec["backcharge"],
            paymentTerm="NET 30 from cert date"))
    return packages, applications, certificates


# PRJ-001's substructure bill lines were never sent anywhere. The columns and
# the slab carry a split; the pile cap, the raft and the rebar do not, which is
# why thirteen of the flagship job's fifteen budget lines had no dated work to
# follow and were spread flat across the programme.
#
# Each line goes to the element that builds it. The rebar is the exception and
# is split, because reinforcement is bought once and placed in both pours — the
# quantity is real and the split is the reason a rebar line can be reported
# against the pour it went into rather than against the purchase.
SUBSTRUCTURE_SPLITS = [
    ("1.E.1.1.01", WBS % 1030, "100.00", "Whole line to the pile caps"),
    ("1.E.1.1.02", WBS % 1031, "100.00", "Whole line to the raft"),
    ("1.E.2.2.01", WBS % 1030, "45.00", "Cage steel, pile caps"),
    ("1.E.2.2.01", WBS % 1031, "55.00", "Cage steel, raft"),
]


def build_substructure_splits():
    """The splits the substructure bill lines never had."""
    fields, items = read("prj-BOQItem")
    by_item_no = {}
    for row in items:
        by_item_no.setdefault(row["itemNo"], row)

    allocations = []
    for index, (item_no, wbs_id, pct, basis) in enumerate(SUBSTRUCTURE_SPLITS):
        item = by_item_no.get(item_no)
        if item is None:
            raise SystemExit("no bill line %s to split" % item_no)
        allocations.append(dict(
            ID=ALLOC % (910 + index), project_ID=PRJ1, boqItem_ID=item["ID"],
            wbs_ID=wbs_id, cbs_ID=item["cbs_ID"], location_ID="",
            allocQty="%.3f" % (float(item["qty"]) * float(pct) / 100.0),
            allocPct=pct, pctOfItem=pct, template="TPL-ELEMENT",
            splitBasis=basis))
    return allocations


def explode_budget_lines():
    """Puts the budget lines on the three keys they are controlled at.

    A line that names only a cost heading can be reported by kind of cost and
    by nothing else — not by the part of the works it pays for, and not into a
    month, because a cost heading has no dates and a WBS element does. The
    splits already say which elements and which bill lines sit under each
    heading, so the line divides across them in proportion to what was
    allocated, and the parts sum back to the amount that was there before.

    A heading nothing is allocated against — preliminaries, insurances, the
    site office — keeps its single line and leaves the two new keys empty.
    That is not a gap to be filled: those costs are carried by the project.

    Collapses before it splits, so a second run over an already-split file
    reproduces the same result rather than splitting the splits. That also
    means a mapping corrected upstream — a bill line re-pointed at the element
    that actually builds it — reaches the budget on the next run instead of
    leaving the money on the element it used to name.
    """
    _f, allocations = read("prj-Allocation")
    _f, items = read("prj-BOQItem")
    item_amount = {row["ID"]: float(row.get("amount") or 0.0) for row in items}

    # What each cost heading has under it: which element, which bill line, and
    # what share of that line's value went there.
    under = {}
    for alloc in allocations:
        cbs_id, wbs_id = alloc.get("cbs_ID"), alloc.get("wbs_ID")
        item_id = alloc.get("boqItem_ID")
        pct = float(alloc.get("allocPct") or 0.0)
        if not (cbs_id and wbs_id and item_id) or pct <= 0:
            continue
        value = item_amount.get(item_id, 0.0) * pct / 100.0
        if value <= 0:
            continue
        key = (cbs_id, wbs_id, item_id)
        under.setdefault(cbs_id, {})
        under[cbs_id][key] = under[cbs_id].get(key, 0.0) + value

    fields, lines = read("bud-BudgetLine")

    # Its own output from last time goes first. The seeded line for a heading
    # is the original and the split rows are derived from it, so keeping both
    # and summing them would count every split heading twice.
    lines = [line for line in lines if not line["ID"].startswith(SPLIT_PREFIX)]

    # Back to one line per heading and cost nature, keeping the earliest ID of
    # each group so a re-run does not renumber what it already wrote.
    order, groups = [], {}
    for line in lines:
        key = (line["budget_ID"], line.get("cbs_ID", ""), line.get("category", ""))
        if key not in groups:
            groups[key] = dict(line)
            groups[key]["amount"] = 0.0
            order.append(key)
        elif line["ID"] < groups[key]["ID"]:
            groups[key]["ID"] = line["ID"]
        groups[key]["amount"] += float(line.get("amount") or 0.0)

    rebuilt, split_lines, serial = [], 0, 0
    for key in order:
        line = groups[key]
        amount = line["amount"]
        parts = under.get(line.get("cbs_ID"))
        if not parts or amount <= 0:
            line["amount"] = "%.2f" % amount
            line["authorised"] = "%.2f" % amount
            line["available"] = "%.2f" % amount
            line["wbs_ID"] = line.get("wbs_ID", "")
            line["boqItem_ID"] = line.get("boqItem_ID", "")
            rebuilt.append(line)
            continue
        total_value = sum(parts.values())
        placed, keys = 0.0, sorted(parts)
        for position, part_key in enumerate(keys):
            part = (amount - placed if position == len(keys) - 1
                    else round(amount * parts[part_key] / total_value, 2))
            placed += part
            row = dict(line)
            if position > 0:
                serial += 1
                row["ID"] = SPLIT_PREFIX + "%012d" % serial
            row["cbs_ID"], row["wbs_ID"], row["boqItem_ID"] = part_key
            row["amount"] = "%.2f" % part
            row["authorised"] = "%.2f" % part
            row["available"] = "%.2f" % part
            rebuilt.append(row)
        split_lines += 1
    write("bud-BudgetLine", fields, rebuilt)
    return split_lines, len(rebuilt)


# ------------------------------------------------ the stretch the job is on
#
# PRJ-001 runs to June 2027 and its programme stopped in May 2026, which is why
# every activity on it reads as finished or overdue and no screen could answer
# "what is the site building this week". The tail was never written.
#
# Written against today rather than against fixed dates, because the one thing
# a work front cannot be is stale: a board of hard-coded activities is accurate
# on the day it is authored and wrong every day after. Re-running this tool
# moves the live stretch to wherever today is.
#
# The three 2025 activities are left exactly as they are. They are 82%, 74% and
# 41% complete against finish dates nine months gone, and that is the truth of
# this project — the reconciliation says the same thing in money. A demo that
# quietly re-dated them would be showing a job that is not the one the numbers
# describe.
#
# (code, name, WBS, start offset from today, duration, percent done, status)
LIVE_ACTS = [
    ("A3000", "MEP first fix L03-L06", WBS_MEP, -55, 80, 62, "In progress"),
    ("A4000", "Facade & cladding to L10", WBS % 1002, -20, 110, 18, "In progress"),
    ("A5000", "Cores & shear walls L11-L24", WBS % 1040, -8, 128, 9, "In progress"),
    ("A5010", "Slabs L07-L14", WBS % 1042, 3, 140, 0, "Planned"),
    ("A5020", "MEP second fix L01-L06", WBS_MEP, 5, 95, 0, "Planned"),
    ("A5030", "Commissioning & handover", WBS % 1002, 240, 55, 0, "Planned"),
]

LIVE_RELS = [
    ("A4000", "A5000", "SS", 30),
    ("A5000", "A5010", "SS", 45),
    ("A3000", "A5020", "FS", 10),
    ("A5020", "A5030", "FS", 0),
]

# Who is on which front, and where. The first two carry crews; A5000 carries
# none, so the board has a front that is running with nobody on it — which is
# the row the screen exists to surface, and a demo where every front is manned
# would never show it.
LIVE_CREWS = [
    ("A3000", "58000000-0000-0000-0000-000000000164", WBS_MEP,
     "32000000-0000-0000-0000-000000000260", LOC % 4, 2, "8.00", "0.00", "320.00"),
    ("A4000", "58000000-0000-0000-0000-000000000165", WBS % 1002,
     "32000000-0000-0000-0000-000000000240", LOC % 5, 4, "8.00", "2.00", "180.00"),
]


def build_live_programme(today):
    """The activities PRJ-001 is standing on this week, and who is on them.

    Two of these already exist, planned for dates that have since gone past.
    They keep their own ids and are re-dated rather than written again: a
    second A3000 beside the first would be two answers to when the MEP first
    fix runs, and nothing on any screen would say which one the budget, the
    links and the daily logs belong to.
    """
    _f, existing = read("prj-Activity")
    id_by_code = {row["code"]: row["ID"] for row in existing
                  if row.get("project_ID") == PRJ1}

    activities, relations, timesheets = [], [], []
    ids = {}

    for index, (code, name, wbs_id, offset, duration, done,
                status) in enumerate(LIVE_ACTS):
        start = add_days(today, offset)
        finish = add_days(start, duration - 1)
        act_id = id_by_code.get(code, ACT % (1100 + index))
        ids[code] = act_id
        activities.append(dict(
            ID=act_id, code=code, name=name, project_ID=PRJ1, wbs_ID=wbs_id,
            durationDays=str(duration), plannedStart=start, plannedFinish=finish,
            status=status, percentDone="%.2f" % done,
            actualStart=start if done else "", actualFinish=""))

    for index, (pre, suc, link, lag) in enumerate(LIVE_RELS):
        relations.append(dict(
            ID=REL % (1100 + index), predecessor_ID=ids[pre],
            successor_ID=ids[suc], linkType=link, lagDays=str(lag)))

    # The last six days of signed logs, so "who is on it today" has an answer
    # and "who has been on it this week" has a different one.
    serial = 0
    for code, crew, wbs_id, cbs_id, location, heads, regular, ot, rate in LIVE_CREWS:
        for back in range(0, 6):
            work_date = add_days(today, -back)
            timesheets.append(dict(
                ID=TS % (1100 + serial), manpowerLine_ID=crew, workDate=work_date,
                headsPresent=str(heads), regularHrs=regular, otHrs=ot,
                wbs_ID=wbs_id, cbs_ID=cbs_id,
                activity="PRJ-001.%s" % code, location_ID=location,
                costAmount="%.2f" % (heads * float(rate)),
                logStatus="Signed", signedBy="Daud Patel - Site Engineer"))
            serial += 1

    return activities, relations, timesheets


def main():
    built = build()

    # PRJ-001's existing elements gain the parent they never had.
    fields, rows = read("prj-WBSElement")
    moved = 0
    for row in rows:
        if row["ID"] in WBS1_REPARENT and not row.get("parent_ID"):
            row["parent_ID"] = WBS1_REPARENT[row["ID"]]
            moved += 1
    write("prj-WBSElement", fields, rows)

    # And its existing splits gain the project they always belonged to.
    #
    # The slab splits also gain the element that actually pours them. They were
    # written against WBS-1.02 Sub-structure while naming levels 3 to 5, and
    # WBS-2.04.2 Slabs L03-L06 — which carries the activity that has the dates —
    # sat beside them unused. Left alone it reads as a mapping error nobody
    # would notice: the money is right, the element is wrong, and the slab is
    # forecast to be poured while the basement is still being dug.
    fields, rows = read("prj-Allocation")
    repointed = 0
    for row in rows:
        if not row.get("project_ID"):
            row["project_ID"] = PRJ1
        if row["ID"] in SLAB_SPLITS and row.get("wbs_ID") != WBS_SLABS:
            row["wbs_ID"] = WBS_SLABS
            repointed += 1
    write("prj-Allocation", fields, rows)

    report = [
        ("prj-Project", built["projects"]),
        ("prj-WBSElement", built["wbs"]),
        ("prj-CBSInstance", built["cbs"]),
        ("prj-SiteLocation", built["locations"]),
        ("prj-BOQ", built["boqs"]),
        ("prj-BOQItem", built["items"]),
        ("prj-Allocation", built["allocations"]),
        ("bud-Budget", built["budgets"]),
        ("bud-BudgetLine", budget1_lines() + built["budget_lines"]),
        ("prj-Activity", built["activities"]),
        ("prj-ActivityRelation", built["relations"]),
    ]

    # The columns line gains the measured quantity its split reports against.
    # Without it every location under the split has hours and nothing built,
    # and productivity reports a blank with a reason rather than a rate.
    patch("prj-BOQItem", COLUMNS_ITEM,
          {"cumDoneQty": COLUMNS_DONE,
           "cumDonePct": "%.2f" % (float(COLUMNS_DONE) / COLUMNS_QTY * 100.0)})
    measured_allocations, measured_days = build_measured_locations()

    live_acts, live_rels, live_days = build_live_programme(TODAY)
    report += [
        ("prj-Activity", live_acts),
        ("prj-ActivityRelation", live_rels),
        ("mpr-TimesheetEntry", live_days),
    ]

    variations, variation_lines = build_variations()
    requests, request_lines, advisories = build_commercial()
    packages, applications, certificates = build_certificates()
    adjustments, ld_steps, back_charges, sign_offs = build_certificate_detail()
    report += [
        ("prj-Allocation", measured_allocations),
        ("mpr-TimesheetEntry", measured_days),
        ("wf-ResourceRequest", requests),
        ("wf-ResourceRequestLine", request_lines),
        ("wf-AdvisoryDecision", advisories),
        ("scr-SubcontractRequest", packages),
        ("scr-PaymentApplication", applications),
        ("scr-PaymentCertificate", certificates),
        ("scr-CertAdjustmentLine", adjustments),
        ("scr-LDCalculationStep", ld_steps),
        ("scr-BackChargeLine", back_charges),
        ("scr-CertSignOff", sign_offs),
        ("vo-VariationOrder", variations),
        ("vo-VariationLine", variation_lines),
    ]

    report.append(("prj-Allocation", build_substructure_splits()))

    print("  WBS elements re-parented under a root: %d" % moved)
    print("  slab splits re-pointed at the element that pours them: %d"
          % repointed)
    for entity, new_rows in report:
        added, total = upsert(entity, new_rows)
        print("  %-24s +%-4d -> %d row(s)" % (entity, added, total))

    split, lines = explode_budget_lines()
    print("  budget lines split over their own splits: %d -> %d row(s)"
          % (split, lines))


main()
