using CollaborationService as service from '../../srv/authorization-service';

annotate service.MyApprovals with {
  docNo        @title : 'Document';
  docType      @title : 'Type';
  stepName     @title : 'Step';
  stepNo       @title : 'Step no.';
  amount       @title : 'Value';
  waitingSince @title : 'Waiting since';
  delegatedTo  @title : 'Delegated to';
  entityName   @title : 'Object';
};

annotate service.MyApprovals with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Approval',
    TypeNamePlural : 'My Approvals',
    Title          : { $Type : 'UI.DataField', Value : docNo },
    Description    : { $Type : 'UI.DataField', Value : stepName },
  },

  // What is worth filtering an inbox by: the kind of document, and its value.
  // Not the person, because every row here is already this person's.
  UI.SelectionFields : [ docType, amount ],

  UI.PresentationVariant : {
    $Type          : 'UI.PresentationVariantType',
    // Oldest first. An approval queue read newest-first is one where the
    // document that has waited longest is the one furthest from the eye.
    SortOrder      : [
      { $Type : 'Common.SortOrderType', Property : waitingSince, Descending : false },
    ],
    Visualizations : [ '@UI.LineItem' ],
  },

  // Enough to decide whether to open it: which document, what it is worth,
  // which step, and how long it has been sitting. A row that has to be opened
  // to find out what it is has moved the work rather than organised it.
  UI.LineItem : [
    { $Type : 'UI.DataFieldForAction', Label : 'Approve',
      Action : 'CollaborationService.approve' },
    { $Type : 'UI.DataFieldForAction', Label : 'Reject',
      Action : 'CollaborationService.reject' },
    { $Type : 'UI.DataField', Value : docNo, Label : 'Document' },
    { $Type : 'UI.DataField', Value : docType, Label : 'Type' },
    { $Type : 'UI.DataField', Value : amount, Label : 'Value' },
    { $Type : 'UI.DataField', Value : stepName, Label : 'Step' },
    { $Type : 'UI.DataField', Value : waitingSince, Label : 'Waiting since' },
    { $Type : 'UI.DataField', Value : delegatedTo, Label : 'Delegated to' },
  ],
);

// A decision removes the row from the list it was taken in, so the table is
// told to re-read itself rather than leave a row that is no longer waiting.
annotate service.MyApprovals actions {
  approve @(Common.SideEffects.TargetEntities : [ '/CollaborationService.EntityContainer/MyApprovals' ]);
  reject  @(Common.SideEffects.TargetEntities : [ '/CollaborationService.EntityContainer/MyApprovals' ]);
};
