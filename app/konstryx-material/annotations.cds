using MasterDataService as service from '../../srv/masterdata-service';

annotate service.Materials with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Material',
    TypeNamePlural : 'Materials',
    Title          : { $Type : 'UI.DataField', Value : materialCode },
    Description    : { $Type : 'UI.DataField', Value : description },
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : materialCode, Label : 'Material' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : baseUoM, Label : 'Base UoM' },
    { $Type : 'UI.DataField', Value : materialGroup, Label : 'Group' },
    { $Type : 'UI.DataField', Value : s4System, Label : 'Source system' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'Sync' },
    { $Type : 'UI.DataField', Value : lastSyncedAt, Label : 'Last synced' },
  ],

  UI.FieldGroup #Details : {
    $Type : 'UI.FieldGroupType',
    Data  : [
    { $Type : 'UI.DataField', Value : materialCode, Label : 'Material' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : baseUoM, Label : 'Base UoM' },
    { $Type : 'UI.DataField', Value : materialGroup, Label : 'Group' },
    { $Type : 'UI.DataField', Value : s4System, Label : 'Source system' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'Sync' },
    { $Type : 'UI.DataField', Value : lastSyncedAt, Label : 'Last synced' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
  ],
);
