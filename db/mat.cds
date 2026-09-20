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

/**
 * The site asking a store for stock it has already reserved, and the ERP
 * movement that answers.
 *
 * A KONSTRYX document: the site raises it and KONSTRYX numbers it, the same
 * way a resource request is ours and a purchase requisition is not. What ERP
 * owns is the movement — the goods issue document, the date it posted and the
 * quantity it actually moved come back stamped on this row and stay empty
 * until they do. They are deliberately not defaulted from what was asked for:
 * asking for eighty bags and being given sixty is an ordinary day on a site,
 * and the difference is the part worth seeing.
 */
entity PullRequest : cuid, managed, common.documented {
  reservationLine : Association to wf.ReservationLine;
  storageLoc      : String(10);
  qtyRequested    : Decimal(15,3);
  qtyIssued       : Decimal(15,3);
  /**
   * What the issue cost, priced at the rate the reservation line was
   * encumbered at. The budget was locked against that rate and the approval
   * was shown it; a rate that has moved since is a variance to report, not
   * one to absorb into the spend without saying so.
   */
  issuedValue     : Decimal(15,2);
  s4GIDoc         : String(20);
  s4GIDate        : Date;
  s4GIQty         : Decimal(15,3);
  s4System        : String(20);
  /** What ERP said when it would not move the stock. */
  syncMessage     : String(1000);
  receipts        : Composition of many SiteReceipt on receipts.pullRequest = $self;
}

/** What the site says arrived, against what the store says it issued. */
entity SiteReceipt : cuid, managed {
  pullRequest     : Association to PullRequest;
  confirmedOnSite : Boolean default false;
  receivedQty     : Decimal(15,3);
  /**
   * What was still unaccounted for after this confirmation — issued less
   * everything received to that point, not just this row. A load arriving in
   * parts is confirmed in parts, and a running balance says whether the last
   * one closed the draw; a per-row difference would read as a shortfall on
   * every partial delivery that was later completed.
   *
   * Stored rather than derived on the screen so a storekeeper can list the
   * draws still owed something without reading every one of them.
   */
  shortQty        : Decimal(15,3);
  note            : String(500);
  receivedBy      : String(120);
  receivedOn      : Date;
}

/**
 * What the work should have consumed against what it did.
 *
 * Theoretical is the day's output times the norm; the wastage allowance is
 * the margin the norm itself grants. A line only overruns once it has spent
 * both, which is why variance is measured against the two together and not
 * against the bare norm.
 */
entity ConsumptionRecord : cuid, managed {
  reservationLine : Association to wf.ReservationLine;
  recordDate      : Date;
  diaryOutputQty  : Decimal(15,3);
  theoreticalQty  : Decimal(15,3);   // diary output x consRate
  actualQty       : Decimal(15,3);
  wastageAllowance: Decimal(15,3);
  /** The norm in force on the record date, kept so the arithmetic can be read back. */
  rateApplied     : Decimal(15,4);
  variance        : Decimal(15,3);
  /**
   * Widened from 5,2: a day that consumed ten times its norm is a real site
   * event, and a percentage column that cannot hold 1,000 turns it into a
   * failed insert rather than a reported overrun.
   */
  variancePct     : Decimal(9,2);
  result          : String(20);      // Within allowance / Over allowance
  recordedBy      : String(120);
  note            : String(500);
}

/**
 * The reservation's final account: what it consumed against what it locked,
 * and what went back to the budget when it stopped.
 */
entity ReservationClosure : cuid, managed {
  reservation    : Association to wf.Reservation;
  finalActual    : Decimal(15,3);
  theoretical    : Decimal(15,3);
  variance       : Decimal(15,3);
  /** Encumbered less consumed, floored at zero — an overrun releases nothing. */
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
   * What to order, in ERP terms. Resolved from the resource when the requisition
   * is raised, not when it is pushed, so remapping a resource later cannot
   * change what an already-open requisition buys. Empty where the resource has
   * no material registered — the ask is still valid, it is the push that stalls.
   */
  material     : Association to master.Material;
  description  : String(255);
  /**
   * Account assignment. A requisition without these cannot commit against the
   * right budget line when ERP returns the commitment (chain step CMT).
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
 * Genuinely ERP-mastered, unlike the requisition: KONSTRYX never creates a
 * purchase order (INTEGRATION.md — "Purchase Order, Goods Receipt, Invoice:
 * ERP -> KONSTRYX"). It is mirrored back so the project can see what was
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
  /**
   * The order's own value, and what of it is still outstanding. Both are
   * summed from the lines whenever the order or one of its receipts is
   * mirrored, rather than counted up as documents arrive: a counter cannot
   * survive an order being cancelled and re-mirrored, and a header that
   * disagrees with its own lines is the one number nobody checks.
   */
  netValue          : Decimal(15,2);
  openValue         : Decimal(15,2);
  /** What the vendor has billed of it, and what of that matched cleanly. */
  invoicedValue     : Decimal(15,2);
  lines             : Composition of many PurchaseOrderLine on lines.parent = $self;
  /**
   * Association rather than composition: a receipt is ERP's document in its
   * own right, and deleting an order here must not take the receipts with it.
   */
  receipts          : Association to many GoodsReceipt on receipts.po = $self;
  invoices          : Association to many SupplierInvoice on invoices.po = $self;
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
  /** What the receipts have brought in, in the line's own unit. */
  receivedQty  : Decimal(15,3);
  /** What the vendor has billed, in the same unit, and for how much. */
  invoicedQty  : Decimal(15,3);
  invoicedValue: Decimal(15,2);
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
  /**
   * The line the receipt landed on, resolved when the receipt is mirrored.
   * poLineNo alone is how ERP names it; the reference is what lets a screen
   * show the receipt beside the description and account assignment it
   * belongs to without re-reading the order line by line.
   */
  poLine       : Association to PurchaseOrderLine;
  grQty        : Decimal(15,3);
  /** Priced at the order line's own rate, which is what a receipt accrues. */
  grValue      : Decimal(15,2);
  datePosted   : Date;
  /**
   * Order, receipt and invoice agreeing. Stamped when an invoice line lands on
   * this receipt, never before: a receipt cannot answer a question about a
   * document nobody holds, and an unset value says exactly that.
   */
  threeWayMatch: Boolean;
  /** Why the match failed, when it did. Empty while it holds. */
  matchVariance: String(255);
}

/**
 * The vendor's bill, mirrored from ERP FI.
 *
 * The last of the three documents, and the one that turns money the project
 * has committed into money it has spent. KONSTRYX raises no invoice and pays
 * nothing — this exists so a budget line can say what it has actually cost,
 * which is the one figure on the control record that has never had a source.
 */
entity SupplierInvoice : cuid, managed, common.s4mirror {
  invoiceNo   : String(10);
  vendor      : Association to master.Vendor;
  /** The order it bills. Every line must sit on that order's lines. */
  po          : Association to PurchaseOrder;
  project     : Association to prj.Project;
  company     : Association to admin.Company;
  postingDate : Date;
  netAmount   : Decimal(15,2);
  status      : String(20);
  /**
   * Whether every line matched its order and its receipt. Held on the header
   * as well as the lines because this is what a clerk filters on: one blocked
   * invoice in a run of two hundred is not found by opening each one.
   */
  matched     : Boolean;
  lines       : Composition of many SupplierInvoiceLine on lines.parent = $self;
}

entity SupplierInvoiceLine : cuid {
  parent       : Association to SupplierInvoice;
  lineNo       : Integer;
  /** The order line billed. Its assignment is what the cost lands on. */
  poLine       : Association to PurchaseOrderLine;
  poLineNo     : Integer;
  /** The receipt this bills against, where one covers it. */
  goodsReceipt : Association to GoodsReceipt;
  description  : String(255);
  qty          : Decimal(15,3);
  netAmount    : Decimal(15,2);
  /**
   * The three-way match, per line, because that is where it is decided: the
   * quantity billed against the quantity received, and the value billed
   * against the order's own rate for it.
   */
  matched      : Boolean;
  variance     : String(255);
}

// ---- R3 stubs: Bid Analyzer ----
entity RfqEvent    : cuid, managed { eventNo : String(20); source : String(20); status : String(20); }
entity Quotation   : cuid, managed { quoteNo : String(20); vendor : Association to master.Vendor; }
entity BidAnalysis : cuid, managed { boqRef : String(20); criterion : String(60); factor : Decimal(5,2);
                                     localContent : Decimal(5,2); pastPerformanceScore : Decimal(5,2); }
