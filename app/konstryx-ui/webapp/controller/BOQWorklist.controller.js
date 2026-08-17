sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/lib/ListPersonalization",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/ui/export/library"
], function (BaseController, ListPersonalization, Filter, FilterOperator, exportLibrary) {
	"use strict";

	/**
	 * Every project's bill of quantities, portfolio-wide — the launchpad
	 * entry point for BOQ, matching the way Resource Requests already has
	 * its own cross-project worklist. Read-only: a BOQ is imported through
	 * the upload framework on its own project, not created here.
	 */
	return BaseController.extend("konstryx.controller.BOQWorklist", {

		onInit: function () {
			this.getRouter().getRoute("boqWorklist").attachPatternMatched(this._onMatched, this);
			this._setUpPersonalization();
		},

		_onMatched: function () {
			this.setNavKey("projects");
			this._applyFilters();
		},

		_setUpPersonalization: function () {
			var EdmType = exportLibrary.EdmType;
			this._aFields = [
				{ key: "project",       label: "Project",        path: "project/code",  edm: EdmType.String, width: 12 },
				{ key: "boqId",         label: "BOQ",             path: "boqId",         edm: EdmType.String, width: 10 },
				{ key: "version",       label: "Version",         path: "version",       edm: EdmType.String, width: 7 },
				{ key: "status",        label: "Status",          path: "status",        edm: EdmType.String, width: 10 },
				{ key: "source",        label: "Source",          path: "source",        edm: EdmType.String, width: 8 },
				{ key: "contractValue", label: "Contract Value",  path: "contractValue", edm: EdmType.Number, width: 16 }
			];
			ListPersonalization.attach({
				target: "boq.worklist", table: this.byId("boqTable"), variant: this.byId("boqVariant"),
				fields: this._aFields, controller: this, onApply: this._onStateApplied.bind(this)
			});
		},

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
			var oBinding = this.byId("boqTable").getBinding("items");
			if (!oBinding) {
				return;
			}
			var sStatus = this.byId("statusFilter").getSelectedKey(),
				aFilters = [];
			if (sStatus && sStatus !== "ALL") {
				aFilters.push(sStatus === "Draft"
					? new Filter({ filters: [
						new Filter("status", FilterOperator.EQ, null),
						new Filter("status", FilterOperator.EQ, "Draft")
					], and: false })
					: new Filter("status", FilterOperator.EQ, sStatus));
			}
			aFilters = aFilters.concat(this._aP13nFilters || []);
			if (this._aP13nSorters && this._aP13nSorters.length) {
				oBinding.sort(this._aP13nSorters);
			}
			// Attach before filter/refresh: an already in-flight response can
			// otherwise fire dataReceived first, while the new request's rows
			// are still empty, and the count sticks at 0 (seen live).
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId("tableTitle").setText(
					"Bills of Quantities (" + oBinding.getAllCurrentContexts().length + ")");
			}, this);
			oBinding.filter(aFilters);
			oBinding.refresh();
		},

		onFilterChange: function () { this._applyFilters(); },
		onAdaptFilters: function () { ListPersonalization.openSettings(this.byId("boqTable"), ["Filter"]); },
		onTableSettings: function () {
			ListPersonalization.openSettings(this.byId("boqTable"), ["Columns", "Sorter", "Groups", "Filter"]);
		},
		onVariantSelect: function (oEvent) {
			ListPersonalization.selectVariant("boq.worklist", oEvent.getParameter("key"));
		},
		onVariantSave: function (oEvent) {
			ListPersonalization.saveVariant("boq.worklist", oEvent);
		},

		onExportExcel: function () {
			var oBinding = this.byId("boqTable").getBinding("items");
			if (!oBinding) { return; }
			var aRows = oBinding.getAllCurrentContexts().map(function (c) {
				var o = Object.assign({}, c.getObject());
				o["project/code"] = o.project && o.project.code;
				return o;
			});
			ListPersonalization.exportToExcel("boq.worklist", aRows, "boq-worklist");
		},

		onOpenBOQ: function (oEvent) {
			var oCtx = oEvent.getSource().getBindingContext("pj");
			// project_ID (the plain FK) isn't in the response cache once the
			// row also binds through the expanded project/code, project/name
			// nav — confirmed live ("invalid segment: project_ID"); the
			// expanded association's own key is read instead.
			this.navTo("projectBOQ", { projectId: oCtx.getProperty("project/ID") });
		}
	});
});
