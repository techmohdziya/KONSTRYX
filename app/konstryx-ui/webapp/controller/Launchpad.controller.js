sap.ui.define([
	"konstryx/controller/BaseController"
], function (BaseController) {
	"use strict";

	return BaseController.extend("konstryx.controller.Launchpad", {

		onInit: function () {
			this.getRouter().getRoute("launchpad").attachPatternMatched(function () {
				this.setNavKey("launchpad");
			}, this);
		},

		onTilePress: function (oEvent) {
			var oTile = oEvent.getSource().getBindingContext().getObject();
			this.navTo(oTile.route, { docType: oTile.arg });
		},

		onOpenCanonical: function () {
			this.navTo("request", { requestId: "RR-2026-0188" });
		}
	});
});
