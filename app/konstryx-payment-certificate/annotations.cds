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

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
    { $Type : 'UI.ReferenceFacet', ID : 'Adjustments', Label : 'Adjustments',
      Target : 'adjustments/@UI.LineItem' },
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
