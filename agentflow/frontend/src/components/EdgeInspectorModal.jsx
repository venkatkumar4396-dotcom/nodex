/**
 * EdgeInspectorModal — inspector for workflow connection edges.
 *
 * Allows configuring:
 *   - Edge Label
 *   - Condition expressions (e.g. output.score >= 7, output.passed == true)
 *   - Branch Type (Standard, Feedback loop, Default fallback, Error handler)
 *   - Data Mapping (e.g. topic: {{trigger.output.topic}})
 *   - Delete connection
 */
import { useState, useEffect } from 'react';
import useStore from '../store';
import { IconLink, IconClose, IconPlay, IconRefresh, IconFork, IconAlertTriangle } from './Icons';

export default function EdgeInspectorModal() {
  const selectedEdgeId = useStore((s) => s.selectedEdgeId);
  const isEdgeModalOpen = useStore((s) => s.isEdgeModalOpen);
  const closeEdgeModal = useStore((s) => s.closeEdgeModal);
  const edges = useStore((s) => s.edges);
  const nodes = useStore((s) => s.nodes);
  const updateEdgeData = useStore((s) => s.updateEdgeData);
  const deleteEdge = useStore((s) => s.deleteEdge);

  const edge = edges.find((e) => e.id === selectedEdgeId);

  const [label, setLabel] = useState('');
  const [condition, setCondition] = useState('');
  const [branchType, setBranchType] = useState('forward'); // 'forward' | 'feedback' | 'default' | 'error'
  const [maxIterations, setMaxIterations] = useState(3);
  const [dataMapText, setDataMapText] = useState('{}');

  useEffect(() => {
    if (edge) {
      setLabel(edge.data?.label || edge.label || '');
      setCondition(edge.data?.condition || '');
      if (edge.data?.is_feedback) setBranchType('feedback');
      else if (edge.data?.is_default) setBranchType('default');
      else if (edge.data?.is_error_handler) setBranchType('error');
      else setBranchType('forward');

      setMaxIterations(edge.data?.max_iterations || 3);
      setDataMapText(JSON.stringify(edge.data?.data_map || {}, null, 2));
    }
  }, [edge]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isEdgeModalOpen) closeEdgeModal();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isEdgeModalOpen, closeEdgeModal]);

  if (!isEdgeModalOpen || !selectedEdgeId || !edge) return null;

  const sourceNode = nodes.find((n) => n.id === edge.source);
  const targetNode = nodes.find((n) => n.id === edge.target);

  const handleSave = () => {
    let dataMap = {};
    try {
      dataMap = JSON.parse(dataMapText || '{}');
    } catch {
      // Keep empty if invalid
    }

    updateEdgeData(edge.id, {
      label: label.trim(),
      condition: branchType === 'default' ? null : condition.trim() || null,
      is_feedback: branchType === 'feedback',
      is_default: branchType === 'default',
      is_error_handler: branchType === 'error',
      max_iterations: branchType === 'feedback' ? parseInt(maxIterations) || 3 : null,
      data_map: dataMap,
    });
    closeEdgeModal();
  };

  const setConditionPreset = (expr, suggestedLabel) => {
    setCondition(expr);
    if (!label) setLabel(suggestedLabel);
    if (branchType === 'default') setBranchType('forward');
  };

  return (
    <div className="af-modal-backdrop" onClick={closeEdgeModal}>
      <div className="af-edge-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="af-modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <IconLink size={20} style={{ color: 'var(--primary)' }} />
              <h2 className="af-modal-title">Connection Configuration</h2>
            </div>
            <div className="af-edge-flow-info">
              <span className="af-edge-flow-node">{sourceNode?.data?.label || edge.source}</span>
              <span className="af-edge-flow-arrow">→</span>
              <span className="af-edge-flow-node">{targetNode?.data?.label || edge.target}</span>
            </div>
          </div>
          <button className="af-close-btn" onClick={closeEdgeModal}>
            <IconClose size={13} />
          </button>
        </div>

        {/* Branch Type Selector */}
        <div className="form-group" style={{ marginBottom: 18 }}>
          <label className="form-label">Branch & Control Flow Type</label>
          <div className="af-branch-type-grid">
            <button
              className={`af-branch-btn ${branchType === 'forward' ? 'af-branch-btn--active' : ''}`}
              onClick={() => setBranchType('forward')}
            >
              <IconPlay size={16} />
              <div>
                <div style={{ fontWeight: 600 }}>Standard Transition</div>
                <div style={{ fontSize: 11, opacity: 0.7 }}>Execute target if condition passes (or unconditionally)</div>
              </div>
            </button>
            <button
              className={`af-branch-btn ${branchType === 'feedback' ? 'af-branch-btn--active af-branch-btn--amber' : ''}`}
              onClick={() => setBranchType('feedback')}
            >
              <IconRefresh size={16} />
              <div>
                <div style={{ fontWeight: 600 }}>Feedback Loop</div>
                <div style={{ fontSize: 11, opacity: 0.7 }}>Loop back to an earlier step with max iteration limit</div>
              </div>
            </button>
            <button
              className={`af-branch-btn ${branchType === 'default' ? 'af-branch-btn--active af-branch-btn--purple' : ''}`}
              onClick={() => setBranchType('default')}
            >
              <IconFork size={16} />
              <div>
                <div style={{ fontWeight: 600 }}>Default Fallback</div>
                <div style={{ fontSize: 11, opacity: 0.7 }}>Execute only when all other conditions evaluate to false</div>
              </div>
            </button>
            <button
              className={`af-branch-btn ${branchType === 'error' ? 'af-branch-btn--active af-branch-btn--rose' : ''}`}
              onClick={() => setBranchType('error')}
            >
              <IconAlertTriangle size={16} />
              <div>
                <div style={{ fontWeight: 600 }}>Error Handler</div>
                <div style={{ fontSize: 11, opacity: 0.7 }}>Route here if source node throws an unhandled error</div>
              </div>
            </button>
          </div>
        </div>

        {/* Edge Label */}
        <div className="form-group" style={{ marginBottom: 14 }}>
          <label className="form-label">Visual Label on Canvas</label>
          <input
            id="edge-label-input"
            name="edge_label"
            className="form-input"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. Score ≥ 7, Revise Draft, Fallback"
          />
        </div>

        {/* Condition (if not default) */}
        {branchType !== 'default' && (
          <div className="form-group" style={{ marginBottom: 14 }}>
            <label className="form-label">
              Condition Expression <span style={{ opacity: 0.6 }}>(Python / CEL syntax)</span>
            </label>
            <input
              id="edge-condition-input"
              name="edge_condition"
              className="form-input af-code-font"
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              placeholder="e.g. output.score >= 7, output.passed == true, 'urgent' in output.tags"
            />
            {/* Quick condition presets */}
            <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Presets:</span>
              <button
                className="af-condition-pill"
                onClick={() => setConditionPreset('output.score >= 7', 'Qualified (Score ≥ 7)')}
              >
                output.score &gt;= 7
              </button>
              <button
                className="af-condition-pill"
                onClick={() => setConditionPreset('output.passed == True', 'Passed')}
              >
                output.passed == True
              </button>
              <button
                className="af-condition-pill"
                onClick={() => setConditionPreset('not output.passed', 'Revise Draft')}
              >
                not output.passed
              </button>
              <button
                className="af-condition-pill"
                onClick={() => setConditionPreset('output.confidence > 0.8', 'High Confidence')}
              >
                output.confidence &gt; 0.8
              </button>
            </div>
          </div>
        )}

        {/* Feedback Max Iterations */}
        {branchType === 'feedback' && (
          <div className="form-group" style={{ marginBottom: 14 }}>
            <label className="form-label">Max Loop Iterations</label>
            <input
              id="edge-max-iterations-input"
              name="edge_max_iterations"
              className="form-input"
              type="number"
              min={1}
              max={20}
              value={maxIterations}
              onChange={(e) => setMaxIterations(e.target.value)}
            />
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              Prevents infinite cycles; execution proceeds forward once iteration limit is reached.
            </div>
          </div>
        )}

        {/* Data Mapping */}
        <div className="form-group" style={{ marginBottom: 16 }}>
          <label className="form-label">
            Data Map <span style={{ opacity: 0.6 }}>(Target inputs from source output)</span>
          </label>
          <textarea
            id="edge-data-map-textarea"
            name="edge_data_map"
            className="form-textarea af-code-font"
            rows={3}
            value={dataMapText}
            onChange={(e) => setDataMapText(e.target.value)}
            placeholder='{"target_field": "{{source_node.output.field}}"}'
          />
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 20 }}>
          <button
            className="btn btn--danger btn--sm"
            onClick={() => {
              deleteEdge(edge.id);
              closeEdgeModal();
            }}
          >
            Delete Connection
          </button>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn--ghost btn--sm" onClick={closeEdgeModal}>
              Cancel
            </button>
            <button className="btn btn--primary btn--sm" onClick={handleSave}>
              Save Connection
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
