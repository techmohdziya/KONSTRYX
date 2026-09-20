using MasterDataService as service from '../../srv/masterdata-service';

annotate service.RosterUploads with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Roster Upload',
    TypeNamePlural : 'Roster Uploads',
    Title          : { $Type : 'UI.DataField', Value : fileName },
    Description    : { $Type : 'UI.DataField', Value : vendor_ID },
  },

  UI.SelectionFields : [ vendor_ID, status ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : uploadedOn, Descending : true } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  // Preview judges and writes nothing; committing writes only what it accepted.
  UI.Identification : [
    { $Type : 'UI.DataFieldForAction',
      Action : 'MasterDataService.preview', Label : 'Preview' },
    { $Type : 'UI.DataFieldForAction',
      Action : 'MasterDataService.commitRoster', Label : 'Create the accepted' },
  ],

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : fileName, Label : 'File' },
    { $Type : 'UI.DataField', Value : vendor_ID, Label : 'Supplier' },
    { $Type : 'UI.DataField', Value : uploadedOn, Label : 'Uploaded' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : rowsTotal, Label : 'Rows' },
    { $Type : 'UI.DataField', Value : rowsAccepted, Label : 'Accepted' },
    { $Type : 'UI.DataField', Value : rowsRejected, Label : 'Rejected' },
    { $Type : 'UI.DataField', Value : rowsDuplicate, Label : 'Already held' },
  ],

  UI.FieldGroup #Upload : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : fileName, Label : 'File' },
      { $Type : 'UI.DataField', Value : vendor_ID, Label : 'Supplier' },
      { $Type : 'UI.DataField', Value : uploadedOn, Label : 'Uploaded' },
      { $Type : 'UI.DataField', Value : status, Label : 'Status' },
      { $Type : 'UI.DataField', Value : rowsTotal, Label : 'Rows' },
      { $Type : 'UI.DataField', Value : rowsAccepted, Label : 'Accepted' },
      { $Type : 'UI.DataField', Value : rowsRejected, Label : 'Rejected' },
      { $Type : 'UI.DataField', Value : rowsDuplicate, Label : 'Already held' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Upload', Label : 'What arrived',
      Target : '@UI.FieldGroup#Upload' },
    { $Type : 'UI.ReferenceFacet', ID : 'Rows', Label : 'Line by line',
      Target : 'rows/@UI.LineItem' },
  ],
);

// The reason is beside the outcome rather than behind it: a roster is
// corrected by the supplier, and they need to be told what to correct.
annotate service.RosterUploadRows with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : lineNo, Label : 'Line' },
    { $Type : 'UI.DataField', Value : fullName, Label : 'Name' },
    { $Type : 'UI.DataField', Value : passportNo, Label : 'Passport' },
    { $Type : 'UI.DataField', Value : tradeCode, Label : 'Trade' },
    { $Type : 'UI.DataField', Value : gradeCode, Label : 'Grade' },
    { $Type : 'UI.DataField', Value : outcome, Label : 'Outcome' },
    { $Type : 'UI.DataField', Value : reason, Label : 'Reason' },
  ],
);
