"""
Graph utilities: topological sort and execution layer builder.

Key design decisions:
  1. We use Kahn's algorithm (BFS-based) for topological sort — it naturally
     produces execution *layers* where all nodes in a layer have no 
     dependency on each other (enabling asyncio.gather for parallel execution).

  2. Cycle detection is built into Kahn's: if not all nodes are processed,
     there's a cycle in the graph.

  3. Conditional edges are NOT resolved here — the graph module only cares
     about the static topology. Condition evaluation happens in the runner
     at execution time (after the source node completes).

  4. In Phase 3, loops are handled by the runner re-queuing nodes; the
     static graph remains a DAG from the graph module's perspective.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from agentflow.core.schemas.workflow import EdgeDef, WorkflowDef


class CycleDetectedError(ValueError):
    """Raised if the workflow graph contains a cycle."""


@dataclass
class ExecutionGraph:
    """
    Processed representation of a WorkflowDef graph.

    Attributes:
        layers: List of execution layers. Layer 0 = trigger/root nodes.
                All nodes in the same layer can execute in parallel.
        adjacency: node_id → list of downstream node_ids (forward edges)
        in_degree: node_id → number of unresolved predecessors (forward edges)
        node_ids: all node IDs in the workflow
        feedback_edges: list of back-edges for loop execution
    """
    layers: list[list[str]] = field(default_factory=list)
    adjacency: dict[str, list[str]] = field(default_factory=dict)
    in_degree: dict[str, int] = field(default_factory=dict)
    node_ids: list[str] = field(default_factory=list)
    feedback_edges: list[EdgeDef] = field(default_factory=list)

    def successors(self, node_id: str) -> list[str]:
        return self.adjacency.get(node_id, [])

    def get_feedback_edges(self, node_id: str) -> list[EdgeDef]:
        """Return all outgoing feedback edges from the given node."""
        return [e for e in self.feedback_edges if e.source == node_id]


def build_execution_graph(workflow: WorkflowDef) -> ExecutionGraph:
    """
    Build an ExecutionGraph from a WorkflowDef.

    Algorithm: Kahn's topological sort (BFS)
      1. Partition edges into forward edges and feedback edges (is_feedback=True)
      2. Build adjacency list and in-degree map from forward edges
      3. Enqueue all nodes with in-degree 0 (layer 0)
      4. For each layer: record it, decrement in-degrees of successors,
         enqueue any that hit 0 (next layer)
      5. If total processed < total nodes → unintended cycle in forward edges

    Returns:
        ExecutionGraph with layers in topological order and feedback_edges recorded.

    Raises:
        CycleDetectedError: if forward edges contain an unexpected cycle.
        ValueError: if there are no nodes.
    """
    nodes = workflow.nodes
    edges = workflow.edges

    if not nodes:
        raise ValueError("Workflow has no nodes.")

    node_ids = [n.id for n in nodes]
    forward_edges = [e for e in edges if not getattr(e, "is_feedback", False)]
    feedback_edges = [e for e in edges if getattr(e, "is_feedback", False)]

    adjacency: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

    for edge in forward_edges:
        adjacency[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    # Kahn's BFS — groups nodes into layers
    queue: deque[str] = deque(nid for nid in node_ids if in_degree[nid] == 0)
    layers: list[list[str]] = []
    processed = 0

    while queue:
        layer_size = len(queue)
        current_layer: list[str] = []

        for _ in range(layer_size):
            node_id = queue.popleft()
            current_layer.append(node_id)
            processed += 1

            for successor in adjacency[node_id]:
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        layers.append(current_layer)

    if processed != len(node_ids):
        unprocessed = [nid for nid in node_ids if in_degree.get(nid, 0) > 0]
        raise CycleDetectedError(
            f"Workflow graph contains an unresolved cycle among forward edges. "
            f"Unresolved nodes: {unprocessed}. "
            "Set `is_feedback=True` on back-edges to declare intentional feedback loops."
        )

    return ExecutionGraph(
        layers=layers,
        adjacency=dict(adjacency),
        in_degree={nid: 0 for nid in node_ids},  # reset after processing
        node_ids=node_ids,
        feedback_edges=feedback_edges,
    )
