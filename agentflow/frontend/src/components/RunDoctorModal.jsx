/**
 * RunDoctorModal — Run Doctor (#3)
 * Analyzes failed workflow runs, identifies root-cause node, quotes exact trace evidence,
 * provides plain-English diagnosis, and offers one-click RFC 6902 JSON patch application.
 */
import { useEffect } from 'react';
import useStore from '../store';
import { IconSparkles, IconClose, IconSearch } from './Icons';

export default function RunDoctorModal() {
  const runDoctorModalOpen = useStore((s) => s.runDoctorModalOpen);
  const setRunDoctorModalOpen = useStore((s) => s.setRunDoctorModalOpen);
  const isDoctorLoading = useStore((s) => s.doctorLoading);
  const doctorDiagnosis = useStore((s) => s.doctorDiagnosis);
  const applyDoctorFix = useStore((s) => s.applyDoctorFix);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isDoctorLoading) setRunDoctorModalOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isDoctorLoading, setRunDoctorModalOpen]);

  if (!runDoctorModalOpen) return null;

  const handleApply = async () => {
    if (!doctorDiagnosis?.patch) return;
    await applyDoctorFix(doctorDiagnosis.patch);
  };

  return (
    <div className="af-modal-backdrop" onClick={() => !isDoctorLoading && setRunDoctorModalOpen(false)}>
      <div
        className="af-edge-modal"
        style={{ width: 680, maxWidth: '95vw', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="af-modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <IconSparkles size={20} style={{ color: 'var(--primary)' }} />
              <h2 className="af-modal-title">Run Doctor</h2>
              <span className="af-badge af-badge--completed">Meta-Agent #3</span>
            </div>
            <p className="af-modal-subtitle">
              Automated root-cause diagnosis and non-destructive RFC 6902 patch repair for failed runs.
            </p>
          </div>
          <button
            className="af-close-btn"
            onClick={() => !isDoctorLoading && setRunDoctorModalOpen(false)}
            disabled={isDoctorLoading}
          >
            <IconClose size={13} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
          {isDoctorLoading && (
            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
                <IconSearch size={36} style={{ color: 'var(--primary)' }} />
              </div>
              <h3 style={{ fontSize: 16, color: '#f0f6fc', marginBottom: 8 }}>
                Investigating Execution Trace...
              </h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Isolating root-cause node, classifying error type, and computing minimal patch operations.
              </p>
            </div>
          )}

          {!isDoctorLoading && doctorDiagnosis && (
            <div>
              {/* Status & Category Banner */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: '#161b22',
                  border: '1px solid #30363d',
                  borderRadius: 8,
                  padding: '12px 16px',
                  marginBottom: 16,
                }}
              >
                <div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block' }}>
                    ROOT CAUSE IDENTIFIED
                  </span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#f85149' }}>
                    Node: {doctorDiagnosis.root_cause_node || 'Workflow Orchestration'}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span
                    className="af-badge"
                    style={{ background: '#7f1d1d', color: '#fecaca', textTransform: 'uppercase', fontSize: 10 }}
                  >
                    {doctorDiagnosis.category}
                  </span>
                  <span className="af-badge af-badge--running" style={{ fontSize: 10 }}>
                    Confidence: {(doctorDiagnosis.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Plain English Explanation */}
              <div style={{ marginBottom: 16 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#8b949e', letterSpacing: '0.04em' }}>
                  DIAGNOSIS EXPLANATION:
                </span>
                <p
                  style={{
                    fontSize: 13,
                    color: '#e6edf3',
                    lineHeight: 1.6,
                    margin: '6px 0',
                    background: '#0d1117',
                    padding: '10px 14px',
                    borderRadius: 6,
                    border: '1px solid #21262d',
                  }}
                >
                  {doctorDiagnosis.explanation}
                </p>
              </div>

              {/* Exact Trace Evidence Quote */}
              {doctorDiagnosis.evidence && (
                <div style={{ marginBottom: 16 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#8b949e', letterSpacing: '0.04em' }}>
                    TRACE EVIDENCE QUOTE:
                  </span>
                  <pre
                    style={{
                      fontSize: 11,
                      color: '#f85149',
                      background: '#161b22',
                      padding: '10px 12px',
                      borderRadius: 6,
                      border: '1px solid #30363d',
                      overflowX: 'auto',
                      whiteSpace: 'pre-wrap',
                      marginTop: 6,
                    }}
                  >
                    {doctorDiagnosis.evidence}
                  </pre>
                </div>
              )}

              {/* Proposed JSON Patch Table */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#8b949e', letterSpacing: '0.04em' }}>
                    PROPOSED JSON PATCH ({doctorDiagnosis.patch?.length || 0} OP):
                  </span>
                  {doctorDiagnosis.safe_to_auto_apply && (
                    <span className="af-badge af-badge--completed" style={{ fontSize: 10 }}>
                      Safe to Auto-Apply
                    </span>
                  )}
                </div>

                <div style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 6, overflow: 'hidden' }}>
                  {(doctorDiagnosis.patch || []).map((p, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '8px 12px',
                        borderBottom: idx < doctorDiagnosis.patch.length - 1 ? '1px solid #21262d' : 'none',
                        fontSize: 12,
                        display: 'flex',
                        gap: 10,
                      }}
                    >
                      <span style={{ color: '#58a6ff', fontWeight: 600, minWidth: 60 }}>
                        {p.op.toUpperCase()}
                      </span>
                      <span style={{ color: '#79c0ff', fontFamily: 'monospace' }}>
                        {p.path}
                      </span>
                      <span style={{ color: '#8b949e', flex: 1, textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {typeof p.value === 'object' ? JSON.stringify(p.value) : String(p.value || '')}
                      </span>
                    </div>
                  ))}
                  {(!doctorDiagnosis.patch || doctorDiagnosis.patch.length === 0) && (
                    <div style={{ padding: 12, fontSize: 12, color: '#8b949e', textAlign: 'center' }}>
                      No automated patch needed (manual intervention required).
                    </div>
                  )}
                </div>
              </div>

              {/* Verification Hint */}
              {doctorDiagnosis.how_to_verify && (
                <div style={{ fontSize: 11, color: '#8b949e', marginBottom: 20 }}>
                  <strong>How to verify:</strong> {doctorDiagnosis.how_to_verify}
                </div>
              )}

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingTop: 12, borderTop: '1px solid #21262d' }}>
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => setRunDoctorModalOpen(false)}
                >
                  Dismiss
                </button>
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={handleApply}
                  disabled={!doctorDiagnosis.patch || doctorDiagnosis.patch.length === 0}
                >
                  Apply Fix & Patch Canvas
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
