sap.ui.define([
	"konstryx/controller/BaseController"
], function (BaseController) {
	"use strict";

	/**
	 * Root controller. Deliberately thin: the shell handlers that used to live
	 * here — menu toggle, side-navigation select, company switcher, global
	 * search — belonged to chrome the launchpad now owns (decision D-16).
	 *
	 * Global search is the launchpad's; company scope is a business filter and
	 * belongs on the pages that use it, not in a shell the app no longer has.
	 */
	return BaseController.extend("konstryx.controller.App", {

		onInit: function () {
			this.getView().addStyleClass(this.getOwnerComponent().getContentDensityClass());
		}
	});
});
