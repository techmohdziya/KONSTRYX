/**
 * KONSTRYX — konstryx.bil
 * Client billing: the interim payment application and the certificate that
 * answers it. Wireframe v13, operations.html · pa-detail / pa-detail-approved
 * / pa-cert.
 *
 * The money coming in, which nothing in the model held. konstryx.scr bills the
 * subcontractor and has since the SCR rebuild; the same event on the client
 * side — measure the bill, claim it, have it certified, get paid — had no
 * entity at all, so a project could say what it owed and not what it was owed.
 *
 * Its own namespace rather than more entities on scr, because the two are
 * mirror images and not the same thing. A subcontract application is one the
 * company receives and certifies; this is one the company submits and has
 * certified against it, and the deductions, the approval chain and the
 * documents on either side belong to different contracts.
 */
namespace konstryx.bil;

using { cuid, managed, Currency } from '@sap/cds/common';
using { konstryx.common } from './common';
using { konstryx.prj } from './prj';
using { konstryx.vo } from './vo';
using { konstryx.admin } from './admin';

/**
 * One interim application: everything measured in a period, claimed at
 * contract rates.
 *
 * Kept per period and never rewritten, because it is a claim that was made on
 * a date. The next application carries what this one established rather than
 * restating it, which is what `previousApplication` is for: a chain of
 * applications is how a reader gets from the first claim to the current
 * cumulative position without re-measuring anything.
 */
entity PaymentApplication : cuid, managed, common.documented {
  // docNo is the application number, PA-C-013.
  boq            : Association to prj.BOQ;
  /** Its place in the sequence, and how many the contract expects. */
  seq            : Integer;
  seqOf          : Integer;
  periodName     : String(40);
  periodStart    : Date;
  periodEnd      : Date;
  /**
   * The application this one follows.
   *
   * The prior cumulative on every line comes from here, so a claim can be
   * read back to the one before it rather than taking the contractor's word
   * for what was claimed last time. Null on the first application, which is
   * the only one entitled to a prior of zero.
   */
  previousApplication : Association to PaymentApplication;

  /**
   * The gross at each stage it passed through, kept apart rather than
   * overwritten.
   *
   * A claim that was proposed at 2.19m, reviewed down to 2.15m and approved at
   * 2.13m has three different true answers to "what was claimed", and a single
   * column would keep whichever was written last. The difference between them
   * is what a commercial meeting is about.
   */
  proposedGross   : Decimal(15,2);
  qsReviewedGross : Decimal(15,2);
  /** What the project manager signed and sent, which is the QS's figure unless
   *  they disagreed with it. */
  submittedGross  : Decimal(15,2);
  approvedGross   : Decimal(15,2);

  // ------------------------------------------------------------ deductions
  /** Retention held this period, at the contract's own percentage. */
  retentionPct     : Decimal(5,2);
  retentionAmount  : Decimal(15,2);
  /** Advance recovered this period, and what remains outstanding after it. */
  advanceRecovery  : Decimal(15,2);
  advanceOutstanding : Decimal(15,2);
  /** What the client has set against the claim: LDs, back-charges, contra. */
  otherDeductions  : Decimal(15,2);
  netPayable       : Decimal(15,2);

  ccy            : Currency;
  submittedOn    : Date;
  dueOn          : Date;
  lines          : Composition of many PaymentApplicationLine on lines.parent = $self;
  /**
   * Association, not composition. The certificate is the certifier's document
   * and is edited and issued on its own; deleting a superseded application
   * must not take a certificate somebody has already been paid against with
   * it, and a certificate has to be creatable without reopening the claim.
   */
  certificates   : Association to many PaymentCertificate on certificates.application = $self;
}

/**
 * One measured item on one application: the contract line, what was built,
 * what was claimed for it, and what survived each review.
 *
 * The row the whole screen is for. Without it an application is a lump sum
 * and nobody can answer "which items is this 2.1m for", "what did we claim
 * last month" or "how far through this item are we" — the three questions a
 * payment application exists to answer.
 */
entity PaymentApplicationLine : cuid {
  parent       : Association to PaymentApplication;
  lineNo       : Integer;

  /**
   * What is being claimed: a bill item, or a variation's own line.
   *
   * Both appear in the same table on the screen and both are claimed the same
   * way, so they are one entity with two references rather than two entities
   * that every total would have to add up separately. Exactly one is set —
   * a variation line claims against the variation that approved it, not
   * against the original bill, even where it varies one.
   */
  boqItem      : Association to prj.BOQItem;
  variationLine : Association to vo.VariationLine;

  /**
   * The contract terms, copied onto the line rather than read through the
   * reference. A rate that is renegotiated later must not change what a
   * certificate issued last quarter said it was.
   */
  itemNo       : String(40);
  description  : String(255);
  uom          : String(10);
  rate         : Decimal(15,2);
  contractQty  : Decimal(15,3);

  /**
   * What every previous application established for this item, cumulative.
   * Taken from the chain rather than keyed, so this period's claim is the
   * only quantity anyone enters.
   */
  priorQty     : Decimal(15,3);

  // ------------------------------------------- what each stage said, in turn
  /** What the contractor put forward. */
  proposedQty   : Decimal(15,3);
  proposedValue : Decimal(15,2);
  /** What the quantity surveyor made it after remeasure. */
  qsQty         : Decimal(15,3);
  qsValue       : Decimal(15,2);
  /**
   * What the Consultant approved, which is what gets paid.
   *
   * Three stages on a line, not four: submission is the project manager
   * signing the surveyor's figures and sending them, and it moves no
   * quantity. A column that never differs from the one before it is a column
   * a reader learns to skip, and then skips on the one occasion it does.
   */
  approvedQty   : Decimal(15,3);
  approvedValue : Decimal(15,2);

  /**
   * Where the item stands after this claim: prior plus what is proposed this
   * period, and that against the contract quantity.
   *
   * Measured against what was proposed rather than what was approved, because
   * it answers a question about the work and not about the paperwork: the
   * concrete is poured whether or not the consultant has agreed the quantity
   * yet. The approved columns say what will be paid; this says how far through
   * the item the site actually is.
   */
  cumQty       : Decimal(15,3);
  cumPct       : Decimal(5,2);

  /** Why a stage moved the quantity, where one did. */
  adjustmentReason : String(500);
}

/**
 * The interim payment certificate issued against one application.
 *
 * A separate document from the application, and deliberately so: the claim is
 * the contractor's statement and the certificate is the certifier's, and under
 * most forms of contract the second is what creates the entitlement to be
 * paid. Collapsing them would leave no way to say that a claim was made and
 * not certified, which is the state that starts most payment disputes.
 */
entity PaymentCertificate : cuid, managed, common.documented {
  // docNo is the certificate number, IPC-C-013.
  application    : Association to PaymentApplication;
  certSeq        : Integer;
  claimedGross   : Decimal(15,2);
  certifiedGross : Decimal(15,2);
  /** Signed: negative is a deduction. */
  adjustment     : Decimal(15,2);
  retentionAmount : Decimal(15,2);
  advanceRecovery : Decimal(15,2);
  netCertified   : Decimal(15,2);
  certifiedOn    : Date;
  certifiedBy    : String(120);
  /** The Consultant's reasoning, per line, where a line was cut. */
  adjustments    : Composition of many CertAdjustment on adjustments.certificate = $self;
  /** Where the money got to, once the client paid it. */
  settledAmount  : Decimal(15,2);
  settledOn      : Date;
}

/** One line the Engineer moved, and why. */
entity CertAdjustment : cuid {
  certificate  : Association to PaymentCertificate;
  applicationLine : Association to PaymentApplicationLine;
  itemNo       : String(40);
  description  : String(255);
  claimed      : Decimal(15,2);
  certified    : Decimal(15,2);
  adjustment   : Decimal(15,2);
  reasoning    : String(500);
}
