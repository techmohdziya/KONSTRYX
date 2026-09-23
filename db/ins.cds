/**
 * KONSTRYX — konstryx.ins (Data Model Spec §8)
 * Insight: Cost Value Reconciliation and Earned Value, per project per period.
 */
namespace konstryx.ins;

using { cuid, managed, Currency } from '@sap/cds/common';
using { konstryx.prj } from './prj';
using { konstryx.fin } from './fin';

/**
 * What a project is worth, what it has cost, and what it will cost — measured
 * once per period and kept.
 *
 * Kept rather than computed on demand, for the same reason productivity is: a
 * margin on its own says far less than the same margin falling for three
 * months, and a figure recomputed later can never be compared with what was
 * reported at the time because the quantities and hours behind it have moved.
 * A board pack that cannot be reproduced is a board pack nobody can defend.
 *
 * The period is a fiscal period rather than a YYYY-MM string, which is what it
 * used to be. Ziya ruled on 2026-08-26 that the IPC follows the fiscal
 * calendar, so a certificate, a cashflow bucket and this report all end their
 * month on the same day — the only way any two of them can be reconciled
 * against the third.
 */
entity ProjectPeriodReport : cuid, managed {
  project        : Association to prj.Project;
  period         : Association to fin.FiscalPeriod;
  /** Denormalised so a list reads without a join. */
  periodName     : String(40);
  takenAt        : Timestamp;

  // ------------------------------------------------------ what it is worth

  /** The priced bills, as contracted. */
  contractValue  : Decimal(15,2);
  /**
   * Approved variations, and only approved ones.
   *
   * A submitted claim is a negotiating position; counting it would make this
   * figure — and the margin below it — depend on the client agreeing something
   * they have not yet agreed. What is claimed and outstanding goes in the note
   * instead, so a reader can see how much of the picture is still being argued.
   */
  variations     : Decimal(15,2);
  adjustedValue  : Decimal(15,2);

  // --------------------------------------------------------- earned value

  /**
   * Planned value: what the programme said would have been spent by now.
   *
   * The phased budget, summed over every period that has already begun. It was
   * null for the whole life of this report because nothing said which month a
   * budget line belonged to; phaseBudget supplies that, and this and the two
   * indices below follow from it.
   *
   * Still null where a project's budget has not been phased. An approximation
   * dressed as a measurement would be worse than an empty cell, because a
   * schedule index computed from a guess looks exactly like one computed from
   * a plan.
   */
  plannedValue   : Decimal(15,2);
  /** Measured work at contract rates: the value of what has been built. */
  earnedValue    : Decimal(15,2);
  /** What that work has actually cost. */
  actualCost     : Decimal(15,2);

  /**
   * The same measured work priced at what it was budgeted to cost, rather
   * than at what it was sold for.
   *
   * Earned value is revenue and actual cost is cost, so an index of one
   * against the other is an index of the margin as much as of performance -
   * on a job sold at a 20 % margin it reads 1.25 before anything has gone
   * either right or wrong. This is the like-for-like figure: budgeted cost of
   * the work performed, against what that work actually cost, which is the
   * comparison that says whether the job is building to its estimate.
   *
   * Null where the bill's items are not costed - a budget line carries a BOQ
   * item only where the cost mapping gave it one, and work whose cost was
   * never estimated cannot have earned any of it.
   */
  earnedCost     : Decimal(15,2);

  costVariance     : Decimal(15,2);   // EV - AC
  scheduleVariance : Decimal(15,2);   // EV - PV; null while PV is
  /** EV / AC. Above 1 is earning more than it spends. */
  cpi            : Decimal(9,4);
  /**
   * Earned cost / actual cost: the index with the margin taken out of it.
   *
   * Below 1 means the work performed cost more than it was budgeted to. This
   * is the number to argue about on a cost report; cpi above is the one to
   * quote on a revenue one, and a reader given only the first would read the
   * contract's margin as the site's performance.
   */
  costCPI        : Decimal(9,4);
  /** EV / PV. Null while PV is. */
  spi            : Decimal(9,4);
  /**
   * Earned cost / planned value: the schedule index with the margin out of it.
   *
   * spi above divides revenue-priced earned value by a cost-priced planned
   * value, so on any job sold at a margin it reads high before anything has
   * happened - and on one whose budget covers only part of the priced scope it
   * reads absurdly high. This is the like-for-like pair: budgeted cost of the
   * work performed against the budgeted cost of the work planned, which is the
   * comparison that says whether the job is where its own budget expected it.
   */
  costSPI        : Decimal(9,4);

  // ----------------------------------------------------- cost to complete

  costToDate     : Decimal(15,2);
  /**
   * The two halves of cost to date, kept apart because they are written by
   * different events and a reader asked to act on the total needs to know
   * which one moved. Signed labour is the daily logs; stock issued is
   * material drawn from a store, whose goods issue is the cost. What was
   * bought and billed, and what was subcontracted and certified, are not
   * here — they reach actual cost from the invoices and the certificates
   * directly, without passing through a reservation line.
   */
  signedLabourCost : Decimal(15,2);
  stockIssuedCost  : Decimal(15,2);
  /**
   * Estimated cost to complete, priced at what the work has actually cost so
   * far rather than at what it was budgeted to cost. The two differ, and the
   * difference is the finding.
   */
  costToComplete : Decimal(15,2);
  forecastCost   : Decimal(15,2);     // cost to date + cost to complete
  /** Adjusted value less forecast cost: the projected profit or loss. */
  forecastMargin : Decimal(15,2);
  forecastMarginPct : Decimal(9,2);
  /** How much of the contract has been measured as built. */
  percentComplete : Decimal(5,2);

  // ------------------------------------------------ both currencies (D-4)

  /** The company's own currency. Every figure above is in it. */
  companyCcy     : Currency;
  /** The group's presentation currency. */
  groupCcy       : Currency;
  /**
   * Which rate type converted them, read from the group's configuration
   * rather than fixed. A group reporting at the average rate for the period
   * and one reporting at the closing rate are both right, and a figure that
   * does not say which it used cannot be reconciled against anyone else's.
   */
  rateType       : String(10);
  rateApplied    : Decimal(15,6);

  adjustedValueGroup  : Decimal(15,2);
  forecastCostGroup   : Decimal(15,2);
  forecastMarginGroup : Decimal(15,2);

  /**
   * What could not be computed, and why. Never left silently empty.
   *
   * Long enough to hold all of it. A report carries a note for every figure
   * it could not measure and every one it measured with a caveat, and at 255
   * the field held the first two and cut the second mid-word, so the caveats
   * a reader most needed were the ones that never arrived.
   */
  note           : String(2000);
}

/**
 * One project on one page: what it is worth, what it may spend, what it has
 * spent, where the programme has got to, and what is waiting on someone.
 *
 * The project object page already held all of this and held it across seven
 * facets, which answers "show me the bills" and does not answer "how is this
 * project doing". Nothing here is new information — every figure is derived
 * from the bills, the budget, the reservations, the daily logs, the programme
 * and the last reconciliation.
 *
 * Recomputed on every read rather than written by an action. A stored overview
 * is a number that was true once, and the one thing a summary page must never
 * do is disagree with the screen a reader opens next to check it. The cost of
 * recomputing is one pass over a project's own rows; the cost of being stale
 * is that nobody trusts the page again after the first time it is wrong.
 */
entity ProjectOverview : cuid {
  project          : Association to prj.Project;
  code             : String(24);
  name             : String(150);
  stage            : String(40);
  companyName      : String(150);
  ccy              : Currency;
  startDate        : Date;
  endDate          : Date;
  refreshedAt      : Timestamp;

  // ------------------------------------------------------------- the money
  /** The contract, as signed. */
  contractValue    : Decimal(15,2);
  /** The priced bills. Different from the contract by preliminaries and
   *  provisional sums, and a page that showed only one would hide the gap. */
  boqValue         : Decimal(15,2);
  budgetTotal      : Decimal(15,2);
  committed        : Decimal(15,2);
  encumbered       : Decimal(15,2);
  actual           : Decimal(15,2);
  available        : Decimal(15,2);
  /** How much of the budget is spoken for, however it was spoken for. */
  budgetUsedPct    : Decimal(5,2);

  // --------------------------------------------------------- how it is doing
  earnedValue      : Decimal(15,2);
  actualCost       : Decimal(15,2);
  cpi              : Decimal(9,4);
  percentComplete  : Decimal(5,2);
  forecastMargin   : Decimal(15,2);
  forecastMarginPct: Decimal(9,2);
  /** The period the two figures above were measured in, so a reader knows how
   *  old they are without opening the report. */
  measuredPeriod   : String(40);

  // ------------------------------------------------------------ the programme
  activitiesTotal  : Integer;
  activitiesDone   : Integer;
  activitiesCritical : Integer;
  /** Where the critical path says the job finishes. */
  scheduleFinish   : Date;
  /** Days between that and the contract finish. Negative is early. */
  slipDays         : Integer;

  // ------------------------------------------------------ what needs a human
  openRequests     : Integer;
  unsignedDays     : Integer;
  requisitionsUnsent : Integer;
  linesOverBudget  : Integer;
  certifiedNet     : Decimal(15,2);

  /**
   * What this page could not compute, and why. A blank cell that does not say
   * why is read as a bug; a project with no budget and a project whose budget
   * is zero look identical without it.
   */
  note             : String(255);
}

/**
 * What a project is expected to spend each month, and what it has spent.
 *
 * Cost out only. A cashflow with a revenue line would be the more useful
 * report, and KONSTRYX has nothing to build one from: client payment
 * applications are not modelled, so every "money in" figure would be an
 * invention. The row says so rather than showing a blank column that reads as
 * a project earning nothing.
 *
 * Planned comes from the phased budget, which is why phasing had to exist
 * first. Where a budget line could not be tied to dated work it is spread
 * evenly across the project, and the share of the curve that rests on that is
 * reported per row — a straight line drawn from envelopes is not a forecast,
 * and a reader cannot tell by looking.
 */
entity ProjectCashflow : cuid {
  project        : Association to prj.Project;
  period         : Association to fin.FiscalPeriod;
  periodName     : String(40);
  startDate      : Date;
  endDate        : Date;
  ccy            : Currency;

  /** Phased budget falling in this period. */
  plannedOut     : Decimal(15,2);
  plannedOutCum  : Decimal(15,2);
  /** Signed labour and posted cost in this period. */
  actualOut      : Decimal(15,2);
  actualOutCum   : Decimal(15,2);
  /** Planned less actual. Positive is under the curve. */
  variance       : Decimal(15,2);
  varianceCum    : Decimal(15,2);
  /** How much of this period's plan rests on a straight-line spread. */
  envelopePct    : Decimal(5,2);
  note           : String(255);
}


/**
 * Where the job is being built today, one row per open front.
 *
 * Everything else in this namespace answers a question about a month. This
 * one answers the question a project manager actually opens a screen to ask at
 * seven in the morning: which fronts are open, who is standing on them, and
 * which of them had nobody yesterday.
 *
 * A front is an activity that today falls inside. Not a location and not a WBS
 * element: a location has no dates and a WBS element has no state, and the
 * thing a site runs on is a piece of work with a start, a finish and a gang.
 * The location, the crew and the hours hang off it.
 *
 * Derived on read, and never kept. The period report is kept because a margin
 * has to be reproducible months later; this is the opposite kind of number —
 * it is only ever asked about now, and a stored copy of "today" is wrong by
 * tomorrow morning without anything saying so.
 */
entity WorkFront : cuid {
  project        : Association to prj.Project;
  projectCode    : String(24);
  projectName    : String(150);
  /** The day this was read for. On the screen it is always today. */
  onDate         : Date;
  refreshedAt    : Timestamp;

  activity       : Association to prj.Activity;
  activityCode   : String(40);
  activityName   : String(255);
  wbs            : Association to prj.WBSElement;
  wbsCode        : String(40);
  wbsName        : String(255);
  isCritical     : Boolean;

  // ------------------------------------------------------------ where it sits
  /** The dates the network settled on, falling back to the agreed programme. */
  startDate      : Date;
  finishDate     : Date;
  durationDays   : Integer;
  /** Days from the start to today, and from today to the finish. Negative
   *  days remaining is an activity that should already have finished. */
  daysElapsed    : Integer;
  daysRemaining  : Integer;
  totalFloat     : Integer;

  // ---------------------------------------------------------- how it is going
  percentDone    : Decimal(5,2);
  /**
   * Where the activity would be if it had run evenly from its start date.
   *
   * Not a target and not a forecast — a straight line through the duration.
   * It is here because "40% done" means nothing on its own and everything
   * beside "and it should be at 75%".
   */
  expectedPct    : Decimal(5,2);
  /** Done less expected. Negative is behind. */
  driftPct       : Decimal(5,2);

  // ------------------------------------------------------------ who is on it
  headsToday     : Integer;
  hoursToday     : Decimal(9,2);
  headsWeek      : Integer;
  hoursWeek      : Decimal(9,2);
  /** The most recent day anyone signed hours against this element. Blank
   *  means nobody ever has, which is a different thing from nobody today. */
  lastWorkedOn   : Date;
  daysSinceWorked : Integer;
  /** Where the crew were, when the signed days name a place. */
  locations      : String(255);

  // --------------------------------------------------------------- the verdict
  /**
   * OPEN        running, and somebody is on it
   * QUIET       running, and nobody has signed a day against it this week
   * STARTING    starts within the week and has not been started
   * OVERDUE     past its finish date and not complete
   * FINISHING   complete or all but, and still inside its dates
   */
  state          : String(12);
  /** 1 red, 2 amber, 3 green. Read by the renderer, not by a person. */
  stateCriticality : Integer;
  /** What the row could not work out, and why. */
  note           : String(255);
}
