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

			// Who is actually signed in. The JSON model ships a placeholder so
			// that a failed call never leaves a stale name on screen, and this
			// replaces it with the id the service saw.
			this._loadSignedInUser();

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

		/**
		 * Replaces the placeholder user with the signed-in one.
		 *
		 * The name shown is the XSUAA logon name rather than a display name,
		 * deliberately: it is the string the approval trail, the import history
		 * and every persona assignment are keyed on. A prettier name here would
		 * mean the identity a person reads is not the identity their actions
		 * are filed under — and when an assignment is keyed on a different
		 * spelling, the refusal looks exactly like having no assignment at all.
		 *
		 * A plain fetch rather than the OData model's bound function: this is a
		 * GET, so it needs no CSRF handshake, and it must not wait on the
		 * model's metadata to render the shell.
		 */
		_loadSignedInUser: function () {
			var oModel = this.getModel();
			if (!oModel) {
				return;
			}
			fetch("/odata/v4/collaboration/whoAmI()", {
				credentials: "same-origin",
				headers: { "Accept": "application/json" }
			}).then(function (oResponse) {
				return oResponse.ok ? oResponse.json() : null;
			}).then(function (oBody) {
				if (!oBody) {
					return;
				}
				// CAP returns a complex function result inline; some stacks wrap
				// it in "value". Accept either rather than depend on which.
				var oUser = oBody.logon ? oBody : oBody.value;
				if (!oUser || !oUser.logon) {
					return;
				}
				oModel.setProperty("/user/logon", oUser.logon);
				oModel.setProperty("/user/name", oUser.logon);
				oModel.setProperty("/user/initials", oUser.initials || "?");
				// Admin-only affordances bind to this. The scope bypasses the
				// permission model rather than satisfying it, so a screen cannot
				// infer it from what the data lets through.
				oModel.setProperty("/user/isAdmin", !!oUser.isAdmin);
				// Personas are defined in the admin module and are not assigned
				// yet, so say what is true rather than name a role nobody holds.
				oModel.setProperty("/user/role", oUser.isAdmin
					? (oUser.hasPersona ? "Administrator" : "Full access — no persona assigned")
					: (oUser.hasPersona ? "Persona-based access" : "No persona assigned"));
			}).catch(function () {
				// Offline or unauthenticated: the placeholder stands, and it
				// does not claim to be anybody.
			});
		},

		getContentDensityClass: function () {
			return Device.support.touch ? "sapUiSizeCozy" : "sapUiSizeCompact";
		}
	});
});
