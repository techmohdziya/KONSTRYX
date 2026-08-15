/**
 * KONSTRYX — konstryx.bud (Data Model Spec §5)
 * Budget header/lines, mobilization auth, approvals, availability log.
 */
namespace konstryx.bud;

using { cuid, managed } from '@sap/cds/common';
using { konstryx.common } from './common';
using { konstryx.prj } from './prj';

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
