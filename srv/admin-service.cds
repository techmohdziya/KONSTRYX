/**
 * KONSTRYX — Admin & Platform service
 * Group/company setup, role-collection mapping, mdg promotion queue, sync config.
 * Restricted to platform administrators / master-data stewards.
 */
using { konstryx.admin } from '../db/admin';
using { konstryx.int } from '../db/int';

@requires: 'Admin'
service AdminService @(path:'/admin') {
  entity CompanyGroups      as projection on admin.CompanyGroup;
  entity Companies          as projection on admin.Company;
  entity RoleCollections    as projection on admin.RoleCollectionMap;
  entity UserAccess         as projection on admin.UserCompanyAccess;
  entity SyncConfigs        as projection on admin.S4SyncConfig;

  /**
   * Visible here for platform oversight, but the decision lives on
   * MasterDataService: the person who judges whether a master should be shared
   * group-wide is the master data steward, not the platform administrator.
   */
  @readonly entity PromotionRequests as projection on admin.PromotionRequest;

  // Integration monitoring (read-only)
  @readonly entity SyncRuns   as projection on int.SyncRun;
  @readonly entity ErrorQueue as projection on int.ErrorQueueItem;

  // -- organizational values, read from the connected S/4 -------------------

  /**
   * Plants, purchasing organizations, profit centres, cost centres and project
   * profiles as they exist in this tenant's own S/4 system. Read-only, like
   * every S/4 mirror: correcting a plant means correcting it in S/4.
   */
  @readonly entity S4OrgValues as projection on admin.S4OrgValue;

  /**
   * Re-reads the organizational values from S/4 through the ITS_S4 destination
   * and fills each company from what it finds.
   *
   * These values cannot be shipped in a content pack. They are configuration
   * of the customer's own system, so no value is right for every tenant — and
   * a seeded guess is not detectably wrong until S/4 refuses a live document,
   * which is exactly how "Profit Center 10001000 does not exist" reached a
   * real push. Reading them is the only way the same build is correct on every
   * subscriber.
   *
   * Safe to run at any time and safe to repeat. It writes only the mirror and
   * the company org fields, and it leaves a field that already holds a value
   * S/4 recognises exactly as it is. The return value is a report: what
   * answered, what was set, and what still needs a human choice.
   */
  action syncOrgFromS4() returns LargeString;
}
