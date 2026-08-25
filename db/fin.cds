/**
 * KONSTRYX — konstryx.fin
 * The financial framework every time-phased and multi-currency figure rests on.
 *
 * Currency codes were already on the entities that need them — a project, a
 * company, a rate — and nothing converted between them. That is invisible while
 * a group trades in one currency and wrong the moment it does not: a
 * subcontract in euros and a budget in dirhams were being compared as bare
 * numbers, and an approval band carried a currency that no code read.
 */
namespace konstryx.fin;

using { cuid, managed, Currency } from '@sap/cds/common';

/**
 * One rate between two currencies, of one kind, from one date.
 *
 * The kinds are not interchangeable and the enum exists to stop them being
 * substituted for one another. A contract rate is agreed at award and prices
 * revenue for the life of the contract. A budget rate is fixed at baseline and
 * prices cost, so that a currency movement cannot retroactively rewrite a
 * margin that was already reported. Spot and average price actuals and
 * reporting, and move constantly.
 *
 * Using the wrong one is not a rounding difference — it is the difference
 * between a project that lost money and a project whose currency moved.
 */
entity ExchangeRate : cuid, managed {
  fromCcy   : Currency;
  toCcy     : Currency;
  rateType  : String(10) enum { CONTRACT; BUDGET; SPOT; AVERAGE; } default 'SPOT';
  /** The rate applies from this date until superseded by a later one. */
  validFrom : Date;
  /**
   * Six decimal places. Four is not enough for the currencies this product
   * actually meets: an INR/AED rate at four places carries a rounding error of
   * roughly one part in two hundred, which on a labour subcontract is real money.
   */
  rate      : Decimal(15,6);
  /** Where the number came from — S/4 TCURR, a central bank, the contract. */
  source    : String(60);
}
