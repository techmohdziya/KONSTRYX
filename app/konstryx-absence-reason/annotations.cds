using MasterDataService as service from '../../srv/masterdata-service';

annotate service.AbsenceReasons with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Absence Reason',
    TypeNamePlural : 'Absence Reasons',
    Title          : { $Type : 'UI.DataField', Value : description },
    Description    : { $Type : 'UI.DataField', Value : code },
  },

  UI.SelectionFields : [ code ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : code } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Reason' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : blocksTimesheet, Label : 'Blocks timesheet' },
    { $Type : 'UI.DataField', Value : blocksMobilisation, Label : 'Blocks mobilisation' },
    { $Type : 'UI.DataField', Value : documentRequired, Label : 'Document required' },
    { $Type : 'UI.DataField', Value : postsAsAbsenceHours, Label : 'Posts as absence hours' },
    { $Type : 'UI.DataField', Value : returnsAutomatically, Label : 'Returns automatically' },
  ],

  UI.FieldGroup #Reason : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code, Label : 'Reason' },
      { $Type : 'UI.DataField', Value : description, Label : 'Description' },
      { $Type : 'UI.DataField', Value : blocksTimesheet, Label : 'Blocks timesheet' },
      { $Type : 'UI.DataField', Value : blocksMobilisation, Label : 'Blocks mobilisation' },
      { $Type : 'UI.DataField', Value : documentRequired, Label : 'Document required' },
      { $Type : 'UI.DataField', Value : postsAsAbsenceHours, Label : 'Posts as absence hours' },
      { $Type : 'UI.DataField', Value : returnsAutomatically, Label : 'Returns automatically' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Reason', Label : 'What follows from it',
      Target : '@UI.FieldGroup#Reason' },
  ],
);
