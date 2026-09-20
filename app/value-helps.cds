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
using AuthorizationService from '../srv/authorization-service';

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

  wbs @title : 'WBS element' @Common : {
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

  cbs @title : 'CBS node' @Common : {
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

  boqItem @title : 'Bill item' @Common : {
    Text : boqItem.itemNo,
    TextArrangement : #TextOnly,
    ValueList : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'BOQItems',
      Label          : 'Bill items',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : boqItem_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'itemNo' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'description' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'uom' }
      ]
    }
  };
}

/**
 * The pickers behind a budget line's three keys.
 *
 * A bill item picker that leads with the UUID is the same defect as the crew
 * picker below: the column someone chooses by is the item number, and the one
 * they can never choose by is the key.
 */
annotate BudgetService.BOQItems with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : itemNo,      Label : 'Item' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : qty,         Label : 'Quantity' },
    { $Type : 'UI.DataField', Value : uom,         Label : 'UoM' },
    { $Type : 'UI.DataField', Value : amount,      Label : 'Revenue' },
  ],
);

annotate BudgetService.WBSElements with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,        Label : 'WBS' },
    { $Type : 'UI.DataField', Value : description, Label : 'Description' },
    { $Type : 'UI.DataField', Value : activityType, Label : 'Activity type' },
  ],
);

annotate BudgetService.ProjectCBS with @(
  UI.LineItem : [
    { $Type : 'UI.DataField', Value : code,       Label : 'CBS' },
    { $Type : 'UI.DataField', Value : level,      Label : 'Level' },
    { $Type : 'UI.DataField', Value : costNature, Label : 'Cost nature' },
  ],
);

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

// A value help renders the target's own UI.LineItem when it has one, and falls
// back to the raw ValueList parameters when it does not — which puts the key
// first and shows a foreman "58000000-0000-0..." as the leading column of the
// crew picker. These give each picker the columns someone actually chooses by.
//
// A line comment rather than a doc comment: this entity is annotated twice, and
// two doc comments on one target make the compiler keep the last and drop the
// other, which is a warning on every build and an explanation nobody reads.
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

// ------------------------------------------------------------- procurement
//
// The four documents of a purchase reference each other by number, and a
// number on a screen that cannot be opened is a dead end: the reader copies it
// and goes looking for the app it belongs to. The mapping is what makes the
// jump land on the document rather than on an unfiltered list.

// Deliberately NOT on poNo or invoiceNo. A document's own number inside its
// own app is not a link to somewhere else — annotating it turns the column
// that opens the object page into a popover offering nothing, which is worse
// than the plain text it replaced.
annotate MaterialService.PurchaseOrders with {
  projectCode   @Common : { SemanticObject : 'KonstryxProject' };
  requisitionNo @Common : {
    SemanticObject        : 'KonstryxPurchaseRequisition',
    SemanticObjectMapping : [{
      $Type                  : 'Common.SemanticObjectMappingType',
      LocalProperty          : requisitionNo,
      SemanticObjectProperty : 'prNo'
    }]
  };
}

// A stock draw is read from the reservation that authorised it, so the
// reservation number is the jump worth having. Its own docNo is left alone for
// the same reason poNo is.
annotate MaterialService.PullRequests with {
  projectCode   @Common : { SemanticObject : 'KonstryxProject' };
  reservationNo @Common : {
    SemanticObject        : 'KonstryxReservation',
    SemanticObjectMapping : [{
      $Type                  : 'Common.SemanticObjectMappingType',
      LocalProperty          : reservationNo,
      SemanticObjectProperty : 'docNo'
    }]
  };
}

annotate MaterialService.ConsumptionRecords with {
  projectCode   @Common : { SemanticObject : 'KonstryxProject' };
  reservationNo @Common : {
    SemanticObject        : 'KonstryxReservation',
    SemanticObjectMapping : [{
      $Type                  : 'Common.SemanticObjectMappingType',
      LocalProperty          : reservationNo,
      SemanticObjectProperty : 'docNo'
    }]
  };
}

annotate MaterialService.SupplierInvoices with {
  projectCode @Common : { SemanticObject : 'KonstryxProject' };
  orderNo     @Common : {
    SemanticObject        : 'KonstryxPurchaseOrder',
    SemanticObjectMapping : [{
      $Type                  : 'Common.SemanticObjectMappingType',
      LocalProperty          : orderNo,
      SemanticObjectProperty : 'poNo'
    }]
  };
}

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


// ----------------------------------------------------------- authorization

annotate AuthorizationService.AuthObjects with {
  code       @title : 'Authorization object';
  name       @title : 'Object';
  entityName @title : 'Entity';
}

annotate AuthorizationService.Activities with {
  code  @title : 'Activity';
  name  @title : 'Activity';
}

annotate AuthorizationService.Personas with {
  code        @title : 'Persona';
  name        @title : 'Name';
  description @title : 'Description';
  isActive    @title : 'Active';
  isDelivered @title : 'Delivered with the product';
}

// A grant is a sentence: this persona may do this activity to this object.
// Both halves are catalogue entries, so both are picked rather than typed.
annotate AuthorizationService.PersonaPermissions with {
  granted @title : 'Granted';

  authObject @title : 'Object' @Common : {
    Text : authObject.name,
    TextArrangement : #TextOnly,
    ValueList : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'AuthObjects',
      Label          : 'Authorization objects',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : authObject_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'entityName' }
      ]
    }
  };

  activity @title : 'Activity' @Common : {
    Text : activity.name,
    TextArrangement : #TextOnly,
    ValueList : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'Activities',
      Label          : 'Activities',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : activity_code, ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' }
      ]
    }
  };
}

// An assignment is who, as what, and where. Company and project left empty
// mean everywhere, which is why neither is mandatory and both are pickable.
annotate AuthorizationService.UserAssignments with {
  user      @title : 'User';
  validFrom @title : 'Valid from';
  validTo   @title : 'Valid to';
  isActive  @title : 'Active';

  persona @title : 'Persona' @Common : {
    Text : persona.name,
    TextArrangement : #TextOnly,
    ValueList : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'Personas',
      Label          : 'Personas',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : persona_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'isActive' }
      ]
    }
  };
}

// The step already carries the name of who should sign it; this is what makes
// that name a rule rather than a label.
annotate AuthorizationService.ApprovalStepDefs with {
  stepNo        @title : 'Step';
  name          @title : 'Step name';
  minAmount     @title : 'From value';
  maxAmount     @title : 'To value';
  allowChaining @title : 'Same person may sign again';

  approver @title : 'Approver' @Common : {
    Text : approver.name,
    TextArrangement : #TextOnly,
    ValueList : {
      $Type          : 'Common.ValueListType',
      CollectionPath : 'Personas',
      Label          : 'Personas',
      Parameters     : [
        { $Type : 'Common.ValueListParameterInOut',
          LocalDataProperty : approver_ID, ValueListProperty : 'ID' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'code' },
        { $Type : 'Common.ValueListParameterDisplayOnly', ValueListProperty : 'name' }
      ]
    }
  };
}
