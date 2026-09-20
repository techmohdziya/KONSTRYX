/**
 * KONSTRYX — konstryx.sys
 * Cross-cutting platform capabilities every business object relies on:
 * attachments, per-user UI personalization, and object-level notes.
 *
 * Both are polymorphic (entityName + objectID) rather than one child table per
 * parent. A drawing attaches to a resource request, a reservation, a payment
 * certificate and a snag alike; modelling that as thirty compositions would
 * mean thirty upload handlers.
 */
namespace konstryx.sys;

using { cuid, managed } from '@sap/cds/common';
using { konstryx.auth } from './auth';

// ---------------------------------------------------------- delivered content

/**
 * Record of which delivered content packs have been applied to this tenant.
 *
 * Content that a client may edit cannot ship in db/data. CAP turns those CSVs
 * into .hdbtabledata, and HDI re-imports the rows it manages on every deploy —
 * so a client who changed a number range scope or a rate would silently have it
 * reverted at the next upgrade. db/data is therefore reserved for the immutable
 * catalogue the runtime cannot start without.
 *
 * Everything else is a versioned pack applied once, insert-if-missing, never
 * update. An upgrade that adds rows to a pack ships a new version; existing
 * rows the client has since edited are left exactly as they are.
 */
entity ContentPack : cuid, managed {
  packId       : String(40);      // NUMBER_RANGES · ECO_STARTER
  version      : String(20);
  description  : String(255);
  appliedAt    : Timestamp;
  appliedBy    : String(120);
  rowsInserted : Integer;
  rowsSkipped  : Integer;         // already present, left untouched
  /**
   * A pack that fails is recorded too, and that is the point of the field.
   *
   * A failure used to leave nothing behind: the rows were rolled back, no row
   * was written here, and a tenant missing its personas looked exactly like a
   * tenant that was never given any. The only trace was one line in a boot log,
   * which is the wrong place for it — the symptom is every request returning
   * 403, that sends somebody to the authorization model, and by the time they
   * think to doubt the seed the container has restarted and taken the log.
   *
   * Kept for the same reason ImportRun keeps every load: the question is asked
   * long after the event.
   */
  outcome      : String(10) default 'APPLIED';   // APPLIED · FAILED
  /** What went wrong, naming the row. Empty on a pack that applied. */
  message      : String(1000);
}

// ------------------------------------------------------------------ imports

/**
 * One upload. Every import is kept — what was loaded, by whom, from which
 * file, and what happened to each row — because "who changed the rates last
 * Tuesday" is asked far more often than anyone expects, and a load that left
 * no trace cannot answer it.
 */
entity ImportRun : cuid, managed {
  target       : String(120);   // MasterDataService.Resources
  fileName     : String(255);
  rowsTotal    : Integer;
  rowsAccepted : Integer;
  rowsRejected : Integer;
  /** PARTIAL keeps the good rows; nothing is kept when a VALIDATED run fails. */
  mode         : String enum { VALIDATE_ONLY; ALL_OR_NOTHING; PARTIAL; } default 'ALL_OR_NOTHING';
  status       : String enum { RUNNING; COMPLETED; REJECTED; FAILED; } default 'RUNNING';
  message      : String(1000);
  rows         : Composition of many ImportRow on rows.run = $self;
}

/**
 * A staged row. The raw payload is kept alongside the error so a user can see
 * exactly what they uploaded rather than guessing which line the message meant.
 */
entity ImportRow : cuid {
  run       : Association to ImportRun;
  lineNo    : Integer;
  payload   : LargeString;      // the source line, verbatim
  accepted  : Boolean default false;
  error     : String(1000);
}

// -------------------------------------------------------------- attachments

entity Attachment : cuid, managed {
  /** Polymorphic target. */
  entityName  : String(120);
  objectID    : UUID;
  objectDocNo : String(20);                // denormalised so lists need no join

  fileName    : String(255);
  mimeType    : String(120) @Core.IsMediaType;
  content     : LargeBinary @Core.MediaType: mimeType @Core.ContentDisposition.Filename: fileName;
  fileSize    : Integer64;

  /** Client-configurable classification — drawing, permit, invoice, photo. */
  category    : Association to AttachmentCategory;
  note        : String(500);
  /** Successive uploads under one logical document keep their history. */
  version     : Integer default 1;
  supersedes  : Association to Attachment;
  /**
   * Withdrawn without being destroyed.
   *
   * A version another version supersedes cannot be deleted — doing so leaves
   * its successor pointing at nothing, and the history is the only reason to
   * keep versions at all. But somebody who uploads the wrong file needs a way
   * to say so, and refusing with no alternative is how a rule gets worked
   * around. This is that alternative: the row stays, the chain holds, and the
   * file stops being offered as current.
   */
  isObsolete  : Boolean default false;
}

entity AttachmentCategory : cuid, managed {
  code        : String(40);
  name        : String(80);
  /** Restrict a category to one object type, or leave null for any. */
  authObject  : Association to auth.AuthObject;
  isMandatory : Boolean default false;     // block submit until one is present
  isActive    : Boolean default true;
}

// ---------------------------------------------------------- personalization

/**
 * Table and filter personalization, per user. A standalone SAPUI5 app has no
 * Fiori launchpad personalization service behind it, so the variants have to
 * be stored by the application or they die with the browser profile.
 *
 * payload holds the UI5 p13n/variant state verbatim. It is deliberately opaque
 * to the backend: the shape belongs to the UI5 version in use, and parsing it
 * server-side would couple the service to the front end.
 */
entity UserVariant : cuid, managed {
  user        : String(120);
  /** Stable identifier of the personalized control, e.g. worklist.requestTable. */
  target      : String(120);
  variantName : String(120);
  payload     : LargeString;
  isDefault   : Boolean default false;
  /** Published by an administrator for everyone; not editable by end users. */
  isPublic    : Boolean default false;
}
