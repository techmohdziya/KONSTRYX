sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/model/TreeBuilder",
	"sap/ui/model/json/JSONModel",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, TreeBuilder, JSONModel, MessageBox, MessageToast) {
	"use strict";

	/**
	 * CBS library. Deliberately the same shape as the resource hierarchy: both
	 * are scoped masters with the same promotion path and the same parent-linked
	 * structure, the backend treats them identically, and the screens should not
	 * invent differences.
	 *
	 * Both are trees rather than lists because in both cases the nesting is the
	 * meaning. A CBS sorted flat by code says nothing about what rolls up into
	 * what, which is the only reason a cost breakdown structure exists.
	 */
	return BaseController.extend("konstryx.controller.MasterCBS", {

		onInit: function () {
			this.getView().setModel(new JSONModel({ nodes: [] }), "tree");
			this.getRouter().getRoute("masterCBS").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function () {
			this.setNavKey("masters");
			this._load();
		},

		_load: function () {
			var oList = this.getModel("md").bindList("/CBSLibrary", null, null, null, {
				$select: "ID,code,level,parent_ID,phase,constructionType,scope",
				$expand: "owningCompany($select=code,legalName)"
			});

			oList.requestContexts(0, 2000).then(function (aContexts) {
				this._aRows = aContexts.map(function (oContext) {
					return oContext.getObject();
				});
				this._rebuild();
			}.bind(this)).catch(function (oError) {
				MessageBox.error(oError.message || "The CBS library could not be read.");
			});
		},

		/**
		 * Filtering a tree keeps the ancestors of every match, so a hit still
		 * shows where it sits. A level filter is the clearest case: asking for L3
		 * and getting five bare rows tells you nothing about which L1 each
		 * belongs to.
		 */
		_rebuild: function () {
			var sScope = this.byId("scopeFilter").getSelectedKey(),
				sLevel = this.byId("levelFilter").getSelectedKey(),
				sQuery = (this.byId("cbsSearch").getValue() || "").trim().toLowerCase(),
				bFiltering = (sScope && sScope !== "ALL")
					|| (sLevel && sLevel !== "ALL")
					|| !!sQuery;

			var fnMatches = !bFiltering ? null : function (oRow) {
				if (sScope && sScope !== "ALL" && oRow.scope !== sScope) {
					return false;
				}
				if (sLevel && sLevel !== "ALL" && oRow.level !== sLevel) {
					return false;
				}
				if (sQuery) {
					var sHaystack = (oRow.code || "") + " " + (oRow.phase || "");
					if (sHaystack.toLowerCase().indexOf(sQuery) === -1) {
						return false;
					}
				}
				return true;
			};

			var oTree = TreeBuilder.build(this._aRows || [], {
				idKey: "ID",
				parentKey: "parent_ID",
				sortKey: "code",
				matches: fnMatches
			});

			this.getModel("tree").setData({ nodes: oTree.nodes });
			this.byId("tableTitle").setText(bFiltering
				? "CBS nodes (" + oTree.matched + " of " + (this._aRows || []).length + ")"
				: "CBS nodes (" + oTree.total + ")");

			var oTable = this.byId("cbsTree");
			if (oTable) {
				oTable.expandToLevel(TreeBuilder.depth(oTree.nodes));
			}
		},

		onFilterChange: function () { this._rebuild(); },
		onSearch:       function () { this._rebuild(); },
		onExpandAll:    function () {
			this.byId("cbsTree").expandToLevel(
				TreeBuilder.depth(this.getModel("tree").getProperty("/nodes")));
		},
		onCollapseAll:  function () { this.byId("cbsTree").collapseAll(); },

		onSelect: function (oEvent) {
			var oCtx = oEvent.getParameter("rowContext");
			if (!oCtx) {
				return;
			}
			var oRow = oCtx.getObject(),
				bPromotable = oRow.scope === "COMPANY";

			this._oSelected = oRow;
			this.byId("promoteButton").setEnabled(bPromotable);
			this.byId("selectionHint").setText(bPromotable
				? oRow.code + " is local to "
					+ ((oRow.owningCompany && oRow.owningCompany.code) || "its company")
					+ " and can be promoted to group scope."
				: oRow.code + " is already shared across the group.");
		},

		onRequestPromotion: function () {
			var oRow = this._oSelected;
			if (!oRow) {
				return;
			}

			// The tree model is a plain client-side copy, so the bound action
			// needs a real OData context.
			var oCtx = this.getModel("md")
				.bindContext("/CBSLibrary(ID=" + oRow.ID + ",IsActiveEntity=true)")
				.getBoundContext();

			MessageBox.confirm(
				"Request that " + oRow.code + " be shared across the whole group?",
				{
					title: "Request promotion",
					emphasizedAction: MessageBox.Action.OK,
					onClose: function (sAction) {
						if (sAction !== MessageBox.Action.OK) {
							return;
						}
						var oOperation = this.getModel("md").bindContext(
							"MasterDataService.requestPromotion(...)", oCtx);
						oOperation.setParameter("reason", "Requested from the CBS library");
						oOperation.execute().then(function () {
							MessageToast.show(oOperation.getBoundContext().getValue());
							this._load();
						}.bind(this)).catch(function (oError) {
							MessageBox.error(oError.message || "The request could not be raised.");
						});
					}.bind(this)
				}
			);
		}
	});
});
