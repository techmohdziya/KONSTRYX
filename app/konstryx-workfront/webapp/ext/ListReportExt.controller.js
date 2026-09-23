sap.ui.define([
	"sap/ui/core/mvc/ControllerExtension"
], function (ControllerExtension) {
	"use strict";

	/**
	 * Applies filters handed over in the URL query string.
	 *
	 * The dashboard counts overdue fronts and offers the number as a tile. A
	 * tile that says four and opens a list of twelve is worse than one that
	 * does not open at all, because the reader has to work out which four.
	 *
	 * SAP's own answer to this is intent-based navigation, where the launchpad
	 * resolves an intent and passes its parameters to the target. These apps
	 * are served standalone with no launchpad to do the resolving, so the
	 * parameters arrive as a plain query string and something has to read
	 * them. That is all this does.
	 *
	 * setFilterValues is the framework's own API for it. Reaching into the
	 * filter bar's controls directly would work until the next UI5 upgrade
	 * moved them.
	 */
	return ControllerExtension.extend("konstryxworkfront.ext.ListReportExt", {

		override: {

			onAfterRendering: function () {
				// Once. onAfterRendering fires again on every re-render, and
				// re-applying would fight a user who had since cleared the
				// filter themselves.
				if (this._kxApplied) {
					return;
				}
				this._kxApplied = true;

				var oParams = new URLSearchParams(window.location.search);
				// Only the properties this page actually filters on. Anything
				// else in the query string belongs to somebody else.
				var aAllowed = ["state", "projectCode", "wbsCode", "isCritical"];
				var oApi = this.base.getExtensionAPI();
				var aPending = [];

				aAllowed.forEach(function (sName) {
					var sValue = oParams.get(sName);
					if (sValue) {
						aPending.push(oApi.setFilterValues(sName, "EQ", sValue));
					}
				});

				if (!aPending.length) {
					return;
				}
				// Setting a value does not run the search; the table still
				// shows what it loaded before the filter arrived.
				Promise.all(aPending).then(function () {
					if (typeof oApi.refresh === "function") {
						oApi.refresh();
					}
				}).catch(function (oError) {
					// A filter that cannot be applied is not worth breaking the
					// page over - the reader still gets the unfiltered list.
					/* eslint-disable-next-line no-console */
					console.warn("Could not apply URL filters:", oError && oError.message);
				});
			}
		}
	});
});
