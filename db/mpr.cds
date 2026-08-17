/**
 * KONSTRYX — konstryx.mpr
 * Manpower (MPR) vertical extension of the request line.
 *
 * Same architecture as konstryx.eq (2026-08-15): vertical-specific attributes
 * hang off the spine as a per-vertical extension rather than being denormalised
 * onto wf.ResourceRequestLine. An equipment line is instances over a mob/demob
 * window; a manpower line is heads in a crew, sourced either from own payroll or
 * from a labour subcontractor, working hours that have to be logged daily. One
 * flat line entity carrying the union of both would be mostly null in every row.
 *
 * The dependency points mpr -> wf. The reverse association is declared here by
 * extension so the spine never has to know about its verticals.
 */
namespace konstryx.mpr;

using { cuid, managed } from '@sap/cds/common';
using { konstryx.wf } from './wf';
using { konstryx.prj } from './prj';
using { konstryx.master } from './master';

entity ManpowerRequestLine : cuid {
  line          : Association to wf.ResourceRequestLine;

  /** Heads requested. The spine's qty is hours; this is people. */
  heads         : Integer;
  tradeGrade    : String(40);                  // MP-CIV-STF-SK-G1 grade label

  /**
   * Own payroll or labour subcontract. This is the decision the advisory step
   * records, as executed — a line can be re-sourced by variation without
   * re-opening ADV, which is why it lives here and not on the decision.
   */
  sourceType    : String enum { OWN; LSC; };
  vendor        : Association to master.Vendor; // set when sourceType = LSC

  /** Gang the heads work in. Null for a floating assignment. */
  crewId        : String(20);
  crewLead      : String(120);

  mobDate       : Date;
  demobDate     : Date;
  durationDays  : Integer;

  /**
   * All-in cost of one head for one day — wage plus the overheads a site
   * actually carries (accommodation, transport, supervision). The reservation
   * encumbers heads x days x this, so it is the number the commercial team
   * argues about and it has to be visible rather than derived silently.
   */
  ratePerHeadDay : Decimal(15,2);

  /** HSE induction, permits and skill assessment, as one readable state. */
  inductionState : String(60);

  timesheets    : Composition of many TimesheetEntry on timesheets.manpowerLine = $self;
}

/**
 * One day of one manpower line. The daily log is what turns a reservation into
 * actual cost: heads present against heads reserved is the absence signal, and
 * regular against overtime hours is what posts to the WBS.
 *
 * Kept per line per day rather than per employee per day on purpose. The crew is
 * the unit a site foreman signs for, and per-employee attendance belongs with
 * the employee master in SuccessFactors, not in the project's cost record.
 */
entity TimesheetEntry : cuid, managed {
  manpowerLine  : Association to ManpowerRequestLine;
  workDate      : Date;

  headsPresent  : Integer;
  regularHrs    : Decimal(9,2);
  otHrs         : Decimal(9,2);

  /** Where the hours land. Both are needed: WBS carries the S/4 posting, CBS the cost nature. */
  wbs           : Association to prj.WBSElement;
  cbs           : Association to prj.CBSInstance;
  activity      : String(40);                  // PRJ-001.02.30.STR-RBR

  costAmount    : Decimal(15,2);
  /** Draft -> Signed -> Posted. Only a signed day may reach S/4. */
  logStatus     : String(20) default 'Draft';
  signedBy      : String(120);
}

// Back-association so a line and its manpower detail come back in one $expand.
extend wf.ResourceRequestLine with {
  manpower : Association to ManpowerRequestLine on manpower.line = $self;
}
