package com.inflexion.konstryx.apr;

import com.sap.cds.Row;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.request.UserInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.Map;
import java.util.Optional;

/**
 * Binds the approval actions to the engine.
 *
 * The bound actions arrive with the step's key in the CQN target rather than in
 * the parameters, so the key is read from there.
 */
@Component
@ServiceName("CollaborationService")
public class ApprovalHandler implements EventHandler {

    @Autowired
    private ApprovalEngine engine;

    @Autowired
    private UserInfo userInfo;

    @Autowired
    private PersistenceService db;

    @On(event = "submitForApproval")
    public void onSubmit(EventContext context) {
        String entityName = required(context, "entityName");
        String objectID = required(context, "objectID");
        String docNo = str(context.get("docNo"));
        BigDecimal amount = dec(context.get("amount"));
        String companyID = str(context.get("companyID"));

        Map<String, Object> result = engine.submit(
                entityName, objectID.toLowerCase(),
                docNo == null ? objectID : docNo,
                amount, companyID, userInfo.getName());

        context.put("result", result.get("message"));
        context.setCompleted();
    }

    @On(event = "approve")
    public void onApprove(EventContext context) {
        context.put("result", engine.decide(stepKey(context), "APPROVED",
                str(context.get("comment")), userInfo.getName()));
        context.setCompleted();
    }

    @On(event = "reject")
    public void onReject(EventContext context) {
        String comment = str(context.get("comment"));
        if (comment == null || comment.isBlank()) {
            // A rejection without a reason sends the document back with nothing
            // to act on, which is the commonest complaint about approval inboxes.
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Give a reason for the rejection so the submitter knows what to correct.");
        }
        context.put("result", engine.decide(stepKey(context), "REJECTED", comment, userInfo.getName()));
        context.setCompleted();
    }

    @On(event = "delegate")
    public void onDelegate(EventContext context) {
        context.put("result", engine.delegate(stepKey(context), str(context.get("to")),
                str(context.get("comment")), userInfo.getName()));
        context.setCompleted();
    }

    @On(event = "withdraw")
    public void onWithdraw(EventContext context) {
        context.put("result", engine.withdraw(instanceKey(context),
                str(context.get("reason")), userInfo.getName()));
        context.setCompleted();
    }

    // ----------------------------------------------------------------- helpers

    private String stepKey(EventContext context) {
        return keyOf(context, "step");
    }

    private String instanceKey(EventContext context) {
        return keyOf(context, "approval");
    }

    /**
     * The bound entity's key. A bound action carries its target in the CQN, not
     * in the parameters, so the target is read back and its key taken from the
     * row — the same approach the template and promotion actions use.
     */
    private String keyOf(EventContext context, String what) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        if (select != null) {
            Optional<Row> row = db.run(select).first();
            if (row.isPresent() && row.get().get("ID") != null) {
                return String.valueOf(row.get().get("ID")).toLowerCase();
            }
        }
        throw new ServiceException(ErrorStatuses.NOT_FOUND,
                "Could not tell which " + what + " this action is for.");
    }

    private static String required(EventContext context, String name) {
        Object value = context.get(name);
        if (value == null || String.valueOf(value).isBlank()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST, name + " is required.");
        }
        return String.valueOf(value);
    }

    private static String str(Object v) { return v == null ? null : String.valueOf(v); }

    private static BigDecimal dec(Object v) {
        if (v == null) { return null; }
        if (v instanceof BigDecimal b) { return b; }
        try { return new BigDecimal(v.toString()); }
        catch (NumberFormatException e) { return null; }
    }
}
