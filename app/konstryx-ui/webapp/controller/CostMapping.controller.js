sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/json/JSONModel",
	"sap/m/Dialog",
	"sap/m/Button",
	"sap/m/Select",
	"sap/m/Input",
	"sap/m/Label",
	"sap/m/VBox",
	"sap/m/HBox",
	"sap/m/Text",
	"sap/ui/core/Item",
	"sap/m/MessageBox",
	"sap/m/MessageToast",
	"konstryx/lib/ActionPost"
], function (BaseController, JSONModel, Dialog, Button, Select, Input, Label, VBox, HBox, Text,
             Item, MessageBox, MessageToast, ActionPost) {
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

		/**
		 * A queue this short and already filtered doesn't need the full
		 * variant-management/adapt-filters apparatus the general list screens
		 * carry — there is nothing left to filter once "only exceptions" has
		 * already been applied. Export is still useful: a coordinator hands
		 * the list to whoever owns the resolution.
		 */
		onExportExcel: function () {
			var aRows = (this.getView().getModel("view").getData() || {}).exceptions || [];
			sap.ui.require(["sap/ui/export/Spreadsheet"], function (Spreadsheet) {
				new Spreadsheet({
					workbook: {
						columns: [
							{ label: "Item", property: "itemNo" },
							{ label: "Reason", property: "reason" },
							{ label: "Detail", property: "detail" },
							{ label: "Suggestion", property: "suggestedCbs" }
						]
					},
					dataSource: aRows,
					fileName: "cost-mapping-exceptions.xlsx"
				}).build();
			});
		},

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

		/**
		 * TPL-SINGLE puts the line whole onto one element; TPL-FLOORS and
		 * TPL-ZONES split it by weight across several — the same three
		 * decisions distributeToWBS already covers for 1,100 of the canonical
		 * 1,142 lines (KX-DIST). The dialog only decides which template and
		 * which targets; the server owns the arithmetic, the replace-on-rerun
		 * behaviour, and every validation.
		 */
		onDistribute: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("view").getObject(),
				that = this;

			this._loadWbsOptions().then(function (aWbs) {
				if (!aWbs.length) {
					MessageBox.warning("This project has no WBS elements yet.");
					return;
				}
				that._openDistributeDialog(oRow, aWbs);
			});
		},

		_loadWbsOptions: function () {
			if (this._aWbsOptions) {
				return Promise.resolve(this._aWbsOptions);
			}
			var that = this;
			return this.getModel("pj").bindList("/WBS", null, null, null, {
				$filter: "project_ID eq " + this._sProjectId,
				$select: "ID,code,description",
				$orderby: "code"
			}).requestContexts(0, 200).then(function (aContexts) {
				that._aWbsOptions = aContexts.map(function (c) { return c.getObject(); });
				return that._aWbsOptions;
			});
		},

		_openDistributeDialog: function (oRow, aWbs) {
			var that = this,
				oRowsBox = new VBox().addStyleClass("sapUiTinyMarginTop");

			function wbsSelect(sKey) {
				return new Select({
					width: "100%",
					selectedKey: sKey || aWbs[0].code,
					items: aWbs.map(function (w) {
						return new Item({ key: w.code, text: w.code + " · " + w.description });
					})
				});
			}

			function addRow(sWeight) {
				var oWeight = new Input({
					width: "6rem", type: "Number", value: sWeight || "1",
					visible: oTemplate.getSelectedKey() !== "TPL-SINGLE"
				});
				var oRowBox = new HBox({
					alignItems: "Center",
					items: [wbsSelect(), oWeight]
				}).addStyleClass("sapUiTinyMarginTop");
				oRowBox.data("weightField", oWeight);
				oRowsBox.addItem(oRowBox);
			}

			function resetRows(bMulti) {
				oRowsBox.removeAllItems();
				addRow();
				if (bMulti) {
					addRow();
				}
			}

			var oTemplate = new Select({
				width: "100%",
				selectedKey: "TPL-SINGLE",
				items: [
					new Item({ key: "TPL-SINGLE", text: "Whole line onto one element" }),
					new Item({ key: "TPL-FLOORS", text: "Split by floor — GFA-weighted" }),
					new Item({ key: "TPL-ZONES", text: "Split by zone — weighted" })
				],
				change: function () {
					var bMulti = oTemplate.getSelectedKey() !== "TPL-SINGLE";
					oRowsBox.getItems().forEach(function (oRowBox) {
						oRowBox.data("weightField").setVisible(bMulti);
					});
					if (bMulti && oRowsBox.getItems().length < 2) {
						addRow();
					}
				}
			});
			resetRows(false);

			var oAddButton = new Button({
				text: "+ Add target", type: "Transparent",
				visible: false,
				press: function () { addRow(); }
			});
			oTemplate.attachChange(function () {
				oAddButton.setVisible(oTemplate.getSelectedKey() !== "TPL-SINGLE");
			});

			var oDialog = new Dialog({
				title: "Distribute " + oRow.itemNo,
				contentWidth: "28rem",
				content: [
					new VBox({
						items: [
							new Text({ text: oRow.detail }),
							new Label({ text: "How to split it" }).addStyleClass("sapUiSmallMarginTop"),
							oTemplate,
							new Label({ text: "Target WBS element(s)" }).addStyleClass("sapUiSmallMarginTop"),
							oRowsBox,
							oAddButton
						]
					}).addStyleClass("sapUiSmallMargin")
				],
				beginButton: new Button({
					text: "Distribute", type: "Emphasized",
					press: function () {
						var sTemplate = oTemplate.getSelectedKey(),
							aTargets = oRowsBox.getItems().map(function (oRowBox) {
								var oSelect = oRowBox.getItems()[0],
									oWeight = oRowBox.data("weightField");
								var oTarget = { wbsCode: oSelect.getSelectedKey() };
								if (sTemplate !== "TPL-SINGLE") {
									oTarget.weight = parseFloat(oWeight.getValue()) || 0;
								}
								return oTarget;
							});
						oDialog.close();
						that._runDistribute(oRow, sTemplate, aTargets);
					}
				}),
				endButton: new Button({ text: "Cancel", press: function () { oDialog.close(); } }),
				afterClose: function () { oDialog.destroy(); }
			});

			this.getView().addDependent(oDialog);
			oDialog.open();
		},

		/**
		 * A raw POST rather than the typed action-parameter path: the SAPUI5 v4
		 * model serialises a Decimal inside an array-of-complex-type parameter
		 * as a JSON string, and CAP's OData V4 deserialiser refuses a quoted
		 * decimal on this property ("Invalid value for property 'weight'") —
		 * confirmed against the live service, which accepts the identical
		 * payload the moment weight is a bare JSON number. targets/template/
		 * itemNos are simple enough here that hand-building the body is safer
		 * than fighting the model's serialisation for one field.
		 */
		_runDistribute: function (oRow, sTemplate, aTargets) {
			var oModel = this.getModel("pj"),
				that = this,
				sUrl = oModel.getServiceUrl() + "BOQs(ID=" + oRow.boqId
					+ ",IsActiveEntity=true)/ProjectService.distributeToWBS";

			ActionPost.post(sUrl, {
				template: sTemplate, targets: aTargets, itemNos: [oRow.itemNo]
			}, "The distribution was refused.").then(function (oBody) {
				MessageToast.show(String(oBody.value || ""));
				that._refresh();
			}).catch(function (oError) {
				// A template/target mismatch or an unknown WBS code is refused
				// here, with the service's own explanation.
				MessageBox.error(oError.message || "The distribution was refused.");
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
				var sBoqId = aContexts[0].getProperty("ID");
				/**
				 * Raw fetch, not the typed action-parameter path: difficultyPct
				 * is a Decimal, and SAPUI5's v4 model negotiates
				 * IEEE754Compatible=true while CAP Java's action-parameter
				 * deserialiser only accepts a Decimal as a *quoted* string when
				 * that flag is set — the model sends a bare number, so the
				 * typed path 400s ("Invalid value for property
				 * 'difficultyPct'"), confirmed live. Same root cause as
				 * distributeToWBS's weight field below; it isn't specific to
				 * array-of-complex-type parameters.
				 */
				var sUrl = oModel.getServiceUrl() + "BOQs(ID=" + sBoqId
					+ ",IsActiveEntity=true)/ProjectService.generateBuildUp";
				ActionPost.post(sUrl, { difficultyPct: 110 },
						"Generation failed.").then(function (oBody) {
					MessageToast.show(String(oBody.value || ""));
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
			this.navTo("budget", { projectId: this._sProjectId });
		},

		onNoop: function () { }
	});
});
