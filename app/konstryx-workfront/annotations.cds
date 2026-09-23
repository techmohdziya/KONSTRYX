using ProjectService as service from '../../srv/project-service';

/**
 * Today's work front.
 *
 * Every other insight screen in the product answers a question about a month.
 * This one answers the question a project manager opens a screen to ask at
 * seven in the morning: which fronts are open, who is standing on them, and
 * which of them had nobody yesterday.
 *
 * Sorted by how much attention a row needs rather than by project or by date.
 * A board that opens on PRJ-001's first activity is a list; a board that opens
 * on the overdue fronts and the ones nobody has touched this week is the thing
 * a site meeting runs from.
 */
annotate service.WorkFronts with @(

  UI.HeaderInfo : {
    $Type          : 'UI.HeaderInfoType',
    TypeName       : 'Front',
    TypeNamePlural : 'Work Fronts',
    Title          : { $Type : 'UI.DataField', Value : activityName },
    Description    : { $Type : 'UI.DataField', Value : projectCode },
  },

  UI.SelectionFields : [ projectCode, state, isCritical, wbsCode ],

  UI.PresentationVariant : {
    $Type     : 'UI.PresentationVariantType',
    SortOrder : [
      { $Type : 'Common.SortOrderType', Property : stateCriticality,
        Descending : false },
      { $Type : 'Common.SortOrderType', Property : daysRemaining,
        Descending : false },
    ],
    Visualizations : [ '@UI.LineItem' ],
  },

  UI.LineItem : [
    { $Type : 'UI.DataField', Value : state, Label : 'State',
      Criticality : stateCriticality },
    { $Type : 'UI.DataField', Value : projectCode, Label : 'Project' },
    { $Type : 'UI.DataField', Value : activityName, Label : 'Front' },
    { $Type : 'UI.DataField', Value : wbsCode, Label : 'WBS' },
    { $Type : 'UI.DataField', Value : finishDate, Label : 'Due',
      Criticality : finishCriticality },
    { $Type : 'UI.DataField', Value : daysRemaining, Label : 'Days left',
      Criticality : finishCriticality },
    { $Type : 'UI.DataField', Value : percentDone, Label : 'Done %' },
    { $Type : 'UI.DataField', Value : driftPct, Label : 'Drift %',
      Criticality : driftCriticality },
    { $Type : 'UI.DataField', Value : headsToday, Label : 'Heads today' },
    { $Type : 'UI.DataField', Value : hoursWeek, Label : 'Hours this week' },
    { $Type : 'UI.DataField', Value : locations, Label : 'Where' },
    { $Type : 'UI.DataField', Value : isCritical, Label : 'Critical path' },
  ],

  UI.FieldGroup #Front : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : projectCode, Label : 'Project' },
      { $Type : 'UI.DataField', Value : projectName, Label : 'Name' },
      { $Type : 'UI.DataField', Value : activityCode, Label : 'Activity' },
      { $Type : 'UI.DataField', Value : activityName, Label : 'Front' },
      { $Type : 'UI.DataField', Value : wbsCode, Label : 'WBS element' },
      { $Type : 'UI.DataField', Value : wbsName, Label : 'Description' },
      { $Type : 'UI.DataField', Value : isCritical, Label : 'On the critical path' },
      { $Type : 'UI.DataField', Value : onDate, Label : 'As at' },
    ],
  },

  UI.FieldGroup #Timing : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : startDate, Label : 'Start' },
      { $Type : 'UI.DataField', Value : finishDate, Label : 'Finish',
        Criticality : finishCriticality },
      { $Type : 'UI.DataField', Value : durationDays, Label : 'Duration (days)' },
      { $Type : 'UI.DataField', Value : daysElapsed, Label : 'Days elapsed' },
      { $Type : 'UI.DataField', Value : daysRemaining, Label : 'Days remaining',
        Criticality : finishCriticality },
      { $Type : 'UI.DataField', Value : totalFloat, Label : 'Total float' },
    ],
  },

  /**
   * Done against the straight line through the duration. Not a target and not
   * a forecast — "40% done" means nothing on its own and everything beside
   * "and it should be at 75%".
   */
  UI.FieldGroup #Progress : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : percentDone, Label : 'Reported done %' },
      { $Type : 'UI.DataField', Value : expectedPct, Label : 'Straight line to today %' },
      { $Type : 'UI.DataField', Value : driftPct, Label : 'Drift %',
        Criticality : driftCriticality },
      { $Type : 'UI.DataField', Value : state, Label : 'State',
        Criticality : stateCriticality },
    ],
  },

  /**
   * The crew, from the signed daily logs. Drafts do not count: an unsigned day
   * is a foreman's note to himself, and a board that counted it would put a
   * gang on a front on the strength of a number nobody has stood behind.
   */
  UI.FieldGroup #Crew : {
    $Type : 'UI.FieldGroupType',
    Data  : [
      { $Type : 'UI.DataField', Value : headsToday, Label : 'Heads today' },
      { $Type : 'UI.DataField', Value : hoursToday, Label : 'Man-hours today' },
      { $Type : 'UI.DataField', Value : headsWeek, Label : 'Head-days this week' },
      { $Type : 'UI.DataField', Value : hoursWeek, Label : 'Man-hours this week' },
      { $Type : 'UI.DataField', Value : lastWorkedOn, Label : 'Last signed day' },
      { $Type : 'UI.DataField', Value : daysSinceWorked, Label : 'Days since' },
      { $Type : 'UI.DataField', Value : locations, Label : 'Where they worked' },
      { $Type : 'UI.DataField', Value : note, Label : 'What this row cannot say' },
    ],
  },

  UI.Facets : [
    { $Type : 'UI.ReferenceFacet', ID : 'Front', Label : 'Front',
      Target : '@UI.FieldGroup#Front' },
    { $Type : 'UI.ReferenceFacet', ID : 'Timing', Label : 'Timing',
      Target : '@UI.FieldGroup#Timing' },
    { $Type : 'UI.ReferenceFacet', ID : 'Progress', Label : 'Progress',
      Target : '@UI.FieldGroup#Progress' },
    { $Type : 'UI.ReferenceFacet', ID : 'Crew', Label : 'Crew',
      Target : '@UI.FieldGroup#Crew' },
  ],
);

annotate service.WorkFronts with {
  projectCode     @title : 'Project';
  projectName     @title : 'Project name';
  activityCode    @title : 'Activity';
  activityName    @title : 'Front';
  wbsCode         @title : 'WBS';
  wbsName         @title : 'WBS description';
  isCritical      @title : 'On the critical path';
  onDate          @title : 'As at';
  startDate       @title : 'Start';
  finishDate      @title : 'Finish';
  durationDays    @title : 'Duration (days)';
  daysElapsed     @title : 'Days elapsed';
  daysRemaining   @title : 'Days remaining';
  totalFloat      @title : 'Total float';
  percentDone     @title : 'Reported done %';
  expectedPct     @title : 'Straight line to today %';
  driftPct        @title : 'Drift %';
  headsToday      @title : 'Heads today';
  hoursToday      @title : 'Man-hours today';
  headsWeek       @title : 'Head-days this week';
  hoursWeek       @title : 'Man-hours this week';
  lastWorkedOn    @title : 'Last signed day';
  daysSinceWorked @title : 'Days since anyone worked here';
  locations       @title : 'Where';
  state           @title : 'State';
  note            @title : 'What this row cannot say';

  /**
   * Instructions to the renderer, not information. A reader offered
   * "stateCriticality" in a column list has been handed a number between 0 and
   * 3 that means nothing to them.
   */
  stateCriticality  @UI.Hidden;
  driftCriticality  @UI.Hidden;
  finishCriticality @UI.Hidden;
  refreshedAt       @UI.Hidden;

  project @Common : {
    Text            : projectCode,
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
};

/** The project as a person names it, not as the service keys it. */
annotate service.WorkFronts with {
  projectCode @title : 'Project';
  projectName @title : 'Project name';
}
