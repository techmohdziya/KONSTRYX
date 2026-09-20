/**
 * KONSTRYX — konstryx.vo
 * Variation orders: what changed after the contract was signed, what the client
 * pays for it, and what it costs to do.
 */
namespace konstryx.vo;

using { cuid, managed, Currency } from '@sap/cds/common';
using { konstryx.common } from './common';
using { konstryx.prj } from './prj';

/**
 * A change to the contracted scope, priced.
 *
 * Until now the cost value reconciliation reported variations as zero and said
 * so in its own note, because there was nowhere to record one. That is not a
 * cosmetic gap: on a construction job the variation account is routinely a
 * tenth of the contract and occasionally more than the margin, so a CVR without
 * it reports a project that has not changed since the day it was signed — which
 * describes no project.
 *
 * Two amounts, never one. A variation earns revenue at the rate agreed with the
 * client and costs whatever it costs to build, and the two are different
 * questions with different answers: a remeasure at contract rates can add
 * revenue and lose money. Collapsing them into a single "value" is how a
 * variation account grows while the margin shrinks and nobody sees it happen.
 *
 * Only APPROVED variations reach the reconciliation. A submitted claim is a
 * negotiating position, and counting it as revenue is how a forecast comes to
 * depend on a conversation nobody has had yet.
 */
entity VariationOrder : cuid, managed, common.documented {
  /**
   * The client's own reference for the change — their instruction or VO
   * number. Carried rather than derived, because it is the number both sides
   * argue from and it is not ours to issue.
   */
  clientRef      : String(40);
  title          : String(255);
  /** The bill this varies. A variation always varies a priced document. */
  boq            : Association to prj.BOQ;

  /**
   * Why the change happened, which decides who pays for it.
   *
   * CLIENT_INSTRUCTION and DESIGN_CHANGE are recoverable; SITE_CONDITION
   * usually is, subject to the contract; ERROR_OMISSION is the contractor's
   * own and is recorded so the cost lands somewhere honest rather than being
   * quietly folded into a claim that will not survive scrutiny.
   */
  origin         : String(20) enum {
    CLIENT_INSTRUCTION; DESIGN_CHANGE; SITE_CONDITION; ERROR_OMISSION;
  };
  instructionRef : String(60);
  instructedOn   : Date;
  submittedOn    : Date;
  decidedOn      : Date;
  decidedBy      : String(120);
  /** Why it was rejected, or what the approval was conditional on. */
  decisionNote   : String(500);

  ccy            : Currency;

  // ------------------------------------------------------------- the money
  //
  // All three are DERIVED from the lines by recalculate. They are stored so a
  // list can be read without expanding every variation, and recomputed rather
  // than typed for the same reason the certificate's net is: a header figure
  // that disagrees with its own lines is the defect this product exists to
  // prevent.

  /** What the client pays. */
  revenueAmount  : Decimal(15,2);
  /** What it costs to build. */
  costAmount     : Decimal(15,2);
  marginAmount   : Decimal(15,2);
  marginPct      : Decimal(9,2);

  /**
   * Days of extension of time this change carries.
   *
   * On the variation rather than in a note, because time and money are claimed
   * together and settled together — a variation approved for its cost and
   * silent on its delay is the one that turns into a liquidated damages
   * argument later.
   */
  timeExtensionDays : Integer default 0;

  lines          : Composition of many VariationLine on lines.variation = $self;
}

/**
 * One changed item: what it does to the bill, in quantity and in money.
 *
 * A line names the bill item it varies where it varies one. Genuinely new
 * scope names none — that is what an ADD with no bill item means — and the
 * distinction matters at settlement, because a remeasure is argued at
 * contract rates and new scope is argued at whatever was agreed for it.
 */
entity VariationLine : cuid {
  variation   : Association to VariationOrder;
  lineNo      : Integer;
  /** The bill line this changes. Null where the change is new scope. */
  boqItem     : Association to prj.BOQItem;
  /**
   * ADD        new work, or more of the same
   * OMIT       work taken out; quantity is entered positive and deducts
   * REMEASURE  the quantity was wrong; this is the difference, either way
   * RATE_CHANGE the quantity stands and the rate does not
   */
  changeType  : String(12) enum { ADD; OMIT; REMEASURE; RATE_CHANGE; };
  description : String(500);

  qty         : Decimal(15,3);
  uom         : String(10);
  /** The rate the client is charged. */
  revenueRate : Decimal(15,2);
  /** What it costs to do, per unit. Not the same question. */
  costRate    : Decimal(15,2);
  revenueAmount : Decimal(15,2);
  costAmount    : Decimal(15,2);

  /** Where the work is built, and which cost node absorbs it. */
  wbs         : Association to prj.WBSElement;
  cbs         : Association to prj.CBSInstance;
}
