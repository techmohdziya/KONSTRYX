sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxreservation/test/integration/pages/ReservationsList.gen",
	"konstryxreservation/test/integration/pages/ReservationsObjectPage.gen"
], function (JourneyRunner, ReservationsListGenerated, ReservationsObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxreservation') + '/test/flp.html#app-preview',
        pages: {
			onTheReservationsListGenerated: ReservationsListGenerated,
			onTheReservationsObjectPageGenerated: ReservationsObjectPageGenerated
        },
        async: true
    });

    return runner;
});

