/**
 * KONSTRYX — konstryx.wf (Data Model Spec §6)
 * Workflow spine: RR -> ADV -> AVC -> RES, vertical-agnostic.
 * Status lives on both header and line; lines progress independently.
 */
namespace konstryx.wf;

using { cuid, managed } from '@sap/cds/common';
using { konstryx.common } from './common';
using { konstryx.prj } from './prj';
using { konstryx.master } from './master';

type VerticalType : String enum { MR; EQR; MPR; VR; SCR; SF_DESIGN; SF_MATERIAL; };

// ---- RR (Resource Request) ----
entity ResourceRequest : cuid, managed, common.documented {
  verticalType   : VerticalType;
  wbs            : Association to prj.WBSElement;
  needBy         : Date;
  isSubstitution : Boolean default false;   // MSR flag
  prFlag         : Boolean default false;    // direct-PR indicator
  lines          : Composition of many ResourceRequestLine on lines.parent = $self;
}

entity ResourceRequestLine : cuid {
  parent      : Association to ResourceRequest;
  lineNo      : Integer;
  resource    : Association to master.ResourceNode;  // L5 code
  description : String(255);
  qty         : Decimal(15,3);
  uom         : String(10);
  cbs         : Association to prj.CBSInstance;
  estUnitCost : Decimal(15,2);
  estTotal    : Decimal(15,2);
  needBy      : Date;
  lineStatus  : String(20);
  advisory    : Association to AdvisoryDecision;
  avcResult   : Association to AvailabilityCheckLine;
}

// ---- ADV (Advisory) ----
entity AdvisoryDecision : cuid, managed {
  rr        : Association to ResourceRequest;
  line      : Association to ResourceRequestLine;
  decision  : String enum { IN_HOUSE; PROCURE; SUBSTITUTE; REJECT; };
  decidedBy : String(120);
  decidedOn : DateTime;
  rationale : String(500);
}

// ---- AVC (Availability Check) ----
entity AvailabilityCheck : cuid, managed, common.documented {
  rr    : Association to ResourceRequest;
  lines : Composition of many AvailabilityCheckLine on lines.parent = $self;
}

entity AvailabilityCheckLine : cuid {
  parent       : Association to AvailabilityCheck;
  rrLine       : Association to ResourceRequestLine;
  atpQty       : Decimal(15,3);
  stockQty     : Decimal(15,3);
  expectedQty  : Decimal(15,3);    // stock + inbound GR
  storageLoc   : String(10);
  result       : String(20);
}

// ---- RES (Reservation) ----
entity Reservation : cuid, managed, common.documented {
  rr            : Association to ResourceRequest;
  executionFlow : String enum { IN_HOUSE; PROCUREMENT; };
  lines         : Composition of many ReservationLine on lines.reservation = $self;
}

// The cost-control record; encumbers budget on create (§1.5).
entity ReservationLine : cuid {
  reservation     : Association to Reservation;
  rrLine          : Association to ResourceRequestLine;
  resource        : Association to master.ResourceNode;
  qty             : Decimal(15,3);
  uom             : String(10);
  dailyRate       : Decimal(15,2);
  encumberedAmount: Decimal(15,2);    // locked on create
  consumedToDate  : Decimal(15,3);
  burnPct         : Decimal(5,2);
  costToDate      : Decimal(15,2);
  drift           : Decimal(15,2);
  lineStatus      : String(20);       // Created(Encumbered) -> Issuing -> Consuming -> Reconciling -> Closed
}

// ---- Cross-cutting ----
entity StatusHistory : cuid {
  docType   : String(20);
  docId     : String(40);
  fromState : String(20);
  toState   : String(20);
  changedBy : String(120);
  changedOn : DateTime;
  comment   : String(500);
}

entity DocumentLink : cuid {
  fromDoc  : String(40);
  toDoc    : String(40);
  linkType : String(30);
}
