sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxrequisition/test/integration/pages/PurchaseRequisitionsList.gen",
	"konstryxrequisition/test/integration/pages/PurchaseRequisitionsObjectPage.gen"
], function (JourneyRunner, PurchaseRequisitionsListGenerated, PurchaseRequisitionsObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxrequisition') + '/test/flp.html#app-preview',
        pages: {
			onThePurchaseRequisitionsListGenerated: PurchaseRequisitionsListGenerated,
			onThePurchaseRequisitionsObjectPageGenerated: PurchaseRequisitionsObjectPageGenerated
        },
        async: true
    });

    return runner;
});

