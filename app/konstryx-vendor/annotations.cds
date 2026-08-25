using MasterDataService as service from '../../srv/masterdata-service';

annotate service.Vendors with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Vendor',
    TypeNamePlural : 'Vendors',
    Title          : { $Type : 'UI.DataField', Value : bpNumber },
    Description    : { $Type : 'UI.DataField', Value : name },
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : bpNumber, Label : 'Business partner' },
    { $Type : 'UI.DataField', Value : name, Label : 'Name' },
    { $Type : 'UI.DataField', Value : purchOrgs, Label : 'Purchasing orgs' },
    { $Type : 'UI.DataField', Value : paymentTerms, Label : 'Payment terms' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : s4System, Label : 'Source system' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'Sync' },
  ],

  UI.FieldGroup #Details : {
    $Type : 'UI.FieldGroupType',
    Data  : [
    { $Type : 'UI.DataField', Value : bpNumber, Label : 'Business partner' },
    { $Type : 'UI.DataField', Value : name, Label : 'Name' },
    { $Type : 'UI.DataField', Value : purchOrgs, Label : 'Purchasing orgs' },
    { $Type : 'UI.DataField', Value : paymentTerms, Label : 'Payment terms' },
    { $Type : 'UI.DataField', Value : status, Label : 'Status' },
    { $Type : 'UI.DataField', Value : s4System, Label : 'Source system' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'Sync' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
  ],
);
