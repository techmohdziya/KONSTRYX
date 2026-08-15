package com.inflexion.konstryx.sys;

import com.sap.cds.CdsData;
import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.cds.CdsCreateEventContext;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.runtime.CdsRuntime;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Attachments on any business object.
 *
 * The target is polymorphic — an entity name and a key rather than a typed
 * association — which is what lets one attachment table serve every object
 * without each module growing its own. The cost is that no foreign key protects
 * it, so the checks a foreign key would have given us are made here.
 */
@Component
@ServiceName("CollaborationService")
public class AttachmentHandler implements EventHandler {

    private static final String E_ATTACHMENT = "konstryx.sys.Attachment";

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    @Before(event = "CREATE", entity = "CollaborationService.Attachments")
    public void beforeCreate(CdsCreateEventContext context, List<CdsData> attachments) {
        for (CdsData attachment : attachments) {
            String entityName = str(attachment.get("entityName"));
            String objectID = str(attachment.get("objectID"));

            if (entityName == null || objectID == null) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "An attachment must say which object it belongs to.");
            }
            if (isBlank(str(attachment.get("fileName")))) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "The file needs a name.");
            }

            objectID = objectID.toLowerCase();
            attachment.put("objectID", objectID);

            Row target = loadTarget(entityName, objectID);
            // Denormalised so an attachment list needs no join back into an
            // entity the list does not otherwise know how to reach.
            if (attachment.get("objectDocNo") == null && target.get("docNo") != null) {
                attachment.put("objectDocNo", target.get("docNo"));
            }

            applyVersioning(attachment, entityName, objectID);
        }
    }

    /**
     * A second upload of the same file name against the same object is a new
     * version of it, not a duplicate. Superseded versions stay: on a
     * construction project the drawing that was current when work was approved
     * matters as much as the current one.
     */
    private void applyVersioning(CdsData attachment, String entityName, String objectID) {
        String fileName = str(attachment.get("fileName"));

        Optional<Row> latest = db.run(Select.from(E_ATTACHMENT)
                        .where(a -> a.get("entityName").eq(entityName)
                                .and(a.get("objectID").eq(objectID))
                                .and(a.get("fileName").eq(fileName))))
                .stream()
                .max(Comparator.comparingInt(r -> intOf(r.get("version"))));

        if (latest.isPresent()) {
            attachment.put("version", intOf(latest.get().get("version")) + 1);
            attachment.put("supersedes_ID", latest.get().get("ID"));
        } else {
            attachment.put("version", 1);
        }
    }

    private Row loadTarget(String entityName, String objectID) {
        if (runtime.getCdsModel().findEntity(entityName).isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    entityName + " is not an entity in this model.");
        }
        return db.run(Select.from(entityName).where(e -> e.get("ID").eq(objectID)))
                .first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "There is no " + entityName + " with key " + objectID
                                + " to attach anything to."));
    }

    // ----------------------------------------------------------------- helpers

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static boolean isBlank(String s) { return s == null || s.isBlank(); }

    private static int intOf(Object v) {
        if (v instanceof Number n) {
            return n.intValue();
        }
        try { return v == null ? 0 : Integer.parseInt(v.toString()); }
        catch (NumberFormatException e) { return 0; }
    }
}
