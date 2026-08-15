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

  entity ProductivityRates as projection on master.ProductivityRate;
  entity ConsumptionRates  as projection on master.ConsumptionRate;
  entity Rates             as projection on master.RateMaster;

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
