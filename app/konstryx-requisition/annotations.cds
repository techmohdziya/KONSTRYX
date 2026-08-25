using MaterialService as service from '../../srv/material-service';

annotate service.PurchaseRequisitions with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Purchase Requisition',
    TypeNamePlural : 'Purchase Requisitions',
    Title          : { $Type : 'UI.DataField', Value : prNo },
    Description    : { $Type : 'UI.DataField', Value : status },
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : prNo, Label : 'Requisition' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : raisedBy, Label : 'Raised by' },
    { $Type : 'UI.DataField', Value : raisedOn, Label : 'Raised on' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'S/4 sync' },
    { $Type : 'UI.DataField', Value : s4Key, Label : 'S/4 number' },
    { $Type : 'UI.DataField', Value : syncMessage, Label : 'S/4 message' },
    { $Type : 'UI.DataField', Value : syncAttempts, Label : 'Attempts' },
  ],

  UI.FieldGroup #Details : {
    $Type : 'UI.FieldGroupType',
    Data  : [
    { $Type : 'UI.DataField', Value : prNo, Label : 'Requisition' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : raisedBy, Label : 'Raised by' },
    { $Type : 'UI.DataField', Value : raisedOn, Label : 'Raised on' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'S/4 sync' },
    { $Type : 'UI.DataField', Value : s4Key, Label : 'S/4 number' },
    { $Type : 'UI.DataField', Value : syncMessage, Label : 'S/4 message' },
    { $Type : 'UI.DataField', Value : syncAttempts, Label : 'Attempts' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
    { $Type : 'UI.ReferenceFacet', ID : 'RequisitionLines', Label : 'Requisition Lines',
      Target : 'lines/@UI.LineItem' },
  ],
);

annotate service.PurchaseRequisitionLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : lineNo, Label : '#' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : qtyProcure, Label : 'Quantity' },
    { $Type : 'UI.DataField', Value : uom, Label : 'UoM' },
    { $Type : 'UI.DataField', Value : estUnitPrice, Label : 'Unit price' },
    { $Type : 'UI.DataField', Value : estTotal, Label : 'Line value' },
    { $Type : 'UI.DataField', Value : needBy, Label : 'Need by' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
  ],
);
