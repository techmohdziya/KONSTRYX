/**
 * KONSTRYX — Common aspects (Data Model Spec §1.1)
 * Reusable aspects mixed into masters, mirrors and workflow documents.
 */
namespace konstryx.common;

using { konstryx.admin } from './admin';
using { konstryx.prj } from './prj';
using { cuid, managed } from '@sap/cds/common';

// Hybrid scoped masters: GROUP (shared) vs COMPANY (local), promotable.
aspect scoped {
  scope         : String enum { GROUP; COMPANY; } default 'COMPANY';
  owningCompany : Association to admin.Company;          // null when GROUP
  masterStatus  : String enum { ACTIVE; INACTIVE; PENDING_PROMOTION; } default 'ACTIVE';
  promotedFrom  : Association to admin.PromotionRequest;
}

// Read-only S/4HANA Public Cloud mirror metadata.
aspect s4mirror {
  s4Key        : String(60);   // S/4 object key
  s4System     : String(20);   // logical system / company tenant
  lastSyncedAt : Timestamp;
  syncStatus   : String enum { OK; STALE; ERROR; } default 'OK';
}

// Workflow document header attributes (RR / ADV / AVC / RES / Budget).
aspect documented {
  docNo    : String(20);       // e.g. RR-2026-00142
  project  : Association to prj.Project;
  company  : Association to admin.Company;
  status   : String(20);       // per status model §6.1
  raisedBy : String(120);
  raisedOn : Date;
}
