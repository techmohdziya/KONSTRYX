sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxvendor/test/integration/pages/VendorsList.gen",
	"konstryxvendor/test/integration/pages/VendorsObjectPage.gen"
], function (JourneyRunner, VendorsListGenerated, VendorsObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxvendor') + '/test/flp.html#app-preview',
        pages: {
			onTheVendorsListGenerated: VendorsListGenerated,
			onTheVendorsObjectPageGenerated: VendorsObjectPageGenerated
        },
        async: true
    });

    return runner;
});

