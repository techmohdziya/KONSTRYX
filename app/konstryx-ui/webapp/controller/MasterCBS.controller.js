sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, Filter, FilterOperator, MessageBox, MessageToast) {
	"use strict";

	/**
	 * CBS library list. Deliberately the same shape as the resource hierarchy:
	 * both are scoped masters with the same promotion path, and the backend
	 * treats them identically, so the screens should not invent differences.
	 */
	return BaseController.extend("konstryx.controller.MasterCBS", {

		onInit: function () {
			this.getRouter().getRoute("masterCBS").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function () {
			this.setNavKey("masters");
			this._applyFilters();
		},

		_applyFilters: function () {
			var oBinding = this.byId("cbsTable") && this.byId("cbsTable").getBinding("items");
			if (!oBinding) {
				return;
			}

			var aFilters = [],
				sScope = this.byId("scopeFilter").getSelectedKey(),
				sLevel = this.byId("levelFilter").getSelectedKey(),
				sQuery = (this.byId("cbsSearch").getValue() || "").trim();

			if (sScope && sScope !== "ALL") {
				aFilters.push(new Filter("scope", FilterOperator.EQ, sScope));
			}
			if (sLevel && sLevel !== "ALL") {
				aFilters.push(new Filter("level", FilterOperator.EQ, sLevel));
			}
			if (sQuery) {
				aFilters.push(new Filter({
					filters: [
						new Filter("code", FilterOperator.Contains, sQuery),
						new Filter("phase", FilterOperator.Contains, sQuery)
					],
					and: false
				}));
			}

			oBinding.filter(aFilters);
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId("tableTitle").setText("CBS nodes (" + oBinding.getLength() + ")");
			}, this);
		},

		onFilterChange: function () { this._applyFilters(); },
		onSearch:       function () { this._applyFilters(); },

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

		onRequestPromotion: function () {
			var oCtx = this._oSelected;
			if (!oCtx) {
				return;
			}
			MessageBox.confirm(
				"Request that " + oCtx.getProperty("code") + " be shared across the whole group?",
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
						}).catch(function (oError) {
							MessageBox.error(oError.message || "The request could not be raised.");
						});
					}.bind(this)
				}
			);
		}
	});
});
