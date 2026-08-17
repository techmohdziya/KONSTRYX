sap.ui.define([
	"konstryx/controller/BaseController"
], function (BaseController) {
	"use strict";

	/**
	 * Payment Certificates worklist. Commercial's entry point — first
	 * increment of the SCR (Subcontracting Request) chain, per
	 * KONSTRYX_Wireframe_v12/modules/subcontract.html. The surrounding
	 * twelve nodes (SR, Advisory, RFQ, Bid, Award, Sub-BOQ, the PA worklist,
	 * Variation, TOC, Final Account) are the wireframe's other screens and
	 * are not built here.
	 */
	return BaseController.extend("konstryx.controller.PaymentCertificates", {

		onInit: function () {
			this.getRouter().getRoute("paymentCertificates").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function () {
			this.setNavKey("paymentCertificates");
			var oBinding = this.byId("certTable").getBinding("items");
			if (oBinding) {
				oBinding.attachEventOnce("dataReceived", function () {
					this.byId("certCount").setText("Certificates (" + oBinding.getLength() + ")");
				}, this);
			}
		},

		onOpen: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("scr").getObject();
			this.navTo("paymentCertificate", { certId: oRow.ID });
		}
	});
});
