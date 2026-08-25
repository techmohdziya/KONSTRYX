/**
 * KONSTRYX — Resource Workflow service
 * The RR -> ADV -> AVC -> RES spine across all verticals (MVP: MR).
 * Reservation lines encumber budget on creation.
 */
using { konstryx.wf } from '../db/wf';
using { konstryx.eq } from '../db/eq';
using { konstryx.mpr } from '../db/mpr';
using { konstryx.prj } from '../db/prj';

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
       * The S/4 ATP call slots in behind the same document once a tenant
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
       * number range and gets no docNo, because S/4 owns the requisition
       * number. It is created here as NOT_SENT with its account assignment
       * carried from each request line, and takes its prNo when S/4 accepts it.
       */
      action raisePurchaseRequisition() returns String;
    };
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
       * reservation, and only a signed day may reach S/4.
       *
       * standardDayHours defaults to 8. Overtime is costed at the same all-in
       * hourly rate as regular time, because the model carries one rate per
       * head-day and no premium - an overtime multiplier would be a number
       * invented here rather than agreed commercially.
       */
      action sign(standardDayHours : Decimal(4,2)) returns String;
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
    };
  entity ReservationLines as projection on wf.ReservationLine {
    *,
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
   * how far its thread has come through the ten-step chain, what is still
   * pending, and — honestly — its S/4 connection state. The project sync is
   * live; the CMT budget commitment is not connected yet, and the screen says
   * so per row rather than implying otherwise.
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
    stepsDone      : Integer;
    stepsTotal     : Integer;
    pendingSteps   : String(255);
    s4Commitment   : String(40);
  };

  /**
   * Exposed here so a daily log can offer a value help for what it charges to.
   * A Fiori value list must resolve inside the service it is annotated in, and
   * a timesheet that asks a foreman to type a WBS UUID is not a screen anyone
   * can use. Read-only: the structures are maintained on ProjectService, and
   * this is a lookup, not a second place to edit them.
   */
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
