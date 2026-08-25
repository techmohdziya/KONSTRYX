/**
 * KONSTRYX — konstryx.prj (Data Model Spec §5)
 * Project & WBS mirrors, BOQ, project CBS, allocations, planned resources.
 */
namespace konstryx.prj;

using { cuid, managed, Currency } from '@sap/cds/common';
using { konstryx.common } from './common';
using { konstryx.admin } from './admin';
using { konstryx.master } from './master';
using { konstryx.fin } from './fin';

// S/4 Enterprise Project mirror + Konstryx-local attributes.
/**
 * Mastered in KONSTRYX (D-17), not mirrored from S/4. A project is created
 * here — or imported from Primavera — and pushed outward, so it carries the
 * outbound sync aspect whose default is NOT_SENT rather than OK.
 */
entity Project : cuid, managed, common.s4outbound {
  code             : String(24);
  name             : String(150);
  company          : Association to admin.Company;
  customerParent   : String(120);
  contractValue    : Decimal(15,2);
  ccy              : Currency;
  startDate        : Date;
  endDate          : Date;
  /**
   * The rates this project's money is read at, pinned rather than floating.
   *
   * Revenue converts at the rate agreed when the contract was awarded and cost
   * at the rate the budget was baselined on. Without pinning them, a currency
   * that moves in March changes the margin reported for February, and two
   * reports run a week apart on the same closed period disagree.
   */
  contractFx       : Association to fin.ExchangeRate;
  budgetFx         : Association to fin.ExchangeRate;
  /** Configurable lifecycle; a project only leaves DRAFT once it is complete. */
  stage            : String(40) default 'Draft';
  executingCompany : Association to admin.Company;
  /**
   * Association, not Composition. A self-referencing composition makes CAP
   * expand the hierarchy recursively on draft activation and overflow the
   * stack, and it implies cascade-delete — removing a parent would silently
   * take its sub-projects with it (issue I-23).
   */
  childProjects    : Association to many Project on childProjects.parentProject = $self;
  parentProject    : Association to Project;
  wbsElements      : Composition of many WBSElement on wbsElements.project = $self;
  /**
   * The bills and the cost breakdown belong to the project and are read from
   * it, but each is a document in its own right rather than part of the
   * project's own edit.
   */
  boqs             : Association to many BOQ on boqs.project = $self;
  cbs              : Association to many CBSInstance on cbs.project = $self;
  activities       : Association to many Activity on activities.project = $self;
  locations        : Association to many SiteLocation on locations.project = $self;
}

// S/4 WBS mirror.
/** Mastered here alongside its project (D-17), so outbound like the project. */
entity WBSElement : cuid, managed, common.s4outbound {
  code         : String(24);
  project      : Association to Project;
  parent       : Association to WBSElement;
  activityType : String(20);          // S/4 activity type
  description  : String(255);
  /**
   * Associated rather than composed. An activity is a document in its own
   * right - it is scheduled, progressed and reported on independently - and a
   * composition would put it inside the project's draft tree, where it could
   * only be created by editing the project.
   */
  activities   : Association to many Activity on activities.wbs = $self;
}

/**
 * A schedulable task under a WBS element.
 *
 * The WBS says what the work is; an activity says how long it takes and what
 * has to finish before it can start. Dates are split into planned, early,
 * late and actual because they answer different questions: the early and late
 * sets are derived by scheduling, the planned set is what was agreed, and the
 * actual set is what happened.
 */
entity Activity : cuid, managed {
  code          : String(40);
  name          : String(255);
  project       : Association to Project;
  wbs           : Association to WBSElement;

  durationDays  : Integer default 0;
  plannedStart  : Date;
  plannedFinish : Date;

  /**
   * Derived by the critical path calculation, never keyed. Early dates come
   * from the forward pass, late dates from the backward pass, and total float
   * is the difference — an activity with none of it cannot slip without moving
   * the project's finish, which is what makes it critical.
   */
  earlyStart    : Date;
  earlyFinish   : Date;
  lateStart     : Date;
  lateFinish    : Date;
  totalFloat    : Integer;
  freeFloat     : Integer;
  isCritical    : Boolean default false;

  actualStart   : Date;
  actualFinish  : Date;
  percentDone   : Decimal(5,2) default 0;
  status        : String(20) default 'Planned';

  /** What must happen before this activity. */
  predecessors  : Composition of many ActivityRelation
                    on predecessors.successor = $self;
  successors    : Association to many ActivityRelation
                    on successors.predecessor = $self;
}

/**
 * One dependency between two activities.
 *
 * The four standard types are carried rather than assuming finish-to-start:
 * a site programme routinely overlaps trades with start-to-start and a lag,
 * and collapsing that to FS would push every downstream date out.
 */
entity ActivityRelation : cuid, managed {
  predecessor : Association to Activity;
  successor   : Association to Activity;
  /** FS finish-to-start, SS start-to-start, FF finish-to-finish, SF start-to-finish. */
  linkType    : String(2) default 'FS';
  /** Days added after the predecessor's driving date. Negative is a lead. */
  lagDays     : Integer default 0;
}

entity BOQ : cuid, managed {
  boqId         : String(20);
  project       : Association to Project;
  version       : String(10);
  status        : String(20);
  contractValue : Decimal(15,2);
  source        : String enum { IMPORT; MANUAL; } default 'IMPORT';
  items         : Composition of many BOQItem on items.boq = $self;
}

entity BOQItem : cuid, managed {
  boq          : Association to BOQ;
  itemNo       : String(20);
  code         : String(40);
  description  : String(500);
  /** Contract quantity — the certification basis. Revenue always uses this. */
  qty          : Decimal(15,3);
  /**
   * Budgeted quantity — IFC take-off plus pour wastage and test cubes, entered
   * in the conversion wizard. Cost always uses this; never crossed with qty
   * (CALC-05). Null means not yet budgeted, and cost falls back to qty.
   */
  budgetQty    : Decimal(15,3);
  uom          : String(10);
  rate         : Decimal(15,2);
  amount       : Decimal(15,2);
  billedToDate : Decimal(15,2);
  cumDoneQty   : Decimal(15,3);
  cumDonePct   : Decimal(5,2);
  certifiedPct : Decimal(5,2);
  cbs          : Association to CBSInstance;
  buildUp      : Composition of many BOQItemResource on buildUp.boqItem = $self;
}

/**
 * The resource build-up of one bill line: which resources, in what quantity,
 * the line consumes. An instance, not a master — it is generated from the CBS
 * recipe (the norms keyed to the line's CBS leaf) and is editable afterwards,
 * but a MANUAL row is an exception to flag for recipe creation, not a way of
 * working (wireframe cost-mapping step 3).
 */
entity BOQItemResource : cuid, managed {
  boqItem       : Association to BOQItem;
  resource      : Association to master.ResourceNode;
  /** Cost nature, one of the six verticals — taken from the resource. */
  category      : String(10);
  /** Quantity per one unit of the bill line, before scaling. */
  qtyPerUom     : Decimal(15,4);
  /** Scaled by budgetQty, not contract qty (CALC-05). */
  totalQty      : Decimal(15,3);
  uom           : String(10);
  /** Money from the Rate Master at generation time — never from the norm. */
  unitRate      : Decimal(15,2);
  amountPerUnit : Decimal(15,4);
  totalAmount   : Decimal(15,2);
  /**
   * The audit trail that makes the governance rule enforceable: a dashboard of
   * MANUAL lines IS the flag-for-recipe-creation queue. Never drop this field.
   */
  source        : String enum { RECIPE; MANUAL; IMPORTED; } default 'RECIPE';
  /** The norm row this line was generated from, resolvable. */
  sourceNorm    : String(60);
  /** Applied once, never multiplied (CALC-03 / KX-BUD-014). */
  difficultyPct : Decimal(6,2) default 100;
  /** Which precedence tier won: activity / activityLibrary / project / none. */
  difficultySrc : String(20);
  /** How the number was reached — norm, wastage, difficulty — for audit. */
  basis         : String(255);
}

// Project CBS instantiated from the library.
entity CBSInstance : cuid, managed {
  code         : String(40);
  project      : Association to Project;
  parent       : Association to CBSInstance;
  libraryNode  : Association to master.CBSNode;
  /**
   * DERIVED, never keyed. The sum of the budget lines posted against this node
   * and every node beneath it.
   *
   * It was a stored decimal that nothing recomputed, so the lines under a node
   * could sum to one figure while the node reported another and neither was
   * wrong enough to notice. Recomputed by rollUpBudget; an inbound value is
   * ignored, not trusted — the same treatment ConsumptionRate.netRate gets, and
   * for the same reason.
   */
  budgetAmount : Decimal(15,2);
  /** This node's own lines, before its children are added in. */
  ownAmount    : Decimal(15,2);
  /**
   * Copied from the library node at instantiation and overridable per project:
   * a cost that is an overhead on a tower is a direct cost on the site
   * infrastructure package that exists to provide it.
   */
  costNature   : String(10) enum { DIRECT; INDIRECT; OVERHEAD; } default 'DIRECT';
  allocBasis   : String(20);
  level        : String(2);
  // Association for the same reason as the library hierarchies: self-referencing
  // compositions break draft activation and imply cascade-delete of a subtree.
  children     : Association to many CBSInstance on children.parent = $self;
}

/**
 * Where on the site the work is.
 *
 * Productivity is output per man-hour, and it was not computable — not for
 * want of arithmetic, but because a daily log could not say where the hours
 * were worked. Output per man-hour across a whole project is a number nobody
 * can act on; per level, per zone, per pour it is the number a site is run on.
 *
 * Owned by the project rather than held as a global master. A grid reference
 * means nothing outside the building it is drawn on, and two projects on
 * neighbouring plots both have a "Level 3".
 */
entity SiteLocation : cuid, managed {
  project      : Association to Project;
  code         : String(40);                   // T1-L03-ZA
  name         : String(150);
  level        : String(2) enum { L1; L2; L3; L4; };
  locationType : String(20) enum { SITE; BUILDING; FLOOR; ZONE; GRID; AREA; };
  /**
   * Association, not Composition — the same reason the WBS, CBS and resource
   * hierarchies use one. A self-referencing composition overflows the stack on
   * draft activation, and it would mean deleting a floor silently deletes
   * every zone on it.
   */
  parent       : Association to SiteLocation;
  children     : Association to many SiteLocation on children.parent = $self;
  /**
   * Gross floor area. Carried so an area-weighted allocation can read it
   * rather than assert it: the split basis "GFA-weighted per floor" was a
   * sentence in a string field with no floor areas anywhere behind it.
   */
  gfa          : Decimal(15,3);
  uom          : String(10);
}

// BOQItem <-> WBS <-> CBS mapping.
entity Allocation : cuid, managed {
  boqItem      : Association to BOQItem;
  wbs          : Association to WBSElement;
  cbs          : Association to CBSInstance;
  allocQty     : Decimal(15,3);
  allocPct     : Decimal(5,2);
  pctOfItem    : Decimal(5,2);
  pctOfCBSRate : Decimal(5,2);
  /** Which template made this row: TPL-SINGLE / TPL-FLOORS / TPL-ZONES (B.1). */
  template     : String(20);
  /** The human words behind the split — "GFA-weighted per floor". */
  splitBasis   : String(40);
  /**
   * The floor or zone this share of the bill line belongs to.
   *
   * TPL-FLOORS and TPL-ZONES were already splitting a bill line across the
   * building, with the floors named only inside a template string and the
   * weighting asserted in splitBasis. Pointing at the location makes the same
   * split computable: a GFA weighting now reads the areas off these rows.
   */
  location     : Association to SiteLocation;
}

entity ProjectResource : cuid, managed {
  project     : Association to Project;
  wbs         : Association to WBSElement;
  resource    : Association to master.ResourceNode;
  plannedQty  : Decimal(15,3);
  uom         : String(10);
  buildUp     : String(500);
}
