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

  @odata.draft.enabled
  entity PromotionRequests  as projection on admin.PromotionRequest;

  // Integration monitoring (read-only)
  @readonly entity SyncRuns   as projection on int.SyncRun;
  @readonly entity ErrorQueue as projection on int.ErrorQueueItem;
}
