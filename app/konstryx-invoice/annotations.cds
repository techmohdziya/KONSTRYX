using MaterialService as service from '../../srv/material-service';

annotate service.SupplierInvoices with {
  invoiceNo   @title : 'Invoice';
  orderNo     @title : 'Order';
  vendorName  @title : 'Vendor';
  projectCode @title : 'Project';
  postingDate @title : 'Posted on';
  netAmount   @title : 'Invoice value';
  matched     @title : 'Three-way match';
  status      @title : 'Status';
};

annotate service.SupplierInvoiceLines with {
  lineNo      @title : 'Line';
  poLineNo    @title : 'Order line';
  description @title : 'Description';
  qty         @title : 'Quantity';
  netAmount   @title : 'Line value';
  matched     @title : 'Matched';
  variance    @title : 'Why not';
};

annotate service.SupplierInvoices with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Supplier Invoice',
    TypeNamePlural : 'Supplier Invoices',
    Title          : { $Type : 'UI.DataField', Value : invoiceNo },
    Description    : { $Type : 'UI.DataField', Value : vendorName },
  },

  // Match first. The reason a clerk opens this list is to find the bills that
  // disagree with the order or the delivery; everything else is filing.
  UI.SelectionFields : [ matched, projectCode, vendorName, postingDate ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [
      { $Type : 'Common.SortOrderType', Property : matchCriticality },
      { $Type : 'Common.SortOrderType', Property : postingDate, Descending : true },
    ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : invoiceNo },
    { $Type : 'UI.DataField', Value : matched, Label : 'Three-way match',
      Criticality : matchCriticality },
    { $Type : 'UI.DataField', Value : vendorName },
    { $Type : 'UI.DataField', Value : projectCode },
    { $Type : 'UI.DataField', Value : orderNo },
    { $Type : 'UI.DataField', Value : netAmount },
    { $Type : 'UI.DataField', Value : postingDate },
  ],

  UI.FieldGroup #Invoice : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : invoiceNo },
      { $Type : 'UI.DataField', Value : status },
      { $Type : 'UI.DataField', Value : matched, Criticality : matchCriticality },
      { $Type : 'UI.DataField', Value : postingDate },
      { $Type : 'UI.DataField', Value : netAmount },
      { $Type : 'UI.DataField', Value : vendorName },
      { $Type : 'UI.DataField', Value : projectCode },
      { $Type : 'UI.DataField', Value : orderNo },
    ],
  },

  UI.FieldGroup #Source : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : s4Key, Label : 'ERP number' },
      { $Type : 'UI.DataField', Value : s4System, Label : 'ERP system' },
      { $Type : 'UI.DataField', Value : syncStatus, Label : 'Mirror state' },
      { $Type : 'UI.DataField', Value : lastSyncedAt, Label : 'Mirrored at' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Invoice', Label : 'Invoice',
      Target : '@UI.FieldGroup#Invoice' },
    { $Type : 'UI.ReferenceFacet', ID : 'InvoiceLines', Label : 'Lines',
      Target : 'lines/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Source', Label : 'ERP',
      Target : '@UI.FieldGroup#Source' },
  ],
);

annotate service.SupplierInvoiceLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : lineNo },
    { $Type : 'UI.DataField', Value : description },
    { $Type : 'UI.DataField', Value : poLineNo },
    { $Type : 'UI.DataField', Value : qty },
    { $Type : 'UI.DataField', Value : netAmount },
    { $Type : 'UI.DataField', Value : matched, Criticality : matchCriticality },
    // Carried on the line rather than left to the header's flag, because the
    // header only says something failed and this says what.
    { $Type : 'UI.DataField', Value : variance },
  ],
);
