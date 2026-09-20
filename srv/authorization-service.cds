/**
 * KONSTRYX — Administration service
 * The S/4-style configuration surface: authorization, approval schemes,
 * attachment categories. Everything here is maintained by the client's own
 * administrator at runtime; nothing requires a redeploy.
 */
using { konstryx.auth } from '../db/auth';
using { konstryx.apr } from '../db/apr';
using { konstryx.sys } from '../db/sys';
using { konstryx.nr } from '../db/nr';

@requires: 'Admin'
service AuthorizationService @(path:'/authorization') {

  // -- catalogue: product content, read-only to the client -----------------
  @readonly entity Modules     as projection on auth.Module;
  @readonly entity AuthObjects as projection on auth.AuthObject;
  @readonly entity Activities  as projection on auth.Activity;

  // -- configuration: the administrator maintains these --------------------
  @odata.draft.enabled
  entity Personas as projection on auth.Persona
    actions {
      /** Clone an existing persona as the starting point for a new one. */
      action copyAs(
        code : String(40) @title : 'Code',
        name : String(80) @title : 'Name'
      ) returns UUID;
    };

  entity PersonaPermissions as projection on auth.PersonaPermission;
  entity UserAssignments    as projection on auth.UserAssignment;

  /** "What can this person actually do?" — resolved across all assignments. */
  @readonly entity EffectivePermissions as projection on auth.EffectivePermission;

  // -- approval configuration ----------------------------------------------
  @odata.draft.enabled
  entity ApprovalSchemes as projection on apr.ApprovalScheme;
  entity ApprovalStepDefs as projection on apr.ApprovalStepDef;

  // -- attachment configuration --------------------------------------------
  entity AttachmentCategories as projection on sys.AttachmentCategory;

  // -- document number ranges ----------------------------------------------
  /** Scope (GLOBAL vs COMPANY) and pattern are both configurable per object. */
  entity NumberRangeObjects as projection on nr.NumberRangeObject;
  /** Live counters. Read-only: numbers are issued by the runtime, never keyed. */
  @readonly entity NumberRangeCounters as projection on nr.NumberRangeCounter;

  /** Which delivered content packs this tenant has received, and when. */
  @readonly entity ContentPacks as projection on sys.ContentPack;

  // -- upload / download ----------------------------------------------------
  /** Every upload, and the fate of each of its rows. */
  @readonly entity ImportRuns as projection on sys.ImportRun;
  @readonly entity ImportRows as projection on sys.ImportRow;

  /**
   * Current rows as CSV. With templateOnly it returns the header alone, which
   * is the upload template — so the columns a user sees are by definition the
   * ones the importer accepts.
   */
  action exportCsv(target : String(120), templateOnly : Boolean) returns LargeString;

  /**
   * Loads a CSV through the target's own service, so every rule that service
   * enforces applies to the upload too.
   *
   * mode:  ALL_OR_NOTHING (default) keeps nothing unless every row is valid
   *        PARTIAL        keeps the valid rows and reports the rest
   *        VALIDATE_ONLY  changes nothing; reports what would happen
   */
  action importCsv(
    target   : String(120),
    fileName : String(255),
    content  : LargeString,
    mode     : String(20)
  ) returns String;

  /**
   * Re-runs delivered content deployment without restarting the service.
   * Needed after an upgrade ships a new pack version, and safe to call at any
   * time: packs already applied are skipped, and rows that already exist are
   * never overwritten.
   */
  action applyContentPacks() returns String;

  /**
   * Re-runs the check the service makes at boot: does every authorization
   * object still name an entity that exists, and a scope path that resolves.
   *
   * The catalogue is data and the model it points at is code, so the two drift
   * apart when an entity or an association is renamed and neither side
   * complains. A broken object does not enforce badly, it does not enforce at
   * all — and an operator who has just upgraded should be able to ask without
   * restarting and reading a log.
   */
  action checkAuthorizationCatalogue() returns String;
}

/**
 * Runtime surface for the frameworks — reachable by any authenticated user,
 * with row-level access governed by the authorization model rather than by a
 * service-level @requires.
 */
service CollaborationService @(path:'/collaboration') {

  /** Approvals addressed to the current user, and their history. */
  entity ApprovalInstances as projection on apr.ApprovalInstance
    actions {
      action withdraw(reason : String(500) @title : 'Reason for withdrawing') returns String;
    };

  entity ApprovalSteps as projection on apr.ApprovalStepInstance
    actions {
      action approve(comment : String(1000) @title : 'Comment') returns String;
      action reject(comment : String(1000) @title : 'Reason for rejecting')  returns String;
      action delegate(
        to      : String(120) @title : 'Hand to',
        comment : String(1000) @title : 'Comment'
      ) returns String;
    };

  /**
   * The approvals waiting on this person, oldest first.
   *
   * Answered by the same three rules the decide path enforces — the step is
   * the one its document is actually waiting on, the caller holds the persona
   * it asks for, and they have not already decided an earlier step of the same
   * document. A worklist built from a looser rule lists work that is refused
   * when opened, which teaches people that refusals are noise.
   *
   * A projection rather than a computed list, narrowed to those steps as it is
   * read. A worklist is filtered, sorted, paged and counted, and a list built
   * in memory answers none of those: it returns everything while appearing to
   * have applied them. Which steps is the engine's question; what they look
   * like is the model's.
   */
  // The step keeps its own entity for the document's own page; this one is the
  // worklist, so the composition on the instance stays pointed at that.
  @readonly
  @cds.redirection.target : false
  entity MyApprovals as projection on apr.ApprovalStepInstance {
    key ID                              as stepId,
        instance.ID                     as instanceId,
        instance.objectDocNo            as docNo,
        /** Named from the catalogue, so a mixed inbox groups by what things are. */
        instance.scheme.authObject.name as docType,
        instance.entityName             as entityName,
        instance.objectID               as objectID,
        instance.amount                 as amount,
        instance.ccy                    as ccy,
        instance.startedAt              as waitingSince,
        stepNo,
        name                            as stepName,
        /** Set where the step was handed to somebody by name. */
        delegatedTo
  } actions {
    action approve(comment : String(1000) @title : 'Comment') returns String;
    action reject(comment : String(1000) @title : 'Reason for rejecting')  returns String;
  };


  /**
   * The numbers the launchpad tiles show.
   *
   * A dynamic tile is not decoration: a tile that reads "3 over budget" is the
   * reason someone opens that app rather than another, and one that reads only
   * its own name makes the launchpad a menu. Returned as one call rather than
   * a dozen because a launchpad renders every tile at once, and thirteen
   * round trips on a cold start is what makes a home page feel slow.
   *
   * Each row carries the shape a dynamic launcher binds to - a number, the
   * unit it is counted in, a subtitle, and a state that colours it. The state
   * is computed from the number rather than fixed, because a tile whose colour
   * never changes tells you nothing the title did not.
   */
  action launchpadKpis() returns array of {
    tile        : String(40);
    title       : String(60);
    number      : Decimal(15,2);
    numberUnit  : String(20);
    subtitle    : String(80);
    /** Neutral | Positive | Critical | Negative — the tile's colour. */
    state       : String(10);
    /** Why it is that colour, in words, for the tile's footer. */
    info        : String(80);
  };

  /**
   * Starts an approval for any business object. The scheme is chosen by object
   * type and company, and the steps whose value bands cover the amount are
   * frozen onto the instance at submission — a scheme edited later does not
   * rewrite what an in-flight approval requires.
   */
  action submitForApproval(
    entityName : String(120),
    objectID   : UUID,
    docNo      : String(20),
    amount     : Decimal(15,2),
    companyID  : UUID
  ) returns String;

  /**
   * The uploads this person ran, and why each row was rejected.
   *
   * Every importer answers with "import run X holds the detail", and until now
   * that detail lived on the administrator's service. Telling someone where to
   * look and then refusing them entry is worse than not telling them.
   */
  @readonly entity MyImportRuns as projection on sys.ImportRun;
  @readonly entity MyImportRows as projection on sys.ImportRow;

  /** Attachments on any object. */
  entity Attachments as projection on sys.Attachment;

  /** Per-user table personalization. Filtered to the requesting user. */
  entity UserVariants as projection on sys.UserVariant;

  /**
   * Who the platform says this is.
   *
   * The screens read a name out of the UI's own JSON model until now, where it
   * was a wireframe persona — so every user, on every tenant, was greeted as
   * the same fictional person. In a multi-tenant product that is worse than
   * showing nothing: it invites someone to believe they are looking at their
   * own authorization when they are looking at a mock-up.
   *
   * `logon` is the XSUAA logon name, and it is deliberately the field the
   * screens display. It is the identity everything else in the product keys
   * on — the approval trail, the import history and the authorization model
   * all record this exact string — so showing a prettier name in the corner of
   * the screen would mean the name a person reads is not the name their
   * actions are filed under. A persona assignment that refuses because it was
   * keyed on a different spelling looks identical to no assignment at all, and
   * the only way to see that from a browser is to be shown the raw id.
   */
  type SignedInUser {
    /** XSUAA logon name — the id every audit trail records. */
    logon    : String(120);
    /** Display name where the identity provider supplies one, else the logon. */
    name     : String(150);
    initials : String(4);
    /**
     * True while this session bypasses the data-driven permission model
     * entirely, which is what the `Admin` scope does. Worth surfacing: an
     * administrator sees every row on every screen, and cannot tell from the
     * data alone that the permission model was never consulted.
     */
    isAdmin  : Boolean;
    /** Whether any persona is assigned to this logon on this tenant. */
    hasPersona : Boolean;
    tenant   : String(120);
  }

  /**
   * Reachable by any authenticated user, and deliberately not behind the
   * authorization model: a person who cannot yet be identified by it still
   * needs to be told which id the token carried.
   */
  function whoAmI() returns SignedInUser;
}
