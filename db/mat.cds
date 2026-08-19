/**
 * KONSTRYX — konstryx.mat (Data Model Spec §7)
 * MR vertical (MVP): issue, receipt, consumption, closure + S/4 PR/PO/GR mirrors.
 * R3 stubs: RFQ / Quotation / Bid Analyzer.
 */
namespace konstryx.mat;

using { cuid, managed, Currency } from '@sap/cds/common';
using { konstryx.common } from './common';
using { konstryx.wf } from './wf';
using { konstryx.master } from './master';
using { konstryx.prj } from './prj';
using { konstryx.admin } from './admin';

// Issue against a reservation line (Konstryx + S/4 GI mirror).
entity PullRequest : cuid, managed {
  pullReqNo       : String(20);
  reservationLine : Association to wf.ReservationLine;
  storageLoc      : String(10);
  qtyRequested    : Decimal(15,3);
  qtyIssued       : Decimal(15,3);
  s4GIDoc         : String(20);
  s4GIDate        : Date;
  s4GIQty         : Decimal(15,3);
  status          : String(20);
}

entity SiteReceipt : cuid, managed {
  pullRequest     : Association to PullRequest;
  confirmedOnSite : Boolean default false;
  receivedQty     : Decimal(15,3);
  receivedBy      : String(120);
  receivedOn      : Date;
}

entity ConsumptionRecord : cuid, managed {
  reservationLine : Association to wf.ReservationLine;
  recordDate      : Date;
  diaryOutputQty  : Decimal(15,3);
  theoreticalQty  : Decimal(15,3);   // qty x consRate
  actualQty       : Decimal(15,3);   // from S/4
  wastageAllowance: Decimal(15,3);
  variance        : Decimal(15,3);
  variancePct     : Decimal(5,2);
}

entity ReservationClosure : cuid, managed {
  reservation    : Association to wf.Reservation;
  finalActual    : Decimal(15,3);
  theoretical    : Decimal(15,3);
  variance       : Decimal(15,3);
  releasedAmount : Decimal(15,2);
  result         : String(20);
  postedBy       : String(120);
  postedOn       : Date;
}

// ---- S/4 mirrors (created via API) ----

/**
 * The purchase requisition is NOT a KONSTRYX document (your ruling: "Resource
 * request is KONSTRYX doc, Purchase request is S/4 number not internal").
 * KONSTRYX raises it from the PROCURE-decided lines of a resource request, but
 * S/4 assigns the number and owns the document from then on — so this entity
 * deliberately does NOT carry common.documented and never draws a KONSTRYX
 * number range. prNo stays empty until S/4 accepts it.
 *
 * s4outbound, not s4mirror: a mirror defaults syncStatus to OK, which would
 * call a requisition that never reached S/4 a good one. Outbound defaults to
 * NOT_SENT and keeps what S/4 said when it refused.
 */
entity PurchaseRequisition : cuid, managed, common.s4outbound {
  /** The S/4 requisition number. Filled on acceptance, never issued here. */
  prNo          : String(10);
  status        : String(20);
  /** Where it came from: the request whose PROCURE lines raised it. */
  sourceRequest : Association to wf.ResourceRequest;
  /**
   * Carried rather than reached through sourceRequest so the buyer's worklist
   * can filter and the authorization layer can scope without a join.
   */
  project       : Association to prj.Project;
  company       : Association to admin.Company;
  raisedBy      : String(120);
  raisedOn      : Date;
  lines         : Composition of many PurchaseRequisitionLine on lines.parent = $self;
}

entity PurchaseRequisitionLine : cuid {
  parent       : Association to PurchaseRequisition;
  lineNo       : Integer;
  /** What was actually asked for, in KONSTRYX terms. */
  resource     : Association to master.ResourceNode;
  /**
   * What to order, in S/4 terms. Resolved from the resource when the requisition
   * is raised, not when it is pushed, so remapping a resource later cannot
   * change what an already-open requisition buys. Empty where the resource has
   * no material registered — the ask is still valid, it is the push that stalls.
   */
  material     : Association to master.Material;
  description  : String(255);
  /**
   * Account assignment. A requisition without these cannot commit against the
   * right budget line when S/4 returns the commitment (chain step CMT).
   */
  wbs          : Association to prj.WBSElement;
  cbs          : Association to prj.CBSInstance;
  /** The request line this came from, so the chain stays traceable both ways. */
  sourceLine   : Association to wf.ResourceRequestLine;
  qtyProcure   : Decimal(15,3);
  uom          : String(10);
  estUnitPrice : Decimal(15,2);
  estTotal     : Decimal(15,2);
  needBy       : Date;
  status       : String(20);
  approverRole : String(60);
}

/**
 * Genuinely S/4-mastered, unlike the requisition: KONSTRYX never creates a
 * purchase order (INTEGRATION.md — "Purchase Order, Goods Receipt, Invoice:
 * S/4 -> KONSTRYX"). It is mirrored back so the project can see what was
 * ordered against its requisition, and so the order's value can commit
 * against the budget line it charges. s4mirror is therefore correct here.
 */
entity PurchaseOrder : cuid, managed, common.s4mirror {
  poNo              : String(10);
  vendor            : Association to master.Vendor;
  status            : String(20);
  /** The requisition S/4 created it against, so the chain reads back. */
  sourceRequisition : Association to PurchaseRequisition;
  /** Carried for scoping and worklists, as on the requisition. */
  project           : Association to prj.Project;
  company           : Association to admin.Company;
  orderedOn         : Date;
  lines             : Composition of many PurchaseOrderLine on lines.parent = $self;
}

entity PurchaseOrderLine : cuid {
  parent       : Association to PurchaseOrder;
  lineNo       : Integer;
  material     : Association to master.Material;
  resource     : Association to master.ResourceNode;
  description  : String(255);
  /**
   * Account assignment, carried from the requisition line. This is what lets
   * netValue commit against the right budget line — without it an order is
   * money spent against nothing in particular.
   */
  wbs          : Association to prj.WBSElement;
  cbs          : Association to prj.CBSInstance;
  sourcePRLine : Association to PurchaseRequisitionLine;
  qty          : Decimal(15,3);
  openQty      : Decimal(15,3);
  netValue     : Decimal(15,2);
  eta          : Date;
  acknowledged : Boolean;
  paymentTerms : String(10);
  status       : String(20);
}

entity GoodsReceipt : cuid, managed, common.s4mirror {
  grDoc        : String(20);
  po           : Association to PurchaseOrder;
  poLineNo     : Integer;
  grQty        : Decimal(15,3);
  datePosted   : Date;
  threeWayMatch: Boolean;
}

// ---- R3 stubs: Bid Analyzer ----
entity RfqEvent    : cuid, managed { eventNo : String(20); source : String(20); status : String(20); }
entity Quotation   : cuid, managed { quoteNo : String(20); vendor : Association to master.Vendor; }
entity BidAnalysis : cuid, managed { boqRef : String(20); criterion : String(60); factor : Decimal(5,2);
                                     localContent : Decimal(5,2); pastPerformanceScore : Decimal(5,2); }
