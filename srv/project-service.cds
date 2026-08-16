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

      /**
       * Copies the CBS library into this project. A project costs against its
       * own copy, not the library, so that a later library change cannot
       * silently reshape a project already being costed — the same rule the
       * templates follow.
       */
      action instantiateCBS() returns String;
      /**
       * The gate (KX-GOV-002). Nothing generates budget lines until every rule
       * passes. Returns each rule with its counts, so the screen shows what is
       * failing rather than a mute disabled button.
       */
      action validateForBudget() returns array of {
        ruleId       : String(10);
        description  : String(120);
        linesChecked : Integer;
        failing      : Integer;
        result       : String(4);
      };

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
  entity BOQs as projection on prj.BOQ
    actions {
      /**
       * Loads priced items from a CSV. A bill arrives as a spreadsheet from the
       * QS in every case, so this is the normal way a BOQ enters the system,
       * not an exception path.
       *
       * All-or-nothing: a bill that loaded 400 of its 600 lines still adds up
       * to a contract value, and it is the wrong one.
       */
      action importItems(fileName : String(255), content : LargeString,
                         validateOnly : Boolean) returns String;

      /** Recomputes the header value from the priced lines. */
      action recalculate() returns String;

      /**
       * Resolves every mapped line's build-up from the CBS recipes: the norms
       * keyed to the line's CBS leaf, company override beating the group
       * default. Difficulty applies on top of the productivity norms,
       * most-specific-wins; the master norm itself is never adjusted
       * (KX-BUD-014). Returns the coverage the wireframe reports: recipe-found,
       * no-recipe, unmapped, rate-missing. MANUAL rows survive a regeneration —
       * they are someone's judgement, flagged, not overwritten.
       */
      action generateBuildUp(difficultyPct : Decimal(5,2)) returns String;
    };

  entity BOQItems as projection on prj.BOQItem
    actions {
      /**
       * Allocates part of this item's quantity to a WBS element and a CBS node.
       * This is the join between what was sold and where the cost lands.
       */
      action allocate(wbsCode : String(24), cbsCode : String(40),
                      qty : Decimal(15,3)) returns String;
    };

  entity BOQItemResources as projection on prj.BOQItemResource;
  entity CBS              as projection on prj.CBSInstance;
  entity Allocations      as projection on prj.Allocation;
  entity ProjectResources as projection on prj.ProjectResource;
}
