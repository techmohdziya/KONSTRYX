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
using { konstryx.admin } from './admin';

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


/**
 * The period grid every time-phased figure is bucketed into.
 *
 * Cashflow forecasting, EVM's planned and earned value, and a payment
 * certificate's cut-off all need to agree on what a period is. Without one
 * definition each of them invents its own and they disagree by a few days,
 * which is exactly enough for two reports on the same month to differ.
 *
 * The certificate cut-off follows this calendar rather than the contract
 * (D-2, 2026-08-26), so there is one grid per company and not a second,
 * contract-defined one beside it.
 */
entity FiscalCalendar : cuid, managed {
  code         : String(20);
  name         : String(120);
  /** Null applies the calendar group-wide. */
  company      : Association to admin.Company;
  variant      : String(20) enum { CALENDAR_MONTH; FOUR_FOUR_FIVE; WEEKLY; } default 'CALENDAR_MONTH';
  /** The month the fiscal year opens on, 1-12. */
  startMonth   : Integer default 1;
  weekStartsOn : Integer default 1;                  // 1 = Monday
  isDefault    : Boolean default false;
  periods      : Composition of many FiscalPeriod on periods.calendar = $self;
}

entity FiscalPeriod : cuid, managed {
  calendar     : Association to FiscalCalendar;
  fiscalYear   : Integer;
  periodNo     : Integer;                            // 1-12, or 13 for adjustment
  name         : String(40);                         // FY26 P03 - Mar 2026
  startDate    : Date;
  endDate      : Date;
  /**
   * CLOSED refuses a posting outright. SOFT_CLOSED accepts one with a stated
   * reason, which is what month-end actually needs: a site goes on signing
   * days while commercial is still reconciling, and a period that only knows
   * open and shut forces someone to choose between a wrong date and a lost day.
   */
  status       : String(12) enum { OPEN; SOFT_CLOSED; CLOSED; } default 'OPEN';
  isAdjustment : Boolean default false;
}
