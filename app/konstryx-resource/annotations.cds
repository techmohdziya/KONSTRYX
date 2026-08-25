using MasterDataService as service from '../../srv/masterdata-service';

annotate service.Resources with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Resource',
    TypeNamePlural : 'Resources',
    Title          : { $Type : 'UI.DataField', Value : code },
    Description    : { $Type : 'UI.DataField', Value : description },
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Code' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : level, Label : 'Level' },
    { $Type : 'UI.DataField', Value : verticalType, Label : 'Vertical' },
    { $Type : 'UI.DataField', Value : consUoM, Label : 'Consumption UoM' },
    { $Type : 'UI.DataField', Value : outputUoM, Label : 'Output UoM' },
    { $Type : 'UI.DataField', Value : scope, Label : 'Scope' },
    { $Type : 'UI.DataField', Value : masterStatus, Label : 'Status' },
  ],

  UI.FieldGroup #Details : {
    $Type : 'UI.FieldGroupType',
    Data  : [
    { $Type : 'UI.DataField', Value : code, Label : 'Code' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : level, Label : 'Level' },
    { $Type : 'UI.DataField', Value : verticalType, Label : 'Vertical' },
    { $Type : 'UI.DataField', Value : consUoM, Label : 'Consumption UoM' },
    { $Type : 'UI.DataField', Value : outputUoM, Label : 'Output UoM' },
    { $Type : 'UI.DataField', Value : scope, Label : 'Scope' },
    { $Type : 'UI.DataField', Value : masterStatus, Label : 'Status' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
  ],
);
