sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, Filter, FilterOperator, MessageBox, MessageToast) {
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
		},

		_onMatched: function () {
			this.setNavKey("masters");
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
			oBinding.filter(aFilters);
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId("tableTitle").setText("Requests (" + oBinding.getLength() + ")");
				this._clearSelection();
			}, this);
		},

		onFilterChange: function () { this._applyFilters(); },

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
