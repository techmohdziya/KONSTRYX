/**
 * KONSTRYX — Budget service
 * BOQ->budget conversion, baseline lock, availability & spend control,
 * mobilization auth, approvals.
 */
using { konstryx.bud } from '../db/bud';

@requires: 'BudgetController'
service BudgetService @(path:'/budget') {
  @odata.draft.enabled
  entity Budgets           as projection on bud.Budget
    actions {
      action submit();
      action approve();
      action baseline();
      action lock();
    };
  entity BudgetLines       as projection on bud.BudgetLine;
  entity MobilizationAuths as projection on bud.MobilizationAuth;
  entity PreBaselineSpend  as projection on bud.PreBaselineSpend;
  @readonly entity Approvals       as projection on bud.BudgetApproval;
  @readonly entity AvailabilityLog as projection on bud.AvailabilityLog;
}
