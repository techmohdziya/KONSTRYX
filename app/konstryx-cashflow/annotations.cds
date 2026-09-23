using ProjectService as service from '../../srv/project-service';

/**
 * The spend curve: what each period was expected to cost, and what it did.
 *
 * Read as a chart and a table together. A cashflow is a shape before it is a
 * set of numbers — whether the curve is ahead of or behind plan is the whole
 * question, and a column of figures makes a reader construct that shape in
 * their head.
 *
 * Both halves. Money in on the period the cash arrives, money out on the
 * period the cost fell, and the running position through them - which goes
 * negative through the middle of every job, because a contractor pays for a
 * month's work inside that month and is paid for it two months later. The
 * depth of that trough is what the job has to fund.
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
  /**
   * The two curves as aggregated measures.
   *
   * A chart measure is a total the service computes, not a column the table
   * happens to show, so each one names the property it sums and how.
   */
  Analytics.AggregatedProperty #plannedCurve : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'plannedCurve',
    AggregatableProperty : plannedOutCum,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Planned, cumulative',
  },
  Analytics.AggregatedProperty #actualCurve : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'actualCurve',
    AggregatableProperty : actualOutCum,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Actual, cumulative',
  },
  Analytics.AggregatedProperty #inflow : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'inflow',
    AggregatableProperty : cashIn,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Cash in',
  },
  /**
   * The outflow negated, so the bars fall below the axis.
   *
   * Cost is a positive number everywhere else in this model. Charting it
   * downward is a statement about direction, not about sign, and the column
   * beside it in the table still reads as money spent.
   */
  Analytics.AggregatedProperty #outflow : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'outflow',
    AggregatableProperty : cashOutSigned,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Cash out',
  },
  Analytics.AggregatedProperty #position : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'position',
    AggregatableProperty : cumPosition,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Net position',
  },

  /**
   * Planned and actual as two lines over the same axis, cumulative rather
   * than per period: a monthly bar chart of spend answers "was March busy",
   * and the question a cashflow is opened for is "are we ahead or behind",
   * which only the running total answers.
   */
  /**
   * The valley: cash in above the line, cash out below it, and the running
   * position drawn through both.
   *
   * First of the two charts because it is the one a reader opens this app
   * for. The spend curve below answers whether the job is ahead of budget;
   * this one answers whether it can pay for next month.
   */
  UI.Chart #Valley : {
    $Type               : 'UI.ChartDefinitionType',
    Title               : 'Cash in, cash out and the running position',
    ChartType           : #Column,
    Dimensions          : [ periodName ],
    DimensionAttributes : [
      { $Type : 'UI.ChartDimensionAttributeType', Dimension : periodName,
        Role : #Category },
    ],
    DynamicMeasures     : [
      '@Analytics.AggregatedProperty#inflow',
      '@Analytics.AggregatedProperty#outflow',
      '@Analytics.AggregatedProperty#position',
    ],
    MeasureAttributes   : [
      { $Type : 'UI.ChartMeasureAttributeType',
        DynamicMeasure : '@Analytics.AggregatedProperty#inflow', Role : #Axis1 },
      { $Type : 'UI.ChartMeasureAttributeType',
        DynamicMeasure : '@Analytics.AggregatedProperty#outflow', Role : #Axis1 },
      { $Type : 'UI.ChartMeasureAttributeType',
        DynamicMeasure : '@Analytics.AggregatedProperty#position', Role : #Axis2 },
    ],
  },

  UI.Chart #Curve : {
    $Type               : 'UI.ChartDefinitionType',
    Title               : 'Planned against actual, cumulative',
    ChartType           : #Line,
    Dimensions          : [ periodName ],
    DimensionAttributes : [
      { $Type : 'UI.ChartDimensionAttributeType', Dimension : periodName,
        Role : #Category },
    ],
    DynamicMeasures     : [
      '@Analytics.AggregatedProperty#plannedCurve',
      '@Analytics.AggregatedProperty#actualCurve',
    ],
  },

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    // Oldest first: a curve read backwards is not a curve.
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : startDate,
                         Descending : false } ],
    Visualizations : [ '@UI.Chart#Valley', '@UI.LineItem' ],
  },

  /**
   * One row per period, read left to right as the money moves: what the work
   * was valued at, what was held back, what that leaves certified, what
   * actually arrived, what went out, and where that puts the job.
   */
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : projectCode,      Label : 'Project' },
    { $Type : 'UI.DataField', Value : periodName,       Label : 'Period' },
    { $Type : 'UI.DataField', Value : billedGross,      Label : 'Valued' },
    { $Type : 'UI.DataField', Value : retentionPct,     Label : 'Retention %' },
    { $Type : 'UI.DataField', Value : retentionHeld,    Label : 'Retention held' },
    { $Type : 'UI.DataField', Value : netCertified,     Label : 'Net certified' },
    { $Type : 'UI.DataField', Value : advanceRecovery,  Label : 'Advance recovered' },
    { $Type : 'UI.DataField', Value : cashIn,           Label : 'Cash in' },
    { $Type : 'UI.DataField', Value : actualOut,        Label : 'Cash out' },
    { $Type : 'UI.DataField', Value : netMonthly,       Label : 'Net this period' },
    { $Type : 'UI.DataField', Value : cumPosition,      Label : 'Position',
      Criticality : positionCriticality },
    { $Type : 'UI.DataField', Value : lagDays,          Label : 'Lag (days)' },
    { $Type : 'UI.DataField', Value : plannedOut,       Label : 'Planned spend' },
    { $Type : 'UI.DataField', Value : variance,         Label : 'Spend variance' },
    { $Type : 'UI.DataField', Value : actualOutCum,     Label : 'Spent to date' },
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
