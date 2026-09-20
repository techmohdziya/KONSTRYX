using AuthorizationService as service from '../../srv/authorization-service';

annotate service.ApprovalSchemes with {
  code      @title : 'Scheme';
  name      @title : 'Name';
  isActive  @title : 'Active';
  validFrom @title : 'Valid from';
  validTo   @title : 'Valid to';
};

annotate service.ApprovalSchemes with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Approval Scheme',
    TypeNamePlural : 'Approval Schemes',
    Title          : { $Type : 'UI.DataField', Value : name },
    Description    : { $Type : 'UI.DataField', Value : code },
  },

  UI.SelectionFields : [ code, isActive ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : code } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Scheme' },
    { $Type : 'UI.DataField', Value : name, Label : 'Name' },
    { $Type : 'UI.DataField', Value : authObject_ID, Label : 'Approves' },
    { $Type : 'UI.DataField', Value : company_ID, Label : 'Company' },
    { $Type : 'UI.DataField', Value : isActive, Label : 'Active' },
  ],

  UI.FieldGroup #Scheme : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code, Label : 'Scheme' },
      { $Type : 'UI.DataField', Value : name, Label : 'Name' },
      { $Type : 'UI.DataField', Value : authObject_ID, Label : 'Approves' },
      // Empty means the scheme applies group-wide; set it to vary by entity.
      { $Type : 'UI.DataField', Value : company_ID, Label : 'Company' },
      { $Type : 'UI.DataField', Value : isActive, Label : 'Active' },
      { $Type : 'UI.DataField', Value : validFrom, Label : 'Valid from' },
      { $Type : 'UI.DataField', Value : validTo, Label : 'Valid to' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Scheme', Label : 'Scheme',
      Target : '@UI.FieldGroup#Scheme' },
    { $Type : 'UI.ReferenceFacet', ID : 'Steps', Label : 'Who signs, and when',
      Target : 'steps/@UI.LineItem' },
  ],
);

// The approver is the point of the step. A step with none is open to any
// authorised user — legitimate for a scheme that only wants a second pair of
// eyes, and a mistake everywhere else, so it is the first column after the name.
annotate service.ApprovalStepDefs with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : stepNo, Label : 'Step' },
    { $Type : 'UI.DataField', Value : name, Label : 'Step name' },
    { $Type : 'UI.DataField', Value : approver_ID, Label : 'Approver' },
    { $Type : 'UI.DataField', Value : minAmount, Label : 'From value' },
    { $Type : 'UI.DataField', Value : maxAmount, Label : 'To value' },
    { $Type : 'UI.DataField', Value : isMandatory, Label : 'Mandatory' },
    { $Type : 'UI.DataField', Value : allowChaining, Label : 'Same person may sign again' },
  ],
  UI.FieldGroup #Step : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : stepNo, Label : 'Step' },
      { $Type : 'UI.DataField', Value : name, Label : 'Step name' },
      { $Type : 'UI.DataField', Value : approver_ID, Label : 'Approver' },
      { $Type : 'UI.DataField', Value : mode, Label : 'Mode' },
      { $Type : 'UI.DataField', Value : isMandatory, Label : 'Mandatory' },
      { $Type : 'UI.DataField', Value : allowChaining, Label : 'Same person may sign again' },
    ],
  },
  // Inclusive of the lower bound and exclusive of the upper, which is why they
  // are shown together rather than as one "threshold".
  UI.FieldGroup #Band : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : minAmount, Label : 'From value' },
      { $Type : 'UI.DataField', Value : maxAmount, Label : 'To value' },
      { $Type : 'UI.DataField', Value : ccy_code, Label : 'Currency' },
    ],
  },
  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Step', Label : 'Step',
      Target : '@UI.FieldGroup#Step' },
    { $Type : 'UI.ReferenceFacet', ID : 'Band', Label : 'Value band',
      Target : '@UI.FieldGroup#Band' },
  ],
);
