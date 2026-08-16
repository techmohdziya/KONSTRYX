sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/lib/ObjectLinks",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, ObjectLinks, Filter, FilterOperator, MessageBox, MessageToast) {
	"use strict";

	/**
	 * The bill of one project, and the build-up of the selected line.
	 *
	 * The screen deliberately shows contract qty and budget qty side by side —
	 * revenue basis and cost basis — because crossing them is the classic
	 * mistake (CALC-05), and a MANUAL build-up row renders as a warning because
	 * it is a flagged exception awaiting a recipe, not a way of working.
	 */
	return BaseController.extend("konstryx.controller.ProjectBOQ", {

		onInit: function () {
			this.getRouter().getRoute("projectBOQ").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function (oEvent) {
			this.setNavKey("projects");
			var sProjectId = oEvent.getParameter("arguments").projectId;
			this._sProjectId = sProjectId;

			var oModel = this.getModel("pj");
			var that = this;

			// The BOQ header for the project; the first bill is bound with its
			// items expanded so the table needs no second round trip.
			oModel.bindList("/BOQs", null, null, null, {
				$filter: "project_ID eq " + sProjectId + " and IsActiveEntity eq true",
				$select: "ID,boqId,version,status,contractValue",
				$expand: "project($select=code,name)"
			}).requestContexts(0, 10).then(function (aContexts) {
				if (!aContexts.length) {
					that.byId("boqTitle").setText("No bill of quantities yet");
					that.byId("boqSubtitle").setText(
						"Import one on the project, or through the upload framework.");
					return;
				}
				var oBoq = aContexts[0].getObject();
				that._sBoqId = oBoq.ID;
				that.byId("boqTitle").setText(oBoq.project.code + " · " + oBoq.boqId
					+ " " + (oBoq.version || ""));
				that.byId("boqSubtitle").setText(oBoq.project.name
					+ " — contract value " + Number(oBoq.contractValue)
						.toLocaleString("en-US", { maximumFractionDigits: 0 }));

				var oBinding = that.byId("itemTable").getBinding("items");
				oBinding.filter([new Filter("boq_ID", FilterOperator.EQ, oBoq.ID)]);
				if (oBinding.isSuspended()) {
					oBinding.resume();
				}
				oBinding.attachEventOnce("dataReceived", function () {
					that.byId("itemCount").setText("Bill lines (" + oBinding.getLength() + ")");
				});
			});
		},

		onItemSelect: function (oEvent) {
			var oItem = oEvent.getParameter("listItem").getBindingContext("pj").getObject();
			this.byId("buildUpTitle").setText("Resource build-up — " + oItem.itemNo);
			var oBinding = this.byId("buildUpTable").getBinding("items");
			oBinding.filter([new Filter("boqItem_ID", FilterOperator.EQ, oItem.ID)]);
			if (oBinding.isSuspended()) {
				oBinding.resume();
			}
			oBinding.attachEventOnce("dataReceived", function () {
				var iManual = 0;
				oBinding.getAllCurrentContexts().forEach(function (oContext) {
					if (oContext.getObject().source === "MANUAL") {
						iManual++;
					}
				});
				this.byId("buildUpOrigin").setText(iManual
					? iManual + " manual — flagged for recipe creation" : "");
			}, this);
		},

		onGenerateBuildUp: function () {
			if (!this._sBoqId) {
				return;
			}
			var oModel = this.getModel("pj");
			var oOperation = oModel.bindContext("ProjectService.generateBuildUp(...)",
				oModel.bindContext("/BOQs(ID=" + this._sBoqId + ",IsActiveEntity=true)")
					.getBoundContext());
			oOperation.setParameter("difficultyPct", 110);
			oOperation.execute().then(function () {
				MessageBox.information(oOperation.getBoundContext().getValue().value
					|| oOperation.getBoundContext().getValue(),
					{ title: "Build-up coverage" });
			}).catch(function (oError) {
				MessageBox.error(oError.message || "Generation failed.");
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
				var bFailing = aRules.some(function (oRule) { return oRule.result !== "Pass"; });
				MessageBox[bFailing ? "warning" : "success"](sText, {
					title: "KX-GOV-002 — budget generation gate"
				});
			}).catch(function (oError) {
				MessageBox.error(oError.message || "The gate could not be evaluated.");
			});
		},

		// ------------------------------------------------------------- links

		onCbsLink: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("pj").getObject();
			ObjectLinks.open(this, "cbs", oRow.cbs || {}, oEvent.getSource());
		},

		onResourceLink: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("pj").getObject();
			ObjectLinks.open(this, "resource", oRow.resource || {}, oEvent.getSource());
		}
	});
});
