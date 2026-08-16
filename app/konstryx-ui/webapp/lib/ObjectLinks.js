sap.ui.define([
	"sap/m/ResponsivePopover",
	"sap/m/List",
	"sap/m/StandardListItem",
	"sap/m/Button",
	"sap/m/Dialog",
	"sap/m/CheckBox",
	"sap/m/VBox",
	"sap/m/Title",
	"sap/m/MessageToast",
	"sap/ui/model/json/JSONModel"
], function (ResponsivePopover, List, StandardListItem, Button, Dialog, CheckBox,
             VBox, Title, MessageToast, JSONModel) {
	"use strict";

	/**
	 * S/4-style object links: an object key rendered as a hyperlink that offers
	 * one or more navigation targets, and which targets appear is the user's
	 * own choice — persisted per user through the same UserVariant backend that
	 * already keeps table layouts isolated between people.
	 *
	 * One target navigates immediately. Several open a popover, the way an S/4
	 * smart link offers its related apps. The registry below is the product's
	 * delivered set; the user's configuration can only hide targets, never
	 * invent them, so a link can never lead somewhere the backend would refuse.
	 */
	var REGISTRY = {
		project: [
			{ key: "boq",     text: "Bill of Quantities",  icon: "sap-icon://list",
			  route: "projectBOQ", args: function (o) { return { projectId: o.ID }; } },
			{ key: "costMapping", text: "Cost Mapping",    icon: "sap-icon://combine",
			  route: "costMapping", args: function (o) { return { projectId: o.ID }; } },
			{ key: "requests", text: "Resource Requests",  icon: "sap-icon://cart",
			  route: "worklist", args: function () { return { docType: "RR" }; } }
		],
		cbs: [
			// The transaction leads: from a bill line the CBS code opens the
			// ASSIGNED node of this project with its recipe resources. The
			// library is a secondary target for whoever maintains it - a
			// transaction must never dump a user into master maintenance.
			{ key: "assigned", text: "Assigned CBS · this project", icon: "sap-icon://overview-chart",
			  route: "projectCBS",
			  args: function (o) { return { projectId: o.projectId, cbsId: o.ID }; } },
			{ key: "library", text: "CBS Library (master)", icon: "sap-icon://org-chart",
			  route: "masterCBS", args: function () { return undefined; } }
		],
		resource: [
			{ key: "detail",  text: "Resource Master",     icon: "sap-icon://tree",
			  route: "resourceDetail",
			  args: function (o) { return { code: encodeURIComponent(o.code) }; } },
			{ key: "rates",   text: "Rate Master",         icon: "sap-icon://money-bills",
			  route: "masterRates", args: function () { return undefined; } },
			{ key: "norms",   text: "Norms",               icon: "sap-icon://trend-up",
			  route: "masterNorms", args: function () { return undefined; } }
		]
	};

	return {

		/**
		 * Opens the link's targets for one object.
		 * @param {sap.ui.core.mvc.Controller} oController owner (for navTo + models)
		 * @param {string} sType   registry key: project | cbs | resource
		 * @param {object} oObject the row data the targets' args draw from
		 * @param {sap.ui.core.Control} oSource the pressed link, popover anchor
		 */
		open: function (oController, sType, oObject, oSource) {
			var that = this;
			this._loadEnabled(oController, sType).then(function (aEnabledKeys) {
				var aTargets = (REGISTRY[sType] || []).filter(function (oTarget) {
					return aEnabledKeys.indexOf(oTarget.key) > -1;
				});

				if (aTargets.length === 0) {
					MessageToast.show("Every link target is switched off for this object. "
						+ "Use Configure links to switch one back on.");
					aTargets = REGISTRY[sType] || [];
				}
				if (aTargets.length === 1) {
					oController.navTo(aTargets[0].route, aTargets[0].args(oObject));
					return;
				}

				var oList = new List({
					items: aTargets.map(function (oTarget) {
						return new StandardListItem({
							title: oTarget.text,
							icon: oTarget.icon,
							type: "Active",
							press: function () {
								oPopover.close();
								oController.navTo(oTarget.route, oTarget.args(oObject));
							}
						});
					})
				});

				var oPopover = new ResponsivePopover({
					title: oObject.code || oObject.docNo || "Navigate",
					contentWidth: "18rem",
					content: [oList],
					endButton: new Button({
						icon: "sap-icon://action-settings",
						tooltip: "Configure links",
						press: function () {
							oPopover.close();
							that._configure(oController, sType);
						}
					}),
					afterClose: function () { oPopover.destroy(); }
				});
				oController.getView().addDependent(oPopover);
				oPopover.openBy(oSource);
			});
		},

		/** The per-user configuration dialog: check the targets you want. */
		_configure: function (oController, sType) {
			var that = this;
			this._loadEnabled(oController, sType).then(function (aEnabledKeys) {
				var aBoxes = (REGISTRY[sType] || []).map(function (oTarget) {
					return new CheckBox({
						text: oTarget.text,
						selected: aEnabledKeys.indexOf(oTarget.key) > -1
					}).data("key", oTarget.key);
				});
				var oDialog = new Dialog({
					title: "Links for " + sType,
					content: [new VBox({ items: aBoxes }).addStyleClass("sapUiSmallMargin")],
					beginButton: new Button({
						text: "Save",
						type: "Emphasized",
						press: function () {
							var aChosen = aBoxes.filter(function (oBox) {
								return oBox.getSelected();
							}).map(function (oBox) { return oBox.data("key"); });
							that._saveEnabled(oController, sType, aChosen).then(function () {
								MessageToast.show("Link settings saved for you.");
							});
							oDialog.close();
						}
					}),
					endButton: new Button({ text: "Cancel", press: function () { oDialog.close(); } }),
					afterClose: function () { oDialog.destroy(); }
				});
				oController.getView().addDependent(oDialog);
				oDialog.open();
			});
		},

		// -------------------------------------------------- per-user persistence

		_variantTarget: function (sType) { return "objectLinks." + sType; },

		_loadEnabled: function (oController, sType) {
			var that = this;
			var oModel = oController.getOwnerComponent().getModel("collab");
			var aAll = (REGISTRY[sType] || []).map(function (t) { return t.key; });
			if (!oModel) {
				return Promise.resolve(aAll);
			}
			var oList = oModel.bindList("/UserVariants", null, null, null, {
				$filter: "target eq '" + this._variantTarget(sType) + "'",
				$select: "ID,payload"
			});
			return oList.requestContexts(0, 10).then(function (aContexts) {
				if (!aContexts.length) {
					return aAll;   // no choice made yet: everything delivered shows
				}
				that._variantId = that._variantId || {};
				that._variantId[sType] = aContexts[0].getObject().ID;
				try {
					var aKeys = JSON.parse(aContexts[0].getObject().payload).enabled;
					return Array.isArray(aKeys) ? aKeys : aAll;
				} catch (e) {
					return aAll;
				}
			}).catch(function () { return aAll; });
		},

		_saveEnabled: function (oController, sType, aKeys) {
			var oModel = oController.getOwnerComponent().getModel("collab");
			if (!oModel) {
				return Promise.resolve();
			}
			var sPayload = JSON.stringify({ enabled: aKeys });
			var sId = (this._variantId || {})[sType];
			if (sId) {
				var oContext = oModel
					.bindContext("/UserVariants(" + sId + ")", null,
						{ $$updateGroupId: "links" })
					.getBoundContext();
				oContext.setProperty("payload", sPayload);
				return oModel.submitBatch("links");
			}
			var oBinding = oModel.bindList("/UserVariants", null, null, null,
				{ $$updateGroupId: "links" });
			var oCreated = oBinding.create({
				target: this._variantTarget(sType),
				variantName: "Link settings",
				payload: sPayload
			});
			oModel.submitBatch("links");
			return oCreated.created();
		}
	};
});
