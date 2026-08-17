/**
 * KONSTRYX — Subcontract service
 * First increment: read the Payment Certificate the wireframe's scr-pa-cert
 * screen renders. Certification/S/4 invoice posting is not built here.
 */
using { konstryx.scr } from '../db/scr';

@requires: 'BudgetController'
service SubcontractService @(path:'/subcontract') {
  @readonly entity SubcontractRequests as projection on scr.SubcontractRequest;
  @readonly entity PaymentApplications as projection on scr.PaymentApplication;
  @readonly entity PaymentCertificates as projection on scr.PaymentCertificate;
  @readonly entity CertAdjustmentLines as projection on scr.CertAdjustmentLine;
  @readonly entity LDCalculationSteps  as projection on scr.LDCalculationStep;
  @readonly entity BackChargeLines     as projection on scr.BackChargeLine;
  @readonly entity CertSignOffs        as projection on scr.CertSignOff;
}
