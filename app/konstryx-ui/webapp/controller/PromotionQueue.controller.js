sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/lib/ListPersonalization",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/ui/export/library",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, ListPersonalization, Filter, FilterOperator, exportLibrary,
             MessageBox, MessageToast) {
	"use strict";

	/**
	 * The steward queue.
	 *
	 * Approving is not a status flip: the service promotes the referenced master
	 * to group scope and clears its owning company, and refuses when another
	 * company already holds the same code locally. The screen therefore surfaces
	 * whatever the service says rather than predicting the outcome.
	 */
	return BaseController.extend("konstryx.controller.PromotionQueue", {

		onInit: function () {
			this.getRouter().getRoute("promotionQueue").attachPatternMatched(this._onMatched, this);
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
				{ key: "objectKey",    label: "Master",        path: "objectKey",    edm: EdmType.String, width: 12 },
				{ key: "objectType",   label: "Object type",   path: "objectType",   edm: EdmType.String, width: 14 },
				{ key: "currentScope", label: "Current scope", path: "currentScope", edm: EdmType.String, width: 10 },
				{ key: "requester",    label: "Requested by",  path: "requester",    edm: EdmType.String, width: 20 },
				{ key: "comment",      label: "Reason",        path: "comment",      edm: EdmType.String, width: 30 },
				{ key: "status",       label: "Status",        path: "status",       edm: EdmType.String, width: 10 },
				{ key: "decidedBy",    label: "Decided by",    path: "decidedBy",    edm: EdmType.String, width: 20 }
			];

			ListPersonalization.attach({
				target: "masters.promotionQueue",
				table: this.byId("queueTable"),
				variant: this.byId("queueVariant"),
				fields: this._aFields,
				controller: this,
				onApply: this._onStateApplied.bind(this)
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
			var oBinding = this.byId("queueTable") && this.byId("queueTable").getBinding("items");
			if (!oBinding) {
				return;
			}
			var sStatus = this.byId("statusFilter").getSelectedKey(),
				aFilters = [];

			if (sStatus && sStatus !== "ALL") {
				aFilters.push(new Filter("status", FilterOperator.EQ, sStatus));
			}
			aFilters = aFilters.concat(this._aP13nFilters || []);

			oBinding.filter(aFilters);
			if (this._aP13nSorters && this._aP13nSorters.length) {
				oBinding.sort(this._aP13nSorters);
			}
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId("tableTitle").setText("Requests (" + oBinding.getLength() + ")");
				this._clearSelection();
			}, this);
		},

		onFilterChange: function () { this._applyFilters(); },

		onTableSettings: function () {
			ListPersonalization.openSettings(this.byId("queueTable"),
				["Columns", "Sorter", "Groups", "Filter"]);
		},

		onAdaptFilters: function () {
			ListPersonalization.openSettings(this.byId("queueTable"), ["Filter"]);
		},

		onVariantSelect: function (oEvent) {
			ListPersonalization.selectVariant("masters.promotionQueue", oEvent.getParameter("key"));
		},

		onVariantSave: function (oEvent) {
			ListPersonalization.saveVariant("masters.promotionQueue", oEvent);
		},

		onExportExcel: function () {
			var oBinding = this.byId("queueTable").getBinding("items");
			if (!oBinding) {
				return;
			}
			var aRows = oBinding.getAllCurrentContexts().map(function (c) {
				return c.getObject();
			});
			ListPersonalization.exportToExcel("masters.promotionQueue", aRows, "promotion-queue");
		},

		onPrint: function () {
			ListPersonalization.printView();
		},

		_clearSelection: function () {
			this._oSelected = null;
			this.byId("approveButton").setEnabled(false);
			this.byId("rejectButton").setEnabled(false);
			this.byId("selectionHint").setText("Select a pending request to decide it.");
		},

		onSelect: function (oEvent) {
			var oCtx = oEvent.getParameter("listItem").getBindingContext("md"),
				bPending = oCtx.getProperty("status") === "PENDING";

			this._oSelected = oCtx;
			this.byId("approveButton").setEnabled(bPending);
			this.byId("rejectButton").setEnabled(bPending);
			this.byId("selectionHint").setText(bPending
				? oCtx.getProperty("objectKey") + " — requested by " + oCtx.getProperty("requester")
				: "This request was already decided by " + (oCtx.getProperty("decidedBy") || "a steward") + ".");
		},

		onApprove: function () {
			this._decide("approve",
				"Share this master across the whole group?\n\nEvery company will see it, and it will "
					+ "no longer belong to the requesting company.");
		},

		onReject: function () {
			this._decide("reject", "Reject this request? The master stays local to its company.");
		},

		_decide: function (sAction, sQuestion) {
			var oCtx = this._oSelected;
			if (!oCtx) {
				return;
			}
			MessageBox.confirm(sQuestion, {
				title: sAction === "approve" ? "Approve promotion" : "Reject promotion",
				emphasizedAction: MessageBox.Action.OK,
				onClose: function (sChoice) {
					if (sChoice !== MessageBox.Action.OK) {
						return;
					}
					var oOperation = this.getModel("md").bindContext(
						"MasterDataService." + sAction + "(...)", oCtx);
					oOperation.setParameter("comment", "Decided from the promotion queue");
					oOperation.execute().then(function () {
						MessageToast.show(oOperation.getBoundContext().getValue());
						this._applyFilters();
					}.bind(this)).catch(function (oError) {
						// A collision — another company holds the same code — arrives here.
						MessageBox.error(oError.message || "The decision could not be recorded.");
					});
				}.bind(this)
			});
		}
	});
});
