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
