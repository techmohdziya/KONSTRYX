sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxpaymentapplication/test/integration/pages/PaymentApplicationsList.gen",
	"konstryxpaymentapplication/test/integration/pages/PaymentApplicationsObjectPage.gen"
], function (JourneyRunner, PaymentApplicationsListGenerated, PaymentApplicationsObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxpaymentapplication') + '/test/flp.html#app-preview',
        pages: {
			onThePaymentApplicationsListGenerated: PaymentApplicationsListGenerated,
			onThePaymentApplicationsObjectPageGenerated: PaymentApplicationsObjectPageGenerated
        },
        async: true
    });

    return runner;
});

