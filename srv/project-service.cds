/**
 * KONSTRYX — Project & BOQ service
 * Project/WBS mirrors, BOQ import & items, project CBS, allocations (Cost
 * Mapping Workbench), planned resources.
 */
using { konstryx.prj } from '../db/prj';

@requires: 'ProjectManager'
service ProjectService @(path:'/project') {
  @readonly entity Projects   as projection on prj.Project;     // S/4 mirror
  @readonly entity WBS        as projection on prj.WBSElement;  // S/4 mirror

  @odata.draft.enabled
  entity BOQs              as projection on prj.BOQ;
  entity BOQItems         as projection on prj.BOQItem;
  entity CBS              as projection on prj.CBSInstance;
  entity Allocations      as projection on prj.Allocation;
  entity ProjectResources as projection on prj.ProjectResource;
}
