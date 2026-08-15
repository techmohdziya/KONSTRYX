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

  // S/4 mirrors — read-only
  @readonly entity PurchaseRequisitions as projection on mat.PurchaseRequisition;
  @readonly entity PurchaseOrders       as projection on mat.PurchaseOrder;
  @readonly entity GoodsReceipts        as projection on mat.GoodsReceipt;

  // R3 Bid Analyzer stubs
  @readonly entity RfqEvents    as projection on mat.RfqEvent;
  @readonly entity Quotations   as projection on mat.Quotation;
  @readonly entity BidAnalyses  as projection on mat.BidAnalysis;
}
