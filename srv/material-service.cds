/**
 * KONSTRYX — Material Execution service (MR vertical, MVP)
 * Pull request / goods issue, site receipt, consumption, reservation closure,
 * and S/4 PR/PO/GR mirrors. R3 stubs: RFQ/Quotation/Bid Analyzer.
 */
using { konstryx.mat } from '../db/mat';

@requires: 'SiteEngineer'
service MaterialService @(path:'/material') {
  /**
   * Read-only for the same reason a reservation is: a pull request exists
   * because a reservation line stands behind it, and one keyed by hand would
   * draw stock nothing has locked the money for. WorkflowService.raisePull
   * creates it; everything after that is one of the actions below.
   */
  @readonly entity PullRequests as projection on mat.PullRequest {
    *,
    project.code            as projectCode      : String(24),
    project.name            as projectName      : String(150),
    reservationLine.reservation.docNo as reservationNo : String(20),
    reservationLine.resource.code     as resourceCode  : String(40),
    reservationLine.uom               as uom           : String(10),
    qtyRequested - qtyIssued as shortIssued : Decimal(15,3),
    case status
      when 'Confirmed'     then 3
      when 'Part received' then 2
      when 'Refused'       then 1
      else 0
    end as statusCriticality : Integer
  }
  actions {
    /**
     * ERP moved the stock, and this is what it moved — or refused to, with the
     * reason. The movement is ERP's document: KONSTRYX asks for it with the
     * pull request and never posts one itself, so this is the only way a goods
     * issue enters. The connector and a manual correction both come through
     * here, so an issue only ever lands one way.
     */
    action recordGoodsIssue(giDoc : String(20), giDate : Date,
                            giQty : Decimal(15,3), s4System : String(20),
                            message : String(1000)) returns String;

    /** The site's count of what actually arrived. */
    action confirmSiteReceipt(receivedQty : Decimal(15,3),
                              receivedBy : String(120),
                              receivedOn : Date,
                              note : String(500)) returns String;
  };

  @readonly entity SiteReceipts as projection on mat.SiteReceipt {
    *,
    pullRequest.docNo as pullRequestNo : String(20),
    case when shortQty > 0 then 2 else 3 end as shortCriticality : Integer
  };

  @readonly entity ConsumptionRecords as projection on mat.ConsumptionRecord {
    *,
    reservationLine.reservation.docNo   as reservationNo : String(20),
    reservationLine.reservation.project.code as projectCode : String(24),
    reservationLine.resource.code       as resourceCode  : String(40),
    reservationLine.uom                 as uom           : String(10),
    case when variance > 0 then 1 when variance < 0 then 3 else 0
    end as varianceCriticality : Integer
  };

  @readonly entity ReservationClosures as projection on mat.ReservationClosure {
    *,
    reservation.docNo        as reservationNo : String(20),
    reservation.project.code as projectCode   : String(24),
    case result when 'Overrun' then 1 when 'Underrun' then 2 else 3
    end as resultCriticality : Integer
  };

  /**
   * A day's consumption against the norm in force on that day. Unbound: the
   * record does not exist yet, and the reservation line it belongs to is what
   * identifies it.
   */
  action recordConsumption(
    reservationNo  : String(20),
    lineNo         : Integer,
    resourceCode   : String(40),
    recordDate     : Date,
    diaryOutputQty : Decimal(15,3),
    actualQty      : Decimal(15,3),
    note           : String(500)
  ) returns String;

  /**
   * Raised by WorkflowService.raisePurchaseRequisition, never keyed by hand —
   * read-only here for the same reason a reservation is: the document exists
   * because a decision upstream created it. S/4 owns its number.
   */
  @readonly entity PurchaseRequisitions     as projection on mat.PurchaseRequisition
    actions {
      /**
       * The live push (SAP_COM_0053). Sends the requisition and records what
       * came back — the counterpart of recordRequisitionResult, exactly as
       * ProjectService.syncToS4 is to recordSyncResult. Only a requisition S/4
       * has not already numbered may go; re-sending an accepted one would buy
       * the same scope twice.
       */
      action syncToS4() returns String;

      /**
       * The requisition's inbound half: ERP accepted it and issued a number,
       * or refused it. Called by the connector, and the same entry point a
       * manual correction uses — one writer for sync state either way, the
       * way projects already work (ProjectService.recordSyncResult).
       */
      action recordRequisitionResult(success : Boolean, prNo : String(10),
                                     s4System : String(20),
                                     message : String(1000)) returns String;
    };
  @readonly entity PurchaseRequisitionLines as projection on mat.PurchaseRequisitionLine;

  // ERP mirrors — read-only
  @readonly entity PurchaseOrders     as projection on mat.PurchaseOrder {
    *,
    // Flattened rather than reached through the association: the project,
    // the vendor and the requisition all live in services this one does not
    // expose, so without their codes here every column on the order list
    // renders as a key nobody can read.
    project.code           as projectCode   : String(24),
    project.name           as projectName   : String(150),
    vendor.bpNumber        as vendorNo      : String(10),
    vendor.name            as vendorName    : String(150),
    sourceRequisition.prNo as requisitionNo : String(10),
    // Kept here rather than in the annotations so the buyer's list, the
    // project's list and anything else that shows an order all colour it the
    // same way. An order still carrying open value is the ordinary case, not
    // a warning; the two states worth marking are settled and stopped.
    case status
      when 'Received'  then 3
      when 'Cancelled' then 1
      else 0
    end as statusCriticality : Integer
  };
  @readonly entity PurchaseOrderLines as projection on mat.PurchaseOrderLine {
    *,
    wbs.code      as wbsCode      : String(24),
    cbs.code      as cbsCode      : String(40),
    material.materialCode as materialCode : String(40),
    case status
      when 'Received' then 3
      else 0
    end as statusCriticality : Integer
  };
  @readonly entity GoodsReceipts      as projection on mat.GoodsReceipt {
    *,
    case
      when threeWayMatch is null then 0
      when threeWayMatch      then 3
      else 1
    end as matchCriticality : Integer
  };
  /**
   * Service entry sheets: the acceptance of work that arrives on no lorry.
   *
   * Read-only for the same reason the goods receipt is. S/4 owns the
   * acceptance because S/4 owns the commitment it releases, and a sheet
   * entered in two places would release it twice.
   */
  @readonly entity ServiceEntrySheets as projection on mat.ServiceEntrySheet {
    *,
    po.poNo as orderNo : String(10),
    case
      when threeWayMatch is null then 0
      when threeWayMatch      then 3
      else 1
    end as matchCriticality : Integer
  };
  @readonly entity SupplierInvoices     as projection on mat.SupplierInvoice {
    *,
    po.poNo         as orderNo    : String(10),
    vendor.name     as vendorName : String(150),
    project.code    as projectCode : String(24),
    case
      when matched is null then 0
      when matched      then 3
      else 1
    end as matchCriticality : Integer
  };
  @readonly entity SupplierInvoiceLines as projection on mat.SupplierInvoiceLine {
    *,
    case
      when matched is null then 0
      when matched      then 3
      else 1
    end as matchCriticality : Integer
  };

  /**
   * Mirrors a purchase order ERP raised against one of our requisitions.
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

  /**
   * Mirrors a goods receipt ERP posted against one of the orders we hold.
   * The receipt is what turns an order from committed into delivered, so it
   * is the leg that moves openQty and closes the line — without it every
   * order stays fully open however much of it has arrived on site.
   *
   * Lines are matched by the order's own line numbers. A receipt for more
   * than the line still has open is refused rather than clamped: an
   * over-delivery is a real event and it needs the order corrected, not the
   * excess quietly dropped.
   */
  action recordGoodsReceipt(
    poNo       : String(10),
    grDoc      : String(20),
    s4System   : String(20),
    datePosted : Date,
    lines      : array of {
      poLineNo : Integer;
      grQty    : Decimal(15,3);
    }
  ) returns String;

  /**
   * Mirrors a supplier invoice ERP FI posted against one of our orders.
   *
   * The third document, and the one that decides what the project has spent.
   * Each line is matched three ways as it lands: against the order line it
   * bills, against what the receipts on that line actually brought in, and
   * against the order's own rate for it. A line that fails is recorded as
   * failed WITH the reason, not refused — ERP posted the invoice whether or
   * not it agrees with the order, and an invoice we would not mirror is one
   * nobody can see is wrong. Refusal is reserved for what makes the document
   * unreadable: no number, no order, a line that is not on that order.
   */
  action recordSupplierInvoice(
    poNo        : String(10),
    invoiceNo   : String(10),
    s4System    : String(20),
    postingDate : Date,
    lines       : array of {
      poLineNo  : Integer;
      qty       : Decimal(15,3);
      netAmount : Decimal(15,2);
    }
  ) returns String;

  // R3 Bid Analyzer stubs
  @readonly entity RfqEvents    as projection on mat.RfqEvent;
  @readonly entity Quotations   as projection on mat.Quotation;
  @readonly entity BidAnalyses  as projection on mat.BidAnalysis;
}
