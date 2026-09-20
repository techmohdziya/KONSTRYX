/**
 * KONSTRYX — konstryx.bud (Data Model Spec §5)
 * Budget header/lines, mobilization auth, approvals, availability log.
 */
namespace konstryx.bud;

using { cuid, managed } from '@sap/cds/common';
using { konstryx.common } from './common';
using { konstryx.prj } from './prj';
using { konstryx.fin } from './fin';

entity Budget : cuid, managed, common.documented {
  // status: Draft -> Submitted -> Approved -> Baselined -> Locked
  version     : String(10);
  daysToLock  : Integer;
  totalAmount : Decimal(15,2);
  lines       : Composition of many BudgetLine on lines.budget = $self;
  approvals   : Composition of many BudgetApproval on approvals.budget = $self;
}

// The control record: budget vs committed/encumbered/actual.
entity BudgetLine : cuid {
  budget     : Association to Budget;
  /**
   * The three questions a budget line has to answer at once: what work it pays
   * for, who builds it, and what absorbs the cost.
   *
   * A line that names only its CBS says what kind of cost it is and nothing
   * about where that cost is incurred. Allocation already joins the bill line
   * to a WBS element and a CBS node, so the budget is generated over that join
   * rather than over the CBS alone — which is also what lets a line be phased
   * from the activities under its own WBS instead of spread flat.
   *
   * Any of the three may be empty on a line that genuinely has no counterpart:
   * preliminaries are carried by the project, not by a bill item, and are left
   * blank rather than attached to an arbitrary one.
   */
  wbs        : Association to prj.WBSElement;
  cbs        : Association to prj.CBSInstance;
  boqItem    : Association to prj.BOQItem;
  /**
   * Cost nature — one of the six verticals (MR, MPR, EQR, VR, SF, SC), carried
   * from the resource build-up the line was generated from. Six, not four: the
   * four-way taxonomy is the movement ledger below, computed from ledger
   * entries, and the two must never be conflated.
   */
  category   : String(10);
  amount     : Decimal(15,2);
  authorised : Decimal(15,2);
  committed  : Decimal(15,2);     // S/4 PO/SO
  encumbered : Decimal(15,2);     // Konstryx RES
  actual     : Decimal(15,2);     // S/4 FI
  available  : Decimal(15,2);     // amount - committed - encumbered - actual
  availPct   : Decimal(5,2);
  usedPct    : Decimal(5,2);
  eac        : Decimal(15,2);
  eacMargin  : Decimal(15,2);
  costRate   : Decimal(15,2);
  costDelta  : Decimal(15,2);
  /**
   * When this line is expected to be spent.
   *
   * A budget line knew its amount and its CBS and nothing said which month
   * that amount was meant to go out in — which is why planned value, the
   * schedule index and the cashflow curve were all missing at once. They are
   * the same missing fact asked three ways.
   */
  phases     : Composition of many BudgetPhase on phases.line = $self;
}

/**
 * One month of one budget line: what it is expected to cost, and when.
 *
 * Derived, never keyed. A phase is produced by spreading a line across the
 * periods its work actually falls in, and re-phasing replaces the set rather
 * than adding to it — a hand-edited phase would be a figure nobody could
 * reconcile against either the line above it or the programme behind it.
 *
 * The period is a fiscal period, not a month string, for the same reason the
 * period report's is: a cashflow bucket, a certificate and a CVR that end
 * their month on different days cannot be reconciled against each other.
 */
entity BudgetPhase : cuid {
  line       : Association to BudgetLine;
  /** Denormalised so a curve can be read for a project without a join. */
  project    : Association to prj.Project;
  budget     : Association to Budget;
  period     : Association to fin.FiscalPeriod;
  periodName : String(40);
  /** The period's own start, so a series sorts without resolving the period. */
  startDate  : Date;
  amount     : Decimal(15,2);
  /**
   * How the share was decided.
   *
   * PROGRAMME  the line's CBS is mapped to WBS elements that carry activities,
   *            and the amount follows those activities' working days.
   * ENVELOPE   nothing maps it to any dated work, so it is spread evenly
   *            across the project's own dates. Flagged rather than silent: a
   *            curve built from envelopes is a straight line pretending to be
   *            a forecast, and the reader has to know which lines are which.
   */
  basis      : String(12) enum { PROGRAMME; ENVELOPE; };
}

/**
 * The movement ledger (KX-BUD-004): every dirham of budget movement is one
 * ledger entry in exactly one of four categories. A line's amount is never
 * edited after baseline — it is the sum of its ledger entries, and the ledger
 * is the answer to "how did this number become this number".
 */
entity BudgetLedgerEntry : cuid, managed {
  budget    : Association to Budget;
  line      : Association to BudgetLine;
  category  : String enum { ORIGINAL; SHIFT; RISK_TRANSFER; VARIATION; };
  /** Signed. A shift is two entries that sum to zero across its two lines. */
  amount    : Decimal(15,2);
  reference : String(40);      // the document that caused the movement
  reason    : String(500);
  /** Pairs the two sides of a shift so neither can be read alone. */
  pairKey   : String(36);
}

entity MobilizationAuth : cuid, managed, common.documented {
  amount     : Decimal(15,2);
  validTo    : Date;
  approvedBy : String(120);
  approvedOn : Date;
  spend      : Composition of many PreBaselineSpend on spend.ma = $self;
}

entity PreBaselineSpend : cuid, managed {
  project : Association to prj.Project;
  ma      : Association to MobilizationAuth;
  amount  : Decimal(15,2);
  spendDate : Date;
  doc     : String(40);
}

entity BudgetApproval : cuid, managed {
  budget       : Association to Budget;
  step         : Integer;
  approverRole : String(60);
  approvedBy   : String(120);
  approvedOn   : DateTime;
  decision     : String(20);
  comment      : String(500);
}

entity AvailabilityLog : cuid, managed {
  budget        : Association to Budget;
  line          : Association to BudgetLine;
  checkedAmount : Decimal(15,2);
  result        : String(20);    // PASS / FAIL / WARN
  checkedOn     : DateTime;
  sourceDoc     : String(40);
}
