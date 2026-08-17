sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/json/JSONModel",
	"sap/m/MessageBox"
], function (BaseController, JSONModel, MessageBox) {
	"use strict";

	/**
	 * Cost Mapping across the portfolio: which projects still need a human.
	 *
	 * The per-project workbench stays exactly as it was — this is the other
	 * view onto the same read, for whoever runs several jobs rather than one.
	 * It shows counts only and no exception rows: the question here is which
	 * project to open, not what to do inside it.
	 *
	 * The server returns only the projects the user may see (the portfolio
	 * action reads through the application service, so the authorization
	 * layer's instance filter applies) — this screen does no scoping of its own.
	 */
	return BaseController.extend("konstryx.controller.CostMappingPortfolio", {

		onInit: function () {
			this.getView().setModel(new JSONModel({ rows: [], all: [] }), "view");
			this.getRouter().getRoute("costMappingPortfolio")
				.attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function () {
			this.setNavKey("projects");
			this._load();
		},

		_load: function () {
			var oModel = this.getModel("pj"),
				that = this,
				oOperation = oModel.bindContext("/costMappingPortfolio(...)");

			oOperation.execute().then(function () {
				var vValue = oOperation.getBoundContext().getValue(),
					aRows = (vValue && vValue.value) || vValue || [];
				that.getView().getModel("view").setProperty("/all", aRows);
				that._applyFilter();
			}).catch(function (oError) {
				MessageBox.error(oError.message || "The portfolio could not be read.");
			});
		},

		_applyFilter: function () {
			var oViewModel = this.getView().getModel("view"),
				aAll = oViewModel.getProperty("/all") || [],
				sKey = this.byId("readyFilter").getSelectedKey(),
				aRows = aAll;

			if (sKey === "READY") {
				aRows = aAll.filter(function (r) { return r.budgetReady; });
			} else if (sKey === "ATTENTION") {
				// A project with no bill at all is not "attention" — there is
				// nothing to map yet. Attention means mapping work outstanding.
				aRows = aAll.filter(function (r) {
					return r.totalLines > 0 && !r.budgetReady;
				});
			}

			oViewModel.setProperty("/rows", aRows);
			this.byId("portfolioTitle").setText("Projects (" + aRows.length + ")");
		},

		onFilterChange: function () { this._applyFilter(); },

		onRefresh: function () { this._load(); },

		onOpenProject: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("view").getObject();
			this.navTo("costMapping", { projectId: oRow.projectId });
		},

		onExportExcel: function () {
			var aRows = this.getView().getModel("view").getProperty("/rows") || [];
			sap.ui.require(["sap/ui/export/Spreadsheet"], function (Spreadsheet) {
				new Spreadsheet({
					workbook: {
						columns: [
							{ label: "Project code", property: "projectCode" },
							{ label: "Project", property: "projectName" },
							{ label: "Stage", property: "stage" },
							{ label: "Bill lines", property: "totalLines" },
							{ label: "CBS open", property: "cbsOpen" },
							{ label: "WBS open", property: "wbsOpen" },
							{ label: "Resources open", property: "resOpen" },
							{ label: "Exceptions", property: "exceptionCount" },
							{ label: "Gate rules failing", property: "gateFailing" },
							{ label: "Budget ready", property: "budgetReady" }
						]
					},
					dataSource: aRows,
					fileName: "cost-mapping-portfolio.xlsx"
				}).build();
			});
		}
	});
});
