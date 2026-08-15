sap.ui.define([
	"sap/ui/model/json/JSONModel",
	"sap/ui/Device"
], function (JSONModel, Device) {
	"use strict";

	return {

		createDeviceModel: function () {
			var oModel = new JSONModel(Device);
			oModel.setDefaultBindingMode("OneWay");
			return oModel;
		},

		/**
		 * UI state that is not business data: which nav item is selected,
		 * whether the side navigation is collapsed, the active company.
		 */
		createAppStateModel: function () {
			return new JSONModel({
				navExpanded: true,
				selectedKey: "launchpad",
				activeCompany: "INFC"
			});
		}
	};
});
