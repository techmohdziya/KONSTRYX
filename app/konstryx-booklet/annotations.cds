using ProjectService as service from '../../srv/project-service';

/**
 * The financial booklet: revenue, cost and margin for every project, side by
 * side, for a period the reader picks.
 *
 * Modelled on the S/4 Project Financial Booklet, which answers one question
 * across a portfolio - where is the margin - rather than one project in depth.
 * The Cost Value Reconciliation app shows a single project's reconciliation
 * with its caveats; this shows every project's bottom line next to every
 * other, which is the view a commercial review actually opens on.
 *
 * Two pairs of columns and the gap between them. Planned revenue and planned
 * cost are what the contract and the budget said; recognised revenue and
 * recognised cost are what has been measured and spent. A booklet that showed
 * only one pair would answer half the question, and the half it answered would
 * be the half nobody argues about.
 */
annotate service.Booklet with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Project',
    TypeNamePlural : 'Project Margin Overview',
    Title          : { $Type : 'UI.DataField', Value : project.code },
    Description    : { $Type : 'UI.DataField', Value : periodName },
  },

  /**
   * The filter bar. Fiscal period first because a booklet is always read for
   * one - "the margin" with no period on it is not a figure anybody can act
   * on - then the project and the currency the figures are stated in.
   */
  UI.SelectionFields : [ periodName, projectCode, companyCcy_code ],

  /**
   * The margin overview, in the order the question is asked: what we planned
   * to earn and spend, what we have earned and spent, and what that leaves.
   *
   * Recognised revenue is measured work at contract rates and recognised cost
   * is what that work cost, so the margin between them is the one the site has
   * actually produced. The forecast margin further along is a different figure
   * answering a different question, and both belong here for exactly that
   * reason.
   */
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : project.code,      Label : 'Project' },
    { $Type : 'UI.DataField', Value : project.name,      Label : 'Name' },
    { $Type : 'UI.DataField', Value : periodName,        Label : 'Period' },
    { $Type : 'UI.DataField', Value : adjustedValue,     Label : 'Planned revenue' },
    { $Type : 'UI.DataField', Value : plannedValue,      Label : 'Planned cost' },
    { $Type : 'UI.DataField', Value : earnedValue,       Label : 'Recognised revenue' },
    { $Type : 'UI.DataField', Value : actualCost,        Label : 'Recognised cost' },
    { $Type : 'UI.DataField', Value : costVariance,      Label : 'Recognised margin' },
    { $Type : 'UI.DataField', Value : percentComplete,   Label : 'Complete %' },
    { $Type : 'UI.DataField', Value : forecastMargin,    Label : 'Forecast margin',
      Criticality : marginCriticality },
    { $Type : 'UI.DataField', Value : forecastMarginPct, Label : 'Forecast margin %',
      Criticality : marginCriticality },
  ],

  /**
   * The measures, declared as aggregations rather than columns.
   *
   * A chart measure is a total the service computes, not a field the table
   * happens to show, so each one names the property it sums and the method it
   * sums it by. Without these the chart has nothing to draw and Fiori Elements
   * renders an empty frame.
   */
  Analytics.AggregatedProperty #plannedRevenue : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'plannedRevenue',
    AggregatableProperty : adjustedValue,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Planned revenue',
  },
  Analytics.AggregatedProperty #recognisedRevenue : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'recognisedRevenue',
    AggregatableProperty : earnedValue,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Recognised revenue',
  },
  Analytics.AggregatedProperty #recognisedCost : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'recognisedCost',
    AggregatableProperty : actualCost,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Recognised cost',
  },
  Analytics.AggregatedProperty #marginTotal : {
    $Type                : 'Analytics.AggregatedPropertyType',
    Name                 : 'marginTotal',
    AggregatableProperty : forecastMargin,
    AggregationMethod    : 'sum',
    @Common.Label        : 'Forecast margin',
  },

  /**
   * The chart the page opens on: planned revenue against what has actually
   * been recognised and spent, one column group per project.
   *
   * A reader scanning five projects for the one that has stopped earning sees
   * it here before reading a single number.
   */
  UI.Chart #alpChart : {
    $Type               : 'UI.ChartDefinitionType',
    Title               : 'Planned against recognised',
    ChartType           : #Column,
    Dimensions          : [ projectName ],
    DimensionAttributes : [
      { $Type : 'UI.ChartDimensionAttributeType', Dimension : projectName, Role : #Category },
    ],
    DynamicMeasures     : [
      '@Analytics.AggregatedProperty#plannedRevenue',
      '@Analytics.AggregatedProperty#recognisedRevenue',
      '@Analytics.AggregatedProperty#recognisedCost',
    ],
  },

  /** The margin on its own, which is the column a review actually stops on. */
  UI.Chart #marginChart : {
    $Type               : 'UI.ChartDefinitionType',
    Title               : 'Forecast margin by project',
    ChartType           : #Bar,
    Dimensions          : [ projectName ],
    DimensionAttributes : [
      { $Type : 'UI.ChartDimensionAttributeType', Dimension : projectName, Role : #Category },
    ],
    DynamicMeasures     : [ '@Analytics.AggregatedProperty#marginTotal' ],
  },

  /**
   * The object page: one project's booklet page, with the indices that say
   * whether its margin is a measurement or an artefact.
   *
   * The cost-basis pair sits beside the revenue-basis one deliberately. On a
   * job whose budget covers part of its bill the revenue indices read absurdly
   * high, and a booklet that printed only those would be quoting the contract
   * margin as site performance.
   */
  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Margin', Label : 'Margin',
      Target : '@UI.FieldGroup#BookletMargin' },
    { $Type : 'UI.ReferenceFacet', ID : 'Indices', Label : 'Performance',
      Target : '@UI.FieldGroup#BookletIndices' },
    { $Type : 'UI.ReferenceFacet', ID : 'Caveats', Label : 'What this figure rests on',
      Target : '@UI.FieldGroup#BookletNote' },
  ],

  UI.FieldGroup #BookletMargin : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : contractValue,  Label : 'Contract value' },
      { $Type : 'UI.DataField', Value : variations,     Label : 'Approved variations' },
      { $Type : 'UI.DataField', Value : adjustedValue,  Label : 'Planned revenue' },
      { $Type : 'UI.DataField', Value : plannedValue,   Label : 'Planned cost to date' },
      { $Type : 'UI.DataField', Value : earnedValue,    Label : 'Recognised revenue' },
      { $Type : 'UI.DataField', Value : actualCost,     Label : 'Recognised cost' },
      { $Type : 'UI.DataField', Value : costVariance,   Label : 'Recognised margin' },
      { $Type : 'UI.DataField', Value : forecastCost,   Label : 'Forecast cost' },
      { $Type : 'UI.DataField', Value : forecastMargin, Label : 'Forecast margin',
        Criticality : marginCriticality },
      { $Type : 'UI.DataField', Value : forecastMarginPct, Label : 'Forecast margin %',
        Criticality : marginCriticality },
    ],
  },

  UI.FieldGroup #BookletIndices : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : percentComplete, Label : 'Complete %' },
      { $Type : 'UI.DataField', Value : earnedCost,      Label : 'Earned cost' },
      { $Type : 'UI.DataField', Value : cpi,             Label : 'CPI (revenue basis)',
        Criticality : cpiCriticality },
      { $Type : 'UI.DataField', Value : costCPI,         Label : 'Cost CPI' },
      { $Type : 'UI.DataField', Value : spi,             Label : 'SPI (revenue basis)' },
      { $Type : 'UI.DataField', Value : costSPI,         Label : 'Cost SPI' },
    ],
  },

  UI.FieldGroup #BookletNote : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : note, Label : 'Caveats' },
      { $Type : 'UI.DataField', Value : takenAt, Label : 'Measured' },
    ],
  },
);

/** The two columns the projection adds, named for a reader rather than a developer. */
annotate service.Booklet with {
  projectCode @title : 'Project';
  projectName @title : 'Project name';
}
