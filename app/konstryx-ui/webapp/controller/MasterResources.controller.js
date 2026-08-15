sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/model/TreeBuilder",
	"sap/ui/model/json/JSONModel",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, TreeBuilder, JSONModel, Filter, FilterOperator, MessageBox, MessageToast) {
	"use strict";

	/**
	 * Resource hierarchy master list.
	 *
	 * Reads MasterDataService.Resources directly. What the user sees is already
	 * narrowed by the backend: the authorization grants decide whether they may
	 * read the object at all, and the scoped-master rule hides other companies'
	 * local masters. Nothing here filters for security - the filters below are
	 * the user's own.
	 */
	return BaseController.extend("konstryx.controller.MasterResources", {

		onInit: function () {
			this.getView().setModel(new JSONModel({ nodes: [] }), "tree");
			this.getRouter().getRoute("masterResources").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function () {
			this.setNavKey("masters");
			this._load();
		},

		/**
		 * The whole catalogue is read once and nested on the client.
		 *
		 * A tree cannot be paged the way a list can: to show a leaf you need its
		 * ancestors, and the server would have to be asked for them separately.
		 * A resource catalogue is a few hundred rows of reference data, read far
		 * more often than it changes, so one request is the right trade. If a
		 * client ever arrives with a catalogue large enough for this to hurt,
		 * the answer is server-side hierarchy, not paging this.
		 *
		 * What comes back is still narrowed by the backend: authorization decides
		 * whether the user may read the object at all, and the scoped-master rule
		 * hides other companies' local masters. Nothing here filters for
		 * security — the filters below are the user's own.
		 */
		_load: function () {
			var oList = this.getModel("md").bindList("/Resources", null, null, null, {
				$select: "ID,code,level,parent_ID,verticalType,description,scope,masterStatus",
				$expand: "owningCompany($select=code,legalName)"
			});

			// A large enough page to hold the catalogue in one request; the tree
			// is built from whatever came back.
			oList.requestContexts(0, 2000).then(function (aContexts) {
				this._aRows = aContexts.map(function (oContext) {
					return oContext.getObject();
				});
				this._rebuild();
			}.bind(this)).catch(function (oError) {
				MessageBox.error(oError.message || "The resource catalogue could not be read.");
			});
		},

		/** Filters are applied to the loaded rows, keeping ancestors of matches. */
		_rebuild: function () {
			var sScope = this.byId("scopeFilter").getSelectedKey(),
				sVertical = this.byId("verticalFilter").getSelectedKey(),
				sQuery = (this.byId("masterSearch").getValue() || "").trim().toLowerCase(),
				bFiltering = (sScope && sScope !== "ALL")
					|| (sVertical && sVertical !== "ALL")
					|| !!sQuery;

			var fnMatches = !bFiltering ? null : function (oRow) {
				if (sScope && sScope !== "ALL" && oRow.scope !== sScope) {
					return false;
				}
				if (sVertical && sVertical !== "ALL" && oRow.verticalType !== sVertical) {
					return false;
				}
				if (sQuery) {
					var sHaystack = (oRow.code || "") + " " + (oRow.description || "");
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
				? "Resources (" + oTree.matched + " of " + (this._aRows || []).length + ")"
				: "Resources (" + oTree.total + ")");

			// Filtering implies the user is looking for something, so open the
			// tree to it rather than making them click down to their own result.
			var oTable = this.byId("resourceTree");
			if (oTable) {
				oTable.expandToLevel(bFiltering ? TreeBuilder.depth(oTree.nodes) : 1);
			}
		},

		onFilterChange: function () { this._rebuild(); },
		onSearch:       function () { this._rebuild(); },
		onExpandAll:    function () {
			this.byId("resourceTree").expandToLevel(
				TreeBuilder.depth(this.getModel("tree").getProperty("/nodes")));
		},
		onCollapseAll:  function () { this.byId("resourceTree").collapseAll(); },

		/**
		 * Promotion applies only to a company-scoped master. A group master is
		 * already shared and the service rejects the request, so the button stays
		 * disabled rather than offering an action that cannot succeed.
		 */
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

		/** Code opens the master; selection stays for the promotion action. */
		onNavigateToDetail: function (oEvent) {
			var oCtx = oEvent.getSource().getBindingContext("tree");
			this.navTo("resourceDetail", { code: encodeURIComponent(oCtx.getProperty("code")) });
		},

		onRequestPromotion: function () {
			var oRow = this._oSelected;
			if (!oRow) {
				return;
			}
			var sCode = oRow.code;

			// The tree model is a plain client-side copy, so the bound action
			// needs a real OData context. Resources is draft-enabled, hence the
			// IsActiveEntity half of the key.
			var oCtx = this.getModel("md")
				.bindContext("/Resources(ID=" + oRow.ID + ",IsActiveEntity=true)")
				.getBoundContext();

			MessageBox.confirm(
				"Request that " + sCode + " be shared across the whole group?\n\n"
					+ "A master data steward decides. Until then it stays local.",
				{
					title: "Request promotion",
					emphasizedAction: MessageBox.Action.OK,
					onClose: function (sAction) {
						if (sAction !== MessageBox.Action.OK) {
							return;
						}
						var oOperation = this.getModel("md").bindContext(
							"MasterDataService.requestPromotion(...)", oCtx);
						oOperation.setParameter("reason", "Requested from the resource hierarchy list");
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
