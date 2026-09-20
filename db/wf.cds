/**
 * KONSTRYX — konstryx.wf (Data Model Spec §6)
 * Workflow spine: RR -> ADV -> AVC -> RES, vertical-agnostic.
 * Status lives on both header and line; lines progress independently.
 */
namespace konstryx.wf;

using { cuid, managed } from '@sap/cds/common';
using { konstryx.sys } from './sys';
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
  /**
   * What was filed with this request. An association rather than a
   * composition: an attachment belongs to the upload, not to the document,
   * and deleting a request should not silently take a signed permit with it.
   */
  attachments : Association to many sys.Attachment on attachments.objectID = ID;
  /**
   * The chain this request produced, and the one that produced it.
   *
   * The links were being written by the chain handler and read by nothing.
   * Every step of a request's life was recorded and no screen showed it, so a
   * coordinator holding an approved request had no way to see whether it had
   * become an availability check, a reservation, a requisition, some of those
   * or none.
   *
   * Joined on the document number rather than a key, because the chain crosses
   * entities: a foreign key per target would need a column for every kind of
   * document a request might ever produce.
   */
  flowOut : Association to many DocumentLink on flowOut.fromDoc = docNo;
  flowIn  : Association to many DocumentLink on flowIn.toDoc = docNo;
  /** Every state this request has been through, and who moved it. */
  history : Association to many StatusHistory on history.docId = docNo;
}

entity ResourceRequestLine : cuid {
  parent      : Association to ResourceRequest;
  lineNo      : Integer;
  resource    : Association to master.ResourceNode;  // L5 code
  description : String(255);
  qty         : Decimal(15,3);
  uom         : String(10);
  // Spec §6: every line carries one WBS and one CBS. The header WBS is the
  // request's default; lines may charge different WBS elements, which the
  // canonical EQR thread does (two lines on 2.04, one on 1.02, two on 0.10).
  wbs         : Association to prj.WBSElement;
  cbs         : Association to prj.CBSInstance;
  estUnitCost : Decimal(15,2);
  estTotal    : Decimal(15,2);
  needBy      : Date;
  // How long the resource is wanted for. A crane priced per day and a bag of
  // cement priced per bag both have a quantity and a rate, and only one of
  // them costs its rate once: without a period, a request for two cranes at
  // 320 a day asks for 640, which is what a two-day hire costs and not what
  // anybody meant. Both dates or neither -- a line with only one end of a
  // period has said nothing about duration.
  periodFrom  : Date;
  periodTo    : Date;
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
  // Wide enough for a sentence a human wrote. Twenty characters forced the
  // seed into fragments like "FA valid · quoted" and truncated anything real.
  result       : String(60);
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
  // The duration behind the lock, taken from the request line's period. The
  // amount alone cannot be read back: 416,000 against 8 heads at 520 is a
  // hundred days, but only if you already know the arithmetic ran that way,
  // and dividing to find out breaks on a line that locked nothing. Null on
  // reservations raised before the period existed, where the division is
  // still the only answer available.
  reservedDays    : Decimal(9,2);
  consumedToDate  : Decimal(15,3);
  burnPct         : Decimal(5,2);
  costToDate      : Decimal(15,2);
  drift           : Decimal(15,2);
  lineStatus      : String(20);       // Created(Encumbered) -> Issuing -> Consuming -> Reconciling -> Closed
}

/**
 * A change to a reservation that is already live: step 8 of the chain.
 *
 * Not the same document as a BOQ variation. That one varies a priced bill and
 * argues with the client about revenue; this one varies what the job has
 * locked to build with, and the only party to it is the project. Slab cycle
 * slipped, both cranes need thirty more days: nothing about the bill changed,
 * and the reservation is now short.
 *
 * A variation is applied, not proposed. It carries the before and the after on
 * every line it touches, so what the lock was at the moment it moved survives
 * the move — otherwise the only record of a rate that doubled is the rate it
 * doubled to.
 */
entity ReservationVariation : cuid, managed, common.documented {
  reservation   : Association to Reservation;
  /**
   * Why the reservation moved, which is not the same question as what moved.
   * A duration extension and a rate correction can produce the identical
   * delta, and only one of them is a planning failure.
   */
  reason        : String(20) enum {
    DURATION; QUANTITY; RATE; SCOPE; CANCELLATION;
  };
  narrative     : String(500);
  effectiveFrom : Date;
  decidedBy     : String(120);
  decidedOn     : Date;
  /** Signed: the sum of its lines. Negative gives budget back. */
  deltaAmount   : Decimal(15,2);
  lines         : Composition of many ReservationVariationLine
                    on lines.variation = $self;
}

/**
 * One line's move. Before and after are both stored: the reservation line
 * itself only ever holds the current figure, so without these a variation
 * could be read but never checked.
 */
entity ReservationVariationLine : cuid {
  variation        : Association to ReservationVariation;
  reservationLine  : Association to ReservationLine;
  qtyBefore        : Decimal(15,3);
  qtyAfter         : Decimal(15,3);
  rateBefore       : Decimal(15,2);
  rateAfter        : Decimal(15,2);
  /**
   * The days the lock covers. Not stored on the reservation line — its
   * quantity is heads and its rate is per day, so the duration is whatever
   * the approved lock divided by the two comes to. Written down here because
   * a variation is the one moment it is known, and a lock read back years
   * later cannot say whether it grew by heads or by weeks.
   */
  daysBefore       : Decimal(9,2);
  daysAfter        : Decimal(9,2);
  encumberedBefore : Decimal(15,2);
  encumberedAfter  : Decimal(15,2);
  /** After less before. What the budget gains or gives up on this line. */
  delta            : Decimal(15,2);
}

// ---- Cross-cutting ----
entity StatusHistory : cuid {
  docType   : String(20);
  docId     : String(40);
  fromState : String(20);
  toState   : String(20);
  changedBy : String(120);
  changedOn : DateTime;
  /**
   * Where this entry sits in that document's own account of itself, counting
   * from one.
   *
   * Ordering on changedOn alone cannot separate two moves made inside one
   * request: they tie on the wall clock, and what comes back first is then
   * whatever the store feels like. A withdrawal and the resubmission that
   * followed it read in either order on successive runs, which on a record
   * whose whole purpose is to say how a document got where it is means it can
   * be read as saying the opposite.
   *
   * Per document rather than global, so it survives the document being given a
   * new number: a requisition enters the flow under its own key and takes its
   * history with it when ERP issues one, and the entries stay in the order
   * they happened.
   */
  seq       : Integer;
  comment   : String(500);
}

/**
 * One step of a document chain: which document produced which, and how.
 *
 * Held by document number rather than by key because the chain crosses
 * entities - a request produces an availability check, a reservation and a
 * requisition - and a foreign key per target would need a column for every
 * kind of document anything might ever produce.
 */
entity DocumentLink : cuid {
  fromDoc  : String(40);
  toDoc    : String(40);
  linkType : String(30);
  /** When the step happened, so a flow reads in the order it occurred. */
  linkedAt : Timestamp;
}
