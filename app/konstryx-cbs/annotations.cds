using MasterDataService as service from '../../srv/masterdata-service';

/**
 * The Cost Breakdown Structure library — the three-level shape every project's
 * CBS is instantiated from.
 *
 * A project's own CBS carries the money; this carries the structure, and it is
 * the only place the shape is decided. Instantiating copies it into the project
 * rather than referencing it, so a later change to the library does not
 * silently reshape a job already being costed.
 *
 * Read as a tree, for the same reason the WBS and the resource catalogue are:
 * a breakdown that renders as a flat list of forty codes has broken nothing
 * down, and the level column is the only clue that any row belongs to another.
 */
annotate service.CBSLibrary with @(

  UI.PresentationVariant : {
    $Type                 : 'UI.PresentationVariantType',
    // Two levels: the phases and what sits under them. The third level is the
    // leaves a norm is keyed to, which is a search rather than a browse.
    InitialExpansionLevel : 2,
    // By code, so a breakdown reads 01.10, 01.20, 01.30 rather than in
    // whatever order the rows come back. A cost structure out of order is
    // one a reader has to sort in their head before they can use it.
    SortOrder             : [ { $Type : 'Common.SortOrderType',
                                Property : code, Descending : false } ],
    Visualizations        : [ '@UI.LineItem' ],
  },

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'CBS Node',
    TypeNamePlural : 'Cost Breakdown Library',
    Title          : { $Type : 'UI.DataField', Value : code },
    Description    : { $Type : 'UI.DataField', Value : name },
  },

  UI.SelectionFields : [ level, costNature, constructionType, scope ],

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,             Label : 'CBS' },
    // The node's own name, which it did not have until now. Every level-2 under
    // superstructure read "Super-structure" before, because the screen was
    // showing the phase for want of anything else.
    { $Type : 'UI.DataField', Value : name,             Label : 'Name' },
    { $Type : 'UI.DataField', Value : constructionType, Label : 'Construction type' },
    { $Type : 'UI.DataField', Value : phase,            Label : 'Phase' },
    { $Type : 'UI.DataField', Value : level,            Label : 'Level' },
    { $Type : 'UI.DataField', Value : costNature,       Label : 'Cost nature' },
    { $Type : 'UI.DataField', Value : allocBasis,       Label : 'Allocation basis' },
    { $Type : 'UI.DataField', Value : scope,            Label : 'Scope' },
    { $Type : 'UI.DataField', Value : masterStatus,     Label : 'Status' },
  ],

  UI.FieldGroup #Node : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code,             Label : 'CBS' },
      { $Type : 'UI.DataField', Value : name,             Label : 'Name' },
      { $Type : 'UI.DataField', Value : constructionType, Label : 'Construction type' },
      { $Type : 'UI.DataField', Value : phase,            Label : 'Phase' },
      { $Type : 'UI.DataField', Value : level,            Label : 'Level' },
      { $Type : 'UI.DataField', Value : parent_ID,        Label : 'Under' },
    ],
  },

  /**
   * How this node behaves when overheads are spread.
   *
   * A node either absorbs allocated cost or is a pool that gets spread, and
   * nothing carried the distinction before — which left the allocation engine
   * to take a hard-coded list of codes or to allocate an overhead onto an
   * overhead. That compounds silently and is invisible in the result, because
   * the total still reconciles.
   */
  UI.FieldGroup #Allocation : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : costNature, Label : 'Cost nature' },
      { $Type : 'UI.DataField', Value : allocBasis, Label : 'Allocation basis' },
    ],
  },

  UI.FieldGroup #Governance : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : scope,        Label : 'Scope' },
      { $Type : 'UI.DataField', Value : masterStatus, Label : 'Status' },
      { $Type : 'UI.DataField', Value : owningCompany_ID, Label : 'Owning company' },
    ],
  },

  UI.Identification : [
    { $Type  : 'UI.DataFieldForAction',
      Action : 'MasterDataService.requestPromotion',
      Label  : 'Request promotion to group' },
  ],

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Node', Label : 'Node',
      Target : '@UI.FieldGroup#Node' },
    { $Type : 'UI.ReferenceFacet', ID : 'Allocation', Label : 'Allocation',
      Target : '@UI.FieldGroup#Allocation' },
    { $Type : 'UI.ReferenceFacet', ID : 'Governance', Label : 'Governance',
      Target : '@UI.FieldGroup#Governance' },
  ],
);

annotate service.CBSLibrary with {
  name @title : 'Name';
  code             @title : 'CBS';
  constructionType @title : 'Construction type';
  phase            @title : 'Phase';
  level            @title : 'Level';
  costNature       @title : 'Cost nature';
  allocBasis       @title : 'Allocation basis';

  parent @Common : {
    Text            : parent.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'CBSLibrary',
      Label          : 'Parent node',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : parent_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly',
          ValueListProperty : 'constructionType' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'level' }
      ]
    }
  };
};
