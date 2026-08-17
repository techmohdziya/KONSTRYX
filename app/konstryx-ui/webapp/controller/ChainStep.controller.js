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
				oReq = oData.requests.filter(function (r) { return r.id === sRequestId; })[0];

			// The chain documents are one flat array and each carries the request it
			// was authored for, but this used to filter on step alone. Every thread
			// therefore rendered the equipment thread's documents: opening the
			// manpower reservation showed RES-2026-0188, EQR, 18 instances. Match on
			// the request too, and derive a document where none was authored.
			var oTemplate = oData.chain.filter(function (c) { return c.step === iStep; })[0];
			var oDoc = oData.chain.filter(function (c) {
				return c.step === iStep && c.request === sRequestId;
			})[0];

			if (!oReq || !oTemplate) { this.getRouter().getTargets().display("notFound"); return; }
			if (!oDoc) { oDoc = this._deriveDoc(oTemplate, oReq, iStep); }

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

		/**
		 * Builds a chain document for a thread the mock model never authored one for.
		 *
		 * Only the equipment thread has ten hand-written documents. Rather than show
		 * its numbers under another request's heading, the document is derived from
		 * the request itself: the number carries the request's own sequence, and the
		 * fields are the request's own totals.
		 *
		 * Steps one to four are the part that actually exists for every vertical —
		 * request, advisory, availability, reservation are all seeded. Beyond that
		 * nothing has been recorded for material or manpower yet, and the document
		 * says so instead of borrowing figures from equipment.
		 */
		_deriveDoc: function (oTemplate, oReq, iStep) {
			var mUnits = { EQR: "instances", MPR: "crews", MR: "materials", VR: "vehicles" };
			var sUnit = mUnits[oReq.type] || "lines";
			// RR-2026-0162 -> RES-2026-0162: the chain keeps one sequence per thread.
			var sSeq = String(oReq.id).replace(/^[A-Z]+-/, "");
			var sDocNo = oTemplate.code + "-" + sSeq;
			var bRecorded = iStep <= 4;

			var aFields = [
				{ label: oTemplate.title, value: sDocNo },
				{ label: "Type", value: oReq.type + " · " + oReq.typeName },
				{ label: "Project", value: oReq.project + " · " + oReq.projectName },
				{ label: "Lines", value: oReq.lineCount + " " + sUnit },
				{ label: "Value", value: "AED " + Number(oReq.value).toLocaleString("en-US") },
				{ label: "WBS elements", value: String(oReq.wbsCount) },
				{ label: "Window", value: oReq.window },
				{ label: "Raised by", value: oReq.raisedBy }
			];

			return {
				step: iStep,
				code: oTemplate.code,
				id: sDocNo,
				request: oReq.id,
				title: oTemplate.title,
				owner: oTemplate.owner,
				date: oReq.raisedOn,
				status: bRecorded ? oReq.state : "Not recorded",
				statusState: bRecorded ? (oReq.stateType || "Success") : "None",
				persona: oReq.raisedBy,
				intro: bRecorded
					? ""
					: "No " + oTemplate.title.toLowerCase() + " has been recorded for this "
						+ (oReq.typeName || "").toLowerCase() + " thread yet.",
				fields: aFields,
				// No lineExtra: the per-line step texts were written for the equipment
				// thread, so a derived document leaves that column empty rather than
				// captioning a crew with a crane's inspection note.
				lineExtra: null,
				actions: []
			};
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
