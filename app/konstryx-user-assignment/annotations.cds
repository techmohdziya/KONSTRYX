using AuthorizationService as service from '../../srv/authorization-service';

annotate service.UserAssignments with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Assignment',
    TypeNamePlural : 'User Assignments',
    Title          : { $Type : 'UI.DataField', Value : user },
    Description    : { $Type : 'UI.DataField', Value : persona_ID },
  },

  UI.SelectionFields : [ user, persona_ID, isActive ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : user } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  // Who, as what, and where. The scope columns are shown even when empty,
  // because empty is a decision here — it means everywhere — and a column that
  // disappears when it is blank hides the widest grant on the screen.
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : user, Label : 'User' },
    { $Type : 'UI.DataField', Value : persona_ID, Label : 'Persona' },
    { $Type : 'UI.DataField', Value : company_ID, Label : 'Company' },
    { $Type : 'UI.DataField', Value : project_ID, Label : 'Project' },
    { $Type : 'UI.DataField', Value : validFrom, Label : 'Valid from' },
    { $Type : 'UI.DataField', Value : validTo, Label : 'Valid to' },
    { $Type : 'UI.DataField', Value : isActive, Label : 'Active' },
  ],

  UI.FieldGroup #Assignment : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : user, Label : 'User' },
      { $Type : 'UI.DataField', Value : persona_ID, Label : 'Persona' },
      { $Type : 'UI.DataField', Value : isActive, Label : 'Active' },
    ],
  },

  UI.FieldGroup #Scope : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : company_ID, Label : 'Company' },
      { $Type : 'UI.DataField', Value : project_ID, Label : 'Project' },
    ],
  },

  // An assignment that has expired still explains what somebody could do last
  // month, so the dates are part of the record rather than a filter on it.
  UI.FieldGroup #Validity : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : validFrom, Label : 'Valid from' },
      { $Type : 'UI.DataField', Value : validTo, Label : 'Valid to' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Assignment', Label : 'Assignment',
      Target : '@UI.FieldGroup#Assignment' },
    { $Type : 'UI.ReferenceFacet', ID : 'Scope', Label : 'Where it applies',
      Target : '@UI.FieldGroup#Scope' },
    { $Type : 'UI.ReferenceFacet', ID : 'Validity', Label : 'Validity',
      Target : '@UI.FieldGroup#Validity' },
  ],
);
