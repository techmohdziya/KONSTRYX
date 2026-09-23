using ProjectService as service from '../../srv/project-service';

/**
 * Cost Value Reconciliation — what a project is worth, what it has cost, and
 * what it will cost, measured once per period and kept.
 *
 * Kept rather than recomputed on demand, which is what makes it a report: a
 * margin on its own says far less than the same margin falling for three
 * months, and a figure recomputed later cannot be compared with what was
 * reported at the time because the quantities and hours behind it have moved.
 *
 * Two columns on this screen are deliberately empty. Planned value and the
 * schedule index need the budget time-phased across the programme, and nothing
 * phases it yet — so they come back null with the reason on the row rather than
 * as an approximation. A schedule index computed from a guess is
 * indistinguishable on a board pack from one computed from a plan.
 */
annotate service.PeriodReports with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Period Report',
    TypeNamePlural : 'Cost Value Reconciliation',
    Title          : { $Type : 'UI.DataField', Value : project.code },
    Description    : { $Type : 'UI.DataField', Value : periodName },
  },

  UI.SelectionFields : [ project_ID, periodName, companyCcy_code ],

  /**
   * Worth, earned, spent, and what it is forecast to make. In that order
   * because that is the order the question is asked in, and with the margin
   * carrying its colour so a loss is visible without reading the number.
   */
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : project.code,      Label : 'Project' },
    { $Type : 'UI.DataField', Value : periodName,        Label : 'Period' },
    { $Type : 'UI.DataField', Value : adjustedValue,     Label : 'Worth' },
    { $Type : 'UI.DataField', Value : earnedValue,       Label : 'Earned' },
    { $Type : 'UI.DataField', Value : percentComplete,   Label : 'Complete %' },
    { $Type : 'UI.DataField', Value : actualCost,        Label : 'Spent' },
    { $Type : 'UI.DataField', Value : costVariance,      Label : 'Cost variance' },
    { $Type : 'UI.DataField', Value : cpi,               Label : 'CPI',
      Criticality : cpiCriticality },
    // Beside CPI rather than instead of it. CPI is earned revenue over cost and
    // carries the contract's margin inside it; this is the same work priced at
    // what it was budgeted to cost, so performance and margin read apart.
    { $Type : 'UI.DataField', Value : costCPI,           Label : 'Cost CPI' },
    { $Type : 'UI.DataField', Value : forecastCost,      Label : 'Forecast cost' },
    { $Type : 'UI.DataField', Value : forecastMargin,    Label : 'Forecast margin',
      Criticality : marginCriticality },
    { $Type : 'UI.DataField', Value : forecastMarginPct, Label : 'Margin %',
      Criticality : marginCriticality },
    { $Type : 'UI.DataField', Value : takenAt,           Label : 'Measured' },
  ],

  UI.FieldGroup #Value : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : contractValue, Label : 'Contract value' },
      { $Type : 'UI.DataField', Value : variations,    Label : 'Variations' },
      { $Type : 'UI.DataField', Value : adjustedValue, Label : 'Adjusted value' },
      { $Type : 'UI.DataField', Value : companyCcy_code, Label : 'Currency' },
    ],
  },

  UI.FieldGroup #Earned : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : earnedValue,     Label : 'Earned value' },
      { $Type : 'UI.DataField', Value : percentComplete, Label : 'Complete %' },
      { $Type : 'UI.DataField', Value : actualCost,      Label : 'Actual cost' },
      { $Type : 'UI.DataField', Value : costVariance,    Label : 'Cost variance' },
      { $Type : 'UI.DataField', Value : cpi,             Label : 'Cost performance index',
        Criticality : cpiCriticality },
      { $Type : 'UI.DataField', Value : earnedCost,      Label : 'Earned cost (budgeted cost of work done)' },
      { $Type : 'UI.DataField', Value : costCPI,         Label : 'Cost CPI (earned cost / spent)' },
      { $Type : 'UI.DataField', Value : plannedValue,    Label : 'Planned value' },
      { $Type : 'UI.DataField', Value : scheduleVariance, Label : 'Schedule variance' },
      { $Type : 'UI.DataField', Value : spi,             Label : 'Schedule performance index' },
      { $Type : 'UI.DataField', Value : costSPI,         Label : 'Cost SPI (earned cost / planned)' },
    ],
  },

  UI.FieldGroup #Forecast : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : costToDate,      Label : 'Cost to date' },
      // The two halves of it, because they are written by different events and
      // a reader asked to act on the total needs to know which one moved.
      // Signed labour is the daily logs; stock issued is material drawn from a
      // store, whose goods issue is the cost.
      { $Type : 'UI.DataField', Value : signedLabourCost, Label : 'of which signed labour' },
      { $Type : 'UI.DataField', Value : stockIssuedCost,  Label : 'of which stock issued' },
      { $Type : 'UI.DataField', Value : costToComplete,  Label : 'Cost to complete' },
      { $Type : 'UI.DataField', Value : forecastCost,    Label : 'Forecast cost' },
      { $Type : 'UI.DataField', Value : forecastMargin,  Label : 'Forecast margin',
        Criticality : marginCriticality },
      { $Type : 'UI.DataField', Value : forecastMarginPct, Label : 'Margin %',
        Criticality : marginCriticality },
    ],
  },

  /**
   * The same figures in the group's presentation currency, and the rate that
   * got them there. A group reporting at the average rate and one reporting at
   * the closing rate are both right, and a figure that does not say which it
   * used cannot be reconciled against anyone else's.
   */
  UI.FieldGroup #Group : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : groupCcy_code,       Label : 'Group currency' },
      { $Type : 'UI.DataField', Value : rateType,            Label : 'Rate type' },
      { $Type : 'UI.DataField', Value : rateApplied,         Label : 'Rate applied' },
      { $Type : 'UI.DataField', Value : adjustedValueGroup,  Label : 'Adjusted value' },
      { $Type : 'UI.DataField', Value : forecastCostGroup,   Label : 'Forecast cost' },
      { $Type : 'UI.DataField', Value : forecastMarginGroup, Label : 'Forecast margin' },
    ],
  },

  /**
   * What could not be computed, and why. First on the page rather than last:
   * a margin that flatters because only labour is costed is a margin nobody
   * should read before they have read this.
   */
  UI.FieldGroup #Caveats : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : note, Label : 'Read this first' },
      { $Type : 'UI.DataField', Value : takenAt, Label : 'Measured at' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Caveats', Label : 'Basis',
      Target : '@UI.FieldGroup#Caveats' },
    { $Type : 'UI.ReferenceFacet', ID : 'Value', Label : 'What it is worth',
      Target : '@UI.FieldGroup#Value' },
    { $Type : 'UI.ReferenceFacet', ID : 'Earned', Label : 'Earned against spent',
      Target : '@UI.FieldGroup#Earned' },
    { $Type : 'UI.ReferenceFacet', ID : 'Forecast', Label : 'Forecast',
      Target : '@UI.FieldGroup#Forecast' },
    { $Type : 'UI.ReferenceFacet', ID : 'Group', Label : 'Group currency',
      Target : '@UI.FieldGroup#Group' },
  ],
);

annotate service.PeriodReports with {
  periodName        @title : 'Period';
  contractValue     @title : 'Contract value';
  variations        @title : 'Variations';
  adjustedValue     @title : 'Adjusted value';
  plannedValue      @title : 'Planned value';
  earnedValue       @title : 'Earned value';
  actualCost        @title : 'Actual cost';
  costVariance      @title : 'Cost variance';
  scheduleVariance  @title : 'Schedule variance';
  cpi               @title : 'Cost performance index';
  earnedCost        @title : 'Earned cost';
  costCPI           @title : 'Cost performance index (cost basis)';
  costSPI           @title : 'Schedule performance index (cost basis)';
  spi               @title : 'Schedule performance index';
  costToDate        @title : 'Cost to date';
  signedLabourCost  @title : 'Signed labour cost';
  stockIssuedCost   @title : 'Stock issued cost';
  costToComplete    @title : 'Cost to complete';
  forecastCost      @title : 'Forecast cost';
  forecastMargin    @title : 'Forecast margin';
  forecastMarginPct @title : 'Margin %';
  percentComplete   @title : 'Complete %';
  rateType          @title : 'Rate type';
  rateApplied       @title : 'Rate applied';
  note              @title : 'Basis';
  takenAt           @title : 'Measured at';
  marginCriticality @UI.Hidden;
  cpiCriticality    @UI.Hidden;

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

/**
 * The reconciliation as analytics: earned value, planned value and actual
 * cost side by side, per project.
 *
 * The three curves of earned value management in one picture. A reader can
 * see at a glance which projects have earned more than they have spent and
 * which have spent against nothing measured - the shape the CPI and SPI
 * columns express as numbers and nobody reads across five rows.
 */
annotate service.PeriodReports with @(
  Analytics.AggregatedProperty #evTotal : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'evTotal',
    AggregatableProperty : earnedValue,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Earned value',
  },
  Analytics.AggregatedProperty #pvTotal : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'pvTotal',
    AggregatableProperty : plannedValue,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Planned value',
  },
  Analytics.AggregatedProperty #acTotal : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'acTotal',
    AggregatableProperty : actualCost,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Actual cost',
  },
  Analytics.AggregatedProperty #ecTotal : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'ecTotal',
    AggregatableProperty : earnedCost,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Earned cost',
  },

  /** The classic three, which is what earned value management is. */
  UI.Chart #alpChart : {
    $Type               : 'UI.ChartDefinitionType',
    Title               : 'Planned, earned and spent',
    ChartType           : #Column,
    Dimensions          : [ projectCode ],
    DimensionAttributes : [
      { $Type : 'UI.ChartDimensionAttributeType', Dimension : projectCode, Role : #Category },
    ],
    DynamicMeasures     : [
      '@Analytics.AggregatedProperty#pvTotal',
      '@Analytics.AggregatedProperty#evTotal',
      '@Analytics.AggregatedProperty#acTotal',
    ],
  },

  /**
   * Earned cost against actual cost: the comparison with the contract margin
   * taken out of it, and the only pair on this page measured in the same unit.
   */
  UI.Chart #costBasis : {
    $Type               : 'UI.ChartDefinitionType',
    Title               : 'Earned cost against actual',
    ChartType           : #Column,
    Dimensions          : [ projectCode ],
    DimensionAttributes : [
      { $Type : 'UI.ChartDimensionAttributeType', Dimension : projectCode, Role : #Category },
    ],
    DynamicMeasures     : [
      '@Analytics.AggregatedProperty#ecTotal',
      '@Analytics.AggregatedProperty#acTotal',
    ],
  },
);

annotate service.PeriodReports with {
  projectCode @title : 'Project';
}
