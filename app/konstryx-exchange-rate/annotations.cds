using AdminService as service from '../../srv/admin-service';

annotate service.ExchangeRates with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Exchange Rate',
    TypeNamePlural : 'Exchange Rates',
    Title          : { $Type : 'UI.DataField', Value : fromCcy_code },
    Description    : { $Type : 'UI.DataField', Value : rateType },
  },

  // The rate type is a column rather than a detail, because the same pair on
  // the same day legitimately carries three different rates and the screen has
  // to make that visible rather than look like duplicate rows.
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : fromCcy_code, Label : 'From' },
    { $Type : 'UI.DataField', Value : toCcy_code,   Label : 'To' },
    { $Type : 'UI.DataField', Value : rateType,     Label : 'Rate type' },
    { $Type : 'UI.DataField', Value : rate,         Label : 'Rate' },
    { $Type : 'UI.DataField', Value : validFrom,    Label : 'Valid from' },
    { $Type : 'UI.DataField', Value : source,       Label : 'Source' },
  ],

  UI.SelectionFields : [ fromCcy_code, toCcy_code, rateType, validFrom ],

  UI.FieldGroup #Rate : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : fromCcy_code, Label : 'From' },
      { $Type : 'UI.DataField', Value : toCcy_code,   Label : 'To' },
      { $Type : 'UI.DataField', Value : rateType,     Label : 'Rate type' },
      { $Type : 'UI.DataField', Value : rate,         Label : 'Rate' },
      { $Type : 'UI.DataField', Value : validFrom,    Label : 'Valid from' },
      { $Type : 'UI.DataField', Value : source,       Label : 'Source' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Rate', Label : 'The rate',
      Target : '@UI.FieldGroup#Rate' },
  ],
);

annotate service.ExchangeRates with {
  fromCcy   @title : 'From';
  toCcy     @title : 'To';
  /**
   * CONTRACT prices revenue and is fixed at award. BUDGET prices cost and is
   * fixed at baseline. SPOT and AVERAGE price actuals. They are not
   * interchangeable, which is why the type is a filter on the list.
   */
  rateType  @title : 'Rate type';
  rate      @title : 'Rate';
  validFrom @title : 'Valid from';
  source    @title : 'Source';
};
