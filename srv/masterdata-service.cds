/**
 * KONSTRYX — Master Data service
 * Resource hierarchy, CBS library, rates, productivity/consumption norms,
 * templates, vendor & material mirrors. Stewarded master data.
 */
using { konstryx.master } from '../db/master';
using from '../db/wfm';
using { konstryx.admin } from '../db/admin';

@requires: 'MasterDataSteward'
service MasterDataService @(path:'/masterdata') {

  /**
   * Hybrid scoped masters. A COMPANY-scoped record belongs to one legal entity
   * and is invisible to the others; a GROUP-scoped record is shared across the
   * group. Local records are promoted to group scope through the steward
   * queue rather than by editing the scope directly — promotion is a decision
   * with an owner and an audit trail, not a field update.
   *
   * The RBS is five levels deep and was served flat, so a catalogue of 77 nodes
   * read as 77 unrelated rows and the level column was the only clue that any
   * of them belonged to another. The transient elements are filled per request
   * by hierarchy expansion — depth, drill state, how many descendants a search
   * matched — and are never stored.
   */
  @odata.draft.enabled
  entity Resources         as projection on master.ResourceNode {
    *,
    null as DistanceFromRoot       : Int64   @UI.Hidden,
    null as DrillState             : String  @UI.Hidden,
    null as LimitedDescendantCount : Int64   @UI.Hidden,
    null as Matched                : Boolean @UI.Hidden,
    null as MatchedDescendantCount : Int64   @UI.Hidden,
  }
    actions {
      action requestPromotion(reason : String(500) @title : 'Why this belongs to the group') returns String;
    };

  /**
   * The CBS library, read as a tree. Three levels that broke nothing down when
   * served flat: the phases, what sits under them, and the leaves a norm is
   * keyed to.
   */
  @odata.draft.enabled
  entity CBSLibrary        as projection on master.CBSNode {
    *,
    null as DistanceFromRoot       : Int64   @UI.Hidden,
    null as DrillState             : String  @UI.Hidden,
    null as LimitedDescendantCount : Int64   @UI.Hidden,
    null as Matched                : Boolean @UI.Hidden,
    null as MatchedDescendantCount : Int64   @UI.Hidden,
  }
    actions {
      action requestPromotion(reason : String(500) @title : 'Why this belongs to the group') returns String;
    };

  /**
   * A template is a construction type plus the CBS structure and default
   * resources that go with it. Instantiating copies that structure into a
   * project rather than referencing it, so a later change to the library does
   * not silently reshape a project already being costed.
   */
  @odata.draft.enabled
  entity ProjectTemplates  as projection on master.ProjectTemplate
    actions {
      action instantiate(projectCode : String(24)) returns String;
    };

  entity TemplateResources as projection on master.ProjectTemplateResource;

  /**
   * Rates and norms are draft-enabled for the same reason the masters are: a
   * rate is entered against a resource, a basis, a currency and a date, and a
   * half-entered one must not be visible to anyone costing a project.
   */
  @odata.draft.enabled
  entity ProductivityRates as projection on master.ProductivityRate;

  @odata.draft.enabled
  entity ConsumptionRates  as projection on master.ConsumptionRate;

  @odata.draft.enabled
  entity Rates as projection on master.RateMaster;

  /**
   * Which rate actually applies on a given day.
   *
   * Effective dating is only worth having if something resolves it. A resource
   * accumulates rate revisions over years, and every consumer - a budget, a
   * reservation, a variation - needs the one in force on its own date, not the
   * newest row. Answering that in one place stops each module inventing its own
   * interpretation of "current".
   */
  function rateOn(resourceCode : String(40), onDate : Date, companyCode : String(10))
    returns {
      resourceCode  : String(40);
      rateValue     : Decimal(15,2);
      netRate       : Decimal(15,2);
      basis         : String(10);
      currency      : String(3);
      effectiveFrom : Date;
      scope         : String(10);
      source        : String(120);
    };

  // S/4 mirrors — read-only in Konstryx
  @readonly entity Vendors    as projection on master.Vendor;
  @readonly entity Materials  as projection on master.Material;
  @readonly entity Customers  as projection on master.Customer;

  // ----------------------------------------------------------------- workforce

  /**
   * The working day and its overtime ladder.
   *
   * Every place that used to carry a multiplier of its own now reads the rungs
   * under a pattern instead, so a commercial agreement is changed once.
   */
  @odata.draft.enabled
  entity ShiftPatterns     as projection on master.ShiftPattern;
  entity OvertimeSteps     as projection on master.OvertimeStep;

  @odata.draft.enabled
  entity HolidayCalendars  as projection on master.HolidayCalendar;
  entity HolidayEntries    as projection on master.HolidayCalendarEntry;

  @odata.draft.enabled
  entity Trades            as projection on master.TradeCatalogue;
  entity TradeGrades       as projection on master.TradeGrade;
  entity TradeCertificates as projection on master.TradeCertificate;

  /**
   * The own-payroll workers.
   *
   * Outbound rather than mirrored: without a work agreement in the ERP no
   * timesheet can post, and nothing upstream will create one for us.
   */
  @odata.draft.enabled
  entity Workers           as projection on master.Employee
    actions {
      /** Pushes the work agreement so time can post against this man. */
      action releaseToErp() returns String;
    };
  entity WorkerDocuments   as projection on master.EmployeeDocument;

  /**
   * The workers whose agreement has not reached the ERP, with the reason.
   *
   * A man in this list can be paid but cannot have time posted, so it is read
   * before a mobilisation rather than after a payroll run.
   */
  @readonly
  @cds.redirection.target : false
  entity WorkerPushQueue   as projection on master.Employee {
    key ID           as workerId,
        empNo,
        fullName,
        trade.description as trade,
        owningCompany.code as company,
        syncStatus,
        syncMessage,
        syncAttempts,
        lastSyncedAt
  } where syncStatus <> 'SENT';

  @odata.draft.enabled
  entity CrewTemplates     as projection on master.CrewTemplate;
  entity CrewTemplateSlots as projection on master.CrewTemplateSlot;

  @odata.draft.enabled
  entity Gangs             as projection on master.Gang;
  entity GangSlots         as projection on master.GangSlot;

  @odata.draft.enabled
  entity AbsenceReasons    as projection on master.AbsenceReason;

  /**
   * Who cannot be planned, and why. Availability only — no balance, no accrual
   * and no approval, because payroll is not in KONSTRYX.
   */
  @odata.draft.enabled
  entity Absences          as projection on master.Absence;

  @odata.draft.enabled
  entity SubcontractWorkers as projection on master.SubcontractWorker;
  entity SubcontractWorkerDocuments as projection on master.SubcontractWorkerDocument;

  /**
   * A spell on site against one purchase order item. Overlapping spells for one
   * man are refused: the same day cannot be billed by two suppliers.
   */
  @odata.draft.enabled
  entity SubcontractEngagements as projection on master.SubcontractEngagement;

  @odata.draft.enabled
  entity RosterUploads     as projection on master.RosterUpload
    actions {
      /** Judges every row without writing any worker. */
      action preview() returns String;
      /** Creates the men the preview accepted, and only those. */
      action commitRoster() returns String;
    };
  entity RosterUploadRows  as projection on master.RosterUploadRow;

  /**
   * The steward queue. Approving promotes the referenced master to GROUP scope
   * and clears its owning company; the request is kept as the record of who
   * decided and why.
   *
   * It sits on this service rather than AdminService because the judgement —
   * should this master be shared across every company — belongs to the master
   * data steward, not to a platform administrator.
   */
  @cds.redirection.target
  entity PromotionRequests as projection on admin.PromotionRequest
    actions {
      action approve(comment : String(500) @title : 'Comment') returns String;
      action reject(comment : String(500) @title : 'Reason for rejecting')  returns String;
    };
}
