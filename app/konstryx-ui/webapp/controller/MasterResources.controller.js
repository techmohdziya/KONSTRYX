sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, Filter, FilterOperator, MessageBox, MessageToast) {
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
			this.getRouter().getRoute("masterResources").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function () {
			this.setNavKey("masters");
			this._applyFilters();
		},

		/** Filters go to the service; the client never holds the full master list. */
		_applyFilters: function () {
			var oTable = this.byId("resourceTable"),
				oBinding = oTable && oTable.getBinding("items");

			if (!oBinding) {
				return;
			}

			var aFilters = [],
				sScope = this.byId("scopeFilter").getSelectedKey(),
				sVertical = this.byId("verticalFilter").getSelectedKey(),
				sQuery = (this.byId("masterSearch").getValue() || "").trim();

			if (sScope && sScope !== "ALL") {
				aFilters.push(new Filter("scope", FilterOperator.EQ, sScope));
			}
			if (sVertical && sVertical !== "ALL") {
				aFilters.push(new Filter("verticalType", FilterOperator.EQ, sVertical));
			}
			if (sQuery) {
				aFilters.push(new Filter({
					filters: [
						new Filter("code", FilterOperator.Contains, sQuery),
						new Filter("description", FilterOperator.Contains, sQuery)
					],
					and: false
				}));
			}

			oBinding.filter(aFilters);
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId("tableTitle").setText("Resources (" + oBinding.getLength() + ")");
			}, this);
		},

		onFilterChange: function () { this._applyFilters(); },
		onSearch:       function () { this._applyFilters(); },

		/**
		 * Promotion applies only to a company-scoped master. A group master is
		 * already shared and the service rejects the request, so the button stays
		 * disabled rather than offering an action that cannot succeed.
		 */
		onSelect: function (oEvent) {
			var oCtx = oEvent.getParameter("listItem").getBindingContext("md"),
				bPromotable = oCtx.getProperty("scope") === "COMPANY";

			this._oSelected = oCtx;
			this.byId("promoteButton").setEnabled(bPromotable);
			this.byId("selectionHint").setText(bPromotable
				? oCtx.getProperty("code") + " is local to "
					+ (oCtx.getProperty("owningCompany/code") || "its company")
					+ " and can be promoted to group scope."
				: oCtx.getProperty("code") + " is already shared across the group.");
		},

		/** Row press opens the master; selection stays for the promotion action. */
		onNavigateToDetail: function (oEvent) {
			var oCtx = oEvent.getSource().getBindingContext("md");
			this.navTo("resourceDetail", { code: encodeURIComponent(oCtx.getProperty("code")) });
		},

		onRequestPromotion: function () {
			var oCtx = this._oSelected;
			if (!oCtx) {
				return;
			}
			var sCode = oCtx.getProperty("code");

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
						}).catch(function (oError) {
							MessageBox.error(oError.message || "The request could not be raised.");
						});
					}.bind(this)
				}
			);
		}
	});
});
