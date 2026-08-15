sap.ui.define([
	"sap/ui/core/UIComponent",
	"sap/ui/Device",
	"konstryx/model/models"
], function (UIComponent, Device, models) {
	"use strict";

	return UIComponent.extend("konstryx.Component", {

		metadata: { manifest: "json" },

		init: function () {
			UIComponent.prototype.init.apply(this, arguments);

			this.setModel(models.createDeviceModel(), "device");
			this.setModel(models.createAppStateModel(), "app");

			// The router is what makes this behave like an application rather
			// than a deck of screens: every document in the chain has its own
			// URL, so back/forward and deep links work.
			//
			// It must not start until the root view exists. The root view is
			// created asynchronously, so initialising in init() would fire the
			// first route match while the NavContainer it targets is still
			// undefined — the page stack then stays empty and the shell renders
			// with nothing inside it.
			this.rootControlLoaded().then(function () {
				this.getRouter().initialize();
			}.bind(this));
		},

		getContentDensityClass: function () {
			return Device.support.touch ? "sapUiSizeCozy" : "sapUiSizeCompact";
		}
	});
});
