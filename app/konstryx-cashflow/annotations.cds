using ProjectService as service from '../../srv/project-service';

/**
 * The spend curve: what each period was expected to cost, and what it did.
 *
 * Read as a chart and a table together. A cashflow is a shape before it is a
 * set of numbers — whether the curve is ahead of or behind plan is the whole
 * question, and a column of figures makes a reader construct that shape in
 * their head.
 *
 * Cost out only, and every row says so. Client payment applications are not
 * modelled, so a money-in line would be invented; an empty revenue column
 * would read as a project earning nothing, which is a worse answer than the
 * absence stated in words.
 */
annotate service.Cashflow with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Period',
    TypeNamePlural : 'Project Cashflow',
    Title          : { $Type : 'UI.DataField', Value : periodName },
    Description    : { $Type : 'UI.DataField', Value : project.code },
  },

  UI.SelectionFields : [ projectCode, periodName ],

  /**
   * Planned and actual as two lines over the same axis, cumulative rather
   * than per period: a monthly bar chart of spend answers "was March busy",
   * and the question a cashflow is opened for is "are we ahead or behind",
   * which only the running total answers.
   */
  UI.Chart #Curve : {
    $Type               : 'UI.ChartDefinitionType',
    ChartType           : #Line,
    Dimensions          : [ periodName ],
    Measures            : [ plannedOutCum, actualOutCum ],
    MeasureAttributes   : [
      { $Type : 'UI.ChartMeasureAttributeType', Measure : plannedOutCum,
        Role : #Axis1 },
      { $Type : 'UI.ChartMeasureAttributeType', Measure : actualOutCum,
        Role : #Axis1 },
    ],
  },

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    // Oldest first: a curve read backwards is not a curve.
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : startDate,
                         Descending : false } ],
    Visualizations : [ '@UI.Chart#Curve', '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : project.code,   Label : 'Project' },
    { $Type : 'UI.DataField', Value : periodName,     Label : 'Period' },
    { $Type : 'UI.DataField', Value : plannedOut,     Label : 'Planned' },
    { $Type : 'UI.DataField', Value : actualOut,      Label : 'Actual' },
    { $Type : 'UI.DataField', Value : variance,       Label : 'Variance' },
    { $Type : 'UI.DataField', Value : plannedOutCum,  Label : 'Planned to date' },
    { $Type : 'UI.DataField', Value : actualOutCum,   Label : 'Actual to date' },
    { $Type : 'UI.DataField', Value : varianceCum,    Label : 'Variance to date' },
    { $Type : 'UI.DataField', Value : envelopePct,    Label : 'From straight-line %' },
  ],

  UI.FieldGroup #Period : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : project.code, Label : 'Project' },
      { $Type : 'UI.DataField', Value : periodName,   Label : 'Period' },
      { $Type : 'UI.DataField', Value : startDate,    Label : 'From' },
      { $Type : 'UI.DataField', Value : endDate,      Label : 'To' },
      { $Type : 'UI.DataField', Value : ccy_code,     Label : 'Currency' },
    ],
  },

  UI.FieldGroup #Amounts : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : plannedOut,    Label : 'Planned this period' },
      { $Type : 'UI.DataField', Value : actualOut,     Label : 'Actual this period' },
      { $Type : 'UI.DataField', Value : variance,      Label : 'Variance' },
      { $Type : 'UI.DataField', Value : plannedOutCum, Label : 'Planned to date' },
      { $Type : 'UI.DataField', Value : actualOutCum,  Label : 'Actual to date' },
      { $Type : 'UI.DataField', Value : varianceCum,   Label : 'Variance to date' },
    ],
  },

  /**
   * How much of this period's plan is a straight-line spread rather than a
   * forecast. A budget line that could not be traced to dated work is spread
   * evenly across the project, and the resulting curve looks identical to one
   * built from the programme.
   */
  UI.FieldGroup #Basis : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : envelopePct, Label : 'From straight-line spread %' },
      { $Type : 'UI.DataField', Value : note,        Label : 'What this curve is' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Period', Label : 'Period',
      Target : '@UI.FieldGroup#Period' },
    { $Type : 'UI.ReferenceFacet', ID : 'Amounts', Label : 'Amounts',
      Target : '@UI.FieldGroup#Amounts' },
    { $Type : 'UI.ReferenceFacet', ID : 'Basis', Label : 'Basis',
      Target : '@UI.FieldGroup#Basis' },
  ],
);

annotate service.Cashflow with {
  periodName    @title : 'Period';
  startDate     @title : 'From';
  endDate       @title : 'To';
  plannedOut    @title : 'Planned';
  plannedOutCum @title : 'Planned to date';
  actualOut     @title : 'Actual';
  actualOutCum  @title : 'Actual to date';
  variance      @title : 'Variance';
  varianceCum   @title : 'Variance to date';
  envelopePct   @title : 'From straight-line spread %';
  note          @title : 'What this curve is';

  project @Common : {
    Text            : project.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'Projects',
      Label          : 'Project',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : project_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' }
      ]
    }
  };
};

/** The project as a person names it, not as the service keys it. */
annotate service.Cashflow with {
  projectCode @title : 'Project';
  projectName @title : 'Project name';
}
