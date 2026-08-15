package com.inflexion.konstryx.master;

import com.sap.cds.Row;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * The mdg-queue: promoting a company-local master to group scope.
 *
 * Promotion is deliberately not a field the owner can edit. Making a rate or a
 * resource code visible group-wide affects every other company's costing, so it
 * is a request that a steward decides, with the reason and the decision kept.
 */
@Component
public class PromotionHandler implements EventHandler {

    private static final String E_PROMOTION = "konstryx.admin.PromotionRequest";

    @Autowired
    private PersistenceService db;

    // ------------------------------------------------------- request (master side)

    @Component
    @ServiceName("MasterDataService")
    public static class RequestSide implements EventHandler {

        @Autowired
        private PersistenceService db;

        @On(event = "requestPromotion")
        public void onRequestPromotion(EventContext context) {
            CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
            String entityName = context.getTarget().getQualifiedName();

            Row master = loadTarget(select, entityName);

            String currentScope = String.valueOf(master.getOrDefault("scope", "COMPANY"));
            if ("GROUP".equals(currentScope)) {
                throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "This master is already shared across the group.");
            }

            String code = String.valueOf(master.getOrDefault("code", ""));

            boolean pending = db.run(Select.from(E_PROMOTION)
                    .where(p -> p.get("objectType").eq(entityName)
                            .and(p.get("objectKey").eq(code))
                            .and(p.get("status").eq("PENDING"))))
                    .first().isPresent();
            if (pending) {
                throw new ServiceException(ErrorStatuses.CONFLICT,
                        "A promotion request for " + code + " is already awaiting a decision.");
            }

            Map<String, Object> request = new HashMap<>();
            request.put("ID", UUID.randomUUID().toString());
            request.put("objectType", entityName);
            request.put("objectKey", code);
            request.put("currentScope", currentScope);
            request.put("proposedScope", "GROUP");
            request.put("requester", context.getUserInfo().getName());
            request.put("comment", String.valueOf(context.get("reason")));
            request.put("decision", "PENDING");
            request.put("status", "PENDING");
            request.put("age", 0);
            db.run(Insert.into(E_PROMOTION).entry(request));

            context.put("result", "Promotion requested for " + code + " — awaiting a steward decision.");
            context.setCompleted();
        }

        private Row loadTarget(CqnSelect select, String entityName) {
            Optional<Row> row = (select != null)
                    ? db.run(select).first()
                    : Optional.empty();
            return row.orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                    "Could not read the master to promote from " + entityName + "."));
        }
    }

    // -------------------------------------------------------- decide (steward side)

    @Component
    @ServiceName("AdminService")
    public static class DecisionSide implements EventHandler {

        @Autowired
        private PersistenceService db;

        @On(event = "approve")
        public void onApprove(EventContext context) {
            Row request = loadRequest(context);
            String objectType = String.valueOf(request.get("objectType"));
            String objectKey = String.valueOf(request.get("objectKey"));

            // Promote the master itself: group scope has no owning company.
            // HashMap, not Map.of — the latter rejects null values, and
            // clearing the owner is precisely a null.
            Map<String, Object> promotion = new HashMap<>();
            promotion.put("scope", "GROUP");
            promotion.put("owningCompany_ID", null);

            long updated = db.run(Update.entity(objectType)
                    .data(promotion)
                    .where(m -> m.get("code").eq(objectKey))).rowCount();

            if (updated == 0) {
                throw new ServiceException(ErrorStatuses.NOT_FOUND,
                        "Master " + objectKey + " no longer exists in " + objectType + ".");
            }

            close(context, request, "APPROVED",
                    objectKey + " promoted to group scope.");
        }

        @On(event = "reject")
        public void onReject(EventContext context) {
            Row request = loadRequest(context);
            close(context, request, "REJECTED",
                    String.valueOf(request.get("objectKey")) + " stays local to its company.");
        }

        private void close(EventContext context, Row request, String decision, String message) {
            Map<String, Object> data = new HashMap<>();
            data.put("decision", decision);
            data.put("status", decision);
            data.put("decidedBy", context.getUserInfo().getName());
            String comment = String.valueOf(context.get("comment"));
            if (comment != null && !"null".equals(comment)) {
                data.put("comment", comment);
            }
            db.run(Update.entity(E_PROMOTION).data(data)
                    .where(p -> p.get("ID").eq(request.get("ID"))));

            context.put("result", message);
            context.setCompleted();
        }

        private Row loadRequest(EventContext context) {
            CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
            Optional<Row> row = (select != null) ? db.run(select).first() : Optional.empty();
            Row request = row.orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                    "Promotion request not found."));
            if (!"PENDING".equals(String.valueOf(request.get("status")))) {
                throw new ServiceException(ErrorStatuses.CONFLICT,
                        "This request has already been decided.");
            }
            return request;
        }
    }
}
