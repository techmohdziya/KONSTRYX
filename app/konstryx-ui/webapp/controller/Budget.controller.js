sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/m/Dialog",
	"sap/m/Button",
	"sap/m/Input",
	"sap/m/DatePicker",
	"sap/m/Label",
	"sap/m/VBox",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, Filter, FilterOperator, Dialog, Button, Input, DatePicker, Label,
             VBox, MessageBox, MessageToast) {
	"use strict";

	/**
	 * Project Budgets worklist. One project can carry more than one Budget
	 * document over its life (a provisional V1 during mobilization, a detailed
	 * V2 once the BOQ prices out) — this is the entry point to any of them, and
	 * to creating the next one.
	 */
	return BaseController.extend("konstryx.controller.Budget", {

		onInit: function () {
			this.getRouter().getRoute("budget").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function (oEvent) {
			this.setNavKey("projects");
			this._sProjectId = oEvent.getParameter("arguments").projectId;
			this._loadProject().then(this._applyFilter.bind(this));
		},

		/** The project's own company drives Budget.company_ID at creation — never asked twice. */
		_loadProject: function () {
			var that = this;
			return this.getModel("pj").bindList("/Projects", null, null, null, {
				$filter: "ID eq " + this._sProjectId + " and IsActiveEntity eq true",
				$select: "ID,code,name,company_ID"
			}).requestContexts(0, 1).then(function (aContexts) {
				if (!aContexts.length) {
					return;
				}
				var oProject = aContexts[0].getObject();
				that._sCompanyId = oProject.company_ID;
				that.byId("budgetTitle").setText("Project Budgets — " + oProject.code + " " + oProject.name);
			});
		},

		_applyFilter: function () {
			var oBinding = this.byId("budgetTable").getBinding("items");
			if (!oBinding) {
				return;
			}
			// Attach before filter/refresh: an already in-flight response can
			// otherwise fire dataReceived first, while the new request's rows
			// are still empty, and the count sticks at 0 (seen live — the
			// header read "Budgets (0)" while the row rendered correctly).
			// getAllCurrentContexts() rather than getLength() for the same
			// reason: it reflects what is actually materialised.
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId("budgetTableTitle").setText(
					"Budgets (" + oBinding.getAllCurrentContexts().length + ")");
			}, this);
			oBinding.filter([new Filter("project_ID", FilterOperator.EQ, this._sProjectId)]);
			oBinding.refresh();
		},

		onOpenBudget: function (oEvent) {
			var oCtx = oEvent.getSource().getBindingContext("bud");
			this.navTo("budgetDetail", {
				projectId: this._sProjectId,
				budgetId: oCtx.getProperty("ID")
			});
		},

		onExportExcel: function () {
			var oBinding = this.byId("budgetTable").getBinding("items");
			if (!oBinding) {
				return;
			}
			var aRows = oBinding.getAllCurrentContexts().map(function (c) { return c.getObject(); });
			sap.ui.require(["sap/ui/export/Spreadsheet"], function (Spreadsheet) {
				new Spreadsheet({
					workbook: {
						columns: [
							{ label: "Document", property: "docNo" },
							{ label: "Version", property: "version" },
							{ label: "Status", property: "status" },
							{ label: "Total Amount", property: "totalAmount" },
							{ label: "Days to Lock", property: "daysToLock" },
							{ label: "Raised by", property: "raisedBy" },
							{ label: "Raised on", property: "raisedOn" }
						]
					},
					dataSource: aRows,
					fileName: "project-budgets.xlsx"
				}).build();
			});
		},

		/**
		 * The header a new Budget document needs. Raised by / on are asked here
		 * rather than guessed — nothing in this app currently exposes who the
		 * logged-in user is to client-side code (Basic Auth carries it to the
		 * server, not to the browser), so the person creating the document
		 * states it, the way they would fill in a paper form's letterhead.
		 */
		onNewBudget: function () {
			var oVersion = new Input({ value: "V1", placeholder: "e.g. V1" }),
				oRaisedBy = new Input({ placeholder: "Your name" }),
				oRaisedOn = new DatePicker({ value: new Date().toISOString().slice(0, 10), valueFormat: "yyyy-MM-dd", displayFormat: "medium" }),
				that = this;

			var oDialog = new Dialog({
				title: "New Budget",
				contentWidth: "24rem",
				content: [
					new VBox({
						items: [
							new Label({ text: "Version" }), oVersion,
							new Label({ text: "Raised by" }).addStyleClass("sapUiSmallMarginTop"), oRaisedBy,
							new Label({ text: "Raised on" }).addStyleClass("sapUiSmallMarginTop"), oRaisedOn
						]
					}).addStyleClass("sapUiSmallMargin")
				],
				beginButton: new Button({
					text: "Create", type: "Emphasized",
					press: function () {
						var sVersion = oVersion.getValue().trim(),
							sRaisedBy = oRaisedBy.getValue().trim(),
							sRaisedOn = oRaisedOn.getValue();
						if (!sVersion || !sRaisedBy || !sRaisedOn) {
							MessageBox.warning("Version, raised by and raised on are all required.");
							return;
						}
						oDialog.close();
						that._createBudget(sVersion, sRaisedBy, sRaisedOn);
					}
				}),
				endButton: new Button({ text: "Cancel", press: function () { oDialog.close(); } }),
				afterClose: function () { oDialog.destroy(); }
			});

			this.getView().addDependent(oDialog);
			oDialog.open();
		},

		_createBudget: function (sVersion, sRaisedBy, sRaisedOn) {
			var oModel = this.getModel("bud"),
				that = this;

			var oCreated = oModel.bindList("/Budgets").create({
				project_ID: this._sProjectId,
				company_ID: this._sCompanyId,
				version: sVersion,
				raisedBy: sRaisedBy,
				raisedOn: sRaisedOn
			});

			oCreated.created().then(function () {
				var oActivate = oModel.bindContext("BudgetService.draftActivate(...)", oCreated);
				return oActivate.execute().then(function () {
					var oResult = oActivate.getBoundContext().getObject();
					MessageToast.show("Budget " + (oResult.docNo || "") + " created.");
					that.navTo("budgetDetail", { projectId: that._sProjectId, budgetId: oResult.ID });
				});
			}).catch(function (oError) {
				MessageBox.error(oError.message || "The budget could not be created.");
			});
		}
	});
});
