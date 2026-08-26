using SubcontractService as service from '../../srv/subcontract-service';

annotate service.PaymentCertificates with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Payment Certificate',
    TypeNamePlural : 'Payment Certificates',
    Title          : { $Type : 'UI.DataField', Value : docNo },
    Description    : { $Type : 'UI.DataField', Value : status },
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : docNo, Label : 'Certificate' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : certSeq, Label : 'Sequence' },
    { $Type : 'UI.DataField', Value : claimedGross, Label : 'Claimed' },
    { $Type : 'UI.DataField', Value : adjustment, Label : 'Adjustment' },
    { $Type : 'UI.DataField', Value : certifiedGross, Label : 'Certified' },
    { $Type : 'UI.DataField', Value : retentionAmount, Label : 'Retention' },
    { $Type : 'UI.DataField', Value : netCertified, Label : 'Net certified' },
    { $Type : 'UI.DataField', Value : ldApplied, Label : 'LD applied' },
  ],

  UI.FieldGroup #Details : {
    $Type : 'UI.FieldGroupType',
    Data  : [
    { $Type : 'UI.DataField', Value : docNo, Label : 'Certificate' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : certSeq, Label : 'Sequence' },
    { $Type : 'UI.DataField', Value : claimedGross, Label : 'Claimed' },
    { $Type : 'UI.DataField', Value : adjustment, Label : 'Adjustment' },
    { $Type : 'UI.DataField', Value : certifiedGross, Label : 'Certified' },
    { $Type : 'UI.DataField', Value : retentionAmount, Label : 'Retention' },
    { $Type : 'UI.DataField', Value : netCertified, Label : 'Net certified' },
    { $Type : 'UI.DataField', Value : ldApplied, Label : 'LD applied' },
    ],
  },

  // Every deduction the net is made of, each on its own tab. Two of the four
  // were not on the screen at all, which meant a certificate could show a net
  // reduced by liquidated damages and back charges with nowhere to see either.
  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
    { $Type : 'UI.ReferenceFacet', ID : 'Adjustments', Label : 'Adjustments',
      Target : 'adjustments/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'LDSteps', Label : 'Liquidated Damages',
      Target : 'ldSteps/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'BackCharges', Label : 'Back Charges',
      Target : 'backCharges/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'SignOffs', Label : 'Sign-offs',
      Target : 'signOffs/@UI.LineItem' },
  ],

  /**
   * Recalculate had no button, so the one action that makes a certificate
   * agree with its own lines could not be run from the screen it corrects.
   */
  UI.Identification : [
    { $Type : 'UI.DataFieldForAction', Label : 'Recalculate',
      Action : 'SubcontractService.recalculate' },
    { $Type : 'UI.DataFieldForAction', Label : 'Sign off',
      Action : 'SubcontractService.signOff' },
  ],
);

// Recalculating rewrites four figures on the certificate itself, so the header
// has to be re-read or the screen keeps showing the net it just replaced.
annotate service.PaymentCertificates with @(
  Common.SideEffects #Recalculated : {
    SourceEvents     : [ 'SubcontractService.recalculate' ],
    // The empty navigation path is the record itself. Listing the four
    // properties alone was not enough - the action ran, the database moved,
    // and the screen kept showing the net it had just replaced, which is the
    // worst of the three outcomes because it looks like the button did
    // nothing.
    TargetEntities   : [ '' ],
    TargetProperties : [ 'certifiedGross', 'retentionAmount',
                         'backChargeTotal', 'netCertified' ],
  },
  Common.SideEffects #SignedOff : {
    SourceEvents     : [ 'SubcontractService.signOff' ],
    TargetEntities   : [ '', signOffs ],
    TargetProperties : [ 'status' ],
  }
);

annotate service.LDCalculationSteps with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : seq,         Label : 'Step' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : days,        Label : 'Days' },
    { $Type : 'UI.DataField', Value : rate,        Label : 'Rate' },
    { $Type : 'UI.DataField', Value : amount,      Label : 'Amount' },
  ],
);

annotate service.BackChargeLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : description,  Label : 'Description' },
    { $Type : 'UI.DataField', Value : cause,        Label : 'Cause' },
    { $Type : 'UI.DataField', Value : rechargeType, Label : 'Recharge type' },
    { $Type : 'UI.DataField', Value : amount,       Label : 'Amount' },
  ],
);

// The chain is a record of who decided, so it reads in the order decided.
annotate service.CertSignOffs with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : seq,       Label : 'Step' },
    { $Type : 'UI.DataField', Value : role,      Label : 'Role' },
    { $Type : 'UI.DataField', Value : name,      Label : 'Name' },
    { $Type : 'UI.DataField', Value : decision,  Label : 'Decision' },
    { $Type : 'UI.DataField', Value : decidedOn, Label : 'Decided on' },
  ],
);

annotate service.CertAdjustmentLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : subBoqLine, Label : 'BOQ line' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : claimedQty, Label : 'Claimed qty' },
    { $Type : 'UI.DataField', Value : certifiedQty, Label : 'Certified qty' },
    { $Type : 'UI.DataField', Value : deltaQty, Label : 'Delta' },
    { $Type : 'UI.DataField', Value : uom, Label : 'UoM' },
    { $Type : 'UI.DataField', Value : reason, Label : 'Reason' },
  ],
);
