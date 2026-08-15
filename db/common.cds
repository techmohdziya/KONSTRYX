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
// The object is mastered in S/4; KONSTRYX holds a copy. OK is the right default
// because a mirror row only exists once something arrived.
aspect s4mirror {
  s4Key        : String(60);   // S/4 object key
  s4System     : String(20);   // logical system / company tenant
  lastSyncedAt : Timestamp;
  syncStatus   : String enum { OK; STALE; ERROR; } default 'OK';
}

/**
 * The opposite direction: the object is mastered in KONSTRYX and has to reach
 * S/4. Deliberately a separate aspect rather than more values on s4mirror,
 * because the default has to be the other way round. A project created here
 * that never reached S/4 has not synchronised, and s4mirror would have called
 * it OK — which is precisely the state that lets people raise requests and
 * budgets against a project that can never post.
 */
aspect s4outbound {
  s4Key        : String(60);   // filled by S/4 on acceptance, not by us
  s4System     : String(20);
  lastSyncedAt : Timestamp;
  syncStatus   : String enum { NOT_SENT; PENDING; SENT; FAILED; } default 'NOT_SENT';
  syncMessage  : String(1000); // what S/4 said when it refused
  syncAttempts : Integer default 0;
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
