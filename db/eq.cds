/**
 * KONSTRYX — konstryx.eq
 * Equipment (EQR) vertical extension of the request line.
 *
 * Architecture decision (2026-08-15): vertical-specific attributes hang off
 * the spine as a per-vertical extension entity rather than being denormalised
 * onto wf.ResourceRequestLine or inferred from the advisory decision. The six
 * verticals differ genuinely — an equipment line is instances over a mob/demob
 * window, a material line is a quantity against a delivery date — and one flat
 * line entity carrying the union of all six would be mostly null in every row.
 *
 * The dependency points eq -> wf. The reverse association is declared here by
 * extension so the spine never has to know about its verticals.
 */
namespace konstryx.eq;

using { cuid } from '@sap/cds/common';
using { konstryx.wf } from './wf';
using { konstryx.master } from './master';

entity EquipmentRequestLine : cuid {
  line         : Association to wf.ResourceRequestLine;

  instances    : Integer;                      // units of the asset requested
  durationDays : Integer;
  mobDate      : Date;
  demobDate    : Date;

  // Routing outcome, as executed. The decision itself and its rationale stay
  // on wf.AdvisoryDecision; this records which pool or vendor the line landed
  // on, because a line can be re-sourced by variation without re-opening ADV.
  sourceType   : String enum { OWN_FLEET; RENTAL; };
  sourceDetail : String(120);                  // fleet yard, or vendor trading name
  vendor       : Association to master.Vendor; // set when sourceType = RENTAL

  operatorsReq : Integer;                      // operators are Manpower resource codes
}

// Back-association so a line and its equipment detail come back in one $expand.
extend wf.ResourceRequestLine with {
  equipment : Association to EquipmentRequestLine on equipment.line = $self;
}
