sap.ui.define([
	"sap/ui/core/mvc/Controller",
	"sap/ui/core/UIComponent",
	"sap/m/MessageToast"
], function (Controller, UIComponent, MessageToast) {
	"use strict";

	return Controller.extend("konstryx.controller.BaseController", {

		getRouter: function () {
			return UIComponent.getRouterFor(this);
		},

		getModel: function (sName) {
			return this.getView().getModel(sName);
		},

		getAppModel: function () {
			return this.getOwnerComponent().getModel("app");
		},

		getData: function () {
			return this.getOwnerComponent().getModel().getData();
		},

		/** Marks the side-navigation entry that corresponds to the current route. */
		setNavKey: function (sKey) {
			this.getAppModel().setProperty("/selectedKey", sKey);
		},

		navTo: function (sName, oParams, bReplace) {
			this.getRouter().navTo(sName, oParams, bReplace);
		},

		onNavBack: function () {
			var oHistory = sap.ui.core.routing.History.getInstance();
			if (oHistory.getPreviousHash() !== undefined) {
				window.history.go(-1);
			} else {
				this.navTo("launchpad", {}, true);
			}
		},

		onNotImplemented: function () {
			MessageToast.show("Not part of this slice — the EQR chain RR → CLS is what is built out.");
		},

		formatAED: function (v) {
			if (v === null || v === undefined || v === "") { return ""; }
			return "AED " + Number(v).toLocaleString("en-US");
		}
	});
});
