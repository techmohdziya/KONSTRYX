sap.ui.define([
	"konstryx/controller/BaseController"
], function (BaseController) {
	"use strict";
	return BaseController.extend("konstryx.controller.NotFound", {
		onHome: function () { this.navTo("launchpad"); }
	});
});
