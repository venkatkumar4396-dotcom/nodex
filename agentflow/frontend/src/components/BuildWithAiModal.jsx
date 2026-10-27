/**
 * BuildWithAiModal — Workflow Architect (#1)
 * Converts natural-language goals into validated, runnable multi-agent DAGs.
 * Displays the complete Architectural Review Card with summary, assumptions, cost, risks,
 * and one-click Replace or Append canvas options.
 */
import { useState, useEffect } from 'react';
import useStore from '../store';
import { IconSparkles, IconClose, IconLayers } from './Icons';

const PRESET_GOALS = [
  {
    icon: 'sales_outreach',
    title: 'B2B Lead Research & Outreach',
    goal: 'Research company leads using web search, score qualification, draft personalized outreach, and require human approval before sending email.',
  },
  {
    icon: 'security_redteam',
    title: 'PR Review & Security Guardrail',
    goal: 'Analyze git PR diffs for security vulnerabilities, run AI guardrail check, and require manager approval before posting comments.',
  },
  {
    icon: 'synthesizer',
    title: 'Financial Document Intelligence',
    goal: 'Parse financial PDF filings, extract balance sheet metrics, calculate trends with code agent, and compile executive deliverable.',
  },
  {
    icon: 'deep_investigation',
    title: 'Deep Competitor Market Intelligence',
    goal: 'Investigate competitor pricing updates using live web search, synthesize key differences, and post formatted Slack alert.',
  },
  {
    icon: 'trigger_manual',
    title: 'Support Ticket Auto-Triage',
    goal: 'Incoming webhook support ticket triage: classify urgency, route billing tickets to specialist, and auto-reply to FAQs.',
  },
];

export default function BuildWithAiModal() {
  const buildWithAiModalOpen = useStore((s) => s.buildWithAiModalOpen);
  const setBuildWithAiModalOpen = useStore((s) => s.setBuildWithAiModalOpen);
  const architectWorkflow = useStore((s) => s.architectWorkflow);
  const applyArchitectGraph = useStore((s) => s.applyArchitectGraph);
  const isArchitecting = useStore((s) => s.architectLoading);
  const architectResult = useStore((s) => s.architectResult);
  const setArchitectResult = useStore((s) => s.setArchitectResult);

  const [goal, setGoal] = useState('');
  const [constraints, setConstraints] = useState('');

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isArchitecting) setBuildWithAiModalOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isArchitecting, setBuildWithAiModalOpen]);

  if (!buildWithAiModalOpen) return null;

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!goal.trim() || isArchitecting) return;
    await architectWorkflow(goal.trim(), constraints.trim());
  };

  const handleApply = (mode) => {
    if (!architectResult) return;
    applyArchitectGraph(architectResult, mode);
  };

  return (
    <div className="af-modal-backdrop" onClick={() => !isArchitecting && setBuildWithAiModalOpen(false)}>
      <div
        className="af-edge-modal"
        style={{ width: 780, maxWidth: '95vw', maxHeight: '92vh', display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="af-modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <IconSparkles size={20} style={{ color: 'var(--primary)' }} />
              <h2 className="af-modal-title">Workflow Architect</h2>
              <span className="af-badge af-badge--completed">Meta-Agent #1</span>
            </div>
            <p className="af-modal-subtitle">
              Describe your objective in plain English. The Architect designs, validates, and wires a runnable agent DAG.
            </p>
          </div>
          <button
            className="af-close-btn"
            onClick={() => !isArchitecting && setBuildWithAiModalOpen(false)}
            disabled={isArchitecting}
          >
            <IconClose size={13} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
          {/* Quick Preset Ideas */}
          {!architectResult && (
            <div style={{ marginBottom: 16 }}>
              <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--text-muted)' }}>
                PROVEN MULTI-AGENT ARCHITECTURES
              </span>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                {PRESET_GOALS.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="af-condition-pill"
                    style={{ fontSize: 11, padding: '4px 10px' }}
                    onClick={() => setGoal(p.goal)}
                  >
                    {p.icon} {p.title}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Goal Input Form */}
          <form onSubmit={handleSubmit}>
            <div className="form-group" style={{ marginBottom: 14 }}>
              <label className="form-label">What is the workflow goal?</label>
              <textarea
                className="form-textarea"
                rows={3}
                placeholder="E.g., Ingest daily customer feedback, classify sentiment, require human review for churn risk, and auto-reply to positive reviews..."
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                disabled={isArchitecting}
              />
            </div>

            <div className="form-group" style={{ marginBottom: 18 }}>
              <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Specific Constraints (Optional)</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Tools, models, limits</span>
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="E.g., Must use web_search, require approval before sending emails, max 5 nodes"
                value={constraints}
                onChange={(e) => setConstraints(e.target.value)}
                disabled={isArchitecting}
              />
            </div>

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginBottom: 20 }}>
              {architectResult && (
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => setArchitectResult(null)}
                  disabled={isArchitecting}
                >
                  Clear Blueprint
                </button>
              )}
              <button
                type="submit"
                className="btn btn--primary"
                disabled={isArchitecting || !goal.trim()}
              >
                {isArchitecting ? 'Designing Architecture...' : 'Architect Workflow Graph'}
              </button>
            </div>
          </form>

          {/* ── Architectural Review Card ── */}
          {architectResult && (
            <div
              style={{
                background: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: 10,
                padding: '18px 20px',
                marginTop: 10,
              }}
            >
              {/* Card Header & Badge */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <IconLayers size={18} style={{ color: '#58a6ff' }} />
                  <span style={{ fontWeight: 700, fontSize: 14, color: '#f0f6fc' }}>
                    Architectural Blueprint
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <span className="af-badge af-badge--completed">
                    {architectResult.nodes?.length || 0} Nodes
                  </span>
                  <span className="af-badge af-badge--running">
                    {architectResult.edges?.length || 0} Edges
                  </span>
                  <span
                    className="af-badge"
                    style={{
                      background:
                        architectResult.estimated_cost_per_run === 'low'
                          ? '#064e3b'
                          : architectResult.estimated_cost_per_run === 'high'
                          ? '#7f1d1d'
                          : '#78350f',
                      color: '#f9fafb',
                    }}
                  >
                    Est. Cost: {architectResult.estimated_cost_per_run?.toUpperCase() || 'LOW'}
                  </span>
                </div>
              </div>

              {/* Summary */}
              <div style={{ fontSize: 13, color: '#e6edf3', marginBottom: 12, lineHeight: 1.5 }}>
                <strong>Outcome:</strong> {architectResult.summary}
              </div>

              {/* Assumptions */}
              {architectResult.assumptions?.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#8b949e', letterSpacing: '0.04em' }}>
                    KEY ASSUMPTIONS:
                  </span>
                  <ul style={{ margin: '4px 0 0 16px', padding: 0, fontSize: 12, color: '#8b949e' }}>
                    {architectResult.assumptions.map((asm, i) => (
                      <li key={i}>{asm}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Node Sequence Preview */}
              <div style={{ marginBottom: 16 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#8b949e', letterSpacing: '0.04em' }}>
                  NODE EXECUTION TOPOLOGY:
                </span>
                <div
                  style={{
                    display: 'flex',
                    gap: 6,
                    overflowX: 'auto',
                    padding: '8px 0',
                    alignItems: 'center',
                  }}
                >
                  {(architectResult.nodes || []).map((node, i) => (
                    <div key={node.id} style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                      {i > 0 && <span style={{ color: '#484f58', fontSize: 13 }}>→</span>}
                      <span
                        className="af-template-chip"
                        style={{
                          background: '#161b22',
                          border: '1px solid #30363d',
                          color: '#58a6ff',
                          padding: '4px 10px',
                          fontSize: 12,
                        }}
                      >
                        <strong>{node.label || node.id}</strong> ({node.type})
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Risks & Warnings */}
              {architectResult.risks?.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#f85149', letterSpacing: '0.04em' }}>
                    RISKS & STRUCTURAL NOTES:
                  </span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
                    {architectResult.risks.map((r, i) => (
                      <div
                        key={i}
                        style={{
                          fontSize: 11,
                          color: '#f85149',
                          background: 'rgba(248, 81, 73, 0.1)',
                          padding: '4px 8px',
                          borderRadius: 4,
                          borderLeft: '2px solid #f85149',
                        }}
                      >
                        {r}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Buttons: Replace or Append */}
              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingTop: 12, borderTop: '1px solid #21262d' }}>
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => handleApply('append')}
                >
                  Append to Current Canvas
                </button>
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={() => handleApply('replace')}
                >
                  Replace Canvas Graph
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
