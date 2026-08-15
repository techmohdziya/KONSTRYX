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
      action copyAs(code : String(40), name : String(80)) returns UUID;
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

  /**
   * Re-runs delivered content deployment without restarting the service.
   * Needed after an upgrade ships a new pack version, and safe to call at any
   * time: packs already applied are skipped, and rows that already exist are
   * never overwritten.
   */
  action applyContentPacks() returns String;
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
      action withdraw(reason : String(500));
    };

  entity ApprovalSteps as projection on apr.ApprovalStepInstance
    actions {
      action approve(comment : String(1000));
      action reject(comment : String(1000));
      action delegate(to : String(120), comment : String(1000));
    };

  /** Attachments on any object. */
  entity Attachments as projection on sys.Attachment;

  /** Per-user table personalization. Filtered to the requesting user. */
  entity UserVariants as projection on sys.UserVariant;
}
