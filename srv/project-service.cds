/**
 * KONSTRYX — Project & BOQ service
 * Project/WBS mirrors, BOQ import & items, project CBS, allocations (Cost
 * Mapping Workbench), planned resources.
 */
using { konstryx.prj } from '../db/prj';
using { konstryx.master } from '../db/master';

@requires: 'ProjectManager'
service ProjectService @(path:'/project') {
  @readonly entity Projects   as projection on prj.Project;     // S/4 mirror
  @readonly entity WBS        as projection on prj.WBSElement;  // S/4 mirror

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
