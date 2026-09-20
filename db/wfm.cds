/**
 * KONSTRYX — konstryx.master, workforce.
 *
 * The working day, the calendar that interrupts it, and the people who turn
 * up. Kept apart from the resource hierarchy and the rate masters because
 * these answer a different question: not what a resource costs, but who is
 * available to be planned tomorrow and under what terms their hours are paid.
 */
namespace konstryx.master;

using { cuid, managed } from '@sap/cds/common';
using { konstryx.common } from './common';
using { konstryx.prj } from './prj';
using { konstryx.master } from './master';

/**
 * The working day and where overtime begins.
 *
 * S/4HANA Cloud Public Edition carries no shift master and no work-schedule
 * object — it accepts a flat row per person per date — so the pattern is
 * mastered here outright and pushes a generated calendar rather than mirroring
 * one.
 *
 * The duty day and the manday are different lengths and both are real: norms
 * are stated per 8-hour manday while rates and patterns run a 9.5-hour duty
 * day. Nothing reconciles them silently; a crew template has to choose.
 */
entity ShiftPattern : cuid, managed, common.scoped {
  code            : String(40);
  description     : String(255);
  /** The paid day. Hours beyond it are overtime, at the ladder below. */
  dutyHours       : Decimal(4,2) default 9.50;
  /** The day the productivity norms are written against. */
  mandayHours     : Decimal(4,2) default 8.00;
  breakMinutes    : Integer default 60;
  /**
   * A pattern that books no standard hours: the whole day is overtime. Used by
   * the holiday pattern, where a man who works is paid at the holiday step
   * from his first hour rather than after his ninth.
   */
  allHoursAreOT   : Boolean default false;
  calendar        : Association to HolidayCalendar;
  effectiveFrom   : Date;
  /**
   * The one ladder. Timesheet costing, the rate master, the crew rate and the
   * charge side all read this rather than each carrying a number of its own —
   * a multiplier is a commercial agreement, and four copies of it are four
   * chances to disagree.
   */
  overtimeSteps   : Composition of many OvertimeStep on overtimeSteps.pattern = $self;
}

/**
 * One rung of the overtime ladder.
 *
 * Cost and charge are separate multipliers on the same rung, not two versions
 * of one number: what an hour costs the company and what it bills the client
 * move independently.
 */
entity OvertimeStep : cuid {
  pattern      : Association to ShiftPattern;
  /** OT1 | NIGHT | RESTDAY | HOLIDAY | BEYOND12 | STANDBY */
  kind         : String(20);
  description  : String(120);
  costFactor   : Decimal(5,2);
  chargeFactor : Decimal(5,2);
  /** Hours into the day at which this rung starts, where that is what selects it. */
  fromHour     : Decimal(4,2);
  sequence     : Integer;
}

/**
 * A named list of dated non-working days, and nothing more.
 *
 * Deliberately not country-specific: the country is an attribute of a calendar,
 * not the shape of the master. One project shutdown and one continuous
 * operation with no holidays at all are calendars on the same footing as a
 * national one.
 */
entity HolidayCalendar : cuid, managed, common.scoped {
  code        : String(40);
  description : String(255);
  country     : String(3);
  region      : String(40);
  year        : Integer;
  entries     : Composition of many HolidayCalendarEntry on entries.calendar = $self;
}

/**
 * A dated entry on a calendar.
 *
 * Class and overtime treatment are separate because they answer different
 * questions: a client shutdown stops work without paying an uplift, while a
 * worked statutory holiday pays a premium. A day can be non-working and cheap,
 * or working and expensive.
 *
 * Fixed dates are known years ahead; lunar ones stay Provisional until
 * decreed, which is why the status is on the entry rather than on the calendar.
 */
entity HolidayCalendarEntry : cuid {
  calendar    : Association to HolidayCalendar;
  holidayDate : Date;
  description : String(120);
  /** STATUTORY | SHUTDOWN | RELIGIOUS | COMPANY */
  class       : String(20);
  /** PROVISIONAL | CONFIRMED */
  status      : String(20) default 'CONFIRMED';
  /** Which rung of the pattern's ladder a worked hour on this day takes. */
  otKind      : String(20);
  nonWorking  : Boolean default true;
}

/**
 * The construction trades, shared at group level.
 *
 * Availability is per company rather than per catalogue: most trades exist
 * everywhere, a few are private to one entity, and splitting the catalogue to
 * express that would give the same trade two codes.
 */
entity TradeCatalogue : cuid, managed, common.scoped {
  code             : String(40);
  description      : String(255);
  discipline       : String(60);
  /** Cards a man must hold to work this trade at all. A crew inherits these. */
  certificates     : Composition of many TradeCertificate on certificates.trade = $self;
  grades           : Composition of many TradeGrade on grades.trade = $self;
}

/** A grade within a trade. Trade x grade is what a rate is keyed on. */
entity TradeGrade : cuid {
  trade       : Association to TradeCatalogue;
  code        : String(20);
  description : String(120);
  sequence    : Integer;
}

entity TradeCertificate : cuid {
  trade       : Association to TradeCatalogue;
  code        : String(40);
  description : String(120);
  /** Without it the man may not be counted toward the crew's manning. */
  blocking    : Boolean default true;
}

/**
 * A worker on our own payroll.
 *
 * Three sources, and their precedence is not the obvious one. S/4HANA Cloud
 * Public Edition is not an HR system: it supplies company, cost centre and a
 * grading band, and never a trade, a shift, a certificate or a document.
 * Where SuccessFactors is not licensed, KONSTRYX is the employee master and
 * pushes the work agreement outward so that time can post at all — which is
 * why the outbound aspect is here rather than a mirror.
 *
 * Passport or Emirates ID is the duplicate key, and it is checked across
 * companies: the same man hired twice in the group is one man.
 */
entity Employee : cuid, managed, common.scoped, common.s4outbound {
  empNo           : String(20);
  fullName        : String(120);
  passportNo      : String(40);
  emiratesId      : String(40);
  nationality     : String(60);
  /** SF | ERP | MAN — where identity is mastered, not where it is used. */
  source          : String(10) default 'MAN';
  trade           : Association to TradeCatalogue;
  grade           : Association to TradeGrade;
  shiftPattern    : Association to ShiftPattern;
  calendar        : Association to HolidayCalendar;
  costCentre      : String(20);
  gradingBand     : String(20);
  joinedOn        : Date;
  leftOn          : Date;
  status          : String(20) default 'Active';
  documents       : Composition of many EmployeeDocument on documents.employee = $self;
}

/**
 * A document or certificate a worker carries, and the date it stops counting.
 *
 * Expiry is what makes this more than filing: an expired blocking certificate
 * takes the man out of his gang's manning without anybody recording an absence.
 */
entity EmployeeDocument : cuid {
  employee    : Association to Employee;
  code        : String(40);
  description : String(120);
  documentNo  : String(60);
  issuedOn    : Date;
  expiresOn   : Date;
  blocking    : Boolean default false;
}

/**
 * What a gang contains.
 *
 * Labour is planned, requested, mobilised and costed by the gang, but until a
 * gang has a composition nothing can price it or check the men on site against
 * the men the norm assumed. A norm that says "1 gang of 6 = 42 m3/day" names a
 * number and not the six.
 *
 * The crew rate is derived from the slots and never typed: it is the sum of
 * what the trades in it cost, and a typed rate would drift from them silently.
 */
entity CrewTemplate : cuid, managed, common.scoped {
  code                   : String(40);
  description            : String(255);
  /**
   * Which day the stated output is per: MANDAY_8H as the norms are written, or
   * DUTY_DAY as the rates and shift patterns run. The two are 19% apart and
   * this is the only object that touches both, so the choice is made here
   * rather than assumed by whoever reads the number.
   */
  outputBasis            : String(20) default 'MANDAY_8H';
  outputPerDay           : Decimal(15,3);
  outputUoM              : String(10);
  /** Below this the gang may not mobilise, however cheap it has become. */
  minimumManning         : Integer;
  substitutionAllowed    : Boolean default false;
  /** A working foreman counts toward output; a supervising one does not. */
  foremanCountsToOutput  : Boolean default false;
  /** Whether slots may be filled from own payroll and subcontract together. */
  mixedSourcingAllowed   : Boolean default true;
  /**
   * DERIVED from the slots at their trade x grade rates. Recomputed on every
   * write; an inbound value is ignored rather than trusted.
   */
  crewRatePerHr          : Decimal(15,2);
  slots                  : Composition of many CrewTemplateSlot on slots.template = $self;
}

/**
 * One position in a crew, by trade and grade rather than by name.
 *
 * The certificate requirement is derived: adding a slot whose trade demands a
 * card makes the whole crew demand it, and no gang on the template mans up
 * without one.
 */
entity CrewTemplateSlot : cuid {
  template   : Association to CrewTemplate;
  slotNo     : Integer;
  trade      : Association to TradeCatalogue;
  grade      : Association to TradeGrade;
  isForeman  : Boolean default false;
  /** Read from the rate master for this trade x grade, not keyed here. */
  ratePerHr  : Decimal(15,2);
}

/**
 * A gang actually on site: an instance of a template, manned from own payroll,
 * from subcontract, or from both.
 *
 * The number worth reading is the comparison against the template. An
 * under-manned gang costs less per hour than the template it came from, so a
 * cost report alone reads it as a saving while its output is down — the rate
 * variance and the productivity variance point in opposite directions and only
 * one of them reaches a cost report today.
 */
entity Gang : cuid, managed, common.scoped {
  code            : String(40);
  description     : String(255);
  template        : Association to CrewTemplate;
  project         : Association to prj.Project;
  /** DERIVED: slots filled by a man who is present and not blocked. */
  manned          : Integer;
  /** DERIVED from the template, so the two are always compared like for like. */
  slotsRequired   : Integer;
  /** DERIVED at the rates of the men actually in the slots. */
  actualRatePerHr : Decimal(15,2);
  status          : String(20) default 'Planned';
  /** Why it may not mobilise, where it may not. Empty when it may. */
  blockedReason   : String(255);
  slots           : Composition of many GangSlot on slots.gang = $self;
}

/**
 * One filled — or unfilled — position in a live gang.
 *
 * A slot filled from a subcontract purchase order carries that order's item
 * price, which is not the rate of the trade the man is working: a Helper slot
 * filled by a man engaged as a Steel Fixer is paid at his engaged rate while
 * doing a Helper's work, and that difference is invisible unless both are held.
 */
entity GangSlot : cuid {
  gang           : Association to Gang;
  slotNo         : Integer;
  /** OWN | SUBCONTRACT */
  source         : String(20);
  employee       : Association to Employee;
  engagement     : Association to SubcontractEngagement;
  /** The trade the slot is for, which need not be the trade the man is engaged as. */
  trade          : Association to TradeCatalogue;
  grade          : Association to TradeGrade;
  ratePerHr      : Decimal(15,2);
  /** Set where the man is on the slot but may not be counted: an expired card. */
  blockedReason  : String(255);
}

/**
 * Why a man cannot be planned, and what follows from it.
 *
 * The switches are on the reason, not chosen per absence: the person recording
 * one should not be deciding whether it stops a timesheet.
 */
entity AbsenceReason : cuid, managed, common.scoped {
  code                : String(40);
  description         : String(255);
  blocksTimesheet     : Boolean default false;
  blocksMobilisation  : Boolean default true;
  documentRequired    : Boolean default false;
  /** Whether the hours go outward as absence rather than simply not going. */
  postsAsAbsenceHours : Boolean default false;
  /** Absconded and Removed from site never return, and follow the man across suppliers. */
  returnsAutomatically: Boolean default true;
}

/**
 * Availability, not leave entitlement.
 *
 * No balances, accruals, approvals or pay: payroll is outside KONSTRYX. This
 * answers one question — can this man be planned tomorrow, and if not why.
 *
 * A subcontract man being absent costs nothing while an own man still costs.
 * Both break the gang equally, which is why one register holds both.
 */
entity Absence : cuid, managed, common.scoped {
  employee    : Association to Employee;
  engagement  : Association to SubcontractEngagement;
  reason      : Association to AbsenceReason;
  fromDate    : Date;
  toDate      : Date;
  /**
   * Set where the row was raised by an expiry rather than typed. A derived
   * absence cannot be edited by hand: the document is what ends it.
   */
  derived     : Boolean default false;
  note        : String(500);
}

/**
 * A subcontract worker: the man, not the contract.
 *
 * He is created once and identified by his passport. Being on site is a
 * separate engagement against a purchase order, so the same man returning next
 * year on another project under another supplier is reused rather than created
 * again — which is the whole point of holding him. Under a contract-scoped
 * design he would be four records with four sets of documents, and nothing
 * would show that the man on site today already has years of history here.
 *
 * Identity and statutory documents belong to the man because they do not
 * change. Trade, grade and rate belong to the engagement because they do.
 */
entity SubcontractWorker : cuid, managed, common.scoped {
  workerNo    : String(20);
  fullName    : String(120);
  passportNo  : String(40);
  emiratesId  : String(40);
  nationality : String(60);
  status      : String(20) default 'Active';
  documents   : Composition of many SubcontractWorkerDocument on documents.worker = $self;
  /**
   * Associated, not composed: an engagement is a document against a purchase
   * order with its own life, not a child of the man's record. Deleting a man
   * must not silently delete the spells that were billed for him.
   */
  engagements : Association to many SubcontractEngagement on engagements.worker = $self;
}

entity SubcontractWorkerDocument : cuid {
  worker      : Association to SubcontractWorker;
  code        : String(40);
  description : String(120);
  documentNo  : String(60);
  issuedOn    : Date;
  expiresOn   : Date;
  blocking    : Boolean default false;
}

/**
 * One spell on site, against one purchase order item.
 *
 * Cost posts through a service entry sheet against that order: no payroll, no
 * cost centre, no work agreement. HSE induction follows the engagement because
 * it is redone per project; workmen's compensation follows the order.
 *
 * One man may hold only one live engagement — two overlapping spells would let
 * the same day be billed by two suppliers, so an overlap is refused on save
 * whatever the supplier or the company.
 */
entity SubcontractEngagement : cuid, managed, common.scoped {
  worker          : Association to SubcontractWorker;
  vendor          : Association to master.Vendor;
  project         : Association to prj.Project;
  /** The order the hours are certified against, and its item. */
  poNo            : String(20);
  poItem          : String(10);
  /** The trade he is engaged as, which is what he is paid at. */
  trade           : Association to TradeCatalogue;
  grade           : Association to TradeGrade;
  ratePerHr       : Decimal(15,2);
  fromDate        : Date;
  toDate          : Date;
  hseInductionOn  : Date;
  wcCoverExpiry   : Date;
  status          : String(20) default 'Active';
}

/**
 * How subcontract labour actually arrives: a supplier's spreadsheet with two
 * hundred names, the morning before the men turn up.
 *
 * The mapping is saved per vendor because every supplier's columns differ and
 * re-mapping two hundred rows by hand at 6am is how bad data gets in. Nothing
 * commits until the preview has run: a duplicate passport is a man already
 * held, not a new one.
 */
entity RosterUpload : cuid, managed, common.scoped {
  vendor        : Association to master.Vendor;
  fileName      : String(255);
  uploadedOn    : Timestamp;
  status        : String(20) default 'Preview';
  rowsTotal     : Integer;
  rowsAccepted  : Integer;
  rowsRejected  : Integer;
  /** Rows whose passport already belongs to a man on another master. */
  rowsDuplicate : Integer;
  rows          : Composition of many RosterUploadRow on rows.upload = $self;
}

/**
 * One line of a supplier's roster, as read and as judged.
 *
 * Grade and document expiries are carried as well as the name and trade:
 * without a grade no rate resolves, so a roster that omits it produces men who
 * cannot be costed.
 */
entity RosterUploadRow : cuid {
  upload       : Association to RosterUpload;
  lineNo       : Integer;
  fullName     : String(120);
  passportNo   : String(40);
  tradeCode    : String(40);
  gradeCode    : String(20);
  joiningDate  : Date;
  visaExpiry   : Date;
  /** Accepted | Rejected | Duplicate */
  outcome      : String(20);
  reason       : String(255);
  worker       : Association to SubcontractWorker;
}
