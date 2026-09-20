using MasterDataService as service from '../../srv/masterdata-service';

/**
 * Productivity norms — how much a crew installs in an hour, and in a day.
 *
 * These are what turn a bill line into a labour cost. A norm belongs to a CBS
 * leaf rather than to a bill line: nobody keys resources per bill line, and the
 * build-up of a line resolves through the line's CBS. A row with no linked CBS
 * is a plain resource norm and takes no part in a recipe — shown here as a
 * column so the distinction is visible rather than discovered.
 *
 * Output per hour and output per 8-hour manday are both carried because both
 * are quoted: a subcontractor prices in mandays and a planner schedules in
 * hours, and deriving one from the other with an assumed shift length is how a
 * norm ends up disagreeing with the quote it came from.
 */
annotate service.ProductivityRates with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Productivity Norm',
    TypeNamePlural : 'Productivity Norms',
    Title          : { $Type : 'UI.DataField', Value : activity },
    Description    : { $Type : 'UI.DataField', Value : crewComposition },
  },

  UI.SelectionFields : [ activity, resource_ID, linkedCBS_ID, scope, effectiveFrom ],

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : resource_ID,       Label : 'Resource' },
    { $Type : 'UI.DataField', Value : activity,          Label : 'Activity' },
    { $Type : 'UI.DataField', Value : linkedCBS_ID,      Label : 'Linked CBS' },
    { $Type : 'UI.DataField', Value : crewComposition,   Label : 'Crew' },
    { $Type : 'UI.DataField', Value : outputPerHr,       Label : 'Output / hour' },
    { $Type : 'UI.DataField', Value : outputPerManday8h, Label : 'Output / manday' },
    { $Type : 'UI.DataField', Value : outputUoM,         Label : 'UoM' },
    { $Type : 'UI.DataField', Value : effectiveFrom,     Label : 'Effective from' },
    { $Type : 'UI.DataField', Value : scope,             Label : 'Scope' },
  ],

  UI.FieldGroup #Norm : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : resource_ID,       Label : 'Resource' },
      { $Type : 'UI.DataField', Value : activity,          Label : 'Activity' },
      { $Type : 'UI.DataField', Value : crewComposition,   Label : 'Crew composition' },
      { $Type : 'UI.DataField', Value : outputPerHr,       Label : 'Output per hour' },
      { $Type : 'UI.DataField', Value : outputPerManday8h, Label : 'Output per 8h manday' },
      { $Type : 'UI.DataField', Value : outputUoM,         Label : 'Unit of measure' },
    ],
  },

  /**
   * What makes this a recipe rather than a reference figure. The build-up of a
   * bill line resolves through the line's CBS leaf, so a norm with no linked
   * CBS is never picked up by a generation run.
   */
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

annotate service.ProductivityRates with {
  activity          @title : 'Activity';
  crewComposition   @title : 'Crew composition';
  outputPerHr       @title : 'Output per hour';
  outputPerManday8h @title : 'Output per 8h manday';
  outputUoM         @title : 'Unit of measure';
  basis             @title : 'Basis';
  effectiveFrom     @title : 'Effective from';

  resource @Common : {
    Text            : resource.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'Resources',
      Label          : 'Resource',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : resource_ID, ValueListProperty : 'ID' },
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
