sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxmaterial/test/integration/pages/MaterialsList.gen",
	"konstryxmaterial/test/integration/pages/MaterialsObjectPage.gen"
], function (JourneyRunner, MaterialsListGenerated, MaterialsObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxmaterial') + '/test/flp.html#app-preview',
        pages: {
			onTheMaterialsListGenerated: MaterialsListGenerated,
			onTheMaterialsObjectPageGenerated: MaterialsObjectPageGenerated
        },
        async: true
    });

    return runner;
});

