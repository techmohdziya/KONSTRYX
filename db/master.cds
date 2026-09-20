/**
 * KONSTRYX — konstryx.master (Data Model Spec §4)
 * Resource hierarchy, CBS library, rates, templates, vendor/material mirrors.
 * R2-R4 verticals listed as stubs.
 */
namespace konstryx.master;

using { cuid, managed, Currency } from '@sap/cds/common';
using { konstryx.common } from './common';
using { konstryx.prj } from './prj';
using { konstryx.admin } from './admin';

type VerticalType : String enum { MR; EQR; MPR; VR; SCR; SF_DESIGN; SF_MATERIAL; };

// Resource hierarchy L1->L5; L5 = the KONSTRYX resource code.
entity ResourceNode : cuid, managed, common.scoped {
  code         : String(40);
  level        : String(2) enum { L1; L2; L3; L4; L5; };
  parent       : Association to ResourceNode;
  verticalType : VerticalType;
  description  : String(255);
  consUoM      : String(10);
  outputUoM    : String(10);
  /**
   * The S/4 material this resource buys as. Without it a requisition can say
   * what was wanted in KONSTRYX terms but not what to order, because
   * API_PURCHASEREQ_PROCESS_SRV is keyed on the material number, not on a
   * description (I-35).
   *
   * One material per resource, not one per company — decided 2026-08-17. The
   * group is on a single S/4 client, where a material number is client-level:
   * every company code sees the same number and only the plant and valuation
   * extensions differ. Where a company genuinely buys a different item, that
   * item is already its own COMPANY-scoped leaf, so the company dimension is
   * carried by the hierarchy and does not need repeating here.
   *
   * A reference, never a master: materials are created in S/4 and registered
   * here, which is why this points at the mirror rather than holding a code.
   *
   * MATERIAL class only. A material number is source-independent — the same
   * item bought from any vendor is the same product — which is what makes one
   * per resource correct. The other classes are not like that; see
   * s4ServiceProduct below and RateMaster's own routing fields.
   */
  s4Material   : Association to Material;
  /**
   * The ERP product code this resource is registered as, and the code of the
   * service product it is registered as when it is hired rather than bought.
   *
   * The associations above point at rows in the mirror, and the mirror is
   * rebuilt from ERP on every read - a mirror row's key is generated here, so
   * an association stored against it stops resolving the moment the catalogue
   * is read again. The registration therefore has to be the code, which is
   * stable in S/4 and is what a customer actually configures; the associations
   * are resolved from it after each master sync.
   *
   * A leaf with no registration is not an error. It is a resource KONSTRYX can
   * plan and cost and cannot yet order, and the requisition says so in those
   * words rather than failing with a null.
   */
  s4MaterialCode       : String(40);
  s4ServiceProductCode : String(40);
  /**
   * What a requisition orders when the leaf is NOT a material: manpower hired
   * in, plant rented, a subcontracted service (spec §8 / P10, class -> S/4
   * routing). Held on the leaf rather than on the rate because a requisition
   * is raised BEFORE a vendor exists — the vendor arrives with the award — so
   * the pre-award document needs a generic service product to name.
   *
   * RateMaster carries the vendor-specific one for costing and award. The two
   * are different questions: this one is "what am I asking to buy", that one
   * is "what did this vendor quote it as".
   */
  s4ServiceProduct : Association to Material;
  defaultCBS   : Association to CBSNode;
  linkedRate   : Association to RateMaster;
  // Association, not Composition. A self-referencing composition sends CAP's
  // draft activation into infinite recursion expanding its own children, and
  // composition would mean deleting an L2 silently deletes its whole subtree.
  // The hierarchy is owned by `parent`; children are simply the inverse.
  children     : Association to many ResourceNode on children.parent = $self;
}

// CBS library L1->L3 + resource affinity.
entity CBSNode : cuid, managed, common.scoped {
  code             : String(40);
  /**
   * What this node is called.
   *
   * There was no name field, so every screen showed `phase` instead — which is
   * the L1 phase a node belongs to, not the node. The result was a breakdown
   * where five different level-2 nodes all read "Super-structure" and the only
   * thing telling them apart was a code, and a cost breakdown whose rows cannot
   * be told apart is not a breakdown.
   */
  name             : String(120);
  level            : String(2) enum { L1; L2; L3; };
  parent           : Association to CBSNode;
  constructionType : String(60);
  /** The L1 phase this node sits under. A grouping, not a name. */
  phase            : String(60);
  /**
   * Whether this node absorbs allocated cost or is a pool that gets spread.
   *
   * The allocation engine needs the distinction and nothing carried it, so the
   * engine would either take a hard-coded list of codes or allocate an overhead
   * onto an overhead — which compounds silently and is invisible in the result,
   * because the total still reconciles.
   */
  costNature       : String(10) enum { DIRECT; INDIRECT; OVERHEAD; } default 'DIRECT';
  /**
   * The driver used when this node IS the pool: LABOUR_HOURS, DIRECT_COST,
   * HEADCOUNT, GFA. A default rather than a rule — an allocation run may
   * override it, because the same overhead is fairly spread by hours in one
   * month and by direct cost in another.
   */
  allocBasis       : String(20);
  children         : Association to many CBSNode on children.parent = $self;
}

entity ProjectTemplate : cuid, managed, common.scoped {
  code             : String(40);
  name             : String(150);
  constructionType : String(60);
  version          : String(10);
  cbsRoot          : Association to CBSNode;
  resources        : Composition of many ProjectTemplateResource on resources.template = $self;
}

entity ProjectTemplateResource : cuid {
  template : Association to ProjectTemplate;
  resource : Association to ResourceNode;
}

entity ProductivityRate : cuid, managed, common.scoped {
  resource           : Association to ResourceNode;
  /**
   * The recipe key (wireframe m-prodrates): a norm belongs to a CBS leaf, and
   * the build-up of a BOQ line resolves through the line's CBS, never through
   * the line itself — nobody keys resources per BOQ line. A row with no
   * linkedCBS is a plain resource norm and takes no part in recipes.
   */
  linkedCBS          : Association to CBSNode;
  activity           : String(40);
  crewComposition    : String(255);
  outputPerHr        : Decimal(15,3);
  outputPerManday8h  : Decimal(15,3);
  outputUoM          : String(10);
  basis              : String(60);
  effectiveFrom      : Date;
}

entity ConsumptionRate : cuid, managed, common.scoped {
  material           : Association to ResourceNode;   // material modeled as resource
  /** Same recipe key as productivity: Material x Linked CBS x Activity. */
  linkedCBS          : Association to CBSNode;
  activity           : String(40);
  consRate           : Decimal(15,4);
  consUoM            : String(10);
  wastageAllowancePct: Decimal(5,2);
  /**
   * DERIVED, never keyed (CALC-01): theoretical x (1 + wastage/100), 4 dp
   * half-up. Stored for query performance; recomputed on every write; an
   * inbound value is ignored, not trusted.
   */
  netRate            : Decimal(10,4);
  basis              : String(60);
  effectiveFrom      : Date;
}

entity RateMaster : cuid, managed, common.scoped {
  resource      : Association to ResourceNode;
  /**
   * Where the resource comes from. A rate is not a property of the resource
   * alone — the wireframe's own master lists MP-CIV-CAR-SK-G1 three times, at
   * three different rates: once on our payroll and once per labour
   * subcontractor. Source is what separates those rows.
   */
  source        : String enum { IN_HOUSE; HIRED; LSC_HIRED; } default 'IN_HOUSE';
  /** Who supplies it. Null when IN_HOUSE — we are the supplier. */
  vendor        : Association to Vendor;
  /**
   * The S/4 routing for this row, and the reason source exists (spec §8, P10).
   * Internal cost is quantity x the S/4 activity price and posts a journal;
   * external cost is procured and posts through PR -> PO -> invoice. A row
   * that carried both would be costed twice, so exactly one applies and
   * source decides which:
   *
   *   IN_HOUSE            -> s4ActivityType, no service product, no vendor
   *   HIRED / LSC_HIRED   -> s4ServiceProduct + vendor, no activity type
   *
   * MATERIAL leaves use neither: they route through ResourceNode.s4Material,
   * because a material is bought the same way whoever supplies it.
   */
  s4ActivityType   : String(20);
  s4ServiceProduct : Association to Material;
  rateValue     : Decimal(15,2);
  basis         : String(10);        // hr / day / unit
  ccy           : Currency;
  netRate       : Decimal(15,2);
  effectiveFrom : Date;
  company       : Association to admin.Company;
}

// S/4 Business Partner mirror.
entity Vendor : cuid, managed, common.s4mirror {
  bpNumber     : String(10);
  name         : String(150);
  purchOrgs    : String(120);
  paymentTerms : String(10);
  hseCert      : String(60);
  status       : String(20);
}

/**
 * S/4 Customer mirror — the other half of the business partner.
 *
 * A project already named its client, as free text on customerParent, which is
 * enough to print on a report and useless for anything else: it cannot be
 * filtered, two spellings of the same client are two clients, and nothing ties
 * a project to the account S/4 will invoice. This is the same master the
 * supplier mirror reads, filtered to the customer role.
 *
 * Read-only like every mirror: correcting a customer means correcting it in
 * S/4.
 */
entity Customer : cuid, managed, common.s4mirror {
  bpNumber     : String(10);
  name         : String(150);
  /** The account group S/4 files it under - domestic, foreign, one-time. */
  accountGroup : String(10);
  country      : String(3);
  city         : String(60);
  status       : String(20);
}

// S/4 Product Master mirror (MR vertical).
entity Material : cuid, managed, common.s4mirror {
  materialCode  : String(40);
  description   : String(255);
  baseUoM       : String(10);
  materialGroup : String(20);
}

// ---- R2-R4 stubs (declared minimally; fields added before S5-S6) ----
entity WorkforceCatalog : cuid, managed, common.scoped { code : String(40); description : String(255); }
entity AssetRegister    : cuid, managed, common.s4mirror { assetNo : String(40); description : String(255); }

// Trades, the working day and the people are in wfm.cds — the same namespace,
// kept in their own file because they answer availability rather than price.
