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
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'S/4 sync' },
    { $Type : 'UI.DataField', Value : s4Key, Label : 'S/4 project' },
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
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'S/4 sync' },
    { $Type : 'UI.DataField', Value : s4Key, Label : 'S/4 project' },
    ],
  },

  UI.Identification : [
    { $Type  : 'UI.DataFieldForAction',
      Action : 'ProjectService.schedule',
      Label  : 'Run critical path' },
    { $Type  : 'UI.DataFieldForAction',
      Action : 'ProjectService.releaseToS4',
      Label  : 'Release to S/4' },
    { $Type  : 'UI.DataFieldForAction',
      Action : 'ProjectService.measureProductivity',
      Label  : 'Measure productivity' },
  ],

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Details', Label : 'Details',
      Target : '@UI.FieldGroup#Details' },
    { $Type : 'UI.ReferenceFacet', ID : 'WBSElements', Label : 'WBS Elements',
      Target : 'wbsElements/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Bills', Label : 'Bills of Quantities',
      Target : 'boqs/@UI.LineItem#OnProject' },
    { $Type : 'UI.ReferenceFacet', ID : 'CostBreakdown', Label : 'Cost Breakdown',
      Target : 'cbs/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Schedule', Label : 'Schedule',
      Target : 'activities/@UI.LineItem' },
    { $Type : 'UI.ReferenceFacet', ID : 'Locations', Label : 'Site Locations',
      Target : 'locations/@UI.LineItem' },
  ],
);

annotate service.WBS with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code, Label : 'WBS' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : activityType, Label : 'Activity type' },
    { $Type : 'UI.DataField', Value : syncStatus, Label : 'S/4 sync' },
    { $Type : 'UI.DataField', Value : s4Key, Label : 'S/4 element' },
  ],
);

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
  // Own budget beside the rolled-up figure, because a parent that carries real
  // cost of its own reads identically to a heading when only the total shows.
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,         Label : 'CBS' },
    { $Type : 'UI.DataField', Value : level,        Label : 'Level' },
    { $Type : 'UI.DataField', Value : parent_ID,    Label : 'Under' },
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
    Description    : { $Type : 'UI.DataField', Value : level },
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
    { $Type : 'UI.DataField', Value : code,         Label : 'Activity' },
    { $Type : 'UI.DataField', Value : name,         Label : 'Name' },
    { $Type : 'UI.DataField', Value : durationDays, Label : 'Duration (d)' },
    { $Type : 'UI.DataField', Value : earlyStart,   Label : 'Early start' },
    { $Type : 'UI.DataField', Value : earlyFinish,  Label : 'Early finish' },
    { $Type : 'UI.DataField', Value : lateStart,    Label : 'Late start' },
    { $Type : 'UI.DataField', Value : lateFinish,   Label : 'Late finish' },
    { $Type : 'UI.DataField', Value : totalFloat,   Label : 'Total float' },
    { $Type : 'UI.DataField', Value : isCritical,   Label : 'Critical' },
    { $Type : 'UI.DataField', Value : percentDone,  Label : 'Done %' },
  ],
);

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
