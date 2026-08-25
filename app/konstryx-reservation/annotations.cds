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

  UI.SelectionFields : [ docNo, status, executionFlow, raisedBy ],

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

  // The reservation is where consumption is posted from, because posting is a
  // decision about the whole document: every line is rolled forward from the
  // days signed behind it, together, so no two lines can be current to
  // different dates.
  UI.Identification : [
    { $Type : 'UI.DataFieldForAction', Label : 'Post consumption',
      Action : 'WorkflowService.postConsumption' },
    { $Type : 'UI.DataFieldForAction', Label : 'Close',
      Action : 'WorkflowService.close' },
  ],
);

// Posting rewrites every line's consumption, so the lines table has to be
// re-read. Without this the screen keeps the figures the action just replaced.
annotate service.Reservations with @(
  Common.SideEffects #Posted : {
    SourceEvents   : [ 'WorkflowService.postConsumption' ],
    TargetEntities : [ lines ],
  }
);

annotate service.ReservationLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : qty, Label : 'Quantity' },
    { $Type : 'UI.DataField', Value : uom, Label : 'UoM' },
    { $Type : 'UI.DataField', Value : dailyRate, Label : 'Daily rate' },
    { $Type : 'UI.DataField', Value : encumberedAmount, Label : 'Encumbered' },
    { $Type : 'UI.DataField', Value : consumedToDate, Label : 'Consumed (head-days)' },
    { $Type : 'UI.DataField', Value : burnPct, Label : 'Burn %',
      Criticality : burnCriticality },
    { $Type : 'UI.DataField', Value : costToDate, Label : 'Cost to date' },
    { $Type : 'UI.DataField', Value : drift, Label : 'Drift',
      Criticality : driftCriticality },
    { $Type : 'UI.DataField', Value : lineStatus, Label : 'Status' },
  ],
);

// Labels for the filter bar and the value helps. Without them the screen
// offers a coordinator "docNo" and "executionFlow" to filter on.
annotate service.Reservations with {
  docNo         @title : 'Reservation';
  status        @title : 'Status';
  raisedBy      @title : 'Raised by';
  raisedOn      @title : 'Raised on';
  executionFlow @title : 'Execution flow';
};

annotate service.ReservationLines with {
  qty              @title : 'Quantity';
  uom              @title : 'UoM';
  dailyRate        @title : 'Daily rate';
  encumberedAmount @title : 'Encumbered';
  consumedToDate   @title : 'Consumed (head-days)';
  costToDate       @title : 'Cost to date';
  burnPct          @title : 'Burn %';
  drift            @title : 'Drift';
  lineStatus       @title : 'Status';
};
