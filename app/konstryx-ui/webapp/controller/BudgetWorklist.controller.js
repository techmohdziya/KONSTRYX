sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/lib/ListPersonalization",
	"sap/ui/model/json/JSONModel",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/ui/export/library"
], function (BaseController, ListPersonalization, JSONModel, Filter, FilterOperator, exportLibrary) {
	"use strict";

	/**
	 * Every project's budget, portfolio-wide — the launchpad entry point for
	 * Budget, matching the way Resource Requests already has its own
	 * cross-project worklist rather than requiring "open a project first".
	 *
	 * Read-only by design: creating a budget needs a project decided first
	 * (and its company), so that stays on the per-project Budget screen
	 * reached from a project's own Budget link. This screen is for finding
	 * and opening one, across every project at once.
	 */
	return BaseController.extend("konstryx.controller.BudgetWorklist", {

		onInit: function () {
			this.getView().setModel(new JSONModel({ projectById: {} }), "view");
			this.getRouter().getRoute("budgets").attachPatternMatched(this._onMatched, this);
			this._setUpPersonalization();
		},

		_onMatched: function () {
			this.setNavKey("projects");
			this._loadProjects().then(this._applyFilters.bind(this));
		},

		/**
		 * Budgets.project is an association whose target (prj.Project) is not
		 * exposed by BudgetService — cannot $expand or dot-navigate across a
		 * service boundary in OData v4 — so the project's code/name are
		 * resolved client-side from project_ID via a lookup built here, the
		 * same pattern used for CBS codes on the Budget detail screen.
		 */
		_loadProjects: function () {
			var that = this;
			return this.getModel("pj").bindList("/Projects", null, null, null, {
				$filter: "IsActiveEntity eq true",
				$select: "ID,code,name"
			}).requestContexts(0, 500).then(function (aContexts) {
				var oMap = {};
				aContexts.forEach(function (c) {
					var o = c.getObject();
					oMap[o.ID] = { code: o.code, name: o.name };
				});
				that.getView().getModel("view").setProperty("/projectById", oMap);
			});
		},

		formatProjectTitle: function (sProjectId, oMap) {
			var o = oMap && oMap[sProjectId];
			return o ? o.name : "";
		},

		formatProjectCode: function (sProjectId, oMap) {
			var o = oMap && oMap[sProjectId];
			return o ? o.code : sProjectId || "";
		},

		_setUpPersonalization: function () {
			var EdmType = exportLibrary.EdmType;
			this._aFields = [
				{ key: "project_ID",  label: "Project",     path: "project_ID",  edm: EdmType.String, width: 16 },
				{ key: "docNo",       label: "Document",    path: "docNo",       edm: EdmType.String, width: 14 },
				{ key: "version",     label: "Version",     path: "version",     edm: EdmType.String, width: 7 },
				{ key: "status",      label: "Status",      path: "status",      edm: EdmType.String, width: 10 },
				{ key: "totalAmount", label: "Total Amount",path: "totalAmount", edm: EdmType.Number, width: 16 },
				{ key: "daysToLock",  label: "Days to Lock",path: "daysToLock",  edm: EdmType.Number, width: 10 },
				{ key: "raisedBy",    label: "Raised by",   path: "raisedBy",    edm: EdmType.String, width: 16 },
				{ key: "raisedOn",    label: "Raised on",   path: "raisedOn",    edm: EdmType.String, width: 10 }
			];
			ListPersonalization.attach({
				target: "budgets.worklist", table: this.byId("budgetsTable"), variant: this.byId("budgetsVariant"),
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
			var oBinding = this.byId("budgetsTable").getBinding("items");
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
					"Budgets (" + oBinding.getAllCurrentContexts().length + ")");
			}, this);
			oBinding.filter(aFilters);
			oBinding.refresh();
		},

		onFilterChange: function () { this._applyFilters(); },
		onAdaptFilters: function () { ListPersonalization.openSettings(this.byId("budgetsTable"), ["Filter"]); },
		onTableSettings: function () {
			ListPersonalization.openSettings(this.byId("budgetsTable"), ["Columns", "Sorter", "Groups", "Filter"]);
		},
		onVariantSelect: function (oEvent) {
			ListPersonalization.selectVariant("budgets.worklist", oEvent.getParameter("key"));
		},
		onVariantSave: function (oEvent) {
			ListPersonalization.saveVariant("budgets.worklist", oEvent);
		},

		onExportExcel: function () {
			var oBinding = this.byId("budgetsTable").getBinding("items"),
				that = this;
			if (!oBinding) { return; }
			var aRows = oBinding.getAllCurrentContexts().map(function (c) {
				var o = Object.assign({}, c.getObject());
				o.project_ID = that.formatProjectCode(o.project_ID,
					that.getView().getModel("view").getProperty("/projectById"));
				return o;
			});
			ListPersonalization.exportToExcel("budgets.worklist", aRows, "budgets");
		},

		onOpenBudget: function (oEvent) {
			var oCtx = oEvent.getSource().getBindingContext("bud");
			this.navTo("budgetDetail", {
				projectId: oCtx.getProperty("project_ID"),
				budgetId: oCtx.getProperty("ID")
			});
		}
	});
});
