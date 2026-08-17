sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/json/JSONModel",
	"sap/m/MessageToast"
], function (BaseController, JSONModel, MessageToast) {
	"use strict";

	/**
	 * Manpower: the crews reserved against a project and the daily log that turns
	 * those reservations into actual cost.
	 *
	 * The rows are assembled in the controller rather than bound straight to the
	 * table because the data spans three services. A manpower line lives in
	 * WorkflowService, but its WBS and CBS are ProjectService entities and its
	 * labour-subcontract vendor is a MasterDataService one, and OData v4 cannot
	 * $expand across a service boundary — the association resolves to nothing and
	 * the request fails. So each side is read once and joined here by key, which
	 * is the same approach the budget screens already take.
	 */
	return BaseController.extend("konstryx.controller.ManpowerOverview", {

		onInit: function () {
			this._oViewModel = new JSONModel({
				busy: false,
				lines: [],
				lineCount: 0,
				timesheets: [],
				timesheetCount: 0,
				kpi: {
					heads: 0, ownHeads: 0, lscHeads: 0,
					committed: "0", hours: "0", otHours: "0", loggedCost: "0"
				}
			});
			this.getView().setModel(this._oViewModel, "view");
			this.getRouter().getRoute("manpower").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function () {
			this.setNavKey("MP");
			this._load();
		},

		onRefresh: function () {
			this._load();
		},

		/** Reads a whole entity set as plain objects. */
		_read: function (sModel, sPath, mParameters) {
			var oModel = this.getView().getModel(sModel);
			var oBinding = oModel.bindList(sPath, null, [], [], mParameters || {});
			return oBinding.requestContexts(0, 500).then(function (aContexts) {
				return aContexts.map(function (oContext) { return oContext.getObject(); });
			});
		},

		_load: function () {
			var that = this;
			this._oViewModel.setProperty("/busy", true);

			Promise.all([
				// The request line carries the trade description, the money and the
				// WBS/CBS keys; it is in the same service, so this one expands.
				this._read("kx", "/ManpowerRequestLines", {
					$expand: "line($select=lineNo,description,estTotal,lineStatus,wbs_ID,cbs_ID;$expand=parent($select=docNo))",
					$orderby: "heads desc"
				}),
				this._read("kx", "/Timesheets", { $orderby: "workDate desc" }),
				this._read("pj", "/WBS", { $select: "ID,code,description" }),
				this._read("pj", "/CBS", { $select: "ID,code" }),
				this._read("md", "/Vendors", { $select: "ID,name" })
			]).then(function (aResults) {
				that._apply.apply(that, aResults);
			}).catch(function (oError) {
				MessageToast.show("Manpower could not be loaded: " + oError.message);
			}).finally(function () {
				that._oViewModel.setProperty("/busy", false);
			});
		},

		_apply: function (aLines, aTimesheets, aWbs, aCbs, aVendors) {
			var mWbs = {}, mCbs = {}, mVendor = {};
			aWbs.forEach(function (w) { mWbs[w.ID] = w.code; });
			aCbs.forEach(function (c) { mCbs[c.ID] = c.code; });
			aVendors.forEach(function (v) { mVendor[v.ID] = v.name; });

			var iHeads = 0, iOwn = 0, iLsc = 0, fCommitted = 0;
			var mByLine = {};

			var aRows = aLines.map(function (oLine) {
				var oReq = oLine.line || {};
				var iLineHeads = Number(oLine.heads || 0);
				var fRate = Number(oLine.ratePerHeadDay || 0);
				var iDays = Number(oLine.durationDays || 0);
				// The committed figure is heads x days x the all-in rate. Computed
				// rather than read from the request line so the screen shows its own
				// arithmetic; the two agreeing is what test_content asserts.
				var fCommit = iLineHeads * iDays * fRate;

				iHeads += iLineHeads;
				fCommitted += fCommit;
				if (oLine.sourceType === "OWN") { iOwn += iLineHeads; } else { iLsc += iLineHeads; }

				var oRow = {
					id: oLine.ID,
					lineNo: oReq.lineNo,
					trade: oReq.description || oLine.tradeGrade,
					tradeGrade: oLine.tradeGrade,
					crewId: oLine.crewId || "Floating",
					crewLead: oLine.crewLead || "—",
					heads: iLineHeads,
					sourceType: oLine.sourceType,
					sourceLabel: oLine.sourceType === "OWN"
						? "Own payroll"
						: "LSC · " + (mVendor[oLine.vendor_ID] || "subcontract"),
					durationDays: iDays,
					window: formatWindow(oLine.mobDate, oLine.demobDate),
					rateText: fRate.toLocaleString("en-US", { minimumFractionDigits: 2 }),
					committedText: fCommit.toLocaleString("en-US", { minimumFractionDigits: 2 }),
					wbsCode: mWbs[oReq.wbs_ID] || "—",
					cbsCode: mCbs[oReq.cbs_ID] || "—",
					inductionState: oLine.inductionState || "",
					lineStatus: oReq.lineStatus || "",
					requestDocNo: (oReq.parent || {}).docNo || ""
				};
				mByLine[oLine.ID] = oRow;
				return oRow;
			});

			var fHours = 0, fOt = 0, fLoggedCost = 0;
			var aLog = aTimesheets.map(function (oEntry) {
				var oCrew = mByLine[oEntry.manpowerLine_ID] || {};
				var fReg = Number(oEntry.regularHrs || 0);
				var fOtHrs = Number(oEntry.otHrs || 0);
				var fCost = Number(oEntry.costAmount || 0);
				fHours += fReg;
				fOt += fOtHrs;
				fLoggedCost += fCost;
				return {
					workDate: oEntry.workDate,
					crewId: oCrew.crewId || "—",
					trade: oCrew.trade || "",
					headsPresent: Number(oEntry.headsPresent || 0),
					headsReserved: oCrew.heads || 0,
					presentText: oEntry.headsPresent + " of " + (oCrew.heads || "—"),
					regularHrs: fReg.toFixed(2),
					otHrs: fOtHrs.toFixed(2),
					activity: oEntry.activity || "",
					costText: fCost.toLocaleString("en-US", { minimumFractionDigits: 2 }),
					logStatus: oEntry.logStatus || "Draft"
				};
			});

			this._oViewModel.setProperty("/lines", aRows);
			this._oViewModel.setProperty("/lineCount", aRows.length);
			this._oViewModel.setProperty("/timesheets", aLog);
			this._oViewModel.setProperty("/timesheetCount", aLog.length);
			this._oViewModel.setProperty("/kpi", {
				heads: iHeads,
				ownHeads: iOwn,
				lscHeads: iLsc,
				committed: fCommitted.toLocaleString("en-US"),
				hours: fHours.toLocaleString("en-US"),
				otHours: fOt.toLocaleString("en-US"),
				loggedCost: fLoggedCost.toLocaleString("en-US")
			});
		},

		// ------------------------------------------------------------- events

		onBreadcrumbHome: function () {
			this.navTo("launchpad");
		},

		/** A crew row opens the request it was raised on. */
		onLinePress: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("view").getObject();
			if (oRow && oRow.requestDocNo) {
				this.navTo("request", { requestId: oRow.requestDocNo });
			}
		},

		onExportCrews: function () {
			this._export("/lines", "manpower-crews.xlsx", [
				{ label: "#", property: "lineNo" },
				{ label: "Trade", property: "trade" },
				{ label: "Crew", property: "crewId" },
				{ label: "Crew lead", property: "crewLead" },
				{ label: "Source", property: "sourceLabel" },
				{ label: "Heads", property: "heads", type: "Number" },
				{ label: "Duration (days)", property: "durationDays", type: "Number" },
				{ label: "Rate per head-day (AED)", property: "rateText" },
				{ label: "Committed (AED)", property: "committedText" },
				{ label: "WBS", property: "wbsCode" },
				{ label: "CBS", property: "cbsCode" },
				{ label: "Status", property: "lineStatus" }
			]);
		},

		onExportLog: function () {
			this._export("/timesheets", "manpower-daily-log.xlsx", [
				{ label: "Date", property: "workDate" },
				{ label: "Crew", property: "crewId" },
				{ label: "Trade", property: "trade" },
				{ label: "Heads present", property: "headsPresent", type: "Number" },
				{ label: "Heads reserved", property: "headsReserved", type: "Number" },
				{ label: "Regular hours", property: "regularHrs" },
				{ label: "Overtime hours", property: "otHrs" },
				{ label: "Activity", property: "activity" },
				{ label: "Cost (AED)", property: "costText" },
				{ label: "Log", property: "logStatus" }
			]);
		},

		_export: function (sPath, sFileName, aColumns) {
			var aRows = this._oViewModel.getProperty(sPath);
			sap.ui.require(["sap/ui/export/Spreadsheet"], function (Spreadsheet) {
				new Spreadsheet({
					workbook: { columns: aColumns },
					dataSource: aRows,
					fileName: sFileName
				}).build();
			});
		}
	});

	/**
	 * "14 May → 22 Aug 26". Written out rather than left as two ISO dates because
	 * the mobilization window is read as one span, not two facts.
	 */
	function formatWindow(sFrom, sTo) {
		if (!sFrom && !sTo) { return "—"; }
		var fmt = function (s) {
			if (!s) { return "—"; }
			var d = new Date(s);
			return isNaN(d) ? s : d.toLocaleDateString("en-GB",
				{ day: "2-digit", month: "short", year: "2-digit" });
		};
		return fmt(sFrom) + " → " + fmt(sTo);
	}
});
