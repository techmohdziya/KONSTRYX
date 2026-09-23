sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxbooklet/test/integration/pages/PeriodReportsList.gen",
	"konstryxbooklet/test/integration/pages/PeriodReportsObjectPage.gen"
], function (JourneyRunner, PeriodReportsListGenerated, PeriodReportsObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxbooklet') + '/test/flp.html#app-preview',
        pages: {
			onThePeriodReportsListGenerated: PeriodReportsListGenerated,
			onThePeriodReportsObjectPageGenerated: PeriodReportsObjectPageGenerated
        },
        async: true
    });

    return runner;
});

