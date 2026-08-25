sap.ui.define([
    "sap/fe/test/JourneyRunner",
	"konstryxproject/test/integration/pages/ProjectsList.gen",
	"konstryxproject/test/integration/pages/ProjectsObjectPage.gen"
], function (JourneyRunner, ProjectsListGenerated, ProjectsObjectPageGenerated) {
    'use strict';

    const runner = new JourneyRunner({
        launchUrl: sap.ui.require.toUrl('konstryxproject') + '/test/flp.html#app-preview',
        pages: {
			onTheProjectsListGenerated: ProjectsListGenerated,
			onTheProjectsObjectPageGenerated: ProjectsObjectPageGenerated
        },
        async: true
    });

    return runner;
});

