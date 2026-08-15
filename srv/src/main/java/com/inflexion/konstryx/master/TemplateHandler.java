package com.inflexion.konstryx.master;

import com.sap.cds.Row;
import com.sap.cds.ql.Insert;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.cqn.CqnSelect;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.EventContext;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.handler.EventHandler;
import com.sap.cds.services.handler.annotations.On;
import com.sap.cds.services.handler.annotations.ServiceName;
import com.sap.cds.services.persistence.PersistenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * Instantiates a project template.
 *
 * The template's CBS structure is copied into the project rather than
 * referenced. A project being costed must not reshape itself because someone
 * edited the library afterwards, and the copy is what a project CBS is for:
 * the library says what a high-rise usually looks like, the project instance
 * says what this one actually is.
 *
 * Default resources are copied the same way, giving the project a planned
 * resource list before any request is raised.
 */
@Component
@ServiceName("MasterDataService")
public class TemplateHandler implements EventHandler {

    private static final String E_TEMPLATE = "konstryx.master.ProjectTemplate";
    private static final String E_TEMPLATE_RES = "konstryx.master.ProjectTemplateResource";
    private static final String E_CBS_NODE = "konstryx.master.CBSNode";
    private static final String E_CBS_INSTANCE = "konstryx.prj.CBSInstance";
    private static final String E_PROJECT = "konstryx.prj.Project";
    private static final String E_PROJECT_RES = "konstryx.prj.ProjectResource";

    @Autowired
    private PersistenceService db;

    @On(event = "instantiate")
    public void onInstantiate(EventContext context) {
        Row template = loadTemplate(context);
        String projectCode = String.valueOf(context.get("projectCode"));

        Row project = db.run(Select.from(E_PROJECT)
                .where(p -> p.get("code").eq(projectCode)))
                .first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "No project with code " + projectCode + "."));

        String projectId = String.valueOf(project.get("ID"));
        String constructionType = String.valueOf(template.get("constructionType"));

        // Refuse rather than silently duplicating. Instantiating twice would give
        // the project two of every CBS node and no way to tell them apart.
        boolean alreadyHasCbs = db.run(Select.from(E_CBS_INSTANCE)
                .where(c -> c.get("project_ID").eq(projectId)))
                .first().isPresent();
        if (alreadyHasCbs) {
            throw new ServiceException(ErrorStatuses.CONFLICT,
                    projectCode + " already has a cost breakdown structure. Instantiating a"
                            + " template again would duplicate it.");
        }

        int cbsCopied = copyCbs(constructionType, projectId);
        int resourcesCopied = copyResources(String.valueOf(template.get("ID")), projectId);

        context.put("result", String.format(
                "%s instantiated into %s: %d CBS nodes and %d planned resources.",
                template.get("code"), projectCode, cbsCopied, resourcesCopied));
        context.setCompleted();
    }

    /**
     * Copies every library node of this construction type, in two passes so a
     * child can point at the instance its parent became rather than at the
     * library node it came from.
     */
    private int copyCbs(String constructionType, String projectId) {
        Map<String, String> libraryToInstance = new HashMap<>();
        java.util.List<Row> nodes = new java.util.ArrayList<>();

        for (Row node : db.run(Select.from(E_CBS_NODE)
                .where(n -> n.get("constructionType").eq(constructionType)))) {
            nodes.add(node);
            libraryToInstance.put(String.valueOf(node.get("ID")), UUID.randomUUID().toString());
        }

        for (Row node : nodes) {
            String libraryId = String.valueOf(node.get("ID"));
            Object parentLibraryId = node.get("parent_ID");

            Map<String, Object> instance = new HashMap<>();
            instance.put("ID", libraryToInstance.get(libraryId));
            instance.put("code", node.get("code"));
            instance.put("level", node.get("level"));
            instance.put("project_ID", projectId);
            instance.put("libraryNode_ID", libraryId);
            instance.put("parent_ID", parentLibraryId == null
                    ? null
                    : libraryToInstance.get(String.valueOf(parentLibraryId)));
            db.run(Insert.into(E_CBS_INSTANCE).entry(instance));
        }
        return nodes.size();
    }

    private int copyResources(String templateId, String projectId) {
        int count = 0;
        for (Row link : db.run(Select.from(E_TEMPLATE_RES)
                .where(r -> r.get("template_ID").eq(templateId)))) {
            Map<String, Object> planned = new HashMap<>();
            planned.put("ID", UUID.randomUUID().toString());
            planned.put("project_ID", projectId);
            planned.put("resource_ID", link.get("resource_ID"));
            planned.put("buildUp", "From template");
            db.run(Insert.into(E_PROJECT_RES).entry(planned));
            count++;
        }
        return count;
    }

    private Row loadTemplate(EventContext context) {
        CqnSelect select = context.get("cqn") instanceof CqnSelect s ? s : null;
        Optional<Row> row = (select != null) ? db.run(select).first() : Optional.empty();
        return row.orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                "Template not found."));
    }
}
