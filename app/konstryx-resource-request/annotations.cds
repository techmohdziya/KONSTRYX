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
    /**
     * The document flow. A request is the spine of the chain and its own
     * screen said nothing about what it had become — whether it reached an
     * availability check, a reservation, a requisition, or stopped. The links
     * were being written all along and read by no one.
     */
    {
      $Type  : 'UI.ReferenceFacet',
      ID     : 'Flow',
      Label  : 'Document Flow',
      Target : 'flowOut/@UI.LineItem',
    },
    {
      $Type  : 'UI.ReferenceFacet',
      ID     : 'History',
      Label  : 'Status History',
      Target : 'history/@UI.LineItem',
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

/**
 * What a request line points at, in words.
 *
 * The line stored resource, WBS and CBS as keys and displayed them as keys, so
 * a reader saw "4c000000-0000-0000-0000-000000000005" where the resource
 * should be and reasonably concluded the line pointed at nothing in the
 * master. It always did; the screen simply never resolved it.
 */
annotate service.ResourceRequestLines with {
  lineNo      @title : 'Line';
  description @title : 'Description';
  qty         @title : 'Quantity';
  uom         @title : 'UoM';
  estUnitCost @title : 'Unit cost';
  estTotal    @title : 'Line value';
  needBy      @title : 'Need by';
  lineStatus  @title : 'Status';

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
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'description' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'level' }
      ]
    }
  };

  wbs @Common : {
    Text            : wbs.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'WBSElements',
      Label          : 'WBS element',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : wbs_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'description' }
      ]
    }
  };

  cbs @Common : {
    Text            : cbs.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'ProjectCBS',
      Label          : 'CBS node',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : cbs_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'level' }
      ]
    }
  };
};

/** The picker's own columns; without them it leads with the UUID. */
annotate service.Resources with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,        Label : 'Code' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : level,       Label : 'Level' },
    { $Type : 'UI.DataField', Value : verticalType, Label : 'Vertical' },
  ],
);
annotate service.Resources with { ID @UI.Hidden };

/**
 * One step of the chain: what this document produced, and how.
 */
annotate service.DocumentLinks with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : linkType, Label : 'Step' },
    { $Type : 'UI.DataField', Value : fromDoc,  Label : 'From document' },
    { $Type : 'UI.DataField', Value : toDoc,    Label : 'To document' },
    { $Type : 'UI.DataField', Value : linkedAt, Label : 'Linked at' },
  ],

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Chain Step',
    TypeNamePlural : 'Document Flow',
    Title          : { $Type : 'UI.DataField', Value : linkType },
    Description    : { $Type : 'UI.DataField', Value : toDoc },
  },
);

annotate service.DocumentLinks with {
  linkType @title : 'Step';
  fromDoc  @title : 'From document';
  toDoc    @title : 'To document';
  linkedAt @title : 'Linked at';
  ID       @UI.Hidden;
};

annotate service.StatusHistory with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : changedOn, Label : 'When' },
    { $Type : 'UI.DataField', Value : fromState, Label : 'From' },
    { $Type : 'UI.DataField', Value : toState,   Label : 'To' },
    { $Type : 'UI.DataField', Value : changedBy, Label : 'By' },
    { $Type : 'UI.DataField', Value : comment,   Label : 'Comment' },
  ],
);

annotate service.StatusHistory with {
  changedOn @title : 'When';
  fromState @title : 'From';
  toState   @title : 'To';
  changedBy @title : 'By';
  comment   @title : 'Comment';
  ID        @UI.Hidden;
};

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
