using ProjectService as service from '../../srv/project-service';

/**
 * Project 360 — one project on one page.
 *
 * The project object page already held all of this across seven facets, which
 * answers "show me the bills" and does not answer "how is this project doing".
 * Nothing here is new information; what is new is that the answer is one
 * screen rather than seven clicks and a mental total.
 *
 * The header carries the five figures a project manager is actually asked
 * about — margin, cost index, complete, budget used, slip. A page that opens
 * on a table makes the reader do the summarising the page exists to do.
 */
annotate service.ProjectOverviews with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Project',
    TypeNamePlural : 'Project 360',
    Title          : { $Type : 'UI.DataField', Value : code },
    Description    : { $Type : 'UI.DataField', Value : name },
  },

  UI.SelectionFields : [ code, stage, companyName ],

  /**
   * Each header figure is a DataPoint rather than a field, so it renders as a
   * number with its own colour, and each takes the criticality the projection
   * computed — the thresholds live once, on the service.
   */
  UI.DataPoint #Margin : {
    $Type       : 'UI.DataPointType',
    Value       : forecastMarginPct,
    Title       : 'Forecast margin %',
    Criticality : marginCriticality,
  },
  UI.DataPoint #CPI : {
    $Type       : 'UI.DataPointType',
    Value       : cpi,
    Title       : 'Cost performance',
    Criticality : cpiCriticality,
  },
  UI.DataPoint #Complete : {
    $Type       : 'UI.DataPointType',
    Value       : percentComplete,
    Title       : 'Complete %',
    TargetValue : 100,
  },
  UI.DataPoint #BudgetUsed : {
    $Type       : 'UI.DataPointType',
    Value       : budgetUsedPct,
    Title       : 'Budget used %',
    TargetValue : 100,
    Criticality : budgetCriticality,
  },
  UI.DataPoint #Slip : {
    $Type       : 'UI.DataPointType',
    Value       : slipDays,
    Title       : 'Slip (days)',
    Criticality : slipCriticality,
  },

  UI.HeaderFacets : [
    { $Type : 'UI.ReferenceFacet', ID : 'hMargin',   Target : '@UI.DataPoint#Margin' },
    { $Type : 'UI.ReferenceFacet', ID : 'hCPI',      Target : '@UI.DataPoint#CPI' },
    { $Type : 'UI.ReferenceFacet', ID : 'hComplete', Target : '@UI.DataPoint#Complete' },
    { $Type : 'UI.ReferenceFacet', ID : 'hBudget',   Target : '@UI.DataPoint#BudgetUsed' },
    { $Type : 'UI.ReferenceFacet', ID : 'hSlip',     Target : '@UI.DataPoint#Slip' },
  ],

  /** The portfolio, one row per project. */
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,              Label : 'Project' },
    { $Type : 'UI.DataField', Value : name,              Label : 'Name' },
    { $Type : 'UI.DataField', Value : stage,             Label : 'Stage' },
    { $Type : 'UI.DataField', Value : contractValue,     Label : 'Contract' },
    { $Type : 'UI.DataField', Value : budgetTotal,       Label : 'Budget' },
    { $Type : 'UI.DataField', Value : budgetUsedPct,     Label : 'Budget used %',
      Criticality : budgetCriticality },
    { $Type : 'UI.DataField', Value : percentComplete,   Label : 'Complete %' },
    { $Type : 'UI.DataField', Value : cpi,               Label : 'CPI',
      Criticality : cpiCriticality },
    { $Type : 'UI.DataField', Value : forecastMarginPct, Label : 'Margin %',
      Criticality : marginCriticality },
    { $Type : 'UI.DataField', Value : slipDays,          Label : 'Slip (d)',
      Criticality : slipCriticality },
    { $Type : 'UI.DataField', Value : openRequests,      Label : 'Open requests' },
    { $Type : 'UI.DataField', Value : unsignedDays,      Label : 'Unsigned days' },
  ],

  UI.FieldGroup #Identity : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code,        Label : 'Project' },
      { $Type : 'UI.DataField', Value : name,        Label : 'Name' },
      { $Type : 'UI.DataField', Value : stage,       Label : 'Stage' },
      { $Type : 'UI.DataField', Value : companyName, Label : 'Company' },
      { $Type : 'UI.DataField', Value : startDate,   Label : 'Start' },
      { $Type : 'UI.DataField', Value : endDate,     Label : 'Contract finish' },
    ],
  },

  /**
   * The contract and the bills side by side. They differ by preliminaries and
   * provisional sums, and a page showing only one hides the gap between what
   * was signed and what has been priced.
   */
  UI.FieldGroup #Money : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : contractValue, Label : 'Contract value' },
      { $Type : 'UI.DataField', Value : boqValue,      Label : 'Priced bills' },
      { $Type : 'UI.DataField', Value : budgetTotal,   Label : 'Budget' },
      { $Type : 'UI.DataField', Value : committed,     Label : 'Committed' },
      { $Type : 'UI.DataField', Value : encumbered,    Label : 'Encumbered' },
      { $Type : 'UI.DataField', Value : actual,        Label : 'Actual' },
      { $Type : 'UI.DataField', Value : available,     Label : 'Available' },
      { $Type : 'UI.DataField', Value : budgetUsedPct, Label : 'Budget used %',
        Criticality : budgetCriticality },
    ],
  },

  UI.FieldGroup #Performance : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : earnedValue,       Label : 'Earned value' },
      { $Type : 'UI.DataField', Value : actualCost,        Label : 'Actual cost' },
      { $Type : 'UI.DataField', Value : cpi,               Label : 'Cost performance index',
        Criticality : cpiCriticality },
      { $Type : 'UI.DataField', Value : percentComplete,   Label : 'Complete %' },
      { $Type : 'UI.DataField', Value : forecastMargin,    Label : 'Forecast margin',
        Criticality : marginCriticality },
      { $Type : 'UI.DataField', Value : forecastMarginPct, Label : 'Margin %',
        Criticality : marginCriticality },
      { $Type : 'UI.DataField', Value : measuredPeriod,    Label : 'Measured in' },
    ],
  },

  UI.FieldGroup #Programme : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : activitiesTotal,    Label : 'Activities' },
      { $Type : 'UI.DataField', Value : activitiesDone,     Label : 'Finished' },
      { $Type : 'UI.DataField', Value : activitiesCritical, Label : 'On the critical path' },
      { $Type : 'UI.DataField', Value : scheduleFinish,     Label : 'Forecast finish' },
      { $Type : 'UI.DataField', Value : slipDays,           Label : 'Slip (days)',
        Criticality : slipCriticality },
    ],
  },

  /**
   * What is waiting on a person. Not a summary — every number here is a queue,
   * and a project manager reads this page to decide which one to open next.
   */
  UI.FieldGroup #Worklist : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : openRequests,       Label : 'Open resource requests' },
      { $Type : 'UI.DataField', Value : unsignedDays,       Label : 'Daily logs unsigned' },
      { $Type : 'UI.DataField', Value : requisitionsUnsent, Label : 'Requisitions without an ERP number' },
      { $Type : 'UI.DataField', Value : linesOverBudget,    Label : 'Budget lines overspent' },
      { $Type : 'UI.DataField', Value : certifiedNet,       Label : 'Certified to subcontractors' },
    ],
  },

  UI.FieldGroup #Basis : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : note,        Label : 'What is not computed' },
      { $Type : 'UI.DataField', Value : refreshedAt, Label : 'Read at' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Identity', Label : 'The project',
      Target : '@UI.FieldGroup#Identity' },
    { $Type : 'UI.ReferenceFacet', ID : 'Money', Label : 'Money',
      Target : '@UI.FieldGroup#Money' },
    { $Type : 'UI.ReferenceFacet', ID : 'Performance', Label : 'Performance',
      Target : '@UI.FieldGroup#Performance' },
    { $Type : 'UI.ReferenceFacet', ID : 'Programme', Label : 'Programme',
      Target : '@UI.FieldGroup#Programme' },
    { $Type : 'UI.ReferenceFacet', ID : 'Worklist', Label : 'Waiting on someone',
      Target : '@UI.FieldGroup#Worklist' },
    { $Type : 'UI.ReferenceFacet', ID : 'Basis', Label : 'Basis',
      Target : '@UI.FieldGroup#Basis' },
  ],
);

annotate service.ProjectOverviews with {
  code               @title : 'Project';
  name               @title : 'Name';
  stage              @title : 'Stage';
  companyName        @title : 'Company';
  contractValue      @title : 'Contract value';
  boqValue           @title : 'Priced bills';
  budgetTotal        @title : 'Budget';
  committed          @title : 'Committed';
  encumbered         @title : 'Encumbered';
  actual             @title : 'Actual';
  available          @title : 'Available';
  budgetUsedPct      @title : 'Budget used %';
  earnedValue        @title : 'Earned value';
  actualCost         @title : 'Actual cost';
  cpi                @title : 'Cost performance index';
  percentComplete    @title : 'Complete %';
  forecastMargin     @title : 'Forecast margin';
  forecastMarginPct  @title : 'Margin %';
  measuredPeriod     @title : 'Measured in';
  activitiesTotal    @title : 'Activities';
  activitiesDone     @title : 'Finished';
  activitiesCritical @title : 'On the critical path';
  scheduleFinish     @title : 'Forecast finish';
  slipDays           @title : 'Slip (days)';
  openRequests       @title : 'Open resource requests';
  unsignedDays       @title : 'Daily logs unsigned';
  requisitionsUnsent @title : 'Requisitions without an ERP number';
  linesOverBudget    @title : 'Budget lines overspent';
  certifiedNet       @title : 'Certified to subcontractors';
  note               @title : 'What is not computed';
  refreshedAt        @title : 'Read at';
  marginCriticality  @UI.Hidden;
  cpiCriticality     @UI.Hidden;
  budgetCriticality  @UI.Hidden;
  slipCriticality    @UI.Hidden;
};
