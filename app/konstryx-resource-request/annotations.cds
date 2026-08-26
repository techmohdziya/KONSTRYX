using WorkflowService as service from '../../srv/workflow-service';

/**
 * Resource Request — List Report and Object Page.
 *
 * ResourceRequests is draft-enabled and its lines are a composition, so the
 * line table below is editable in draft and carries its own create.
 */

annotate service.ResourceRequests with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Resource Request',
    TypeNamePlural : 'Resource Requests',
    Title          : { $Type : 'UI.DataField', Value : docNo },
    Description    : { $Type : 'UI.DataField', Value : verticalType },
  },

  /** State, vertical and need-by date are how a coordinator narrows the list. */
  UI.SelectionFields : [ status, verticalType, needBy ],

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : docNo,        Label : 'Request' },
    { $Type : 'UI.DataField', Value : verticalType, Label : 'Vertical' },
    { $Type : 'UI.DataField', Value : status,       Label : 'Status' },
    { $Type : 'UI.DataField', Value : needBy,       Label : 'Need by' },
    { $Type : 'UI.DataField', Value : raisedBy,     Label : 'Raised by' },
    { $Type : 'UI.DataField', Value : raisedOn,     Label : 'Raised on' },
  ],

  UI.FieldGroup #General : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : docNo,        Label : 'Request' },
      { $Type : 'UI.DataField', Value : verticalType, Label : 'Vertical' },
      { $Type : 'UI.DataField', Value : status,       Label : 'Status' },
      { $Type : 'UI.DataField', Value : needBy,       Label : 'Need by' },
    ],
  },

  UI.FieldGroup #Origin : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : project_ID,     Label : 'Project' },
      { $Type : 'UI.DataField', Value : company_ID,     Label : 'Company' },
      { $Type : 'UI.DataField', Value : wbs_ID,         Label : 'WBS element' },
      { $Type : 'UI.DataField', Value : raisedBy,       Label : 'Raised by' },
      { $Type : 'UI.DataField', Value : raisedOn,       Label : 'Raised on' },
      { $Type : 'UI.DataField', Value : isSubstitution, Label : 'Substitution (MSR)' },
      { $Type : 'UI.DataField', Value : prFlag,         Label : 'Direct PR' },
    ],
  },

  UI.Facets : [
    {
      $Type  : 'UI.ReferenceFacet',
      ID     : 'General',
      Label  : 'General',
      Target : '@UI.FieldGroup#General',
    },
    {
      $Type  : 'UI.ReferenceFacet',
      ID     : 'Origin',
      Label  : 'Origin',
      Target : '@UI.FieldGroup#Origin',
    },
    {
      $Type  : 'UI.ReferenceFacet',
      ID     : 'Lines',
      Label  : 'Line Items',
      Target : 'lines/@UI.LineItem',
    },
    {
      $Type  : 'UI.ReferenceFacet',
      ID     : 'Attachments',
      Label  : 'Attachments',
      Target : 'attachments/@UI.LineItem',
    },
  ],

  /**
   * The request chain, in the order it is walked. Each action validates the
   * request's state and returns the reason when it cannot run, so the buttons
   * stay visible rather than disappearing between steps.
   */
  UI.Identification : [
    { $Type  : 'UI.DataFieldForAction',
      Action : 'WorkflowService.submit',
      Label  : 'Submit for approval' },
    { $Type  : 'UI.DataFieldForAction',
      Action : 'WorkflowService.runAvailabilityCheck',
      Label  : 'Run availability check' },
    { $Type  : 'UI.DataFieldForAction',
      Action : 'WorkflowService.createReservation',
      Label  : 'Create reservation' },
    { $Type  : 'UI.DataFieldForAction',
      Action : 'WorkflowService.raisePurchaseRequisition',
      Label  : 'Raise purchase requisition' },
  ],
);

annotate service.ResourceRequestLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : lineNo,      Label : '#' },
    { $Type : 'UI.DataField', Value : resource_ID, Label : 'Resource' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : qty,         Label : 'Quantity' },
    { $Type : 'UI.DataField', Value : uom,         Label : 'UoM' },
    { $Type : 'UI.DataField', Value : wbs_ID,      Label : 'WBS' },
    { $Type : 'UI.DataField', Value : cbs_ID,      Label : 'CBS' },
    { $Type : 'UI.DataField', Value : estUnitCost, Label : 'Unit cost' },
    { $Type : 'UI.DataField', Value : estTotal,    Label : 'Line value' },
    { $Type : 'UI.DataField', Value : needBy,      Label : 'Need by' },
    { $Type : 'UI.DataField', Value : lineStatus,  Label : 'Status' },
  ],

  UI.FieldGroup #Line : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : lineNo,      Label : '#' },
      { $Type : 'UI.DataField', Value : resource_ID, Label : 'Resource' },
      { $Type : 'UI.DataField', Value : description, Label : 'Description' },
      { $Type : 'UI.DataField', Value : qty,         Label : 'Quantity' },
      { $Type : 'UI.DataField', Value : uom,         Label : 'UoM' },
      { $Type : 'UI.DataField', Value : wbs_ID,      Label : 'WBS' },
      { $Type : 'UI.DataField', Value : cbs_ID,      Label : 'CBS' },
      { $Type : 'UI.DataField', Value : estUnitCost, Label : 'Unit cost' },
      { $Type : 'UI.DataField', Value : estTotal,    Label : 'Line value' },
      { $Type : 'UI.DataField', Value : needBy,      Label : 'Need by' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Line', Label : 'Line',
      Target : '@UI.FieldGroup#Line' },
  ],
);

/**
 * What has been filed against a request: drawings, permits, method statements.
 *
 * The content column is what makes the row an upload rather than a record of
 * one - Core.MediaType on the field is what tells Fiori Elements to render a
 * file link and accept a file in return, and it is already on the model.
 */
annotate service.RequestAttachments with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : fileName, Label : 'File' },
    { $Type : 'UI.DataField', Value : mimeType, Label : 'Type' },
    { $Type : 'UI.DataField', Value : fileSize, Label : 'Size' },
    { $Type : 'UI.DataField', Value : note,     Label : 'Note' },
    { $Type : 'UI.DataField', Value : version,  Label : 'Version' },
    { $Type : 'UI.DataField', Value : createdBy, Label : 'Uploaded by' },
    { $Type : 'UI.DataField', Value : createdAt, Label : 'Uploaded at' },
  ],

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Attachment',
    TypeNamePlural : 'Attachments',
    Title          : { $Type : 'UI.DataField', Value : fileName },
    Description    : { $Type : 'UI.DataField', Value : note },
  },
);

annotate service.RequestAttachments with {
  entityName  @UI.Hidden;
  objectID    @UI.Hidden;
  objectDocNo @UI.Hidden;
  fileSize    @readonly;
  version     @readonly;
};
