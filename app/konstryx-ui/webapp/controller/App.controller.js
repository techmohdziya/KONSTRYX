sap.ui.define([
	"konstryx/controller/BaseController"
], function (BaseController) {
	"use strict";

	return BaseController.extend("konstryx.controller.App", {

		onInit: function () {
			this.getView().addStyleClass(this.getOwnerComponent().getContentDensityClass());
		},

		onMenuButtonPress: function () {
			var oApp = this.getAppModel();
			oApp.setProperty("/navExpanded", !oApp.getProperty("/navExpanded"));
		},

		/**
		 * One handler for the whole menu. Document-type keys route to that
		 * type's worklist; everything else is either home or not in this slice.
		 */
		onNavItemSelect: function (oEvent) {
			var sKey = oEvent.getParameter("item").getKey();

			if (!sKey) { return; }

			if (sKey === "launchpad") {
				this.navTo("launchpad");
				return;
			}

			var bIsDocType = this.getData().docTypes.some(function (d) { return d.code === sKey; });
			if (bIsDocType) {
				this.navTo("worklist", { docType: sKey });
				return;
			}

			this.onNotImplemented();
			// keep the previously selected entry highlighted
			this.getAppModel().refresh(true);
		},

		onCompanyChange: function (oEvent) {
			var sKey = oEvent.getSource().getSelectedKey();
			sap.m.MessageToast.show("Active company: " + sKey + " — scope of every worklist follows this.");
		},

		onShellSearch: function (oEvent) {
			var sQuery = (oEvent.getParameter("query") || "").trim();
			if (!sQuery) { return; }
			var oHit = this.getData().requests.filter(function (r) {
				return r.id.toLowerCase().indexOf(sQuery.toLowerCase()) > -1;
			})[0];
			if (oHit) {
				this.navTo("request", { requestId: oHit.id });
			} else {
				sap.m.MessageToast.show("No document matches “" + sQuery + "”.");
			}
		}
	});
});
