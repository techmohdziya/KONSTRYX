using MasterDataService as service from '../../srv/masterdata-service';

annotate service.Absences with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Absence',
    TypeNamePlural : 'Availability',
    Title          : { $Type : 'UI.DataField', Value : reason_ID },
    Description    : { $Type : 'UI.DataField', Value : fromDate },
  },

  UI.SelectionFields : [ reason_ID, fromDate ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : fromDate, Descending : true } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : employee_ID, Label : 'Worker' },
    { $Type : 'UI.DataField', Value : engagement_ID, Label : 'Engagement' },
    { $Type : 'UI.DataField', Value : reason_ID, Label : 'Reason' },
    { $Type : 'UI.DataField', Value : fromDate, Label : 'From' },
    { $Type : 'UI.DataField', Value : toDate, Label : 'To' },
    { $Type : 'UI.DataField', Value : derived, Label : 'Raised by an expiry' },
  ],

  UI.FieldGroup #Absence : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : employee_ID, Label : 'Worker' },
      { $Type : 'UI.DataField', Value : engagement_ID, Label : 'Engagement' },
      { $Type : 'UI.DataField', Value : reason_ID, Label : 'Reason' },
      { $Type : 'UI.DataField', Value : fromDate, Label : 'From' },
      { $Type : 'UI.DataField', Value : toDate, Label : 'To' },
      { $Type : 'UI.DataField', Value : derived, Label : 'Raised by an expiry' },
      { $Type : 'UI.DataField', Value : note, Label : 'Note' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Absence', Label : 'Who, and for how long',
      Target : '@UI.FieldGroup#Absence' },
  ],
);
