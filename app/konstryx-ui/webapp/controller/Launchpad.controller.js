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

		/**
		 * Chain worklists carry a document type; the master screens are their own
		 * route with no argument, so only pass one when the tile defines it.
		 */
		onTilePress: function (oEvent) {
			var oTile = oEvent.getSource().getBindingContext().getObject();
			this.navTo(oTile.route, oTile.arg ? { docType: oTile.arg } : undefined);
		},

		onOpenCanonical: function () {
			this.navTo("request", { requestId: "RR-2026-0188" });
		}
	});
});
