using ProjectService as service from '../../srv/project-service';

/**
 * Variation orders — what changed after the contract was signed.
 *
 * Revenue and cost sit side by side on every row, because they are different
 * questions with different answers: a remeasure at contract rates can add
 * revenue and lose money, and a single "value" column is how that happens
 * without anyone noticing. The margin carries its colour so a variation that
 * loses money is visible before the number is read.
 */
annotate service.Variations with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Variation Order',
    TypeNamePlural : 'Variation Orders',
    Title          : { $Type : 'UI.DataField', Value : docNo },
    Description    : { $Type : 'UI.DataField', Value : title },
  },

  UI.SelectionFields : [ status, origin, projectCode ],

  UI.DataPoint #Revenue : {
    $Type : 'UI.DataPointType',
    Value : revenueAmount,
    Title : 'Claimed from client',
  },
  UI.DataPoint #Margin : {
    $Type       : 'UI.DataPointType',
    Value       : marginPct,
    Title       : 'Margin %',
    Criticality : marginCriticality,
  },
  UI.DataPoint #Time : {
    $Type : 'UI.DataPointType',
    Value : timeExtensionDays,
    Title : 'Extension of time (days)',
  },

  UI.HeaderFacets : [
    { $Type : 'UI.ReferenceFacet', ID : 'hRevenue', Target : '@UI.DataPoint#Revenue' },
    { $Type : 'UI.ReferenceFacet', ID : 'hMargin',  Target : '@UI.DataPoint#Margin' },
    { $Type : 'UI.ReferenceFacet', ID : 'hTime',    Target : '@UI.DataPoint#Time' },
  ],

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : docNo,         Label : 'Variation' },
    { $Type : 'UI.DataField', Value : title,         Label : 'Title' },
    { $Type : 'UI.DataField', Value : project_ID,    Label : 'Project' },
    { $Type : 'UI.DataField', Value : status,        Label : 'Status',
      Criticality : statusCriticality },
    { $Type : 'UI.DataField', Value : origin,        Label : 'Origin' },
    { $Type : 'UI.DataField', Value : revenueAmount, Label : 'Revenue' },
    { $Type : 'UI.DataField', Value : costAmount,    Label : 'Cost' },
    { $Type : 'UI.DataField', Value : marginAmount,  Label : 'Margin',
      Criticality : marginCriticality },
    { $Type : 'UI.DataField', Value : marginPct,     Label : 'Margin %',
      Criticality : marginCriticality },
    { $Type : 'UI.DataField', Value : timeExtensionDays, Label : 'EOT (d)' },
    { $Type : 'UI.DataField', Value : clientRef,     Label : 'Client reference' },
  ],

  /**
   * The chain, in the order it is walked. The buttons stay visible between
   * steps and each action says why it cannot run, rather than disappearing and
   * leaving a user to guess what state the document is in.
   */
  UI.Identification : [
    { $Type : 'UI.DataFieldForAction', Label : 'Recalculate',
      Action : 'ProjectService.recalculate' },
    { $Type : 'UI.DataFieldForAction', Label : 'Submit to client',
      Action : 'ProjectService.submit' },
    { $Type : 'UI.DataFieldForAction', Label : 'Approve',
      Action : 'ProjectService.approve' },
    { $Type : 'UI.DataFieldForAction', Label : 'Reject',
      Action : 'ProjectService.reject' },
  ],

  UI.FieldGroup #Change : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : docNo,          Label : 'Variation' },
      { $Type : 'UI.DataField', Value : title,          Label : 'Title' },
      { $Type : 'UI.DataField', Value : project_ID,     Label : 'Project' },
      { $Type : 'UI.DataField', Value : boq_ID,         Label : 'Bill varied' },
      { $Type : 'UI.DataField', Value : origin,         Label : 'Origin' },
      { $Type : 'UI.DataField', Value : instructionRef, Label : 'Instruction' },
      { $Type : 'UI.DataField', Value : instructedOn,   Label : 'Instructed on' },
    ],
  },

  /**
   * Both sides of the money. A variation that adds revenue and loses margin is
   * the one worth finding, and it is invisible on any screen that shows a
   * single value.
   */
  UI.FieldGroup #Money : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : revenueAmount, Label : 'Claimed from client' },
      { $Type : 'UI.DataField', Value : costAmount,    Label : 'Cost to build' },
      { $Type : 'UI.DataField', Value : marginAmount,  Label : 'Margin',
        Criticality : marginCriticality },
      { $Type : 'UI.DataField', Value : marginPct,     Label : 'Margin %',
        Criticality : marginCriticality },
      { $Type : 'UI.DataField', Value : ccy_code,      Label : 'Currency' },
    ],
  },

  UI.FieldGroup #Decision : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : status,            Label : 'Status',
        Criticality : statusCriticality },
      { $Type : 'UI.DataField', Value : submittedOn,       Label : 'Submitted' },
      { $Type : 'UI.DataField', Value : decidedOn,         Label : 'Decided' },
      { $Type : 'UI.DataField', Value : decidedBy,         Label : 'Decided by' },
      { $Type : 'UI.DataField', Value : clientRef,         Label : 'Client reference' },
      { $Type : 'UI.DataField', Value : timeExtensionDays, Label : 'Extension of time (days)' },
      { $Type : 'UI.DataField', Value : decisionNote,      Label : 'Note' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Change', Label : 'The change',
      Target : '@UI.FieldGroup#Change' },
    { $Type : 'UI.ReferenceFacet', ID : 'Lines', Label : 'Priced Lines',
      Target : 'lines/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Money', Label : 'Money',
      Target : '@UI.FieldGroup#Money' },
    { $Type : 'UI.ReferenceFacet', ID : 'Decision', Label : 'Decision',
      Target : '@UI.FieldGroup#Decision' },
  ],
);

annotate service.Variations with {
  docNo             @title : 'Variation';
  title             @title : 'Title';
  clientRef         @title : 'Client reference';
  origin            @title : 'Origin';
  instructionRef    @title : 'Instruction';
  instructedOn      @title : 'Instructed on';
  submittedOn       @title : 'Submitted';
  decidedOn         @title : 'Decided';
  decidedBy         @title : 'Decided by';
  decisionNote      @title : 'Decision note';
  revenueAmount     @title : 'Claimed from client';
  costAmount        @title : 'Cost to build';
  marginAmount      @title : 'Margin';
  marginPct         @title : 'Margin %';
  timeExtensionDays @title : 'Extension of time (days)';
  status            @title : 'Status';
  raisedBy          @title : 'Raised by';
  raisedOn          @title : 'Raised on';
  marginCriticality @UI.Hidden;
  statusCriticality @UI.Hidden;

  project @Common : {
    Text            : project.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'Projects',
      Label          : 'Project',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : project_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' }
      ]
    }
  };

  boq @Common : {
    Text            : boq.boqId,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'BOQs',
      Label          : 'Bill of quantities',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : boq_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'boqId' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'version' }
      ]
    }
  };
};

/**
 * One changed item. The bill line it varies is named where it varies one; new
 * scope names none, and that distinction is what separates a remeasure argued
 * at contract rates from work argued at whatever was agreed for it.
 */
annotate service.VariationLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : lineNo,        Label : '#' },
    { $Type : 'UI.DataField', Value : changeType,    Label : 'Change' },
    { $Type : 'UI.DataField', Value : description,   Label : 'Description' },
    { $Type : 'UI.DataField', Value : boqItem_ID,    Label : 'Bill line varied' },
    { $Type : 'UI.DataField', Value : qty,           Label : 'Quantity' },
    { $Type : 'UI.DataField', Value : uom,           Label : 'UoM' },
    { $Type : 'UI.DataField', Value : revenueRate,   Label : 'Revenue rate' },
    { $Type : 'UI.DataField', Value : costRate,      Label : 'Cost rate' },
    { $Type : 'UI.DataField', Value : revenueAmount, Label : 'Revenue' },
    { $Type : 'UI.DataField', Value : costAmount,    Label : 'Cost' },
    { $Type : 'UI.DataField', Value : wbs_ID,        Label : 'WBS' },
    { $Type : 'UI.DataField', Value : cbs_ID,        Label : 'CBS' },
  ],

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Variation Line',
    TypeNamePlural : 'Priced Lines',
    Title          : { $Type : 'UI.DataField', Value : description },
    Description    : { $Type : 'UI.DataField', Value : changeType },
  },
);

annotate service.VariationLines with {
  lineNo        @title : 'Line';
  changeType    @title : 'Change';
  description   @title : 'Description';
  qty           @title : 'Quantity';
  uom           @title : 'UoM';
  revenueRate   @title : 'Revenue rate';
  costRate      @title : 'Cost rate';
  revenueAmount @title : 'Revenue';
  costAmount    @title : 'Cost';

  boqItem @Common : {
    Text            : boqItem.itemNo,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'BOQItems',
      Label          : 'Bill line',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : boqItem_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'itemNo' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'description' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'rate' }
      ]
    }
  };

  wbs @Common : {
    Text            : wbs.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'WBS',
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
      CollectionPath : 'CBS',
      Label          : 'CBS node',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : cbs_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' }
      ]
    }
  };
};

/** The project as a person names it, not as the service keys it. */
annotate service.Variations with {
  projectCode @title : 'Project';
  projectName @title : 'Project name';
}
