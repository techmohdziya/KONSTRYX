sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/json/JSONModel",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, JSONModel, MessageBox, MessageToast) {
	"use strict";

	/**
	 * The Cost Mapping workbench: four step tiles and an exception queue.
	 *
	 * The wireframe's rule is the whole design: the user only resolves
	 * exceptions. Mapped, distributed, resolved lines are counted on the tiles
	 * and never listed. Generate Budget Lines stays disabled while the gate
	 * fails, and its tooltip names the failing rules rather than sulking mutely
	 * (spec UI-04).
	 */
	return BaseController.extend("konstryx.controller.CostMapping", {

		onInit: function () {
			this.getView().setModel(new JSONModel({ exceptions: [] }), "view");
			this.getRouter().getRoute("costMapping").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function (oEvent) {
			this.setNavKey("projects");
			this._sProjectId = oEvent.getParameter("arguments").projectId;
			this._refresh();
		},

		_refresh: function () {
			var oModel = this.getModel("pj"),
				that = this;

			var oOperation = oModel.bindContext("ProjectService.costMappingSummary(...)",
				oModel.bindContext("/Projects(ID=" + this._sProjectId + ",IsActiveEntity=true)")
					.getBoundContext());
			oOperation.execute().then(function () {
				var oSummary = oOperation.getBoundContext().getObject();

				that.byId("numCbs").setValue(oSummary.cbsOpen);
				that.byId("numCbs").setValueColor(oSummary.cbsOpen ? "Critical" : "Good");
				that.byId("tileCbs").setSubheader(oSummary.cbsMapped + " of "
					+ oSummary.totalLines + " mapped");

				that.byId("numWbs").setValue(oSummary.wbsOpen);
				that.byId("numWbs").setValueColor(oSummary.wbsOpen ? "Critical" : "Good");
				that.byId("tileWbs").setSubheader(oSummary.wbsDone + " of "
					+ oSummary.totalLines + " distributed");

				that.byId("numRes").setValue(oSummary.resOpen);
				that.byId("numRes").setValueColor(oSummary.resOpen ? "Critical" : "Good");
				that.byId("tileRes").setSubheader(oSummary.resResolved + " of "
					+ oSummary.totalLines + " resolved");

				that.byId("numGate").setValue(oSummary.gateFailing);
				that.byId("numGate").setValueColor(oSummary.gateFailing ? "Error" : "Good");
				that.byId("tileGate").setSubheader(oSummary.gatePassing + " rule(s) passing");

				that.getView().getModel("view").setProperty("/exceptions",
					oSummary.exceptions || []);
				that.byId("exceptionCount").setText("Exceptions ("
					+ (oSummary.exceptions || []).length + ")");

				// UI-04: disabled while failing, and the tooltip says why.
				var bReady = oSummary.gateFailing === 0;
				that.byId("generateBudgetBtn").setEnabled(bReady);
				that.byId("generateBudgetBtn").setTooltip(bReady
					? "Every gate rule passes"
					: oSummary.gateFailing + " gate rule(s) failing — open the "
						+ "Validation Gate tile for the list");
			}).catch(function (oError) {
				MessageBox.error(oError.message || "The summary could not be read.");
			});
		},

		onAcceptSuggestion: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("view").getObject(),
				oModel = this.getModel("pj"),
				that = this;

			var oContext = oModel.bindContext(
				"/BOQItems(ID=" + oRow.boqItemId + ",IsActiveEntity=true)", null,
				{ $$updateGroupId: "cm" }).getBoundContext();
			oContext.setProperty("cbs_ID", oRow.suggestedCbsId);
			oModel.submitBatch("cm").then(function () {
				MessageToast.show(oRow.itemNo + " mapped to CBS " + oRow.suggestedCbs
					+ ". The row leaves the queue.");
				that._refresh();
			}).catch(function (oError) {
				MessageBox.error(oError.message || "The mapping was refused.");
			});
		},

		onGenerateBuildUp: function () {
			var oModel = this.getModel("pj"),
				that = this;
			// The project's first bill carries the action.
			oModel.bindList("/BOQs", null, null, null, {
				$filter: "project_ID eq " + this._sProjectId + " and IsActiveEntity eq true",
				$select: "ID"
			}).requestContexts(0, 1).then(function (aContexts) {
				if (!aContexts.length) {
					MessageBox.information("This project has no bill of quantities yet.");
					return;
				}
				var oOperation = oModel.bindContext("ProjectService.generateBuildUp(...)",
					aContexts[0]);
				oOperation.setParameter("difficultyPct", 110);
				oOperation.execute().then(function () {
					MessageToast.show(String(oOperation.getBoundContext().getValue().value
						|| oOperation.getBoundContext().getValue()));
					that._refresh();
				}).catch(function (oError) {
					MessageBox.error(oError.message || "Generation failed.");
				});
			});
		},

		onCheckGate: function () {
			var oModel = this.getModel("pj");
			var oOperation = oModel.bindContext("ProjectService.validateForBudget(...)",
				oModel.bindContext("/Projects(ID=" + this._sProjectId + ",IsActiveEntity=true)")
					.getBoundContext());
			oOperation.execute().then(function () {
				var aRules = oOperation.getBoundContext().getValue().value
					|| oOperation.getBoundContext().getValue() || [];
				var sText = aRules.map(function (oRule) {
					return (oRule.result === "Pass" ? "✓ " : "✗ ") + oRule.ruleId + "  "
						+ oRule.failing + "/" + oRule.linesChecked + "  " + oRule.description;
				}).join("\n");
				MessageBox.information(sText, { title: "KX-GOV-002 — budget generation gate" });
			});
		},

		onGenerateBudget: function () {
			MessageBox.information(
				"Budget generation runs on the Budget object: create or open the budget "
				+ "and run Generate Lines there. The gate is green, so it will pass.");
		},

		onNoop: function () { }
	});
});
