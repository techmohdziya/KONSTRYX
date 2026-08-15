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
entity PurchaseRequisition : cuid, managed, common.s4mirror {
  prNo   : String(10);
  status : String(20);
  lines  : Composition of many PurchaseRequisitionLine on lines.parent = $self;
}

entity PurchaseRequisitionLine : cuid {
  parent       : Association to PurchaseRequisition;
  lineNo       : Integer;
  material     : Association to master.Material;
  qtyProcure   : Decimal(15,3);
  estUnitPrice : Decimal(15,2);
  estTotal     : Decimal(15,2);
  needBy       : Date;
  status       : String(20);
  approverRole : String(60);
}

entity PurchaseOrder : cuid, managed, common.s4mirror {
  poNo         : String(10);
  vendor       : Association to master.Vendor;
  status       : String(20);
  lines        : Composition of many PurchaseOrderLine on lines.parent = $self;
}

entity PurchaseOrderLine : cuid {
  parent       : Association to PurchaseOrder;
  lineNo       : Integer;
  material     : Association to master.Material;
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
