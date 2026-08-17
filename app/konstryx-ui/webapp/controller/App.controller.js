sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/json/JSONModel",
	"sap/m/ResponsivePopover",
	"sap/m/VBox",
	"sap/m/Avatar",
	"sap/m/Title",
	"sap/m/Text",
	"sap/m/Button",
	"sap/m/MessageToast"
], function (BaseController, JSONModel, ResponsivePopover, VBox, Avatar, Title, Text, Button, MessageToast) {
	"use strict";

	/**
	 * Root controller. Deliberately thin: the shell handlers that used to live
	 * here — menu toggle, side-navigation select, company switcher, global
	 * search — belonged to chrome the launchpad now owns (decision D-16).
	 *
	 * Global search is the launchpad's; company scope is a business filter and
	 * belongs on the pages that use it, not in a shell the app no longer has.
	 *
	 * onGoHome/onProfilePress belong to the temporary dev ShellBar in
	 * App.view.xml only — real home/profile behaviour is the launchpad's once
	 * D-16's actual shell is in place.
	 */
	return BaseController.extend("konstryx.controller.App", {

		onInit: function () {
			this.getView().addStyleClass(this.getOwnerComponent().getContentDensityClass());

			// Self-disabling: a real launchpad hosts the app in an iframe, so
			// the dev shell never shows twice once D-16's actual shell wraps it.
			var bEmbedded = window.self !== window.top;
			this.getView().setModel(new JSONModel({ showDevShell: !bEmbedded }), "view");
		},

		onGoHome: function () {
			this.navTo("launchpad", {}, true);
		},

		onProfilePress: function (oEvent) {
			var oData = this.getData().user || {};

			var oPopover = new ResponsivePopover({
				placement: "Bottom",
				showHeader: false,
				contentWidth: "16rem",
				content: [
					new VBox({
						items: [
							new Avatar({ initials: oData.initials, displaySize: "M" })
								.addStyleClass("sapUiSmallMarginBottom"),
							new Title({ text: oData.name, level: "H5" }),
							new Text({ text: oData.role || "" }).addStyleClass("kxSubText"),
							new Text({ text: oData.company || "" }).addStyleClass("kxSubText sapUiTinyMarginBottom"),
							new Button({
								text: "Sign out", type: "Transparent", icon: "sap-icon://log",
								press: function () {
									oPopover.close();
									MessageToast.show("Sign-out is the launchpad's, once this runs inside one.");
								}
							})
						]
					}).addStyleClass("sapUiSmallMargin")
				],
				afterClose: function () { oPopover.destroy(); }
			});

			this.getView().addDependent(oPopover);
			oPopover.openBy(oEvent.getParameter("avatar") || oEvent.getSource());
		}
	});
});
