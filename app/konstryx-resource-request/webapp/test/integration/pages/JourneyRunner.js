sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxresourcerequest/test/integration/pages/ResourceRequestsList.gen",
	"konstryxresourcerequest/test/integration/pages/ResourceRequestsObjectPage.gen"
], function (JourneyRunner, ResourceRequestsListGenerated, ResourceRequestsObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxresourcerequest') + '/test/flp.html#app-preview',
        pages: {
			onTheResourceRequestsListGenerated: ResourceRequestsListGenerated,
			onTheResourceRequestsObjectPageGenerated: ResourceRequestsObjectPageGenerated
        },
        async: true
    });

    return runner;
});

