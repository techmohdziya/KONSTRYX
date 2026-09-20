using MasterDataService as service from '../../srv/masterdata-service';

/**
 * Customers, mirrored from S/4.
 *
 * A project's client was free text on the project itself, which is enough to
 * print on a report and useless for anything else: two spellings are two
 * clients, nothing can be filtered, and no project can point at the account
 * that will be invoiced. This is the customer role of the same business
 * partner the supplier mirror reads.
 *
 * Read-only, like every mirror. Correcting a customer means correcting it in
 * ERP and reading it again.
 */
annotate service.Customers with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Customer',
    TypeNamePlural : 'Customers',
    Title          : { $Type : 'UI.DataField', Value : name },
    Description    : { $Type : 'UI.DataField', Value : bpNumber },
  },

  UI.SelectionFields : [ bpNumber, name, country, accountGroup ],

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : bpNumber,     Label : 'Business partner' },
    { $Type : 'UI.DataField', Value : name,         Label : 'Name' },
    { $Type : 'UI.DataField', Value : accountGroup, Label : 'Account group' },
    { $Type : 'UI.DataField', Value : country,      Label : 'Country' },
    { $Type : 'UI.DataField', Value : city,         Label : 'City' },
    { $Type : 'UI.DataField', Value : s4System,     Label : 'Source system' },
    { $Type : 'UI.DataField', Value : syncStatus,   Label : 'Sync' },
  ],

  UI.FieldGroup #Details : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : bpNumber,     Label : 'Business partner' },
      { $Type : 'UI.DataField', Value : name,         Label : 'Name' },
      { $Type : 'UI.DataField', Value : accountGroup, Label : 'Account group' },
      { $Type : 'UI.DataField', Value : country,      Label : 'Country' },
      { $Type : 'UI.DataField', Value : city,         Label : 'City' },
      { $Type : 'UI.DataField', Value : status,       Label : 'Status' },
    ],
  },

  UI.FieldGroup #Source : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : s4Key,        Label : 'ERP key' },
      { $Type : 'UI.DataField', Value : s4System,     Label : 'Source system' },
      { $Type : 'UI.DataField', Value : lastSyncedAt, Label : 'Last read' },
      { $Type : 'UI.DataField', Value : syncStatus,   Label : 'Sync' },
      { $Type : 'UI.DataField', Value : syncMessage,  Label : 'Message' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
    { $Type : 'UI.ReferenceFacet', ID : 'Source', Label : 'Source',
      Target : '@UI.FieldGroup#Source' },
  ],
);

annotate service.Customers with {
  bpNumber     @title : 'Business partner';
  name         @title : 'Name';
  accountGroup @title : 'Account group';
  country      @title : 'Country';
  city         @title : 'City';
  status       @title : 'Status';
};
