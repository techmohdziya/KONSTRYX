using MaterialService as service from '../../srv/material-service';

// The flattened columns are elements of a projection, so nothing else gives
// them a name — without these the filter bar offers "projectCode" and
// "vendorName" as the labels a buyer reads.
annotate service.PurchaseOrders with {
  poNo          @title : 'Order';
  status        @title : 'Status';
  orderedOn     @title : 'Ordered on';
  netValue      @title : 'Order value';
  openValue     @title : 'Still to deliver';
  invoicedValue @title : 'Invoiced';
  projectCode   @title : 'Project';
  projectName   @title : 'Project name';
  vendorNo      @title : 'Vendor number';
  vendorName    @title : 'Vendor';
  requisitionNo @title : 'From requisition';
};

annotate service.PurchaseOrderLines with {
  lineNo       @title : 'Line';
  description  @title : 'Description';
  qty          @title : 'Ordered';
  receivedQty  @title : 'Received';
  openQty      @title : 'Open';
  netValue     @title : 'Line value';
  invoicedQty  @title : 'Invoiced';
  invoicedValue @title : 'Invoiced value';
  eta          @title : 'Expected';
  wbsCode      @title : 'Element';
  cbsCode      @title : 'Cost node';
  materialCode @title : 'ERP material';
  status       @title : 'Status';
};

annotate service.GoodsReceipts with {
  grDoc      @title : 'Receipt';
  poLineNo   @title : 'Order line';
  grQty      @title : 'Quantity';
  grValue    @title : 'Value';
  datePosted @title : 'Posted on';
};

annotate service.PurchaseOrders with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Purchase Order',
    TypeNamePlural : 'Purchase Orders',
    Title          : { $Type : 'UI.DataField', Value : poNo },
    Description    : { $Type : 'UI.DataField', Value : status },
  },

  // What a buyer opens this screen to find: which orders still owe something,
  // and against which job. Value before dates, because the question is almost
  // always how much rather than when.
  UI.SelectionFields : [ status, projectCode, vendorName, orderedOn ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [
      { $Type : 'Common.SortOrderType', Property : openValue, Descending : true },
      { $Type : 'Common.SortOrderType', Property : orderedOn, Descending : true },
    ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : poNo, Label : 'Order' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status',
      Criticality : statusCriticality },
    { $Type : 'UI.DataField', Value : projectCode, Label : 'Project' },
    { $Type : 'UI.DataField', Value : vendorName, Label : 'Vendor' },
    { $Type : 'UI.DataField', Value : netValue, Label : 'Order value' },
    { $Type : 'UI.DataField', Value : openValue, Label : 'Still to deliver' },
    { $Type : 'UI.DataField', Value : orderedOn, Label : 'Ordered on' },
    { $Type : 'UI.DataField', Value : requisitionNo, Label : 'From requisition' },
  ],

  UI.FieldGroup #Order : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : poNo, Label : 'Order' },
      { $Type : 'UI.DataField', Value : status, Label : 'Status',
        Criticality : statusCriticality },
      { $Type : 'UI.DataField', Value : orderedOn, Label : 'Ordered on' },
      { $Type : 'UI.DataField', Value : vendorName, Label : 'Vendor' },
      { $Type : 'UI.DataField', Value : projectCode, Label : 'Project' },
      { $Type : 'UI.DataField', Value : requisitionNo, Label : 'From requisition' },
    ],
  },

  UI.FieldGroup #Value : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : netValue, Label : 'Order value' },
      { $Type : 'UI.DataField', Value : openValue, Label : 'Still to deliver' },
      { $Type : 'UI.DataField', Value : invoicedValue, Label : 'Invoiced' },
    ],
  },

  // The order is ERP's document, so where it came from is part of reading it:
  // an order whose mirror state is anything but OK is showing figures that may
  // already have moved on the other side.
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
    { $Type : 'UI.ReferenceFacet', ID : 'Order', Label : 'Order',
      Target : '@UI.FieldGroup#Order' },
    { $Type : 'UI.ReferenceFacet', ID : 'Value', Label : 'Value',
      Target : '@UI.FieldGroup#Value' },
    { $Type : 'UI.ReferenceFacet', ID : 'OrderLines', Label : 'Lines',
      Target : 'lines/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Receipts', Label : 'Goods Receipts',
      Target : 'receipts/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Invoices', Label : 'Invoices',
      Target : 'invoices/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Source', Label : 'ERP',
      Target : '@UI.FieldGroup#Source' },
  ],
);

annotate service.PurchaseOrderLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : lineNo, Label : '#' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : qty, Label : 'Ordered' },
    { $Type : 'UI.DataField', Value : receivedQty, Label : 'Received' },
    { $Type : 'UI.DataField', Value : openQty, Label : 'Open' },
    { $Type : 'UI.DataField', Value : netValue, Label : 'Line value' },
    { $Type : 'UI.DataField', Value : eta, Label : 'Expected' },
    // The account assignment is the whole reason the line matters to a budget,
    // so it is on the line rather than folded away behind the material.
    { $Type : 'UI.DataField', Value : wbsCode, Label : 'Element' },
    { $Type : 'UI.DataField', Value : cbsCode, Label : 'Cost node' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status',
      Criticality : statusCriticality },
  ],
);

annotate service.GoodsReceipts with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : grDoc, Label : 'Receipt' },
    { $Type : 'UI.DataField', Value : poLineNo, Label : 'Order line' },
    { $Type : 'UI.DataField', Value : grQty, Label : 'Quantity' },
    { $Type : 'UI.DataField', Value : grValue, Label : 'Value' },
    { $Type : 'UI.DataField', Value : datePosted, Label : 'Posted on' },
    { $Type : 'UI.DataField', Value : threeWayMatch, Label : 'Three-way match',
      Criticality : matchCriticality },
    { $Type : 'UI.DataField', Value : matchVariance, Label : 'Why not' },
  ],
);
