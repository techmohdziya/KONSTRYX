sap.ui.define([
	"konstryx/controller/BaseController",
	"sap/m/Title",
	"sap/m/Text",
	"sap/m/GenericTile",
	"sap/m/TileContent",
	"sap/m/NumericContent",
	"sap/f/GridContainer",
	"sap/f/GridContainerSettings",
	"sap/f/GridContainerItemLayoutData"
], function (BaseController, Title, Text, GenericTile, TileContent, NumericContent,
             GridContainer, GridContainerSettings, GridContainerItemLayoutData) {
	"use strict";

	return BaseController.extend("konstryx.controller.Launchpad", {

		onInit: function () {
			this.getRouter().getRoute("launchpad").attachPatternMatched(function () {
				this.setNavKey("launchpad");
			}, this);
			this._buildGroups();
		},

		/**
		 * The launchpad's worlds, straight from /tileGroups: the wireframe's
		 * segregation, with the Resource Workflow split by process phase.
		 */
		_buildGroups: function () {
			var oHost = this.byId("tileGroupHost"),
				aGroups = (this.getData() || {}).tileGroups || [],
				that = this;

			aGroups.forEach(function (oGroup) {
				oHost.addItem(new Title({ text: oGroup.title, level: "H4" })
					.addStyleClass("kxGroupTitle"));
				if (oGroup.subtitle) {
					oHost.addItem(new Text({ text: oGroup.subtitle })
						.addStyleClass("kxGroupSub"));
				}
				var oGrid = new GridContainer({
					snapToRow: true,
					layout: new GridContainerSettings({
						rowSize: "5.5rem", columnSize: "5.5rem", gap: "0.5rem"
					})
				});
				oGroup.tiles.forEach(function (oTile) {
					oGrid.addItem(new GenericTile({
						header: oTile.title,
						subheader: oTile.subtitle,
						press: function () {
							that.navTo(oTile.route,
								oTile.arg ? { docType: oTile.arg } : undefined);
						},
						layoutData: new GridContainerItemLayoutData({ columns: 2, rows: 2 }),
						tileContent: new TileContent({
							unit: oTile.unit,
							content: new NumericContent({
								value: oTile.value, valueColor: oTile.state,
								icon: oTile.icon, withMargin: false
							})
						})
					}));
				});
				oHost.addItem(oGrid);
			});
		},

		/**
		 * Chain worklists carry a document type; the master screens are their own
		 * route with no argument, so only pass one when the tile defines it.
		 */
		onTilePress: function (oEvent) {
			var oTile = oEvent.getSource().getBindingContext().getObject();
			this.navTo(oTile.route, oTile.arg ? { docType: oTile.arg } : undefined);
		},

		onOpenCanonical: function () {
			this.navTo("request", { requestId: "RR-2026-0188" });
		}
	});
});
