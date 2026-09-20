using MasterDataService as service from '../../srv/masterdata-service';

annotate service.SubcontractWorkers with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Subcontract Worker',
    TypeNamePlural : 'Subcontract Workers',
    Title          : { $Type : 'UI.DataField', Value : fullName },
    Description    : { $Type : 'UI.DataField', Value : workerNo },
  },

  UI.SelectionFields : [ workerNo, passportNo, status ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : workerNo } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : workerNo, Label : 'Worker number' },
    { $Type : 'UI.DataField', Value : fullName, Label : 'Name' },
    { $Type : 'UI.DataField', Value : passportNo, Label : 'Passport' },
    { $Type : 'UI.DataField', Value : nationality, Label : 'Nationality' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
  ],

  UI.FieldGroup #Man : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : workerNo, Label : 'Worker number' },
      { $Type : 'UI.DataField', Value : fullName, Label : 'Name' },
      { $Type : 'UI.DataField', Value : passportNo, Label : 'Passport' },
      { $Type : 'UI.DataField', Value : emiratesId, Label : 'Emirates ID' },
      { $Type : 'UI.DataField', Value : nationality, Label : 'Nationality' },
      { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Man', Label : 'The man',
      Target : '@UI.FieldGroup#Man' },
    { $Type : 'UI.ReferenceFacet', ID : 'Documents', Label : 'Statutory documents',
      Target : 'documents/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Engagements', Label : 'Every spell he has worked',
      Target : 'engagements/@UI.LineItem' },
  ],
);

// Identity and statutory papers follow the man because they do not change.
// Trade, grade and rate are on the engagement because they do.
annotate service.SubcontractWorkerDocuments with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Document' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : documentNo, Label : 'Number' },
    { $Type : 'UI.DataField', Value : expiresOn, Label : 'Expires' },
    { $Type : 'UI.DataField', Value : blocking, Label : 'Stops him working' },
  ],
);
