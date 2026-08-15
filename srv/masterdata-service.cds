/**
 * KONSTRYX — Master Data service
 * Resource hierarchy, CBS library, rates, productivity/consumption norms,
 * templates, vendor & material mirrors. Stewarded master data.
 */
using { konstryx.master } from '../db/master';

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

  @odata.draft.enabled
  entity ProjectTemplates  as projection on master.ProjectTemplate;

  entity ProductivityRates as projection on master.ProductivityRate;
  entity ConsumptionRates  as projection on master.ConsumptionRate;
  entity Rates             as projection on master.RateMaster;

  // S/4 mirrors — read-only in Konstryx
  @readonly entity Vendors    as projection on master.Vendor;
  @readonly entity Materials  as projection on master.Material;
}
