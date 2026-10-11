---
name: plan
description: View or edit a Mentor course's knowledge graph - add a capability, mark something as already known, split or merge nodes, add a missing prerequisite.
argument-hint: "[course] [what to change]"
allowed-tools: mcp__plugin_mentor_core, Read, Write, Agent
---

# /mentor:plan: the course map

1. `course_status` → `dir`. `graph_get(course)` for the frontier and capabilities, and
   `graph_get(course, view="mermaid")` for the map.
2. With no change requested, show the capabilities, the frontier, and the map, and ask what to adjust.
3. To change it:
   - read `<dir>/graph.yaml`, edit the YAML (same schema; see the `curriculum-architect` agent
     for field meanings), then `graph_propose(course, yaml)`. Fix any errors and resubmit;
   - one new prerequisite: `graph_insert_node(course, node_yaml, edges_yaml)`;
   - big restructures (a new capability, a changed goal): spawn `curriculum-architect` with
     the change request, then `graph-critic`, then propose;
   - "I already know X": run 2-3 quick check questions on X (`evidence_record kind=check`)
     instead of trusting the claim blindly; if they pass, the engine will count it.
4. Evidence is never deleted: removed nodes keep their history. Summarize what changed.
