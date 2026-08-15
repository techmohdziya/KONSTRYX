package com.inflexion.konstryx.io;

import com.sap.cds.services.EventContext;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;

/**
 * Exposes import and export as administrator actions.
 */
@Component
@ServiceName("AuthorizationService")
public class ImportExportHandler implements EventHandler {

    @Autowired
    private ImportExportService io;

    @On(event = "exportCsv")
    public void onExport(EventContext context) {
        String target = String.valueOf(context.get("target"));
        Object templateOnly = context.get("templateOnly");
        context.put("result", io.export(target, Boolean.TRUE.equals(templateOnly)));
        context.setCompleted();
    }

    @On(event = "importCsv")
    public void onImport(EventContext context) {
        String target = String.valueOf(context.get("target"));
        String fileName = context.get("fileName") == null ? "upload.csv"
                : String.valueOf(context.get("fileName"));
        Object content = context.get("content");
        String mode = context.get("mode") == null ? "ALL_OR_NOTHING"
                : String.valueOf(context.get("mode"));

        if (content == null || String.valueOf(content).isBlank()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, "The file is empty.");
        }

        Map<String, Object> result = io.importCsv(target, fileName, String.valueOf(content), mode);

        // A rejected import is a result, not a server error: the run and its
        // per-line reasons are stored, and the caller is told where to look.
        // Throwing here would roll the audit trail back and leave the user with
        // an error and nothing to correct.
        context.put("result", result.get("message")
                + " Import run " + result.get("runId") + " holds the per-line detail.");
        context.setCompleted();
    }
}
