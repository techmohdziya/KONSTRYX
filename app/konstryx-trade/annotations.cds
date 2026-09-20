using MasterDataService as service from '../../srv/masterdata-service';

annotate service.Trades with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Trade',
    TypeNamePlural : 'Trades',
    Title          : { $Type : 'UI.DataField', Value : description },
    Description    : { $Type : 'UI.DataField', Value : code },
  },

  UI.SelectionFields : [ code, discipline ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    SortOrder      : [ { $Type : 'Common.SortOrderType', Property : code } ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Trade' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : discipline, Label : 'Discipline' },
  ],

  UI.FieldGroup #Trade : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code, Label : 'Trade' },
      { $Type : 'UI.DataField', Value : description, Label : 'Description' },
      { $Type : 'UI.DataField', Value : discipline, Label : 'Discipline' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Trade', Label : 'Trade',
      Target : '@UI.FieldGroup#Trade' },
    { $Type : 'UI.ReferenceFacet', ID : 'Grades', Label : 'Grades',
      Target : 'grades/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Certificates', Label : 'Cards a man must hold',
      Target : 'certificates/@UI.LineItem' },
  ],
);

annotate service.TradeGrades with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : sequence, Label : 'Order' },
    { $Type : 'UI.DataField', Value : code, Label : 'Grade' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
  ],
);

// Blocking is the column that matters: a lapsed blocking card takes the
// man out of his gang's manning without anybody recording an absence.
annotate service.TradeCertificates with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Certificate' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : blocking, Label : 'Stops him working' },
  ],
);
