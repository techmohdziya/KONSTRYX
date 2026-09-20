using MasterDataService as service from '../../srv/masterdata-service';

/**
 * The Rate Master — what a resource costs, from whom, on what basis, from when.
 *
 * Money lives here and nowhere else. A norm says how much of a resource one
 * unit of work takes; this says what that resource is worth, and the build-up
 * of a bill line takes the quantity from the norm and the money from here. The
 * two are kept apart because they change for different reasons and on
 * different cycles — a productivity norm holds for years, a hire rate is
 * renegotiated every season.
 *
 * The same resource can be rated more than once: own fleet, hired in, and
 * supplied by a labour subcontractor are three different costs for the same
 * trade, and a project picks by source and date rather than by there being
 * only one row.
 */
annotate service.Rates with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Rate',
    TypeNamePlural : 'Rate Master',
    Title          : { $Type : 'UI.DataField', Value : resource.code },
    Description    : { $Type : 'UI.DataField', Value : source },
  },

  UI.SelectionFields : [ resource_ID, source, vendor_ID, effectiveFrom, scope ],

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : resource_ID,   Label : 'Resource' },
    { $Type : 'UI.DataField', Value : source,        Label : 'Source' },
    { $Type : 'UI.DataField', Value : vendor_ID,     Label : 'Vendor' },
    { $Type : 'UI.DataField', Value : rateValue,     Label : 'Rate' },
    { $Type : 'UI.DataField', Value : basis,         Label : 'Per' },
    { $Type : 'UI.DataField', Value : ccy_code,      Label : 'Currency' },
    { $Type : 'UI.DataField', Value : netRate,       Label : 'Net rate' },
    { $Type : 'UI.DataField', Value : effectiveFrom, Label : 'Effective from' },
    { $Type : 'UI.DataField', Value : scope,         Label : 'Scope' },
  ],

  UI.FieldGroup #Rate : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : resource_ID,   Label : 'Resource' },
      { $Type : 'UI.DataField', Value : rateValue,     Label : 'Rate' },
      { $Type : 'UI.DataField', Value : basis,         Label : 'Per (hour / day / unit)' },
      { $Type : 'UI.DataField', Value : ccy_code,      Label : 'Currency' },
      { $Type : 'UI.DataField', Value : netRate,       Label : 'Net rate' },
      { $Type : 'UI.DataField', Value : effectiveFrom, Label : 'Effective from' },
    ],
  },

  /**
   * Where the resource comes from, and who supplies it. A hired rate without a
   * vendor is a rate nobody can raise a document against; an in-house rate
   * with one is a rate that will be misread as a quote.
   */
  UI.FieldGroup #Source : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : source,     Label : 'Source' },
      { $Type : 'UI.DataField', Value : vendor_ID,  Label : 'Vendor' },
      { $Type : 'UI.DataField', Value : company_ID, Label : 'Company' },
    ],
  },

  UI.FieldGroup #Governance : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : scope,            Label : 'Scope' },
      { $Type : 'UI.DataField', Value : masterStatus,     Label : 'Status' },
      { $Type : 'UI.DataField', Value : owningCompany_ID, Label : 'Owning company' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Rate', Label : 'Rate',
      Target : '@UI.FieldGroup#Rate' },
    { $Type : 'UI.ReferenceFacet', ID : 'Source', Label : 'Source',
      Target : '@UI.FieldGroup#Source' },
    { $Type : 'UI.ReferenceFacet', ID : 'Governance', Label : 'Governance',
      Target : '@UI.FieldGroup#Governance' },
  ],
);

annotate service.Rates with {
  source        @title : 'Source';
  rateValue     @title : 'Rate';
  basis         @title : 'Per';
  netRate       @title : 'Net rate';
  effectiveFrom @title : 'Effective from';

  resource @Common : {
    Text            : resource.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'Resources',
      Label          : 'Resource',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : resource_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'description' }
      ]
    }
  };

  vendor @Common : {
    Text            : vendor.name,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'Vendors',
      Label          : 'Vendor',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : vendor_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'bpNumber' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' }
      ]
    }
  };
};
