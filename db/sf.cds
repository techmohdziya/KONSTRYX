/**
 * KONSTRYX — konstryx.sf
 * Scaffolding & Formwork vertical extension of the request line.
 *
 * Same architecture as konstryx.eq / konstryx.mpr (2026-08-15): vertical-
 * specific attributes hang off the spine as a per-vertical extension rather
 * than being denormalised onto wf.ResourceRequestLine.
 *
 * SF is two verticals, not one (VerticalType: SF_DESIGN, SF_MATERIAL — see
 * db/wf.cds) because they are genuinely different requests: a design line
 * asks an engineer for a scheme before any element is booked, a material
 * line books element quantities for a rental window. A line carries one
 * verticalType and populates exactly one of the two extensions below.
 *
 * The dependency points sf -> wf. The reverse associations are declared here
 * by extension so the spine never has to know about its verticals.
 */
namespace konstryx.sf;

using { cuid } from '@sap/cds/common';
using { konstryx.wf } from './wf';
using { konstryx.master } from './master';

/** SF_DESIGN: the engineering deliverable that precedes any booking. */
entity ScaffoldDesignRequestLine : cuid {
  line           : Association to wf.ResourceRequestLine;

  deliverable    : String enum { SCHEME; DRAWING; CALC_NOTE; };
  loadClass      : String(40);                 // design load case, e.g. TG5 heavy duty
  engineer       : String(120);
  dueDate        : Date;

  /** Set once the engineer signs off; BOQ / booking downstream waits on this. */
  approvedOn     : Date;
}

/** SF_MATERIAL: element quantities booked for a rental window. */
entity ScaffoldMaterialRequestLine : cuid {
  line           : Association to wf.ResourceRequestLine;

  elementType    : String(60);                 // standard, ledger, board, tie, base plate, ...
  bookingStart   : Date;
  bookingEnd     : Date;

  sourceType     : String enum { OWN_YARD; RENTAL; };
  vendor         : Association to master.Vendor; // set when sourceType = RENTAL

  /** Per-qty-per-day rental rate; billing runs to plant's cut-off, not this date. */
  ratePerDayUnit : Decimal(15,2);

  /** Set on return/inspection; what came back short or damaged is a variance to report. */
  returnedQty    : Decimal(15,3);
  returnCondition : String enum { OK; DAMAGED; SHORT; };
}

// Back-associations so a line and its SF detail come back in one $expand.
extend wf.ResourceRequestLine with {
  scaffoldDesign   : Association to ScaffoldDesignRequestLine on scaffoldDesign.line = $self;
  scaffoldMaterial : Association to ScaffoldMaterialRequestLine on scaffoldMaterial.line = $self;
}
