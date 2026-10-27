/**
 * NodeInspectorModal — AgentFlow Step Data Inspector.
 *
 * Provides:
 *   - Split inspection: INPUT (data received) vs OUTPUT (data produced) vs CONFIG
 *   - 3 View Modes: Table (Key-Value), JSON (with 1-click copy), Schema breakdown
 *   - Runtime metrics: duration (ms), total tokens, cost (USD), status
 *   - Step navigation: previous / next step in execution graph
 */
import { useState, useEffect } from 'react';
import useStore from '../store';
import { renderNodeIcon, IconCopy, IconCheck, IconFileText, IconSettings, IconClose } from './Icons';
import Draggable from 'react-draggable';

export default function NodeInspectorModal() {
  const inspectingNodeId = useStore((s) => s.inspectingNodeId);
  const closeNodeInspector = useStore((s) => s.closeNodeInspector);
  const openNodeInspector = useStore((s) => s.openNodeInspector);
  const nodes = useStore((s) => s.nodes);
  const addToast = useStore((s) => s.addToast);

  const [activeTab, setActiveTab] = useState('output'); // 'output' | 'input' | 'config'
  const [viewMode, setViewMode] = useState('table'); // 'table' | 'json' | 'raw'
  const [copied, setCopied] = useState(false);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') closeNodeInspector();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [closeNodeInspector]);

  if (!inspectingNodeId) return null;

  const nodeIndex = nodes.findIndex((n) => n.id === inspectingNodeId);
  const node = nodes[nodeIndex];
  if (!node) return null;

  const prevNode = nodeIndex > 0 ? nodes[nodeIndex - 1] : null;
  const nextNode = nodeIndex < nodes.length - 1 ? nodes[nodeIndex + 1] : null;

  const { data } = node;
  const { label, nodeType, color, status, input, output, metrics, config, error } = data;

  const currentPayload = activeTab === 'input' ? input : activeTab === 'output' ? output : config;

  const handleCopy = (content) => {
    const text = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
    navigator.clipboard.writeText(text);
    setCopied(true);
    addToast('Copied payload to clipboard', 'success', 2000);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="af-inspector-backdrop" style={{ pointerEvents: 'none', background: 'transparent' }}>
      <Draggable handle=".af-inspector-header">
        <div className="af-inspector-modal" onClick={(e) => e.stopPropagation()} style={{ pointerEvents: 'auto', position: 'absolute', top: '5%', left: '5%', margin: 0 }}>
        {/* ── Top Header Bar ── */}
        <div className="af-inspector-header" style={{ cursor: 'move' }}>
          <div className="af-inspector-node-info">
            <div
              className="af-inspector-icon"
              style={{ background: `${color || '#6366f1'}25`, color: color || '#6366f1', borderColor: `${color || '#6366f1'}50` }}
            >
              {renderNodeIcon(nodeType, label, 18)}
            </div>
            <div>
              <div className="af-inspector-title-row">
                <h2 className="af-inspector-title">{label}</h2>
                <span className="af-badge af-badge--type">{nodeType?.replace(/_/g, ' ')}</span>
                {status && (
                  <span className={`af-badge af-badge--status af-badge--${status}`}>
                    {status === 'completed' && 'Completed'}
                    {status === 'running' && 'Running...'}
                    {status === 'failed' && 'Failed'}
                    {status === 'skipped' && 'Skipped'}
                  </span>
                )}
              </div>
              <div className="af-inspector-node-id">
                Node ID: {node.id} • Step {nodeIndex + 1} of {nodes.length}
              </div>
            </div>
          </div>

          {/* Metrics bar */}
          <div className="af-inspector-metrics">
            {metrics?.latency_ms !== undefined && (
              <div className="af-metric-pill" title="Execution duration">
                Duration: {metrics.latency_ms.toLocaleString()} ms
              </div>
            )}
            {metrics?.tokens !== undefined && metrics.tokens > 0 && (
              <div className="af-metric-pill" title="Tokens consumed">
                Tokens: {metrics.tokens.toLocaleString()}
              </div>
            )}
            {metrics?.cost_usd !== undefined && metrics.cost_usd > 0 && (
              <div className="af-metric-pill" title="Estimated cost">
                Cost: ${metrics.cost_usd.toFixed(4)}
              </div>
            )}
            <button className="af-close-btn" onClick={closeNodeInspector} title="Close (Esc)">
              <IconClose size={13} />
            </button>
          </div>
        </div>

        {/* ── Navigation Tabs ── */}
        <div className="af-inspector-nav">
          <div className="af-inspector-tabs">
            <button
              className={`af-tab ${activeTab === 'output' ? 'af-tab--active' : ''}`}
              onClick={() => setActiveTab('output')}
            >
              OUTPUT
              {output && <span className="af-tab__dot" />}
            </button>
            <button
              className={`af-tab ${activeTab === 'input' ? 'af-tab--active' : ''}`}
              onClick={() => setActiveTab('input')}
            >
              INPUT
              {input && <span className="af-tab__dot" />}
            </button>
            <button
              className={`af-tab ${activeTab === 'config' ? 'af-tab--active' : ''}`}
              onClick={() => setActiveTab('config')}
            >
              CONFIG
            </button>
          </div>

          {/* View mode toggle + copy button */}
          <div className="af-inspector-actions">
            {activeTab !== 'config' && (
              <div className="af-view-toggle">
                <button
                  className={`af-view-btn ${viewMode === 'table' ? 'af-view-btn--active' : ''}`}
                  onClick={() => setViewMode('table')}
                  title="Table view"
                >
                  Table
                </button>
                <button
                  className={`af-view-btn ${viewMode === 'json' ? 'af-view-btn--active' : ''}`}
                  onClick={() => setViewMode('json')}
                  title="JSON view"
                >
                  JSON
                </button>
              </div>
            )}
            <button
              className="af-copy-btn"
              onClick={() => handleCopy(currentPayload || {})}
              title="Copy to clipboard"
            >
              {copied ? (
                <>
                  <IconCheck size={12} style={{ marginRight: 4 }} /> Copied
                </>
              ) : (
                <>
                  <IconCopy size={12} style={{ marginRight: 4 }} /> Copy
                </>
              )}
            </button>
          </div>
        </div>

        {/* ── Body Content ── */}
        <div className="af-inspector-body">
          {/* Error Banner */}
          {error && activeTab === 'output' && (
            <div className="af-error-banner">
              <span style={{ fontWeight: 700, fontSize: 14 }}>!</span>
              <div>
                <div style={{ fontWeight: 600 }}>Execution Error</div>
                <div style={{ fontSize: 12, opacity: 0.9 }}>{error}</div>
              </div>
            </div>
          )}

          {/* Running State */}
          {status === 'running' && (
            <div className="empty-state" style={{ padding: '60px 0' }}>
              <div className="spinner" style={{ width: 36, height: 36, margin: '0 auto 16px' }} />
              <div className="empty-state__text" style={{ fontSize: 15, fontWeight: 600 }}>
                Node is actively executing...
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>
                Awaiting completion from LLM / tool pipeline
              </div>
            </div>
          )}

          {/* Empty Payload */}
          {!currentPayload && status !== 'running' && (
            <div className="empty-state" style={{ padding: '60px 0' }}>
              <div className="empty-state__icon"><IconFileText size={32} /></div>
              <div className="empty-state__text" style={{ fontSize: 14 }}>
                No {activeTab} data available
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>
                {status ? 'This step did not produce output' : 'Execute the workflow to see runtime output'}
              </div>
            </div>
          )}

          {/* Table / Object View */}
          {currentPayload && status !== 'running' && viewMode === 'table' && activeTab !== 'config' && (
            typeof currentPayload === 'string' ? (
              <div className="af-text-viewer">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 11, color: 'var(--text-muted)' }}>
                  <span>Raw Text Output</span>
                  <span>{currentPayload.length} chars • {currentPayload.split(/\s+/).filter(Boolean).length} words</span>
                </div>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit', lineHeight: 1.6 }}>
                  {currentPayload}
                </pre>
              </div>
            ) : Array.isArray(currentPayload) ? (
              <div className="af-table-container">
                <table className="af-data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '12%' }}>#</th>
                      <th>ITEM</th>
                    </tr>
                  </thead>
                  <tbody>
                    {currentPayload.map((item, idx) => (
                      <tr key={idx}>
                        <td className="af-table-key">[{idx}]</td>
                        <td className="af-table-val">
                          <RenderTableCell value={item} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="af-table-container">
                <table className="af-data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '28%' }}>KEY</th>
                      <th>VALUE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(currentPayload).map(([key, val]) => (
                      <tr key={key}>
                        <td className="af-table-key">{key}</td>
                        <td className="af-table-val">
                          <RenderTableCell value={val} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}

          {/* JSON View */}
          {currentPayload && status !== 'running' && (viewMode === 'json' || activeTab === 'config') && (
            <pre className="af-json-viewer">
              <code>{typeof currentPayload === 'string' ? currentPayload : JSON.stringify(currentPayload, null, 2)}</code>
            </pre>
          )}
        </div>

        {/* ── Footer Navigation Bar ── */}
        <div className="af-inspector-footer">
          <button
            className="btn btn--ghost btn--sm"
            disabled={!prevNode}
            onClick={() => prevNode && openNodeInspector(prevNode.id)}
            title={prevNode ? `Previous: ${prevNode.data.label}` : 'No previous step'}
          >
            ← Previous Step
          </button>

          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Use ← → keys or buttons to step through execution
          </span>

          <button
            className="btn btn--ghost btn--sm"
            disabled={!nextNode}
            onClick={() => nextNode && openNodeInspector(nextNode.id)}
            title={nextNode ? `Next: ${nextNode.data.label}` : 'No next step'}
          >
            Next Step →
          </button>
        </div>
        </div>
      </Draggable>
    </div>
  );
}

function RenderTableCell({ value }) {
  if (value === null) return <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>null</span>;
  if (value === undefined) return <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>undefined</span>;
  if (typeof value === 'boolean') {
    return (
      <span className={`af-badge ${value ? 'af-badge--status-completed' : 'af-badge--status-failed'}`}>
        {value ? 'true' : 'false'}
      </span>
    );
  }
  if (typeof value === 'number') {
    return <span style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>{value}</span>;
  }
  if (typeof value === 'string') {
    if (value.startsWith('http://') || value.startsWith('https://')) {
      return (
        <a href={value} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-sky)', textDecoration: 'underline' }}>
          {value}
        </a>
      );
    }
    return <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{value}</span>;
  }
  if (Array.isArray(value)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {value.map((item, idx) => (
          <div key={idx} className="af-array-item">
            {typeof item === 'object' ? (
              <pre style={{ margin: 0, fontSize: 11 }}>{JSON.stringify(item, null, 2)}</pre>
            ) : (
              String(item)
            )}
          </div>
        ))}
      </div>
    );
  }
  if (typeof value === 'object') {
    return (
      <pre style={{ margin: 0, fontSize: 11, background: 'rgba(0,0,0,0.3)', padding: 6, borderRadius: 4 }}>
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return String(value);
}
