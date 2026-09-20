using MasterDataService as service from '../../srv/masterdata-service';

annotate service.WorkerPushQueue with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Work Agreement',
    TypeNamePlural : 'Work Agreements',
    Title          : { $Type : 'UI.DataField', Value : fullName },
    Description    : { $Type : 'UI.DataField', Value : empNo },
  },

  UI.SelectionFields : [ syncStatus, company ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : syncStatus } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : empNo, Label : 'Works number' },
    { $Type : 'UI.DataField', Value : fullName, Label : 'Name' },
    { $Type : 'UI.DataField', Value : trade, Label : 'Trade' },
    { $Type : 'UI.DataField', Value : company, Label : 'Company' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'State' },
    { $Type : 'UI.DataField', Value : syncMessage, Label : 'Why' },
    { $Type : 'UI.DataField', Value : syncAttempts, Label : 'Attempts' },
  ],

  UI.FieldGroup #Queued : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : empNo, Label : 'Works number' },
      { $Type : 'UI.DataField', Value : fullName, Label : 'Name' },
      { $Type : 'UI.DataField', Value : trade, Label : 'Trade' },
      { $Type : 'UI.DataField', Value : company, Label : 'Company' },
      { $Type : 'UI.DataField', Value : syncStatus, Label : 'State' },
      { $Type : 'UI.DataField', Value : syncMessage, Label : 'Why' },
      { $Type : 'UI.DataField', Value : syncAttempts, Label : 'Attempts' },
      { $Type : 'UI.DataField', Value : lastSyncedAt, Label : 'Last attempt' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Queued', Label : 'Why he is waiting',
      Target : '@UI.FieldGroup#Queued' },
  ],
);
