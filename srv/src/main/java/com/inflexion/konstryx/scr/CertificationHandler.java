package com.inflexion.konstryx.scr;

import com.sap.cds.Row;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.ServiceException;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.request.UserInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * Certification of a subcontractor's payment application.
 *
 * What a certificate is worth is derived from its own parts rather than
 * stored independently of them. Before this, every money field was a number
 * someone had typed, so a certificate could state a net figure its own back
 * charge lines contradicted, and nothing would notice.
 */
@Component
@ServiceName("SubcontractService")
public class CertificationHandler implements EventHandler {

    private static final String E_APPLICATION = "konstryx.scr.PaymentApplication";
    private static final String E_CERTIFICATE = "konstryx.scr.PaymentCertificate";
    private static final String E_BACKCHARGE = "konstryx.scr.BackChargeLine";
    private static final String E_SIGNOFF = "konstryx.scr.CertSignOff";

    private static final BigDecimal HUNDRED = new BigDecimal("100");

    @Autowired
    private PersistenceService db;

    @Autowired
    private UserInfo userInfo;

    // ------------------------------------------------------------- certify

    @On(event = "certify")
    public void onCertify(EventContext context) {
        Row application = targetOf(context, "Payment application");
        String applicationId = str(application.get("ID"));

        BigDecimal claimed = decimal(application.get("claimedAmount"));
        if (claimed == null) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The application has no claimed amount, so there is nothing to certify.");
        }

        // Certificates are numbered within their application, so the sequence
        // says "3 of 8" rather than being globally unique and meaningless.
        //
        // The next number follows the highest sequence already used, not the
        // count of rows. An application whose earlier certificates were
        // imported or partly archived has a highest sequence well above its
        // row count, and numbering by count would reissue a number that has
        // already been given to a subcontractor.
        int existing = 0;
        for (Row row : db.run(Select.from(E_CERTIFICATE)
                .where(c -> c.get("pa_ID").eq(applicationId)))) {
            Object seq = row.get("certSeq");
            existing = Math.max(existing, seq instanceof Number n ? n.intValue() : 0);
        }

        BigDecimal retentionPct = decimal(context.get("retentionPct"));
        if (retentionPct == null) {
            retentionPct = BigDecimal.ZERO;
        }
        if (retentionPct.signum() < 0 || retentionPct.compareTo(HUNDRED) > 0) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "Retention must be between 0 and 100 per cent.");
        }

        BigDecimal retention = round(claimed.multiply(retentionPct).divide(HUNDRED, 4, RoundingMode.HALF_UP));

        String id = UUID.randomUUID().toString();
        Map<String, Object> certificate = new LinkedHashMap<>();
        certificate.put("ID", id);
        certificate.put("pa_ID", applicationId);
        certificate.put("scr_ID", application.get("scr_ID"));
        certificate.put("certSeq", existing + 1);
        certificate.put("claimedGross", claimed);
        certificate.put("adjustment", BigDecimal.ZERO);
        certificate.put("certifiedGross", claimed);
        certificate.put("retentionPct", retentionPct);
        certificate.put("retentionAmount", retention);
        certificate.put("ldApplied", BigDecimal.ZERO);
        certificate.put("backChargeTotal", BigDecimal.ZERO);
        certificate.put("netCertified", round(claimed.subtract(retention)));
        certificate.put("status", "Draft");
        certificate.put("raisedBy", userName());
        certificate.put("raisedOn", java.time.LocalDate.now());
        db.run(Insert.into(E_CERTIFICATE).entry(certificate));

        return_(context, String.format(
                "Certificate %d raised for %s claimed, %s retained, %s net. "
                        + "Enter any adjustment, liquidated damages or back charges, "
                        + "then recalculate.",
                existing + 1, claimed.toPlainString(), retention.toPlainString(),
                round(claimed.subtract(retention)).toPlainString()));
    }

    // --------------------------------------------------------- recalculate

    @On(event = "recalculate")
    public void onRecalculate(EventContext context) {
        Row certificate = targetOf(context, "Payment certificate");
        String id = str(certificate.get("ID"));

        BigDecimal claimed = orZero(decimal(certificate.get("claimedGross")));
        BigDecimal adjustment = orZero(decimal(certificate.get("adjustment")));
        BigDecimal retentionPct = orZero(decimal(certificate.get("retentionPct")));
        BigDecimal ld = orZero(decimal(certificate.get("ldApplied")));

        BigDecimal backCharges = BigDecimal.ZERO;
        int backChargeLines = 0;
        for (Row line : db.run(Select.from(E_BACKCHARGE)
                .where(b -> b.get("pc_ID").eq(id)))) {
            backCharges = backCharges.add(orZero(decimal(line.get("amount"))));
            backChargeLines++;
        }
        backCharges = round(backCharges);

        BigDecimal certifiedGross = round(claimed.add(adjustment));
        BigDecimal retention = round(certifiedGross.multiply(retentionPct)
                .divide(HUNDRED, 4, RoundingMode.HALF_UP));
        BigDecimal net = round(certifiedGross.subtract(retention)
                .subtract(ld).subtract(backCharges));

        Map<String, Object> update = new HashMap<>();
        update.put("certifiedGross", certifiedGross);
        update.put("retentionAmount", retention);
        update.put("backChargeTotal", backCharges);
        update.put("netCertified", net);
        db.run(Update.entity(E_CERTIFICATE).data(update).where(c -> c.get("ID").eq(id)));

        String warning = net.signum() < 0
                ? " The deductions exceed the certified gross, so this certificate "
                        + "is negative — it is a debit against the subcontractor, not a payment."
                : "";

        return_(context, String.format(
                "%s claimed %s%s = %s gross. Less %s retention at %s%%, %s "
                        + "liquidated damages and %s back charges over %d line(s): "
                        + "%s net certified.%s",
                str(certificate.get("docNo")) == null ? "Certificate"
                        : str(certificate.get("docNo")),
                claimed.toPlainString(),
                adjustment.signum() == 0 ? ""
                        : (adjustment.signum() > 0 ? " + " : " - ")
                                + adjustment.abs().toPlainString() + " adjustment",
                certifiedGross.toPlainString(), retention.toPlainString(),
                retentionPct.toPlainString(), ld.toPlainString(),
                backCharges.toPlainString(), backChargeLines,
                net.toPlainString(), warning));
    }

    // -------------------------------------------------------------- signOff

    @On(event = "signOff")
    public void onSignOff(EventContext context) {
        Row certificate = targetOf(context, "Payment certificate");
        String id = str(certificate.get("ID"));

        String role = trimmed(context.get("role"));
        String decision = trimmed(context.get("decision"));
        if (isBlank(role) || isBlank(decision)) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "A sign-off needs both a role and a decision.");
        }

        int seq = 0;
        for (Row existing : db.run(Select.from(E_SIGNOFF)
                .where(s -> s.get("pc_ID").eq(id)))) {
            Object number = existing.get("seq");
            seq = Math.max(seq, number instanceof Number n ? n.intValue() : 0);
        }

        Map<String, Object> signOff = new LinkedHashMap<>();
        signOff.put("ID", UUID.randomUUID().toString());
        signOff.put("pc_ID", id);
        signOff.put("seq", seq + 1);
        signOff.put("role", role);
        // The name defaults to whoever is signing rather than being trusted
        // from the payload: a sign-off is a record of who decided.
        String name = trimmed(context.get("name"));
        signOff.put("name", isBlank(name) ? userName() : name);
        signOff.put("decision", decision);
        signOff.put("decidedOn", Instant.now());
        db.run(Insert.into(E_SIGNOFF).entry(signOff));

        // A rejection stops the certificate; an approval only advances it once
        // nobody has rejected, so one refusal is not overwritten by the next
        // approval in the chain.
        String status = "Rejected".equalsIgnoreCase(decision) ? "Rejected" : "Certified";
        if (!"Rejected".equalsIgnoreCase(decision)) {
            for (Row existing : db.run(Select.from(E_SIGNOFF)
                    .where(s -> s.get("pc_ID").eq(id)))) {
                if ("Rejected".equalsIgnoreCase(str(existing.get("decision")))) {
                    status = "Rejected";
                    break;
                }
            }
        }
        Map<String, Object> update = new HashMap<>();
        update.put("status", status);
        db.run(Update.entity(E_CERTIFICATE).data(update).where(c -> c.get("ID").eq(id)));

        return_(context, role + " recorded " + decision + " as step " + (seq + 1)
                + ". The certificate is " + status + ".");
    }

    // ---------------------------------------------------------------- helpers

    /**
     * The document the action was called on. Same idiom the project and
     * budget handlers use: the runtime hands over the select that resolved
     * the bound target.
     */
    private Row targetOf(EventContext context, String label) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        return (select == null ? Optional.<Row>empty() : db.run(select).first())
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        label + " not found."));
    }

    private String userName() {
        String name = userInfo == null ? null : userInfo.getName();
        return isBlank(name) ? "unknown" : name;
    }

    private static void return_(EventContext context, String message) {
        context.put("result", message);
        context.setCompleted();
    }

    /** Money is held to two places; the intermediate division keeps four. */
    private static BigDecimal round(BigDecimal value) {
        return value.setScale(2, RoundingMode.HALF_UP);
    }

    private static BigDecimal orZero(BigDecimal value) {
        return value == null ? BigDecimal.ZERO : value;
    }

    private static BigDecimal decimal(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof BigDecimal d) {
            return d;
        }
        try {
            return new BigDecimal(String.valueOf(value));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static String trimmed(Object value) {
        return value == null ? null : String.valueOf(value).trim();
    }

    private static boolean isBlank(String s) {
        return s == null || s.isBlank();
    }

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }
}
