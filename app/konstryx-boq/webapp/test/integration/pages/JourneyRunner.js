sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxboq/test/integration/pages/BOQsList.gen",
	"konstryxboq/test/integration/pages/BOQsObjectPage.gen"
], function (JourneyRunner, BOQsListGenerated, BOQsObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxboq') + '/test/flp.html#app-preview',
        pages: {
			onTheBOQsListGenerated: BOQsListGenerated,
			onTheBOQsObjectPageGenerated: BOQsObjectPageGenerated
        },
        async: true
    });

    return runner;
});

