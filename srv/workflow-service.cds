/**
 * KONSTRYX — Resource Workflow service
 * The RR -> ADV -> AVC -> RES spine across all verticals (MVP: MR).
 * Reservation lines encumber budget on creation.
 */
using { konstryx.wf } from '../db/wf';
using { konstryx.eq } from '../db/eq';

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
  entity AdvisoryDecisions    as projection on wf.AdvisoryDecision;
  entity AvailabilityChecks   as projection on wf.AvailabilityCheck;

  entity Reservations as projection on wf.Reservation
    actions {
      /** Closes every line and the document; the encumbrance record remains. */
      action close() returns String;
    };
  entity ReservationLines as projection on wf.ReservationLine;

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
