/**
 * RunModal — custom execution launcher.
 * Lets users review or modify trigger inputs (e.g. lead name, company, topic)
 * or supply raw JSON before executing the DAG.
 */
import { useState, useEffect } from 'react';
import useStore from '../store';
import { IconPlay, IconClose } from './Icons';

export default function RunModal() {
  const runModalOpen = useStore((s) => s.runModalOpen);
  const setRunModalOpen = useStore((s) => s.setRunModalOpen);
  const triggerData = useStore((s) => s.triggerData);
  const setTriggerData = useStore((s) => s.setTriggerData);
  const triggerRun = useStore((s) => s.triggerRun);
  const nodes = useStore((s) => s.nodes);

  const [mode, setMode] = useState('form'); // 'form' | 'json'
  const [jsonText, setJsonText] = useState(JSON.stringify(triggerData, null, 2));
  const [jsonError, setJsonError] = useState(null);
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');

  // Sync jsonText whenever modal is opened
  useEffect(() => {
    if (runModalOpen) {
      setJsonText(JSON.stringify(triggerData, null, 2));
      setJsonError(null);
    }
  }, [runModalOpen, triggerData]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setRunModalOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [setRunModalOpen]);

  if (!runModalOpen) return null;

  const handleModeSwitch = (newMode) => {
    if (newMode === 'form' && mode === 'json') {
      try {
        const parsed = JSON.parse(jsonText);
        setTriggerData(parsed);
        setJsonError(null);
      } catch (err) {
        setJsonError(`Cannot switch to Form view: ${err.message}`);
        return;
      }
    } else if (newMode === 'json' && mode === 'form') {
      setJsonText(JSON.stringify(triggerData, null, 2));
      setJsonError(null);
    }
    setMode(newMode);
  };

  const handleLaunch = () => {
    let payload = triggerData;
    if (mode === 'json') {
      try {
        payload = JSON.parse(jsonText);
      } catch (err) {
        setJsonError(`Invalid JSON: ${err.message}`);
        return;
      }
    }
    setTriggerData(payload);
    setRunModalOpen(false);
    triggerRun(payload);
  };

  const handleFormChange = (key, value) => {
    const updated = { ...triggerData, [key]: value };
    setTriggerData(updated);
    setJsonText(JSON.stringify(updated, null, 2));
  };

  const handleAddField = () => {
    if (!newKey.trim()) return;
    const updated = { ...triggerData, [newKey.trim()]: newValue };
    setTriggerData(updated);
    setJsonText(JSON.stringify(updated, null, 2));
    setNewKey('');
    setNewValue('');
  };

  const handleRemoveField = (key) => {
    const updated = { ...triggerData };
    delete updated[key];
    setTriggerData(updated);
    setJsonText(JSON.stringify(updated, null, 2));
  };

  const handleClearAll = () => {
    setTriggerData({});
    setJsonText('{}');
  };

  const setPreset = (preset) => {
    setTriggerData(preset);
    setJsonText(JSON.stringify(preset, null, 2));
    setJsonError(null);
  };

  const triggerNode = nodes.find((n) => n.data?.nodeType?.startsWith('trigger_'));

  return (
    <div className="af-modal-backdrop" onClick={() => setRunModalOpen(false)}>
      <div className="af-run-modal" onClick={(e) => e.stopPropagation()}>
        <div className="af-modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <IconPlay size={16} />
              </div>
              <h2 className="af-modal-title">Launch Workflow Execution</h2>
            </div>
            <p className="af-modal-subtitle">
              Supply input variables to seed the trigger node ({triggerNode?.data?.label || 'Trigger'}).
            </p>
          </div>
          <button className="af-close-btn" onClick={() => setRunModalOpen(false)}>
            <IconClose size={13} />
          </button>
        </div>

        {/* Quick Presets */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>
            QUICK PRESETS:
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              className="af-preset-btn"
              onClick={() =>
                setPreset({
                  lead_name: 'Sarah Chen',
                  company: 'Acme Corp',
                  topic: 'AI Workflow Orchestration & Dataform Integration',
                  goal: 'Schedule architecture consultation and validate ICP fit',
                })
              }
            >
              Sarah Chen (B2B Lead)
            </button>
            <button
              className="af-preset-btn"
              onClick={() =>
                setPreset({
                  pr_number: 142,
                  repo: 'agentflow-studio',
                  author: 'alex-engineer',
                  commit_hash: '8f9a2b1',
                  diff_summary: 'Add guardrail node, fix async SSE cancellation, and overhaul dark theme',
                })
              }
            >
              GitHub PR #142 Code Review
            </button>
            <button
              className="af-preset-btn"
              onClick={() =>
                setPreset({
                  document_title: 'Q3 Financial Health Report.pdf',
                  entity: 'Apex Global Financials',
                  fiscal_period: 'Q3 2026',
                  metrics_focus: ['revenue_growth', 'ebitda_margin', 'free_cash_flow', 'operating_expenses'],
                })
              }
            >
              Financial Document OCR & KPI
            </button>
            <button
              className="af-preset-btn"
              onClick={() =>
                setPreset({
                  topic: 'Next-Generation Autonomous AI Agents in Enterprise Systems',
                  category: 'Research Briefing',
                  audience: 'VP of Engineering',
                })
              }
            >
              Tech Intelligence Briefing
            </button>
          </div>
        </div>

        {/* Mode Toggle */}
        <div className="tab-bar" style={{ marginBottom: 16 }}>
          <button
            className={`tab-bar__tab ${mode === 'form' ? 'tab-bar__tab--active' : ''}`}
            onClick={() => handleModeSwitch('form')}
          >
            Form Fields
          </button>
          <button
            className={`tab-bar__tab ${mode === 'json' ? 'tab-bar__tab--active' : ''}`}
            onClick={() => handleModeSwitch('json')}
          >
            {'{ }'} Raw JSON Payload
          </button>
        </div>

        {mode === 'form' ? (
          <div className="af-form-fields">
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
              {Object.keys(triggerData).length > 0 && (
                <button
                  type="button"
                  onClick={handleClearAll}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    fontSize: 11,
                    cursor: 'pointer',
                    textDecoration: 'underline',
                  }}
                >
                  Clear All Fields
                </button>
              )}
            </div>

            {Object.keys(triggerData).length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 12, textAlign: 'center' }}>
                No trigger fields configured. Add custom fields below or switch to Raw JSON.
              </div>
            ) : (
              Object.entries(triggerData).map(([k, v]) => (
                <div key={k} className="form-group" style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <label className="form-label" style={{ margin: 0, textTransform: 'capitalize' }}>
                      {k.replace(/_/g, ' ')}:
                    </label>
                    <button
                      type="button"
                      onClick={() => handleRemoveField(k)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        fontSize: 14,
                        padding: '0 4px',
                      }}
                      title="Remove parameter"
                    >
                      ×
                    </button>
                  </div>
                  <input
                    id={`run-param-${k}`}
                    name={k}
                    className="form-input"
                    value={typeof v === 'object' ? JSON.stringify(v) : v}
                    onChange={(e) => handleFormChange(k, e.target.value)}
                  />
                </div>
              ))
            )}

            {/* Add Custom Parameter */}
            <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>
                + ADD CUSTOM PARAMETER:
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  placeholder="field_name"
                  className="form-input"
                  style={{ flex: 1 }}
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddField()}
                />
                <input
                  placeholder="value"
                  className="form-input"
                  style={{ flex: 1.5 }}
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddField()}
                />
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={handleAddField}
                  style={{ whiteSpace: 'nowrap', fontSize: 12 }}
                >
                  Add
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="form-group">
            <textarea
              id="run-trigger-json"
              name="trigger_json"
              className="form-textarea af-code-font"
              value={jsonText}
              onChange={(e) => {
                setJsonText(e.target.value);
                setJsonError(null);
              }}
              rows={8}
              placeholder="Paste JSON trigger data..."
            />
            {jsonError && <div style={{ color: 'var(--status-failed)', fontSize: 12, marginTop: 4 }}>{jsonError}</div>}
          </div>
        )}

        <div className="af-modal-footer">
          <button className="btn btn--ghost" onClick={() => setRunModalOpen(false)}>
            Cancel
          </button>
          <button className="btn btn--emerald" onClick={handleLaunch} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <IconPlay size={13} />
            <span>Run Workflow Now</span>
          </button>
        </div>
      </div>
    </div>
  );
}
