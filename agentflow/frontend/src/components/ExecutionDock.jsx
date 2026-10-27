/**
 * ExecutionDock — n8n-style bottom execution dock & data inspector.
 *
 * Provides organized, clean, and structured outputs:
 *   - Formatted View (Default): Executive summaries, email draft previews,
 *     key findings cards, source links, and structured attribute tables.
 *   - Tree View: Schema tree with type badges (#, T, {}, [ ], bool) and expandable text.
 *   - JSON View: Raw syntax-highlighted code block with 1-click clipboard copy.
 *   - Zero emojis: Clean SVG vector icons and polished typography.
 */
import { useState, useMemo, useEffect, useRef } from 'react';
import useStore from '../store';
import {
  IconTrash,
  IconClose,
  IconMaximize,
  IconRestore,
  IconFloat,
  IconDock,
  IconSearch,
  IconCheck,
  IconCopy,
  IconSparkles,
  IconMail,
  IconGlobe,
  IconFileText,
  IconExternalLink,
  IconChevronDown,
  IconChevronRight,
  IconRefresh,
  renderNodeIcon,
} from './Icons';

/**
 * Type badge helper for n8n tree view:
 *   # : number (cyan)
 *   T : string (purple/violet)
 *   bool : boolean (amber)
 *  {} : object (indigo)
 *  [] : array (emerald)
 */
function getTypeInfo(val) {
  if (val === null || val === undefined) return { label: 'null', color: '#64748b', bg: 'rgba(100, 116, 139, 0.15)' };
  if (typeof val === 'number') return { label: '#', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.18)' };
  if (typeof val === 'string') return { label: 'T', color: '#c084fc', bg: 'rgba(192, 132, 252, 0.18)' };
  if (typeof val === 'boolean') return { label: 'bool', color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.18)' };
  if (Array.isArray(val)) return { label: '[ ]', color: '#34d399', bg: 'rgba(52, 211, 153, 0.18)' };
  if (typeof val === 'object') return { label: '{ }', color: '#818cf8', bg: 'rgba(129, 140, 248, 0.18)' };
  return { label: '?', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.15)' };
}

/**
 * Recursive Tree Node Row matching Photo 2 with inline expansion for long text
 */
function SchemaTreeRow({ pathKey, value, depth = 0 }) {
  const [expanded, setExpanded] = useState(depth < 1);
  const [textExpanded, setTextExpanded] = useState(false);
  const typeInfo = getTypeInfo(value);
  const isObject = value !== null && typeof value === 'object' && !Array.isArray(value);
  const isArray = Array.isArray(value);
  const hasChildren = isObject || isArray;

  const childEntries = useMemo(() => {
    if (!hasChildren) return [];
    if (isArray) {
      return value.map((item, idx) => ({ key: `${pathKey}[${idx}]`, val: item }));
    }
    return Object.entries(value).map(([k, v]) => ({ key: k, val: v }));
  }, [hasChildren, isArray, pathKey, value]);

  const renderValuePreview = () => {
    if (value === null) return <span className="af-dock-tree-val af-dock-tree-val--null">null</span>;
    if (value === undefined) return <span className="af-dock-tree-val af-dock-tree-val--null">undefined</span>;
    if (typeof value === 'boolean') {
      return <span className="af-dock-tree-val af-dock-tree-val--bool">{String(value)}</span>;
    }
    if (typeof value === 'number') {
      return <span className="af-dock-tree-val af-dock-tree-val--num">{value}</span>;
    }
    if (typeof value === 'string') {
      const isLong = value.length > 90 || value.includes('\n');
      if (isLong && textExpanded) {
        return (
          <div className="af-dock-tree-str-expanded" onClick={(e) => e.stopPropagation()}>
            <div className="af-dock-tree-str-full">{value}</div>
            <button
              type="button"
              className="af-dock-expand-btn"
              onClick={() => setTextExpanded(false)}
            >
              Show less
            </button>
          </div>
        );
      }
      return (
        <span className="af-dock-tree-val af-dock-tree-val--str" title={value}>
          {value.length > 90 ? `${value.slice(0, 90)}...` : value}
          {isLong && (
            <button
              type="button"
              className="af-dock-expand-btn"
              onClick={(e) => {
                e.stopPropagation();
                setTextExpanded(true);
              }}
            >
              Expand
            </button>
          )}
        </span>
      );
    }
    if (isArray) {
      return (
        <span className="af-dock-tree-val af-dock-tree-val--coll">
          [{value.length} {value.length === 1 ? 'item' : 'items'}]
        </span>
      );
    }
    if (isObject) {
      return (
        <span className="af-dock-tree-val af-dock-tree-val--coll">
          {`{${Object.keys(value).length} keys}`}
        </span>
      );
    }
    return <span className="af-dock-tree-val">{String(value)}</span>;
  };

  return (
    <div className="af-dock-tree-node">
      <div
        className={`af-dock-tree-row ${hasChildren ? 'af-dock-tree-row--clickable' : ''}`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={hasChildren ? () => setExpanded(!expanded) : undefined}
      >
        {/* Expand / collapse arrow */}
        <span className="af-dock-tree-arrow">
          {hasChildren ? (
            expanded ? <IconChevronDown size={11} /> : <IconChevronRight size={11} />
          ) : (
            <span className="af-dock-tree-dot">•</span>
          )}
        </span>

        {/* Type Badge (#, T, {}, [], bool) */}
        <span
          className="af-dock-type-badge"
          style={{ color: typeInfo.color, background: typeInfo.bg }}
          title={typeof value}
        >
          {typeInfo.label}
        </span>

        {/* Field Key */}
        <span className="af-dock-tree-key">{pathKey}</span>

        {/* Field Value Preview */}
        {renderValuePreview()}
      </div>

      {/* Expanded Child Rows */}
      {hasChildren && expanded && (
        <div className="af-dock-tree-children">
          {childEntries.map((c) => (
            <SchemaTreeRow
              key={c.key}
              pathKey={c.key}
              value={c.val}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Clean, organized, human-readable Formatted Output View
 */
function FormattedOutputView({ payload, nodeName }) {
  const [copiedKey, setCopiedKey] = useState(null);

  const copyToClipboard = (text, key) => {
    navigator.clipboard?.writeText?.(typeof text === 'object' ? JSON.stringify(text, null, 2) : String(text));
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1800);
  };

  if (!payload || (typeof payload === 'object' && Object.keys(payload).length === 0)) {
    return (
      <div className="af-formatted-empty">
        <IconSearch size={18} />
        <span>No attributes to format</span>
      </div>
    );
  }

  // Primitive value
  if (typeof payload !== 'object') {
    return (
      <div className="af-formatted-card af-formatted-card--primitive">
        <div className="af-formatted-card__header">
          <span className="af-formatted-badge">Result</span>
          <button
            type="button"
            className="af-formatted-copy-btn"
            onClick={() => copyToClipboard(payload, 'prim')}
          >
            {copiedKey === 'prim' ? <><IconCheck size={11} /> Copied</> : <><IconCopy size={11} /> Copy</>}
          </button>
        </div>
        <div className="af-formatted-content-body">{String(payload)}</div>
      </div>
    );
  }

  // Array of items
  if (Array.isArray(payload)) {
    return (
      <div className="af-formatted-container">
        <div className="af-formatted-section-header">
          <span className="af-formatted-badge">{payload.length} items</span>
        </div>
        <div className="af-formatted-list">
          {payload.map((item, idx) => (
            <div key={idx} className="af-formatted-card af-formatted-card--list-item">
              <div className="af-formatted-card__header">
                <span className="af-formatted-badge">Item #{idx + 1}</span>
                <button
                  type="button"
                  className="af-formatted-copy-btn"
                  onClick={() => copyToClipboard(item, `arr_${idx}`)}
                >
                  {copiedKey === `arr_${idx}` ? <><IconCheck size={11} /> Copied</> : <><IconCopy size={11} /> Copy</>}
                </button>
              </div>
              <div className="af-formatted-card__body">
                {typeof item === 'object' && item !== null ? (
                  Object.entries(item).map(([k, v]) => (
                    <div key={k} className="af-formatted-kv-row">
                      <span className="af-formatted-kv-key">{k}</span>
                      <span className="af-formatted-kv-val">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                    </div>
                  ))
                ) : (
                  <div className="af-formatted-content-body">{String(item)}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Structured Dictionary / Object
  const {
    summary,
    result,
    content,
    subject,
    body,
    key_findings,
    findings,
    sources,
    urls,
    status,
    agent_type,
    tool_calls_count,
    ...restFields
  } = payload;

  const mainResultText = result || content;
  const findingsList = Array.isArray(key_findings) ? key_findings : Array.isArray(findings) ? findings : null;
  const sourcesList = Array.isArray(sources) ? sources : Array.isArray(urls) ? urls : null;
  const hasEmail = Boolean(subject || body);

  return (
    <div className="af-formatted-container">
      {/* 1. Executive Summary Card */}
      {summary && (
        <div className="af-formatted-card af-formatted-card--summary">
          <div className="af-formatted-card__header">
            <div className="af-formatted-card__title">
              <IconSparkles size={14} className="af-accent-icon" />
              <span>Executive Summary</span>
            </div>
            <button
              type="button"
              className="af-formatted-copy-btn"
              onClick={() => copyToClipboard(summary, 'summary')}
            >
              {copiedKey === 'summary' ? <><IconCheck size={11} /> Copied</> : <><IconCopy size={11} /> Copy</>}
            </button>
          </div>
          <div className="af-formatted-summary-text">{summary}</div>
        </div>
      )}

      {/* 2. Email Draft Preview Card */}
      {hasEmail && (
        <div className="af-formatted-card af-formatted-card--email">
          <div className="af-formatted-card__header">
            <div className="af-formatted-card__title">
              <IconMail size={14} className="af-email-icon" />
              <span>Generated Outreach Draft</span>
            </div>
            <button
              type="button"
              className="af-formatted-copy-btn"
              onClick={() => copyToClipboard(`Subject: ${subject || ''}\n\n${body || ''}`, 'email')}
            >
              {copiedKey === 'email' ? <><IconCheck size={11} /> Copied</> : <><IconCopy size={11} /> Copy Draft</>}
            </button>
          </div>
          <div className="af-formatted-email-box">
            {subject && (
              <div className="af-formatted-email-subject">
                <span className="af-formatted-email-label">Subject:</span>
                <span className="af-formatted-email-subject-text">{subject}</span>
              </div>
            )}
            {restFields.lead_name && (
              <div className="af-formatted-email-meta">
                <span className="af-formatted-email-label">To:</span>
                <span>{restFields.lead_name} {restFields.company ? `(${restFields.company})` : ''}</span>
              </div>
            )}
            {body && <div className="af-formatted-email-body">{body}</div>}
          </div>
        </div>
      )}

      {/* 3. Key Findings Cards */}
      {findingsList && findingsList.length > 0 && (
        <div className="af-formatted-card af-formatted-card--findings">
          <div className="af-formatted-card__header">
            <div className="af-formatted-card__title">
              <IconFileText size={14} />
              <span>Key Findings ({findingsList.length})</span>
            </div>
          </div>
          <div className="af-formatted-findings-grid">
            {findingsList.map((f, idx) => (
              <div key={idx} className="af-formatted-finding-item">
                <span className="af-formatted-finding-num">{idx + 1}</span>
                <div className="af-formatted-finding-content">
                  {typeof f === 'object' && f !== null ? (
                    <div>
                      {f.title && <div className="af-formatted-finding-title">{f.title}</div>}
                      <div className="af-formatted-finding-desc">
                        {f.description || f.detail || f.point || JSON.stringify(f)}
                      </div>
                    </div>
                  ) : (
                    <div>{String(f)}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Output Analysis & Results (Main Text Content) */}
      {mainResultText && !hasEmail && mainResultText !== summary && (
        <div className="af-formatted-card af-formatted-card--result">
          <div className="af-formatted-card__header">
            <div className="af-formatted-card__title">
              <IconFileText size={14} />
              <span>Output Analysis & Results</span>
            </div>
            <button
              type="button"
              className="af-formatted-copy-btn"
              onClick={() => copyToClipboard(mainResultText, 'result')}
            >
              {copiedKey === 'result' ? <><IconCheck size={11} /> Copied</> : <><IconCopy size={11} /> Copy</>}
            </button>
          </div>
          <div className="af-formatted-content-body">
            {mainResultText}
          </div>
        </div>
      )}

      {/* 5. Referencing Sources */}
      {sourcesList && sourcesList.length > 0 && (
        <div className="af-formatted-card af-formatted-card--sources">
          <div className="af-formatted-card__header">
            <div className="af-formatted-card__title">
              <IconGlobe size={14} />
              <span>Referenced Sources ({sourcesList.length})</span>
            </div>
          </div>
          <div className="af-formatted-sources-list">
            {sourcesList.map((src, i) => {
              const url = typeof src === 'string' ? src : src.url || src.link || '';
              const title = typeof src === 'object' ? src.title || src.name || url : url;
              return (
                <a
                  key={i}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="af-formatted-source-chip"
                >
                  <IconExternalLink size={11} />
                  <span>{title}</span>
                </a>
              );
            })}
          </div>
        </div>
      )}

      {/* 6. Structured Attributes (Clean key-value grid for trigger inputs, config, metadata) */}
      {Object.keys(restFields).length > 0 && (
        <div className="af-formatted-card af-formatted-card--attributes">
          <div className="af-formatted-card__header">
            <div className="af-formatted-card__title">
              <IconCheck size={13} />
              <span>Structured Attributes</span>
            </div>
          </div>
          <div className="af-formatted-grid">
            {Object.entries(restFields).map(([key, val]) => (
              <div key={key} className="af-formatted-grid-cell">
                <span className="af-formatted-grid-label">{key.replace(/_/g, ' ')}</span>
                <span className="af-formatted-grid-value" title={String(val)}>
                  {typeof val === 'object' && val !== null ? JSON.stringify(val) : String(val)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ExecutionDock() {
  const executionDockOpen = useStore((s) => s.executionDockOpen);
  const setExecutionDockOpen = useStore((s) => s.setExecutionDockOpen);
  const selectedExecutionNodeId = useStore((s) => s.selectedExecutionNodeId);
  const setSelectedExecutionNodeId = useStore((s) => s.setSelectedExecutionNodeId);
  const executionDockTab = useStore((s) => s.executionDockTab);
  const setExecutionDockTab = useStore((s) => s.setExecutionDockTab);
  const executionDockView = useStore((s) => s.executionDockView);
  const setExecutionDockView = useStore((s) => s.setExecutionDockView);
  const clearExecution = useStore((s) => s.clearExecution);
  const nodes = useStore((s) => s.nodes);
  const runEvents = useStore((s) => s.runEvents);
  const runStatus = useStore((s) => s.runStatus);
  const addToast = useStore((s) => s.addToast);
  const retryNode = useStore((s) => s.retryNode);
  const workflowId = useStore((s) => s.workflowId);
  const workflowName = useStore((s) => s.workflowName);
  const runId = useStore((s) => s.runId);
  const runMetrics = useStore((s) => s.runMetrics);
  const workflowContext = useStore((s) => s.workflowContext);

  const executionDockHeight = useStore((s) => s.executionDockHeight);
  const setExecutionDockHeight = useStore((s) => s.setExecutionDockHeight);
  const executionDockFloating = useStore((s) => s.executionDockFloating);
  const setExecutionDockFloating = useStore((s) => s.setExecutionDockFloating);
  const executionDockPosition = useStore((s) => s.executionDockPosition);
  const setExecutionDockPosition = useStore((s) => s.setExecutionDockPosition);
  const executionDockMaximized = useStore((s) => s.executionDockMaximized);
  const setExecutionDockMaximized = useStore((s) => s.setExecutionDockMaximized);

  const [copied, setCopied] = useState(false);
  const [traceCopied, setTraceCopied] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [isDraggingWindow, setIsDraggingWindow] = useState(false);
  const [floatingSize, setFloatingSize] = useState({ width: 920, height: 500 });

  const handleCopyTraceJson = () => {
    const traceSnapshot = {
      workflow: {
        id: workflowId,
        name: workflowName,
      },
      execution: {
        runId,
        status: runStatus,
        metrics: runMetrics,
        timestamp: new Date().toISOString(),
      },
      context: workflowContext,
      nodes: nodes.map((n) => ({
        id: n.id,
        label: n.data?.label || n.id,
        nodeType: n.data?.nodeType,
        status: n.data?.status || 'idle',
        input: n.data?.input,
        output: n.data?.output,
        error: n.data?.error,
        metrics: n.data?.metrics,
      })),
      events: runEvents,
    };
    navigator.clipboard?.writeText?.(JSON.stringify(traceSnapshot, null, 2));
    setTraceCopied(true);
    addToast('Complete Execution Trace JSON copied to clipboard', 'success', 2500);
    setTimeout(() => setTraceCopied(false), 2000);
  };

  // Sync CSS variable for docked layout
  useEffect(() => {
    if (typeof window !== 'undefined' && !executionDockFloating && executionDockHeight) {
      document.documentElement.style.setProperty('--af-dock-height', `${executionDockHeight}px`);
    }
  }, [executionDockHeight, executionDockFloating]);

  // Handle vertical resize of bottom dock
  const handleResizeMouseDown = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizing(true);
    const startY = e.clientY;
    const startHeight = executionDockHeight;

    const onMouseMove = (ev) => {
      const deltaY = startY - ev.clientY;
      const newHeight = Math.min(
        Math.max(140, startHeight + deltaY),
        window.innerHeight - 80
      );
      setExecutionDockHeight(newHeight);
    };

    const onMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  // Handle moving the floating window around
  const handleHeaderMouseDown = (e) => {
    if (!executionDockFloating) return;
    if (e.target.closest('button, input, select, a, .af-dock-segment-btn, .af-dock-view-btn, .af-dock-logs-pill')) {
      return;
    }
    e.preventDefault();
    setIsDraggingWindow(true);
    const startX = e.clientX;
    const startY = e.clientY;
    const initialPos = { ...executionDockPosition };

    const onMouseMove = (ev) => {
      const deltaX = ev.clientX - startX;
      const deltaY = ev.clientY - startY;
      const newX = Math.max(0, Math.min(window.innerWidth - 180, initialPos.x + deltaX));
      const newY = Math.max(0, Math.min(window.innerHeight - 80, initialPos.y + deltaY));
      setExecutionDockPosition({ x: newX, y: newY });
    };

    const onMouseUp = () => {
      setIsDraggingWindow(false);
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  // Double click header or resizer to toggle maximize
  const handleHeaderDoubleClick = (e) => {
    if (e && e.target.closest('button, input, select, a, .af-dock-segment-btn, .af-dock-view-btn')) return;
    setExecutionDockMaximized(!executionDockMaximized);
  };

  // Handle corner resizing of floating window
  const handleCornerResizeMouseDown = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizing(true);
    const startX = e.clientX;
    const startY = e.clientY;
    const startW = floatingSize.width;
    const startH = floatingSize.height;

    const onMouseMove = (ev) => {
      const newW = Math.max(500, Math.min(window.innerWidth - executionDockPosition.x - 20, startW + (ev.clientX - startX)));
      const newH = Math.max(240, Math.min(window.innerHeight - executionDockPosition.y - 20, startH + (ev.clientY - startY)));
      setFloatingSize({ width: newW, height: newH });
    };

    const onMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  // Chronological list of executed nodes
  const executedNodes = useMemo(() => {
    const executedNodeIds = [];
    runEvents.forEach((ev) => {
      const nid = ev.node_id || ev.nodeId || ev.id;
      if (nid && !executedNodeIds.includes(nid)) {
        executedNodeIds.push(nid);
      }
    });

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    const list = [];
    for (const id of executedNodeIds) {
      if (nodeMap.has(id)) {
        list.push(nodeMap.get(id));
      }
    }

    if (list.length === 0) {
      return nodes.filter(
        (n) => n.data?.status === 'completed' || n.data?.status === 'running' || n.data?.status === 'failed'
      );
    }
    return list;
  }, [runEvents, nodes]);

  // Active node to inspect
  const activeNode = useMemo(() => {
    if (selectedExecutionNodeId) {
      const found = nodes.find((n) => n.id === selectedExecutionNodeId);
      if (found) return found;
    }

    // Auto-select latest completed node with output
    const completedWithOutput = [...nodes].reverse().find(
      (n) => n.data?.status === 'completed' && (n.data?.output !== undefined && n.data?.output !== null)
    );
    if (completedWithOutput) return completedWithOutput;

    // Or any completed node
    const anyCompleted = [...nodes].reverse().find((n) => n.data?.status === 'completed');
    if (anyCompleted) return anyCompleted;

    // Or running node
    const running = nodes.find((n) => n.data?.status === 'running');
    if (running) return running;

    if (executedNodes.length > 0) {
      return executedNodes[executedNodes.length - 1];
    }
    return nodes[0] || null;
  }, [selectedExecutionNodeId, nodes, executedNodes]);

  // Auto-sync selectedExecutionNodeId when an active node is chosen
  useEffect(() => {
    if (!selectedExecutionNodeId && activeNode) {
      setSelectedExecutionNodeId(activeNode.id);
    }
  }, [activeNode, selectedExecutionNodeId, setSelectedExecutionNodeId]);

  // Determine active payload for Input or Output
  const activePayload = useMemo(() => {
    if (!activeNode) return null;
    const nodeData = activeNode.data || {};

    if (executionDockTab === 'output') {
      // 1. Check direct output on nodeData
      if (nodeData.output !== undefined && nodeData.output !== null) return nodeData.output;
      if (nodeData.outputs !== undefined && nodeData.outputs !== null) return nodeData.outputs;
      if (nodeData.outputData !== undefined && nodeData.outputData !== null) return nodeData.outputData;
      if (nodeData.result !== undefined && nodeData.result !== null) return nodeData.result;

      // 2. Check runEvents for node_completed
      const completedEv = [...runEvents].reverse().find(
        (e) =>
          (e.node_id === activeNode.id || e.id === activeNode.id) &&
          (e.event === 'node_completed' || e.event_type === 'node_completed' || e.data?.output !== undefined)
      );
      if (completedEv?.data?.output !== undefined && completedEv?.data?.output !== null) {
        return completedEv.data.output;
      }

      // 3. Trigger fallback
      if (
        activeNode.id?.toLowerCase().includes('trigger') ||
        activeNode.data?.nodeType?.toLowerCase().includes('trigger')
      ) {
        return nodeData.config?.trigger_data || nodeData.config || nodeData.input || null;
      }

      return null;
    }

    if (executionDockTab === 'input') {
      // 1. Check direct input on nodeData
      if (nodeData.input !== undefined && nodeData.input !== null) return nodeData.input;
      if (nodeData.inputs !== undefined && nodeData.inputs !== null) return nodeData.inputs;
      if (nodeData.inputData !== undefined && nodeData.inputData !== null) return nodeData.inputData;
      if (nodeData.initial_payload !== undefined && nodeData.initial_payload !== null) return nodeData.initial_payload;

      // 2. Check runEvents
      const startEv = [...runEvents].reverse().find(
        (e) =>
          (e.node_id === activeNode.id || e.id === activeNode.id) &&
          e.data?.input !== undefined &&
          e.data?.input !== null
      );
      if (startEv?.data?.input !== undefined && startEv?.data?.input !== null) {
        return startEv.data.input;
      }

      // 3. Fallback to node config
      if (nodeData.config && Object.keys(nodeData.config).length > 0) {
        return nodeData.config;
      }

      return null;
    }

    return null;
  }, [activeNode, executionDockTab, runEvents]);

  // Count items / keys in active payload
  const itemCount = useMemo(() => {
    if (!activePayload) return 0;
    if (Array.isArray(activePayload)) return activePayload.length;
    if (typeof activePayload === 'object') return Object.keys(activePayload).length;
    return 1;
  }, [activePayload]);

  const handleCopyJson = () => {
    if (!activePayload) return;
    try {
      navigator.clipboard?.writeText(JSON.stringify(activePayload, null, 2));
      setCopied(true);
      if (addToast) addToast('Copied payload to clipboard', 'info');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  const totalRunDuration = useMemo(() => {
    if (runEvents.length < 2) return null;
    const first = new Date(runEvents[0].timestamp || Date.now()).getTime();
    const last = new Date(runEvents[runEvents.length - 1].timestamp || Date.now()).getTime();
    const diff = last - first;
    if (diff > 0 && diff < 600000) {
      return diff > 1000 ? `${(diff / 1000).toFixed(2)}s` : `${diff}ms`;
    }
    return null;
  }, [runEvents]);

  if (!executionDockOpen) return null;

  // Window positioning styles (docked vs floating vs maximized)
  let windowStyle = {};
  if (executionDockMaximized) {
    windowStyle = {
      position: 'fixed',
      top: 56,
      left: 12,
      right: 12,
      bottom: 12,
      width: 'calc(100vw - 24px)',
      height: 'calc(100vh - 68px)',
      zIndex: 99999,
      borderRadius: 10,
    };
  } else if (executionDockFloating) {
    windowStyle = {
      position: 'fixed',
      top: executionDockPosition.y,
      left: executionDockPosition.x,
      width: `${floatingSize.width}px`,
      height: `${floatingSize.height}px`,
      zIndex: 99999,
      borderRadius: 10,
    };
  } else {
    windowStyle = {
      height: `${executionDockHeight}px`,
    };
  }

  return (
    <div
      className={`af-dock ${executionDockFloating ? 'af-dock--floating' : 'af-dock--docked'} ${
        executionDockMaximized ? 'af-dock--maximized' : ''
      }`}
      style={windowStyle}
    >
      {/* Resizer Handle (Only for bottom docked mode) */}
      {!executionDockFloating && !executionDockMaximized && (
        <div
          className={`af-dock__resizer ${isResizing ? 'af-dock__resizer--active' : ''}`}
          onMouseDown={handleResizeMouseDown}
          onDoubleClick={handleHeaderDoubleClick}
          title="Drag up or down to resize output bar • Double-click to maximize"
        >
          <div className="af-dock__resizer-handle" />
        </div>
      )}

      {/* ── Top Bar matching Photo 2 ── */}
      <div
        className={`af-dock__header ${executionDockFloating ? 'af-dock__header--draggable' : ''} ${
          isDraggingWindow ? 'af-dock__header--dragging' : ''
        }`}
        onMouseDown={handleHeaderMouseDown}
        onDoubleClick={handleHeaderDoubleClick}
        title={
          executionDockFloating
            ? 'Drag to move window anywhere • Double-click to maximize'
            : 'Double-click to expand or restore output bar'
        }
      >
        {/* Left Side: Logs Pill, Clear Execution & Copy Trace JSON */}
        <div className="af-dock__header-left">
          <div className="af-dock-logs-pill">
            <span className="af-dock-dot" />
            <span>Logs</span>
            {runEvents.length > 0 && <span className="af-dock-counter">{runEvents.length}</span>}
          </div>

          <button
            type="button"
            className="af-dock-btn af-dock-btn--ghost"
            onClick={clearExecution}
            title="Clear all executed outputs and reset run state"
          >
            <IconTrash size={12} />
            <span>Clear</span>
          </button>

          <button
            type="button"
            className="af-dock-btn af-dock-btn--ghost"
            onClick={handleCopyTraceJson}
            title="Copy complete execution trace snapshot as JSON for debugging"
          >
            {traceCopied ? <IconCheck size={12} /> : <IconCopy size={12} />}
            <span>{traceCopied ? 'Trace Copied' : 'Copy Trace JSON'}</span>
          </button>
        </div>

        {/* Center: Selected Node Icon + Name + Timing Badge */}
        <div className="af-dock__header-center">
          {activeNode ? (
            <div className="af-dock-node-badge">
              <span className="af-dock-node-icon">
                {renderNodeIcon(activeNode.data?.nodeType, activeNode.data?.label, 13)}
              </span>
              <span className="af-dock-node-title">{activeNode.data?.label || activeNode.id}</span>

              {activeNode.data?.status === 'completed' && (
                <span className="af-dock-timing-badge af-dock-timing-badge--success">
                  Success{activeNode.data?.metrics?.latency_ms ? ` in ${activeNode.data.metrics.latency_ms}ms` : ''}
                </span>
              )}
              {activeNode.data?.status === 'running' && (
                <span className="af-dock-timing-badge af-dock-timing-badge--running">
                  <span className="spinner-dots" /> Running...
                </span>
              )}
              {activeNode.data?.status === 'failed' && (
                <span className="af-dock-timing-badge af-dock-timing-badge--error">
                  Failed{activeNode.data?.metrics?.latency_ms ? ` in ${activeNode.data.metrics.latency_ms}ms` : ''}
                </span>
              )}
              {activeNode.data?.status === 'timed_out' && (
                <span className="af-dock-timing-badge af-dock-timing-badge--error" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', borderColor: '#f59e0b' }}>
                  Timed Out
                </span>
              )}
              {activeNode.data?.status === 'skipped' && (
                <span className="af-dock-timing-badge af-dock-timing-badge--skipped">
                  Skipped (DPE)
                </span>
              )}

              {activeNode.data?.metrics?.tokens > 0 && (
                <span className="af-dock-timing-badge" style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', borderColor: 'rgba(99, 102, 241, 0.3)' }}>
                  {activeNode.data.metrics.tokens} tokens
                </span>
              )}

              {(activeNode.data?.status === 'failed' || activeNode.data?.status === 'timed_out') && (
                <button
                  type="button"
                  className="af-dock-retry-step-btn"
                  onClick={() => retryNode(activeNode.id)}
                  title="Retry single node execution with cached parent inputs without restarting pipeline"
                >
                  <IconRefresh size={11} />
                  <span>↻ Retry Step</span>
                </button>
              )}
            </div>
          ) : (
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>No node selected</span>
          )}
        </div>

        {/* Right Side: Segmented [ Input ] [ Output ] + Items Counter + View Switcher */}
        <div className="af-dock__header-right">
          {/* Segmented Input / Output Toggle (n8n signature) */}
          <div className="af-dock-segmented-group">
            <button
              type="button"
              className={`af-dock-segment-btn ${
                executionDockTab === 'input' ? 'af-dock-segment-btn--active' : ''
              }`}
              onClick={() => setExecutionDockTab('input')}
            >
              Input
            </button>
            <button
              type="button"
              className={`af-dock-segment-btn ${
                executionDockTab === 'output' ? 'af-dock-segment-btn--active' : ''
              }`}
              onClick={() => setExecutionDockTab('output')}
            >
              Output
            </button>
          </div>

          {/* Items Counter Badge */}
          <span className="af-dock-items-count">
            {itemCount} {itemCount === 1 ? 'item' : 'items'}
          </span>

          {/* Formatted vs Tree vs JSON View Switcher */}
          <div className="af-dock-view-toggle">
            <button
              type="button"
              className={`af-dock-view-btn ${executionDockView === 'formatted' ? 'active' : ''}`}
              onClick={() => setExecutionDockView('formatted')}
              title="Organized, Clean Formatted Cards"
            >
              Formatted
            </button>
            <button
              type="button"
              className={`af-dock-view-btn ${executionDockView === 'tree' ? 'active' : ''}`}
              onClick={() => setExecutionDockView('tree')}
              title="Schema Tree View with Type Badges"
            >
              Tree
            </button>
            <button
              type="button"
              className={`af-dock-view-btn ${executionDockView === 'json' ? 'active' : ''}`}
              onClick={() => setExecutionDockView('json')}
              title="Raw JSON Code"
            >
              JSON
            </button>
          </div>

          {/* Header Actions: Float/Dock, Maximize/Restore, Close */}
          <div className="af-dock-header-actions">
            <button
              type="button"
              className={`af-dock-action-icon-btn ${executionDockFloating ? 'active' : ''}`}
              onClick={() => setExecutionDockFloating(!executionDockFloating)}
              title={
                executionDockFloating
                  ? 'Dock output bar to bottom of canvas'
                  : 'Detach as movable floating window (drag anywhere)'
              }
            >
              {executionDockFloating ? <IconDock size={12} /> : <IconFloat size={12} />}
              <span>{executionDockFloating ? 'Dock' : 'Float'}</span>
            </button>

            <button
              type="button"
              className="af-dock-action-icon-btn"
              onClick={() => setExecutionDockMaximized(!executionDockMaximized)}
              title={executionDockMaximized ? 'Restore normal height' : 'Maximize output view'}
            >
              {executionDockMaximized ? <IconRestore size={12} /> : <IconMaximize size={12} />}
            </button>

            <button
              type="button"
              className="af-dock-close-btn"
              onClick={() => setExecutionDockOpen(false)}
              title="Close Output Dock"
            >
              <IconClose size={12} />
            </button>
          </div>
        </div>
      </div>

      {/* ── Dock Body: Two Column Split View (Photo 2) ── */}
      <div className="af-dock__body">
        {/* ── Left Column: Executed Nodes List ── */}
        <div className="af-dock__sidebar">
          <div className="af-dock__sidebar-header">
            {runStatus === 'completed' && (
              <span className="af-dock-overall-status af-dock-overall-status--success">
                Success{totalRunDuration ? ` in ${totalRunDuration}` : ''}
              </span>
            )}
            {runStatus === 'failed' && (
              <span className="af-dock-overall-status af-dock-overall-status--failed">
                Failed{totalRunDuration ? ` in ${totalRunDuration}` : ''}
              </span>
            )}
            {runStatus === 'running' && (
              <span className="af-dock-overall-status af-dock-overall-status--running">
                <span className="spinner-dots" /> Executing DAG...
              </span>
            )}
            {!runStatus && (
              <span className="af-dock-overall-status">Workflow Nodes</span>
            )}
          </div>

          <div className="af-dock__node-list">
            {(executedNodes.length > 0 ? executedNodes : nodes).map((node) => {
              const isSelected = activeNode?.id === node.id;
              const nStatus = node.data?.status;
              const nTiming = node.data?.metrics?.latency_ms;

              return (
                <div
                  key={node.id}
                  className={`af-dock-node-row ${isSelected ? 'af-dock-node-row--selected' : ''}`}
                  onClick={() => setSelectedExecutionNodeId(node.id)}
                >
                  <span className="af-dock-node-row-icon">
                    {renderNodeIcon(node.data?.nodeType, node.data?.label, 13)}
                  </span>
                  <div className="af-dock-node-row-text">
                    <span className="af-dock-node-row-title">{node.data?.label || node.id}</span>
                    <span className="af-dock-node-row-sub">
                      {node.data?.nodeType?.replace(/_/g, ' ') || 'agent'}
                    </span>
                  </div>

                  <div className="af-dock-node-row-meta">
                    {nStatus === 'completed' && (
                      <span className="af-dock-status-dot af-dock-status-dot--success" title="Completed">
                        <IconCheck size={10} />
                      </span>
                    )}
                    {nStatus === 'failed' && (
                      <span className="af-dock-status-dot af-dock-status-dot--failed" title="Failed">
                        <IconClose size={10} />
                      </span>
                    )}
                    {nStatus === 'timed_out' && (
                      <span className="af-dock-status-dot af-dock-status-dot--failed" style={{ background: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b', borderColor: '#f59e0b' }} title="Timed Out">
                        !
                      </span>
                    )}
                    {nStatus === 'running' && (
                      <span className="af-dock-status-dot af-dock-status-dot--running" title="Running">
                        <span className="af-dock-pulse-dot" />
                      </span>
                    )}
                    {nStatus === 'skipped' && (
                      <span className="af-dock-status-dot af-dock-status-dot--skipped" title="Skipped">
                        –
                      </span>
                    )}
                    {nTiming ? <span className="af-dock-timing-text">{nTiming}ms</span> : null}
                    {(nStatus === 'failed' || nStatus === 'timed_out') && (
                      <button
                        type="button"
                        className="af-dock-node-retry-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          retryNode(node.id);
                        }}
                        title="Retry step with cached parent input"
                      >
                        <IconRefresh size={9} />
                        <span>Retry</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Right Column: Data Inspector (Formatted / Tree / JSON) ── */}
        <div className="af-dock__main">
          <div className="af-dock__main-header">
            <span className="af-dock-label-heading">
              {executionDockTab.toUpperCase()} • {executionDockView.toUpperCase()}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="af-dock-main-item-count">
                {itemCount} {itemCount === 1 ? 'item' : 'items'}
              </span>
              {activePayload && (
                <button
                  type="button"
                  className="af-dock-copy-btn"
                  onClick={handleCopyJson}
                  title="Copy payload to clipboard"
                >
                  {copied ? <><IconCheck size={11} /> Copied</> : <><IconCopy size={11} /> Copy JSON</>}
                </button>
              )}
            </div>
          </div>

          <div className="af-dock__main-content">
            {activePayload ? (
              executionDockView === 'formatted' ? (
                <FormattedOutputView
                  payload={activePayload}
                  nodeName={activeNode?.data?.label || 'Node'}
                  tabType={executionDockTab}
                />
              ) : executionDockView === 'tree' ? (
                <div className="af-dock-tree-view">
                  {typeof activePayload === 'object' && !Array.isArray(activePayload) ? (
                    Object.entries(activePayload).map(([k, v]) => (
                      <SchemaTreeRow key={k} pathKey={k} value={v} depth={0} />
                    ))
                  ) : Array.isArray(activePayload) ? (
                    activePayload.map((item, idx) => (
                      <SchemaTreeRow key={idx} pathKey={`item[${idx}]`} value={item} depth={0} />
                    ))
                  ) : (
                    <SchemaTreeRow pathKey="value" value={activePayload} depth={0} />
                  )}
                </div>
              ) : (
                <pre className="af-dock-json-code">
                  {JSON.stringify(activePayload, null, 2)}
                </pre>
              )
            ) : activeNode?.data?.status === 'running' ? (
              <div className="af-dock-empty-state">
                <span className="af-dock-pulse-dot" style={{ width: 12, height: 12, marginBottom: 12 }} />
                <span className="af-dock-empty-title">
                  Executing {activeNode?.data?.label || activeNode?.id}...
                </span>
                <span className="af-dock-empty-desc">
                  Node is actively running. Output will appear here automatically upon completion.
                </span>
              </div>
            ) : (
              <div className="af-dock-empty-state">
                <span className="af-dock-empty-icon"><IconSearch size={24} /></span>
                <span className="af-dock-empty-title">
                  No {executionDockTab} data recorded for {activeNode?.data?.label || 'this node'}
                </span>
                <span className="af-dock-empty-desc">
                  Execute the workflow to capture live inputs and outputs across all nodes.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Corner resizer handle when floating */}
      {executionDockFloating && !executionDockMaximized && (
        <div
          className="af-dock__corner-resizer"
          onMouseDown={handleCornerResizeMouseDown}
          title="Drag to resize window width and height"
        />
      )}
    </div>
  );
}
