using MaterialService as service from '../../srv/material-service';

// Flattened columns are elements of a projection and nothing else names them,
// so without this the filter bar offers "projectCode" and "reservationNo" as
// the labels a storekeeper reads.
annotate service.PullRequests with {
  docNo         @title : 'Pull request';
  status        @title : 'Status';
  raisedOn      @title : 'Raised on';
  raisedBy      @title : 'Raised by';
  storageLoc    @title : 'Store';
  qtyRequested  @title : 'Asked for';
  qtyIssued     @title : 'Issued';
  shortIssued   @title : 'Not issued';
  issuedValue   @title : 'Issued value';
  projectCode   @title : 'Project';
  projectName   @title : 'Project name';
  reservationNo @title : 'Reservation';
  resourceCode  @title : 'Material';
  uom           @title : 'Unit';
  s4GIDoc       @title : 'ERP goods issue';
  s4GIDate      @title : 'Issued on';
  s4GIQty       @title : 'ERP quantity';
  s4System      @title : 'ERP system';
  syncMessage   @title : 'ERP message';
};

annotate service.SiteReceipts with {
  receivedQty   @title : 'Received';
  shortQty      @title : 'Outstanding after this';
  receivedBy    @title : 'Received by';
  receivedOn    @title : 'Received on';
  note          @title : 'Note';
  pullRequestNo @title : 'Pull request';
};

annotate service.PullRequests with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Stock Draw',
    TypeNamePlural : 'Stock Draws',
    Title          : { $Type : 'UI.DataField', Value : docNo },
    Description    : { $Type : 'UI.DataField', Value : resourceCode },
  },

  // What a storekeeper opens this for: what is still waiting on a movement,
  // and on which job. Material before dates, because the question is what is
  // holding a pour up rather than when it was asked for.
  UI.SelectionFields : [ status, projectCode, resourceCode, storageLoc ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    // Raised first, then part received, then confirmed: the ones still owed
    // something are what anybody is looking for, and within each band the
    // oldest ask has been waiting longest.
    SortOrder      : [
      { $Type : 'Common.SortOrderType', Property : statusCriticality },
      { $Type : 'Common.SortOrderType', Property : raisedOn },
    ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : docNo, Label : 'Pull request' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status',
      Criticality : statusCriticality },
    { $Type : 'UI.DataField', Value : projectCode, Label : 'Project' },
    { $Type : 'UI.DataField', Value : resourceCode, Label : 'Material' },
    { $Type : 'UI.DataField', Value : qtyRequested, Label : 'Asked for' },
    { $Type : 'UI.DataField', Value : qtyIssued, Label : 'Issued' },
    { $Type : 'UI.DataField', Value : issuedValue, Label : 'Issued value' },
    { $Type : 'UI.DataField', Value : storageLoc, Label : 'Store' },
    { $Type : 'UI.DataField', Value : reservationNo, Label : 'Reservation' },
  ],

  UI.FieldGroup #Draw : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : docNo, Label : 'Pull request' },
      { $Type : 'UI.DataField', Value : status, Label : 'Status',
        Criticality : statusCriticality },
      { $Type : 'UI.DataField', Value : projectCode, Label : 'Project' },
      { $Type : 'UI.DataField', Value : reservationNo, Label : 'Reservation' },
      { $Type : 'UI.DataField', Value : storageLoc, Label : 'Store' },
      { $Type : 'UI.DataField', Value : raisedBy, Label : 'Raised by' },
      { $Type : 'UI.DataField', Value : raisedOn, Label : 'Raised on' },
    ],
  },

  // Asked for, issued, and the gap between them. The gap is the reason this
  // group exists: a store that gave out sixty of the eighty asked for has told
  // the site something, and it should not have to be worked out on a page.
  UI.FieldGroup #Movement : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : resourceCode, Label : 'Material' },
      { $Type : 'UI.DataField', Value : qtyRequested, Label : 'Asked for' },
      { $Type : 'UI.DataField', Value : qtyIssued, Label : 'Issued' },
      { $Type : 'UI.DataField', Value : shortIssued, Label : 'Not issued' },
      { $Type : 'UI.DataField', Value : uom, Label : 'Unit' },
      { $Type : 'UI.DataField', Value : issuedValue, Label : 'Issued value' },
    ],
  },

  // The movement is ERP's document, not ours. A draw with no goods issue
  // against it has asked for stock nobody has moved yet, and the empty fields
  // here are the honest way to show that.
  UI.FieldGroup #Source : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : s4GIDoc, Label : 'ERP goods issue' },
      { $Type : 'UI.DataField', Value : s4GIDate, Label : 'Issued on' },
      { $Type : 'UI.DataField', Value : s4GIQty, Label : 'ERP quantity' },
      { $Type : 'UI.DataField', Value : s4System, Label : 'ERP system' },
      { $Type : 'UI.DataField', Value : syncMessage, Label : 'ERP message' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Draw', Label : 'Draw',
      Target : '@UI.FieldGroup#Draw' },
    { $Type : 'UI.ReferenceFacet', ID : 'Movement', Label : 'Movement',
      Target : '@UI.FieldGroup#Movement' },
    { $Type : 'UI.ReferenceFacet', ID : 'Receipts', Label : 'Site Receipts',
      Target : 'receipts/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Source', Label : 'ERP',
      Target : '@UI.FieldGroup#Source' },
  ],
);

annotate service.SiteReceipts with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : receivedOn, Label : 'Received on' },
    { $Type : 'UI.DataField', Value : receivedQty, Label : 'Received' },
    { $Type : 'UI.DataField', Value : shortQty, Label : 'Outstanding after this',
      Criticality : shortCriticality },
    { $Type : 'UI.DataField', Value : receivedBy, Label : 'Received by' },
    { $Type : 'UI.DataField', Value : note, Label : 'Note' },
  ],
);
