/**
 * KONSTRYX — konstryx.ins (Data Model Spec §8)
 * Insight: cost-revenue snapshots (EVM partial for MVP).
 */
namespace konstryx.ins;

using { cuid, managed } from '@sap/cds/common';
using { konstryx.prj } from './prj';

entity CostRevenueSnapshot : cuid, managed {
  project     : Association to prj.Project;
  period      : String(7);       // YYYY-MM
  budget      : Decimal(15,2);
  committed   : Decimal(15,2);
  encumbered  : Decimal(15,2);
  actual      : Decimal(15,2);
  revenue     : Decimal(15,2);   // billedToDate
  earnedValue : Decimal(15,2);
  eac         : Decimal(15,2);
}
