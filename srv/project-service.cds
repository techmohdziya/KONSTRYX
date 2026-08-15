/**
 * KONSTRYX — Project & BOQ service
 * Project/WBS mirrors, BOQ import & items, project CBS, allocations (Cost
 * Mapping Workbench), planned resources.
 */
using { konstryx.prj } from '../db/prj';
using { konstryx.master } from '../db/master';

@requires: 'ProjectManager'
service ProjectService @(path:'/project') {
  /**
   * Mastered here (D-17), so writable — a project is created in KONSTRYX and
   * pushed to S/4, or imported from Primavera. Draft-enabled because a project
   * header is filled in over several sittings and a half-typed one must not be
   * visible to anyone else.
   */
  @odata.draft.enabled
  entity Projects as projection on prj.Project
    actions {
      /**
       * Marks the project ready to leave KONSTRYX. The S/4 connector is not
       * built (Q-09), so this queues rather than posts: syncStatus becomes
       * PENDING and the project is visibly not in S/4 until it is.
       */
      action releaseToS4() returns String;
      /** Records the outcome of a sync attempt. Called by the connector. */
      action recordSyncResult(success : Boolean, s4Key : String(60),
                              s4System : String(20), message : String(1000)) returns String;
    };
  /** Maintained through the project draft — a WBS element only means something
   *  inside the project that owns it. Mastered here (D-17), so writable. */
  entity WBS as projection on prj.WBSElement;

  /**
   * Imports a project and its WBS tree from a Primavera P6 XML export.
   *
   * Deliberately has no PARTIAL mode. A P6 file is one project with a tree
   * hanging off it, and a project that imported its header and two thirds of
   * its WBS is worse than one that did not import at all — the missing branches
   * are invisible until someone tries to budget against them.
   */
  action importP6(
    fileName     : String(255),
    content      : LargeString,
    companyID    : UUID,
    validateOnly : Boolean
  ) returns String;

  // Sync state belongs to the connector. Marked read-only here so the write is
  // refused when it is made, rather than at activation: a user who typed into
  // the field and found out only when they pressed Save would have to unpick a
  // draft to get out of it.
  annotate Projects with {
    syncStatus   @readonly;
    s4Key        @readonly;
    s4System     @readonly;
    lastSyncedAt @readonly;
    syncMessage  @readonly;
    syncAttempts @readonly;
  };
  annotate WBS with {
    syncStatus   @readonly;
    s4Key        @readonly;
    s4System     @readonly;
    lastSyncedAt @readonly;
    syncMessage  @readonly;
    syncAttempts @readonly;
  };

  /**
   * The master entities a project row points at, read-only. Without them CAP
   * drops the associations from the projections entirely — a project CBS node
   * could not say which library node it came from, and a planned resource
   * could not name its resource, which makes both unusable in a UI.
   * Maintenance stays in MasterDataService; these are for resolution only.
   */
  @readonly entity ResourceCatalog as projection on master.ResourceNode;
  @readonly entity CBSLibrary      as projection on master.CBSNode;

  @odata.draft.enabled
  entity BOQs              as projection on prj.BOQ;
  entity BOQItems         as projection on prj.BOQItem;
  entity CBS              as projection on prj.CBSInstance;
  entity Allocations      as projection on prj.Allocation;
  entity ProjectResources as projection on prj.ProjectResource;
}
