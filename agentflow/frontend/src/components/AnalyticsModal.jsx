/**
 * AnalyticsModal — Workflow Performance, Token Spend, and Governance Dashboard.
 * Phase 7: Real-time telemetry, agent popularity, success rates, and audit logs.
 */
import { useEffect } from 'react';
import useStore from '../store';
import { IconChart, IconClose, IconCpu, IconRefresh } from './Icons';

export default function AnalyticsModal() {
  const analyticsModalOpen = useStore((s) => s.analyticsModalOpen);
  const setAnalyticsModalOpen = useStore((s) => s.setAnalyticsModalOpen);
  const analyticsData = useStore((s) => s.analyticsData);
  const isLoading = useStore((s) => s.isLoadingAnalytics);
  const fetchAnalytics = useStore((s) => s.fetchAnalytics);

  useEffect(() => {
    if (analyticsModalOpen) {
      fetchAnalytics();
      const handleKeyDown = (e) => {
        if (e.key === 'Escape') setAnalyticsModalOpen(false);
      };
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [analyticsModalOpen, fetchAnalytics, setAnalyticsModalOpen]);

  if (!analyticsModalOpen) return null;

  const data = analyticsData || {
    total_runs: 0,
    completed_runs: 0,
    failed_runs: 0,
    paused_runs: 0,
    cancelled_runs: 0,
    success_rate: 100,
    total_tokens: 0,
    total_cost_usd: 0,
    avg_duration_ms: 0,
    runs_by_status: {},
    top_agents: [],
    recent_runs: [],
  };

  return (
    <div className="modal-backdrop" onClick={() => setAnalyticsModalOpen(false)}>
      <div
        className="modal modal--analytics"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: 880, width: '94%', maxHeight: '90vh', overflowY: 'auto' }}
      >
        {/* Header */}
        <div className="modal__header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <IconChart size={24} style={{ color: 'var(--primary)' }} />
            <div>
              <h3 className="modal__title" style={{ fontSize: 18, fontWeight: 700 }}>
                Workflow Telemetry & Analytics
              </h3>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>
                System-wide agent execution volume, LLM token expenditure, and reliability metrics.
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              className="btn btn--ghost btn--sm"
              onClick={fetchAnalytics}
              disabled={isLoading}
              title="Refresh telemetry data"
            >
              Refresh
            </button>
            <button className="modal__close" onClick={() => setAnalyticsModalOpen(false)}>
              <IconClose size={13} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="modal__body" style={{ padding: '20px 24px' }}>
          {isLoading && !analyticsData ? (
            <div style={{ padding: '60px 0', textAlign: 'center' }}>
              <div className="spinner" style={{ width: 28, height: 28, margin: '0 auto 12px' }} />
              <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>Loading telemetry metrics...</div>
            </div>
          ) : (
            <>
              {/* Top KPI Cards */}
              <div className="analytics-kpi-grid">
                <div className="analytics-kpi-card">
                  <div className="analytics-kpi-label">Total Executions</div>
                  <div className="analytics-kpi-value">{data.total_runs.toLocaleString()}</div>
                  <div className="analytics-kpi-sub">
                    <span style={{ color: 'var(--color-emerald, #10b981)' }}>{data.completed_runs} completed</span> •{' '}
                    <span style={{ color: 'var(--color-rose, #ef4444)' }}>{data.failed_runs} failed</span>
                  </div>
                </div>

                <div className="analytics-kpi-card">
                  <div className="analytics-kpi-label">Success Rate</div>
                  <div
                    className="analytics-kpi-value"
                    style={{
                      color:
                        data.success_rate >= 90
                          ? 'var(--color-emerald, #10b981)'
                          : data.success_rate >= 75
                          ? 'var(--color-amber, #f59e0b)'
                          : 'var(--color-rose, #ef4444)',
                    }}
                  >
                    {data.success_rate}%
                  </div>
                  <div className="analytics-kpi-sub">
                    {data.paused_runs > 0 ? `${data.paused_runs} awaiting approval` : 'Reliable execution DAG'}
                  </div>
                </div>

                <div className="analytics-kpi-card">
                  <div className="analytics-kpi-label">Tokens Consumed</div>
                  <div className="analytics-kpi-value">{data.total_tokens.toLocaleString()}</div>
                  <div className="analytics-kpi-sub">LiteLLM normalized counts</div>
                </div>

                <div className="analytics-kpi-card">
                  <div className="analytics-kpi-label">Cumulative Spend</div>
                  <div className="analytics-kpi-value" style={{ color: 'var(--color-emerald, #10b981)' }}>
                    ${data.total_cost_usd.toFixed(4)}
                  </div>
                  <div className="analytics-kpi-sub">
                    Avg latency: {data.avg_duration_ms > 0 ? `${(data.avg_duration_ms / 1000).toFixed(1)}s` : 'Instant'}
                  </div>
                </div>
              </div>

              {/* Status Breakdown Bar */}
              {data.total_runs > 0 && (
                <div style={{ marginTop: 20, marginBottom: 24 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 6, fontWeight: 600 }}>
                    <span>Execution Distribution</span>
                    <span style={{ color: 'var(--text-secondary)' }}>{data.total_runs} Total Runs</span>
                  </div>
                  <div className="analytics-progress-bar">
                    <div
                      style={{
                        width: `${(data.completed_runs / data.total_runs) * 100}%`,
                        background: '#10b981',
                      }}
                      title={`Completed: ${data.completed_runs}`}
                    />
                    <div
                      style={{
                        width: `${(data.failed_runs / data.total_runs) * 100}%`,
                        background: '#ef4444',
                      }}
                      title={`Failed: ${data.failed_runs}`}
                    />
                    <div
                      style={{
                        width: `${(data.paused_runs / data.total_runs) * 100}%`,
                        background: '#f59e0b',
                      }}
                      title={`Paused / Approval: ${data.paused_runs}`}
                    />
                    <div
                      style={{
                        width: `${(data.cancelled_runs / data.total_runs) * 100}%`,
                        background: '#6b7280',
                      }}
                      title={`Cancelled: ${data.cancelled_runs}`}
                    />
                  </div>
                  <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11, color: 'var(--text-secondary)' }}>
                    <span>Completed ({data.completed_runs})</span>
                    <span>Failed ({data.failed_runs})</span>
                    <span>Awaiting Approval ({data.paused_runs})</span>
                    <span>Cancelled ({data.cancelled_runs})</span>
                  </div>
                </div>
              )}

              {/* Top Agents Usage & Recent Runs 2-Col Layout */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginTop: 16 }}>
                {/* Popular Agent Types */}
                <div className="analytics-section-box">
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <IconCpu size={14} style={{ color: 'var(--primary)' }} /> Top Agent Workloads
                  </div>
                  {data.top_agents && data.top_agents.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {data.top_agents.map((ag, i) => (
                        <div key={i} className="analytics-agent-row">
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span className="af-rank-pill">{i + 1}</span>
                            <span style={{ fontWeight: 600, fontSize: 12 }}>
                              {ag.agent_type?.replace(/_/g, ' ').toUpperCase()}
                            </span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{ag.count} calls</span>
                            <span className="af-badge af-badge--version">{ag.share}%</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '20px 0', textAlign: 'center' }}>
                      Execute workflows to see agent workload statistics.
                    </div>
                  )}
                </div>

                {/* Recent Runs Audit Trail */}
                <div className="analytics-section-box">
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <IconRefresh size={14} style={{ color: 'var(--text-secondary)' }} /> Recent Run History
                  </div>
                  {data.recent_runs && data.recent_runs.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 220, overflowY: 'auto' }}>
                      {data.recent_runs.map((r, i) => (
                        <div key={i} className="analytics-run-row">
                          <div>
                            <span className={`af-status-pill af-status-pill--${r.status}`} style={{ fontSize: 10, padding: '2px 6px' }}>
                              {r.status}
                            </span>
                            <span style={{ fontSize: 11, marginLeft: 8, color: 'var(--text-muted)' }}>
                              {r.created_at ? new Date(r.created_at).toLocaleTimeString() : ''}
                            </span>
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                            {r.total_tokens?.toLocaleString() || 0} tok • ${r.total_cost_usd?.toFixed(4) || '0.0000'}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '20px 0', textAlign: 'center' }}>
                      No run records found in database.
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="modal__footer" style={{ padding: '14px 24px' }}>
          <button className="btn btn--primary" onClick={() => setAnalyticsModalOpen(false)}>
            Close Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
