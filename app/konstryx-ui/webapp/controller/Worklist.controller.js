sap.ui.define([
	"konstryx/controller/BaseController",
	"konstryx/lib/ListPersonalization",
	"sap/ui/model/json/JSONModel",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/ui/export/library"
], function (BaseController, ListPersonalization, JSONModel, Filter, FilterOperator, exportLibrary) {
	"use strict";

	return BaseController.extend("konstryx.controller.Worklist", {

		onInit: function () {
			this._oViewModel = new JSONModel({ rows: [], title: "", subtitle: "", tableTitle: "", idColumn: "", docType: "RR" });
			this.getView().setModel(this._oViewModel, "view");
			this.getRouter().getRoute("worklist").attachPatternMatched(this._onMatched, this);
			this._setUpPersonalization();
		},

		/**
		 * Columns, sort, group, filter, saved views and download — registered
		 * once for this table. Every field the list shows is declared here, and
		 * that one declaration is what makes it filterable, sortable, groupable
		 * and exportable: there is no second place to keep in step.
		 */
		_setUpPersonalization: function () {
			var EdmType = exportLibrary.EdmType;

			this._aFields = [
				{ key: "docNo",        label: "Document",     path: "docNo",        edm: EdmType.String,   width: 16 },
				{ key: "verticalType", label: "Type",         path: "verticalType", edm: EdmType.String,   width: 8 },
				{ key: "projectName",  label: "Project",      path: "projectName",  edm: EdmType.String,   width: 28 },
				{ key: "projectCode",  label: "Project code", path: "projectCode",  edm: EdmType.String,   width: 12 },
				{ key: "raisedBy",     label: "Raised by",    path: "raisedBy",     edm: EdmType.String,   width: 24 },
				{ key: "raisedOn",     label: "Raised on",    path: "raisedOn",     edm: EdmType.Date,     width: 14 },
				{ key: "lineCount",    label: "Lines",        path: "lineCount",    edm: EdmType.Number,   width: 8 },
				{ key: "needBy",       label: "Need by",      path: "needBy",       edm: EdmType.Date,     width: 14 },
				{ key: "totalValue",   label: "Value (AED)",  path: "totalValue",   edm: EdmType.Number,   width: 16 },
				{ key: "status",       label: "Status",       path: "status",       edm: EdmType.String,   width: 12 }
			];

			ListPersonalization.attach({
				target: "worklist.requestTable",
				table: this.byId("requestTable"),
				variant: this.byId("worklistVariant"),
				fields: this._aFields,
				controller: this,
				onApply: this._onStateApplied.bind(this)
			});
		},

		/**
		 * The personalization dialog hands back sort, group and filter state.
		 * Sorting and grouping are applied to the binding; filters are ANDed
		 * with the ones the filter bar contributes, so neither silently
		 * replaces the other.
		 */
		_onStateApplied: function (oState) {
			var oBinding = this.byId("requestTable").getBinding("items");
			if (!oBinding) {
				return;
			}
			var aSorters = [];
			(oState.Groups || []).forEach(function (g) {
				aSorters.push(new sap.ui.model.Sorter(g.key, false, true));
			});
			(oState.Sorter || []).forEach(function (srt) {
				aSorters.push(new sap.ui.model.Sorter(srt.key, !!srt.descending));
			});
			oBinding.sort(aSorters);

			this._aP13nFilters = [];
			Object.keys(oState.Filter || {}).forEach(function (sKey) {
				(oState.Filter[sKey] || []).forEach(function (oCond) {
					var v = (oCond.values || [])[0];
					if (v !== undefined && v !== null && v !== "") {
						this._aP13nFilters.push(new Filter(sKey, FilterOperator.Contains, String(v)));
					}
				}, this);
			}, this);

			this._render(this.byId("worklistSearch") ? this.byId("worklistSearch").getValue() : "");
		},

		onTableSettings: function () {
			ListPersonalization.openSettings(this.byId("requestTable"),
				["Columns", "Sorter", "Groups", "Filter"]);
		},

		/** Adapt Filters opens the same engine on the filter panel alone. */
		onAdaptFilters: function () {
			ListPersonalization.openSettings(this.byId("requestTable"), ["Filter"]);
		},

		onVariantSelect: function (oEvent) {
			ListPersonalization.selectVariant("worklist.requestTable", oEvent.getParameter("key"));
		},

		onVariantSave: function (oEvent) {
			ListPersonalization.saveVariant("worklist.requestTable", oEvent);
		},

		/**
		 * Downloads what is on screen, not the whole entity set: the columns the
		 * user chose, in their order, with their filters applied. An export that
		 * ignores the arrangement is a different report from the one they are
		 * looking at.
		 */
		onExportExcel: function () {
			var oBinding = this.byId("requestTable").getBinding("items");
			if (!oBinding) {
				return;
			}
			var aRows = oBinding.getAllCurrentContexts().map(function (c) {
				return c.getObject();
			});
			ListPersonalization.exportToExcel("worklist.requestTable", aRows, "resource-requests");
		},

		onPrint: function () {
			ListPersonalization.printView();
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

			// Filters set in the personalization dialog are ANDed with the ones
			// from the filter bar rather than replacing them, so a user does not
			// silently lose the filter they can see while using the one they
			// cannot.
			aFilters = aFilters.concat(this._aP13nFilters || []);

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
