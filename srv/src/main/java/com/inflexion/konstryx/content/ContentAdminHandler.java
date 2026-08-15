package com.inflexion.konstryx.content;

import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.EventContext;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Exposes content deployment as an administrator action, so an upgrade that
 * ships a new pack version can be applied without a service restart.
 */
@Component
@ServiceName("AuthorizationService")
public class ContentAdminHandler implements EventHandler {

    @Autowired
    private ContentDeploymentService content;

    @On(event = "applyContentPacks")
    public void onApplyContentPacks(EventContext context) {
        // Untyped action context: the return value is carried in the context
        // map under "result". A typed context would need generated POJOs.
        context.put("result", content.applyAll());
        context.setCompleted();
    }
}
