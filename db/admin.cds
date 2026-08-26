/**
 * KONSTRYX — konstryx.admin (Data Model Spec §3)
 * Group, companies, roles, promotion queue (mdg-queue), sync config.
 */
namespace konstryx.admin;

using { cuid, managed, Currency } from '@sap/cds/common';

entity CompanyGroup : cuid, managed {
  code           : String(10);
  name           : String(120);
  iasGroup       : String(120);     // IAS group id
  reportingCcy   : Currency;
  /**
   * Which rate a consolidated figure is converted at.
   *
   * Configuration rather than a constant, because it is a commercial
   * convention and not a fact: a group that reports at the average rate for
   * the period and one that reports at the closing rate are both right, and
   * both would call the other wrong. Every report states the type it used
   * alongside the number (D-4, 2026-08-26).
   */
  reportingRateType : String(10) default 'AVERAGE';
  companies      : Composition of many Company on companies.group = $self;
}

entity Company : cuid, managed {
  code         : String(10);        // INFC / PMI / IFO / MJN
  legalName    : String(150);
  group        : Association to CompanyGroup;
  s4CoCode     : String(4);         // S/4 company code
  defaultPlant : String(4);
  purchOrg     : String(4);
  /**
   * The buying group a requisition is raised under. Sits here with the rest of
   * the S/4 org data rather than in an environment variable, because it varies
   * per company exactly as the plant and purchasing org do — a group-wide
   * default would be wrong for every company but one.
   */
  purchGroup   : String(3);
  salesOrg     : String(4);
  profitCtr    : String(10);
  /**
   * The cost centre a project is made responsible to, and the project profile
   * it is created under. Both are S/4 configuration that varies per company,
   * and both used to be build-wide constants in S4ProjectConnector — read off
   * a different tenant, so my434396 answered a real push with "Profit Center
   * 10001000 does not exist". They belong beside the rest of the org data.
   */
  costCtr      : String(10);
  projectProfile : String(7);
  ccy          : Currency;
  isDefault    : Boolean default false;
}

/**
 * Organizational values as they exist in the connected S/4 system.
 *
 * **Why these are read and never shipped.** Plants, purchasing organizations,
 * profit centres and project profiles are configuration of the customer's own
 * S/4 system. In a multi-tenant product there is no value that is right for
 * every tenant, so a content pack cannot carry them: the pack that seeded
 * tenant my434396 carried values read off my401381, and S/4 answered a real
 * project push with "Profit Center 10001000 does not exist". They were
 * plausible, and they belonged to a different system.
 *
 * So this table is filled by reading the tenant's own S/4 through the `ITS_S4`
 * destination, and `Company` selects from it rather than being told what to
 * hold. A value nobody can find in here does not exist in the system the
 * documents are going to.
 *
 * Read-only to the client, like every other S/4 mirror (DM-01): correcting a
 * plant means correcting it in S/4, not here.
 */
entity S4OrgValue : cuid, managed {
  /**
   * COMPANY_CODE | PLANT | PURCH_ORG | PURCH_GROUP | PROFIT_CENTER |
   * COST_CENTER | PROJECT_PROFILE
   */
  kind        : String(20);
  code        : String(20);
  name        : String(120);
  /**
   * The S/4 company code this value belongs to, where S/4 scopes it to one.
   * Blank means the value is global to the system, or that the source that
   * produced it does not say — a catalogue read of all plants cannot tell you
   * which company codes use them.
   */
  parentCode  : String(20);
  ccy         : String(5);
  /**
   * Which S/4 service answered, and whether the value came from configuration
   * or from a document that used it. A value observed on a live requisition is
   * proof it works; a value in a catalogue is only proof it exists.
   */
  source      : String(160);
  inUse       : Boolean default false;
  s4System    : String(30);
  readAt      : Timestamp;
}

// Persona -> XSUAA role collection mapping, with module access matrix.
entity RoleCollectionMap : cuid, managed {
  persona        : String(60);
  roleCollection : String(120);
  moduleAccess   : String(500);     // JSON: { module: 'P'|'A'|'V'|'R' }
}

entity UserCompanyAccess : cuid, managed {
  user      : String(120);
  company   : Association to Company;
  role      : String(60);           // persona
  validFrom : Date;
  validTo   : Date;
}

// mdg-queue: local -> group master promotion requests.
entity PromotionRequest : cuid, managed {
  objectType    : String(40);       // e.g. ResourceNode
  objectKey     : String(60);
  currentScope  : String(10);
  proposedScope : String(10);
  requester     : String(120);
  decision      : String(20);       // PENDING / APPROVED / REJECTED
  decidedBy     : String(120);
  comment       : String(500);
  status        : String(20) default 'PENDING';
  age           : Integer;          // days open (derived)
}

entity S4SyncConfig : cuid, managed {
  company    : Association to Company;
  objectType : String(40);
  direction  : String enum { ![IN]; OUT; } default 'IN';
  trigger    : String(20);          // SCHEDULE / EVENT / ON_DEMAND
  service    : String(120);         // released API / comm scenario
  active     : Boolean default true;
}
