using MaterialService as service from '../../srv/material-service';

annotate service.ConsumptionRecords with {
  recordDate       @title : 'Day';
  diaryOutputQty   @title : 'Output';
  theoreticalQty   @title : 'Norm';
  wastageAllowance @title : 'Wastage allowed';
  actualQty        @title : 'Used';
  rateApplied      @title : 'Norm applied';
  variance         @title : 'Variance';
  variancePct      @title : 'Variance %';
  result           @title : 'Result';
  recordedBy       @title : 'Recorded by';
  note             @title : 'Note';
  reservationNo    @title : 'Reservation';
  projectCode      @title : 'Project';
  resourceCode     @title : 'Material';
  uom              @title : 'Unit';
};

annotate service.ConsumptionRecords with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Consumption Record',
    TypeNamePlural : 'Material Consumption',
    Title          : { $Type : 'UI.DataField', Value : resourceCode },
    Description    : { $Type : 'UI.DataField', Value : result },
  },

  UI.SelectionFields : [ result, projectCode, resourceCode, recordDate ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    // Over the allowance first, then the most recent. A norm is only worth
    // keeping if the days that broke it are the ones on top of the list.
    SortOrder      : [
      { $Type : 'Common.SortOrderType', Property : varianceCriticality },
      { $Type : 'Common.SortOrderType', Property : recordDate, Descending : true },
    ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : recordDate, Label : 'Day' },
    { $Type : 'UI.DataField', Value : projectCode, Label : 'Project' },
    { $Type : 'UI.DataField', Value : resourceCode, Label : 'Material' },
    { $Type : 'UI.DataField', Value : diaryOutputQty, Label : 'Output' },
    { $Type : 'UI.DataField', Value : actualQty, Label : 'Used' },
    { $Type : 'UI.DataField', Value : theoreticalQty, Label : 'Norm' },
    { $Type : 'UI.DataField', Value : wastageAllowance, Label : 'Wastage allowed' },
    { $Type : 'UI.DataField', Value : variance, Label : 'Variance',
      Criticality : varianceCriticality },
    { $Type : 'UI.DataField', Value : result, Label : 'Result',
      Criticality : varianceCriticality },
  ],

  UI.FieldGroup #Day : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : recordDate, Label : 'Day' },
      { $Type : 'UI.DataField', Value : projectCode, Label : 'Project' },
      { $Type : 'UI.DataField', Value : reservationNo, Label : 'Reservation' },
      { $Type : 'UI.DataField', Value : resourceCode, Label : 'Material' },
      { $Type : 'UI.DataField', Value : recordedBy, Label : 'Recorded by' },
      { $Type : 'UI.DataField', Value : note, Label : 'Note' },
    ],
  },

  // The whole arithmetic, in the order it is done: what the day produced, what
  // the norm allows for that, what the norm itself grants as waste, and what
  // was actually used. The norm applied is kept beside them because a variance
  // nobody can retrace is a number nobody argues with — or acts on.
  UI.FieldGroup #Measurement : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : diaryOutputQty, Label : 'Output' },
      { $Type : 'UI.DataField', Value : rateApplied, Label : 'Norm applied' },
      { $Type : 'UI.DataField', Value : theoreticalQty, Label : 'Norm' },
      { $Type : 'UI.DataField', Value : wastageAllowance, Label : 'Wastage allowed' },
      { $Type : 'UI.DataField', Value : actualQty, Label : 'Used' },
      { $Type : 'UI.DataField', Value : uom, Label : 'Unit' },
      { $Type : 'UI.DataField', Value : variance, Label : 'Variance',
        Criticality : varianceCriticality },
      { $Type : 'UI.DataField', Value : variancePct, Label : 'Variance %',
        Criticality : varianceCriticality },
      { $Type : 'UI.DataField', Value : result, Label : 'Result',
        Criticality : varianceCriticality },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Day', Label : 'Day',
      Target : '@UI.FieldGroup#Day' },
    { $Type : 'UI.ReferenceFacet', ID : 'Measurement', Label : 'Against the norm',
      Target : '@UI.FieldGroup#Measurement' },
  ],
);
