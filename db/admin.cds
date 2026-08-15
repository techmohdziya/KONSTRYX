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
  companies      : Composition of many Company on companies.group = $self;
}

entity Company : cuid, managed {
  code         : String(10);        // INFC / PMI / IFO / MJN
  legalName    : String(150);
  group        : Association to CompanyGroup;
  s4CoCode     : String(4);         // S/4 company code
  defaultPlant : String(4);
  purchOrg     : String(4);
  salesOrg     : String(4);
  profitCtr    : String(10);
  ccy          : Currency;
  isDefault    : Boolean default false;
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
