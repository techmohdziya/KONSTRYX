sap.ui.define([
	"konstryx/controller/BaseController"
], function (BaseController) {
	"use strict";

	/**
	 * Productivity and consumption norms.
	 *
	 * These two sit on one screen because they are two halves of the same
	 * derivation: output achieved against the productivity norm gives earned
	 * value, and that same output against the consumption norm gives theoretical
	 * material usage, which is what site consumption is reconciled against.
	 * Maintaining them apart is how the two drift.
	 */
	return BaseController.extend("konstryx.controller.MasterNorms", {

		onInit: function () {
			this.getRouter().getRoute("masterNorms").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function () {
			this.setNavKey("masters");
			this._count("prodTable", "prodTitle", "Productivity norms");
			this._count("consTable", "consTitle", "Consumption norms");
		},

		_count: function (sTable, sTitle, sLabel) {
			var oBinding = this.byId(sTable) && this.byId(sTable).getBinding("items");
			if (!oBinding) {
				return;
			}
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId(sTitle).setText(sLabel + " (" + oBinding.getLength() + ")");
			}, this);
		}
	});
});
