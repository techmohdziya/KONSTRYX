using MasterDataService as service from '../../srv/masterdata-service';

annotate service.SubcontractEngagements with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Engagement',
    TypeNamePlural : 'Engagements',
    Title          : { $Type : 'UI.DataField', Value : poNo },
    Description    : { $Type : 'UI.DataField', Value : worker_ID },
  },

  UI.SelectionFields : [ worker_ID, poNo, status ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : fromDate, Descending : true } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : worker_ID, Label : 'Worker' },
    { $Type : 'UI.DataField', Value : vendor_ID, Label : 'Supplier' },
    { $Type : 'UI.DataField', Value : poNo, Label : 'Purchase order' },
    { $Type : 'UI.DataField', Value : poItem, Label : 'Item' },
    { $Type : 'UI.DataField', Value : trade_ID, Label : 'Engaged as' },
    { $Type : 'UI.DataField', Value : ratePerHr, Label : 'Rate / hour' },
    { $Type : 'UI.DataField', Value : fromDate, Label : 'From' },
    { $Type : 'UI.DataField', Value : toDate, Label : 'To' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
  ],

  UI.FieldGroup #Engagement : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : worker_ID, Label : 'Worker' },
      { $Type : 'UI.DataField', Value : vendor_ID, Label : 'Supplier' },
      { $Type : 'UI.DataField', Value : project_ID, Label : 'Project' },
      { $Type : 'UI.DataField', Value : poNo, Label : 'Purchase order' },
      { $Type : 'UI.DataField', Value : poItem, Label : 'Item' },
      { $Type : 'UI.DataField', Value : trade_ID, Label : 'Engaged as' },
      { $Type : 'UI.DataField', Value : grade_ID, Label : 'Grade' },
      { $Type : 'UI.DataField', Value : ratePerHr, Label : 'Rate / hour' },
      { $Type : 'UI.DataField', Value : fromDate, Label : 'From' },
      { $Type : 'UI.DataField', Value : toDate, Label : 'To' },
      { $Type : 'UI.DataField', Value : hseInductionOn, Label : 'HSE induction' },
      { $Type : 'UI.DataField', Value : wcCoverExpiry, Label : 'WC cover expires' },
      { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Engagement', Label : 'One spell, one order item',
      Target : '@UI.FieldGroup#Engagement' },
  ],
);
