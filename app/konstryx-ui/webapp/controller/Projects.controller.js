sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/lib/ObjectLinks"
], function (BaseController, ObjectLinks) {
	"use strict";

	return BaseController.extend("konstryx.controller.Projects", {

		onInit: function () {
			this.getRouter().getRoute("projects").attachPatternMatched(function () {
				this.setNavKey("projects");
				var oBinding = this.byId("projectTable").getBinding("items");
				if (oBinding) {
					oBinding.attachEventOnce("dataReceived", function () {
						this.byId("projectCount").setText(
							"Projects (" + oBinding.getLength() + ")");
					}, this);
				}
			}, this);
		},

		onProjectLink: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("pj").getObject();
			ObjectLinks.open(this, "project", oRow, oEvent.getSource());
		}
	});
});
