sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/json/JSONModel",
	"sap/m/MessageBox"
], function (BaseController, JSONModel, MessageBox) {
	"use strict";

	/**
	 * The Engineer's Payment Certificate — one subcontractor PA, certified.
	 * Per KONSTRYX_Wireframe_v12/modules/subcontract.html (route scr-pa-cert):
	 * claimed vs certified reconciliation, the LD (liquidated damages)
	 * calculation with its EOT offset, back-charges debited to the PA, the
	 * re-measurement log, and the sign-off chain that ends in the S/4
	 * supplier invoice this certificate triggers.
	 *
	 * Read-only display for this first increment: certifying (which would
	 * write the S/4 invoice) is not built here.
	 */
	return BaseController.extend("konstryx.controller.PaymentCertificate", {

		onInit: function () {
			this.getView().setModel(new JSONModel({ pc: {}, summaryRows: [] }), "view");
			this.getRouter().getRoute("paymentCertificate").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function (oEvent) {
			this.setNavKey("paymentCertificates");
			var sCertId = oEvent.getParameter("arguments").certId,
				that = this;

			this.getModel("scr").bindContext("/PaymentCertificates(ID=" + sCertId + ")", null, {
				$expand: "adjustments,ldSteps,backCharges,signOffs"
			}).requestObject().then(function (oPC) {
				that._render(oPC);
			}).catch(function (oError) {
				MessageBox.error(oError.message || "The certificate could not be read.");
			});
		},

		_render: function (oPC) {
			// CAP's OData V4 Decimal fields arrive as strings on this read
			// (confirmed live: "590000.00", typeof string) — the same
			// IEEE754Compatible behaviour documented elsewhere in this app for
			// action parameters shows up on plain reads too. Coerce every
			// decimal once, up front, so no `+`/`-` below can silently
			// string-concatenate instead of adding (`"590000.00" + -59000`
			// gives the string "590000.00-59000", not 531000).
			var fFmt = function (v) {
				return Number(v || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
			};
			var nClaimedGross = Number(oPC.claimedGross),
				nAdjustment = Number(oPC.adjustment),
				nCertifiedGross = Number(oPC.certifiedGross),
				nRetentionPct = Number(oPC.retentionPct),
				nRetentionAmount = Number(oPC.retentionAmount),
				nNetCertified = Number(oPC.netCertified);

			oPC.subtitle = "Engineer's certification of " + oPC.docNo.replace(/^PC-/, "PA-")
				+ ". Certifying triggers the S/4 supplier invoice under " + oPC.s4Api
				+ " (SAP_COM_0057).";
			oPC.certLabel = "PC-…-" + String(oPC.certSeq).padStart(2, "0");
			oPC.claimedGrossText = fFmt(nClaimedGross);
			oPC.adjustmentText = fFmt(nAdjustment);
			oPC.certifiedGrossText = fFmt(nCertifiedGross);
			oPC.netCertifiedText = fFmt(nNetCertified);

			var fBackChargeSum = (oPC.backCharges || []).reduce(function (n, r) {
				return n + Number(r.amount || 0);
			}, 0);
			oPC.backChargeFooter = "Back-charge — debit to subcontractor PA: AED " + fFmt(fBackChargeSum);

			(oPC.ldSteps || []).sort(function (a, b) { return a.stepNo - b.stepNo; });
			(oPC.signOffs || []).sort(function (a, b) { return a.seq - b.seq; });
			(oPC.signOffs || []).forEach(function (oRow) {
				// A plain JSONModel holds the raw ISO string the OData response
				// already gave us — sap.ui.model.odata.type.DateTime is for a
				// live OData binding, not a value already parsed into JSON, so
				// the date is formatted here rather than via a binding type.
				var oDate = new Date(oRow.decidedOn);
				oRow.decidedOnText = isNaN(oDate.getTime()) ? oRow.decidedOn
					: oDate.toLocaleString("en-US", {
						day: "2-digit", month: "short", year: "numeric",
						hour: "2-digit", minute: "2-digit"
					});
			});

			var fRetentionClaimed = -(nClaimedGross * nRetentionPct / 100);
			var fRetentionCertified = -nRetentionAmount;
			var aSummary = [
				{
					label: "This-period gross",
					claimed: fFmt(nClaimedGross), certified: fFmt(nCertifiedGross),
					delta: fFmt(nCertifiedGross - nClaimedGross), emphasis: false
				},
				{
					label: "− Retention " + oPC.retentionPct + " % on certified",
					claimed: fFmt(fRetentionClaimed), certified: fFmt(fRetentionCertified),
					delta: fFmt(fRetentionCertified - fRetentionClaimed), emphasis: false
				},
				{
					label: "= Net Payable",
					claimed: fFmt(nClaimedGross + fRetentionClaimed),
					certified: fFmt(nNetCertified),
					delta: fFmt(nNetCertified - (nClaimedGross + fRetentionClaimed)),
					emphasis: true
				}
			];

			this.getView().getModel("view").setData({ pc: oPC, summaryRows: aSummary });
		}
	});
});
