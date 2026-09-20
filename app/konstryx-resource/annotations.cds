using MasterDataService as service from '../../srv/masterdata-service';

annotate service.Resources with @(

  /**
   * The catalogue opens two levels deep: the three verticals and the families
   * under them. Deeper than that is 77 rows of leaves, which is the flat list
   * the tree exists to replace; shallower is three rows that say nothing.
   *
   * Fiori Elements reads the depth from the presentation variant and nowhere
   * else - the same setting written into the manifest's table settings is
   * ignored silently, and the only trace is the Levels=1 the table asks for.
   */
  UI.PresentationVariant : {
    $Type                 : 'UI.PresentationVariantType',
    InitialExpansionLevel : 2,
    Visualizations        : [ '@UI.LineItem' ],
  },

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
