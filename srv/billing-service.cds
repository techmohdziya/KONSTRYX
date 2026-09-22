/**
 * KONSTRYX — Client billing service
 * Interim payment applications to the client, and the certificates against
 * them. Wireframe v13, operations.html · payment-apps / pa-detail-approved.
 *
 * The mirror of SubcontractService, and behind the same role: the person who
 * certifies what a subcontractor is owed is the person who claims what the
 * project is owed, and splitting the two across roles would mean a commercial
 * manager could see one side of the same margin.
 */
using { konstryx.bil } from '../db/bil';

@requires: 'BudgetController'
service BillingService @(path:'/billing') {

  /**
   * The applications, newest first on the screen.
   *
   * Draft-enabled because an application is measured over days and corrected
   * before it goes out: a claim is the contractor's working paper until it is
   * submitted, and a half-measured period must never be readable as one that
   * was claimed.
   */
  @odata.draft.enabled
  entity PaymentApplications as projection on bil.PaymentApplication {
    *,
    /**
     * The colours, on the service rather than in each screen's annotations.
     *
     * An application is red once it is past its due date and still uncertified
     * — that is money the project has earned and is not being paid — amber in
     * the week before, and neutral once a certificate answers it. Repeating
     * this in an annotation is how a worklist and a detail page come to
     * disagree about which claims are late.
     */
    case
      when approvedGross is not null then 0
      when dueOn is null             then 0
      when dueOn <  $now             then 1
      else                                2
    end as dueCriticality : Integer,
  };

  /**
   * The measured lines, readable on their own as well as under the
   * application, because "everything ever claimed for this bill item" is a
   * question asked down the chain rather than within one period.
   *
   * Writable here as well as through the application's draft: a surveyor
   * remeasuring one item should not have to open and re-activate the whole
   * claim to correct a single quantity.
   */
  entity PaymentApplicationLines as projection on bil.PaymentApplicationLine;

  /**
   * The certificate, its own draft root rather than part of the application.
   *
   * It is issued by whoever certifies and not by whoever claimed, so it is
   * created, edited and activated on its own. Its per-line reasoning is a
   * composition of it and is edited inside its draft.
   */
  @odata.draft.enabled
  entity PaymentCertificates as projection on bil.PaymentCertificate;

  entity CertAdjustments as projection on bil.CertAdjustment;
}
