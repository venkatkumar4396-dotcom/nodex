/**
 * ApprovalBanner — Human-in-the-Loop review & decision banner.
 * Phase 6: Appears when execution reaches a Human Approval gate and halts for oversight.
 */
import { useState } from 'react';
import useStore from '../store';
import { IconPause, IconShield } from './Icons';

export default function ApprovalBanner() {
  const runStatus = useStore((s) => s.runStatus);
  const pausedApprovalData = useStore((s) => s.pausedApprovalData);
  const approveRun = useStore((s) => s.approveRun);
  const rejectRun = useStore((s) => s.rejectRun);
  const cancelRun = useStore((s) => s.cancelRun);

  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (runStatus !== 'paused' && !pausedApprovalData) return null;

  const handleApprove = async () => {
    setIsSubmitting(true);
    await approveRun(notes);
    setIsSubmitting(false);
  };

  const handleReject = async () => {
    setIsSubmitting(true);
    await rejectRun(notes);
    setIsSubmitting(false);
  };

  const handleCancel = async () => {
    setIsSubmitting(true);
    await cancelRun();
    setIsSubmitting(false);
  };

  const inputPayload = pausedApprovalData?.input || {};
  const promptText = pausedApprovalData?.prompt || 'Review and sign off on node execution before downstream steps proceed.';

  return (
    <div className="af-approval-banner">
      <div className="af-approval-banner__content">
        {/* Header line */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ display: 'flex', alignItems: 'center', color: '#f59e0b' }}>
              <IconPause size={16} />
            </span>
            <span style={{ fontWeight: 700, fontSize: 14, color: '#f59e0b' }}>
              Human Approval Gate Active
            </span>
            <span className="af-badge af-badge--primary" style={{ background: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24', borderColor: '#f59e0b' }}>
              Node: {pausedApprovalData?.node_id || 'human_approval'}
            </span>
          </div>

          <button
            className="btn btn--ghost btn--sm"
            onClick={handleCancel}
            disabled={isSubmitting}
            title="Terminate workflow run"
            style={{ fontSize: 11, color: 'var(--text-muted)' }}
          >
            Cancel Run
          </button>
        </div>

        {/* Prompt description */}
        <p style={{ margin: '0 0 10px 0', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
          {promptText}
        </p>

        {/* Input Data Preview (collapsed snippet) */}
        {Object.keys(inputPayload).length > 0 && (
          <details style={{ marginBottom: 12, background: 'rgba(0,0,0,0.25)', borderRadius: 6, padding: '6px 10px' }}>
            <summary style={{ cursor: 'pointer', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>
              View Payload To Review ({Object.keys(inputPayload).length} keys)
            </summary>
            <pre style={{ margin: '6px 0 0', fontSize: 11, maxHeight: 120, overflowY: 'auto', color: 'var(--text-primary)' }}>
              {JSON.stringify(inputPayload, null, 2)}
            </pre>
          </details>
        )}

        {/* Reviewer Note Input & Action Buttons */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            id="approval-banner-notes-input"
            name="reviewer_notes"
            className="form-input"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Reviewer notes / sign-off comments (optional)..."
            style={{ flex: 1, minWidth: 200, height: 34, fontSize: 12 }}
            disabled={isSubmitting}
          />

          <button
            className="btn btn--emerald btn--sm"
            onClick={handleApprove}
            disabled={isSubmitting}
            style={{ fontWeight: 600, padding: '0 14px', height: 34 }}
          >
            {isSubmitting ? (
              <span className="spinner" style={{ width: 12, height: 12 }} />
            ) : (
              'Approve & Continue'
            )}
          </button>

          <button
            className="btn btn--danger btn--sm"
            onClick={handleReject}
            disabled={isSubmitting}
            style={{ fontWeight: 600, padding: '0 12px', height: 34 }}
          >
            Reject Run
          </button>
        </div>
      </div>
    </div>
  );
}
