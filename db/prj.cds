/**
 * KONSTRYX — konstryx.prj (Data Model Spec §5)
 * Project & WBS mirrors, BOQ, project CBS, allocations, planned resources.
 */
namespace konstryx.prj;

using { cuid, managed, Currency } from '@sap/cds/common';
using { konstryx.common } from './common';
using { konstryx.admin } from './admin';
using { konstryx.master } from './master';

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
}

// S/4 WBS mirror.
/** Mastered here alongside its project (D-17), so outbound like the project. */
entity WBSElement : cuid, managed, common.s4outbound {
  code         : String(24);
  project      : Association to Project;
  parent       : Association to WBSElement;
  activityType : String(20);          // S/4 activity type
  description  : String(255);
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
  budgetAmount : Decimal(15,2);
  level        : String(2);
  // Association for the same reason as the library hierarchies: self-referencing
  // compositions break draft activation and imply cascade-delete of a subtree.
  children     : Association to many CBSInstance on children.parent = $self;
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
}

entity ProjectResource : cuid, managed {
  project     : Association to Project;
  wbs         : Association to WBSElement;
  resource    : Association to master.ResourceNode;
  plannedQty  : Decimal(15,3);
  uom         : String(10);
  buildUp     : String(500);
}
