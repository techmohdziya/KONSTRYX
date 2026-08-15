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
entity Project : cuid, managed, common.s4mirror {
  code             : String(24);
  name             : String(150);
  company          : Association to admin.Company;
  customerParent   : String(120);
  contractValue    : Decimal(15,2);
  ccy              : Currency;
  startDate        : Date;
  endDate          : Date;
  stage            : String(40);
  executingCompany : Association to admin.Company;
  childProjects    : Composition of many Project on childProjects.parentProject = $self;
  parentProject    : Association to Project;
  wbsElements      : Composition of many WBSElement on wbsElements.project = $self;
}

// S/4 WBS mirror.
entity WBSElement : cuid, managed, common.s4mirror {
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
  qty          : Decimal(15,3);
  uom          : String(10);
  rate         : Decimal(15,2);
  amount       : Decimal(15,2);
  billedToDate : Decimal(15,2);
  cumDoneQty   : Decimal(15,3);
  cumDonePct   : Decimal(5,2);
  certifiedPct : Decimal(5,2);
  cbs          : Association to CBSInstance;
}

// Project CBS instantiated from the library.
entity CBSInstance : cuid, managed {
  code         : String(40);
  project      : Association to Project;
  parent       : Association to CBSInstance;
  libraryNode  : Association to master.CBSNode;
  budgetAmount : Decimal(15,2);
  level        : String(2);
  children     : Composition of many CBSInstance on children.parent = $self;
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
}

entity ProjectResource : cuid, managed {
  project     : Association to Project;
  wbs         : Association to WBSElement;
  resource    : Association to master.ResourceNode;
  plannedQty  : Decimal(15,3);
  uom         : String(10);
  buildUp     : String(500);
}
