/**
 * KONSTRYX — Master Data service
 * Resource hierarchy, CBS library, rates, productivity/consumption norms,
 * templates, vendor & material mirrors. Stewarded master data.
 */
using { konstryx.master } from '../db/master';

@requires: 'MasterDataSteward'
service MasterDataService @(path:'/masterdata') {
  @odata.draft.enabled
  entity Resources         as projection on master.ResourceNode;
  @odata.draft.enabled
  entity CBSLibrary        as projection on master.CBSNode;
  @odata.draft.enabled
  entity ProjectTemplates  as projection on master.ProjectTemplate;

  entity ProductivityRates as projection on master.ProductivityRate;
  entity ConsumptionRates  as projection on master.ConsumptionRate;
  entity Rates             as projection on master.RateMaster;

  // S/4 mirrors — read-only in Konstryx
  @readonly entity Vendors    as projection on master.Vendor;
  @readonly entity Materials  as projection on master.Material;
}
