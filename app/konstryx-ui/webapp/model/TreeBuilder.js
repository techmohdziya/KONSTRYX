sap.ui.define([], function () {
	"use strict";

	/**
	 * Turns a flat list of parent-linked rows into the nested shape a TreeTable
	 * binds to.
	 *
	 * Used by every hierarchy master — the resource catalogue, the CBS library,
	 * and the project CBS — because they are all the same shape: a code, a level,
	 * and a parent.
	 *
	 * The part worth reading is what happens when a filter is applied. Searching
	 * a tree for "tower crane" and returning only the matching node produces
	 * something worse than a flat list: the match appears at the root with no
	 * indication of where it sits, so the user cannot tell a top-level category
	 * from a leaf five levels down. Every ancestor of a match is therefore kept
	 * as well, and marked so the view can show it as context rather than as a
	 * result.
	 */
	return {

		/**
		 * @param {object[]} aRows      flat rows, each with an id and a parent id
		 * @param {object}   oOptions   {idKey, parentKey, sortKey, matches}
		 *                              matches(row) -> boolean; omit for no filter
		 * @returns {object} {nodes: [...], total, matched}
		 */
		build: function (aRows, oOptions) {
			var sIdKey = oOptions.idKey || "ID",
				sParentKey = oOptions.parentKey || "parent_ID",
				sSortKey = oOptions.sortKey || "code",
				fnMatches = oOptions.matches,
				mRowById = {},
				mKeep = null,
				iMatched = 0;

			aRows.forEach(function (oRow) {
				mRowById[oRow[sIdKey]] = oRow;
			});

			if (fnMatches) {
				mKeep = {};
				aRows.forEach(function (oRow) {
					if (!fnMatches(oRow)) {
						return;
					}
					iMatched++;
					mKeep[oRow[sIdKey]] = "match";

					// Walk up. The guard is not paranoia: the backend refuses to
					// create a cycle, but this code also runs against data that
					// arrived by import, and an infinite loop here freezes the
					// browser rather than failing visibly.
					var oParent = mRowById[oRow[sParentKey]],
						iGuard = 0;
					while (oParent && iGuard++ < 50) {
						if (mKeep[oParent[sIdKey]] !== "match") {
							mKeep[oParent[sIdKey]] = "context";
						}
						oParent = mRowById[oParent[sParentKey]];
					}
				});
			}

			var mNodeById = {},
				aNodes = [];

			aRows.forEach(function (oRow) {
				if (mKeep && !mKeep[oRow[sIdKey]]) {
					return;
				}
				var oNode = Object.assign({}, oRow);
				oNode.children = [];
				oNode.isMatch = !mKeep || mKeep[oRow[sIdKey]] === "match";
				mNodeById[oRow[sIdKey]] = oNode;
			});

			Object.keys(mNodeById).forEach(function (sId) {
				var oNode = mNodeById[sId],
					oParent = mNodeById[oNode[sParentKey]];

				// A node whose parent is absent becomes a root. That is correct
				// rather than a bug to hide: the parent may be a company master
				// this user is not allowed to see, and the alternative is
				// dropping the child entirely.
				if (oParent && oParent !== oNode) {
					oParent.children.push(oNode);
				} else {
					aNodes.push(oNode);
				}
			});

			function sort(aList) {
				aList.sort(function (a, b) {
					return String(a[sSortKey] || "").localeCompare(String(b[sSortKey] || ""));
				});
				aList.forEach(function (oNode) {
					sort(oNode.children);
				});
			}
			sort(aNodes);

			return {
				nodes: aNodes,
				total: Object.keys(mNodeById).length,
				matched: fnMatches ? iMatched : Object.keys(mNodeById).length
			};
		},

		/** Depth of the deepest branch, so a view can expand the whole tree. */
		depth: function (aNodes) {
			var iMax = 0;
			(aNodes || []).forEach(function (oNode) {
				var iChild = oNode.children && oNode.children.length
					? this.depth(oNode.children)
					: 0;
				iMax = Math.max(iMax, 1 + iChild);
			}.bind(this));
			return iMax;
		}
	};
});
