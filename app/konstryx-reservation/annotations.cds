using WorkflowService as service from '../../srv/workflow-service';

annotate service.Reservations with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Reservation',
    TypeNamePlural : 'Reservations',
    Title          : { $Type : 'UI.DataField', Value : docNo },
    Description    : { $Type : 'UI.DataField', Value : status },
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : docNo, Label : 'Reservation' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : raisedBy, Label : 'Raised by' },
    { $Type : 'UI.DataField', Value : raisedOn, Label : 'Raised on' },
    { $Type : 'UI.DataField', Value : executionFlow, Label : 'Execution flow' },
  ],

  UI.FieldGroup #Details : {
    $Type : 'UI.FieldGroupType',
    Data  : [
    { $Type : 'UI.DataField', Value : docNo, Label : 'Reservation' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : raisedBy, Label : 'Raised by' },
    { $Type : 'UI.DataField', Value : raisedOn, Label : 'Raised on' },
    { $Type : 'UI.DataField', Value : executionFlow, Label : 'Execution flow' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
    { $Type : 'UI.ReferenceFacet', ID : 'ReservationLines', Label : 'Reservation Lines',
      Target : 'lines/@UI.LineItem' },
  ],
);

annotate service.ReservationLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : qty, Label : 'Quantity' },
    { $Type : 'UI.DataField', Value : uom, Label : 'UoM' },
    { $Type : 'UI.DataField', Value : dailyRate, Label : 'Daily rate' },
    { $Type : 'UI.DataField', Value : encumberedAmount, Label : 'Encumbered' },
    { $Type : 'UI.DataField', Value : consumedToDate, Label : 'Consumed' },
    { $Type : 'UI.DataField', Value : burnPct, Label : 'Burn %' },
    { $Type : 'UI.DataField', Value : costToDate, Label : 'Cost to date' },
    { $Type : 'UI.DataField', Value : drift, Label : 'Drift' },
    { $Type : 'UI.DataField', Value : lineStatus, Label : 'Status' },
  ],
);
