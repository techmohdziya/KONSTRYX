sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxbudget/test/integration/pages/BudgetsList.gen",
	"konstryxbudget/test/integration/pages/BudgetsObjectPage.gen"
], function (JourneyRunner, BudgetsListGenerated, BudgetsObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxbudget') + '/test/flp.html#app-preview',
        pages: {
			onTheBudgetsListGenerated: BudgetsListGenerated,
			onTheBudgetsObjectPageGenerated: BudgetsObjectPageGenerated
        },
        async: true
    });

    return runner;
});

