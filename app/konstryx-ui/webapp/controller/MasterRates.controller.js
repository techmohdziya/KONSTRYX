sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/lib/ListPersonalization",
	"konstryx/lib/ObjectLinks",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/ui/export/library"
], function (BaseController, ListPersonalization, ObjectLinks, Filter, FilterOperator, exportLibrary) {
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
			this._setUpPersonalization();
		},

		_onMatched: function () {
			this.setNavKey("masters");
			this._applyFilters();
		},

		/** Columns, sort, group, filter, saved views and download — one declaration. */
		_setUpPersonalization: function () {
			var EdmType = exportLibrary.EdmType;

			this._aFields = [
				{ key: "resource",      label: "Resource",       path: "resource/code",         edm: EdmType.String,  width: 14 },
				{ key: "description",   label: "Description",    path: "resource/description",  edm: EdmType.String,  width: 28 },
				{ key: "rateValue",     label: "Rate",            path: "rateValue",             edm: EdmType.Number,  width: 10 },
				{ key: "basis",         label: "Basis",           path: "basis",                 edm: EdmType.String,  width: 8 },
				{ key: "effectiveFrom", label: "Effective from",  path: "effectiveFrom",         edm: EdmType.Date,    width: 12 },
				{ key: "scope",         label: "Scope",           path: "scope",                 edm: EdmType.String,  width: 10 },
				{ key: "owningCompany", label: "Owned by",        path: "owningCompany/code",    edm: EdmType.String,  width: 16 }
			];

			ListPersonalization.attach({
				target: "masters.rates",
				table: this.byId("rateTable"),
				variant: this.byId("ratesVariant"),
				fields: this._aFields,
				controller: this,
				onApply: this._onStateApplied.bind(this)
			});
		},

		/** p13n sort/group/filter state is ANDed with the filter bar, neither replaces the other. */
		_onStateApplied: function (oState) {
			this._aP13nFilters = [];
			Object.keys(oState.Filter || {}).forEach(function (sKey) {
				(oState.Filter[sKey] || []).forEach(function (oCond) {
					var v = (oCond.values || [])[0];
					if (v !== undefined && v !== null && v !== "") {
						this._aP13nFilters.push(new Filter(sKey, FilterOperator.Contains, String(v)));
					}
				}, this);
			}, this);

			this._aP13nSorters = [];
			(oState.Groups || []).forEach(function (g) {
				this._aP13nSorters.push(new sap.ui.model.Sorter(g.key, false, true));
			}, this);
			(oState.Sorter || []).forEach(function (srt) {
				this._aP13nSorters.push(new sap.ui.model.Sorter(srt.key, !!srt.descending));
			}, this);

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
			aFilters = aFilters.concat(this._aP13nFilters || []);

			oBinding.filter(aFilters);
			if (this._aP13nSorters && this._aP13nSorters.length) {
				oBinding.sort(this._aP13nSorters);
			}
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId("tableTitle").setText("Rates (" + oBinding.getLength() + ")");
			}, this);
		},

		onFilterChange: function () { this._applyFilters(); },
		onSearch:       function () { this._applyFilters(); },

		onResourceLink: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("md").getObject();
			ObjectLinks.open(this, "resource", oRow.resource || {}, oEvent.getSource());
		},

		onTableSettings: function () {
			ListPersonalization.openSettings(this.byId("rateTable"),
				["Columns", "Sorter", "Groups", "Filter"]);
		},

		onAdaptFilters: function () {
			ListPersonalization.openSettings(this.byId("rateTable"), ["Filter"]);
		},

		onVariantSelect: function (oEvent) {
			ListPersonalization.selectVariant("masters.rates", oEvent.getParameter("key"));
		},

		onVariantSave: function (oEvent) {
			ListPersonalization.saveVariant("masters.rates", oEvent);
		},

		onExportExcel: function () {
			var oBinding = this.byId("rateTable").getBinding("items");
			if (!oBinding) {
				return;
			}
			var aRows = oBinding.getAllCurrentContexts().map(function (c) {
				return c.getObject();
			});
			ListPersonalization.exportToExcel("masters.rates", aRows, "rate-master");
		},

		onPrint: function () {
			ListPersonalization.printView();
		}
	});
});
