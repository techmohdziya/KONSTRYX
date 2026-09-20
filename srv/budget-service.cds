/**
 * KONSTRYX — Budget service
 * BOQ->budget conversion, baseline lock, availability & spend control,
 * mobilization auth, approvals.
 */
using { konstryx.bud } from '../db/bud';
using { konstryx.prj } from '../db/prj';

@requires: 'BudgetController'
service BudgetService @(path:'/budget') {
  @odata.draft.enabled
  entity Budgets           as projection on bud.Budget
    actions {
      /**
       * Builds the lines from the project's priced resource build-up, at the
       * key the control record is kept on: WBS x CBS x bill item x cost
       * nature. The build-up says what a bill line costs and the allocation
       * says who builds it and what absorbs it, so the two together place
       * every dirham on an element with dates rather than on a cost heading
       * alone. Refuses a build-up with unpriced resources: a budget with a
       * hole where a rate should be is not conservative, it is wrong by the
       * size of the hole.
       */
      action generateLines() returns String;

      /**
       * Spreads every line across the periods its work actually falls in.
       *
       * Three things were missing for the same reason and this is the reason:
       * planned value, the schedule performance index, and any cashflow curve
       * at all. A budget line knew its amount and its CBS, and nothing said
       * which month the amount was meant to go out in.
       *
       * A line is phased from the programme where its CBS can be traced to
       * dated activities through the cost mapping, and spread evenly across
       * the project's own dates where it cannot. The two are told apart on
       * every phase, because a curve built from even spreads is a straight
       * line and reads exactly like a forecast.
       *
       * Safe to repeat: re-phasing replaces the set rather than adding to it.
       */
      action phaseBudget() returns String;

      /** Hands the budget to the approval framework at its total value. */
      action submit() returns String;

      /**
       * Baselines an approved budget. From here on a line's amount moves only
       * through ledger entries — SHIFT, RISK_TRANSFER or VARIATION — never by
       * editing the number.
       */
      action baseline() returns String;

      /**
       * Moves budget between two lines, zero-sum, as one paired SHIFT. The
       * commonest movement on a live project, and the reason the ledger
       * exists: after ten of these, "why is waterproofing at 1.4m" still has
       * an answer.
       */
      action shift(fromCBS : String(40), toCBS : String(40),
                   fromCategory : String(10), toCategory : String(10),
                   fromItem : String(20), toItem : String(20),
                   fromWBS : String(40), toWBS : String(40),
                   amount : Decimal(15,2), reason : String(500)) returns String;

      /**
       * Moves budget from a risk/contingency line to the line absorbing a
       * realized risk. Zero-sum like a shift — the budget total is unchanged
       * — but tagged RISK_TRANSFER and keyed to the risk reference rather
       * than the budget document, so a year from now "why did this line
       * move" names the risk, not just "a shift happened".
       */
      action riskTransfer(fromCBS : String(40), toCBS : String(40),
                           fromCategory : String(10), toCategory : String(10),
                           fromItem : String(20), toItem : String(20),
                           fromWBS : String(40), toWBS : String(40),
                           amount : Decimal(15,2), riskReference : String(40),
                           reason : String(500)) returns String;

      /**
       * A client-approved scope change — the one ledger category that is not
       * zero-sum, because it genuinely adds (or omits) budget from outside
       * the original envelope. Keyed to the variation order reference; moves
       * both the line and the budget's own total.
       */
      action variation(cbs : String(40), category : String(10),
                        boqItem : String(20), wbs : String(40),
                        amount : Decimal(15,2),
                        variationRef : String(40),
                        reason : String(500)) returns String;

      /**
       * Pulls live encumbrance into the control record: each line's encumbered
       * figure becomes the sum of open reservations whose request lines charge
       * its CBS, and available is recomputed. Committed and actual stay S/4's
       * to fill (Q-09) and are never invented here.
       */
      action refreshControl() returns String;
    };
  /** When each line is expected to be spent. Derived by phaseBudget. */
  @readonly entity BudgetPhases as projection on bud.BudgetPhase;

  entity BudgetLines       as projection on bud.BudgetLine;

  /**
   * What a budget line is controlled against, readable and selectable.
   *
   * A value help resolves inside the service it is annotated in, so without
   * these three a line's element, cost node and bill item are stored UUIDs and
   * displayed as UUIDs — the three keys the budget exists to be read by would
   * be the three columns nobody could read.
   *
   * Read-only: they are maintained on ProjectService, and a second place to
   * edit a WBS element is a second answer to what the structure is.
   */
  @readonly entity WBSElements as projection on prj.WBSElement;
  @readonly entity ProjectCBS  as projection on prj.CBSInstance;
  @readonly entity BOQItems    as projection on prj.BOQItem;
  @readonly entity LedgerEntries as projection on bud.BudgetLedgerEntry;
  entity MobilizationAuths as projection on bud.MobilizationAuth;
  entity PreBaselineSpend  as projection on bud.PreBaselineSpend;
  @readonly entity Approvals       as projection on bud.BudgetApproval;
  @readonly entity AvailabilityLog as projection on bud.AvailabilityLog;
}
