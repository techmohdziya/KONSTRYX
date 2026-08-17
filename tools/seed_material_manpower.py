#!/usr/bin/env python3
"""Adds the material (MR) and manpower (MPR) demo threads to the fixtures.

Why this exists
---------------
Until now the demo showed one vertical. RR-2026-0188 had five equipment lines,
an advisory decision each, an availability check and a reservation; the other
four request headers were empty shells, and there was exactly one of every
downstream document. So the app demonstrated equipment and asserted nothing
about the two verticals that carry most of a contractor's cost.

Every figure here comes from KONSTRYX_Wireframe_v12, not from judgement:

  material  modules/material-inhouse.html    — RR-2026-0148, five stock lines
  manpower  modules/manpower-inhouse.html    — RR-2026-0162, five trade lines,
                                               plus the 14 Aug daily timesheet
  trades    modules/manpower-masters.html    — MP-* codes, in-house and LSC rates
  trades    modules/workforce-masters.html   — trade catalogue rates (TRD-*)
  vendors   modules/manpower-masters.html    — LSC labour suppliers + S/4 BPs

One wireframe arithmetic slip is corrected rather than copied — see MR line 1
below. This is the same class of defect as Q-05, where the request header said
716,044 while its own lines summed to 685,080.

Idempotent: a row whose ID is already present is left alone, so re-running after
editing a value changes nothing. Regenerate the content packs afterwards.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST = ROOT / "test" / "data"
DBD = ROOT / "db" / "data"

# ---------------------------------------------------------------- id builder
# Reusing the fixtures' own convention: one two-hex prefix per entity, so a UUID
# is readable at a glance and a foreign key can be checked by eye.
#
# Built through one helper rather than per-entity format strings. The first
# attempt used a literal template per entity and got the zero-padding wrong in
# six of them, emitting 35- and 38-character ids. H2 stores a UUID column as a
# string and accepted them without complaint, so nothing failed at insert —
# instead six unrelated suites crashed later on empty reads, because a malformed
# id matches nothing and a lookup silently returns no rows. Compute the padding;
# never hand-count zeros.
def uid(prefix: str, suffix: str) -> str:
    """A canonical UUID: 8-4-4-4-12, with `suffix` right-aligned in the last group."""
    if len(prefix) != 2 or len(suffix) > 12:
        raise SystemExit(f"bad id parts: prefix={prefix!r} suffix={suffix!r}")
    return f"{prefix}000000-0000-0000-0000-{suffix.rjust(12, '0')}"


MODULE = uid("70", "8")
AO_MANPOWER = uid("71", "41")
AO_TIMESHEET = uid("71", "42")

# existing rows referenced
PRJ1 = "30000000-0000-0000-0000-000000000001"
INFC = "20000000-0000-0000-0000-000000000001"
WBS_102 = "31000000-0000-0000-0000-000000000102"
WBS_103 = uid("31", "103")
CBS_0310 = "32000000-0000-0000-0000-000000000310"
CBS_0320 = "32000000-0000-0000-0000-000000000320"
CBS_L1_02 = "41000000-0000-0000-0000-000000000003"      # library L1 "02" super-structure
RR_0148 = "50000000-0000-0000-0000-000000000148"
RR_0162 = "50000000-0000-0000-0000-000000000162"
MT_REBAR_HT = "4B000000-0000-0000-0000-000000000032"
MT_STEEL = "4B000000-0000-0000-0000-000000000012"
MT_REB_16 = "4B000000-0000-0000-0000-000000000042"
MP = "4C000000-0000-0000-0000-000000000001"
MP_CIV = "4C000000-0000-0000-0000-000000000002"
CAR_G1 = "4C000000-0000-0000-0000-000000000005"
HLP_G1 = "4C000000-0000-0000-0000-00000000000B"
CEM_BAG = "4C000000-0000-0000-0000-000000000016"
PERSONA_SITE = "72000000-0000-0000-0000-000000000001"
PERSONA_COORD = "72000000-0000-0000-0000-000000000004"
PERSONA_DEMO = "72000000-0000-0000-0000-000000000009"

# new resource nodes
STF_L3 = "4C000000-0000-0000-0000-000000000020"
STF_L4 = "4C000000-0000-0000-0000-000000000021"
STF_G1 = "4C000000-0000-0000-0000-000000000022"
MEP_L2 = "4C000000-0000-0000-0000-000000000023"
ELE_L3 = "4C000000-0000-0000-0000-000000000024"
ELE_L4 = "4C000000-0000-0000-0000-000000000025"
ELE_G1 = "4C000000-0000-0000-0000-000000000026"
REB_12 = "4B000000-0000-0000-0000-000000000043"
ACC_L3 = "4B000000-0000-0000-0000-000000000044"
BWR_L4 = "4B000000-0000-0000-0000-000000000045"
BWR_G1 = "4B000000-0000-0000-0000-000000000046"
CHR_L4 = "4B000000-0000-0000-0000-000000000047"
CHR_50 = "4B000000-0000-0000-0000-000000000048"
VND_ALPHA = "60000000-0000-0000-0000-000000000004"
VND_DELTA = "60000000-0000-0000-0000-000000000005"

SYNC = ["S4HC_100", "2026-08-22T06:00:00Z", "SENT", "", "0"]

# --------------------------------------------------------------------- rows
# Each block is (relative csv path, [row dicts]). Keys must match the header
# already in the file; anything absent is written empty.

ADDITIONS: list[tuple[Path, list[dict]]] = []


def add(path: Path, rows: list[dict]) -> None:
    ADDITIONS.append((path, rows))


# -- 1. masters: the trades and materials the canonical lines actually name ---
# Five of the ten wireframe lines referenced codes the hierarchy did not have.
# Intermediate L2-L4 nodes are created so every new L5 sits under a real branch
# rather than dangling — the hierarchy is L1..L5 and the UI walks it.
add(TEST / "konstryx.master-ResourceNode.csv", [
    # steel fixing: the largest single manpower line in the demo
    dict(ID=STF_L3, code="MP-CIV-STF", level="L3", parent_ID=MP_CIV, verticalType="MPR",
         description="Steel fixing", scope="GROUP", masterStatus="ACTIVE"),
    dict(ID=STF_L4, code="MP-CIV-STF-SK", level="L4", parent_ID=STF_L3, verticalType="MPR",
         description="Steel fixer - skilled", scope="GROUP", masterStatus="ACTIVE"),
    dict(ID=STF_G1, code="MP-CIV-STF-SK-G1", level="L5", parent_ID=STF_L4, verticalType="MPR",
         description="Steel Fixer skilled grade 1", consUoM="hr", scope="GROUP",
         masterStatus="ACTIVE"),
    # MEP trades: a second branch under MP, so manpower is not civil-only
    dict(ID=MEP_L2, code="MP-MEP", level="L2", parent_ID=MP, verticalType="MPR",
         description="MEP trades", scope="GROUP", masterStatus="ACTIVE"),
    dict(ID=ELE_L3, code="MP-MEP-ELE", level="L3", parent_ID=MEP_L2, verticalType="MPR",
         description="Electrical", scope="GROUP", masterStatus="ACTIVE"),
    dict(ID=ELE_L4, code="MP-MEP-ELE-SK", level="L4", parent_ID=ELE_L3, verticalType="MPR",
         description="Electrician - skilled", scope="GROUP", masterStatus="ACTIVE"),
    dict(ID=ELE_G1, code="MP-MEP-ELE-SK-G1", level="L5", parent_ID=ELE_L4, verticalType="MPR",
         description="Electrician skilled grade 1", consUoM="hr", scope="GROUP",
         masterStatus="ACTIVE"),
    # rebar 12 mm sits beside the existing 16 mm under high-tensile BS4449
    dict(ID=REB_12, code="MT-REB-12", level="L5", parent_ID=MT_REBAR_HT, verticalType="MR",
         description="Rebar 12 mm BS4449", consUoM="t", scope="GROUP", masterStatus="ACTIVE"),
    # rebar accessories: consumables that ride with every rebar pour
    dict(ID=ACC_L3, code="MT-STL-ACC", level="L3", parent_ID=MT_STEEL, verticalType="MR",
         description="Rebar accessories", scope="GROUP", masterStatus="ACTIVE"),
    dict(ID=BWR_L4, code="MT-STL-ACC-BWR", level="L4", parent_ID=ACC_L3, verticalType="MR",
         description="Binding wire", scope="GROUP", masterStatus="ACTIVE"),
    dict(ID=BWR_G1, code="MAT-BWR-18SWG", level="L5", parent_ID=BWR_L4, verticalType="MR",
         description="Binding wire 18 SWG", consUoM="kg", scope="GROUP", masterStatus="ACTIVE"),
    dict(ID=CHR_L4, code="MT-STL-ACC-CHR", level="L4", parent_ID=ACC_L3, verticalType="MR",
         description="Rebar chairs & spacers", scope="GROUP", masterStatus="ACTIVE"),
    dict(ID=CHR_50, code="MAT-RBC-50", level="L5", parent_ID=CHR_L4, verticalType="MR",
         description="Rebar chairs 50 mm", consUoM="pc", scope="GROUP", masterStatus="ACTIVE"),
])

# Rates. Manpower hourly rates are the wireframe's in-house figures from
# manpower-masters.html; the electrician comes from the trade catalogue
# (TRD-007, AED 42.00/hr). Material rates are the per-unit rates implied by the
# request's own encumbrance.
add(TEST / "konstryx.master-RateMaster.csv", [
    dict(ID=uid("42", "120"), resource_ID=STF_G1, rateValue="26.00", basis="hr",
         ccy_code="AED", netRate="26.00", effectiveFrom="2026-01-01", scope="GROUP",
         masterStatus="ACTIVE"),
    dict(ID=uid("42", "121"), resource_ID=CAR_G1, rateValue="28.50", basis="hr",
         ccy_code="AED", netRate="28.50", effectiveFrom="2026-01-01", scope="GROUP",
         masterStatus="ACTIVE"),
    dict(ID=uid("42", "122"), resource_ID=ELE_G1, rateValue="42.00", basis="hr",
         ccy_code="AED", netRate="42.00", effectiveFrom="2026-01-01", scope="GROUP",
         masterStatus="ACTIVE"),
    dict(ID=uid("42", "123"), resource_ID=MT_REB_16, rateValue="3422.00", basis="unit",
         ccy_code="AED", netRate="3422.00", effectiveFrom="2026-01-01", scope="GROUP",
         masterStatus="ACTIVE"),
    dict(ID=uid("42", "124"), resource_ID=REB_12, rateValue="3400.00", basis="unit",
         ccy_code="AED", netRate="3400.00", effectiveFrom="2026-01-01", scope="GROUP",
         masterStatus="ACTIVE"),
    dict(ID=uid("42", "125"), resource_ID=BWR_G1, rateValue="9.00", basis="unit",
         ccy_code="AED", netRate="9.00", effectiveFrom="2026-01-01", scope="GROUP",
         masterStatus="ACTIVE"),
    dict(ID=uid("42", "126"), resource_ID=CHR_50, rateValue="1.50", basis="unit",
         ccy_code="AED", netRate="1.50", effectiveFrom="2026-01-01", scope="GROUP",
         masterStatus="ACTIVE"),
])

# LSC labour suppliers. Mirrored from S/4 like the plant vendors already seeded;
# the wireframe's "BP-S4-200044" is normalised to the 10-digit BP number the
# existing rows use.
add(TEST / "konstryx.master-Vendor.csv", [
    dict(ID=VND_ALPHA, bpNumber="0002000044", name="Alpha Civil LLC", purchOrgs="1000",
         paymentTerms="NT30", hseCert="ISO 45001", status="ACTIVE", s4Key="0002000044",
         s4System="S4HC_100", lastSyncedAt="2026-08-22T06:00:00Z", syncStatus="OK"),
    dict(ID=VND_DELTA, bpNumber="0002000158", name="Delta Manpower Co.", purchOrgs="1000",
         paymentTerms="NT45", hseCert="ISO 45001", status="ACTIVE", s4Key="0002000158",
         s4System="S4HC_100", lastSyncedAt="2026-08-22T06:00:00Z", syncStatus="OK"),
])

# -- 2. structure: the WBS and CBS the manpower hours post to -----------------
# The manpower thread charges a finer super-structure breakdown than the seeded
# library carried (02.30/.35/.40/.50/.60), and the electrician sits on WBS-1.03.
add(TEST / "konstryx.prj-WBSElement.csv", [
    dict(ID=WBS_103, code="WBS-1.03", project_ID=PRJ1, activityType="EQ-MEP",
         description="MEP First Fix", s4Key="PRJ-001.1.03", s4System="S4HC_100",
         lastSyncedAt="2026-08-22T06:00:00Z", syncStatus="SENT", syncAttempts="0"),
])

CBS_LIB = [
    ("0040", "02.30", "Raft & pile cap RCC"),
    ("0041", "02.35", "Raft & pile cap RCC - subcontracted"),
    ("0042", "02.40", "Formwork - super-structure"),
    ("0043", "02.50", "MEP first fix"),
    ("0044", "02.60", "Blockwork & masonry"),
]
add(TEST / "konstryx.master-CBSNode.csv", [
    dict(ID=uid("41", sfx.lstrip("0")), code=code, level="L2", parent_ID=CBS_L1_02,
         constructionType="High-rise", phase=phase, scope="GROUP", masterStatus="ACTIVE")
    for sfx, code, phase in CBS_LIB
])
add(TEST / "konstryx.prj-CBSInstance.csv", [
    dict(ID=uid("32", code.replace(".", "").lstrip("0")), code=code, project_ID=PRJ1,
         libraryNode_ID=uid("41", sfx.lstrip("0")), budgetAmount="0.00", level="L2")
    for sfx, code, _ in CBS_LIB
])
CBS_OF = {code: uid("32", code.replace(".", "").lstrip("0")) for _, code, _ in CBS_LIB}

# -- 3. the material thread: RR-2026-0148 ------------------------------------
# material-inhouse.html, "Reserved / Encumbered AED" table.
#
# Line 1 is the one correction: the wireframe states 280,640 for 82.0 t, but
# 82.0 x 3,422.00 = 280,604, and every other line multiplies out exactly. A
# 640/604 transposition in one cell is far likelier than a rate nobody can
# state, so the arithmetic is kept and the total becomes 378,404 rather than the
# stated 378,440. Flagged rather than silently absorbed.
MR_LINES = [
    # lineNo, resource, description, qty, uom, cbs code, unit rate, total, status, decision, avc result
    (1, MT_REB_16, "Rebar 16 mm dom - stock + GR", "82.000", "t", CBS_0310,
     "3422.00", "280604.00", "Awaiting balance GR", "IN_HOUSE",
     "Partial - 11.4 t of 82.0 t from stock"),
    (2, REB_12, "Rebar 12 mm BS4449", "24.000", "t", CBS_0310,
     "3400.00", "81600.00", "PO in transit", "PROCURE", "No stock - PO raised"),
    (3, CEM_BAG, "Cement OPC 53 grade 50 kg", "400.000", "bag", CBS_0320,
     "18.00", "7200.00", "Awaiting balance GR", "PROCURE", "200 of 400 bags received"),
    (4, BWR_G1, "Binding wire 18 SWG", "800.000", "kg", CBS_0310,
     "9.00", "7200.00", "Closed", "IN_HOUSE", "Available - SLoc 1020"),
    (5, CHR_50, "Rebar chairs 50 mm", "1200.000", "pc", CBS_0310,
     "1.50", "1800.00", "Closed", "IN_HOUSE", "Available - SLoc 1010"),
]

# consumed-to-date, from the consumption table in the same module
MR_CONSUMED = {1: "51.000", 2: "0.000", 3: "200.000", 4: "760.000", 5: "1180.000"}

add(TEST / "konstryx.wf-ResourceRequestLine.csv", [
    dict(ID=uid("51", str(140 + n)), parent_ID=RR_0148, lineNo=str(n), resource_ID=res,
         description=desc, qty=qty, uom=uom, wbs_ID=WBS_102, cbs_ID=cbs,
         estUnitCost=rate, estTotal=total, needBy="2026-05-18", lineStatus=status,
         advisory_ID=uid("52", str(140 + n)), avcResult_ID=uid("54", str(140 + n)))
    for n, res, desc, qty, uom, cbs, rate, total, status, _, _ in MR_LINES
])
add(TEST / "konstryx.wf-AdvisoryDecision.csv", [
    dict(ID=uid("52", str(140 + n)), rr_ID=RR_0148, line_ID=uid("51", str(140 + n)),
         decision=dec, decidedBy="Material Planning Desk", decidedOn="2026-05-06T09:00:00Z",
         rationale=rat)
    for n, _, _, _, _, _, _, _, _, dec, rat in MR_LINES
])
add(TEST / "konstryx.wf-AvailabilityCheck.csv", [
    dict(ID=uid("53", "148"), docNo="AVC-2026-0148", rr_ID=RR_0148, project_ID=PRJ1,
         company_ID=INFC, status="Cleared", raisedBy="Jin Lee - Material Buyer",
         raisedOn="2026-05-08"),
])
MR_AVC = {1: ("11.400", "11.400", "82.000", "SLOC-1010", "Partial - balance on PO"),
          2: ("0.000", "0.000", "24.000", "SLOC-1010", "No stock - GR expected 22 May"),
          3: ("200.000", "200.000", "400.000", "SLOC-1030", "200 of 400 bags received"),
          4: ("800.000", "800.000", "800.000", "SLOC-1020", "Available in full"),
          5: ("1200.000", "1200.000", "1200.000", "SLOC-1010", "Available in full")}
add(TEST / "konstryx.wf-AvailabilityCheckLine.csv", [
    dict(ID=uid("54", str(140 + n)), parent_ID=uid("53", "148"),
         rrLine_ID=uid("51", str(140 + n)), atpQty=atp, stockQty=stock,
         expectedQty=exp, storageLoc=loc, result=res)
    for n, (atp, stock, exp, loc, res) in MR_AVC.items()
])
add(TEST / "konstryx.wf-Reservation.csv", [
    dict(ID=uid("55", "148"), docNo="RES-2026-0148", rr_ID=RR_0148,
         executionFlow="PROCUREMENT", project_ID=PRJ1, company_ID=INFC, status="Active",
         raisedBy="Jin Lee - Material Buyer", raisedOn="2026-05-12"),
])
add(TEST / "konstryx.wf-ReservationLine.csv", [
    dict(ID=uid("56", str(140 + n)), reservation_ID=uid("55", "148"),
         rrLine_ID=uid("51", str(140 + n)), resource_ID=res, qty=qty, uom=uom,
         dailyRate=rate, encumberedAmount=total, consumedToDate=MR_CONSUMED[n],
         burnPct=f"{100 * float(MR_CONSUMED[n]) / float(qty):.2f}",
         costToDate=f"{float(rate) * float(MR_CONSUMED[n]):.2f}", drift="0.00",
         lineStatus=status)
    for n, res, _, qty, uom, _, rate, total, status, _, _ in MR_LINES
])

# -- 4. the manpower thread: RR-2026-0162 ------------------------------------
# manpower-inhouse.html closure table: heads x days x all-in rate per head-day.
# Every line multiplies out exactly, and the five sum to the wireframe's stated
# aggregate of 837,380.
MPR_LINES = [
    # n, resource, description, heads, cbs, ratePerHeadDay, days, total, status,
    # decision, rationale, sourceType, vendor, crew, lead, mob, demob, wbs
    (1, STF_G1, "Steel Fixer G1 - own crews GNG-A/B", 8, "02.30", "520.00", 100,
     "416000.00", "Mobilized", "IN_HOUSE", "Own payroll - 8 heads inducted",
     "OWN", "", "GNG-2026-A", "Mahmoud Khan", "2026-05-14", "2026-08-22", WBS_102),
    (2, STF_G1, "Steel Fixer G1 - LSC Alpha Civil", 4, "02.35", "654.45", 100,
     "261780.00", "Mobilized", "PROCURE", "LSC top-up under PO-LSC-2026-0102",
     "LSC", VND_ALPHA, "GNG-2026-C", "Mr Selvam", "2026-05-14", "2026-08-22", WBS_102),
    (3, CAR_G1, "Carpenter Formwork - own GNG-D", 6, "02.40", "280.00", 65,
     "109200.00", "Closed", "IN_HOUSE", "Own payroll - formwork gang",
     "OWN", "", "GNG-2026-D", "F. Sanjay", "2026-05-20", "2026-07-23", WBS_102),
    (4, ELE_G1, "Electrician site-level - floating", 2, "02.50", "320.00", 45,
     "28800.00", "Closed", "IN_HOUSE", "Own payroll - floating assignment",
     "OWN", "", "", "", "2026-05-20", "2026-07-15", WBS_103),
    (5, HLP_G1, "Mason/Helper - LSC Delta Manpower", 4, "02.60", "180.00", 30,
     "21600.00", "Closed", "PROCURE", "LSC - specialist supplier, 14-day mob",
     "LSC", VND_DELTA, "GNG-2026-M", "Mr Iqbal", "2026-05-14", "2026-06-13", WBS_102),
]

add(TEST / "konstryx.wf-ResourceRequestLine.csv", [
    dict(ID=uid("51", str(160 + n)), parent_ID=RR_0162, lineNo=str(n), resource_ID=res,
         description=desc, qty=f"{heads}.000", uom="head", wbs_ID=wbs, cbs_ID=CBS_OF[cbs],
         estUnitCost=rate, estTotal=total, needBy="2026-05-14", lineStatus=status,
         advisory_ID=uid("52", str(160 + n)), avcResult_ID=uid("54", str(160 + n)))
    for (n, res, desc, heads, cbs, rate, days, total, status, dec, rat, src, vnd,
         crew, lead, mob, demob, wbs) in MPR_LINES
])
add(TEST / "konstryx.wf-AdvisoryDecision.csv", [
    dict(ID=uid("52", str(160 + n)), rr_ID=RR_0162, line_ID=uid("51", str(160 + n)),
         decision=dec, decidedBy="Manpower Allocation Committee",
         decidedOn="2026-05-04T10:00:00Z", rationale=rat)
    for (n, res, desc, heads, cbs, rate, days, total, status, dec, rat, src, vnd,
         crew, lead, mob, demob, wbs) in MPR_LINES
])
add(TEST / "konstryx.wf-AvailabilityCheck.csv", [
    dict(ID=uid("53", "162"), docNo="AVC-2026-0162", rr_ID=RR_0162, project_ID=PRJ1,
         company_ID=INFC, status="Cleared", raisedBy="R. Sundaram - Manpower Coordinator",
         raisedOn="2026-05-10"),
])
add(TEST / "konstryx.wf-AvailabilityCheckLine.csv", [
    dict(ID=uid("54", str(160 + n)), parent_ID=uid("53", "162"),
         rrLine_ID=uid("51", str(160 + n)), atpQty=f"{heads}.000",
         stockQty=(f"{heads}.000" if src == "OWN" else "0.000"),
         expectedQty=f"{heads}.000",
         storageLoc=("PAYROLL" if src == "OWN" else "LSC"),
         result=("Own pool - inducted" if src == "OWN" else "LSC - contract valid"))
    for (n, res, desc, heads, cbs, rate, days, total, status, dec, rat, src, vnd,
         crew, lead, mob, demob, wbs) in MPR_LINES
])
add(TEST / "konstryx.wf-Reservation.csv", [
    dict(ID=uid("55", "162"), docNo="RES-2026-0162", rr_ID=RR_0162,
         executionFlow="IN_HOUSE", project_ID=PRJ1, company_ID=INFC, status="Active",
         raisedBy="R. Sundaram - Manpower Coordinator", raisedOn="2026-05-11"),
])
# consumed-to-date in head-days, from the closure table's actual AED
MPR_CONSUMED = {1: ("800.000", "410000.00"), 2: ("400.000", "261780.00"),
                3: ("390.000", "108800.00"), 4: ("90.000", "28800.00"),
                5: ("120.000", "21400.00")}
add(TEST / "konstryx.wf-ReservationLine.csv", [
    dict(ID=uid("56", str(160 + n)), reservation_ID=uid("55", "162"),
         rrLine_ID=uid("51", str(160 + n)), resource_ID=res, qty=f"{heads}.000",
         uom="head", dailyRate=rate, encumberedAmount=total,
         consumedToDate=MPR_CONSUMED[n][0],
         burnPct=f"{100 * float(MPR_CONSUMED[n][1]) / float(total):.2f}",
         costToDate=MPR_CONSUMED[n][1],
         drift=f"{float(MPR_CONSUMED[n][1]) - float(total):.2f}", lineStatus=status)
    for (n, res, desc, heads, cbs, rate, days, total, status, dec, rat, src, vnd,
         crew, lead, mob, demob, wbs) in MPR_LINES
])

# The manpower vertical extension: what the spine cannot express.
add(TEST / "konstryx.mpr-ManpowerRequestLine.csv", [
    dict(ID=uid("58", str(160 + n)), line_ID=uid("51", str(160 + n)),
         heads=str(heads), tradeGrade=desc.split(" - ")[0], sourceType=src,
         vendor_ID=vnd, crewId=crew, crewLead=lead, mobDate=mob, demobDate=demob,
         durationDays=str(days), ratePerHeadDay=rate,
         inductionState=("All inducted - HSE + skill verified" if src == "OWN"
                         else "LSC induction on mobilization"))
    for (n, res, desc, heads, cbs, rate, days, total, status, dec, rat, src, vnd,
         crew, lead, mob, demob, wbs) in MPR_LINES
])

# One canonical day of the daily log — manpower-inhouse.html, 14 Aug: 24 heads,
# 192 regular hours, 24 overtime, AED 5,464. The activity codes are the
# wireframe's own WBS/CBS posting strings.
TIMESHEET = [
    (1, 8, "64.00", "16.00", "PRJ-001.02.30.STR-RBR", "02.30", "2288.00", WBS_102),
    (2, 4, "32.00", "8.00", "PRJ-001.02.35.STR-RBR", "02.35", "1144.00", WBS_102),
    (3, 6, "48.00", "0.00", "PRJ-001.02.40.STR-FRM", "02.40", "1056.00", WBS_102),
    (4, 2, "16.00", "0.00", "PRJ-001.02.50.MEP-1F", "02.50", "400.00", WBS_103),
    (5, 4, "32.00", "0.00", "PRJ-001.02.60.STR-CNC", "02.60", "576.00", WBS_102),
]
add(TEST / "konstryx.mpr-TimesheetEntry.csv", [
    dict(ID=uid("59", str(160 + n)), manpowerLine_ID=uid("58", str(160 + n)),
         workDate="2026-08-14", headsPresent=str(present), regularHrs=reg, otHrs=ot,
         wbs_ID=wbs, cbs_ID=CBS_OF[cbs], activity=act, costAmount=cost,
         logStatus="Signed", signedBy="Daud Patel - Site Engineer")
    for n, present, reg, ot, act, cbs, cost, wbs in TIMESHEET
])

# -- 5. authorization: the new entities must be protectable -------------------
# An entity absent from the catalogue passes through the enforcement handler
# unprotected, so a new vertical has to arrive with its objects.
add(DBD / "konstryx.auth-Module.csv", [
    dict(ID=MODULE, code="MP", name="Manpower & Workforce", sequence="55"),
])
add(DBD / "konstryx.auth-AuthObject.csv", [
    dict(ID=AO_MANPOWER, code="KX_MANPOWER_LINE", name="Manpower Request Line",
         module_ID=MODULE, entityName="konstryx.mpr.ManpowerRequestLine",
         projectScoped="true", projectPath="line.parent.project.code",
         companyPath="line.parent.company.code"),
    dict(ID=AO_TIMESHEET, code="KX_TIMESHEET", name="Timesheet", module_ID=MODULE,
         entityName="konstryx.mpr.TimesheetEntry", projectScoped="true",
         projectPath="manpowerLine.line.parent.project.code",
         companyPath="manpowerLine.line.parent.company.code"),
])
# Grants: the site engineer keys the daily log, the coordinator reads it, the
# demo persona reaches everything.
GRANTS = (
    [("0500", PERSONA_SITE, AO_MANPOWER, "03"),
     ("0501", PERSONA_SITE, AO_TIMESHEET, "01"),
     ("0502", PERSONA_SITE, AO_TIMESHEET, "02"),
     ("0503", PERSONA_SITE, AO_TIMESHEET, "03"),
     ("0504", PERSONA_COORD, AO_MANPOWER, "03"),
     ("0505", PERSONA_COORD, AO_TIMESHEET, "03")]
    + [(f"051{i}", PERSONA_DEMO, obj, act)
       for i, (obj, act) in enumerate([(AO_MANPOWER, "01"), (AO_MANPOWER, "02"),
                                       (AO_MANPOWER, "03"), (AO_TIMESHEET, "01"),
                                       (AO_TIMESHEET, "02"), (AO_TIMESHEET, "03")])]
)
add(TEST / "konstryx.auth-PersonaPermission.csv", [
    dict(ID=uid("73", sfx.lstrip("0")), persona_ID=persona, authObject_ID=obj,
         activity_code=act, granted="true")
    for sfx, persona, obj, act in GRANTS
])


# --------------------------------------------------------------------- apply
NEW_HEADERS = {
    "konstryx.mpr-ManpowerRequestLine.csv": [
        "ID", "line_ID", "heads", "tradeGrade", "sourceType", "vendor_ID", "crewId",
        "crewLead", "mobDate", "demobDate", "durationDays", "ratePerHeadDay",
        "inductionState"],
    "konstryx.mpr-TimesheetEntry.csv": [
        "ID", "manpowerLine_ID", "workDate", "headsPresent", "regularHrs", "otHrs",
        "wbs_ID", "cbs_ID", "activity", "costAmount", "logStatus", "signedBy"],
}


def apply(path: Path, rows: list[dict]) -> tuple[int, int]:
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh, delimiter=";")
            header = reader.fieldnames or []
            existing = list(reader)
    else:
        header = NEW_HEADERS[path.name]
        existing = []

    have = {r["ID"] for r in existing}
    fresh = [r for r in rows if r["ID"] not in have]
    if not fresh:
        return 0, len(rows)

    unknown = {k for r in fresh for k in r if k not in header}
    if unknown:
        raise SystemExit(f"{path.name}: columns not in header: {sorted(unknown)}")

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, delimiter=";",
                                extrasaction="ignore", quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for r in existing + [{k: r.get(k, "") for k in header} for r in fresh]:
            writer.writerow(r)
    return len(fresh), len(rows) - len(fresh)


UUID_RE = __import__("re").compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def validate() -> None:
    """Refuse to write a malformed id, in an id column or a foreign key.

    This gate exists because the first run of this script wrote 68 ids of the
    wrong length and nothing rejected them: the column is a string, the insert
    succeeded, and the damage only appeared as six unrelated suites crashing on
    reads that silently matched nothing. A bad key is not a data-quality nicety,
    it is an invisible outage.
    """
    problems = []
    for path, rows in ADDITIONS:
        for row in rows:
            for col, val in row.items():
                if (col == "ID" or col.endswith("_ID")) and val and not UUID_RE.match(val):
                    problems.append(f"{path.name}: {col} = {val!r} ({len(val)} chars)")
    if problems:
        raise SystemExit("malformed ids, nothing written:\n  "
                         + "\n  ".join(problems))


def main() -> int:
    validate()
    total_new = 0
    for path, rows in ADDITIONS:
        new, skipped = apply(path, rows)
        total_new += new
        state = f"{new} added" + (f", {skipped} already present" if skipped else "")
        print(f"  {path.name:<44} {state}")
    print(f"\n{total_new} row(s) added. Now run tools/build_content_packs.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
