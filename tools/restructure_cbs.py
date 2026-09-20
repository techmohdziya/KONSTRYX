"""Rebuilds the cost breakdown structure so it starts with preliminaries.

The library it replaces did not hold together, and the CBS screen showed it:

    00     Site Establishment          preliminaries, not called preliminaries
    01     Sub-structure               one child, nothing else
    02     Super-structure             but 02.30 was "Raft & pile cap RCC",
                                       which is substructure work, and 02.50
                                       was MEP first fix, which is services
    03     Structure - Concrete        a SECOND structure level-1, overlapping
                                       02 with columns, slabs and core walls

So a cost node's parent said nothing reliable about what kind of cost it was,
which is the one job a breakdown has. It also meant a budget line and the
allocation for the same work could land on different branches — which is
exactly what left the budget phasing falling back to straight-line spreads.

The structure below is the ordinary contractor's one: preliminaries first,
then the works in the order they are built, then services and externals.

IDS ARE PRESERVED. Every existing node keeps its key and changes only its
code, name and parent; new branches get new keys. That matters because budget
lines, allocations, bill items, daily logs and request lines all point at these
rows by ID, not by code — recoding without preserving the keys would silently
re-point every cost in the system at the wrong node, and the totals would still
add up.

    python tools/restructure_cbs.py [--check]
"""
import csv
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "test", "data")
CHECK = "--check" in sys.argv

LIB = "41000000-0000-0000-0000-%012d"
INSTANCE = "32000000-0000-0000-0000-%012d"

# code, name, level, parent code, cost nature, scope, the key it keeps.
#
# A key of None mints a new node. Everything else is an existing row being put
# where it belongs — the third column of each tuple is where it used to be, kept
# here so the move is reviewable rather than something a reader has to
# reconstruct from a diff.
STRUCTURE = [
    # code     name                                   level parent  nature      scope     id     was
    ("00",    "Preliminaries & General",              "L1",  "",    "INDIRECT", "GROUP",   1,   "00 Site Establishment"),
    ("00.10", "Site establishment & facilities",      "L2",  "00",  "INDIRECT", "GROUP",  10,   "00.10"),
    ("00.20", "Temporary works & hoarding",           "L2",  "00",  "INDIRECT", "GROUP",  13,   None),
    ("00.30", "Site supervision & staff",             "L2",  "00",  "INDIRECT", "GROUP",  14,   None),

    ("01",    "Substructure",                         "L1",  "",    "DIRECT",   "GROUP",   2,   "01 Sub-structure"),
    ("01.10", "Excavation & shoring",                 "L2",  "01",  "DIRECT",   "GROUP",  15,   None),
    ("01.20", "Piling",                               "L2",  "01",  "DIRECT",   "GROUP",  11,   "01.20"),
    ("01.30", "Pile caps & raft",                     "L2",  "01",  "DIRECT",   "GROUP",  40,   "02.30 — was under Super-structure"),
    ("01.35", "Pile caps & raft - subcontracted",     "L2",  "01",  "DIRECT",   "GROUP",  41,   "02.35 — was under Super-structure"),
    ("01.40", "Basement retaining walls",             "L2",  "01",  "DIRECT",   "GROUP",  16,   None),

    ("02",    "Superstructure",                       "L1",  "",    "DIRECT",   "GROUP",   3,   "02 Super-structure"),
    ("02.10", "Frame - general",                      "L2",  "02",  "DIRECT",   "GROUP",  12,   "02.10"),
    ("02.20", "Columns",                              "L2",  "02",  "DIRECT",   "GROUP",  31,   "03.10 — was under Structure - Concrete"),
    ("02.30", "Slabs",                                "L2",  "02",  "DIRECT",   "GROUP",  32,   "03.20 — was under Structure - Concrete"),
    ("02.40", "Core & shear walls",                   "L2",  "02",  "DIRECT",   "GROUP",  33,   "03.30 — was under Structure - Concrete"),
    ("02.50", "Formwork",                             "L2",  "02",  "DIRECT",   "GROUP",  42,   "02.40"),
    ("02.90", "Frame - company specific",             "L2",  "02",  "DIRECT",   "COMPANY", 20,  "02.90"),
    ("02.95", "Fabrication - company specific",       "L2",  "02",  "DIRECT",   "COMPANY", 21,  "02.95"),

    ("03",    "Architectural",                        "L1",  "",    "DIRECT",   "GROUP",  30,   "03 Structure - Concrete — repurposed"),
    ("03.10", "Blockwork & masonry",                  "L2",  "03",  "DIRECT",   "GROUP",  44,   "02.60 — was under Super-structure"),
    ("03.20", "Finishes",                             "L2",  "03",  "DIRECT",   "GROUP",  17,   None),

    ("04",    "MEP",                                  "L1",  "",    "DIRECT",   "GROUP",  50,   None),
    ("04.10", "MEP first fix",                        "L2",  "04",  "DIRECT",   "GROUP",  43,   "02.50 — was under Super-structure"),
    ("04.20", "MEP second fix",                       "L2",  "04",  "DIRECT",   "GROUP",  18,   None),

    ("05",    "External works",                       "L1",  "",    "DIRECT",   "GROUP",  60,   None),
    ("05.10", "Roads, hardstanding & landscaping",    "L2",  "05",  "DIRECT",   "GROUP",  19,   None),
]

# The phase a level-1 heads, inherited by everything under it.
PHASE = {"00": "Preliminaries", "01": "Substructure", "02": "Superstructure",
         "03": "Architectural", "04": "MEP", "05": "External works"}

# How the indirect nodes are spread when they are the pool being allocated.
ALLOC_BASIS = {"00": "DIRECT_COST", "00.10": "DIRECT_COST",
               "00.20": "DIRECT_COST", "00.30": "LABOUR_HOURS"}


def path(entity):
    return os.path.join(DATA, "konstryx.%s.csv" % entity)


def read(entity):
    with io.open(path(entity), encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        return list(reader.fieldnames), [dict(row) for row in reader]


def write(entity, fields, rows):
    # Refuse to drop a value on the floor.
    #
    # DictWriter's extrasaction="ignore" quietly discards any key the header
    # does not have, which is how costNature and allocBasis were computed for
    # every node and written nowhere: the file had no such columns, the values
    # vanished, and the model's DIRECT default made the whole breakdown - including
    # preliminaries - read as direct cost. Nothing errored and the tree looked right.
    unknown = sorted({key for row in rows for key in row} - set(fields))
    if unknown:
        raise SystemExit("%s has no column(s) for %s - add them with "
                         "with_column() rather than losing the values"
                         % (entity, ", ".join(unknown)))
    if CHECK:
        return
    with io.open(path(entity), "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow({f: row.get(f, "") for f in fields})


def with_column(fields, rows, column, after):
    """Adds a column in a readable position rather than at the end."""
    if column in fields:
        return fields
    fields = list(fields)
    fields.insert(fields.index(after) + 1 if after in fields else len(fields),
                  column)
    for row in rows:
        row.setdefault(column, "")
    return fields


def rebuild_library():
    fields, rows = read("master-CBSNode")
    fields = with_column(fields, rows, "name", "code")
    fields = with_column(fields, rows, "costNature", "phase")
    fields = with_column(fields, rows, "allocBasis", "costNature")
    existing = {row["ID"]: row for row in rows}

    by_code = {entry[0]: LIB % entry[6] for entry in STRUCTURE}
    kept, minted, moved = 0, 0, []

    out = []
    for code, name, level, parent, nature, scope, key, was in STRUCTURE:
        node_id = LIB % key
        row = existing.get(node_id)
        if row is None:
            row = {"ID": node_id, "masterStatus": "ACTIVE"}
            minted += 1
        else:
            kept += 1
            if row.get("code") != code:
                moved.append("%s -> %s  %s" % (row.get("code"), code, name))
        row.update({
            "code": code,
            "name": name,
            "level": level,
            "parent_ID": by_code[parent] if parent else "",
            "phase": PHASE[code.split(".")[0]],
            "costNature": nature,
            "scope": scope,
            "allocBasis": ALLOC_BASIS.get(code, ""),
        })
        row.setdefault("constructionType", "High-rise")
        row.setdefault("owningCompany_ID", "")
        row.setdefault("masterStatus", "ACTIVE")
        out.append(row)

    orphaned = [row for row in rows
                if row["ID"] not in {entry_id for entry_id in by_code.values()}
                and row["ID"] not in {LIB % e[6] for e in STRUCTURE}]
    if orphaned:
        # Never silently dropped: a node still referenced by a budget line would
        # take the line's cost out of the tree with it.
        raise SystemExit("These library nodes are in the file and not in the "
                         "structure, so restructuring would orphan whatever "
                         "points at them: %s"
                         % ", ".join(r.get("code", r["ID"]) for r in orphaned))

    write("master-CBSNode", fields, out)
    return kept, minted, moved


def rebuild_instances():
    """Re-points every project's own breakdown at the restructured library."""
    fields, rows = read("prj-CBSInstance")
    fields = with_column(fields, rows, "name", "code")
    fields = with_column(fields, rows, "costNature", "level")
    fields = with_column(fields, rows, "allocBasis", "costNature")

    library = {LIB % entry[6]: entry for entry in STRUCTURE}
    parents = {entry[0]: entry for entry in STRUCTURE}

    # A project's instance of a given library node, so a child can find the
    # instance of its parent rather than the library node's.
    instance_of = {}
    for row in rows:
        instance_of.setdefault(row.get("project_ID"), {})[
            row.get("libraryNode_ID")] = row["ID"]

    # A project whose breakdown stops at the eight nodes it happened to be
    # seeded with is a project missing whole phases of its own cost structure.
    # Every project gets every library node; the ones nothing is budgeted
    # against simply sit at zero, which is what an unspent phase looks like.
    projects = sorted({row.get("project_ID") for row in rows if row.get("project_ID")})
    minted = 0
    for index, project_id in enumerate(projects, start=1):
        held = instance_of.setdefault(project_id, {})
        for entry in STRUCTURE:
            lib_id = LIB % entry[6]
            if lib_id in held:
                continue
            # Deterministic and far from the seeded block, so re-running mints
            # the same key rather than a second copy of the same node.
            new_id = INSTANCE % (900000 + index * 1000 + entry[6])
            held[lib_id] = new_id
            rows.append({
                "ID": new_id,
                "project_ID": project_id,
                "libraryNode_ID": lib_id,
                "budgetAmount": "0.00",
                "ownAmount": "0.00",
            })
            minted += 1

    changed = 0
    for row in rows:
        entry = library.get(row.get("libraryNode_ID"))
        if entry is None:
            continue
        code, name, level, parent_code, nature, _scope, _key, _was = entry
        parent_id = ""
        if parent_code:
            parent_entry = parents[parent_code]
            parent_lib = LIB % parent_entry[6]
            parent_id = instance_of.get(row.get("project_ID"), {}).get(parent_lib, "")
        if row.get("code") != code or row.get("name") != name:
            changed += 1
        row["code"] = code
        row["name"] = name
        row["level"] = level
        row["parent_ID"] = parent_id
        row["costNature"] = nature
        row["allocBasis"] = ALLOC_BASIS.get(code, "")

    write("prj-CBSInstance", fields, rows)
    return changed, minted, len(rows)


def main():
    kept, minted, moved = rebuild_library()
    changed, instantiated, total = rebuild_instances()

    print("  Library: %d node(s) kept their key, %d new" % (kept, minted))
    if moved:
        print("  Moved:")
        for line in moved:
            print("    %s" % line)
    print("  Project breakdowns: %d row(s) recoded, %d node(s) instantiated, "
          "%d total" % (changed, instantiated, total))
    if CHECK:
        print("\n  --check: nothing written.")


main()
