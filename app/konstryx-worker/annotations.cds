using MasterDataService as service from '../../srv/masterdata-service';

annotate service.Workers with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Worker',
    TypeNamePlural : 'Workers',
    Title          : { $Type : 'UI.DataField', Value : fullName },
    Description    : { $Type : 'UI.DataField', Value : empNo },
  },

  UI.SelectionFields : [ empNo, trade_ID, status ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : empNo } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : empNo, Label : 'Works number' },
    { $Type : 'UI.DataField', Value : fullName, Label : 'Name' },
    { $Type : 'UI.DataField', Value : trade_ID, Label : 'Trade' },
    { $Type : 'UI.DataField', Value : grade_ID, Label : 'Grade' },
    { $Type : 'UI.DataField', Value : shiftPattern_ID, Label : 'Shift pattern' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'Work agreement' },
  ],

  UI.FieldGroup #Worker : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : empNo, Label : 'Works number' },
      { $Type : 'UI.DataField', Value : fullName, Label : 'Name' },
      { $Type : 'UI.DataField', Value : passportNo, Label : 'Passport' },
      { $Type : 'UI.DataField', Value : emiratesId, Label : 'Emirates ID' },
      { $Type : 'UI.DataField', Value : nationality, Label : 'Nationality' },
      { $Type : 'UI.DataField', Value : source, Label : 'Mastered in' },
      { $Type : 'UI.DataField', Value : trade_ID, Label : 'Trade' },
      { $Type : 'UI.DataField', Value : grade_ID, Label : 'Grade' },
      { $Type : 'UI.DataField', Value : shiftPattern_ID, Label : 'Shift pattern' },
      { $Type : 'UI.DataField', Value : calendar_ID, Label : 'Holiday calendar' },
      { $Type : 'UI.DataField', Value : costCentre, Label : 'Cost centre' },
      { $Type : 'UI.DataField', Value : gradingBand, Label : 'Grading band' },
      { $Type : 'UI.DataField', Value : joinedOn, Label : 'Joined' },
      { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    ],
  },

  // Without an agreement no timesheet posts, and nothing upstream will create
  // one for us — so its state belongs on the man's own page, not only in a
  // monitor somebody has to remember to open.
  UI.FieldGroup #Agreement : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : syncStatus, Label : 'State' },
      { $Type : 'UI.DataField', Value : syncMessage, Label : 'What it said' },
      { $Type : 'UI.DataField', Value : syncAttempts, Label : 'Attempts' },
      { $Type : 'UI.DataField', Value : lastSyncedAt, Label : 'Last attempt' },
      { $Type : 'UI.DataFieldForAction',
        Action : 'MasterDataService.releaseToErp', Label : 'Release to ERP' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Worker', Label : 'The man',
      Target : '@UI.FieldGroup#Worker' },
    { $Type : 'UI.ReferenceFacet', ID : 'Agreement', Label : 'Work agreement',
      Target : '@UI.FieldGroup#Agreement' },
    { $Type : 'UI.ReferenceFacet', ID : 'Documents', Label : 'Documents and cards',
      Target : 'documents/@UI.LineItem' },
  ],
);

annotate service.WorkerDocuments with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Document' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : documentNo, Label : 'Number' },
    { $Type : 'UI.DataField', Value : issuedOn, Label : 'Issued' },
    { $Type : 'UI.DataField', Value : expiresOn, Label : 'Expires' },
    { $Type : 'UI.DataField', Value : blocking, Label : 'Stops him working' },
  ],
);
