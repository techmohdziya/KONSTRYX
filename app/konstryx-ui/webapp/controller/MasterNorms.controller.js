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
	 * Productivity and consumption norms.
	 *
	 * These two sit on one screen because they are two halves of the same
	 * derivation: output achieved against the productivity norm gives earned
	 * value, and that same output against the consumption norm gives theoretical
	 * material usage, which is what site consumption is reconciled against.
	 * Maintaining them apart is how the two drift.
	 *
	 * Two independent tables means two independent personalization targets —
	 * each keeps its own saved views, since a productivity layout has nothing
	 * to do with a consumption one.
	 */
	return BaseController.extend("konstryx.controller.MasterNorms", {

		onInit: function () {
			this.getRouter().getRoute("masterNorms").attachPatternMatched(this._onMatched, this);
			this._setUpPersonalization();
		},

		_onMatched: function () {
			this.setNavKey("masters");
			this._count("prodTable", "prodTitle", "Productivity norms");
			this._count("consTable", "consTitle", "Consumption norms");
		},

		_count: function (sTable, sTitle, sLabel) {
			var oBinding = this.byId(sTable) && this.byId(sTable).getBinding("items");
			if (!oBinding) {
				return;
			}
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId(sTitle).setText(sLabel + " (" + oBinding.getLength() + ")");
			}, this);
		},

		_setUpPersonalization: function () {
			var EdmType = exportLibrary.EdmType;

			this._aProdFields = [
				{ key: "resource",          label: "Resource",         path: "resource/code",       edm: EdmType.String, width: 14 },
				{ key: "crewComposition",   label: "Crew composition", path: "crewComposition",     edm: EdmType.String, width: 20 },
				{ key: "outputPerHr",       label: "Per hour",          path: "outputPerHr",         edm: EdmType.Number, width: 10 },
				{ key: "outputPerManday8h", label: "Per 8h man-day",    path: "outputPerManday8h",   edm: EdmType.Number, width: 12 },
				{ key: "prodBasis",         label: "Basis",             path: "basis",               edm: EdmType.String, width: 12 },
				{ key: "prodScope",         label: "Scope",             path: "scope",               edm: EdmType.String, width: 10 }
			];
			this._aConsFields = [
				{ key: "material",              label: "Material",   path: "material/code",       edm: EdmType.String, width: 14 },
				{ key: "consRate",               label: "Rate",        path: "consRate",             edm: EdmType.Number, width: 12 },
				{ key: "wastageAllowancePct",   label: "Wastage",     path: "wastageAllowancePct", edm: EdmType.Number, width: 10 },
				{ key: "consBasis",              label: "Basis",       path: "basis",               edm: EdmType.String, width: 12 },
				{ key: "consScope",              label: "Scope",       path: "scope",               edm: EdmType.String, width: 10 },
				{ key: "owningCompany",          label: "Owned by",    path: "owningCompany/code",  edm: EdmType.String, width: 16 }
			];

			ListPersonalization.attach({
				target: "masters.norms.productivity",
				table: this.byId("prodTable"),
				variant: this.byId("prodVariant"),
				fields: this._aProdFields,
				controller: this,
				onApply: this._applyState.bind(this, "prodTable")
			});
			ListPersonalization.attach({
				target: "masters.norms.consumption",
				table: this.byId("consTable"),
				variant: this.byId("consVariant"),
				fields: this._aConsFields,
				controller: this,
				onApply: this._applyState.bind(this, "consTable")
			});
		},

		_applyState: function (sTableId, oState) {
			var oBinding = this.byId(sTableId).getBinding("items");
			if (!oBinding) {
				return;
			}
			var aSorters = [];
			(oState.Groups || []).forEach(function (g) {
				aSorters.push(new sap.ui.model.Sorter(g.key, false, true));
			});
			(oState.Sorter || []).forEach(function (srt) {
				aSorters.push(new sap.ui.model.Sorter(srt.key, !!srt.descending));
			});
			oBinding.sort(aSorters);

			var aFilters = [];
			Object.keys(oState.Filter || {}).forEach(function (sKey) {
				(oState.Filter[sKey] || []).forEach(function (oCond) {
					var v = (oCond.values || [])[0];
					if (v !== undefined && v !== null && v !== "") {
						aFilters.push(new Filter(sKey, FilterOperator.Contains, String(v)));
					}
				});
			});
			oBinding.filter(aFilters);
		},

		onProdResourceLink: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("md").getObject();
			ObjectLinks.open(this, "resource", oRow.resource || {}, oEvent.getSource());
		},

		onProdTableSettings: function () {
			ListPersonalization.openSettings(this.byId("prodTable"), ["Columns", "Sorter", "Groups", "Filter"]);
		},
		onProdAdaptFilters: function () {
			ListPersonalization.openSettings(this.byId("prodTable"), ["Filter"]);
		},
		onProdVariantSelect: function (oEvent) {
			ListPersonalization.selectVariant("masters.norms.productivity", oEvent.getParameter("key"));
		},
		onProdVariantSave: function (oEvent) {
			ListPersonalization.saveVariant("masters.norms.productivity", oEvent);
		},
		onProdExportExcel: function () {
			var oBinding = this.byId("prodTable").getBinding("items");
			if (!oBinding) { return; }
			var aRows = oBinding.getAllCurrentContexts().map(function (c) { return c.getObject(); });
			ListPersonalization.exportToExcel("masters.norms.productivity", aRows, "productivity-norms");
		},

		onConsResourceLink: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("md").getObject();
			ObjectLinks.open(this, "resource", oRow.material || {}, oEvent.getSource());
		},

		onConsTableSettings: function () {
			ListPersonalization.openSettings(this.byId("consTable"), ["Columns", "Sorter", "Groups", "Filter"]);
		},
		onConsAdaptFilters: function () {
			ListPersonalization.openSettings(this.byId("consTable"), ["Filter"]);
		},
		onConsVariantSelect: function (oEvent) {
			ListPersonalization.selectVariant("masters.norms.consumption", oEvent.getParameter("key"));
		},
		onConsVariantSave: function (oEvent) {
			ListPersonalization.saveVariant("masters.norms.consumption", oEvent);
		},
		onConsExportExcel: function () {
			var oBinding = this.byId("consTable").getBinding("items");
			if (!oBinding) { return; }
			var aRows = oBinding.getAllCurrentContexts().map(function (c) { return c.getObject(); });
			ListPersonalization.exportToExcel("masters.norms.consumption", aRows, "consumption-norms");
		}
	});
});
