sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/json/JSONModel",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator"
], function (BaseController, JSONModel, Filter, FilterOperator) {
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
		 * Step 1 (RR) is bound straight to the CAP service — see requestTable in
		 * the view. Steps 2–10 still render from the JSON fixture: MOB, OPL, VAR,
		 * DMB and CLS have no CDS entities yet, so there is nothing to bind to.
		 */
		_render: function (sQuery) {
			var oData = this.getData(),
				sType = this._sDocType,
				oDocType = oData.docTypes.filter(function (d) { return d.code === sType; })[0] || oData.docTypes[0],
				aRows = [];

			if (sType !== "RR") {
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
			}

			this._oViewModel.setData({
				rows: aRows,
				docType: sType,
				title: oDocType.plural,
				subtitle: "Step " + oDocType.step + " of the canonical chain · owned by " + oDocType.owner +
					" · scoped to " + oData.project.id + " " + oData.project.name,
				tableTitle: oDocType.plural + (sType === "RR" ? "" : " (" + aRows.length + ")"),
				idColumn: oDocType.code === "RR" ? "Request ID" : oDocType.name + " ID"
			});

			if (sType === "RR") {
				this._applyRequestFilters(sQuery);
			}
		},

		/** Filters are pushed to the service, not applied over a client-side copy. */
		_applyRequestFilters: function (sQuery) {
			var oTable = this.byId("requestTable"),
				oBinding = oTable && oTable.getBinding("items");

			if (!oBinding) {
				return;
			}

			var aFilters = [],
				sTypeFilter = this.byId("typeFilter") ? this.byId("typeFilter").getSelectedKey() : "ALL";

			if (sTypeFilter && sTypeFilter !== "ALL") {
				aFilters.push(new Filter("verticalType", FilterOperator.EQ, sTypeFilter));
			}
			if (sQuery) {
				aFilters.push(new Filter("docNo", FilterOperator.Contains, sQuery));
			}

			oBinding.filter(aFilters);

			// header count comes from the service, once the request settles
			oBinding.attachEventOnce("dataReceived", function () {
				var iCount = oBinding.getLength();
				this._oViewModel.setProperty("/tableTitle", "Resource Requests (" + iCount + ")");
			}, this);
		},

		onSearch: function (oEvent) {
			this._render(oEvent.getParameter("newValue"));
		},

		onFilterChange: function () {
			this._render(this.byId("worklistSearch").getValue());
		},

		/** Row press on the live request table — the OData context carries docNo. */
		onRequestPress: function (oEvent) {
			var oCtx = oEvent.getSource().getBindingContext("kx");
			this.navTo("request", { requestId: oCtx.getProperty("docNo") });
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
