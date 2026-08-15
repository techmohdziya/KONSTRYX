/**
 * KONSTRYX — Resource Workflow service
 * The RR -> ADV -> AVC -> RES spine across all verticals (MVP: MR).
 * Reservation lines encumber budget on creation.
 */
using { konstryx.wf } from '../db/wf';

@requires: 'ResourceCoordinator'
service WorkflowService @(path:'/workflow') {
  @odata.draft.enabled
  entity ResourceRequests as projection on wf.ResourceRequest
    actions {
      action submit();
      action sendToAdvisory();
    };
  entity ResourceRequestLines as projection on wf.ResourceRequestLine;
  entity AdvisoryDecisions    as projection on wf.AdvisoryDecision;
  entity AvailabilityChecks   as projection on wf.AvailabilityCheck;

  entity Reservations as projection on wf.Reservation
    actions {
      action close();
    };
  entity ReservationLines as projection on wf.ReservationLine;

  @readonly entity StatusHistory as projection on wf.StatusHistory;
  @readonly entity DocumentLinks as projection on wf.DocumentLink;
}
