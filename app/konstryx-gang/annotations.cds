using MasterDataService as service from '../../srv/masterdata-service';

annotate service.Gangs with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Gang',
    TypeNamePlural : 'Gangs',
    Title          : { $Type : 'UI.DataField', Value : description },
    Description    : { $Type : 'UI.DataField', Value : code },
  },

  UI.SelectionFields : [ code, template_ID, status ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : code } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Gang' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : template_ID, Label : 'Crew template' },
    { $Type : 'UI.DataField', Value : manned, Label : 'Manned' },
    { $Type : 'UI.DataField', Value : slotsRequired, Label : 'Slots' },
    { $Type : 'UI.DataField', Value : actualRatePerHr, Label : 'Actual rate / hour' },
    { $Type : 'UI.DataField', Value : blockedReason, Label : 'Why it cannot work' },
  ],

  UI.FieldGroup #Gang : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code, Label : 'Gang' },
      { $Type : 'UI.DataField', Value : description, Label : 'Description' },
      { $Type : 'UI.DataField', Value : template_ID, Label : 'Crew template' },
      { $Type : 'UI.DataField', Value : project_ID, Label : 'Project' },
      { $Type : 'UI.DataField', Value : manned, Label : 'Manned' },
      { $Type : 'UI.DataField', Value : slotsRequired, Label : 'Slots' },
      { $Type : 'UI.DataField', Value : actualRatePerHr, Label : 'Actual rate / hour' },
      { $Type : 'UI.DataField', Value : status, Label : 'Status' },
      { $Type : 'UI.DataField', Value : blockedReason, Label : 'Why it cannot work' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Gang', Label : 'Against its template',
      Target : '@UI.FieldGroup#Gang' },
    { $Type : 'UI.ReferenceFacet', ID : 'Slots', Label : 'Slot by slot',
      Target : 'slots/@UI.LineItem' },
  ],
);

// A slot filled from a purchase order carries that order's item price,
// which is not the rate of the trade the slot is for — a man engaged as
// one thing working as another is only visible when both are held.
annotate service.GangSlots with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : slotNo, Label : 'Slot' },
    { $Type : 'UI.DataField', Value : source, Label : 'Sourced from' },
    { $Type : 'UI.DataField', Value : employee_ID, Label : 'Worker' },
    { $Type : 'UI.DataField', Value : engagement_ID, Label : 'Engagement' },
    { $Type : 'UI.DataField', Value : trade_ID, Label : 'Slot trade' },
    { $Type : 'UI.DataField', Value : ratePerHr, Label : 'Rate / hour' },
    { $Type : 'UI.DataField', Value : blockedReason, Label : 'Why he does not count' },
  ],
);
