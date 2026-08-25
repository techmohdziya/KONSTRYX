package com.inflexion.konstryx.prj;

import com.sap.cds.Row;
import com.sap.cds.ql.Select;
import com.sap.cds.ql.Update;
import com.sap.cds.services.ErrorStatuses;
import com.sap.cds.services.ServiceException;
import com.sap.cds.services.persistence.PersistenceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Critical path scheduling for a project's activities.
 *
 * A standard two-pass calculation. The forward pass walks the network in
 * dependency order and gives every activity the earliest it can start and
 * finish; the backward pass walks it in reverse and gives the latest it can
 * start and finish without moving the project's completion. Total float is the
 * gap between the two, and an activity with none of it is on the critical
 * path — it cannot slip by a day without the project slipping with it.
 *
 * All four relationship types are honoured. Assuming finish-to-start would be
 * wrong on any real site programme, where trades overlap start-to-start with a
 * lag, and it would push every downstream date out.
 *
 * Durations are in whole days and the calendar is continuous. A working-time
 * calendar with weekends and holidays is a separate concern and would sit
 * between the date arithmetic here and the dates that come out of it.
 */
@Component
public class ScheduleService {

    private static final String E_ACTIVITY = "konstryx.prj.Activity";
    private static final String E_RELATION = "konstryx.prj.ActivityRelation";
    private static final String E_PROJECT = "konstryx.prj.Project";

    @Autowired
    private PersistenceService db;

    /** One activity while it is being scheduled. */
    private static final class Node {
        final String id;
        final String code;
        final int duration;
        LocalDate earlyStart, earlyFinish, lateStart, lateFinish;
        Integer totalFloat, freeFloat;
        final List<Link> incoming = new ArrayList<>();
        final List<Link> outgoing = new ArrayList<>();

        Node(String id, String code, int duration) {
            this.id = id;
            this.code = code;
            this.duration = Math.max(duration, 0);
        }
    }

    private static final class Link {
        final Node from, to;
        final String type;
        final int lag;

        Link(Node from, Node to, String type, int lag) {
            this.from = from;
            this.to = to;
            this.type = type == null || type.isBlank() ? "FS" : type.toUpperCase();
            this.lag = lag;
        }
    }

    /**
     * Schedules one project and writes the derived dates back. Returns a
     * summary meant to be read: how long the programme runs, and which
     * activities drive it.
     */
    public String schedule(String projectId) {
        Row project = db.run(Select.from(E_PROJECT)
                .where(p -> p.get("ID").eq(projectId))).first()
                .orElseThrow(() -> new ServiceException(ErrorStatuses.NOT_FOUND,
                        "No such project."));

        Map<String, Node> nodes = loadNodes(projectId);
        if (nodes.isEmpty()) {
            return "This project has no activities, so there is nothing to schedule. "
                    + "Add activities under its WBS elements first.";
        }
        loadLinks(nodes);

        List<Node> order = topological(nodes);
        LocalDate start = startOf(project);

        forwardPass(order, start);
        LocalDate finish = latestFinish(order);
        backwardPass(order, finish);
        freeFloat(order);

        int critical = 0;
        for (Node node : order) {
            if (node.totalFloat != null && node.totalFloat <= 0) {
                critical++;
            }
        }
        write(order);

        return String.format(
                "%d activities scheduled from %s to %s (%d days). "
                        + "%d on the critical path.",
                order.size(), start, finish,
                java.time.temporal.ChronoUnit.DAYS.between(start, finish),
                critical);
    }

    // ------------------------------------------------------------------ load

    private Map<String, Node> loadNodes(String projectId) {
        Map<String, Node> nodes = new LinkedHashMap<>();
        for (Row row : db.run(Select.from(E_ACTIVITY)
                .where(a -> a.get("project_ID").eq(projectId)))) {
            String id = String.valueOf(row.get("ID"));
            Object duration = row.get("durationDays");
            nodes.put(id, new Node(id, str(row.get("code")),
                    duration instanceof Number n ? n.intValue() : 0));
        }
        return nodes;
    }

    private void loadLinks(Map<String, Node> nodes) {
        for (Row row : db.run(Select.from(E_RELATION))) {
            Node from = nodes.get(str(row.get("predecessor_ID")));
            Node to = nodes.get(str(row.get("successor_ID")));
            if (from == null || to == null) {
                // A relationship pointing outside this project is not this
                // project's to schedule.
                continue;
            }
            Object lag = row.get("lagDays");
            Link link = new Link(from, to, str(row.get("linkType")),
                    lag instanceof Number n ? n.intValue() : 0);
            from.outgoing.add(link);
            to.incoming.add(link);
        }
    }

    /** The project's own start, or today when it has none. */
    private static LocalDate startOf(Row project) {
        Object start = project.get("startDate");
        if (start instanceof LocalDate date) {
            return date;
        }
        if (start != null) {
            try {
                return LocalDate.parse(String.valueOf(start).substring(0, 10));
            } catch (RuntimeException ignored) {
                // fall through
            }
        }
        return LocalDate.now();
    }

    // ------------------------------------------------------------- the passes

    /**
     * Dependency order, by Kahn's algorithm. A cycle is refused rather than
     * scheduled around: two activities each waiting for the other is a network
     * error, and quietly picking one to go first would hide it behind dates
     * that look reasonable.
     */
    private List<Node> topological(Map<String, Node> nodes) {
        Map<String, Integer> remaining = new HashMap<>();
        Deque<Node> ready = new ArrayDeque<>();
        for (Node node : nodes.values()) {
            remaining.put(node.id, node.incoming.size());
            if (node.incoming.isEmpty()) {
                ready.add(node);
            }
        }
        List<Node> order = new ArrayList<>();
        while (!ready.isEmpty()) {
            Node node = ready.poll();
            order.add(node);
            for (Link link : node.outgoing) {
                int left = remaining.merge(link.to.id, -1, Integer::sum);
                if (left == 0) {
                    ready.add(link.to);
                }
            }
        }
        if (order.size() != nodes.size()) {
            List<String> stuck = new ArrayList<>();
            for (Node node : nodes.values()) {
                if (remaining.getOrDefault(node.id, 0) > 0 && stuck.size() < 8) {
                    stuck.add(node.code);
                }
            }
            throw new ServiceException(ErrorStatuses.BAD_REQUEST,
                    "The activity network contains a loop, so it cannot be "
                            + "scheduled. Involved: " + String.join(", ", stuck));
        }
        return order;
    }

    private void forwardPass(List<Node> order, LocalDate projectStart) {
        for (Node node : order) {
            LocalDate earliest = projectStart;
            for (Link link : node.incoming) {
                LocalDate candidate = drivenStart(link);
                if (candidate != null && candidate.isAfter(earliest)) {
                    earliest = candidate;
                }
            }
            node.earlyStart = earliest;
            node.earlyFinish = finishOf(earliest, node.duration);
        }
    }

    /** The earliest this link allows its successor to start. */
    private static LocalDate drivenStart(Link link) {
        Node from = link.from;
        if (from.earlyFinish == null || from.earlyStart == null) {
            return null;
        }
        switch (link.type) {
            case "SS":
                return from.earlyStart.plusDays(link.lag);
            case "FF":
                // Constrains the finish; convert back to a start.
                return from.earlyFinish.plusDays(link.lag)
                        .minusDays(Math.max(link.to.duration - 1, 0));
            case "SF":
                return from.earlyStart.plusDays(link.lag)
                        .minusDays(Math.max(link.to.duration - 1, 0));
            case "FS":
            default:
                return from.earlyFinish.plusDays(1L + link.lag);
        }
    }

    private static LocalDate latestFinish(List<Node> order) {
        LocalDate finish = null;
        for (Node node : order) {
            if (node.earlyFinish != null
                    && (finish == null || node.earlyFinish.isAfter(finish))) {
                finish = node.earlyFinish;
            }
        }
        return finish;
    }

    private void backwardPass(List<Node> order, LocalDate projectFinish) {
        for (int i = order.size() - 1; i >= 0; i--) {
            Node node = order.get(i);
            LocalDate latest = projectFinish;
            for (Link link : node.outgoing) {
                LocalDate candidate = drivenFinish(link);
                if (candidate != null && candidate.isBefore(latest)) {
                    latest = candidate;
                }
            }
            node.lateFinish = latest;
            node.lateStart = startOf(latest, node.duration);
            node.totalFloat = (int) java.time.temporal.ChronoUnit.DAYS
                    .between(node.earlyFinish, node.lateFinish);
        }
    }

    /** The latest this link allows its predecessor to finish. */
    private static LocalDate drivenFinish(Link link) {
        Node to = link.to;
        if (to.lateStart == null || to.lateFinish == null) {
            return null;
        }
        switch (link.type) {
            case "SS":
                return finishOf(to.lateStart.minusDays(link.lag), link.from.duration);
            case "FF":
                return to.lateFinish.minusDays(link.lag);
            case "SF":
                return finishOf(to.lateFinish.minusDays(link.lag), link.from.duration);
            case "FS":
            default:
                return to.lateStart.minusDays(1L + link.lag);
        }
    }

    /**
     * How long an activity can slip without moving any successor, as opposed
     * to without moving the project. The two differ wherever a chain has slack
     * that a later activity absorbs.
     */
    private void freeFloat(List<Node> order) {
        for (Node node : order) {
            if (node.outgoing.isEmpty()) {
                node.freeFloat = node.totalFloat;
                continue;
            }
            Integer smallest = null;
            for (Link link : node.outgoing) {
                if (link.to.earlyStart == null || node.earlyFinish == null) {
                    continue;
                }
                int slack = (int) java.time.temporal.ChronoUnit.DAYS
                        .between(node.earlyFinish.plusDays(1), link.to.earlyStart)
                        - link.lag;
                if (smallest == null || slack < smallest) {
                    smallest = slack;
                }
            }
            node.freeFloat = smallest == null ? node.totalFloat : Math.max(smallest, 0);
        }
    }

    // ----------------------------------------------------------------- output

    private void write(List<Node> order) {
        for (Node node : order) {
            Map<String, Object> data = new HashMap<>();
            data.put("earlyStart", node.earlyStart);
            data.put("earlyFinish", node.earlyFinish);
            data.put("lateStart", node.lateStart);
            data.put("lateFinish", node.lateFinish);
            data.put("totalFloat", node.totalFloat);
            data.put("freeFloat", node.freeFloat);
            data.put("isCritical", node.totalFloat != null && node.totalFloat <= 0);
            db.run(Update.entity(E_ACTIVITY).data(data)
                    .where(a -> a.get("ID").eq(node.id)));
        }
    }

    /**
     * A one-day activity starts and finishes on the same day, so the finish is
     * the start plus duration minus one. A zero-duration milestone lands on
     * its start date.
     */
    private static LocalDate finishOf(LocalDate start, int duration) {
        return start.plusDays(Math.max(duration - 1, 0));
    }

    private static LocalDate startOf(LocalDate finish, int duration) {
        return finish.minusDays(Math.max(duration - 1, 0));
    }

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }
}
