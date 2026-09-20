/**
 * KONSTRYX — Resource Workflow service
 * The RR -> ADV -> AVC -> RES spine across all verticals (MVP: MR).
 * Reservation lines encumber budget on creation.
 */
using { konstryx.wf } from '../db/wf';
using { konstryx.eq } from '../db/eq';
using { konstryx.mpr } from '../db/mpr';
using { konstryx.prj } from '../db/prj';
using { konstryx.sys } from '../db/sys';
using { konstryx.master } from '../db/master';

@requires: 'ResourceCoordinator'
service WorkflowService @(path:'/workflow') {
  // canonical target: RequestOverview below also projects ResourceRequest,
  // so associations must be told which of the two to redirect to
  @cds.redirection.target
  @odata.draft.enabled
  entity ResourceRequests as projection on wf.ResourceRequest
    actions {
      /**
       * Prices any unpriced line from the rate master and hands the request to
       * the approval framework. The request's own status tracks the approval:
       * Draft -> In Approval, and the approval outcome moves it to Approved or
       * Rejected without anyone re-keying it.
       */
      action submit() returns String;

      /**
       * Records the advisory decision for one line: source it in-house,
       * procure it, substitute it, or reject it. Line by line because that is
       * how the decision is actually made — a request for a crane and cabins
       * routinely splits between the fleet and a hire company.
       */
      action decideLine(lineNo : Integer, decision : String(12),
                        rationale : String(500)) returns String;

      /**
       * Availability for the in-house lines. Locally this documents what
       * KONSTRYX itself knows — competing reservations on the same resource.
       * The ERP ATP call slots in behind the same document once a tenant
       * exists (Q-09); the document shape does not change.
       */
      action runAvailabilityCheck() returns String;

      /**
       * Reserves the in-house lines and encumbers each line's approved value.
       * The encumbrance is the line's estTotal — the figure the approval was
       * given — so what is locked is exactly what was signed for.
       */
      action createReservation() returns String;

      /**
       * The other half of the advisory split: raises a purchase requisition
       * from the PROCURE-decided lines, the way createReservation covers the
       * IN_HOUSE ones. Until now a PROCURE line dead-ended at "Advised" and
       * nothing consumed it.
       *
       * The requisition is deliberately not a KONSTRYX document — it draws no
       * number range and gets no docNo, because ERP owns the requisition
       * number. It is created here as NOT_SENT with its account assignment
       * carried from each request line, and takes its prNo when ERP accepts it.
       */
      action raisePurchaseRequisition() returns String;
    };
  /**
   * The drawings, permits and method statements filed against a request.
   *
   * Joined on the key alone rather than on entityName as well. The target is
   * polymorphic - an entity name and a key - and CDS cannot carry a constant
   * into an association's condition, so the name is not part of the join. It
   * costs nothing in practice: objectID is a UUID, and a UUID that collides
   * across two tables has bigger problems than a mislabelled attachment.
   */
  entity RequestAttachments as projection on sys.Attachment;

  entity ResourceRequestLines as projection on wf.ResourceRequestLine;

  // EQR vertical extension — reached from a line via $expand=equipment
  entity EquipmentRequestLines as projection on eq.EquipmentRequestLine;

  // MPR vertical extension — reached from a line via $expand=manpower.
  // Timesheets are exposed in their own right as well as under the line: the
  // daily log is queried by date across a project far more often than it is
  // read one line at a time.
  entity ManpowerRequestLines as projection on mpr.ManpowerRequestLine;
  // Draft-enabled because a day is entered and corrected before anyone signs
  // it. The entry is the foreman's working copy until it is activated; sign
  // then acts on the active day, so a draft can never be counted as cost.
  @odata.draft.enabled
  entity Timesheets           as projection on mpr.TimesheetEntry {
    *,
    // Rendered as the status colour. A signed or posted day is settled, a
    // draft is not yet anything, and a day with hours logged against nobody
    // present is the one state worth flagging red before it is signed.
    case
      when logStatus = 'Posted' or logStatus = 'Signed' then 3
      when headsPresent = 0 and (regularHrs > 0 or otHrs > 0) then 1
      else 0
    end as statusCriticality : Integer
  }
    actions {
      /**
       * Signs off one day's log.
       *
       * Costs the day from the manpower line's all-in head-day rate and moves
       * it Draft -> Signed. Only a signed day is counted against a
       * reservation, and only a signed day may reach ERP.
       *
       * standardDayHours defaults to 8. Overtime is costed at the same all-in
       * hourly rate as regular time, because the model carries one rate per
       * head-day and no premium - an overtime multiplier would be a number
       * invented here rather than agreed commercially.
       */
      action sign(standardDayHours : Decimal(4,2) @title : 'Standard day (hours)') returns String;
    };
  /**
   * What a reservation's value has been moved by, and why.
   *
   * Read-only over the service: a variation is written by the action on the
   * reservation it varies, because the reservation is what holds the money and
   * a variation keyed on its own would move a lock nobody authorised.
   */
  @readonly entity ReservationVariations as projection on wf.ReservationVariation {
    *,
    reservation.docNo         as reservationNo : String(20),
    reservation.project.code  as projectCode   : String(24),
    reservation.rr.verticalType as verticalType : String(20),
    // A variation that gives budget back reads differently from one that asks
    // for more, and the sign is the whole of it.
    case
      when deltaAmount > 0 then 1
      when deltaAmount < 0 then 3
      else 0
    end as deltaCriticality : Integer
  };

  @readonly entity ReservationVariationLines as projection on wf.ReservationVariationLine {
    *,
    variation.docNo as variationNo : String(20),
    case
      when delta > 0 then 1
      when delta < 0 then 3
      else 0
    end as deltaCriticality : Integer
  };

  entity AdvisoryDecisions    as projection on wf.AdvisoryDecision;
  entity AvailabilityChecks   as projection on wf.AvailabilityCheck;

  entity Reservations as projection on wf.Reservation
    actions {
      /** Closes every line and the document; the encumbrance record remains. */
      action close() returns String;

      /**
       * Rolls the signed daily logs into this reservation's lines.
       *
       * Consumption, cost to date, burn and drift were stored numbers that
       * nothing derived, so a reservation could report a burn its own
       * timesheets contradicted. Each is now computed from the signed days
       * behind the line:
       *
       *   consumed   = the head-days signed for
       *   cost       = the cost of those signed days
       *   burn %     = cost against what was encumbered
       *   drift      = cost, less those head-days at the reserved rate
       *
       * Consumption is in head-days rather than hours because the line is
       * quantified in heads and priced per head-day, so head-days is the one
       * unit the quantity, the rate and the money share. Drift is therefore a
       * difference of rate — zero whenever the rate paid equals the rate
       * reserved — and not a measure of progress.
       *
       * Drafts are ignored. A day nobody has signed is not consumption.
       */
      action postConsumption() returns String;

      /**
       * Asks a store for stock this reservation has already locked the money
       * for. One pull request per line per ask: a line drawn in three loads is
       * three documents, because each one is a different movement in ERP and
       * each is confirmed on site separately.
       *
       * Raised here rather than on the pull request itself because the
       * reservation is what authorises it. A pull request keyed on its own
       * would draw stock against a budget nobody encumbered.
       */
      action raisePullRequest(lineNo : Integer,
                              resourceCode : String(40),
                              qty : Decimal(15,3),
                              storageLoc : String(10)) returns String;

      /**
       * Step 8: varies what this reservation has locked.
       *
       * Applied, not proposed. The line's quantity or its rate moves, the lock
       * moves with it, and the before and after are both written down — the
       * reservation line only ever carries the current figure, so a variation
       * that stored only the outcome would leave no way to check it.
       *
       * The one thing it will not do is lock less than the line has already
       * spent. Releasing budget that is already gone would report headroom
       * nobody has; an overrun is a cost to explain, not a lock to reduce.
       *
       * Three figures make the lock and the line stores only two. Its quantity
       * is heads or instances and its rate is per day; the duration is implied
       * by what the approval locked, and it is read back so that moving one
       * figure leaves the other two where they were.
       *
       * Any of the three may be left empty to keep what the line has. All
       * three unchanged is refused: a variation that varies nothing is a
       * document number spent on a narrative.
       *
       * extendByDays says the same thing about duration in the way people
       * actually ask it — "both cranes need thirty more days" — and exists
       * because nobody outside this handler knows what the current duration is
       * to write an absolute one. Giving both is refused: two ways of saying
       * one thing is two things that can disagree.
       */
      action vary(lineNo : Integer,
                  newQty : Decimal(15,3),
                  newRate : Decimal(15,2),
                  newDurationDays : Decimal(9,2),
                  extendByDays : Decimal(9,2),
                  /**
                   * Several lines moved by one decision, in one document.
                   *
                   * The slab cycle slips and both cranes stay thirty more
                   * days. That is one variation with two lines: one reason,
                   * one narrative, one delta against the budget. Moving one
                   * line per document made it two, and while each was
                   * complete and carried its own before and after, a reader
                   * counting variations counted the decision twice and only
                   * the narrative tied the pair together.
                   *
                   * Give this or the flat parameters above, never both — two
                   * ways of saying which lines move are two answers that can
                   * disagree. Every line is checked before any is written, so
                   * a document that cannot be applied in full is not applied
                   * at all.
                   */
                  lines : many {
                    lineNo          : Integer;
                    newQty          : Decimal(15,3);
                    newRate         : Decimal(15,2);
                    newDurationDays : Decimal(9,2);
                    extendByDays    : Decimal(9,2);
                  },
                  reason : String(20),
                  narrative : String(500),
                  effectiveFrom : Date) returns String;
    };
  // Nothing on a reservation line is typed. The quantity and the rate come
  // from the request the approval judged, the lock from its approved value,
  // the consumption from goods issues and signed days, and every later move
  // from a variation -- which exists precisely so the lock cannot be rewritten
  // by hand. Left writable, the whole of that is one PATCH away from being
  // beside the point.
  @readonly
  entity ReservationLines as projection on wf.ReservationLine {
    *,
    // reservedDays comes through with the rest of the line. It is deliberately
    // not derived when it is absent: quantity times rate divided into the lock
    // gives the duration only where the rate is a daily one, and nothing on
    // the line says whether it is. Rebar is priced by the tonne and cement by
    // the bag, and the division answers "one day" for both — a fabricated
    // number in a column a reader would take at face value.
    // Burn is the number a coordinator scans a reservation for, so it carries
    // its own colour. Over the encumbrance is red because the line is spending
    // money nobody locked for it; the band below it is amber because that is
    // when there is still time to do something about it.
    case
      when burnPct > 100 then 1
      when burnPct >= 90 then 2
      when burnPct > 0   then 3
      else 0
    end as burnCriticality : Integer,
    // Drift only ever moves off zero when the rate paid differs from the rate
    // reserved, so any drift at all is worth a colour rather than a threshold.
    // It is cost less the reserved value of the same head-days: above zero the
    // line is paying more than it reserved, below zero it is paying less.
    case
      when drift > 0 then 1
      when drift < 0 then 3
      else 0
    end as driftCriticality : Integer
  };

  /**
   * The reservation overview a coordinator actually needs: per reservation,
   * how far its thread has come along the chain its vertical actually has,
   * what is still anybody's work, and what nothing in this build can finish.
   *
   * The three are reported apart on purpose. The ten-step chain is drawn for
   * plant, so a material reservation is scored against the eight steps that
   * apply to it rather than against two it can never reach; and a step held
   * up by an unwired connector is not a step somebody forgot.
   */
  action reservationOverview() returns array of {
    reservationID  : UUID;
    docNo          : String(20);
    rrID           : UUID;
    rrDocNo        : String(20);
    projectCode    : String(24);
    projectSync    : String(20);
    executionFlow  : String(20);
    status         : String(20);
    lines          : Integer;
    encumbered     : Decimal(15,2);
    consumed       : Decimal(15,2);
    burnPct        : Decimal(5,2);
    verticalType   : String(20);
    chainScope     : String(60);
    stepsDone      : Integer;
    stepsTotal     : Integer;
    stepsBlocked   : Integer;
    pendingSteps   : String(255);
    blockedSteps   : String(255);
    s4Commitment   : String(40);
  };

  /**
   * Exposed here so a request line and a daily log can resolve and offer a
   * value help for what they point at. A Fiori value list must resolve inside
   * the service it is annotated in, and a line that asks a coordinator to read
   * a UUID is not a screen anyone can use - a request line showing
   * "4c000000-0000-..." where the resource belongs reads as a line pointing at
   * nothing in the master, which is exactly how it was reported.
   *
   * Read-only: these are maintained on ProjectService and MasterDataService,
   * and this is a lookup rather than a second place to edit them.
   */
  @readonly entity Resources     as projection on master.ResourceNode;
  @readonly entity WBSElements   as projection on prj.WBSElement;
  @readonly entity ProjectCBS    as projection on prj.CBSInstance;
  @readonly entity ChargeProjects as projection on prj.Project;
  @readonly entity SiteLocations  as projection on prj.SiteLocation;

  /**
   * Output per man-hour, per location.
   *
   * The headline number of site execution, and until locations existed it
   * could be computed for a whole project and for nothing smaller — which is
   * a figure nobody can act on. Installed quantity comes from the bill lines
   * allocated to the location; the hours come from the signed daily logs
   * against it.
   *
   * Draft days are excluded, as everywhere else: a day nobody has signed is a
   * claim, not a fact, and counting it would flatter the rate.
   *
   * Returns rows even where one side is missing, with the reason stated. A
   * location with hours and no measured output is the single most useful row
   * on the screen — it is work being paid for that nothing has yet claimed.
   */
  action productivity(projectID : UUID) returns array of {
    locationID    : UUID;
    locationCode  : String(40);
    locationName  : String(150);
    locationType  : String(20);
    signedDays    : Integer;
    headDays      : Decimal(15,3);
    labourHours   : Decimal(15,2);
    labourCost    : Decimal(15,2);
    installedQty  : Decimal(15,3);
    uom           : String(10);
    outputPerHour : Decimal(15,4);
    costPerUnit   : Decimal(15,2);
    note          : String(120);
  };

  /**
   * Productivity as it was measured, each time it was measured. Written by the
   * productivity action; read-only here, because a measurement is not
   * something anyone edits after the fact.
   */
  @readonly entity ProductivitySnapshots as projection on mpr.ProductivitySnapshot;

  @readonly entity StatusHistory as projection on wf.StatusHistory;
  @readonly entity DocumentLinks as projection on wf.DocumentLink;

  /**
   * Worklist projection: one row per request with its line count and value
   * rolled up. Keeps the client from fetching every line just to render a
   * list, and makes the request value a single server-side number rather
   * than something each consumer re-derives.
   */
  @readonly
  entity RequestOverview as select from wf.ResourceRequest {
    key ID,
        docNo,
        verticalType,
        status,
        raisedBy,
        raisedOn,
        needBy,
        // The project and company associations are exposed, not just their
        // codes, because the authorization catalogue filters this entity by
        // the paths project.code and company.code. A flattened projection that
        // dropped them would resolve to nothing and fail the request at
        // runtime — which is exactly what it did before this line existed.
        project,
        company,
        project.code       as projectCode : String(24),
        project.name       as projectName : String(150),
        count(lines.ID)    as lineCount   : Integer,
        sum(lines.estTotal) as totalValue : Decimal(15,2)
  } group by
      ID, docNo, verticalType, status, raisedBy, raisedOn, needBy,
      project.ID, company.ID, project.code, project.name;
}
