/**
 * KONSTRYX — konstryx.apr
 * Configurable approval framework, applicable to any business object.
 *
 * bud.BudgetApproval already existed as a one-off for budgets. Every other
 * object that needs approving — resource requests, reservations, variations,
 * payment certificates — would otherwise grow its own copy, each with its own
 * status vocabulary. This generalises it: an administrator defines a scheme
 * per object type, and the runtime instantiates it when an object is submitted.
 *
 * Value bands matter in construction: a variation under AED 50k may need one
 * approver and over AED 500k may need four. Steps therefore carry amount
 * ranges and are selected at instantiation, not hard-coded per object.
 */
namespace konstryx.apr;

using { cuid, managed, Currency } from '@sap/cds/common';
using { konstryx.auth } from './auth';
using { konstryx.admin } from './admin';

// ------------------------------------------------------------ configuration

entity ApprovalScheme : cuid, managed {
  code       : String(40);
  name       : String(120);
  /** The object this scheme approves — same catalogue the authorization uses. */
  authObject : Association to auth.AuthObject;
  /** Null applies the scheme group-wide; set it to vary by legal entity. */
  company    : Association to admin.Company;
  isActive   : Boolean default true;
  validFrom  : Date;
  validTo    : Date;
  steps      : Composition of many ApprovalStepDef on steps.scheme = $self;
}

entity ApprovalStepDef : cuid, managed {
  scheme       : Association to ApprovalScheme;
  stepNo       : Integer;
  name         : String(120);
  /** Who may act. Resolved against auth.UserAssignment in the object's scope. */
  approver     : Association to auth.Persona;
  /** PARALLEL steps sharing a stepNo must all clear before the next number. */
  mode         : String enum { SEQUENTIAL; PARALLEL; } default 'SEQUENTIAL';
  /** Value band, inclusive of min and exclusive of max; null means unbounded. */
  minAmount    : Decimal(15,2);
  maxAmount    : Decimal(15,2);
  ccy          : Currency;
  isMandatory  : Boolean default true;
  /** True lets one approver clear several consecutive steps they qualify for. */
  allowChaining: Boolean default false;
}

// ----------------------------------------------------------------- runtime

entity ApprovalInstance : cuid, managed {
  scheme      : Association to ApprovalScheme;
  /** Polymorphic target: the object under approval. */
  entityName  : String(120);
  objectID    : UUID;
  objectDocNo : String(20);                    // denormalised for worklists
  amount      : Decimal(15,2);                 // the value the bands were matched on
  ccy         : Currency;
  status      : String enum { PENDING; APPROVED; REJECTED; WITHDRAWN; } default 'PENDING';
  startedAt   : Timestamp;
  completedAt : Timestamp;
  steps       : Composition of many ApprovalStepInstance on steps.instance = $self;
}

entity ApprovalStepInstance : cuid, managed {
  instance   : Association to ApprovalInstance;
  stepDef    : Association to ApprovalStepDef;
  stepNo     : Integer;
  name       : String(120);
  /** Filled when the step is acted on; null while pending. */
  actedBy    : String(120);
  decision   : String enum { PENDING; APPROVED; REJECTED; DELEGATED; SKIPPED; } default 'PENDING';
  decidedAt  : Timestamp;
  comment    : String(1000);
  delegatedTo: String(120);
}
