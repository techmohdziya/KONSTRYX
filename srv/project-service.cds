/**
 * KONSTRYX — Project & BOQ service
 * Project/WBS mirrors, BOQ import & items, project CBS, allocations (Cost
 * Mapping Workbench), planned resources.
 */
using { konstryx.prj } from '../db/prj';
using { konstryx.master } from '../db/master';
using { konstryx.ins } from '../db/ins';
using { konstryx.vo } from '../db/vo';
using { konstryx.admin } from '../db/admin';

/** One target of a WBS distribution: the element and its weight share. */
type WBSTarget {
  wbsCode : String(24);
  weight  : Decimal(9,4);
}

@requires: 'ProjectManager'
service ProjectService @(path:'/project') {
  /**
   * Mastered here (D-17), so writable — a project is created in KONSTRYX and
   * pushed to S/4, or imported from Primavera. Draft-enabled because a project
   * header is filled in over several sittings and a half-typed one must not be
   * visible to anyone else.
   */
  @odata.draft.enabled
  entity Projects as projection on prj.Project
    actions {
      /**
       * Sends the project to S/4.
       *
       * It queues first and pushes immediately: syncStatus becomes PENDING,
       * and the connector then runs against that queued row. Both steps matter
       * — PENDING is what the gate writes, and the push refuses anything that
       * is not PENDING, so a project can never reach S/4 without having passed
       * the release checks.
       *
       * Where no S/4 connection is configured it stops at PENDING and says so,
       * which is what it always did. A push that S/4 refuses records FAILED
       * with the reason rather than leaving the project looking queued.
       */
      action releaseToS4() returns String;

      /**
       * Measures output per man-hour on every location of this project, and
       * keeps the measurement.
       *
       * Bound to the project because that is where someone stands when they
       * ask the question, and because productivity is only meaningful within
       * one project - a rate that averaged two towers would describe neither.
       * The measurement is stored rather than only returned, so a rate can be
       * compared with the same rate a month ago.
       */
      action measureProductivity() returns String;

      /**
       * Reconciles the project for a period: what it is worth, what it has
       * cost, and what it will cost.
       *
       * Earned value is measured work at contract rates; actual cost is what
       * that work cost; cost to complete is priced at the rate work has
       * actually cost rather than the rate it was budgeted at, because the
       * difference between those two is the finding rather than a rounding.
       *
       * Planned value is deliberately not computed. Nothing time-phases the
       * budget across the programme - a budget line knows its amount and its
       * CBS and not which month it was meant to be spent in - so the schedule
       * index would be an index of a guess. It comes back null with the reason
       * on the row.
       *
       * onDate picks the period; today's if omitted.
       */
      action reconcile(onDate : Date) returns String;

      /**
       * Runs the critical path over this project's activities and writes back
       * early and late dates, total and free float, and which activities are
       * critical. Safe to repeat: every derived field is recalculated from the
       * network each time rather than adjusted.
       */
      action schedule() returns String;

      /**
       * Copies the CBS library into this project. A project costs against its
       * own copy, not the library, so that a later library change cannot
       * silently reshape a project already being costed — the same rule the
       * templates follow.
       */
      action instantiateCBS() returns String;
      /**
       * Brings this project's WBS tree back in line with a Primavera P6
       * export.
       *
       * Not the same as importP6, which creates a project. This one already
       * has a project, a budget hanging off its cost nodes and allocations
       * hanging off its elements, and the planner has since added three
       * branches and renamed two. Re-importing would produce a second project;
       * matching by code and reconciling produces the same one, moved on.
       *
       * Elements here that the export no longer carries are left in place and
       * counted. A planner filtering a layout is not an instruction to delete
       * a branch that has money and signed work against it — that decision is
       * a person's, and the message says which branches need it.
       *
       * The export has to name this project, either by its own code or by the
       * P6 code somebody has already linked it to. Taking the only project in
       * a file because it is the only one there would graft a stranger's tree
       * onto a live job, and nothing on the screen would say so.
       *
       * The programme itself is not touched. Activities and their links carry
       * progress, actual dates and a critical path computed here, and a WBS
       * sync that quietly replaced them would discard the site's own record of
       * what happened.
       */
      action syncWBSFromP6(
        fileName     : String(255)  @title : 'File name',
        content      : LargeString  @title : 'P6 export',
        p6ProjectId  : String(60)   @title : 'Project in the file',
        validateOnly : Boolean      @title : 'Check only, change nothing'
      ) returns String;

      /**
       * The gate (KX-GOV-002). Nothing generates budget lines until every rule
       * passes. Returns each rule with its counts, so the screen shows what is
       * failing rather than a mute disabled button.
       */
      action validateForBudget() returns array of {
        ruleId       : String(10);
        description  : String(120);
        linesChecked : Integer;
        failing      : Integer;
        result       : String(4);
      };

      /**
       * The Cost Mapping workbench's data: step-tile counts and ONLY the rows
       * that need a human. The canonical bill maps 1,127 of 1,142 lines
       * automatically and those are never rendered (wireframe: "the user only
       * resolves exceptions").
       */
      action costMappingSummary() returns {
        totalLines  : Integer;
        cbsMapped   : Integer;  cbsOpen  : Integer;
        wbsDone     : Integer;  wbsOpen  : Integer;
        resResolved : Integer;  resOpen  : Integer;
        gatePassing : Integer;  gateFailing : Integer;
        exceptions  : array of {
          boqItemId      : UUID;
          boqId          : UUID;
          itemNo         : String(20);
          reason         : String(30);
          detail         : String(255);
          suggestedCbs   : String(40);
          suggestedCbsId : UUID;
        };
      };

      /**
       * Pushes a queued (PENDING) project to ERP through SAP_COM_0308 and
       * records the outcome — the live counterpart of recordSyncResult. On an
       * unconfigured system it refuses rather than pretending.
       */
      action syncToS4() returns String;

      /** Records the outcome of a sync attempt. Called by the connector. */
      action recordSyncResult(success : Boolean, s4Key : String(60),
                              s4System : String(20), message : String(1000)) returns String;
    };
  /**
   * Read as a tree, not a list.
   *
   * Maintained through the project draft — a WBS element only means something
   * inside the project that owns it. Mastered here (D-17), so writable.
   *
   * A WBS is a hierarchy in every system that has one, and it was being served
   * flat: level 3 sat beside level 1 in alphabetical order and nothing on the
   * row said which was under which. The five transient elements below are what
   * OData V4 hierarchy expansion fills in per request — how deep a node sits,
   * whether it can be expanded, how many descendants a filter matched — and
   * the annotations after the service name which element carries which.
   *
   * They are `null as` rather than stored: they are answers about one query's
   * result set, and persisting them would make them wrong the moment anything
   * moved.
   */
  entity WBS as projection on prj.WBSElement {
    *,
    null as DistanceFromRoot       : Int64   @UI.Hidden,
    null as DrillState             : String  @UI.Hidden,
    null as LimitedDescendantCount : Int64   @UI.Hidden,
    null as Matched                : Boolean @UI.Hidden,
    null as MatchedDescendantCount : Int64   @UI.Hidden,
  };

  /**
   * Imports a project and its WBS tree from a Primavera P6 XML export.
   *
   * Deliberately has no PARTIAL mode. A P6 file is one project with a tree
   * hanging off it, and a project that imported its header and two thirds of
   * its WBS is worse than one that did not import at all — the missing branches
   * are invisible until someone tries to budget against them.
   */
  action importP6(
    fileName     : String(255),
    content      : LargeString,
    companyID    : UUID,
    validateOnly : Boolean
  ) returns String;

  // Sync state belongs to the connector. Marked read-only here so the write is
  // refused when it is made, rather than at activation: a user who typed into
  // the field and found out only when they pressed Save would have to unpick a
  // draft to get out of it.
  annotate Projects with {
    p6ProjectId    @readonly;
    p6File         @readonly;
    p6LastSyncedAt @readonly;
    p6SyncMessage  @readonly;
    syncStatus   @readonly;
    s4Key        @readonly;
    s4System     @readonly;
    lastSyncedAt @readonly;
    syncMessage  @readonly;
    syncAttempts @readonly;
  };
  annotate WBS with {
    syncStatus   @readonly;
    s4Key        @readonly;
    s4System     @readonly;
    lastSyncedAt @readonly;
    syncMessage  @readonly;
    syncAttempts @readonly;
  };

  /**
   * The master entities a project row points at, read-only. Without them CAP
   * drops the associations from the projections entirely — a project CBS node
   * could not say which library node it came from, and a planned resource
   * could not name its resource, which makes both unusable in a UI.
   * Maintenance stays in MasterDataService; these are for resolution only.
   */
  @readonly entity ResourceCatalog as projection on master.ResourceNode;
  @readonly entity CBSLibrary      as projection on master.CBSNode;

  @odata.draft.enabled
  entity BOQs as projection on prj.BOQ
    actions {
      /**
       * Loads priced items from a CSV. A bill arrives as a spreadsheet from the
       * QS in every case, so this is the normal way a BOQ enters the system,
       * not an exception path.
       *
       * All-or-nothing: a bill that loaded 400 of its 600 lines still adds up
       * to a contract value, and it is the wrong one.
       */
      action importItems(fileName : String(255), content : LargeString,
                         validateOnly : Boolean) returns String;

      /** Recomputes the header value from the priced lines. */
      action recalculate() returns String;

      /**
       * Costs every line from its own resource build-up, and works out the
       * margin.
       *
       * A bill line carried what it sells for and not what it costs, so no
       * screen could show a line that prices well and builds badly - which is
       * the line a commercial manager most needs to find. Cost comes from the
       * build-up rather than a typed figure, so it cannot disagree with the
       * resources behind it.
       */
      action recalculateCost() returns String;

      /**
       * Distributes bill quantities across WBS by template — the three
       * decisions that cover 1,100 of the canonical 1,142 lines. TPL-SINGLE
       * puts a line whole onto one element; TPL-FLOORS and TPL-ZONES split it
       * across several by weight (GFA shares, zone shares). Re-running a
       * distribution REPLACES the targeted lines' allocations: the last
       * decision wins, visibly, rather than stacking into over-allocation.
       */
      action distributeToWBS(
        template : String(20),
        targets  : array of WBSTarget,
        itemNos  : array of String(20)
      ) returns String;

      /**
       * Resolves every mapped line's build-up from the CBS recipes: the norms
       * keyed to the line's CBS leaf, company override beating the group
       * default. Difficulty applies on top of the productivity norms,
       * most-specific-wins; the master norm itself is never adjusted
       * (KX-BUD-014). Returns the coverage the wireframe reports: recipe-found,
       * no-recipe, unmapped, rate-missing. MANUAL rows survive a regeneration —
       * they are someone's judgement, flagged, not overwritten.
       */
      action generateBuildUp(difficultyPct : Decimal(5,2)) returns String;
    };

  /**
   * Variation orders: what changed after the contract was signed.
   *
   * Draft-enabled because a variation is priced line by line before anyone
   * submits it, and a half-priced claim must not be visible to the
   * reconciliation — which reads approved variations and would otherwise pick
   * up a number still being argued internally.
   */
  @odata.draft.enabled
  entity Variations as projection on vo.VariationOrder {
    *,
    /**
     * The colours, computed here so no two screens disagree about what counts
     * as a variation worth looking at.
     *
     * A negative margin is red whatever the revenue: a change the client is
     * paying for and the contractor is losing on is the one to find. Status
     * follows the decision - approved is settled, rejected is a loss to absorb,
     * submitted is still an argument.
     */
    case
      when marginPct is null then 0
      when marginPct <  0    then 1
      when marginPct <  5    then 2
      else                        3
    end as marginCriticality : Integer,
    case
      when status = 'Approved'  then 3
      when status = 'Rejected'  then 1
      when status = 'Submitted' then 2
      else                           0
    end as statusCriticality : Integer,
  }
    actions {
      /**
       * Recomputes revenue, cost and margin from the lines.
       *
       * The header holds all three so a list reads without expanding every
       * variation, and holding them means they can drift — so they are derived
       * rather than typed, the same rule the payment certificate follows.
       */
      action recalculate() returns Variations;

      /** Sends the priced claim to the client. Refuses an unpriced one. */
      action submit() returns String;

      /**
       * The client's answer.
       *
       * Approving is what makes a variation count: only approved ones reach
       * the cost value reconciliation, because a submitted claim is a
       * negotiating position and a forecast built on one depends on a
       * conversation nobody has had yet.
       */
      action approve(
        clientRef         : String(40)  @title : 'Client reference',
        decisionNote      : String(500) @title : 'Decision note',
        timeExtensionDays : Integer     @title : 'Time extension (days)'
      ) returns String;
      action reject(reason : String(500) @title : 'Reason for rejecting') returns String;
    };

  entity VariationLines as projection on vo.VariationLine;

  entity BOQItems as projection on prj.BOQItem
    actions {
      /**
       * Allocates part of this item's quantity to a WBS element and a CBS node.
       * This is the join between what was sold and where the cost lands.
       */
      action allocate(wbsCode : String(24), cbsCode : String(40),
                      qty : Decimal(15,3)) returns String;
    };

  entity BOQItemResources as projection on prj.BOQItemResource;
  /**
   * The companies a project can belong to, read-only.
   *
   * Here rather than only on AdminService because every project must name one,
   * and a project manager who cannot read the list cannot create a project.
   * AdminService is where they are maintained; this is where they are chosen
   * from.
   */
  @readonly entity Companies as projection on admin.Company;

  /**
   * Schedulable tasks under a WBS element, and what links them.
   *
   * Draft-enabled so the network can be maintained. An activity's predecessors
   * are a composition, which means they are only editable inside the
   * activity's own draft — without one, a planner could read that A waits on B
   * and had no way to say so, and the critical path could only ever run over
   * links that arrived with a P6 import.
   */
  @odata.draft.enabled
  entity Activities         as projection on prj.Activity;

  /**
   * Exposed for resolution only. A dependency is created and deleted inside
   * its successor's draft; this entity set is what lets a relation name the
   * activity it points at.
   */
  entity ActivityRelations  as projection on prj.ActivityRelation;

  entity CBS              as projection on prj.CBSInstance {
    *,
    null as DistanceFromRoot       : Int64   @UI.Hidden,
    null as DrillState             : String  @UI.Hidden,
    null as LimitedDescendantCount : Int64   @UI.Hidden,
    null as Matched                : Boolean @UI.Hidden,
    null as MatchedDescendantCount : Int64   @UI.Hidden,
  }
    actions {
      /**
       * Recomputes every CBS node's budget on this project from the budget
       * lines beneath it, then rolls the tree upward so a parent equals the
       * sum of its own lines and its children.
       *
       * budgetAmount was a stored number that nothing recomputed, so a node
       * could report a figure its own lines contradicted and neither was
       * obviously wrong. Bound to any node on the project; it recomputes the
       * whole tree, because rolling up one branch of a hierarchy is how the
       * parent and its siblings end up disagreeing.
       */
      action rollUpBudget() returns String;
    };
  /**
   * One project on one page.
   *
   * Recomputed before every read rather than written by an action, so the
   * summary can never disagree with the screens a reader opens to check it.
   * Read-only for the same reason a measurement is: there is nothing here to
   * edit, only things to go and change.
   */
  @readonly entity ProjectOverviews as projection on ins.ProjectOverview {
    *,
    /**
     * The colours, computed once on the service rather than per screen.
     *
     * A margin is red because it is negative and amber because it is thin
     * enough that one bad month takes it. Budget use is red past its own
     * total, amber as it approaches. A slip is red when the programme lands
     * after the contract date. Repeating any of these thresholds in an
     * annotation is how two screens come to disagree about which projects
     * need attention.
     */
    case
      when forecastMarginPct is null then 0
      when forecastMarginPct <  0    then 1
      when forecastMarginPct <  5    then 2
      else                                3
    end as marginCriticality : Integer,
    case
      when cpi is null then 0
      when cpi <  0.95 then 1
      when cpi <  1.00 then 2
      when cpi <= 1.15 then 3
      else                  0
    end as cpiCriticality : Integer,
    case
      when budgetUsedPct is null then 0
      when budgetUsedPct > 100   then 1
      when budgetUsedPct >  90   then 2
      else                            3
    end as budgetCriticality : Integer,
    case
      when slipDays is null then 0
      when slipDays >  0    then 1
      when slipDays =  0    then 2
      else                       3
    end as slipCriticality : Integer,
  };

  /**
   * The spend curve: what each period is expected to cost, and what it has.
   * Recomputed on read, from the phased budget and the signed cost.
   */
  @readonly entity Cashflow as projection on ins.ProjectCashflow;

  /**
   * Today's work front: the activities the job is standing on right now, who
   * is on them and which of them nobody has touched this week.
   *
   * Recomputed before every read, like the overview and for a stronger reason:
   * a stored row that says "today" is wrong by tomorrow morning and nothing on
   * the screen would say so.
   */
  @readonly entity WorkFronts as projection on ins.WorkFront {
    *,
    /**
     * The colours, computed here rather than in each screen's annotations.
     *
     * A front is red when it is overdue or when nobody has signed a day
     * against it this week, amber when it is behind its own straight line by
     * more than a tenth, green otherwise. Drift is coloured on the same
     * thresholds so the two columns cannot contradict each other.
     */
    case
      when driftPct is null   then 0
      when driftPct < -10.00  then 1
      when driftPct <   0.00  then 2
      else                         3
    end as driftCriticality : Integer,
    case
      when daysRemaining is null then 0
      when daysRemaining <  0    then 1
      when daysRemaining <= 3    then 2
      else                            3
    end as finishCriticality : Integer,
  };

  /**
   * Cost Value Reconciliation and Earned Value, as measured each period.
   *
   * Read-only: a measurement is not something anyone edits after the fact. It
   * is written by reconcile on the project, and kept, so a margin can be
   * compared with the same margin three months ago rather than only stated.
   */
  @readonly entity PeriodReports as projection on ins.ProjectPeriodReport {
    *,
    /**
     * Colour for the margin and for the cost index, computed here rather than
     * on the screen.
     *
     * A margin is not red because it is small; it is red because it is
     * negative, and amber because it is thin enough that one bad month takes
     * it. Putting the thresholds in the projection keeps every screen that
     * shows this figure agreeing about which of them is which - a rule
     * repeated in an annotation is a rule that drifts.
     */
    case
      when forecastMarginPct is null           then 0
      when forecastMarginPct <  0              then 1
      when forecastMarginPct <  5              then 2
      else                                          3
    end as marginCriticality : Integer,
    /**
     * Above 1 is earning more than it spends, which is good and, on a
     * construction job, usually means cost is only partly captured. Neutral
     * rather than green above 1.15 for that reason: the note on the row says
     * which cost categories are behind the number, and a green tick would
     * invite a reader to skip it.
     */
    case
      when cpi is null      then 0
      when cpi <  0.95      then 1
      when cpi <  1.00      then 2
      when cpi <= 1.15      then 3
      else                       0
    end as cpiCriticality : Integer,
  };

  /**
   * The same measurements, read across the portfolio rather than down one
   * project: the financial booklet.
   *
   * Its own projection rather than a second set of annotations on
   * PeriodReports, because two apps annotating one entity overwrite each
   * other's columns and the one a reader got would depend on which app
   * happened to load last. The reconciliation and the booklet ask different
   * questions of the same rows and are entitled to different screens.
   */
  @readonly entity Booklet as projection on ins.ProjectPeriodReport {
    *,
    case
      when forecastMarginPct is null then 0
      when forecastMarginPct <  0    then 1
      when forecastMarginPct <  5    then 2
      else                                3
    end as marginCriticality : Integer,
    case
      when cpi is null then 0
      when cpi <  0.95 then 1
      when cpi <  1.00 then 2
      when cpi <= 1.15 then 3
      else                  0
    end as cpiCriticality : Integer,
  };

  /**
   * The site's own geography — building, floor, zone, grid. Maintained with
   * the project because that is what owns it.
   */

  entity SiteLocations    as projection on prj.SiteLocation;

  /**
   * Where a bill line's quantity was sent — the join between what was sold,
   * what gets built and what absorbs the cost. Read from the project rather
   * than only from the bill: a QS asks "how is this project mapped", not "how
   * is bill 3 line 41 mapped".
   */
  entity Allocations      as projection on prj.Allocation;
  entity ProjectResources as projection on prj.ProjectResource;

  /**
   * The same workbench read across every project the user may see — the
   * portfolio counterpart of costMappingSummary, which answers for one project.
   * Counts only, no exception rows: this list says which projects need a human,
   * and the per-project workbench handles the one that does.
   */
  action costMappingPortfolio() returns array of {
    projectId      : UUID;
    projectCode    : String(40);
    projectName    : String(150);
    stage          : String(40);
    totalLines     : Integer;
    cbsOpen        : Integer;
    wbsOpen        : Integer;
    resOpen        : Integer;
    gatePassing    : Integer;
    gateFailing    : Integer;
    exceptionCount : Integer;
    budgetReady    : Boolean;
  };

  /**
   * Creates a project and its WBS elements together, in one call.
   *
   * Together rather than separately, deliberately. A project with no WBS
   * element cannot be released — there is nothing for S/4 to post against —
   * and a create that stops at the header leaves exactly that: a project that
   * looks finished and can never leave. The seeded PRJ-002 is the standing
   * example, and it is still stuck.
   *
   * The company is named by its code rather than its key, because a person
   * typing a new project knows INFC and does not know a UUID.
   *
   * Everything is written through this service, so a project typed here gets
   * the same validation as one imported from P6 or seeded from a content pack
   * — including NOT_SENT. Creating a project never puts it in S/4; releasing
   * it does.
   */
  action createProject(
    code          : String(40),
    name          : String(150),
    companyCode   : String(10),
    startDate     : Date,
    endDate       : Date,
    contractValue : Decimal(15,2),
    wbs           : array of {
      code        : String(40);
      description : String(150);
    }
  ) returns String;
}
