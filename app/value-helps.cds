/**
 * Value helps, readable text for keys, and cross-app links.
 *
 * These live once, on the services, rather than in each app's own
 * annotations.cds. What a manpower line is called and how one is picked are
 * properties of the model, not of the screen looking at it — eleven copies
 * would drift, and the twelfth app would start with none.
 *
 * Two annotations do the work together. Common.Text makes an association
 * display as its code instead of the UUID it stores, and Common.ValueList
 * makes it selectable. Without both, a field is unreadable in a list and
 * unusable in a form: a foreman was being asked to type
 * 51000000-0000-0000-0000-000000000161 to say which crew worked today.
 */
using WorkflowService  from '../srv/workflow-service';
using ProjectService   from '../srv/project-service';
using BudgetService    from '../srv/budget-service';
using MasterDataService from '../srv/masterdata-service';

// ---------------------------------------------------------------- workflow

annotate WorkflowService.ManpowerRequestLines with {
  crewId     @title : 'Crew';
  tradeGrade @title : 'Trade / grade';
  heads      @title : 'Heads';
  ratePerHeadDay @title : 'Rate per head-day';
}

annotate WorkflowService.Timesheets with {
  manpowerLine @Common : {
    Text : manpowerLine.crewId,
    TextArrangement : #TextOnly,
    ValueList : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'ManpowerRequestLines',
      Label          : 'Manpower lines',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : manpowerLine_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'crewId' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'tradeGrade' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'heads' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'ratePerHeadDay' }
      ]
    }
  };

  wbs @Common : {
    Text : wbs.code,
    TextArrangement : #TextOnly,
    ValueList : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'WBSElements',
      Label          : 'WBS elements',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : wbs_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'description' }
      ]
    }
  };

  cbs @Common : {
    Text : cbs.code,
    TextArrangement : #TextOnly,
    ValueList : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'ProjectCBS',
      Label          : 'Cost breakdown',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : cbs_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'level' }
      ]
    }
  };

  location @Common : {
    Text : location.code,
    TextArrangement : #TextOnly,
    ValueList : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'SiteLocations',
      Label          : 'Site locations',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : location_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'locationType' }
      ]
    }
  };
}

annotate WorkflowService.SiteLocations with {
  code         @title : 'Location';
  name         @title : 'Name';
  locationType @title : 'Type';
  level        @title : 'Level';
}

annotate WorkflowService.WBSElements with {
  code        @title : 'WBS element';
  description @title : 'Description';
}

annotate WorkflowService.ProjectCBS with {
  code  @title : 'CBS code';
  level @title : 'Level';
}

annotate WorkflowService.Reservations with {
  docNo @Common : { SemanticObject : 'KonstryxReservation' };
}

annotate WorkflowService.ResourceRequests with {
  docNo @Common : { SemanticObject : 'KonstryxResourceRequest' };
}

// ----------------------------------------------------------------- project

annotate ProjectService.Projects with {
  code @Common : { SemanticObject : 'KonstryxProject' };
}

annotate ProjectService.CBS with {
  code       @title : 'CBS code';
  level      @title : 'Level';
  ownAmount  @title : 'Own budget';
  budgetAmount @title : 'Budget (rolled up)';
  costNature @title : 'Cost nature';
  allocBasis @title : 'Allocation basis';

  parent @Common : {
    Text : parent.code,
    TextArrangement : #TextOnly,
    ValueList : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'CBS',
      Label          : 'Parent node',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : parent_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'level' }
      ]
    }
  };
}

annotate ProjectService.BOQs with {
  boqId @Common : { SemanticObject : 'KonstryxBOQ' };
}

// ------------------------------------------------------------------ budget

annotate BudgetService.Budgets with {
  docNo @Common : { SemanticObject : 'KonstryxBudget' };
}

annotate BudgetService.BudgetLines with {
  amount     @title : 'Budget';
  committed  @title : 'Committed';
  encumbered @title : 'Encumbered';
  actual     @title : 'Actual';
  available  @title : 'Available';
  category   @title : 'Cost nature';
}

// ------------------------------------------------------------- master data

annotate MasterDataService.Resources with {
  code @Common : { SemanticObject : 'KonstryxResource' };
}

annotate MasterDataService.Materials with {
  materialCode @Common : { SemanticObject : 'KonstryxMaterial' };
}

annotate MasterDataService.Vendors with {
  bpNumber @Common : { SemanticObject : 'KonstryxVendor' };
}

// ------------------------------------------------------- rendering hints

/**
 * The criticality fields are instructions to the renderer, not information.
 * They exist so a status can be coloured, and a user offered "statusCriticality"
 * in a column list has been handed a number between 0 and 3 that means nothing
 * to them. Hidden rather than labelled: a good label for these would still be
 * a column nobody should add.
 */
annotate WorkflowService.Timesheets with {
  statusCriticality @UI.Hidden;
}

annotate WorkflowService.ReservationLines with {
  burnCriticality  @UI.Hidden;
  driftCriticality @UI.Hidden;
}

// ------------------------------------------------- what a picker looks like

/**
 * A value help renders the target's own UI.LineItem when it has one, and falls
 * back to the raw ValueList parameters when it does not — which puts the key
 * first and shows a foreman "58000000-0000-0..." as the leading column of the
 * crew picker. These give each picker the columns someone actually chooses by.
 */
annotate WorkflowService.ManpowerRequestLines with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : crewId,         Label : 'Crew' },
    { $Type : 'UI.DataField', Value : tradeGrade,     Label : 'Trade / grade' },
    { $Type : 'UI.DataField', Value : heads,          Label : 'Heads' },
    { $Type : 'UI.DataField', Value : ratePerHeadDay, Label : 'Rate per head-day' },
    { $Type : 'UI.DataField', Value : crewLead,       Label : 'Crew lead' },
  ],
);

annotate WorkflowService.SiteLocations with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,         Label : 'Location' },
    { $Type : 'UI.DataField', Value : name,         Label : 'Name' },
    { $Type : 'UI.DataField', Value : locationType, Label : 'Type' },
    { $Type : 'UI.DataField', Value : level,        Label : 'Level' },
  ],
);

annotate WorkflowService.WBSElements with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,        Label : 'WBS element' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
  ],
);

annotate WorkflowService.ProjectCBS with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,         Label : 'CBS code' },
    { $Type : 'UI.DataField', Value : level,        Label : 'Level' },
    { $Type : 'UI.DataField', Value : budgetAmount, Label : 'Budget' },
  ],
);

/**
 * The picker builds its columns from the ValueList parameters, not from the
 * LineItem above, so the key parameter renders as a column of its own — which
 * is how "58000000-0000-0..." came to lead the crew picker. Hiding the key is
 * what removes it: a UUID is the mechanism by which a row is identified, and
 * never information a person chooses by.
 */
annotate WorkflowService.ManpowerRequestLines with { ID @UI.Hidden };
annotate WorkflowService.SiteLocations       with { ID @UI.Hidden };
annotate WorkflowService.WBSElements         with { ID @UI.Hidden };
annotate WorkflowService.ProjectCBS          with { ID @UI.Hidden };
