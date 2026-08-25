sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/lib/ListPersonalization",
	"sap/ui/model/json/JSONModel",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/ui/export/library",
	"sap/m/Dialog",
	"sap/m/Button",
	"sap/m/Select",
	"sap/m/Input",
	"sap/m/TextArea",
	"sap/m/Label",
	"sap/m/VBox",
	"sap/ui/core/Item",
	"sap/m/MessageBox",
	"sap/m/MessageToast",
	"konstryx/lib/ActionPost"
], function (BaseController, ListPersonalization, JSONModel, Filter, FilterOperator, exportLibrary,
             Dialog, Button, Select, Input, TextArea, Label, VBox, Item, MessageBox, MessageToast, ActionPost) {
	"use strict";

	/** The six cost-nature verticals a budget line can carry (bud.cds §BudgetLine.category). */
	var CATEGORIES = [
		{ key: "MR",  text: "MR · Material" },
		{ key: "MPR", text: "MPR · Manpower" },
		{ key: "EQR", text: "EQR · Equipment / Plant" },
		{ key: "VR",  text: "VR · Vehicle" },
		{ key: "SF",  text: "SF · Scaffolding / Formwork" },
		{ key: "SC",  text: "SC · Subcontract" }
	];

	/**
	 * One Budget document: header actions that move it through
	 * Draft -> Submitted -> Approved -> Baselined -> Locked, its control-record
	 * lines, and the ledger that is the only way a line's amount ever changes
	 * once baselined (KX-BUD-004).
	 */
	return BaseController.extend("konstryx.controller.BudgetDetail", {

		onInit: function () {
			this.getView().setModel(new JSONModel({
				budget: {},
				approvals: { instanceStatus: "", steps: [] },
				cbsCodeById: {}
			}), "view");
			this.getRouter().getRoute("budgetDetail").attachPatternMatched(this._onMatched, this);
			this._setUpPersonalization();
		},

		_onMatched: function (oEvent) {
			this.setNavKey("projects");
			var oArgs = oEvent.getParameter("arguments");
			this._sProjectId = oArgs.projectId;
			this._sBudgetId = oArgs.budgetId;
			this._oBudgetCtx = this.getModel("bud")
				.bindContext("/Budgets(ID=" + this._sBudgetId + ",IsActiveEntity=true)")
				.getBoundContext();
			this._refresh();
		},

		_refresh: function () {
			var that = this;
			// CBS lives in prj.CBSInstance, a different OData service (pj) than
			// Budgets/BudgetLines — OData v4 cannot navigate an association whose
			// target isn't exposed in the same service, even one hop for a plain
			// scalar like code, so it is resolved here client-side from cbs_ID
			// rather than through cbs/code in the row binding.
			return Promise.all([this._loadBudget(), this._loadCbsOptions()]).then(function () {
				that._loadLines();
				that._loadLedger();
				that._loadApprovals();
			});
		},

		formatCbsCode: function (sCbsId, oMap) {
			return (oMap && oMap[sCbsId]) || sCbsId || "";
		},

		/**
		 * sap.m.NumericContent truncates its value to 4 characters by default
		 * (truncateValueTo) — a real amount like 381,600 would render as "3816"
		 * with no indication anything was cut. Grouped and given room instead.
		 */
		_setKpi: function (sControlId, vAmount) {
			var oControl = this.byId(sControlId);
			oControl.setTruncateValueTo(20);
			oControl.setValue(Number(vAmount || 0).toLocaleString("en-US"));
		},

		/**
		 * Budgets.project is an association whose target (prj.Project) is not
		 * itself exposed by BudgetService, so it cannot be $expand-ed here —
		 * the project's own code/name is fetched separately from the pj model,
		 * the same split every other cross-service screen in this app uses.
		 */
		_loadBudget: function () {
			var that = this;
			return this.getModel("bud").bindList("/Budgets", null, null, null, {
				$filter: "ID eq " + this._sBudgetId + " and IsActiveEntity eq true",
				$select: "ID,docNo,version,status,totalAmount,daysToLock,project_ID"
			}).requestContexts(0, 1).then(function (aContexts) {
				if (!aContexts.length) {
					return;
				}
				var oBudget = aContexts[0].getObject(),
					oView = that.getView().getModel("view");
				oView.setProperty("/budget", {
					ID: oBudget.ID,
					docNo: oBudget.docNo,
					version: oBudget.version,
					status: oBudget.status,
					totalAmount: oBudget.totalAmount,
					daysToLock: oBudget.daysToLock,
					subtitle: "version " + oBudget.version,
					hasLines: (oView.getProperty("/budget/hasLines")) || false
				});
				that._setKpi("kpiTotal", oBudget.totalAmount);
				return that.getModel("pj").bindList("/Projects", null, null, null, {
					$filter: "ID eq " + oBudget.project_ID + " and IsActiveEntity eq true",
					$select: "code,name"
				}).requestContexts(0, 1).then(function (aProjCtx) {
					if (!aProjCtx.length) {
						return;
					}
					var oProject = aProjCtx[0].getObject();
					oView.setProperty("/budget/subtitle",
						oProject.code + " " + oProject.name + " · version " + oBudget.version);
				});
			});
		},

		_loadLines: function () {
			var oBinding = this.byId("linesTable").getBinding("items"),
				that = this;
			if (!oBinding) {
				return;
			}
			// Attach before filter/refresh: an already in-flight response can
			// otherwise fire dataReceived first, while the new request's rows
			// are still empty, and the counts/KPIs stick at 0 (seen live).
			oBinding.attachEventOnce("dataReceived", function () {
				var aRows = oBinding.getAllCurrentContexts().map(function (c) { return c.getObject(); }),
					fSum = function (sField) {
						return aRows.reduce(function (n, r) { return n + (Number(r[sField]) || 0); }, 0);
					};
				that.byId("linesTitle").setText("Budget Lines (" + aRows.length + ")");
				that._setKpi("kpiCommitted", fSum("committed"));
				that._setKpi("kpiEncumbered", fSum("encumbered"));
				that._setKpi("kpiActual", fSum("actual"));
				that._setKpi("kpiAvailable", fSum("available"));
				that.getView().getModel("view").setProperty("/budget/hasLines", aRows.length > 0);
			});
			oBinding.filter([new Filter("budget_ID", FilterOperator.EQ, this._sBudgetId)]
				.concat(this._aLinesP13nFilters || []));
			if (this._aLinesP13nSorters && this._aLinesP13nSorters.length) {
				oBinding.sort(this._aLinesP13nSorters);
			}
			// budget_ID never changes for this view instance, so .filter() with
			// an unchanged filter array is a no-op that skips the server round
			// trip entirely (confirmed live: after posting a Shift, the table's
			// own binding stayed at its pre-action length even though the
			// server genuinely had the new rows). .refresh() always issues a
			// real request regardless of whether the filter value changed.
			oBinding.refresh();
		},

		_loadLedger: function () {
			var oBinding = this.byId("ledgerTable").getBinding("items"),
				that = this;
			if (!oBinding) {
				return;
			}
			var aFilters = [new Filter("budget_ID", FilterOperator.EQ, this._sBudgetId)]
				.concat(this._aLedgerP13nFilters || []);
			oBinding.attachEventOnce("dataReceived", function () {
				that.byId("ledgerTitle").setText(
					"Ledger (" + oBinding.getAllCurrentContexts().length + ")");
			});
			oBinding.filter(aFilters);
			if (this._aLedgerP13nSorters && this._aLedgerP13nSorters.length) {
				oBinding.sort(this._aLedgerP13nSorters);
			}
			oBinding.refresh();
		},

		/**
		 * The approval chain lives in the generic CollaborationService, not on
		 * the Budget entity itself — bud.cds's own BudgetApproval composition
		 * is unwritten dead weight from an earlier design; submit() hands the
		 * document to CollaborationService.submitForApproval under the hood,
		 * and ApprovalInstances/steps is where the real trail is.
		 */
		_loadApprovals: function () {
			var oView = this.getView().getModel("view"),
				sDocNo = oView.getProperty("/budget/docNo");
			if (!sDocNo) {
				return;
			}
			this.getModel("collab").bindList("/ApprovalInstances", null, null, null, {
				$filter: "objectDocNo eq '" + sDocNo + "'",
				$select: "ID,status",
				$expand: "steps($select=ID,stepNo,name,actedBy,decision,decidedAt,comment;$orderby=stepNo)"
			}).requestContexts(0, 1).then(function (aContexts) {
				if (!aContexts.length) {
					oView.setProperty("/approvals", { instanceStatus: "", steps: [] });
					return;
				}
				var oInstance = aContexts[0].getObject();
				oView.setProperty("/approvals", {
					instanceStatus: oInstance.status,
					steps: oInstance.steps || []
				});
			});
		},

		// ------------------------------------------------------------ header actions

		_runAction: function (sAction, oParams, sBusyId) {
			var oOperation = this.getModel("bud").bindContext(
				"BudgetService." + sAction + "(...)", this._oBudgetCtx),
				that = this;
			Object.keys(oParams || {}).forEach(function (sKey) {
				oOperation.setParameter(sKey, oParams[sKey]);
			});
			return oOperation.execute().then(function () {
				var vResult = oOperation.getBoundContext().getValue();
				MessageToast.show(String((vResult && vResult.value) || vResult || "Done."));
				return that._refresh();
			}).catch(function (oError) {
				MessageBox.error(oError.message || "The action was refused.");
				throw oError;
			});
		},

		onGenerateLines: function () { this._runAction("generateLines"); },
		onSubmit:        function () { this._runAction("submit"); },
		onBaseline:      function () { this._runAction("baseline"); },
		onRefreshControl:function () { this._runAction("refreshControl"); },

		/**
		 * shift/riskTransfer/variation all carry a Decimal `amount` parameter,
		 * which the typed bindContext(...).setParameter(...) path cannot post
		 * successfully — confirmed live: SAPUI5's v4 model negotiates
		 * IEEE754Compatible=true (so Decimals serialise as bare JSON numbers)
		 * but CAP Java's action-parameter deserialiser only accepts a Decimal
		 * as a *quoted* string when that flag is set ("Invalid value for
		 * property 'amount'" otherwise) — the inverse of what the flag is
		 * supposed to mean, and confirmed by curl in all three combinations
		 * (no flag + bare number: OK · flag + quoted string: OK · flag + bare
		 * number, i.e. exactly what the model sends: fails). This is the same
		 * family of bug as the array-of-complex-type Decimal gotcha already
		 * known on distributeToWBS — that workaround happened to dodge it only
		 * because its hand-built fetch never set IEEE754Compatible, not
		 * because array nesting was the real cause. A plain top-level Decimal
		 * action parameter breaks exactly the same way; nothing about Budget's
		 * ledger actions is special-cased here beyond that shared cause.
		 */
		_runActionRaw: function (sAction, oParams) {
			var oModel = this.getModel("bud"),
				that = this,
				sUrl = oModel.getServiceUrl() + "Budgets(ID=" + this._sBudgetId
					+ ",IsActiveEntity=true)/BudgetService." + sAction;

			return ActionPost.post(sUrl, oParams || {},
					"The action was refused.").then(function (oBody) {
				MessageToast.show(String(oBody.value || "Done."));
				return that._refresh();
			}).catch(function (oError) {
				MessageBox.error(oError.message || "The action was refused.");
				throw oError;
			});
		},

		// ------------------------------------------------------------ ledger dialogs

		_loadCbsOptions: function () {
			if (this._aCbsOptions) {
				return Promise.resolve(this._aCbsOptions);
			}
			var that = this;
			return this.getModel("pj").bindList("/CBS", null, null, null, {
				$filter: "project_ID eq " + this._sProjectId,
				$select: "ID,code",
				$orderby: "code"
			}).requestContexts(0, 500).then(function (aContexts) {
				that._aCbsOptions = aContexts.map(function (c) { return c.getObject(); });
				that._oCbsCodeById = {};
				that._aCbsOptions.forEach(function (c) { that._oCbsCodeById[c.ID] = c.code; });
				// A plain JS map read inside a formatter is invisible to UI5's
				// change detection — a formatter only re-runs when the *bound
				// value* changes, not because unrelated state it happens to
				// read was mutated (confirmed live: even an explicit list
				// binding .refresh() afterwards left an already-rendered cell
				// showing the raw GUID). Putting the map on the view model and
				// binding to it as a real second part is what makes it
				// reactive, so it displays correctly regardless of whether the
				// CBS lookup or the lines/ledger table wins the load race.
				that.getView().getModel("view").setProperty("/cbsCodeById", that._oCbsCodeById);
				return that._aCbsOptions;
			});
		},

		_cbsSelect: function (aCbs) {
			return new Select({
				width: "100%",
				items: aCbs.map(function (c) {
					return new Item({ key: c.code, text: c.code });
				})
			});
		},

		_categorySelect: function () {
			return new Select({
				width: "100%",
				items: CATEGORIES.map(function (c) { return new Item({ key: c.key, text: c.text }); })
			});
		},

		onShift: function () {
			var that = this;
			this._loadCbsOptions().then(function (aCbs) {
				if (!aCbs.length) {
					MessageBox.warning("This project has no CBS instances yet.");
					return;
				}
				var oFromCbs = that._cbsSelect(aCbs), oFromCat = that._categorySelect(),
					oToCbs = that._cbsSelect(aCbs), oToCat = that._categorySelect(),
					oAmount = new Input({ type: "Number", value: "0" }),
					oReason = new TextArea({ width: "100%", rows: 2, placeholder: "Mandatory — why is this moving?" });

				var oDialog = new Dialog({
					title: "Shift budget — zero-sum, same total",
					contentWidth: "26rem",
					content: [new VBox({
						items: [
							new Label({ text: "From CBS / category" }), oFromCbs, oFromCat,
							new Label({ text: "To CBS / category" }).addStyleClass("sapUiSmallMarginTop"), oToCbs, oToCat,
							new Label({ text: "Amount" }).addStyleClass("sapUiSmallMarginTop"), oAmount,
							new Label({ text: "Reason" }).addStyleClass("sapUiSmallMarginTop"), oReason
						]
					}).addStyleClass("sapUiSmallMargin")],
					beginButton: new Button({
						text: "Post Shift", type: "Emphasized",
						press: function () {
							var fAmount = parseFloat(oAmount.getValue()) || 0,
								sReason = oReason.getValue().trim();
							if (fAmount <= 0 || !sReason) {
								MessageBox.warning("Amount must be greater than zero and a reason is required.");
								return;
							}
							oDialog.close();
							that._runActionRaw("shift", {
								fromCBS: oFromCbs.getSelectedKey(), toCBS: oToCbs.getSelectedKey(),
								fromCategory: oFromCat.getSelectedKey(), toCategory: oToCat.getSelectedKey(),
								amount: fAmount, reason: sReason
							});
						}
					}),
					endButton: new Button({ text: "Cancel", press: function () { oDialog.close(); } }),
					afterClose: function () { oDialog.destroy(); }
				});
				that.getView().addDependent(oDialog);
				oDialog.open();
			});
		},

		onRiskTransfer: function () {
			var that = this;
			this._loadCbsOptions().then(function (aCbs) {
				if (!aCbs.length) {
					MessageBox.warning("This project has no CBS instances yet.");
					return;
				}
				var oFromCbs = that._cbsSelect(aCbs), oFromCat = that._categorySelect(),
					oToCbs = that._cbsSelect(aCbs), oToCat = that._categorySelect(),
					oAmount = new Input({ type: "Number", value: "0" }),
					oRiskRef = new Input({ placeholder: "e.g. RISK-2026-014" }),
					oReason = new TextArea({ width: "100%", rows: 2, placeholder: "Mandatory — what materialised?" });

				var oDialog = new Dialog({
					title: "Risk Transfer — draws down contingency",
					contentWidth: "26rem",
					content: [new VBox({
						items: [
							new Label({ text: "From CBS / category (usually contingency)" }), oFromCbs, oFromCat,
							new Label({ text: "To CBS / category (absorbing the risk)" }).addStyleClass("sapUiSmallMarginTop"), oToCbs, oToCat,
							new Label({ text: "Amount" }).addStyleClass("sapUiSmallMarginTop"), oAmount,
							new Label({ text: "Risk reference" }).addStyleClass("sapUiSmallMarginTop"), oRiskRef,
							new Label({ text: "Reason" }).addStyleClass("sapUiSmallMarginTop"), oReason
						]
					}).addStyleClass("sapUiSmallMargin")],
					beginButton: new Button({
						text: "Post Risk Transfer", type: "Emphasized",
						press: function () {
							var fAmount = parseFloat(oAmount.getValue()) || 0,
								sRiskRef = oRiskRef.getValue().trim(),
								sReason = oReason.getValue().trim();
							if (fAmount <= 0 || !sRiskRef || !sReason) {
								MessageBox.warning("Amount, risk reference and reason are all required.");
								return;
							}
							oDialog.close();
							that._runActionRaw("riskTransfer", {
								fromCBS: oFromCbs.getSelectedKey(), toCBS: oToCbs.getSelectedKey(),
								fromCategory: oFromCat.getSelectedKey(), toCategory: oToCat.getSelectedKey(),
								amount: fAmount, riskReference: sRiskRef, reason: sReason
							});
						}
					}),
					endButton: new Button({ text: "Cancel", press: function () { oDialog.close(); } }),
					afterClose: function () { oDialog.destroy(); }
				});
				that.getView().addDependent(oDialog);
				oDialog.open();
			});
		},

		onVariation: function () {
			var that = this;
			this._loadCbsOptions().then(function (aCbs) {
				if (!aCbs.length) {
					MessageBox.warning("This project has no CBS instances yet.");
					return;
				}
				var oCbs = that._cbsSelect(aCbs), oCat = that._categorySelect(),
					oAmount = new Input({ type: "Number", value: "0" }),
					oVarRef = new Input({ placeholder: "e.g. VO-2026-003" }),
					oReason = new TextArea({ width: "100%", rows: 2, placeholder: "Mandatory — what did the client change?" });

				var oDialog = new Dialog({
					title: "Variation — the only entry that moves the total",
					contentWidth: "26rem",
					content: [new VBox({
						items: [
							new Label({ text: "CBS / category" }), oCbs, oCat,
							new Label({ text: "Amount" }).addStyleClass("sapUiSmallMarginTop"), oAmount,
							new Label({ text: "Variation order reference" }).addStyleClass("sapUiSmallMarginTop"), oVarRef,
							new Label({ text: "Reason" }).addStyleClass("sapUiSmallMarginTop"), oReason
						]
					}).addStyleClass("sapUiSmallMargin")],
					beginButton: new Button({
						text: "Post Variation", type: "Emphasized",
						press: function () {
							var fAmount = parseFloat(oAmount.getValue()) || 0,
								sVarRef = oVarRef.getValue().trim(),
								sReason = oReason.getValue().trim();
							if (fAmount === 0 || !sVarRef || !sReason) {
								MessageBox.warning("A non-zero amount, the variation order reference and a reason are all required.");
								return;
							}
							oDialog.close();
							that._runActionRaw("variation", {
								cbs: oCbs.getSelectedKey(), category: oCat.getSelectedKey(),
								amount: fAmount, variationRef: sVarRef, reason: sReason
							});
						}
					}),
					endButton: new Button({ text: "Cancel", press: function () { oDialog.close(); } }),
					afterClose: function () { oDialog.destroy(); }
				});
				that.getView().addDependent(oDialog);
				oDialog.open();
			});
		},

		// ------------------------------------------------------------ personalization

		_setUpPersonalization: function () {
			var EdmType = exportLibrary.EdmType;

			this._aLinesFields = [
				{ key: "cbs_ID",     label: "CBS",        path: "cbs_ID",     edm: EdmType.String,  width: 9 },
				{ key: "category",   label: "Category",   path: "category",  edm: EdmType.String,  width: 8 },
				{ key: "amount",     label: "Amount",     path: "amount",    edm: EdmType.Number,  width: 14 },
				{ key: "committed",  label: "Committed",  path: "committed", edm: EdmType.Number,  width: 14 },
				{ key: "encumbered", label: "Encumbered", path: "encumbered",edm: EdmType.Number,  width: 14 },
				{ key: "actual",     label: "Actual",     path: "actual",    edm: EdmType.Number,  width: 14 },
				{ key: "available",  label: "Available",  path: "available", edm: EdmType.Number,  width: 14 },
				{ key: "usedPct",    label: "% Used",     path: "usedPct",   edm: EdmType.Number,  width: 8 }
			];
			ListPersonalization.attach({
				target: "budget.lines", table: this.byId("linesTable"), variant: this.byId("linesVariant"),
				fields: this._aLinesFields, controller: this,
				onApply: this._onLinesStateApplied.bind(this)
			});

			this._aLedgerFields = [
				{ key: "category",  label: "Category",  path: "category",   edm: EdmType.String, width: 9 },
				{ key: "line_cbs_ID", label: "CBS",      path: "line/cbs_ID", edm: EdmType.String, width: 8 },
				{ key: "amount",    label: "Amount",     path: "amount",     edm: EdmType.Number, width: 14 },
				{ key: "reference", label: "Reference",  path: "reference",  edm: EdmType.String, width: 14 },
				{ key: "reason",    label: "Reason",     path: "reason",     edm: EdmType.String, width: 30 },
				{ key: "createdAt", label: "Posted",     path: "createdAt",  edm: EdmType.String, width: 14 }
			];
			ListPersonalization.attach({
				target: "budget.ledger", table: this.byId("ledgerTable"), variant: this.byId("ledgerVariant"),
				fields: this._aLedgerFields, controller: this,
				onApply: this._onLedgerStateApplied.bind(this)
			});
		},

		_stateToFiltersAndSorters: function (oState) {
			var aFilters = [];
			Object.keys(oState.Filter || {}).forEach(function (sKey) {
				(oState.Filter[sKey] || []).forEach(function (oCond) {
					var v = (oCond.values || [])[0];
					if (v !== undefined && v !== null && v !== "") {
						aFilters.push(new Filter(sKey, FilterOperator.Contains, String(v)));
					}
				});
			});
			var aSorters = [];
			(oState.Groups || []).forEach(function (g) {
				aSorters.push(new sap.ui.model.Sorter(g.key, false, true));
			});
			(oState.Sorter || []).forEach(function (srt) {
				aSorters.push(new sap.ui.model.Sorter(srt.key, !!srt.descending));
			});
			return { filters: aFilters, sorters: aSorters };
		},

		_onLinesStateApplied: function (oState) {
			var o = this._stateToFiltersAndSorters(oState);
			this._aLinesP13nFilters = o.filters;
			this._aLinesP13nSorters = o.sorters;
			this._loadLines();
		},

		_onLedgerStateApplied: function (oState) {
			var o = this._stateToFiltersAndSorters(oState);
			this._aLedgerP13nFilters = o.filters;
			this._aLedgerP13nSorters = o.sorters;
			this._loadLedger();
		},

		onLinesTableSettings: function () {
			ListPersonalization.openSettings(this.byId("linesTable"), ["Columns", "Sorter", "Groups", "Filter"]);
		},
		onLinesAdaptFilters: function () {
			ListPersonalization.openSettings(this.byId("linesTable"), ["Filter"]);
		},
		onLinesVariantSelect: function (oEvent) {
			ListPersonalization.selectVariant("budget.lines", oEvent.getParameter("key"));
		},
		onLinesVariantSave: function (oEvent) {
			ListPersonalization.saveVariant("budget.lines", oEvent);
		},
		onLinesExportExcel: function () {
			var oBinding = this.byId("linesTable").getBinding("items"),
				that = this;
			if (!oBinding) { return; }
			var aRows = oBinding.getAllCurrentContexts().map(function (c) {
				var o = Object.assign({}, c.getObject());
				o.cbs_ID = that.formatCbsCode(o.cbs_ID);
				return o;
			});
			ListPersonalization.exportToExcel("budget.lines", aRows, "budget-lines");
		},

		onLedgerTableSettings: function () {
			ListPersonalization.openSettings(this.byId("ledgerTable"), ["Columns", "Sorter", "Groups", "Filter"]);
		},
		onLedgerVariantSelect: function (oEvent) {
			ListPersonalization.selectVariant("budget.ledger", oEvent.getParameter("key"));
		},
		onLedgerVariantSave: function (oEvent) {
			ListPersonalization.saveVariant("budget.ledger", oEvent);
		},
		onLedgerExportExcel: function () {
			var oBinding = this.byId("ledgerTable").getBinding("items"),
				that = this;
			if (!oBinding) { return; }
			var aRows = oBinding.getAllCurrentContexts().map(function (c) {
				var o = Object.assign({}, c.getObject());
				o.line_cbs_ID = that.formatCbsCode(o.line && o.line.cbs_ID);
				return o;
			});
			ListPersonalization.exportToExcel("budget.ledger", aRows, "budget-ledger");
		}
	});
});
