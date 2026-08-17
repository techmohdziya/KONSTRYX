/**
 * KONSTRYX — Material Execution service (MR vertical, MVP)
 * Pull request / goods issue, site receipt, consumption, reservation closure,
 * and S/4 PR/PO/GR mirrors. R3 stubs: RFQ/Quotation/Bid Analyzer.
 */
using { konstryx.mat } from '../db/mat';

@requires: 'SiteEngineer'
service MaterialService @(path:'/material') {
  entity PullRequests        as projection on mat.PullRequest
    actions { action postGoodsIssue(); };
  entity SiteReceipts        as projection on mat.SiteReceipt;
  entity ConsumptionRecords  as projection on mat.ConsumptionRecord;
  entity ReservationClosures as projection on mat.ReservationClosure;

  /**
   * Raised by WorkflowService.raisePurchaseRequisition, never keyed by hand —
   * read-only here for the same reason a reservation is: the document exists
   * because a decision upstream created it. S/4 owns its number.
   */
  @readonly entity PurchaseRequisitions     as projection on mat.PurchaseRequisition
    actions {
      /**
       * The requisition's inbound half: S/4 accepted it and issued a number,
       * or refused it. Called by the connector, and the same entry point a
       * manual correction uses — one writer for sync state either way, the
       * way projects already work (ProjectService.recordSyncResult).
       */
      action recordRequisitionResult(success : Boolean, prNo : String(10),
                                     s4System : String(20),
                                     message : String(1000)) returns String;
    };
  @readonly entity PurchaseRequisitionLines as projection on mat.PurchaseRequisitionLine;

  // S/4 mirrors — read-only
  @readonly entity PurchaseOrders     as projection on mat.PurchaseOrder;
  @readonly entity PurchaseOrderLines as projection on mat.PurchaseOrderLine;
  @readonly entity GoodsReceipts      as projection on mat.GoodsReceipt;

  /**
   * Mirrors a purchase order S/4 raised against one of our requisitions.
   * KONSTRYX never creates a PO, so this is inbound only — the connector
   * calls it, and it is also the entry point a test or a manual correction
   * uses, so every path writes the same state.
   *
   * Lines are matched to the requisition's own lines by prLineNo, which is
   * how S/4's "create with reference to requisition" behaves; each mirrored
   * line inherits that requisition line's account assignment, and that is
   * what lets the order's value commit against the right budget line.
   */
  action recordPurchaseOrder(
    requisitionId : UUID,
    poNo          : String(10),
    vendorBP      : String(10),
    s4System      : String(20),
    orderedOn     : Date,
    lines         : array of {
      prLineNo : Integer;
      qty      : Decimal(15,3);
      netValue : Decimal(15,2);
      eta      : Date;
    }
  ) returns String;

  // R3 Bid Analyzer stubs
  @readonly entity RfqEvents    as projection on mat.RfqEvent;
  @readonly entity Quotations   as projection on mat.Quotation;
  @readonly entity BidAnalyses  as projection on mat.BidAnalysis;
}
