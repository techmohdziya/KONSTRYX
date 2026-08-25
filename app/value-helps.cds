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
