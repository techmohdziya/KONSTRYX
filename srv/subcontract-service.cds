/**
 * KONSTRYX — Subcontract service
 * Subcontract requests, payment applications and their certification.
 */
using { konstryx.scr } from '../db/scr';

@requires: 'BudgetController'
service SubcontractService @(path:'/subcontract') {

  entity SubcontractRequests as projection on scr.SubcontractRequest;

  entity PaymentApplications as projection on scr.PaymentApplication
    actions {
      /**
       * Raises a certificate against this application.
       *
       * The certificate starts at the claimed amount with nothing deducted.
       * Adjustments, liquidated damages and back charges are entered against
       * it, and recalculate derives what is actually payable.
       */
      action certify(retentionPct : Decimal(5,2)) returns String;
    };

  entity PaymentCertificates as projection on scr.PaymentCertificate
    actions {
      /**
       * Derives what is payable from the certificate's own parts.
       *
       * Every money field on a certificate was a stored number with nothing
       * making it agree with the lines beneath it, so a certificate could
       * state a net that its own back charges contradicted. Four figures are
       * derived here and the rest are inputs:
       *
       *   certified gross = claimed gross + adjustment
       *   retention       = certified gross x retention %
       *   back charges    = the sum of the back charge lines
       *   net certified   = certified gross - retention - LD - back charges
       *
       * Liquidated damages stay an input: the LD steps are a calculation
       * shown to a subcontractor in dates and day counts, not a column that
       * can be summed. The adjustment stays an input for the same reason —
       * the adjustment lines carry quantities, not values.
       */
      action recalculate() returns String;

      /** Records one decision on the certificate's sign-off chain. */
      action signOff(
        role     : String(60),
        name     : String(80),
        decision : String(20)
      ) returns String;
    };

  entity CertAdjustmentLines as projection on scr.CertAdjustmentLine;
  entity LDCalculationSteps  as projection on scr.LDCalculationStep;
  entity BackChargeLines     as projection on scr.BackChargeLine;

  /** Written by signOff so the chain is a record, not a form. */
  @readonly entity CertSignOffs as projection on scr.CertSignOff;
}
