using ProjectService as service from '../../srv/project-service';

annotate service.Projects with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Project',
    TypeNamePlural : 'Projects',
    Title          : { $Type : 'UI.DataField', Value : code },
    Description    : { $Type : 'UI.DataField', Value : name },
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'Project' },
    { $Type : 'UI.DataField', Value : name, Label : 'Name' },
    { $Type : 'UI.DataField', Value : stage, Label : 'Stage' },
    { $Type : 'UI.DataField', Value : contractValue, Label : 'Contract value' },
    { $Type : 'UI.DataField', Value : startDate, Label : 'Start' },
    { $Type : 'UI.DataField', Value : endDate, Label : 'Finish' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'ERP sync' },
    { $Type : 'UI.DataField', Value : s4Key, Label : 'ERP project' },
  ],

  UI.FieldGroup #Details : {
    $Type : 'UI.FieldGroupType',
    Data  : [
    { $Type : 'UI.DataField', Value : code, Label : 'Project' },
    { $Type : 'UI.DataField', Value : name, Label : 'Name' },
    { $Type : 'UI.DataField', Value : stage, Label : 'Stage' },
    { $Type : 'UI.DataField', Value : contractValue, Label : 'Contract value' },
    { $Type : 'UI.DataField', Value : startDate, Label : 'Start' },
    { $Type : 'UI.DataField', Value : endDate, Label : 'Finish' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'ERP sync' },
    { $Type : 'UI.DataField', Value : s4Key, Label : 'ERP project' },
    ],
  },

  /**
   * Where the structure on the next tab came from, and when.
   *
   * A WBS tree read out of the planner's tool is a copy, and a copy with no
   * date on it is one every reader re-checks by hand. Blank on a project whose
   * structure was built here, which is the honest answer rather than a gap.
   */
  UI.FieldGroup #Programme : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : p6ProjectId, Label : 'P6 project' },
      { $Type : 'UI.DataField', Value : p6File, Label : 'Last export' },
      { $Type : 'UI.DataField', Value : p6LastSyncedAt, Label : 'Synced' },
      { $Type : 'UI.DataField', Value : p6SyncMessage, Label : 'Outcome' },
    ],
  },

  UI.Identification : [
    { $Type  : 'UI.DataFieldForAction',
      Action : 'ProjectService.schedule',
      Label  : 'Run critical path' },
    { $Type  : 'UI.DataFieldForAction',
      Action : 'ProjectService.releaseToS4',
      Label  : 'Release to ERP' },
    { $Type  : 'UI.DataFieldForAction',
      Action : 'ProjectService.measureProductivity',
      Label  : 'Measure productivity' },
    { $Type  : 'UI.DataFieldForAction',
      Action : 'ProjectService.syncWBSFromP6',
      Label  : 'Sync WBS from Primavera P6' },
  ],

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
    { $Type : 'UI.ReferenceFacet', ID : 'Programme', Label : 'Programme Source',
      Target : '@UI.FieldGroup#Programme' },
    { $Type : 'UI.ReferenceFacet', ID : 'WBSElements', Label : 'WBS Elements',
      Target : 'wbsElements/@UI.PresentationVariant#WBSTree' },
    { $Type : 'UI.ReferenceFacet', ID : 'Bills', Label : 'Bills of Quantities',
      Target : 'boqs/@UI.LineItem#OnProject' },
    { $Type : 'UI.ReferenceFacet', ID : 'CostBreakdown', Label : 'Cost Breakdown',
      Target : 'cbs/@UI.PresentationVariant#CBSTree' },
    { $Type : 'UI.ReferenceFacet', ID : 'Schedule', Label : 'Schedule',
      Target : 'activities/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'CostMapping', Label : 'Cost Mapping',
      Target : 'allocations/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Locations', Label : 'Site Locations',
      Target : 'locations/@UI.LineItem' },
  ],
);

annotate service.WBS with @(
  /**
   * The tree opens showing three levels rather than three roots.
   *
   * A collapsed tree is the right default for a catalogue nobody is reading
   * end to end; a work breakdown is read to see the breakdown, and one that
   * opens as three headings makes a reader click before it has said anything.
   * The depth comes from the presentation variant because that is where Fiori
   * Elements reads it — the same setting written into the manifest's table
   * settings is ignored, which is not visible anywhere except in the request
   * the table sends.
   */
  UI.PresentationVariant #WBSTree : {
    $Type                 : 'UI.PresentationVariantType',
    InitialExpansionLevel : 3,
    Visualizations        : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'WBS' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : activityType, Label : 'Activity type' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'ERP sync' },
    { $Type : 'UI.DataField', Value : s4Key, Label : 'ERP element' },
  ],

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'WBS Element',
    TypeNamePlural : 'WBS Elements',
    Title          : { $Type : 'UI.DataField', Value : code },
    Description    : { $Type : 'UI.DataField', Value : description },
  },

  UI.FieldGroup #WBSDetails : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code,         Label : 'WBS' },
      { $Type : 'UI.DataField', Value : description,  Label : 'Description' },
      { $Type : 'UI.DataField', Value : activityType, Label : 'Activity type' },
      { $Type : 'UI.DataField', Value : parent_ID,    Label : 'Under' },
      { $Type : 'UI.DataField', Value : syncStatus,   Label : 'ERP sync' },
      { $Type : 'UI.DataField', Value : s4Key,        Label : 'ERP element' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'WBSDetails', Label : 'Details',
      Target : '@UI.FieldGroup#WBSDetails' },
    { $Type : 'UI.ReferenceFacet', ID : 'WBSActivities', Label : 'Activities',
      Target : 'activities/@UI.LineItem' },
  ],
);

annotate service.WBS with {
  code         @title : 'WBS';
  description  @title : 'Description';
  activityType @title : 'Activity type';

  // The parent is picked from the same project's tree. Without the text
  // arrangement the field shows the UUID it stores, which is what made the
  // flat list unreadable in the first place.
  parent @Common : {
    Text            : parent.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'WBS',
      Label          : 'Parent WBS element',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : parent_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'description' }
      ]
    }
  };
};

annotate service.BOQs with @(
  UI.LineItem #OnProject : [
    { $Type : 'UI.DataField', Value : boqId,         Label : 'Bill' },
    { $Type : 'UI.DataField', Value : version,       Label : 'Version' },
    { $Type : 'UI.DataField', Value : status,        Label : 'Status' },
    { $Type : 'UI.DataField', Value : contractValue, Label : 'Contract value' },
    { $Type : 'UI.DataField', Value : source,        Label : 'Source' },
  ],
);

annotate service.CBS with @(
  /**
   * Opens two levels deep: the phases, and what sits under each. Deeper is the
   * leaves a budget line is posted to, which is a search rather than a browse.
   */
  UI.PresentationVariant #CBSTree : {
    $Type                 : 'UI.PresentationVariantType',
    InitialExpansionLevel : 2,
    // By code, so a breakdown reads 01.10, 01.20, 01.30 rather than in
    // whatever order the rows come back. A cost structure out of order is
    // one a reader has to sort in their head before they can use it.
    SortOrder             : [ { $Type : 'Common.SortOrderType',
                                Property : code, Descending : false } ],
    Visualizations        : [ '@UI.LineItem' ],
  },

  // Own budget beside the rolled-up figure, because a parent that carries real
  // cost of its own reads identically to a heading when only the total shows.
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,         Label : 'CBS' },
    { $Type : 'UI.DataField', Value : name,         Label : 'Name' },
    { $Type : 'UI.DataField', Value : level,        Label : 'Level' },
    { $Type : 'UI.DataField', Value : costNature,   Label : 'Cost nature' },
    { $Type : 'UI.DataField', Value : ownAmount,    Label : 'Own budget' },
    { $Type : 'UI.DataField', Value : budgetAmount, Label : 'Rolled up' },
    { $Type : 'UI.DataFieldForAction', Label : 'Roll up budget',
      Action : 'ProjectService.rollUpBudget' },
  ],

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'CBS Node',
    TypeNamePlural : 'Cost Breakdown',
    Title          : { $Type : 'UI.DataField', Value : code },
    Description    : { $Type : 'UI.DataField', Value : name },
  },

  UI.Identification : [
    { $Type : 'UI.DataFieldForAction', Label : 'Roll up budget',
      Action : 'ProjectService.rollUpBudget' },
  ],
);

// Rolling up rewrites every node on the project, not only the one the button
// was pressed on, so the whole collection has to be re-read.
annotate service.Projects with @(
  Common.SideEffects #RolledUp : {
    SourceEvents   : [ 'ProjectService.rollUpBudget' ],
    TargetEntities : [ cbs ],
  }
);

annotate service.Activities with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,          Label : 'Activity' },
    { $Type : 'UI.DataField', Value : name,          Label : 'Name' },
    { $Type : 'UI.DataField', Value : wbs_ID,        Label : 'WBS' },
    { $Type : 'UI.DataField', Value : durationDays,  Label : 'Duration (d)' },
    { $Type : 'UI.DataField', Value : plannedStart,  Label : 'Planned start' },
    { $Type : 'UI.DataField', Value : plannedFinish, Label : 'Planned finish' },
    { $Type : 'UI.DataField', Value : earlyStart,    Label : 'Early start' },
    { $Type : 'UI.DataField', Value : earlyFinish,   Label : 'Early finish' },
    { $Type : 'UI.DataField', Value : lateStart,     Label : 'Late start' },
    { $Type : 'UI.DataField', Value : lateFinish,    Label : 'Late finish' },
    { $Type : 'UI.DataField', Value : totalFloat,    Label : 'Total float' },
    { $Type : 'UI.DataField', Value : isCritical,    Label : 'Critical' },
    { $Type : 'UI.DataField', Value : percentDone,   Label : 'Done %' },
    { $Type : 'UI.DataField', Value : status,        Label : 'Status' },
  ],

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Activity',
    TypeNamePlural : 'Activities',
    Title          : { $Type : 'UI.DataField', Value : code },
    Description    : { $Type : 'UI.DataField', Value : name },
  },

  UI.FieldGroup #ActivityDetails : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : code,          Label : 'Activity' },
      { $Type : 'UI.DataField', Value : name,          Label : 'Name' },
      { $Type : 'UI.DataField', Value : wbs_ID,        Label : 'WBS' },
      { $Type : 'UI.DataField', Value : durationDays,  Label : 'Duration (d)' },
      { $Type : 'UI.DataField', Value : plannedStart,  Label : 'Planned start' },
      { $Type : 'UI.DataField', Value : plannedFinish, Label : 'Planned finish' },
      { $Type : 'UI.DataField', Value : actualStart,   Label : 'Actual start' },
      { $Type : 'UI.DataField', Value : actualFinish,  Label : 'Actual finish' },
      { $Type : 'UI.DataField', Value : percentDone,   Label : 'Done %' },
      { $Type : 'UI.DataField', Value : status,        Label : 'Status' },
    ],
  },

  /**
   * The scheduled dates, kept apart from the agreed ones. Every field here is
   * an output of the critical path pass: typing into a derived date produces a
   * schedule that disagrees with its own network and says nothing about which
   * of the two is right.
   */
  UI.FieldGroup #ActivitySchedule : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : earlyStart,  Label : 'Early start' },
      { $Type : 'UI.DataField', Value : earlyFinish, Label : 'Early finish' },
      { $Type : 'UI.DataField', Value : lateStart,   Label : 'Late start' },
      { $Type : 'UI.DataField', Value : lateFinish,  Label : 'Late finish' },
      { $Type : 'UI.DataField', Value : totalFloat,  Label : 'Total float' },
      { $Type : 'UI.DataField', Value : freeFloat,   Label : 'Free float' },
      { $Type : 'UI.DataField', Value : isCritical,  Label : 'On the critical path' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'ActivityDetails', Label : 'Details',
      Target : '@UI.FieldGroup#ActivityDetails' },
    /**
     * The dependencies. A duration on its own is not a programme — what makes
     * one is which activity cannot start until another has finished, and by
     * how many days it trails. Editable here because this is the only place a
     * planner can state it.
     */
    { $Type : 'UI.ReferenceFacet', ID : 'Predecessors', Label : 'Predecessors',
      Target : 'predecessors/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'ActivitySchedule', Label : 'Calculated Dates',
      Target : '@UI.FieldGroup#ActivitySchedule' },
  ],
);

annotate service.Activities with {
  code          @title : 'Activity';
  name          @title : 'Name';
  durationDays  @title : 'Duration (days)';
  plannedStart  @title : 'Planned start';
  plannedFinish @title : 'Planned finish';
  actualStart   @title : 'Actual start';
  actualFinish  @title : 'Actual finish';
  percentDone   @title : 'Done %';
  status        @title : 'Status';
  earlyStart    @title : 'Early start';
  earlyFinish   @title : 'Early finish';
  lateStart     @title : 'Late start';
  lateFinish    @title : 'Late finish';
  totalFloat    @title : 'Total float';
  freeFloat     @title : 'Free float';
  isCritical    @title : 'Critical';

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
};

/**
 * One link in the network: what has to happen first, of which kind, with what
 * lag. The four link types are offered rather than assumed — a site programme
 * routinely overlaps trades start-to-start, and forcing finish-to-start would
 * push every downstream date out and make the float column fiction.
 */
annotate service.ActivityRelations with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : predecessor_ID, Label : 'Predecessor' },
    { $Type : 'UI.DataField', Value : linkType,       Label : 'Link' },
    { $Type : 'UI.DataField', Value : lagDays,        Label : 'Lag (days)' },
  ],

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Dependency',
    TypeNamePlural : 'Dependencies',
    Title          : { $Type : 'UI.DataField', Value : linkType },
  },
);

annotate service.ActivityRelations with {
  linkType @title : 'Link type';
  lagDays  @title : 'Lag (days)';

  predecessor @Common : {
    Text            : predecessor.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'Activities',
      Label          : 'Predecessor activity',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : predecessor_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'durationDays' }
      ]
    }
  };
};

/**
 * Bill line x WBS x CBS: the row that says what was sold, who builds it and
 * which cost node absorbs it. Nothing joined those three on one screen before,
 * so a bill could be priced, a WBS scheduled and a CBS budgeted with no
 * statement anywhere that they were the same work.
 */
annotate service.Allocations with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : boqItem_ID,  Label : 'Bill line' },
    { $Type : 'UI.DataField', Value : wbs_ID,      Label : 'WBS' },
    { $Type : 'UI.DataField', Value : cbs_ID,      Label : 'CBS' },
    { $Type : 'UI.DataField', Value : location_ID, Label : 'Location' },
    { $Type : 'UI.DataField', Value : allocQty,    Label : 'Quantity' },
    { $Type : 'UI.DataField', Value : pctOfItem,   Label : '% of line' },
    { $Type : 'UI.DataField', Value : template,    Label : 'Template' },
    { $Type : 'UI.DataField', Value : splitBasis,  Label : 'Basis' },
  ],

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Allocation',
    TypeNamePlural : 'Cost Mapping',
    Title          : { $Type : 'UI.DataField', Value : allocQty },
  },
);

annotate service.Allocations with {
  allocQty     @title : 'Quantity';
  allocPct     @title : 'Allocated %';
  pctOfItem    @title : '% of line';
  pctOfCBSRate @title : '% of CBS rate';
  template     @title : 'Template';
  splitBasis   @title : 'Basis';

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
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'description' }
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
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'level' }
      ]
    }
  };

  location @Common : {
    Text            : location.code,
    TextArrangement : #TextOnly,
    ValueList       : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'SiteLocations',
      Label          : 'Site location',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : location_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' }
      ]
    }
  };
};

/**
 * The site's own geography. Buildings, floors and zones are what a daily log
 * charges to and what productivity is reported per — a project without them
 * can only report output per man-hour for the whole job, which is a figure
 * nobody can act on.
 */
annotate service.SiteLocations with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,         Label : 'Location' },
    { $Type : 'UI.DataField', Value : name,         Label : 'Name' },
    { $Type : 'UI.DataField', Value : locationType, Label : 'Type' },
    { $Type : 'UI.DataField', Value : level,        Label : 'Level' },
    { $Type : 'UI.DataField', Value : parent_ID,    Label : 'Under' },
    { $Type : 'UI.DataField', Value : gfa,          Label : 'GFA' },
    { $Type : 'UI.DataField', Value : uom,          Label : 'UoM' },
  ],

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Site Location',
    TypeNamePlural : 'Site Locations',
    Title          : { $Type : 'UI.DataField', Value : code },
    Description    : { $Type : 'UI.DataField', Value : name },
  },
);

annotate service.SiteLocations with {
  code         @title : 'Location';
  name         @title : 'Name';
  locationType @title : 'Type';
  level        @title : 'Level';
  gfa          @title : 'Gross floor area';
  uom          @title : 'UoM';

  parent @Common : {
    Text : parent.code,
    TextArrangement : #TextOnly,
    ValueList : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'SiteLocations',
      Label          : 'Parent location',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : parent_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'locationType' }
      ]
    }
  };
};
