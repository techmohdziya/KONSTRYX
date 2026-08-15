package com.inflexion.konstryx.nr;

import com.sap.cds.CdsData;
import com.sap.cds.services.cds.ApplicationService;
import com.sap.cds.services.cds.CdsCreateEventContext;
import com.sap.cds.services.cds.CqnService;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.Before;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.ql.Select;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * Assigns docNo on create, for any entity that has a number range configured
 * against it. Driven by konstryx.nr configuration rather than a switch
 * statement, so adding a document type is configuration, not code.
 *
 * A caller-supplied docNo is left alone: data migration and S/4 mirrors both
 * need to carry numbers that were issued elsewhere.
 */
@Component
@ServiceName(value = "*", type = ApplicationService.class)
public class DocumentNumberHandler implements EventHandler {

    private static final String E_OBJECT = "konstryx.nr.NumberRangeObject";
    private static final String E_COMPANY = "konstryx.admin.Company";

    @Autowired
    private NumberRangeService numberRanges;

    @Autowired
    private PersistenceService db;

    @Before(event = CqnService.EVENT_CREATE)
    public void assignDocumentNumber(CdsCreateEventContext context, List<CdsData> entries) {
        // Only entities that actually carry docNo. A range can be configured
        // against an entity without one — konstryx.wf.AdvisoryDecision has no
        // document number — and blindly writing the field would fail the create
        // rather than the misconfiguration.
        if (context.getTarget().findElement("docNo").isEmpty()) {
            return;
        }

        String entityName = context.getTarget().getQualifiedName();

        String objectCode = objectCodeFor(entityName);
        if (objectCode == null) {
            return;
        }

        for (CdsData entry : entries) {
            Object existing = entry.get("docNo");
            if (existing != null && !existing.toString().isBlank()) {
                continue;   // migration or mirrored document — keep its number
            }
            entry.put("docNo", numberRanges.next(objectCode, companyCodeOf(entry), LocalDate.now()));
        }
    }

    /**
     * Matches on the entity the projection is built over, by suffix: the create
     * targets a service projection while the range is configured against the
     * persistence entity.
     */
    private String objectCodeFor(String entityName) {
        String simple = entityName.substring(entityName.lastIndexOf('.') + 1);
        for (Map<String, Object> row : db.run(Select.from(E_OBJECT)
                .where(o -> o.get("isActive").eq(true)))) {
            Object configured = row.get("entityName");
            if (configured == null) {
                continue;
            }
            String target = configured.toString();
            String targetSimple = target.substring(target.lastIndexOf('.') + 1);
            if (target.equals(entityName)
                    || simple.equals(targetSimple)
                    || simple.equals(targetSimple + "s")) {
                return String.valueOf(row.get("code"));
            }
        }
        return null;
    }

    /** Resolves the company code from the entry's company association, if any. */
    private String companyCodeOf(CdsData entry) {
        Object companyId = entry.get("company_ID");
        if (companyId == null) {
            return "";
        }
        return db.run(Select.from(E_COMPANY).where(c -> c.get("ID").eq(companyId.toString())))
                .first()
                .map(r -> String.valueOf(r.get("code")))
                .orElse("");
    }
}
