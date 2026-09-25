using BillingService as service from '../../srv/billing-service';

/**
 * Interim payment applications to the client — wireframe v13,
 * operations.html · pa-detail-approved.
 *
 * The screen is its line table. A claim rendered as a header and a total is
 * the thing this app exists to replace: the reader's question is never "what
 * is the gross", it is "which items is the gross for, what did we claim for
 * them last month, and how far through each one are we".
 *
 * The wireframe groups the stage columns under banded headers — ① Proposed,
 * ② QS Review, ④ Consultant Approved, each with its own quantity and value.
 * A Fiori Elements table has no banded header, so the columns run flat in the
 * same order and carry the stage in their own labels instead. Running them
 * flat and unlabelled would leave six numeric columns a reader has to count
 * along to identify.
 */
annotate service.PaymentApplications with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Payment Application',
    TypeNamePlural : 'Payment Applications',
    Title          : { $Type : 'UI.DataField', Value : docNo },
    Description    : { $Type : 'UI.DataField', Value : periodName },
  },

  UI.SelectionFields : [ projectCode, status, periodName ],

  /**
   * The worklist. Ordered as the claim moves: what we put in, what the
   * surveyor made of it, what came back approved, and what that leaves
   * payable — with the due date carrying its colour so a claim nobody has
   * answered is visible without reading the date.
   */
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : docNo,           Label : 'Application' },
    { $Type : 'UI.DataField', Value : periodName,      Label : 'Period' },
    { $Type : 'UI.DataField', Value : status,          Label : 'Stage' },
    { $Type : 'UI.DataField', Value : proposedGross,   Label : 'Proposed' },
    { $Type : 'UI.DataField', Value : qsReviewedGross, Label : 'QS Reviewed' },
    { $Type : 'UI.DataField', Value : approvedGross,   Label : 'Approved' },
    { $Type : 'UI.DataField', Value : netPayable,      Label : 'Net Payable' },
    { $Type : 'UI.DataField', Value : dueOn,           Label : 'Due',
      Criticality : dueCriticality },
  ],

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Claim', Label : 'Claim',
      Target : '@UI.FieldGroup#Claim' },
    /**
     * First facet after the header, because it is the document. Everything
     * else on this page is a total of it.
     */
    { $Type : 'UI.ReferenceFacet', ID : 'Lines', Label : 'Approved Line Items',
      Target : 'lines/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Deductions', Label : 'Deductions',
      Target : '@UI.FieldGroup#Deductions' },
    { $Type : 'UI.ReferenceFacet', ID : 'Certificates', Label : 'Certificates',
      Target : 'certificates/@UI.LineItem' },
  ],

  UI.FieldGroup #Claim : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : seq,             Label : 'Application number' },
      { $Type : 'UI.DataField', Value : seqOf,           Label : 'Of' },
      { $Type : 'UI.DataField', Value : periodStart,     Label : 'Period from' },
      { $Type : 'UI.DataField', Value : periodEnd,       Label : 'Period to' },
      // The claim this one follows. Every prior quantity on the lines below
      // was established here, which is what makes them checkable rather than
      // asserted.
      { $Type : 'UI.DataField', Value : previousApplication.docNo,
        Label : 'Previous PA' },
      { $Type : 'UI.DataField', Value : proposedGross,   Label : 'Proposed' },
      { $Type : 'UI.DataField', Value : qsReviewedGross, Label : 'QS Reviewed' },
      { $Type : 'UI.DataField', Value : submittedGross,  Label : 'Submitted' },
      { $Type : 'UI.DataField', Value : approvedGross,   Label : 'Approved' },
      { $Type : 'UI.DataField', Value : submittedOn,     Label : 'Submitted on' },
      { $Type : 'UI.DataField', Value : dueOn,           Label : 'Due on',
        Criticality : dueCriticality },
    ],
  },

  UI.FieldGroup #Deductions : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : retentionPct,       Label : 'Retention %' },
      { $Type : 'UI.DataField', Value : retentionAmount,    Label : 'Retention' },
      { $Type : 'UI.DataField', Value : advanceRecovery,    Label : 'Advance Recovery' },
      { $Type : 'UI.DataField', Value : advanceOutstanding, Label : 'Advance Outstanding' },
      { $Type : 'UI.DataField', Value : otherDeductions,    Label : 'Other deductions' },
      { $Type : 'UI.DataField', Value : netPayable,         Label : 'Net Payable' },
    ],
  },
);

/**
 * The measured line, in the wireframe's own column order.
 *
 * Contract terms first, then what came before, then what each stage said of
 * this period, then where the item now stands. A reader works left to right
 * and arrives at the cumulative percentage having seen everything that
 * produced it.
 */
annotate service.PaymentApplicationLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : itemNo,        Label : 'Item' },
    { $Type : 'UI.DataField', Value : description,   Label : 'Description' },
    { $Type : 'UI.DataField', Value : uom,           Label : 'Unit' },
    { $Type : 'UI.DataField', Value : rate,          Label : 'Rate' },
    { $Type : 'UI.DataField', Value : contractQty,   Label : 'Contract Qty' },
    // What every application before this one established. Not keyed here:
    // it is read from the chain, and a reader comparing it against the
    // previous claim should find the same number.
    { $Type : 'UI.DataField', Value : priorQty,      Label : 'Prior PA Qty' },
    { $Type : 'UI.DataField', Value : proposedQty,   Label : 'This PA Qty (proposed)' },
    { $Type : 'UI.DataField', Value : proposedValue, Label : 'This PA Value (proposed)' },
    { $Type : 'UI.DataField', Value : qsQty,         Label : 'QS Reviewed Qty' },
    { $Type : 'UI.DataField', Value : qsValue,       Label : 'QS Reviewed Value' },
    { $Type : 'UI.DataField', Value : approvedQty,   Label : 'Approved Qty' },
    { $Type : 'UI.DataField', Value : approvedValue, Label : 'Approved Value' },
    { $Type : 'UI.DataField', Value : cumQty,        Label : 'Cum Qty' },
    { $Type : 'UI.DataField', Value : cumPct,        Label : 'Approved Cum %' },
    { $Type : 'UI.DataField', Value : adjustmentReason, Label : 'Reason' },
  ],
);

/** The certificates issued against the claim, and what was settled. */
annotate service.PaymentCertificates with @(
  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Interim Payment Certificate',
    TypeNamePlural : 'Interim Payment Certificates',
    Title          : { $Type : 'UI.DataField', Value : docNo },
  },
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : docNo,          Label : 'IPC' },
    { $Type : 'UI.DataField', Value : certSeq,        Label : 'No.' },
    { $Type : 'UI.DataField', Value : claimedGross,   Label : 'Claimed' },
    { $Type : 'UI.DataField', Value : certifiedGross, Label : 'Certified' },
    { $Type : 'UI.DataField', Value : adjustment,     Label : 'Adjustment' },
    { $Type : 'UI.DataField', Value : retentionAmount, Label : 'Retention' },
    { $Type : 'UI.DataField', Value : netCertified,   Label : 'Net Certified' },
    { $Type : 'UI.DataField', Value : certifiedOn,    Label : 'Certified on' },
    { $Type : 'UI.DataField', Value : settledAmount,  Label : 'Settled' },
  ],
  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Cert', Label : 'IPC',
      Target : '@UI.FieldGroup#Cert' },
    // Why each line moved. A certificate that deducts 23,840 and does not say
    // which lines it came off is the document this facet exists to prevent.
    { $Type : 'UI.ReferenceFacet', ID : 'Adjustments', Label : 'Adjustments',
      Target : 'adjustments/@UI.LineItem' },
  ],
  UI.FieldGroup #Cert : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : application.docNo, Label : 'Against application' },
      { $Type : 'UI.DataField', Value : claimedGross,    Label : 'Claimed' },
      { $Type : 'UI.DataField', Value : certifiedGross,  Label : 'Certified' },
      { $Type : 'UI.DataField', Value : adjustment,      Label : 'Adjustment' },
      { $Type : 'UI.DataField', Value : retentionAmount, Label : 'Retention' },
      { $Type : 'UI.DataField', Value : advanceRecovery, Label : 'Advance Recovery' },
      { $Type : 'UI.DataField', Value : netCertified,    Label : 'Net Certified' },
      { $Type : 'UI.DataField', Value : certifiedBy,     Label : 'Certified by' },
      { $Type : 'UI.DataField', Value : certifiedOn,     Label : 'Certified on' },
      { $Type : 'UI.DataField', Value : settledAmount,   Label : 'Settled' },
      { $Type : 'UI.DataField', Value : settledOn,       Label : 'Settled on' },
    ],
  },
);

annotate service.CertAdjustments with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : itemNo,      Label : 'Item' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : claimed,     Label : 'Claimed' },
    { $Type : 'UI.DataField', Value : certified,   Label : 'Certified' },
    { $Type : 'UI.DataField', Value : adjustment,  Label : 'Adjustment' },
    { $Type : 'UI.DataField', Value : reasoning,   Label : 'Reasoning' },
  ],
);

/** The project as a person names it, not as the service keys it. */
annotate service.PaymentApplications with {
  projectCode @title : 'Project';
  projectName @title : 'Project name';
}
