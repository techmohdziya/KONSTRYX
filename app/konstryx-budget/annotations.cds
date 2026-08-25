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
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : category, Label : 'Category' },
    { $Type : 'UI.DataField', Value : amount, Label : 'Amount' },
    { $Type : 'UI.DataField', Value : authorised, Label : 'Authorised' },
    { $Type : 'UI.DataField', Value : committed, Label : 'Committed' },
    { $Type : 'UI.DataField', Value : encumbered, Label : 'Encumbered' },
    { $Type : 'UI.DataField', Value : actual, Label : 'Actual' },
    { $Type : 'UI.DataField', Value : available, Label : 'Available' },
    { $Type : 'UI.DataField', Value : availPct, Label : 'Available %' },
    { $Type : 'UI.DataField', Value : eac, Label : 'EAC' },
  ],
);
