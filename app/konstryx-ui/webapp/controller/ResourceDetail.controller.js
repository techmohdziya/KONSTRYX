sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/ui/model/json/JSONModel",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, Filter, FilterOperator, JSONModel, MessageBox, MessageToast) {
	"use strict";

	/**
	 * Resource master object page.
	 *
	 * The route carries the resource code rather than its UUID: a master code is
	 * what people quote to each other, and a link to EQ-TWC-12T survives a data
	 * reload while a link to a generated key does not. The code is resolved to a
	 * context on entry.
	 */
	return BaseController.extend("konstryx.controller.ResourceDetail", {

		onInit: function () {
			this.getView().setModel(new JSONModel({ editing: false, busy: false }), "ui");
			this.getRouter().getRoute("resourceDetail").attachPatternMatched(this._onMatched, this);
		},

		_ui: function (sKey, vValue) {
			this.getView().getModel("ui").setProperty("/" + sKey, vValue);
		},

		_onMatched: function (oEvent) {
			var sCode = decodeURIComponent(oEvent.getParameter("arguments").code);
			this.setNavKey("masters");
			this._sCode = sCode;
			this._bindToCode(sCode);
		},

		/**
		 * Resolve code -> context, then hang the page off it.
		 * bActive false resolves the draft copy instead of the stored record.
		 */
		_bindToCode: function (sCode, bActive) {
			var oView = this.getView(),
				bWantActive = bActive !== false,
				mParameters = { $$updateGroupId: "$auto" };

			// Expand only on the stored record. A draft row carries no association
			// targets of its own, and asking for them makes every drill-down on the
			// draft fail with "invalid segment", which then swallows the whole
			// edit-mode switch.
			if (bWantActive) {
				mParameters.$expand = "owningCompany($select=code,legalName),parent($select=code,description)";
			}

			var oList = this.getModel("md").bindList("/Resources", null, null, [
					new Filter("code", FilterOperator.EQ, sCode),
					new Filter("IsActiveEntity", FilterOperator.EQ, bWantActive)
				], mParameters);

			return oList.requestContexts(0, 1).then(function (aContexts) {
				if (!aContexts.length) {
					this.getRouter().getTargets().display("notFound");
					return;
				}
				oView.setBindingContext(aContexts[0], "md");
				// Only a company-scoped master can be promoted, and only while not
				// mid-edit; a group master is already shared and the service refuses.
				this.byId("promoteButton").setVisible(
					bWantActive && aContexts[0].getProperty("scope") === "COMPANY");
				this._bindRates(sCode);
				this._bindChildren(aContexts[0]);
			}.bind(this));
		},

		/** Every rate for this resource, in either scope, newest first. */
		_bindRates: function (sCode) {
			var oTable = this.byId("rateTable"),
				oBinding = oTable.getBinding("items");
			if (!oBinding) {
				return;
			}
			oBinding.filter([new Filter("resource/code", FilterOperator.EQ, sCode)]);
			oBinding.attachEventOnce("dataReceived", function () {
				this.byId("rateTitle").setText("Rates (" + oBinding.getLength() + ")");
			}, this);
		},

		_bindChildren: function (oCtx) {
			var oBinding = this.byId("childTable").getBinding("items");
			if (!oBinding) {
				return;
			}
			oBinding.filter([new Filter("parent_ID", FilterOperator.EQ, oCtx.getProperty("ID"))]);
			oBinding.attachEventOnce("dataReceived", function () {
				var iCount = oBinding.getLength();
				this.byId("childTitle").setText(iCount
					? "Children (" + iCount + ")"
					: "Nothing sits below this node");
			}, this);
		},

		onChildPress: function (oEvent) {
			var oCtx = oEvent.getSource().getBindingContext("md");
			this.navTo("resourceDetail", { code: encodeURIComponent(oCtx.getProperty("code")) });
		},

		onBackToList: function () {
			this.navTo("masterResources");
		},

		// ------------------------------------------------------------ editing

		/**
		 * Draft editing, the CAP way: draftEdit creates a private copy, the form
		 * binds to that copy, and the active record is untouched until activation.
		 * Two people editing the same master therefore cannot half-overwrite each
		 * other, and an abandoned edit leaves nothing behind.
		 */
		onEdit: function () {
			var oCtx = this.getView().getBindingContext("md");
			if (!oCtx) {
				return;
			}
			this._ui("busy", true);

			// Resume an existing draft rather than failing. Someone who closed the
			// tab mid-edit still owns a draft, and draftEdit refuses to create a
			// second one — without this, that master becomes uneditable until the
			// draft is cleared by hand.
			this._findDraft(this._sCode).then(function (oDraft) {
				if (oDraft) {
					return this._enterEditMode();
				}
				var oEdit = this.getModel("md").bindContext("MasterDataService.draftEdit(...)", oCtx);
				oEdit.setParameter("PreserveChanges", true);
				// Re-resolve the draft as an ordinary entity context afterwards.
				// Binding draftActivate against the operation binding's own context
				// nests one deferred operation inside another, which the model
				// refuses outright.
				return oEdit.execute().then(this._enterEditMode.bind(this));
			}.bind(this)).catch(function (oError) {
				this._ui("busy", false);
				MessageBox.error(oError.message || "This master could not be locked for editing.");
			}.bind(this));
		},

		_enterEditMode: function () {
			return this._bindToCode(this._sCode, false).then(function () {
				this._ui("editing", true);
				this._ui("busy", false);
			}.bind(this));
		},

		/** Resolves to the draft context for this code, or null. */
		_findDraft: function (sCode) {
			var oList = this.getModel("md").bindList("/Resources", null, null, [
				new Filter("code", FilterOperator.EQ, sCode),
				new Filter("IsActiveEntity", FilterOperator.EQ, false)
			]);
			return oList.requestContexts(0, 1).then(function (aContexts) {
				return aContexts.length ? aContexts[0] : null;
			}).catch(function () {
				return null;
			});
		},

		onSave: function () {
			var oCtx = this.getView().getBindingContext("md");
			this._ui("busy", true);
			var oActivate = this.getModel("md").bindContext("MasterDataService.draftActivate(...)", oCtx);
			oActivate.execute().then(function () {
				this._ui("editing", false);
				this._ui("busy", false);
				MessageToast.show("Saved.");
				// Re-resolve from the active record so the page shows what was stored,
				// not what was typed.
				this._bindToCode(this._sCode);
			}.bind(this)).catch(function (oError) {
				this._ui("busy", false);
				// Validation refusals - a duplicate code, a level that does not match
				// its parent - surface here as the service's own message.
				MessageBox.error(oError.message || "The change was rejected.");
			}.bind(this));
		},

		onCancel: function () {
			MessageBox.confirm("Discard the changes?", {
				emphasizedAction: MessageBox.Action.OK,
				onClose: function (sAction) {
					if (sAction !== MessageBox.Action.OK) {
						return;
					}
					var oCtx = this.getView().getBindingContext("md");
					oCtx.delete("$direct").then(function () {
						this._ui("editing", false);
						this._bindToCode(this._sCode);
					}.bind(this)).catch(function () {
						this._ui("editing", false);
						this._bindToCode(this._sCode);
					}.bind(this));
				}.bind(this)
			});
		},

		onRequestPromotion: function () {
			var oCtx = this.getView().getBindingContext("md");
			if (!oCtx) {
				return;
			}
			MessageBox.confirm(
				"Request that " + oCtx.getProperty("code") + " be shared across the whole group?",
				{
					title: "Request promotion",
					emphasizedAction: MessageBox.Action.OK,
					onClose: function (sAction) {
						if (sAction !== MessageBox.Action.OK) {
							return;
						}
						var oOperation = this.getModel("md").bindContext(
							"MasterDataService.requestPromotion(...)", oCtx);
						oOperation.setParameter("reason", "Requested from the resource master page");
						oOperation.execute().then(function () {
							MessageToast.show(oOperation.getBoundContext().getValue());
						}).catch(function (oError) {
							MessageBox.error(oError.message || "The request could not be raised.");
						});
					}.bind(this)
				}
			);
		}
	});
});
