package com.inflexion.konstryx.io;

import com.sap.cds.CdsData;
import com.sap.cds.Result;
import com.sap.cds.Row;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.reflect.CdsElement;
import com.sap.cds.reflect.CdsEntity;
import com.sap.cds.services.ServiceCatalog;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.cds.ApplicationService;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.request.UserInfo;
import com.sap.cds.services.runtime.CdsRuntime;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Generic CSV import and export.
 *
 * Built once rather than per screen. Forty modules with bespoke importers means
 * forty different behaviours when a row is wrong, and the one thing a user
 * needs from an upload is a consistent, readable answer to "which line, and
 * why".
 *
 * Rows are written through the application service, not straight to the
 * database, so every rule the service already enforces applies to an upload
 * too: hierarchy integrity, code uniqueness within scope, rate effective
 * dating, authorization and master scope. Validation is never reimplemented
 * here, which is what keeps an upload from becoming the back door that lets
 * bad data in.
 */
@Component
public class ImportExportService {

    private static final String E_RUN = "konstryx.sys.ImportRun";
    private static final String E_ROW = "konstryx.sys.ImportRow";

    private static final char DELIMITER = ';';

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    // ------------------------------------------------------------------ export

    /**
     * Current rows as CSV. Doubles as the upload template: download, edit,
     * upload - so the column set a user sees is by definition the one the
     * importer accepts.
     */
    public String export(String target, boolean templateOnly) {
        ApplicationService service = serviceFor(target);
        CdsEntity entity = entityFor(service, target);
        List<String> columns = writableColumns(entity);

        StringBuilder csv = new StringBuilder(String.join(String.valueOf(DELIMITER), columns));

        if (!templateOnly) {
            Result rows = service.run(Select.from(entitySetOf(target)));
            for (Row row : rows) {
                csv.append('\n').append(columns.stream()
                        .map(c -> escape(row.get(c)))
                        .collect(Collectors.joining(String.valueOf(DELIMITER))));
            }
        }
        return csv.toString();
    }

    // ------------------------------------------------------------------ import

    public Map<String, Object> importCsv(String target, String fileName, String content, String mode) {
        ApplicationService service = serviceFor(target);
        CdsEntity entity = entityFor(service, target);
        String entitySet = entitySetOf(target);

        List<String> lines = content.lines()
                .filter(l -> !l.isBlank())
                .collect(Collectors.toList());

        if (lines.size() < 2) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The file has a header but no rows.");
        }

        List<String> header = split(lines.get(0));
        rejectUnknownColumns(entity, header);

        String runId = UUID.randomUUID().toString();
        List<Map<String, Object>> staged = new ArrayList<>();
        int[] counts = { 0, 0 };   // accepted, rejected
        String effectiveMode = mode == null ? "ALL_OR_NOTHING" : mode;

        // The inserts run in their own change set so they can be abandoned
        // without taking the audit trail with them. A rejected import whose
        // error report also vanished would leave the user with nothing to fix.
        runtime.changeSetContext().run(changeSet -> {
            for (int i = 1; i < lines.size(); i++) {
                String line = lines.get(i);
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("ID", UUID.randomUUID().toString());
                row.put("run_ID", runId);
                row.put("lineNo", i);        // 1-based, matching what the user sees
                row.put("payload", line);

                try {
                    Map<String, Object> entry = toEntry(entity, header, split(line));
                    // Through the application service: every handler fires.
                    service.run(Insert.into(entitySet).entry(entry));
                    row.put("accepted", true);
                    counts[0]++;
                } catch (Exception e) {
                    row.put("accepted", false);
                    row.put("error", rootMessage(e));
                    counts[1]++;
                }
                staged.add(row);
            }

            boolean keep = switch (effectiveMode) {
                case "PARTIAL" -> true;
                case "VALIDATE_ONLY" -> false;
                default -> counts[1] == 0;
            };

            if (!keep) {
                // Nothing half-loaded. A partially imported CBS or rate set is
                // harder to recover from than an import that never happened.
                changeSet.markForCancel();
            }
        });

        int accepted = counts[0];
        int rejected = counts[1];
        boolean kept = "PARTIAL".equals(effectiveMode)
                || ("ALL_OR_NOTHING".equals(effectiveMode) && rejected == 0);

        String status = "VALIDATE_ONLY".equals(effectiveMode) ? "COMPLETED"
                : kept ? "COMPLETED" : "REJECTED";

        writeRun(runId, target, fileName, effectiveMode, staged, accepted, rejected,
                status, summary(accepted, rejected, effectiveMode));

        Map<String, Object> result = new HashMap<>();
        result.put("runId", runId);
        result.put("accepted", accepted);
        result.put("rejected", rejected);
        result.put("kept", kept);
        result.put("message", summary(accepted, rejected, effectiveMode));
        return result;
    }

    private static String summaryOf(int accepted, int rejected, String mode) {
        if ("VALIDATE_ONLY".equals(mode)) {
            return rejected == 0
                    ? "All " + accepted + " rows are valid. Nothing was imported - this was a check."
                    : rejected + " of " + (accepted + rejected) + " rows would fail.";
        }
        if ("PARTIAL".equals(mode)) {
            return accepted + " of " + (accepted + rejected) + " rows imported; "
                    + rejected + " rejected.";
        }
        return rejected == 0
                ? "All " + accepted + " rows imported."
                : "Nothing was imported. " + rejected + " of " + (accepted + rejected)
                  + " rows are invalid - correct them and upload again.";
    }
    private void writeRun(String runId, String target, String fileName, String mode,
                          List<Map<String, Object>> rows, int accepted, int rejected,
                          String status, String message) {
        Map<String, Object> run = new HashMap<>();
        run.put("ID", runId);
        run.put("target", target);
        run.put("fileName", fileName);
        run.put("rowsTotal", accepted + rejected);
        run.put("rowsAccepted", accepted);
        run.put("rowsRejected", rejected);
        run.put("mode", mode == null ? "ALL_OR_NOTHING" : mode);
        run.put("status", status);
        run.put("message", message);
        db.run(Insert.into(E_RUN).entry(run));
        if (!rows.isEmpty()) {
            db.run(Insert.into(E_ROW).entries(rows));
        }
    }

    private static String summary(int accepted, int rejected, String mode) {
        return summaryOf(accepted, rejected, mode);
    }

    // ----------------------------------------------------------------- helpers

    private ApplicationService serviceFor(String target) {
        String serviceName = target.contains(".") ? target.substring(0, target.indexOf('.')) : target;
        ServiceCatalog catalog = runtime.getServiceCatalog();
        return catalog.getServices(ApplicationService.class)
                .filter(s -> s.getName().equals(serviceName))
                .findFirst()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "No such service: " + serviceName));
    }

    private String entitySetOf(String target) {
        return target;
    }

    private CdsEntity entityFor(ApplicationService service, String target) {
        return runtime.getCdsModel().findEntity(target)
                .orElseThrow(() -> new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "No such entity: " + target));
    }

    /**
     * Columns a person can reasonably fill in: plain fields plus foreign keys,
     * minus anything the system owns. Offering createdAt in a template invites
     * someone to set it.
     */
    private List<String> writableColumns(CdsEntity entity) {
        List<String> skip = List.of("createdAt", "createdBy", "modifiedAt", "modifiedBy",
                "IsActiveEntity", "HasActiveEntity", "HasDraftEntity",
                "DraftAdministrativeData_DraftUUID", "DraftMessages");
        return entity.elements()
                .filter(e -> !e.getType().isAssociation())
                .map(CdsElement::getName)
                .filter(n -> !skip.contains(n))
                .collect(Collectors.toList());
    }

    private void rejectUnknownColumns(CdsEntity entity, List<String> header) {
        List<String> known = entity.elements().map(CdsElement::getName).collect(Collectors.toList());
        List<String> unknown = header.stream().filter(h -> !known.contains(h)).collect(Collectors.toList());
        if (!unknown.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The file has columns this entity does not have: " + String.join(", ", unknown)
                            + ". Download the template to see the accepted columns.");
        }
    }

    private Map<String, Object> toEntry(CdsEntity entity, List<String> header, List<String> values) {
        Map<String, Object> entry = new LinkedHashMap<>();
        if (!entity.findElement("ID").isEmpty()) {
            entry.put("ID", UUID.randomUUID().toString());
        }
        for (int i = 0; i < header.size() && i < values.size(); i++) {
            String column = header.get(i);
            String value = values.get(i);
            if ("ID".equals(column) && (value == null || value.isBlank())) {
                continue;   // let the generated key stand
            }
            entry.put(column, value == null || value.isBlank() ? null : coerce(entity, column, value));
        }
        return entry;
    }

    private Object coerce(CdsEntity entity, String column, String value) {
        return entity.findElement(column)
                .map(e -> {
                    String type = e.getType().getQualifiedName();
                    try {
                        return switch (type) {
                            case "cds.Boolean" -> Boolean.valueOf(value);
                            case "cds.Integer", "cds.Int32" -> Integer.valueOf(value.trim());
                            case "cds.Integer64", "cds.Int64" -> Long.valueOf(value.trim());
                            case "cds.Decimal", "cds.Double" -> new java.math.BigDecimal(value.trim());
                            // Keys are stored lower-case and compared exactly, while
                            // SAP GUIDs are conventionally written upper-case. Without
                            // this, pasting a perfectly correct key into a template
                            // fails with "the parent does not exist".
                            case "cds.UUID" -> value.trim().toLowerCase();
                            default -> value;
                        };
                    } catch (NumberFormatException nfe) {
                        throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                                "'" + value + "' is not a valid " + type.replace("cds.", "")
                                        + " for column " + column + ".");
                    }
                })
                .orElse(value);
    }

    private static List<String> split(String line) {
        List<String> out = new ArrayList<>();
        StringBuilder field = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') {
                if (quoted && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    field.append('"');
                    i++;
                } else {
                    quoted = !quoted;
                }
            } else if (c == DELIMITER && !quoted) {
                out.add(field.toString().trim());
                field.setLength(0);
            } else {
                field.append(c);
            }
        }
        out.add(field.toString().trim());
        return out;
    }

    private static String escape(Object value) {
        if (value == null) {
            return "";
        }
        String s = String.valueOf(value);
        if (s.indexOf(DELIMITER) >= 0 || s.indexOf('"') >= 0 || s.indexOf('\n') >= 0) {
            return '"' + s.replace("\"", "\"\"") + '"';
        }
        return s;
    }

    /** The message a user should see, not the wrapper chain around it. */
    private static String rootMessage(Throwable e) {
        Throwable current = e;
        while (current.getCause() != null && current.getCause() != current) {
            current = current.getCause();
        }
        String message = current.getMessage();
        return message == null || message.isBlank() ? current.getClass().getSimpleName() : message;
    }
}

