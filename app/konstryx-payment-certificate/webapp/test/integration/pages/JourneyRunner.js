sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxpaymentcertificate/test/integration/pages/PaymentCertificatesList.gen",
	"konstryxpaymentcertificate/test/integration/pages/PaymentCertificatesObjectPage.gen"
], function (JourneyRunner, PaymentCertificatesListGenerated, PaymentCertificatesObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxpaymentcertificate') + '/test/flp.html#app-preview',
        pages: {
			onThePaymentCertificatesListGenerated: PaymentCertificatesListGenerated,
			onThePaymentCertificatesObjectPageGenerated: PaymentCertificatesObjectPageGenerated
        },
        async: true
    });

    return runner;
});

