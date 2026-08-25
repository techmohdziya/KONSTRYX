/**
 * KONSTRYX — Admin & Platform service
 * Group/company setup, role-collection mapping, mdg promotion queue, sync config.
 * Restricted to platform administrators / master-data stewards.
 */
using { konstryx.admin } from '../db/admin';
using { konstryx.int } from '../db/int';
using { konstryx.fin } from '../db/fin';

@requires: 'Admin'
service AdminService @(path:'/admin') {
  entity CompanyGroups      as projection on admin.CompanyGroup;
  entity Companies          as projection on admin.Company;
  entity RoleCollections    as projection on admin.RoleCollectionMap;
  entity UserAccess         as projection on admin.UserCompanyAccess;
  entity SyncConfigs        as projection on admin.S4SyncConfig;

  /**
   * Exchange rates, maintained here because they are group financial
   * configuration rather than project data — one table serves every company,
   * every project and every report.
   */
  entity ExchangeRates      as projection on fin.ExchangeRate;

  /**
   * Converts an amount, and says which rate it used.
   *
   * Exposed as an action rather than left as an internal helper because every
   * screen that shows a converted figure has to be able to state its rate, and
   * a number whose rate nobody can name cannot be reconciled against anyone
   * else's. asOf defaults to today; rateType defaults to SPOT.
   */
  action convert(
    amount    : Decimal(15,2),
    fromCcy   : String(3),
    toCcy     : String(3),
    rateType  : String(10),
    asOf      : Date
  ) returns {
    amount    : Decimal(15,2);
    ccy       : String(3);
    rate      : Decimal(15,6);
    rateType  : String(10);
    validFrom : Date;
    source    : String(60);
  };

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

  /**
   * Reads master data from S/4 into the KONSTRYX mirrors: products into
   * Material, suppliers into Vendor.
   *
   * Which feeds run, and against which service, comes from SyncConfigs. With
   * no inbound configuration the defaults are used and the report says which
   * were applied. Existing rows are refreshed rather than skipped - S/4 is the
   * author of a mirror, so there is no local edit to preserve.
   */
  action syncMastersFromS4() returns LargeString;
}
