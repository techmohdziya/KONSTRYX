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
       *
       * It returns the certificate rather than a sentence. A message told the
       * user what had happened; it did not tell the screen. Fiori Elements
       * merges an action's returned entity into the bound context, so the
       * header updates - where a Common.SideEffects annotation, in either of
       * the two forms that look correct, left the page showing the net it had
       * just replaced. A button that moves the database and not the screen
       * reads as a button that does nothing. The sentence is not lost: it
       * goes to the message container, which is where a human-readable
       * outcome belongs.
       */
      action recalculate() returns PaymentCertificates;

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
