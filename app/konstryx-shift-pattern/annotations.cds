using MasterDataService as service from '../../srv/masterdata-service';

annotate service.ShiftPatterns with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Shift Pattern',
    TypeNamePlural : 'Shift Patterns',
    Title          : { $Type : 'UI.DataField', Value : description },
    Description    : { $Type : 'UI.DataField', Value : code },
  },

  UI.SelectionFields : [ code, dutyHours ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : code } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Pattern' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : dutyHours, Label : 'Duty day (hours)' },
    { $Type : 'UI.DataField', Value : mandayHours, Label : 'Manday (hours)' },
    { $Type : 'UI.DataField', Value : allHoursAreOT, Label : 'Whole day is overtime' },
    { $Type : 'UI.DataField', Value : effectiveFrom, Label : 'Effective from' },
  ],

  UI.FieldGroup #Pattern : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code, Label : 'Pattern' },
      { $Type : 'UI.DataField', Value : description, Label : 'Description' },
      { $Type : 'UI.DataField', Value : dutyHours, Label : 'Duty day (hours)' },
      { $Type : 'UI.DataField', Value : mandayHours, Label : 'Manday (hours)' },
      { $Type : 'UI.DataField', Value : breakMinutes, Label : 'Break (minutes)' },
      { $Type : 'UI.DataField', Value : allHoursAreOT, Label : 'Whole day is overtime' },
      { $Type : 'UI.DataField', Value : calendar_ID, Label : 'Holiday calendar' },
      { $Type : 'UI.DataField', Value : effectiveFrom, Label : 'Effective from' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Pattern', Label : 'The working day',
      Target : '@UI.FieldGroup#Pattern' },
    { $Type : 'UI.ReferenceFacet', ID : 'Ladder', Label : 'Overtime ladder',
      Target : 'overtimeSteps/@UI.LineItem' },
  ],
);

// Cost and charge sit side by side because they are two agreements, not
// one number shown twice: what an hour costs and what it bills move apart.
annotate service.OvertimeSteps with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : sequence, Label : 'Order' },
    { $Type : 'UI.DataField', Value : kind, Label : 'Rung' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : fromHour, Label : 'From hour' },
    { $Type : 'UI.DataField', Value : costFactor, Label : 'Cost factor' },
    { $Type : 'UI.DataField', Value : chargeFactor, Label : 'Charge factor' },
  ],
);
