/**
 * dagreLayout.js — Intelligent topological DAG layout engine using @dagrejs/dagre.
 *
 * Automatically balances parallel branches vertically with consistent horizontal rank
 * separation (rankdir: 'LR') and prevents overlapping node cards during complex fan-outs.
 */
import dagre from '@dagrejs/dagre';

const DEFAULT_NODE_WIDTH = 260;
const DEFAULT_NODE_HEIGHT = 120;

const COMPACT_NODE_WIDTH = 220;
const COMPACT_NODE_HEIGHT = 80;

/**
 * Calculates topological positions for nodes and edges using Dagre.
 * @param {Array} nodes React Flow nodes
 * @param {Array} edges React Flow edges
 * @param {Object} options Configuration options ({ isCompact: boolean })
 * @returns {Array} Updated nodes with calculated { x, y } positions
 */
export function getLayoutedElements(nodes = [], edges = [], options = {}) {
  if (!nodes || nodes.length === 0) return [];

  const { isCompact = false } = options;
  const nodeWidth = isCompact ? COMPACT_NODE_WIDTH : DEFAULT_NODE_WIDTH;
  const nodeHeight = isCompact ? COMPACT_NODE_HEIGHT : DEFAULT_NODE_HEIGHT;

  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: 'LR',
    align: 'DL',
    nodesep: isCompact ? 40 : 65,
    ranksep: isCompact ? 90 : 160,
    edgesep: 25,
    marginx: 80,
    marginy: 80,
    acyclicer: 'greedy',
  });

  // Register nodes with bounding boxes
  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, {
      width: nodeWidth,
      height: nodeHeight,
    });
  });

  // Register edges (exclude cyclic feedback loop edges from rank calculation to prevent skew)
  edges.forEach((edge) => {
    const isFeedback = Boolean(edge.data?.is_feedback || edge.animated);
    if (!isFeedback && edge.source && edge.target) {
      dagreGraph.setEdge(edge.source, edge.target);
    }
  });

  // Execute topological layout
  dagre.layout(dagreGraph);

  // Return nodes with calculated top-left coordinates for React Flow
  return nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    if (!nodeWithPosition) return node;

    return {
      ...node,
      position: {
        x: Math.round(nodeWithPosition.x - nodeWidth / 2),
        y: Math.round(nodeWithPosition.y - nodeHeight / 2),
      },
    };
  });
}
