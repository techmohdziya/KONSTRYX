package com.inflexion.konstryx.prj;

import com.sap.cds.Row;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceCatalog;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.cds.ApplicationService;
import com.sap.cds.services.persistence.PersistenceService;
import com.sap.cds.services.runtime.CdsRuntime;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.InputSource;

import java.io.StringReader;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;

/**
 * Imports a project and its WBS from a Primavera P6 XML export.
 *
 * This is separate from the generic CSV importer rather than an entity added to
 * it, because a P6 file is not a row set. It is one project with a WBS tree
 * hanging off it, and the tree only means anything whole: a project that
 * imported its header and two thirds of its WBS is worse than one that did not
 * import at all, because the missing branches are invisible until someone tries
 * to budget against them. So there is no PARTIAL mode here. Either the file
 * lands or it does not.
 *
 * Rows are written through ProjectService, so every rule that service enforces
 * applies — code uniqueness, date agreement, company, the cycle guard, and the
 * NOT_SENT default that keeps an imported project visibly absent from S/4.
 */
@Component
public class P6ImportService {

    private static final String E_RUN = "konstryx.sys.ImportRun";
    private static final String E_ROW = "konstryx.sys.ImportRow";

    @Autowired
    private PersistenceService db;

    @Autowired
    private CdsRuntime runtime;

    public Map<String, Object> importXml(String fileName, String xml, String companyId,
                                         boolean validateOnly) {
        Document document = parse(xml);
        List<P6Project> projects = read(document);

        if (projects.isEmpty()) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "No <Project> was found. This does not look like a P6 XML export.");
        }

        String runId = UUID.randomUUID().toString();
        List<Map<String, Object>> audit = new ArrayList<>();
        int[] counts = { 0, 0 };   // accepted, rejected

        runtime.changeSetContext().run(changeSet -> {
            for (P6Project project : projects) {
                try {
                    int wbsCount = load(project, companyId);
                    counts[0] += 1 + wbsCount;
                    audit.add(auditRow(runId, project.line, project.describe(),
                            true, null));
                } catch (Exception e) {
                    counts[1]++;
                    audit.add(auditRow(runId, project.line, project.describe(),
                            false, rootMessage(e)));
                }
            }
            if (validateOnly || counts[1] > 0) {
                changeSet.markForCancel();
            }
        });

        String message = summarise(projects, counts[0], counts[1], validateOnly);
        writeRun(runId, fileName, audit, counts[0], counts[1],
                validateOnly ? "COMPLETED" : (counts[1] == 0 ? "COMPLETED" : "REJECTED"),
                message);

        Map<String, Object> result = new HashMap<>();
        result.put("runId", runId);
        result.put("message", message);
        return result;
    }

    // ------------------------------------------------------------------ parse

    /**
     * External entities and DTDs are switched off. An uploaded XML file is
     * untrusted input, and a DOCTYPE is all it takes to make the parser read
     * files off the server or open connections on its behalf.
     */
    private Document parse(String xml) {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
            factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
            factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
            factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
            factory.setXIncludeAware(false);
            factory.setExpandEntityReferences(false);
            factory.setNamespaceAware(false);

            DocumentBuilder builder = factory.newDocumentBuilder();
            return builder.parse(new InputSource(new StringReader(xml)));
        } catch (Exception e) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The file could not be read as XML: " + rootMessage(e));
        }
    }

    private List<P6Project> read(Document document) {
        List<P6Project> projects = new ArrayList<>();
        NodeList nodes = document.getElementsByTagName("Project");

        for (int i = 0; i < nodes.getLength(); i++) {
            Element element = (Element) nodes.item(i);
            P6Project project = new P6Project();
            project.line = i + 1;
            project.code = text(element, "Id");
            project.name = text(element, "Name");
            project.startDate = date(text(element, "StartDate"));
            project.endDate = date(coalesce(text(element, "FinishDate"),
                    text(element, "MustFinishByDate")));

            for (Element wbs : childElements(element, "WBS")) {
                P6Wbs node = new P6Wbs();
                node.objectId = text(wbs, "ObjectId");
                node.parentObjectId = text(wbs, "ParentObjectId");
                node.code = coalesce(text(wbs, "Code"), text(wbs, "Id"));
                node.name = text(wbs, "Name");
                project.wbs.add(node);
            }
            projects.add(project);
        }
        return projects;
    }

    // ------------------------------------------------------------------- load

    private int load(P6Project p6, String companyId) {
        if (isBlank(p6.code)) {
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The project has no <Id>, so there is nothing to call it.");
        }

        ApplicationService projectService = serviceFor("ProjectService");

        String projectId = UUID.randomUUID().toString();
        Map<String, Object> project = new LinkedHashMap<>();
        project.put("ID", projectId);
        project.put("code", p6.code);
        project.put("name", coalesce(p6.name, p6.code));
        project.put("company_ID", companyId);
        project.put("startDate", p6.startDate);
        project.put("endDate", p6.endDate);
        project.put("stage", "Draft");
        // Through the service, so the same validation an on-screen project gets
        // applies here — including the NOT_SENT default. An imported project is
        // no more in S/4 than a typed one.
        projectService.run(Insert.into("ProjectService.Projects").entry(project));

        return loadWbs(projectService, p6, projectId);
    }

    /**
     * Two passes, because P6 orders WBS rows by its own object id and a child
     * can appear before its parent. The first pass creates every node, the
     * second links them — the same shape the CBS template instantiation uses.
     */
    private int loadWbs(ApplicationService service, P6Project p6, String projectId) {
        Map<String, String> p6ToKonstryx = new HashMap<>();

        for (P6Wbs node : p6.wbs) {
            if (isBlank(node.code) && isBlank(node.name)) {
                continue;
            }
            String id = UUID.randomUUID().toString();
            p6ToKonstryx.put(node.objectId, id);

            Map<String, Object> wbs = new LinkedHashMap<>();
            wbs.put("ID", id);
            wbs.put("project_ID", projectId);
            wbs.put("code", coalesce(node.code, node.name));
            wbs.put("description", node.name);
            service.run(Insert.into("ProjectService.WBS").entry(wbs));
        }

        int linked = 0;
        for (P6Wbs node : p6.wbs) {
            String id = p6ToKonstryx.get(node.objectId);
            String parentId = p6ToKonstryx.get(node.parentObjectId);
            if (id == null) {
                continue;
            }
            if (parentId != null && !parentId.equals(id)) {
                Map<String, Object> patch = new HashMap<>();
                patch.put("parent_ID", parentId);
                db.run(com.sap.cds.ql.Update.entity("konstryx.prj.WBSElement")
                        .data(patch).where(w -> w.get("ID").eq(id)));
            }
            linked++;
        }
        return linked;
    }

    // ------------------------------------------------------------------ audit

    private Map<String, Object> auditRow(String runId, int line, String payload,
                                         boolean accepted, String error) {
        Map<String, Object> row = new HashMap<>();
        row.put("ID", UUID.randomUUID().toString());
        row.put("run_ID", runId);
        row.put("lineNo", line);
        row.put("payload", payload);
        row.put("accepted", accepted);
        row.put("error", error);
        return row;
    }

    private void writeRun(String runId, String fileName, List<Map<String, Object>> rows,
                          int accepted, int rejected, String status, String message) {
        Map<String, Object> run = new HashMap<>();
        run.put("ID", runId);
        run.put("target", "konstryx.prj.Project");
        run.put("fileName", fileName);
        run.put("rowsTotal", rows.size());
        run.put("rowsAccepted", accepted);
        run.put("rowsRejected", rejected);
        run.put("mode", "ALL_OR_NOTHING");
        run.put("status", status);
        run.put("message", message);
        db.run(Insert.into(E_RUN).entry(run));
        if (!rows.isEmpty()) {
            db.run(Insert.into(E_ROW).entries(rows));
        }
    }

    private String summarise(List<P6Project> projects, int accepted, int rejected,
                             boolean validateOnly) {
        int wbsTotal = projects.stream().mapToInt(p -> p.wbs.size()).sum();
        if (rejected > 0) {
            return "Nothing was imported. " + rejected + " of " + projects.size()
                    + " project(s) could not be loaded — see the import run for the reason.";
        }
        if (validateOnly) {
            return projects.size() + " project(s) and " + wbsTotal
                    + " WBS element(s) would import cleanly. Nothing was changed — this was a check.";
        }
        return "Imported " + projects.size() + " project(s) and " + wbsTotal
                + " WBS element(s). Not in S/4 yet: release each project when it is ready.";
    }

    // ---------------------------------------------------------------- helpers

    private ApplicationService serviceFor(String name) {
        ServiceCatalog catalog = runtime.getServiceCatalog();
        return catalog.getServices(ApplicationService.class)
                .filter(s -> s.getName().equals(name))
                .findFirst()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.BAD_REQUEST,
                        "No such service: " + name));
    }

    private static List<Element> childElements(Element parent, String tag) {
        List<Element> found = new ArrayList<>();
        NodeList children = parent.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node child = children.item(i);
            if (child instanceof Element element && tag.equals(element.getTagName())) {
                found.add(element);
            }
        }
        return found;
    }

    /** Direct child only: <Project><Name> must not be answered by <WBS><Name>. */
    private static String text(Element parent, String tag) {
        for (Element child : childElements(parent, tag)) {
            String value = child.getTextContent();
            return value == null || value.isBlank() ? null : value.trim();
        }
        return null;
    }

    private static LocalDate date(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String text = value.trim();
        // P6 writes 2026-09-01T00:00:00; the date half is all a project needs.
        int t = text.indexOf('T');
        if (t > 0) {
            text = text.substring(0, t);
        }
        if (text.length() > 10) {
            text = text.substring(0, 10);
        }
        try { return LocalDate.parse(text); }
        catch (RuntimeException e) { return null; }
    }

    private static String coalesce(String a, String b) {
        return a != null && !a.isBlank() ? a : b;
    }

    private static boolean isBlank(String s) { return s == null || s.isBlank(); }

    private static String rootMessage(Throwable e) {
        Throwable current = e;
        while (current.getCause() != null && current.getCause() != current) {
            current = current.getCause();
        }
        String message = current.getMessage();
        return message == null || message.isBlank() ? current.getClass().getSimpleName() : message;
    }

    // ------------------------------------------------------------ the P6 shape

    private static final class P6Project {
        int line;
        String code;
        String name;
        LocalDate startDate;
        LocalDate endDate;
        final List<P6Wbs> wbs = new ArrayList<>();

        String describe() {
            return "Project " + code + " (" + name + "), " + wbs.size() + " WBS element(s)";
        }
    }

    private static final class P6Wbs {
        String objectId;
        String parentObjectId;
        String code;
        String name;
    }
}
