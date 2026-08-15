sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, Filter, FilterOperator, MessageBox, MessageToast) {
	"use strict";

	/**
	 * Resource master object page.
	 *
	 * The route carries the resource code rather than its UUID: a master code is
	 * what people quote to each other, and a link to EQ-TWC-12T survives a data
	 * reload while a link to a generated key does not. The code is resolved to a
	 * context on entry.
	 */
	return BaseController.extend("konstryx.controller.ResourceDetail", {

		onInit: function () {
			this.getRouter().getRoute("resourceDetail").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function (oEvent) {
			var sCode = decodeURIComponent(oEvent.getParameter("arguments").code);
			this.setNavKey("masters");
			this._sCode = sCode;
			this._bindToCode(sCode);
		},

		/** Resolve code -> context, then hang the page off it. */
		_bindToCode: function (sCode) {
			var oView = this.getView(),
				oList = this.getModel("md").bindList("/Resources", null, null, [
					new Filter("code", FilterOperator.EQ, sCode)
				], { $expand: "owningCompany($select=code,legalName),parent($select=code,description)" });

			oList.requestContexts(0, 1).then(function (aContexts) {
				if (!aContexts.length) {
					this.getRouter().getTargets().display("notFound");
					return;
				}
				oView.setBindingContext(aContexts[0], "md");
				// Only a company-scoped master can be promoted; a group master is
				// already shared and the service would refuse.
				this.byId("promoteButton").setVisible(aContexts[0].getProperty("scope") === "COMPANY");
				this._bindRates(sCode);
				this._bindChildren(aContexts[0]);
			}.bind(this)).catch(function () {
				this.getRouter().getTargets().display("notFound");
			}.bind(this));
		},

		/** Every rate for this resource, in either scope, newest first. */
		_bindRates: function (sCode) {
			var oTable = this.byId("rateTable"),
				oBinding = oTable.getBinding("items");
			if (!oBinding) {
				return;
			}
			oBinding.filter([new Filter("resource/code", FilterOperator.EQ, sCode)]);
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId("rateTitle").setText("Rates (" + oBinding.getLength() + ")");
			}, this);
		},

		_bindChildren: function (oCtx) {
			var oBinding = this.byId("childTable").getBinding("items");
			if (!oBinding) {
				return;
			}
			oBinding.filter([new Filter("parent_ID", FilterOperator.EQ, oCtx.getProperty("ID"))]);
			oBinding.attachEventOnce("dataReceived", function () {
				var iCount = oBinding.getLength();
				this.byId("childTitle").setText(iCount
					? "Children (" + iCount + ")"
					: "Nothing sits below this node");
			}, this);
		},

		onChildPress: function (oEvent) {
			var oCtx = oEvent.getSource().getBindingContext("md");
			this.navTo("resourceDetail", { code: encodeURIComponent(oCtx.getProperty("code")) });
		},

		onBackToList: function () {
			this.navTo("masterResources");
		},

		onRequestPromotion: function () {
			var oCtx = this.getView().getBindingContext("md");
			if (!oCtx) {
				return;
			}
			MessageBox.confirm(
				"Request that " + oCtx.getProperty("code") + " be shared across the whole group?",
				{
					title: "Request promotion",
					emphasizedAction: MessageBox.Action.OK,
					onClose: function (sAction) {
						if (sAction !== MessageBox.Action.OK) {
							return;
						}
						var oOperation = this.getModel("md").bindContext(
							"MasterDataService.requestPromotion(...)", oCtx);
						oOperation.setParameter("reason", "Requested from the resource master page");
						oOperation.execute().then(function () {
							MessageToast.show(oOperation.getBoundContext().getValue());
						}).catch(function (oError) {
							MessageBox.error(oError.message || "The request could not be raised.");
						});
					}.bind(this)
				}
			);
		}
	});
});
