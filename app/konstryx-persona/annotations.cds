using AuthorizationService as service from '../../srv/authorization-service';

annotate service.Personas with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Persona',
    TypeNamePlural : 'Personas',
    Title          : { $Type : 'UI.DataField', Value : name },
    Description    : { $Type : 'UI.DataField', Value : code },
  },

  UI.SelectionFields : [ code, isActive, isDelivered ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : code } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Persona' },
    { $Type : 'UI.DataField', Value : name, Label : 'Name' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : isActive, Label : 'Active' },
    // A delivered persona is product content. Editing one is allowed and
    // sometimes right, but it should never be a surprise, so the list says so.
    { $Type : 'UI.DataField', Value : isDelivered, Label : 'Delivered' },
    { $Type : 'UI.DataFieldForAction', Label : 'Copy as new',
      Action : 'AuthorizationService.copyAs' },
  ],

  UI.FieldGroup #Persona : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code, Label : 'Persona' },
      { $Type : 'UI.DataField', Value : name, Label : 'Name' },
      { $Type : 'UI.DataField', Value : description, Label : 'Description' },
      { $Type : 'UI.DataField', Value : isActive, Label : 'Active' },
      { $Type : 'UI.DataField', Value : isDelivered, Label : 'Delivered with the product' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Persona', Label : 'Persona',
      Target : '@UI.FieldGroup#Persona' },
    { $Type : 'UI.ReferenceFacet', ID : 'Permissions', Label : 'What it may do',
      Target : 'permissions/@UI.LineItem' },
  ],
);

// One row is one sentence: this persona may do this activity to this object.
// Granted is shown rather than assumed, because a permission row that exists
// and is not granted is a deliberate denial and reads differently from an
// absent row.
annotate service.PersonaPermissions with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : authObject_ID, Label : 'Object' },
    { $Type : 'UI.DataField', Value : activity_code, Label : 'Activity' },
    { $Type : 'UI.DataField', Value : granted, Label : 'Granted' },
  ],
  UI.FieldGroup #Permission : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : authObject_ID, Label : 'Object' },
      { $Type : 'UI.DataField', Value : activity_code, Label : 'Activity' },
      { $Type : 'UI.DataField', Value : granted, Label : 'Granted' },
    ],
  },
  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Permission', Label : 'Permission',
      Target : '@UI.FieldGroup#Permission' },
  ],
);
