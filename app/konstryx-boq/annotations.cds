using ProjectService as service from '../../srv/project-service';

annotate service.BOQs with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Bill of Quantities',
    TypeNamePlural : 'Bills of Quantities',
    Title          : { $Type : 'UI.DataField', Value : boqId },
    Description    : { $Type : 'UI.DataField', Value : status },
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : boqId, Label : 'Bill' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : version, Label : 'Version' },
    { $Type : 'UI.DataField', Value : contractValue, Label : 'Contract value' },
    { $Type : 'UI.DataField', Value : source, Label : 'Source' },
  ],

  UI.FieldGroup #Details : {
    $Type : 'UI.FieldGroupType',
    Data  : [
    { $Type : 'UI.DataField', Value : boqId, Label : 'Bill' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : version, Label : 'Version' },
    { $Type : 'UI.DataField', Value : contractValue, Label : 'Contract value' },
    { $Type : 'UI.DataField', Value : source, Label : 'Source' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
    { $Type : 'UI.ReferenceFacet', ID : 'Items', Label : 'Items',
      Target : 'items/@UI.LineItem' },
  ],
);

annotate service.BOQItems with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : itemNo, Label : 'Item' },
    { $Type : 'UI.DataField', Value : code, Label : 'Code' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : qty, Label : 'Contract qty' },
    { $Type : 'UI.DataField', Value : budgetQty, Label : 'Budget qty' },
    { $Type : 'UI.DataField', Value : uom, Label : 'UoM' },
    { $Type : 'UI.DataField', Value : rate, Label : 'Rate' },
    { $Type : 'UI.DataField', Value : amount, Label : 'Amount' },
    { $Type : 'UI.DataField', Value : cumDonePct, Label : 'Done %' },
    { $Type : 'UI.DataField', Value : certifiedPct, Label : 'Certified %' },
  ],
);
