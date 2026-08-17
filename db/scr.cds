/**
 * KONSTRYX — konstryx.scr (Subcontract & Commercial)
 *
 * First increment of the SCR (Subcontracting Request) chain: the Payment
 * Certificate screen, per KONSTRYX_Wireframe_v12/modules/subcontract.html
 * (route scr-pa-cert). The wireframe's canonical thread is SR-2026-0211
 * (Façade Cladding, Curtain Wall + ACP) — its numbers are locked for
 * end-to-end reconciliation (CLAUDE.md, wireframe project memory) and are
 * reproduced here exactly, not re-derived.
 *
 * Scoped deliberately narrow: SR header + one Payment Application + its
 * Payment Certificate, enough to render the certificate screen honestly.
 * The surrounding chain (Advisory, RFQ, Bid, Award, Sub-BOQ, the PA
 * worklist, Variation, TOC, Final Account) is the wireframe's other twelve
 * nodes and is not built here — this is the Payment Certificate on its own,
 * as asked.
 */
namespace konstryx.scr;

using { cuid, managed } from '@sap/cds/common';
using { konstryx.common } from './common';

/** SR: the subcontract package itself. One SR per package, awarded once. */
entity SubcontractRequest : cuid, managed, common.documented {
  scopeDescription : String(500);
  vendorBPNo       : String(20);    // S/4 Business Partner, e.g. 0001000211
  vendorName       : String(120);
  isGroupCompany   : Boolean default false;   // GRP vs EXT — drives the paired IC billing note
  executingCompany : String(10);              // set only when isGroupCompany
  contractValue    : Decimal(15,2);
  ccy              : String(3) default 'AED';
  applications     : Composition of many PaymentApplication on applications.scr = $self;
}

/** PA: one subcontractor payment application against the SR. */
entity PaymentApplication : cuid, managed {
  scr           : Association to SubcontractRequest;
  paNo          : String(20);   // "PA-006"
  claimedAmount : Decimal(15,2);
  status        : String(20);
  certificates  : Composition of many PaymentCertificate on certificates.pa = $self;
}

/**
 * PC: the Engineer's certification of one PA — the object this screen
 * renders. Triggers the S/4 supplier invoice on certification (not built
 * here; s4InvoiceRef/s4Api are the wireframe's own read-only trigger panel).
 */
entity PaymentCertificate : cuid, managed, common.documented {
  pa               : Association to PaymentApplication;
  scr              : Association to SubcontractRequest;
  certSeq          : Integer;        // "6 of 8"
  certOf           : Integer;
  claimedGross     : Decimal(15,2);
  adjustment       : Decimal(15,2);  // signed; negative = deduction
  certifiedGross   : Decimal(15,2);
  retentionPct     : Decimal(5,2);
  retentionAmount  : Decimal(15,2);
  netCertified     : Decimal(15,2);
  ldApplied        : Decimal(15,2);
  backChargeTotal  : Decimal(15,2);
  s4InvoiceRef     : String(40);
  s4Api            : String(60);
  paymentTerm      : String(60);
  adjustments : Composition of many CertAdjustmentLine on adjustments.pc = $self;
  ldSteps     : Composition of many LDCalculationStep  on ldSteps.pc     = $self;
  backCharges : Composition of many BackChargeLine      on backCharges.pc = $self;
  signOffs    : Composition of many CertSignOff         on signOffs.pc    = $self;
}

/** Re-measurement/adjustment lines: claimed qty vs certified qty, per Sub-BOQ line. */
entity CertAdjustmentLine : cuid {
  pc            : Association to PaymentCertificate;
  subBoqLine    : String(20);
  description   : String(255);
  claimedQty    : Decimal(15,3);
  certifiedQty  : Decimal(15,3);
  deltaQty      : Decimal(15,3);
  uom           : String(10);
  reason        : String(500);
}

/** LD (liquidated damages) calculation, one row per step of the wireframe's table. */
entity LDCalculationStep : cuid {
  pc       : Association to PaymentCertificate;
  stepNo   : Integer;
  step     : String(80);
  basis    : String(120);
  value    : String(40);   // the table mixes dates, day-counts and AED amounts — display value, not a single typed column
  emphasis : Boolean default false;   // rows the wireframe highlights (revised completion, chargeable delay, applied LD)
}

/** Recovery of cost KONSTRYX incurred on the subcontractor's behalf, debited to the PA. */
entity BackChargeLine : cuid {
  pc            : Association to PaymentCertificate;
  description   : String(255);
  cause         : String(60);     // NCR / instruction reference
  rechargeType  : String(20);     // RCH-LAB-RECT, RCH-MAT-SUP, ...
  qtyBasis      : String(20);     // "48 hr", "22 m2", "10%" — mixed basis, display value
  rate          : String(20);
  amount        : Decimal(15,2);
}

/** The certification review chain — who signed off, and when. */
entity CertSignOff : cuid {
  pc       : Association to PaymentCertificate;
  seq      : Integer;
  role     : String(60);
  name     : String(80);
  decision : String(20);
  decidedOn: DateTime;
}
