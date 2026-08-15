sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/json/JSONModel"
], function (BaseController, JSONModel) {
	"use strict";

	return BaseController.extend("konstryx.controller.ChainStep", {

		onInit: function () {
			this._oViewModel = new JSONModel({ doc: {}, lines: [], req: {} });
			this.getView().setModel(this._oViewModel, "view");
			this.getRouter().getRoute("doc").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function (oEvent) {
			var oArgs = oEvent.getParameter("arguments"),
				iStep = parseInt(oArgs.step, 10),
				sRequestId = oArgs.requestId,
				oData = this.getData(),
				oDoc = oData.chain.filter(function (c) { return c.step === iStep; })[0],
				oReq = oData.requests.filter(function (r) { return r.id === sRequestId; })[0];

			if (!oDoc || !oReq) { this.getRouter().getTargets().display("notFound"); return; }

			this.setNavKey(oDoc.code);
			this._iStep = iStep;
			this._sRequestId = sRequestId;

			// Per-line view for this step: same five lines, but the step-specific
			// column changes — that is the multi-line model carried down the chain.
			var sPath = oDoc.lineExtra ? oDoc.lineExtra.path : null;
			var aLines = (oReq.lines || []).map(function (l) {
				var oCopy = JSON.parse(JSON.stringify(l));
				oCopy.stepText = sPath && oData.lineTexts[l.no] ? oData.lineTexts[l.no][sPath] : "—";
				return oCopy;
			});

			var aPrimary = (oDoc.actions || []).filter(function (a) { return a.type === "Emphasized"; });

			this._oViewModel.setData({
				doc: oDoc,
				req: oReq,
				requestId: sRequestId,
				lines: aLines,
				lineCount: aLines.length,
				stepColumn: oDoc.lineExtra ? oDoc.lineExtra.label : "Detail",
				ownerNote: oDoc.owner === "S/4 PS"
					? "system of record — read-only in KONSTRYX"
					: "KONSTRYX owns this document",
				readOnlyText: "S/4HANA Project System owns this document. KONSTRYX displays the synced values and never authors them — posting, reversal and release all happen in S/4.",
				hasPrimary: aPrimary.length > 0,
				primaryText: aPrimary.length ? aPrimary[0].text : "",
				primaryTarget: aPrimary.length ? aPrimary[0].target : null,
				hasPrev: iStep > 1,
				hasNext: iStep < 10,
				nextText: iStep < 10 ? "Next: " + oData.chain[iStep].title : "",
				footerNote: "Step " + iStep + " of 10 · " + oDoc.code + " · thread " + sRequestId
			});

			var oPage = this.byId("docObjectPage");
			if (oPage) { oPage.setSelectedSection(this.createId("secFlow")); }
		},

		// ---------------------------------------------------------------- chain

		formatChainButton: function (iStep) {
			return iStep === this._iStep ? "Emphasized" : "Transparent";
		},

		formatChainIcon: function (sState) {
			switch (sState) {
				case "Success": return "sap-icon://sys-enter-2";
				case "Warning": return "sap-icon://pending";
				case "Error":   return "sap-icon://error";
				default:        return "sap-icon://circle-task-2";
			}
		},

		formatNumber: function (v) {
			return (v === null || v === undefined || v === "") ? "" : Number(v).toLocaleString("en-US");
		},

		onChainStepPress: function (oEvent) {
			var oNode = oEvent.getSource().getBindingContext().getObject();
			this._goto(oNode.step);
		},

		_goto: function (iStep) {
			if (iStep === this._iStep) { return; }
			if (iStep === 1) {
				this.navTo("request", { requestId: this._sRequestId });
			} else {
				this.navTo("doc", { requestId: this._sRequestId, step: String(iStep) });
			}
		},

		onPrimaryAction: function () {
			this._goto(this._oViewModel.getProperty("/primaryTarget"));
		},

		onNextStep: function () { this._goto(this._iStep + 1); },
		onPrevStep: function () { this._goto(this._iStep - 1); },

		onBreadcrumbHome: function () { this.navTo("launchpad"); },
		onBreadcrumbRequest: function () { this.navTo("request", { requestId: this._sRequestId }); },
		onBreadcrumbWorklist: function () {
			this.navTo("worklist", { docType: this._oViewModel.getProperty("/doc/code") });
		}
	});
});
