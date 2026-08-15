sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/m/Dialog",
	"sap/m/Button",
	"sap/m/Select",
	"sap/m/Label",
	"sap/m/VBox",
	"sap/m/Text",
	"sap/ui/core/ListItem",
	"sap/m/MessageBox",
	"sap/m/MessageToast"
], function (BaseController, Dialog, Button, Select, Label, VBox, Text, ListItem, MessageBox, MessageToast) {
	"use strict";

	/**
	 * Project templates.
	 *
	 * Instantiating is the only action here that changes anything, and it is not
	 * reversible from this screen — the copy lands in the project's own CBS. The
	 * dialog therefore names what will be created before asking, and the service
	 * refuses a second run rather than silently duplicating.
	 */
	return BaseController.extend("konstryx.controller.MasterTemplates", {

		onInit: function () {
			this.getRouter().getRoute("masterTemplates").attachPatternMatched(this._onMatched, this);
		},

		_onMatched: function () {
			this.setNavKey("masters");
			var oBinding = this.byId("templateTable").getBinding("items");
			if (oBinding) {
				oBinding.attachEventOnce("dataReceived", function () {
					this.byId("tableTitle").setText("Templates (" + oBinding.getLength() + ")");
				}, this);
			}
		},

		onSelect: function (oEvent) {
			this._oSelected = oEvent.getParameter("listItem").getBindingContext("md");
			this.byId("instantiateButton").setEnabled(true);
			this.byId("selectionHint").setText(
				this._oSelected.getProperty("code") + " — "
				+ this._oSelected.getProperty("constructionType")
				+ " structure and its default resources.");
		},

		onInstantiate: function () {
			var oCtx = this._oSelected;
			if (!oCtx) {
				return;
			}

			var oSelect = new Select({
				width: "100%",
				items: {
					path: "pj>/Projects",
					template: new ListItem({ key: "{pj>code}", text: "{pj>code} · {pj>name}" })
				}
			});

			var oDialog = new Dialog({
				title: "Instantiate " + oCtx.getProperty("code"),
				contentWidth: "26rem",
				content: [
					new VBox({
						class: "sapUiSmallMargin",
						items: [
							new Text({
								text: "The template's cost breakdown structure and default resources are"
									+ " copied into the project. A project that already has a CBS is refused."
							}),
							new Label({ text: "Project", class: "sapUiSmallMarginTop" }),
							oSelect
						]
					})
				],
				beginButton: new Button({
					text: "Instantiate",
					type: "Emphasized",
					press: function () {
						var sProject = oSelect.getSelectedKey();
						oDialog.close();
						this._run(oCtx, sProject);
					}.bind(this)
				}),
				endButton: new Button({ text: "Cancel", press: function () { oDialog.close(); } }),
				afterClose: function () { oDialog.destroy(); }
			});

			this.getView().addDependent(oDialog);
			oDialog.open();
		},

		_run: function (oCtx, sProjectCode) {
			if (!sProjectCode) {
				return;
			}
			var oOperation = this.getModel("md").bindContext("MasterDataService.instantiate(...)", oCtx);
			oOperation.setParameter("projectCode", sProjectCode);
			oOperation.execute().then(function () {
				MessageToast.show(oOperation.getBoundContext().getValue(), { duration: 6000 });
			}).catch(function (oError) {
				// A project that already has a CBS lands here, with the service's
				// own explanation rather than a generic failure.
				MessageBox.error(oError.message || "The template could not be instantiated.");
			});
		}
	});
});
