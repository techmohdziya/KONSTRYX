sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/json/JSONModel",
	"sap/m/MessageToast"
], function (BaseController, JSONModel, MessageToast) {
	"use strict";

	/**
	 * The reservation overview: one row per reservation, its ten-step chain
	 * progress computed server-side from the live documents, and the S/4
	 * connection state shown honestly — the project sync is live, the CMT
	 * commitment connector is not wired yet.
	 */
	return BaseController.extend("konstryx.controller.ReservationOverview", {

		onInit: function () {
			this._oViewModel = new JSONModel({
				busy: false,
				rows: [],
				kpi: { count: 0, avgDone: "0", encumbered: "0", consumed: "0", burnPct: 0 }
			});
			this.getView().setModel(this._oViewModel, "view");
			this.getRouter().getRoute("reservations").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function () {
			this.setNavKey("RES");
			this._load();
		},

		onRefresh: function () {
			this._load();
		},

		/** Invoke the unbound action and shape its rows for the table. */
		_load: function () {
			var that = this,
				oModel = this.getView().getModel("kx"),
				oBinding = oModel.bindContext("/reservationOverview(...)");

			this._oViewModel.setProperty("/busy", true);
			oBinding.invoke().then(function () {
				var aRaw = (oBinding.getBoundContext().getObject() || {}).value || [];
				that._apply(aRaw);
			}).catch(function (oError) {
				MessageToast.show("Overview could not be computed: " + oError.message);
			}).finally(function () {
				that._oViewModel.setProperty("/busy", false);
			});
		},

		_apply: function (aRaw) {
			var fEncumbered = 0, fConsumed = 0, iSteps = 0;

			var aRows = aRaw.map(function (oRow) {
				var fEnc = Number(oRow.encumbered || 0),
					fCon = Number(oRow.consumed || 0);
				fEncumbered += fEnc;
				fConsumed += fCon;
				iSteps += oRow.stepsDone;
				return {
					reservationID: oRow.reservationID,
					docNo: oRow.docNo,
					rrID: oRow.rrID,
					rrDocNo: oRow.rrDocNo,
					projectCode: oRow.projectCode,
					projectSync: oRow.projectSync,
					executionFlow: oRow.executionFlow,
					status: oRow.status,
					lines: oRow.lines,
					encumberedText: fEnc.toLocaleString("en-US"),
					burnPct: Number(oRow.burnPct || 0),
					verticalType: oRow.verticalType,
					chainScope: oRow.chainScope,
					stepsDone: oRow.stepsDone,
					stepsTotal: oRow.stepsTotal,
					stepsBlocked: oRow.stepsBlocked,
					progressPct: oRow.stepsTotal
						? Math.round(100 * oRow.stepsDone / oRow.stepsTotal) : 0,
					pendingSteps: oRow.pendingSteps || "nothing outstanding",
					blockedSteps: oRow.blockedSteps,
					s4Commitment: oRow.s4Commitment === "CONNECTOR PENDING"
						? "Connector pending" : oRow.s4Commitment
				};
			});

			this._oViewModel.setProperty("/rows", aRows);
			this._oViewModel.setProperty("/kpi", {
				count: aRows.length,
				// Steps done, averaged. Each row's progress bar is divided by its
				// own scope rather than by a flat ten: the chain a material
				// reservation runs is shorter than the one drawn for plant, and
				// scoring both out of ten reports the material thread as further
				// behind the more of it is finished.
				avgDone: aRows.length ? (iSteps / aRows.length).toFixed(1) : "0",
				encumbered: fEncumbered.toLocaleString("en-US"),
				consumed: fConsumed.toLocaleString("en-US"),
				burnPct: fEncumbered > 0 ? Math.round(100 * fConsumed / fEncumbered) : 0
			});
		},

		// ------------------------------------------------------------- events

		/** The row opens the reservation's chain step, where its history lives. */
		onRowPress: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("view").getObject();
			if (oRow.rrDocNo) {
				// RES is step 4 of the ten-step chain in the doc route.
				this.navTo("doc", { requestId: oRow.rrDocNo, step: "4" });
			}
		},

		/** The request column links to the RR that started the thread. */
		onRequestLink: function (oEvent) {
			var oRow = oEvent.getSource().getBindingContext("view").getObject();
			if (oRow.rrDocNo) {
				this.navTo("request", { requestId: oRow.rrDocNo });
			}
		},

		onExportExcel: function () {
			var aRows = this._oViewModel.getProperty("/rows");
			sap.ui.require(["sap/ui/export/Spreadsheet"], function (Spreadsheet) {
				new Spreadsheet({
					workbook: {
						columns: [
							{ label: "Reservation", property: "docNo" },
							{ label: "Request", property: "rrDocNo" },
							{ label: "Project", property: "projectCode" },
							{ label: "Project ERP sync", property: "projectSync" },
							{ label: "Flow", property: "executionFlow" },
							{ label: "Status", property: "status" },
							{ label: "Lines", property: "lines", type: "Number" },
							{ label: "Encumbered (AED)", property: "encumberedText" },
							{ label: "Consumed %", property: "burnPct", type: "Number" },
							{ label: "Chain scope", property: "chainScope" },
							{ label: "Steps done", property: "stepsDone", type: "Number" },
							{ label: "Steps in scope", property: "stepsTotal", type: "Number" },
							{ label: "Pending steps", property: "pendingSteps" },
							{ label: "Blocked steps", property: "blockedSteps" },
							{ label: "ERP commitment", property: "s4Commitment" }
						]
					},
					dataSource: aRows,
					fileName: "reservation-overview.xlsx"
				}).build();
			});
		}
	});
});
