/**
 * The two structures that are trees, declared as trees.
 *
 * A WBS and a resource breakdown are hierarchies in every system that holds
 * them, and both were being served as flat lists: a level-4 node sat beside a
 * level-1 node in whatever order the database returned, and the only clue that
 * one belonged under the other was a level column and a parent UUID nobody can
 * read. Sorting does not fix that — a tree is not a sorted list, and a QS
 * looking for "everything under substructure" needs the branch, not the rows
 * that happen to share a prefix.
 *
 * Two vocabularies do the work together, and both are required. Aggregation
 * says what the tree IS — which element identifies a node and which
 * association points at its parent. Hierarchy says how one query's answer is
 * carried back — how deep a node sits, whether it can still be expanded, how
 * many of its descendants a filter matched. Without the first, the service has
 * no tree to walk; without the second, the client gets rows and no shape.
 */
using ProjectService    from '../srv/project-service';
using MasterDataService from '../srv/masterdata-service';

annotate ProjectService.WBS with @(
  Aggregation.RecursiveHierarchy #WBSHierarchy : {
    $Type                    : 'Aggregation.RecursiveHierarchyType',
    NodeProperty             : ID,
    ParentNavigationProperty : parent,
  },
  Hierarchy.RecursiveHierarchy #WBSHierarchy : {
    $Type                  : 'Hierarchy.RecursiveHierarchyType',
    // The code, not the UUID: this is what the tree shows and what a search
    // matches on.
    ExternalKey            : code,
    DistanceFromRoot       : DistanceFromRoot,
    DrillState             : DrillState,
    LimitedDescendantCount : LimitedDescendantCount,
    Matched                : Matched,
    MatchedDescendantCount : MatchedDescendantCount,
  },
);

annotate MasterDataService.Resources with @(
  Aggregation.RecursiveHierarchy #ResourceHierarchy : {
    $Type                    : 'Aggregation.RecursiveHierarchyType',
    NodeProperty             : ID,
    ParentNavigationProperty : parent,
  },
  Hierarchy.RecursiveHierarchy #ResourceHierarchy : {
    $Type                  : 'Hierarchy.RecursiveHierarchyType',
    ExternalKey            : code,
    DistanceFromRoot       : DistanceFromRoot,
    DrillState             : DrillState,
    LimitedDescendantCount : LimitedDescendantCount,
    Matched                : Matched,
    MatchedDescendantCount : MatchedDescendantCount,
  },
);

annotate MasterDataService.CBSLibrary with @(
  Aggregation.RecursiveHierarchy #CBSHierarchy : {
    $Type                    : 'Aggregation.RecursiveHierarchyType',
    NodeProperty             : ID,
    ParentNavigationProperty : parent,
  },
  Hierarchy.RecursiveHierarchy #CBSHierarchy : {
    $Type                  : 'Hierarchy.RecursiveHierarchyType',
    ExternalKey            : code,
    DistanceFromRoot       : DistanceFromRoot,
    DrillState             : DrillState,
    LimitedDescendantCount : LimitedDescendantCount,
    Matched                : Matched,
    MatchedDescendantCount : MatchedDescendantCount,
  },
);

/**
 * A project's own breakdown, read as the tree it is.
 *
 * The library above is a tree and the instance of it was a flat list, which
 * meant the same structure read one way on the master screen and another on the
 * project — and the project is where the money is, so it is the one that had to
 * make sense.
 */
annotate ProjectService.CBS with @(
  Aggregation.RecursiveHierarchy #ProjectCBSHierarchy : {
    $Type                    : 'Aggregation.RecursiveHierarchyType',
    NodeProperty             : ID,
    ParentNavigationProperty : parent,
  },
  Hierarchy.RecursiveHierarchy #ProjectCBSHierarchy : {
    $Type                  : 'Hierarchy.RecursiveHierarchyType',
    ExternalKey            : code,
    DistanceFromRoot       : DistanceFromRoot,
    DrillState             : DrillState,
    LimitedDescendantCount : LimitedDescendantCount,
    Matched                : Matched,
    MatchedDescendantCount : MatchedDescendantCount,
  },
);
