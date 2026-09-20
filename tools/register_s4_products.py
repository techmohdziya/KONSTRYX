"""Registers each resource against the product S/4 will order it as.

A purchase requisition is keyed on a product number. KONSTRYX can plan, budget
and cost a resource by its own code, and the moment it asks S/4 to buy one it
has to name something S/4 recognises — which is why the push refused every line
with "nothing registered in S/4 to order against". The resources were right and
the registration was simply absent.

Two kinds, because S/4 treats them differently and so does the requisition:

  a MATERIAL is bought. Cement, rebar, aggregate, ready-mix: the same item from
  any vendor is the same product, which is what makes one registration per
  resource correct.

  a SERVICE PRODUCT is hired or subcontracted. A tower crane with an operator
  and a labour-supply carpenter are not stock; a requisition for them is raised
  before a vendor exists, so it names a generic service rather than a priced
  item.

The codes below are the ones in the connected tenant (my434396), matched by
what the item actually is rather than by any pattern in the code — a rebar
resource registered against a cement product would push cleanly and order the
wrong thing.

Codes rather than keys. A mirror row's key is generated on read, so an
association stored against it stops resolving the next time the catalogue is
read; the connector resolves these codes into associations after every sync.
"""
import csv
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "test", "data", "konstryx.master-ResourceNode.csv")

# resource code -> (s4 material code, s4 service product code)
REGISTRATIONS = {
    # -- bought ---------------------------------------------------------------
    "MAT-CEM-OPC53-50":    ("100023451", ""),   # Cement OPC 53, 50 kg bag
    "MAT-AGG-20MM":        ("100023870", ""),   # Crushed aggregate 20 mm
    "MAT-SND-ADMX":        ("100023880", ""),   # Washed M-sand
    "MAT-CON-RMC-M40-001": ("100024110", ""),   # RMC M40
    "MAT-CON-RMC-M50-001": ("100024112", ""),   # RMC M50
    "MT-RMC-C40-20":       ("100024110", ""),   # Ready-mix C40/20 is the M40 mix
    "MT-REB-12":           ("100024522", ""),   # TMT Rebar Fe500D 12 mm
    "MT-REB-16":           ("100024524", ""),   # TMT Rebar Fe500D 16 mm

    # -- hired or supplied ----------------------------------------------------
    "EQ-TWC-12T":          ("", "SVC-EQ-TWC-12T"),
    "EQ-MBC-50T":          ("", "SVC-EQ-MOC-50T"),
    "MP-CIV-CAR-SK-G1":    ("", "SVC-LAB-CAR-SK-G1-AC"),
    "MP-CIV-STF-SK-G1":    ("", "SVC-LAB-STF-G1"),
}


def main():
    with io.open(PATH, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        fields = list(reader.fieldnames)
        rows = [dict(row) for row in reader]

    for column in ("s4MaterialCode", "s4ServiceProductCode"):
        if column not in fields:
            # Placed beside the associations they resolve into, not appended at
            # the end, so the two read together.
            fields.insert(fields.index("s4Material_ID"), column)
            for row in rows:
                row.setdefault(column, "")

    applied, missing = 0, set(REGISTRATIONS)
    for row in rows:
        registration = REGISTRATIONS.get(row["code"])
        if not registration:
            continue
        missing.discard(row["code"])
        row["s4MaterialCode"], row["s4ServiceProductCode"] = registration
        applied += 1

    with io.open(PATH, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";",
                                extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({f: row.get(f, "") for f in fields})

    print("  %d resource(s) registered against an S/4 product" % applied)
    if missing:
        # Never silent: a registration that matched no resource is a typo in
        # this file, and the only symptom would be a requisition line refusing
        # to push for a reason that looks like a data problem elsewhere.
        print("  No resource has these codes: %s" % ", ".join(sorted(missing)))


main()
