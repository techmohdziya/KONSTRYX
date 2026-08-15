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
  defaultCBS   : Association to CBSNode;
  linkedRate   : Association to RateMaster;
  children     : Composition of many ResourceNode on children.parent = $self;
}

// CBS library L1->L3 + resource affinity.
entity CBSNode : cuid, managed, common.scoped {
  code             : String(40);
  level            : String(2) enum { L1; L2; L3; };
  parent           : Association to CBSNode;
  constructionType : String(60);
  resourceAffinity : String(60);
  phase            : String(60);     // L1 phase
  children         : Composition of many CBSNode on children.parent = $self;
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
  crewComposition    : String(255);
  outputPerHr        : Decimal(15,3);
  outputPerManday8h  : Decimal(15,3);
  outputUoM          : String(10);
  basis              : String(60);
  effectiveFrom      : Date;
}

entity ConsumptionRate : cuid, managed, common.scoped {
  material           : Association to ResourceNode;   // material modeled as resource
  consRate           : Decimal(15,4);
  consUoM            : String(10);
  wastageAllowancePct: Decimal(5,2);
  basis              : String(60);
  effectiveFrom      : Date;
}

entity RateMaster : cuid, managed, common.scoped {
  resource      : Association to ResourceNode;
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

// S/4 Product Master mirror (MR vertical).
entity Material : cuid, managed, common.s4mirror {
  materialCode  : String(40);
  description   : String(255);
  baseUoM       : String(10);
  materialGroup : String(20);
}

// ---- R2-R4 stubs (declared minimally; fields added before S5-S6) ----
entity WorkforceCatalog : cuid, managed, common.scoped { code : String(40); description : String(255); }
entity TradeCatalogue   : cuid, managed, common.scoped { code : String(40); description : String(255); }
entity ShiftPattern     : cuid, managed, common.scoped { code : String(40); description : String(255); }
entity AssetRegister    : cuid, managed, common.s4mirror { assetNo : String(40); description : String(255); }
