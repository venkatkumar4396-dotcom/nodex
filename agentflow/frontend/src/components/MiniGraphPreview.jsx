/**
 * MiniGraphPreview — Crisp client-side SVG mini-map thumbnail of workflow topology.
 *
 * Renders node positions, connections, and color-coded vector badges directly from
 * lightweight preview coordinates without rendering full canvas DOM trees.
 * Strictly adheres to zero-emoji policy using modern geometric vector badges.
 */
import { useMemo } from 'react';

const NODE_COLORS = {
  trigger_manual: '#6366f1',
  trigger_webhook: '#6366f1',
  prompt: '#8b5cf6',
  tool: '#0ea5e9',
  router: '#ec4899',
  human_approval: '#f59e0b',
  code: '#10b981',
  mcp_client: '#06b6d4',
  synthesizer: '#14b8a6',
  research: '#0ea5e9',
  writer: '#8b5cf6',
  reviewer: '#f59e0b',
  email: '#38bdf8',
  default: '#8b5cf6',
};

export default function MiniGraphPreview({ nodes = [], edges = [], height = 110 }) {
  const { viewBox, scaledNodes, scaledEdges } = useMemo(() => {
    const targetWidth = 320;
    const targetHeight = 110;
    const paddingX = 36;
    const paddingY = 28;

    const safeNodes = Array.isArray(nodes) && nodes.length > 0 ? nodes : [
      { id: '1', type: 'trigger_manual', label: 'Trigger', x: 0, y: 0 },
      { id: '2', type: 'prompt', label: 'Processor', x: 0, y: 0 },
      { id: '3', type: 'tool', label: 'Output', x: 0, y: 0 },
    ];

    const safeEdges = Array.isArray(edges) && edges.length > 0 ? edges : [
      { source: '1', target: '2', is_feedback: false },
      { source: '2', target: '3', is_feedback: false },
    ];

    // Check if nodes have distinct valid coordinates
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;

    safeNodes.forEach((n) => {
      const x = typeof n.x === 'number' ? n.x : (n.position?.x ?? 0);
      const y = typeof n.y === 'number' ? n.y : (n.position?.y ?? 0);
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    });

    const hasDistinctCoords = maxX - minX > 30;

    const nodeMap = {};
    const processedNodes = safeNodes.map((n, idx) => {
      let px, py;

      if (hasDistinctCoords) {
        const widthSpan = Math.max(maxX - minX, 100);
        const heightSpan = Math.max(maxY - minY, 50);
        const scaleX = (targetWidth - paddingX * 2) / widthSpan;
        const scaleY = (targetHeight - paddingY * 2) / heightSpan;
        const scale = Math.min(scaleX, scaleY, 0.42);

        const rawX = typeof n.x === 'number' ? n.x : (n.position?.x ?? 0);
        const rawY = typeof n.y === 'number' ? n.y : (n.position?.y ?? 0);

        px = paddingX + (rawX - minX) * scale;
        py = paddingY + (rawY - minY) * scale;
      } else {
        // Automatic aesthetic topological layout when coordinates are identical or missing
        const stepX = (targetWidth - paddingX * 2) / Math.max(safeNodes.length - 1, 1);
        px = paddingX + idx * stepX;
        // Alternating wave for visual clarity
        py = targetHeight / 2 + (idx % 2 === 1 ? 12 : -12);
        if (safeNodes.length <= 2) py = targetHeight / 2;
      }

      const type = n.type || n.data?.nodeType || 'prompt';
      const color = NODE_COLORS[type] || NODE_COLORS.default;
      const rawLabel = n.label || n.data?.label || type;
      const label = rawLabel.replace(/[\u{1F300}-\u{1FAFF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]/gu, '').trim();

      const nodeObj = {
        id: n.id || String(idx),
        x: Math.round(px),
        y: Math.round(py),
        type,
        color,
        label: label.length > 12 ? `${label.slice(0, 10)}…` : label,
      };

      nodeMap[nodeObj.id] = nodeObj;
      return nodeObj;
    });

    const processedEdges = safeEdges
      .map((e, idx) => {
        const src = nodeMap[e.source];
        const tgt = nodeMap[e.target];
        if (!src || !tgt) return null;
        return {
          id: e.id || `${e.source}->${e.target}-${idx}`,
          src,
          tgt,
          isFeedback: Boolean(e.is_feedback || e.data?.is_feedback),
          isErrorHandler: Boolean(e.is_error_handler || e.data?.is_error_handler),
        };
      })
      .filter(Boolean);

    return {
      viewBox: `0 0 ${targetWidth} ${targetHeight}`,
      scaledNodes: processedNodes,
      scaledEdges: processedEdges,
    };
  }, [nodes, edges]);

  return (
    <div
      className="af-mini-graph"
      style={{
        width: '100%',
        height,
        background: 'linear-gradient(180deg, rgba(17,19,26,0.85) 0%, rgba(9,10,14,0.95) 100%)',
        borderRadius: 8,
        border: '1px solid rgba(255,255,255,0.06)',
        position: 'relative',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {/* Background subtle dot pattern */}
      <svg
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          opacity: 0.12,
          pointerEvents: 'none',
        }}
      >
        <pattern id="af-mini-grid" width="16" height="16" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="0.8" fill="#ffffff" />
        </pattern>
        <rect width="100%" height="100%" fill="url(#af-mini-grid)" />
      </svg>

      <svg
        viewBox={viewBox}
        preserveAspectRatio="xMidYMid meet"
        style={{ width: '100%', height: '100%', position: 'relative', zIndex: 1 }}
      >
        <defs>
          <linearGradient id="af-mini-edge" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#6366f1" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.8" />
          </linearGradient>
          <marker
            id="af-mini-arrow"
            viewBox="0 0 10 10"
            refX="6"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 8 5 L 0 9 z" fill="rgba(148, 163, 184, 0.7)" />
          </marker>
        </defs>

        {/* Directed connection curves */}
        {scaledEdges.map((e, idx) => {
          const dx = Math.abs(e.tgt.x - e.src.x) * 0.5;
          const strokeColor = e.isFeedback ? '#f59e0b' : e.isErrorHandler ? '#ef4444' : 'rgba(99, 102, 241, 0.55)';
          const pathD = `M ${e.src.x + 8} ${e.src.y} C ${e.src.x + 8 + dx} ${e.src.y}, ${e.tgt.x - 8 - dx} ${e.tgt.y}, ${e.tgt.x - 8} ${e.tgt.y}`;
          return (
            <path
              key={e.id || idx}
              d={pathD}
              fill="none"
              stroke={strokeColor}
              strokeWidth={e.isFeedback ? '1.5' : '1.7'}
              strokeDasharray={e.isFeedback ? '3 3' : undefined}
              markerEnd="url(#af-mini-arrow)"
            />
          );
        })}

        {/* Nodes with sleek geometric vector badges */}
        {scaledNodes.map((n) => (
          <g key={n.id} transform={`translate(${n.x}, ${n.y})`}>
            {/* Outer soft ambient glow */}
            <circle
              cx="0"
              cy="0"
              r="11"
              fill="none"
              stroke={n.color}
              strokeOpacity="0.25"
              strokeWidth="4"
            />
            {/* Node badge border */}
            <circle
              cx="0"
              cy="0"
              r="8"
              fill="#121319"
              stroke={n.color}
              strokeWidth="1.8"
            />
            {/* Inner core pulse dot */}
            <circle
              cx="0"
              cy="0"
              r="3.2"
              fill={n.color}
            />
            {/* Micro label */}
            <text
              x="0"
              y="16"
              textAnchor="middle"
              fontSize="7.5"
              fontFamily="inherit"
              fill="rgba(226, 232, 240, 0.75)"
              fontWeight="500"
              pointerEvents="none"
            >
              {n.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
