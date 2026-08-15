/**
 * KONSTRYX — Master Data service
 * Resource hierarchy, CBS library, rates, productivity/consumption norms,
 * templates, vendor & material mirrors. Stewarded master data.
 */
using { konstryx.master } from '../db/master';
using { konstryx.admin } from '../db/admin';

@requires: 'MasterDataSteward'
service MasterDataService @(path:'/masterdata') {

  /**
   * Hybrid scoped masters. A COMPANY-scoped record belongs to one legal entity
   * and is invisible to the others; a GROUP-scoped record is shared across the
   * group. Local records are promoted to group scope through the steward
   * queue rather than by editing the scope directly — promotion is a decision
   * with an owner and an audit trail, not a field update.
   */
  @odata.draft.enabled
  entity Resources         as projection on master.ResourceNode
    actions {
      action requestPromotion(reason : String(500)) returns String;
    };

  @odata.draft.enabled
  entity CBSLibrary        as projection on master.CBSNode
    actions {
      action requestPromotion(reason : String(500)) returns String;
    };

  /**
   * A template is a construction type plus the CBS structure and default
   * resources that go with it. Instantiating copies that structure into a
   * project rather than referencing it, so a later change to the library does
   * not silently reshape a project already being costed.
   */
  @odata.draft.enabled
  entity ProjectTemplates  as projection on master.ProjectTemplate
    actions {
      action instantiate(projectCode : String(24)) returns String;
    };

  entity TemplateResources as projection on master.ProjectTemplateResource;

  /**
   * Rates and norms are draft-enabled for the same reason the masters are: a
   * rate is entered against a resource, a basis, a currency and a date, and a
   * half-entered one must not be visible to anyone costing a project.
   */
  @odata.draft.enabled
  entity ProductivityRates as projection on master.ProductivityRate;

  @odata.draft.enabled
  entity ConsumptionRates  as projection on master.ConsumptionRate;

  @odata.draft.enabled
  entity Rates as projection on master.RateMaster;

  /**
   * Which rate actually applies on a given day.
   *
   * Effective dating is only worth having if something resolves it. A resource
   * accumulates rate revisions over years, and every consumer - a budget, a
   * reservation, a variation - needs the one in force on its own date, not the
   * newest row. Answering that in one place stops each module inventing its own
   * interpretation of "current".
   */
  function rateOn(resourceCode : String(40), onDate : Date, companyCode : String(10))
    returns {
      resourceCode  : String(40);
      rateValue     : Decimal(15,2);
      netRate       : Decimal(15,2);
      basis         : String(10);
      currency      : String(3);
      effectiveFrom : Date;
      scope         : String(10);
      source        : String(120);
    };

  // S/4 mirrors — read-only in Konstryx
  @readonly entity Vendors    as projection on master.Vendor;
  @readonly entity Materials  as projection on master.Material;

  /**
   * The steward queue. Approving promotes the referenced master to GROUP scope
   * and clears its owning company; the request is kept as the record of who
   * decided and why.
   *
   * It sits on this service rather than AdminService because the judgement —
   * should this master be shared across every company — belongs to the master
   * data steward, not to a platform administrator.
   */
  @cds.redirection.target
  entity PromotionRequests as projection on admin.PromotionRequest
    actions {
      action approve(comment : String(500)) returns String;
      action reject(comment : String(500))  returns String;
    };
}
