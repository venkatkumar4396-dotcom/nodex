/**
 * AgentNode — rich, modern canvas node card.
 *
 * Features:
 *   - Category accent header bar
 *   - Ambient glowing icon
 *   - Live execution status (pulsing Running spinner, Done, Error, Skipped)
 *   - Tool badges (shows assigned tools like web_search)
 *   - Quick-action toolbar on hover (Inspect, Config, Duplicate, Delete)
 *   - High-contrast IN/OUT ports with magnetic connection feel
 *   - Compact mode support
 */
import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import useStore from '../store';
import { renderNodeIcon, IconCheck, IconSearch, IconSettings, IconCopy, IconTrash, IconPlay } from './Icons';

function AgentNode({ id, data, selected }) {
  const { label, color, icon, nodeType, status, config, metrics } = data;
  const openNodeInspector = useStore((s) => s.openNodeInspector);
  const selectNode = useStore((s) => s.selectNode);
  const setActivePanel = useStore((s) => s.setActivePanel);
  const duplicateNode = useStore((s) => s.duplicateNode);
  const deleteNode = useStore((s) => s.deleteNode);
  const retryNode = useStore((s) => s.retryNode);
  const compactMode = useStore((s) => s.compactMode);

  const tools = config?.tools || [];
  const isRunning = status === 'running';
  const canRetry = status === 'failed' || status === 'timed_out' || status === 'skipped';

  const handleConfigClick = (e) => {
    e.stopPropagation();
    selectNode(id);
    setActivePanel('config');
  };

  const handleInspectClick = (e) => {
    e.stopPropagation();
    openNodeInspector(id);
  };

  const handleDuplicateClick = (e) => {
    e.stopPropagation();
    duplicateNode(id);
  };

  const handleDeleteClick = (e) => {
    e.stopPropagation();
    deleteNode(id);
  };

  const handleRetryClick = (e) => {
    e.stopPropagation();
    if (retryNode) retryNode(id);
  };

  return (
    <div
      className={`agent-node ${selected ? 'selected' : ''} ${compactMode ? 'agent-node--compact' : ''} ${isRunning ? 'agent-node--running' : ''}`}
      onDoubleClick={handleInspectClick}
      style={{ '--node-accent': color || '#6366f1' }}
    >
      {/* ── Top Color Accent Band ── */}
      <div className="agent-node__accent-bar" style={{ background: color || '#6366f1' }} />

      {/* ── Hover Action Bar ── */}
      <div className="agent-node__quick-actions">
        {canRetry && (
          <button className="af-node-action-btn af-node-action-btn--primary" onClick={handleRetryClick} title="Retry Node Re-execution">
            <IconPlay size={11} />
          </button>
        )}
        <button className="af-node-action-btn" onClick={handleInspectClick} title="Inspect Data (Double-click)">
          <IconSearch size={12} />
        </button>
        <button className="af-node-action-btn" onClick={handleConfigClick} title="Configure Node">
          <IconSettings size={12} />
        </button>
        <button className="af-node-action-btn" onClick={handleDuplicateClick} title="Duplicate Node">
          <IconCopy size={12} />
        </button>
        <button className="af-node-action-btn af-node-action-btn--danger" onClick={handleDeleteClick} title="Delete Node">
          <IconTrash size={12} />
        </button>
      </div>

      {/* ── Input Handle (Left) ── */}
      <Handle
        type="target"
        position={Position.Left}
        id="left"
        className="node-handle node-handle--in"
        title="Input: Connect from previous node"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="default"
        className="node-handle node-handle--in"
        style={{ opacity: 0, pointerEvents: 'none' }}
      />
      <span className="node-handle-badge node-handle-badge--in">IN</span>

      {/* ── Card Content ── */}
      <div className="agent-node__content">
        <div
          className="agent-node__icon-box"
          style={{ background: `${color || '#6366f1'}20`, color: color || '#6366f1', borderColor: `${color || '#6366f1'}40` }}
        >
          {renderNodeIcon(nodeType, label, 16)}
        </div>

        <div className="agent-node__info">
          <div className="agent-node__title" title={label}>
            {label}
          </div>
          {!compactMode && (
            <div className="agent-node__subtitle">
              {nodeType?.replace(/_/g, ' ')}
            </div>
          )}
        </div>

        {/* Status Indicator */}
        {status && (
          <div
            className={`agent-node__status-pill agent-node__status-pill--${status}`}
            onClick={handleInspectClick}
            title="Click to inspect step output"
          >
            {status === 'running' && (
              <>
                <span className="spinner-dots" />
                {!compactMode && 'Running...'}
              </>
            )}
            {(status === 'completed' || status === 'success') && (!compactMode ? 'Done' : 'Done')}
            {status === 'failed' && (!compactMode ? 'Error' : 'Error')}
            {status === 'timed_out' && (!compactMode ? 'Timed Out' : 'Timeout')}
            {status === 'skipped' && (!compactMode ? 'Skipped' : 'Skipped')}
          </div>
        )}
      </div>

      {/* ── Tools / Metadata Chips (Non-compact) ── */}
      {!compactMode && tools.length > 0 && (
        <div className="agent-node__tools-row">
          {tools.map((t) => (
            <span key={t} className="agent-node__tool-chip" title={`Tool: ${t}`}>
              {t.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}

      {/* ── Simulated Result Warning Badge ── */}
      {Boolean(
        data.output &&
          (JSON.stringify(data.output).includes('[SIMULATED RESULT]') ||
            JSON.stringify(data.output).includes('SIMULATED RESULT') ||
            data.output?._simulated)
      ) && (
        <div style={{ marginTop: 6, display: 'flex' }}>
          <span
            style={{
              background: '#f59e0b25',
              color: '#f59e0b',
              border: '1px solid #f59e0b60',
              borderRadius: 4,
              padding: '2px 6px',
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.04em',
            }}
          >
            ⚠️ SIMULATED RESULT
          </span>
        </div>
      )}

      {/* ── Metrics Summary (when finished) ── */}
      {!compactMode && status === 'completed' && metrics?.latency_ms && (
        <div className="agent-node__metrics-row">
          <span>{metrics.latency_ms}ms</span>
          {metrics.tokens > 0 && <span>{metrics.tokens} tok</span>}
        </div>
      )}

      {/* ── Output Handle (Right) ── */}
      <span className="node-handle-badge node-handle-badge--out">OUT</span>
      {/* n8n-style Item Count Badge on Output (Photo 2) */}
      {status === 'completed' && data.output && (
        <div
          className="af-node-output-badge"
          onClick={(e) => {
            e.stopPropagation();
            useStore.getState().setSelectedExecutionNodeId(id);
            useStore.getState().setExecutionDockOpen(true);
          }}
          title="Click to inspect output in execution dock"
        >
          <span className="af-node-output-badge-check">
            <IconCheck size={10} />
          </span>
          <span>
            {Array.isArray(data.output)
              ? `${data.output.length} item${data.output.length === 1 ? '' : 's'}`
              : typeof data.output === 'object' && Object.values(data.output).some((v) => Array.isArray(v) && v.length > 1)
              ? `${Object.values(data.output).find((v) => Array.isArray(v) && v.length > 1).length} items total`
              : '1 item'}
          </span>
        </div>
      )}
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        className="node-handle node-handle--out"
        title="Output: Drag arrow to connect to next node"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="default"
        className="node-handle node-handle--out"
        style={{ opacity: 0, pointerEvents: 'none' }}
      />
    </div>
  );
}

export default memo(AgentNode);
