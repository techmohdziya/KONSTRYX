sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/json/JSONModel"
], function (BaseController, JSONModel) {
	"use strict";

	return BaseController.extend("konstryx.controller.Worklist", {

		onInit: function () {
			this._oViewModel = new JSONModel({ rows: [], title: "", subtitle: "", tableTitle: "", idColumn: "", docType: "RR" });
			this.getView().setModel(this._oViewModel, "view");
			this.getRouter().getRoute("worklist").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function (oEvent) {
			var sDocType = oEvent.getParameter("arguments").docType;
			this.setNavKey(sDocType);
			this._sDocType = sDocType;
			this._render();
		},

		/**
		 * Step 1 (RR) lists the requests themselves. Steps 2–10 list the chain
		 * documents of that type — each row still carries the request it belongs
		 * to, so a click lands on the right document of the right thread.
		 */
		_render: function (sQuery) {
			var oData = this.getData(),
				sType = this._sDocType,
				oDocType = oData.docTypes.filter(function (d) { return d.code === sType; })[0] || oData.docTypes[0],
				aRows = [];

			if (sType === "RR") {
				aRows = oData.requests.map(function (r) {
					return {
						id: r.id, type: r.type, title: r.title, sub: r.dominantLine,
						scope: r.lineCount + " lines · " + r.wbsCount + " WBS",
						window: r.window, valueText: Number(r.value).toLocaleString("en-US"),
						status: r.state, statusState: r.stateType,
						date: r.raisedOn, requestId: r.id, step: 1
					};
				});
			} else {
				var oReq = oData.requests[0];
				aRows = oData.chain.filter(function (c) { return c.code === sType; }).map(function (c) {
					return {
						id: c.id, type: oReq.type, title: c.title, sub: c.persona,
						scope: oReq.lineCount + " lines · " + oReq.instances + " inst",
						window: oReq.window, valueText: Number(oReq.value).toLocaleString("en-US"),
						status: c.status, statusState: c.statusState,
						date: c.date, requestId: c.request, step: c.step
					};
				});
			}

			var sTypeFilter = this.byId("typeFilter") ? this.byId("typeFilter").getSelectedKey() : "ALL";
			if (sTypeFilter && sTypeFilter !== "ALL") {
				aRows = aRows.filter(function (r) { return r.type === sTypeFilter; });
			}
			if (sQuery) {
				var q = sQuery.toLowerCase();
				aRows = aRows.filter(function (r) {
					return (r.id + " " + r.title).toLowerCase().indexOf(q) > -1;
				});
			}

			this._oViewModel.setData({
				rows: aRows,
				docType: sType,
				title: oDocType.plural,
				subtitle: "Step " + oDocType.step + " of the canonical chain · owned by " + oDocType.owner +
					" · scoped to " + oData.project.id + " " + oData.project.name,
				tableTitle: oDocType.plural + " (" + aRows.length + ")",
				idColumn: oDocType.code === "RR" ? "Request ID" : oDocType.name + " ID"
			});
		},

		onSearch: function (oEvent) {
			this._render(oEvent.getParameter("newValue"));
		},

		onFilterChange: function () {
			this._render(this.byId("worklistSearch").getValue());
		},

		onRowPress: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("view").getObject();
			if (oRow.step === 1) {
				this.navTo("request", { requestId: oRow.requestId });
			} else {
				this.navTo("doc", { requestId: oRow.requestId, step: String(oRow.step) });
			}
		}
	});
});
