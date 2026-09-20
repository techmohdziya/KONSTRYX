using BudgetService as service from '../../srv/budget-service';

annotate service.Budgets with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Budget',
    TypeNamePlural : 'Budgets',
    Title          : { $Type : 'UI.DataField', Value : docNo },
    Description    : { $Type : 'UI.DataField', Value : status },
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : docNo, Label : 'Budget' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : version, Label : 'Version' },
    { $Type : 'UI.DataField', Value : totalAmount, Label : 'Total' },
    { $Type : 'UI.DataField', Value : raisedBy, Label : 'Raised by' },
    { $Type : 'UI.DataField', Value : raisedOn, Label : 'Raised on' },
    { $Type : 'UI.DataField', Value : daysToLock, Label : 'Days to lock' },
  ],

  UI.FieldGroup #Details : {
    $Type : 'UI.FieldGroupType',
    Data  : [
    { $Type : 'UI.DataField', Value : docNo, Label : 'Budget' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : version, Label : 'Version' },
    { $Type : 'UI.DataField', Value : totalAmount, Label : 'Total' },
    { $Type : 'UI.DataField', Value : raisedBy, Label : 'Raised by' },
    { $Type : 'UI.DataField', Value : raisedOn, Label : 'Raised on' },
    { $Type : 'UI.DataField', Value : daysToLock, Label : 'Days to lock' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
    { $Type : 'UI.ReferenceFacet', ID : 'BudgetLines', Label : 'Budget Lines',
      Target : 'lines/@UI.LineItem' },
  ],
);

annotate service.BudgetLines with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Budget line',
    TypeNamePlural : 'Budget lines',
    Title          : { $Type : 'UI.DataField', Value : cbs.code },
    Description    : { $Type : 'UI.DataField', Value : category },
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : wbs_ID, Label : 'WBS element' },
    { $Type : 'UI.DataField', Value : cbs_ID, Label : 'CBS node' },
    { $Type : 'UI.DataField', Value : boqItem_ID, Label : 'Bill item' },
    { $Type : 'UI.DataField', Value : category, Label : 'Cost nature' },
    { $Type : 'UI.DataField', Value : amount, Label : 'Amount' },
    { $Type : 'UI.DataField', Value : authorised, Label : 'Authorised' },
    { $Type : 'UI.DataField', Value : committed, Label : 'Committed' },
    { $Type : 'UI.DataField', Value : encumbered, Label : 'Encumbered' },
    { $Type : 'UI.DataField', Value : actual, Label : 'Actual' },
    { $Type : 'UI.DataField', Value : available, Label : 'Available' },
    { $Type : 'UI.DataField', Value : availPct, Label : 'Available %' },
    { $Type : 'UI.DataField', Value : eac, Label : 'EAC' },
  ],

  /**
   * The three keys first, because they are what a line is looked up by. A
   * reader arrives at this table asking what a part of the works is budgeted
   * at, not what the fourth MR line of the job is.
   */
  UI.SelectionFields : [ wbs_ID, cbs_ID, boqItem_ID, category ],

  UI.FieldGroup #Control : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : wbs_ID, Label : 'WBS element' },
      { $Type : 'UI.DataField', Value : cbs_ID, Label : 'CBS node' },
      { $Type : 'UI.DataField', Value : boqItem_ID, Label : 'Bill item' },
      { $Type : 'UI.DataField', Value : category, Label : 'Cost nature' },
      { $Type : 'UI.DataField', Value : amount, Label : 'Budget' },
      { $Type : 'UI.DataField', Value : committed, Label : 'Committed' },
      { $Type : 'UI.DataField', Value : encumbered, Label : 'Encumbered' },
      { $Type : 'UI.DataField', Value : actual, Label : 'Actual' },
      { $Type : 'UI.DataField', Value : available, Label : 'Available' },
      { $Type : 'UI.DataField', Value : availPct, Label : 'Available %' },
      { $Type : 'UI.DataField', Value : eac, Label : 'EAC' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Control', Label : 'Control record',
      Target : '@UI.FieldGroup#Control' },
    { $Type : 'UI.ReferenceFacet', ID : 'Phasing', Label : 'Phasing',
      Target : 'phases/@UI.LineItem' },
  ],
);

/**
 * When a line's money is expected to go out, and on what grounds.
 *
 * The basis column is not decoration. A phase spread evenly across the project
 * because nothing dated its work looks exactly like one taken from the
 * programme, and only this column tells the two apart.
 */
annotate service.BudgetPhases with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : periodName, Label : 'Period' },
    { $Type : 'UI.DataField', Value : startDate, Label : 'From' },
    { $Type : 'UI.DataField', Value : amount, Label : 'Amount' },
    { $Type : 'UI.DataField', Value : basis, Label : 'Basis' },
  ],
);
