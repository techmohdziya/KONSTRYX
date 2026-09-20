using MasterDataService as service from '../../srv/masterdata-service';

/**
 * Consumption norms — how much material one unit of work takes, and how much
 * of it is lost getting there.
 *
 * The net rate is derived, never typed: theoretical rate times one plus the
 * wastage allowance, to four decimal places. It is stored so a query does not
 * have to recompute it, recomputed on every write, and an inbound value is
 * ignored rather than trusted — a net rate edited to disagree with its own
 * theoretical rate and wastage is a number nobody can reconcile, and it would
 * flow straight into every budget built from it.
 *
 * Shown alongside both its inputs for that reason: read together, the row
 * explains itself.
 */
annotate service.ConsumptionRates with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Consumption Norm',
    TypeNamePlural : 'Consumption Norms',
    Title          : { $Type : 'UI.DataField', Value : activity },
    Description    : { $Type : 'UI.DataField', Value : basis },
  },

  UI.SelectionFields : [ activity, material_ID, linkedCBS_ID, scope, effectiveFrom ],

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : material_ID,         Label : 'Material' },
    { $Type : 'UI.DataField', Value : activity,            Label : 'Activity' },
    { $Type : 'UI.DataField', Value : linkedCBS_ID,        Label : 'Linked CBS' },
    { $Type : 'UI.DataField', Value : consRate,            Label : 'Theoretical rate' },
    { $Type : 'UI.DataField', Value : wastageAllowancePct, Label : 'Wastage %' },
    { $Type : 'UI.DataField', Value : netRate,             Label : 'Net rate' },
    { $Type : 'UI.DataField', Value : consUoM,             Label : 'UoM' },
    { $Type : 'UI.DataField', Value : effectiveFrom,       Label : 'Effective from' },
    { $Type : 'UI.DataField', Value : scope,               Label : 'Scope' },
  ],

  UI.FieldGroup #Norm : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : material_ID,         Label : 'Material' },
      { $Type : 'UI.DataField', Value : activity,            Label : 'Activity' },
      { $Type : 'UI.DataField', Value : consRate,            Label : 'Theoretical rate' },
      { $Type : 'UI.DataField', Value : wastageAllowancePct, Label : 'Wastage allowance %' },
      { $Type : 'UI.DataField', Value : netRate,             Label : 'Net rate (derived)' },
      { $Type : 'UI.DataField', Value : consUoM,             Label : 'Unit of measure' },
    ],
  },

  UI.FieldGroup #Recipe : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : linkedCBS_ID,  Label : 'Linked CBS leaf' },
      { $Type : 'UI.DataField', Value : basis,         Label : 'Basis' },
      { $Type : 'UI.DataField', Value : effectiveFrom, Label : 'Effective from' },
    ],
  },

  UI.FieldGroup #Governance : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : scope,            Label : 'Scope' },
      { $Type : 'UI.DataField', Value : masterStatus,     Label : 'Status' },
      { $Type : 'UI.DataField', Value : owningCompany_ID, Label : 'Owning company' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Norm', Label : 'Norm',
      Target : '@UI.FieldGroup#Norm' },
    { $Type : 'UI.ReferenceFacet', ID : 'Recipe', Label : 'Recipe key',
      Target : '@UI.FieldGroup#Recipe' },
    { $Type : 'UI.ReferenceFacet', ID : 'Governance', Label : 'Governance',
      Target : '@UI.FieldGroup#Governance' },
  ],
);

annotate service.ConsumptionRates with {
  activity            @title : 'Activity';
  consRate            @title : 'Theoretical rate';
  wastageAllowancePct @title : 'Wastage allowance %';
  // Derived on write. Read-only here so a typed value is refused where it is
  // typed rather than silently discarded at save.
  netRate             @title : 'Net rate' @readonly;
  consUoM             @title : 'Unit of measure';
  basis               @title : 'Basis';
  effectiveFrom       @title : 'Effective from';

  material @Common : {
    Text            : material.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'Resources',
      Label          : 'Material',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : material_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'description' }
      ]
    }
  };

  linkedCBS @Common : {
    Text            : linkedCBS.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'CBSLibrary',
      Label          : 'CBS leaf',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : linkedCBS_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly',
          ValueListProperty : 'constructionType' }
      ]
    }
  };
};
