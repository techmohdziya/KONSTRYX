using WorkflowService as service from '../../srv/workflow-service';

annotate service.Timesheets with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Daily Log',
    TypeNamePlural : 'Daily Logs',
    Title          : { $Type : 'UI.DataField', Value : workDate },
    Description    : { $Type : 'UI.DataField', Value : manpowerLine.tradeGrade },
  },

  // The day, who was on it, what it cost and whether anyone has stood behind
  // it. Cost is shown next to the hours rather than on a separate screen,
  // because the number a foreman is signing for is the point of the row.
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : workDate,                Label : 'Date' },
    { $Type : 'UI.DataField', Value : manpowerLine.crewId,     Label : 'Crew' },
    { $Type : 'UI.DataField', Value : manpowerLine.tradeGrade, Label : 'Trade / grade' },
    { $Type : 'UI.DataField', Value : headsPresent,            Label : 'Heads present' },
    { $Type : 'UI.DataField', Value : regularHrs,              Label : 'Regular hrs' },
    { $Type : 'UI.DataField', Value : otHrs,                   Label : 'Overtime hrs' },
    { $Type : 'UI.DataField', Value : costAmount,              Label : 'Cost' },
    { $Type : 'UI.DataField', Value : logStatus,               Label : 'Status',
      Criticality : statusCriticality },
    { $Type : 'UI.DataField', Value : signedBy,                Label : 'Signed by' },
    { $Type : 'UI.DataFieldForAction', Label : 'Sign',
      Action : 'WorkflowService.sign' },
  ],

  UI.SelectionFields : [ workDate, logStatus, manpowerLine_ID, headsPresent ],

  UI.FieldGroup #Day : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : workDate,     Label : 'Date' },
      { $Type : 'UI.DataField', Value : headsPresent, Label : 'Heads present' },
      { $Type : 'UI.DataField', Value : regularHrs,   Label : 'Regular hrs' },
      { $Type : 'UI.DataField', Value : otHrs,        Label : 'Overtime hrs' },
    ],
  },

  // Where the hours land. Both the WBS and the CBS are needed: the WBS carries
  // the S/4 posting, the CBS the cost nature, and a day that has one without
  // the other cannot be accounted for on either side.
  UI.FieldGroup #Charge : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : manpowerLine_ID, Label : 'Manpower line' },
      { $Type : 'UI.DataField', Value : wbs_ID,          Label : 'WBS element' },
      { $Type : 'UI.DataField', Value : cbs_ID,          Label : 'CBS instance' },
      { $Type : 'UI.DataField', Value : activity,        Label : 'Activity' },
    ],
  },

  // Cost, status and signature are outcomes of signing, not things typed in,
  // so they sit apart from what the foreman fills in.
  UI.FieldGroup #Settlement : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : costAmount, Label : 'Cost' },
      { $Type : 'UI.DataField', Value : logStatus,  Label : 'Status',
        Criticality : statusCriticality },
      { $Type : 'UI.DataField', Value : signedBy,   Label : 'Signed by' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Day',        Label : 'The day',
      Target : '@UI.FieldGroup#Day' },
    { $Type : 'UI.ReferenceFacet', ID : 'Charge',     Label : 'Where it charges',
      Target : '@UI.FieldGroup#Charge' },
    { $Type : 'UI.ReferenceFacet', ID : 'Settlement', Label : 'Sign-off',
      Target : '@UI.FieldGroup#Settlement' },
  ],

  UI.Identification : [
    { $Type : 'UI.DataFieldForAction', Label : 'Sign',
      Action : 'WorkflowService.sign' },
  ],
);

// Signing writes the cost, the status and the signature, so the object page
// has to re-read them rather than keep showing the day as an unsigned draft.
annotate service.Timesheets with @(
  Common.SideEffects #Signed : {
    SourceEvents     : [ 'WorkflowService.sign' ],
    TargetProperties : [ 'costAmount', 'logStatus', 'signedBy',
                         'statusCriticality' ],
  }
);

// The filter bar and the value helps read these labels, and without them the
// screen offers "workDate" and "manpowerLine_ID" to a foreman.
annotate service.Timesheets with {
  workDate       @title : 'Date';
  headsPresent   @title : 'Heads present';
  regularHrs     @title : 'Regular hrs';
  otHrs          @title : 'Overtime hrs';
  activity       @title : 'Activity';
  manpowerLine   @title : 'Manpower line';
  wbs            @title : 'WBS element';
  cbs            @title : 'CBS instance';
  costAmount     @title : 'Cost'       @readonly;
  logStatus      @title : 'Status'     @readonly;
  signedBy       @title : 'Signed by'  @readonly;
};
