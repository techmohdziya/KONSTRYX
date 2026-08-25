using WorkflowService as service from '../../srv/workflow-service';

annotate service.ProductivitySnapshots with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Measurement',
    TypeNamePlural : 'Productivity',
    Title          : { $Type : 'UI.DataField', Value : locationCode },
    Description    : { $Type : 'UI.DataField', Value : locationName },
  },

  // Read left to right as the argument the number makes: where, over how many
  // signed days and hours, at what cost, produced how much — and only then the
  // rate. A rate shown without what it was computed from invites the reader to
  // trust it, and it is exactly the figure worth questioning.
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : locationCode,  Label : 'Location' },
    { $Type : 'UI.DataField', Value : locationName,  Label : 'Name' },
    { $Type : 'UI.DataField', Value : takenAt,       Label : 'Measured' },
    { $Type : 'UI.DataField', Value : signedDays,    Label : 'Signed days' },
    { $Type : 'UI.DataField', Value : labourHours,   Label : 'Labour hrs' },
    { $Type : 'UI.DataField', Value : labourCost,    Label : 'Labour cost' },
    { $Type : 'UI.DataField', Value : installedQty,  Label : 'Installed' },
    { $Type : 'UI.DataField', Value : uom,           Label : 'UoM' },
    { $Type : 'UI.DataField', Value : outputPerHour, Label : 'Output / hr' },
    { $Type : 'UI.DataField', Value : costPerUnit,   Label : 'Cost / unit' },
    { $Type : 'UI.DataField', Value : note,          Label : 'Note' },
  ],

  UI.SelectionFields : [ locationCode, locationType, takenAt ],

  UI.FieldGroup #Where : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : locationCode, Label : 'Location' },
      { $Type : 'UI.DataField', Value : locationName, Label : 'Name' },
      { $Type : 'UI.DataField', Value : locationType, Label : 'Type' },
      { $Type : 'UI.DataField', Value : takenAt,      Label : 'Measured at' },
    ],
  },

  // What the rate was computed from, kept together and ahead of the rate
  // itself, so the reader can see the basis before the conclusion.
  UI.FieldGroup #Basis : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : signedDays,   Label : 'Signed days' },
      { $Type : 'UI.DataField', Value : headDays,     Label : 'Head-days' },
      { $Type : 'UI.DataField', Value : labourHours,  Label : 'Labour hours' },
      { $Type : 'UI.DataField', Value : labourCost,   Label : 'Labour cost' },
      { $Type : 'UI.DataField', Value : installedQty, Label : 'Installed quantity' },
      { $Type : 'UI.DataField', Value : uom,          Label : 'UoM' },
    ],
  },

  UI.FieldGroup #Rate : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : outputPerHour, Label : 'Output per hour' },
      { $Type : 'UI.DataField', Value : costPerUnit,   Label : 'Cost per unit' },
      { $Type : 'UI.DataField', Value : note,          Label : 'Note' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Where', Label : 'Where and when',
      Target : '@UI.FieldGroup#Where' },
    { $Type : 'UI.ReferenceFacet', ID : 'Basis', Label : 'What it was computed from',
      Target : '@UI.FieldGroup#Basis' },
    { $Type : 'UI.ReferenceFacet', ID : 'Rate', Label : 'The rate',
      Target : '@UI.FieldGroup#Rate' },
  ],
);

annotate service.ProductivitySnapshots with {
  locationCode  @title : 'Location';
  locationName  @title : 'Name';
  locationType  @title : 'Type';
  takenAt       @title : 'Measured at';
  signedDays    @title : 'Signed days';
  headDays      @title : 'Head-days';
  labourHours   @title : 'Labour hours';
  labourCost    @title : 'Labour cost';
  installedQty  @title : 'Installed quantity';
  uom           @title : 'UoM';
  outputPerHour @title : 'Output per hour';
  costPerUnit   @title : 'Cost per unit';
  note          @title : 'Note';
};
