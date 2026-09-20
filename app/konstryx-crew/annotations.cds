using MasterDataService as service from '../../srv/masterdata-service';

annotate service.CrewTemplates with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Crew Template',
    TypeNamePlural : 'Crew Templates',
    Title          : { $Type : 'UI.DataField', Value : description },
    Description    : { $Type : 'UI.DataField', Value : code },
  },

  UI.SelectionFields : [ code, outputBasis ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : code } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Crew' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : crewRatePerHr, Label : 'Crew rate / hour' },
    { $Type : 'UI.DataField', Value : outputPerDay, Label : 'Output per day' },
    { $Type : 'UI.DataField', Value : outputUoM, Label : 'Unit' },
    { $Type : 'UI.DataField', Value : outputBasis, Label : 'Output stated per' },
    { $Type : 'UI.DataField', Value : minimumManning, Label : 'Minimum manning' },
  ],

  UI.FieldGroup #Crew : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code, Label : 'Crew' },
      { $Type : 'UI.DataField', Value : description, Label : 'Description' },
      { $Type : 'UI.DataField', Value : crewRatePerHr, Label : 'Crew rate / hour' },
      { $Type : 'UI.DataField', Value : minimumManning, Label : 'Minimum manning' },
      { $Type : 'UI.DataField', Value : substitutionAllowed, Label : 'Substitution allowed' },
      { $Type : 'UI.DataField', Value : foremanCountsToOutput, Label : 'Foreman counts to output' },
      { $Type : 'UI.DataField', Value : mixedSourcingAllowed, Label : 'Mixed sourcing allowed' },
    ],
  },

  // The norms are written per 8-hour manday while the rates and shift patterns
  // run a 9.5-hour duty day — 19% apart. This is the only object that touches
  // both, so the basis is stated beside the number rather than assumed.
  UI.FieldGroup #Output : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : outputPerDay, Label : 'Output per day' },
      { $Type : 'UI.DataField', Value : outputUoM, Label : 'Unit' },
      { $Type : 'UI.DataField', Value : outputBasis, Label : 'Output stated per' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Crew', Label : 'The crew',
      Target : '@UI.FieldGroup#Crew' },
    { $Type : 'UI.ReferenceFacet', ID : 'Output', Label : 'What it produces',
      Target : '@UI.FieldGroup#Output' },
    { $Type : 'UI.ReferenceFacet', ID : 'Slots', Label : 'Composition',
      Target : 'slots/@UI.LineItem' },
  ],
);

// The slots are the crew rate. Nothing here is typed into the header:
// adding a slot changes what the crew costs, and that is the point.
annotate service.CrewTemplateSlots with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : slotNo, Label : 'Slot' },
    { $Type : 'UI.DataField', Value : trade_ID, Label : 'Trade' },
    { $Type : 'UI.DataField', Value : grade_ID, Label : 'Grade' },
    { $Type : 'UI.DataField', Value : isForeman, Label : 'Foreman' },
    { $Type : 'UI.DataField', Value : ratePerHr, Label : 'Rate / hour' },
  ],
);
