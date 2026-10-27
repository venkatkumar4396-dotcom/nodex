/**
 * HitlInboxModal — Centralized Human-in-the-Loop approval queue.
 *
 * Provides a dedicated review interface where pending pause states
 * across all running workflows wait for human approval or rejection.
 */
import { useEffect, useState } from 'react';
import useStore from '../store';
import { IconLayers, IconClose, IconCheck, IconPause } from './Icons';

export default function HitlInboxModal() {
  const hitlModalOpen = useStore((s) => s.hitlModalOpen);
  const setHitlModalOpen = useStore((s) => s.setHitlModalOpen);
  const pendingApprovals = useStore((s) => s.pendingApprovals);
  const fetchPendingApprovals = useStore((s) => s.fetchPendingApprovals);
  const approvePendingRun = useStore((s) => s.approvePendingRun);
  const rejectPendingRun = useStore((s) => s.rejectPendingRun);

  const [notes, setNotes] = useState({});
  const [processingId, setProcessingId] = useState(null);

  useEffect(() => {
    if (hitlModalOpen) {
      fetchPendingApprovals();
      const interval = setInterval(fetchPendingApprovals, 3000);
      return () => clearInterval(interval);
    }
  }, [hitlModalOpen, fetchPendingApprovals]);

  if (!hitlModalOpen) return null;

  const handleApprove = async (item) => {
    setProcessingId(item.run_id);
    await approvePendingRun(item.run_id, item.node_id, notes[item.run_id] || 'Approved in Review Queue');
    setProcessingId(null);
  };

  const handleReject = async (item) => {
    setProcessingId(item.run_id);
    await rejectPendingRun(item.run_id, item.node_id, notes[item.run_id] || 'Rejected in Review Queue');
    setProcessingId(null);
  };

  return (
    <div className="modal-backdrop" onClick={() => setHitlModalOpen(false)}>
      <div
        className="modal-card"
        style={{ maxWidth: 840, width: '92%', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <IconLayers size={24} style={{ color: 'var(--primary)' }} />
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Human-in-the-Loop (HITL) Inbox</h2>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Centralized review queue for paused agent runs awaiting human authorization.
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className={`af-badge ${pendingApprovals.length > 0 ? 'af-badge--warning' : 'af-badge--muted'}`}>
              {pendingApprovals.length} pending
            </span>
            <button className="btn btn--ghost btn--sm" onClick={() => setHitlModalOpen(false)}>
              <IconClose size={13} />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div style={{ flex: 1, overflowY: 'auto', paddingRight: 4 }}>
          {pendingApprovals.length === 0 ? (
            <div className="empty-state" style={{ minHeight: 280, padding: '40px 0' }}>
              <IconCheck size={40} style={{ color: 'var(--primary)', marginBottom: 12, display: 'inline-block' }} />
              <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
                All clear! No approvals pending
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: 13, maxWidth: 380, margin: '8px auto 0' }}>
                When workflows encounter Human Approval nodes or quality gates, pending execution cards will appear here in real-time.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {pendingApprovals.map((item) => (
                <div
                  key={item.run_id}
                  style={{
                    background: 'rgba(24, 24, 27, 0.75)',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    borderRadius: 10,
                    padding: 16,
                    boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                  }}
                >
                  {/* Item Top Bar */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <IconPause size={16} style={{ color: '#f59e0b' }} />
                        <span style={{ fontSize: 15, fontWeight: 700, color: '#f59e0b' }}>
                          {item.workflow_name}
                        </span>
                        <span className="af-badge af-badge--warning" style={{ fontSize: 11 }}>
                          Node: {item.node_label}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        Paused {item.paused_at ? new Date(item.paused_at).toLocaleTimeString() : 'recently'} • Run ID: {String(item.run_id).slice(0, 8)}...
                      </div>
                    </div>
                  </div>

                  {/* Summary / Message Prompt */}
                  <div
                    style={{
                      background: 'rgba(0, 0, 0, 0.4)',
                      borderRadius: 6,
                      padding: '10px 14px',
                      fontSize: 13,
                      color: 'var(--text-primary)',
                      borderLeft: '3px solid #f59e0b',
                      marginBottom: 12,
                    }}
                  >
                    <strong>Review Objective:</strong> {item.prompt_or_message}
                  </div>

                  {/* Input Payload Preview */}
                  {item.input_snapshot && Object.keys(item.input_snapshot).length > 0 && (
                    <div style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase' }}>
                        Payload Snapshot:
                      </div>
                      <pre
                        style={{
                          background: '#09090b',
                          border: '1px solid rgba(255,255,255,0.08)',
                          borderRadius: 6,
                          padding: 10,
                          fontSize: 12,
                          color: '#e4e4e7',
                          maxHeight: 140,
                          overflowY: 'auto',
                          margin: 0,
                        }}
                      >
                        {JSON.stringify(item.input_snapshot, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Reviewer Notes & Action Buttons */}
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Add reviewer notes or conditions (optional)..."
                      style={{ flex: 1, fontSize: 12, padding: '7px 12px' }}
                      value={notes[item.run_id] || ''}
                      onChange={(e) => setNotes({ ...notes, [item.run_id]: e.target.value })}
                    />
                    <button
                      className="btn btn--ghost btn--danger btn--sm"
                      disabled={processingId === item.run_id}
                      onClick={() => handleReject(item)}
                    >
                      Reject
                    </button>
                    <button
                      className="btn btn--primary btn--sm"
                      style={{ background: '#10b981', border: 'none' }}
                      disabled={processingId === item.run_id}
                      onClick={() => handleApprove(item)}
                    >
                      {processingId === item.run_id ? 'Resuming...' : 'Approve & Resume'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
