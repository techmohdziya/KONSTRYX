sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxresource/test/integration/pages/ResourcesList.gen",
	"konstryxresource/test/integration/pages/ResourcesObjectPage.gen"
], function (JourneyRunner, ResourcesListGenerated, ResourcesObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxresource') + '/test/flp.html#app-preview',
        pages: {
			onTheResourcesListGenerated: ResourcesListGenerated,
			onTheResourcesObjectPageGenerated: ResourcesObjectPageGenerated
        },
        async: true
    });

    return runner;
});

