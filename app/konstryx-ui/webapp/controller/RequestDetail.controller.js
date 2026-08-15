sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/json/JSONModel",
	"sap/m/MessageBox"
], function (BaseController, JSONModel, MessageBox) {
	"use strict";

	return BaseController.extend("konstryx.controller.RequestDetail", {

		onInit: function () {
			this._oViewModel = new JSONModel({ req: {}, wbs: [] });
			this.getView().setModel(this._oViewModel, "view");
			this.getRouter().getRoute("request").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function (oEvent) {
			var sId = oEvent.getParameter("arguments").requestId,
				oData = this.getData(),
				oReq = oData.requests.filter(function (r) { return r.id === sId; })[0];

			if (!oReq) { this.getRouter().getTargets().display("notFound"); return; }

			this.setNavKey("RR");
			this._sRequestId = sId;

			var oCopy = JSON.parse(JSON.stringify(oReq));
			oCopy.valueText = Number(oCopy.value).toLocaleString("en-US");

			this._oViewModel.setData({ req: oCopy, wbs: this._rollUpWbs(oCopy) });

			var oPage = this.byId("requestObjectPage");
			if (oPage) { oPage.setSelectedSection(this.createId("secFlow")); }
		},

		/** Aggregate the line values per WBS — the allocation card is derived, never keyed. */
		_rollUpWbs: function (oReq) {
			var mHeadroom = { "WBS-2.04": 1240000, "WBS-1.02": 385000, "WBS-0.10": 412000 },
				mNames = { "WBS-2.04": "Super-structure", "WBS-1.02": "Sub-structure", "WBS-0.10": "Site Establishment" },
				mAgg = {};

			(oReq.lines || []).forEach(function (l) {
				if (!mAgg[l.wbs]) { mAgg[l.wbs] = { wbs: l.wbs, name: mNames[l.wbs] || l.wbsName, lines: 0, value: 0 }; }
				mAgg[l.wbs].lines += 1;
				mAgg[l.wbs].value += l.value;
			});

			return Object.keys(mAgg).map(function (k) {
				var o = mAgg[k];
				o.headroom = (mHeadroom[k] || 0) - o.value;
				o.check = o.headroom > 0 ? "Within budget" : "Over budget";
				o.checkState = o.headroom > 0 ? "Success" : "Error";
				return o;
			});
		},

		// ---------------------------------------------------------------- chain

		formatChainButton: function (iStep) {
			return iStep === 1 ? "Emphasized" : "Transparent";
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
			if (oNode.step === 1) { return; }
			this.navTo("doc", { requestId: this._sRequestId, step: String(oNode.step) });
		},

		onOpenStep: function (oEvent) {
			var sStep = oEvent.getSource().data("step");
			this.navTo("doc", { requestId: this._sRequestId, step: sStep });
		},

		onLinePress: function (oEvent) {
			var oLine = oEvent.getSource().getBindingContext("view").getObject();
			MessageBox.information(
				oLine.no + " · " + oLine.resource + "\n\n" +
				"Code: " + oLine.code + "\n" +
				"WBS: " + oLine.wbs + " " + oLine.wbsName + " · CBS " + oLine.cbs + "\n" +
				"Scope: " + oLine.qty + " instances × " + oLine.days + " days\n" +
				"Source: " + oLine.source + " · " + oLine.sourceDetail + "\n" +
				"Line value: AED " + Number(oLine.value).toLocaleString("en-US"),
				{ title: "Line detail" }
			);
		},

		onBreadcrumbHome: function () { this.navTo("launchpad"); },
		onBreadcrumbWorklist: function () { this.navTo("worklist", { docType: "RR" }); }
	});
});
