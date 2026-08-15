sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator"
], function (BaseController, Filter, FilterOperator) {
	"use strict";

	/**
	 * Rate master.
	 *
	 * Rates are effective-dated rather than edited in place: a revision is a new
	 * row with a later effectiveFrom, so a posting made last year keeps the rate
	 * it was costed at. The list therefore shows several rows per resource, most
	 * recent first, and the effective date is the column that matters.
	 */
	return BaseController.extend("konstryx.controller.MasterRates", {

		onInit: function () {
			this.getRouter().getRoute("masterRates").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function () {
			this.setNavKey("masters");
			this._applyFilters();
		},

		_applyFilters: function () {
			var oBinding = this.byId("rateTable") && this.byId("rateTable").getBinding("items");
			if (!oBinding) {
				return;
			}

			var aFilters = [],
				sScope = this.byId("scopeFilter").getSelectedKey(),
				sEffective = this.byId("effectiveFilter").getSelectedKey(),
				sQuery = (this.byId("rateSearch").getValue() || "").trim(),
				sToday = this.getData().project.dataDate;

			if (sScope && sScope !== "ALL") {
				aFilters.push(new Filter("scope", FilterOperator.EQ, sScope));
			}
			if (sEffective === "CURRENT") {
				aFilters.push(new Filter("effectiveFrom", FilterOperator.LE, sToday));
			} else if (sEffective === "FUTURE") {
				aFilters.push(new Filter("effectiveFrom", FilterOperator.GT, sToday));
			}
			if (sQuery) {
				aFilters.push(new Filter("resource/code", FilterOperator.Contains, sQuery));
			}

			oBinding.filter(aFilters);
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId("tableTitle").setText("Rates (" + oBinding.getLength() + ")");
			}, this);
		},

		onFilterChange: function () { this._applyFilters(); },
		onSearch:       function () { this._applyFilters(); }
	});
});
