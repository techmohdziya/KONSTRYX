using MasterDataService as service from '../../srv/masterdata-service';

annotate service.HolidayCalendars with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Holiday Calendar',
    TypeNamePlural : 'Holiday Calendars',
    Title          : { $Type : 'UI.DataField', Value : description },
    Description    : { $Type : 'UI.DataField', Value : code },
  },

  UI.SelectionFields : [ code, country, year ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : code } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Calendar' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : country, Label : 'Country' },
    { $Type : 'UI.DataField', Value : region, Label : 'Region' },
    { $Type : 'UI.DataField', Value : year, Label : 'Year' },
  ],

  UI.FieldGroup #Calendar : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code, Label : 'Calendar' },
      { $Type : 'UI.DataField', Value : description, Label : 'Description' },
      { $Type : 'UI.DataField', Value : country, Label : 'Country' },
      { $Type : 'UI.DataField', Value : region, Label : 'Region' },
      { $Type : 'UI.DataField', Value : year, Label : 'Year' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Calendar', Label : 'Calendar',
      Target : '@UI.FieldGroup#Calendar' },
    { $Type : 'UI.ReferenceFacet', ID : 'Days', Label : 'The days',
      Target : 'entries/@UI.LineItem' },
  ],
);

// Status is on the day rather than the calendar: a fixed date is known
// years ahead, a lunar one stays provisional until it is decreed.
annotate service.HolidayEntries with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : holidayDate, Label : 'Date' },
    { $Type : 'UI.DataField', Value : description, Label : 'Occasion' },
    { $Type : 'UI.DataField', Value : class, Label : 'Class' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : nonWorking, Label : 'Non-working' },
    { $Type : 'UI.DataField', Value : otKind, Label : 'Overtime rung' },
  ],
);
