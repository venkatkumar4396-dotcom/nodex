/**
 * PublishWorkflowModal — Marketplace Publisher (#6) & Automated Dual Quality Gate
 * Executes Security Red-Team (#7) and Evaluator (#4) before sanitizing secrets and publishing.
 */
import { useState, useEffect } from 'react';
import useStore from '../store';
import { IconShield, IconClose, IconCheck, IconAlertTriangle, IconSparkles, IconLayers } from './Icons';

export default function PublishWorkflowModal() {
  const isOpen = useStore((s) => s.publishModalOpen);
  const setIsOpen = useStore((s) => s.setPublishModalOpen);
  const isPublishing = useStore((s) => s.publishGateLoading);
  const gateResult = useStore((s) => s.publishGateResult);
  const gateStep = useStore((s) => s.publishGateStep);
  const runPublishToMarketplace = useStore((s) => s.runPublishToMarketplace);
  const workflowName = useStore((s) => s.workflowName);
  const nodes = useStore((s) => s.nodes);

  const [notes, setNotes] = useState('');

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isPublishing) setIsOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPublishing, setIsOpen]);

  if (!isOpen) return null;

  const handlePublish = async () => {
    await runPublishToMarketplace({ notes });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="flex flex-col w-full max-w-3xl max-h-[92vh] bg-surface-900 border border-surface-700/80 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-700/60 bg-gradient-to-r from-purple-900/30 via-surface-850 to-surface-850">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400 font-bold shadow-sm">
              <IconShield size={20} className="text-purple-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white">Publish to Marketplace</h2>
                <span className="px-2 py-0.5 text-xs font-semibold bg-purple-500/20 text-purple-300 rounded-full border border-purple-500/30">
                  Dual-Gate Verification
                </span>
              </div>
              <p className="text-xs text-surface-400">
                Automated Quality Gate: Red-Team (#7) & Evaluator (#4) must pass before Publisher (#6) lists your workflow.
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            disabled={isPublishing}
            className="p-1.5 text-surface-400 hover:text-white rounded-lg hover:bg-surface-700/50 transition-colors"
          >
            <IconClose size={13} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Workflow Snapshot Info */}
          <div className="flex items-center justify-between p-4 rounded-xl bg-surface-800/80 border border-surface-700">
            <div>
              <div className="text-xs text-surface-400">Target Workflow</div>
              <div className="text-sm font-bold text-white mt-0.5">{workflowName || 'Current Workflow'}</div>
              <div className="text-xs text-surface-400 mt-1">
                Nodes count: <span className="text-purple-400 font-mono">{nodes.length}</span>
              </div>
            </div>
            <div className="text-right">
              <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-surface-700/60 text-surface-300 border border-surface-600">
                Pre-Publish Review
              </span>
            </div>
          </div>

          {/* Quality Gate Visual Pipeline */}
          <div className="p-4 rounded-xl bg-surface-850 border border-surface-700 space-y-3">
            <div className="text-xs font-bold text-surface-300 uppercase tracking-wider">
              Automated 3-Stage Quality Gate
            </div>
            <div className="grid grid-cols-3 gap-3">
              {/* Gate 1 */}
              <div
                className={`p-3 rounded-xl border text-center transition-all ${
                  gateResult?.red_team_output
                    ? gateResult.red_team_output.safe_to_publish
                      ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400'
                      : 'bg-rose-500/10 border-rose-500/40 text-rose-400'
                    : isPublishing
                    ? 'bg-purple-500/10 border-purple-500/40 text-purple-400 animate-pulse'
                    : 'bg-surface-800 border-surface-700 text-surface-400'
                }`}
              >
                <div className="flex justify-center mb-1">
                  {gateResult?.red_team_output?.safe_to_publish ? (
                    <IconCheck size={18} />
                  ) : gateResult?.red_team_output ? (
                    <IconClose size={18} />
                  ) : (
                    <IconShield size={18} />
                  )}
                </div>
                <div className="text-xs font-bold">1. Security Red-Team</div>
                <div className="text-[10px] mt-0.5 opacity-80">
                  {gateResult?.red_team_output ? `Score: ${gateResult.red_team_output.security_score}/100` : 'Injection & Agency Scan'}
                </div>
              </div>

              {/* Gate 2 */}
              <div
                className={`p-3 rounded-xl border text-center transition-all ${
                  gateResult?.evaluator_output
                    ? gateResult.evaluator_output.verdict !== 'block'
                      ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400'
                      : 'bg-rose-500/10 border-rose-500/40 text-rose-400'
                    : isPublishing
                    ? 'bg-purple-500/10 border-purple-500/40 text-purple-400 animate-pulse'
                    : 'bg-surface-800 border-surface-700 text-surface-400'
                }`}
              >
                <div className="flex justify-center mb-1">
                  {gateResult?.evaluator_output?.verdict !== 'block' && gateResult?.evaluator_output ? (
                    <IconCheck size={18} />
                  ) : gateResult?.evaluator_output ? (
                    <IconClose size={18} />
                  ) : (
                    <IconSparkles size={18} />
                  )}
                </div>
                <div className="text-xs font-bold">2. QA Evaluator</div>
                <div className="text-[10px] mt-0.5 opacity-80">
                  {gateResult?.evaluator_output ? `Score: ${gateResult.evaluator_output.overall_score}/5` : '8 Tests & Rubric'}
                </div>
              </div>

              {/* Gate 3 */}
              <div
                className={`p-3 rounded-xl border text-center transition-all ${
                  gateResult?.passed
                    ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400'
                    : gateResult && !gateResult.passed
                    ? 'bg-surface-800 border-surface-700 text-surface-500 opacity-60'
                    : isPublishing
                    ? 'bg-purple-500/10 border-purple-500/40 text-purple-400 animate-pulse'
                    : 'bg-surface-800 border-surface-700 text-surface-400'
                }`}
              >
                <div className="flex justify-center mb-1">
                  {gateResult?.passed ? <IconCheck size={18} /> : <IconLayers size={18} />}
                </div>
                <div className="text-xs font-bold">3. Sanitizer & Docs</div>
                <div className="text-[10px] mt-0.5 opacity-80">
                  {gateResult?.passed ? 'Listing Ready' : 'Secret Scrubbing'}
                </div>
              </div>
            </div>
          </div>

          {/* Publisher Notes Input */}
          {!gateResult && (
            <div>
              <label className="block text-xs font-semibold text-surface-300 mb-1">
                Author Notes & Verification Context (Optional)
              </label>
              <textarea
                rows={3}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Describe intended use case, test parameters, or permissions needed..."
                className="w-full px-3.5 py-2 rounded-xl bg-surface-800 border border-surface-700 text-white text-xs focus:outline-none focus:border-purple-500 transition-colors resize-none"
              />
            </div>
          )}

          {/* Gate Result Presentation */}
          {gateResult && (
            <div className="space-y-4">
              {/* Status Banner */}
              <div
                className={`p-4 rounded-xl border flex items-start gap-3 ${
                  gateResult.passed
                    ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                    : 'bg-rose-500/10 border-rose-500/40 text-rose-300'
                }`}
              >
                <div className="mt-0.5">
                  {gateResult.passed ? (
                    <IconShield size={24} className="text-emerald-400" />
                  ) : (
                    <IconAlertTriangle size={24} className="text-rose-400" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-bold text-white">
                    {gateResult.passed ? 'Quality Gate Certified — Published Successfully!' : 'Publication Blocked by Quality Gate'}
                  </div>
                  <ul className="text-xs space-y-1 mt-1 opacity-90 list-disc list-inside">
                    {gateResult.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Red-Team Findings if any */}
              {gateResult.red_team_output?.findings?.length > 0 && (
                <div className="p-4 rounded-xl bg-surface-800/80 border border-surface-700 space-y-2">
                  <div className="text-xs font-bold text-surface-300 uppercase">
                    Security Red-Team Audit Findings ({gateResult.red_team_output.findings.length})
                  </div>
                  <div className="space-y-2">
                    {gateResult.red_team_output.findings.map((f) => (
                      <div key={f.id} className="p-3 rounded-lg bg-surface-900 border border-surface-800 text-xs">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-bold text-white">{f.id}</span>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              f.severity === 'critical'
                                ? 'bg-rose-500/20 text-rose-300'
                                : f.severity === 'high'
                                ? 'bg-orange-500/20 text-orange-300'
                                : 'bg-amber-500/20 text-amber-300'
                            }`}
                          >
                            {f.severity}
                          </span>
                        </div>
                        <p className="text-surface-300 mb-1"><strong>Attack:</strong> {f.attack_example}</p>
                        <p className="text-cyan-400"><strong>Fix:</strong> {f.fix}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Published Listing Card Preview */}
              {gateResult.passed && gateResult.listing_item && (
                <div className="p-4 rounded-xl bg-gradient-to-br from-surface-800 to-surface-850 border border-purple-500/30 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                      Marketplace Listing Card Preview
                    </span>
                    <span className="text-xs font-mono text-emerald-400">ID: {gateResult.listing_item.id}</span>
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-white">{gateResult.listing_item.title}</h3>
                    <p className="text-xs text-purple-300 mt-0.5">{gateResult.listing_item.tagline}</p>
                    <p className="text-xs text-surface-400 mt-2">{gateResult.listing_item.description}</p>
                  </div>
                  <div className="flex flex-wrap gap-2 pt-2 border-t border-surface-700/60 text-xs">
                    <span className="px-2 py-0.5 rounded bg-surface-900 text-surface-300">
                      Cost: {gateResult.listing_item.cost_estimate}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-surface-900 text-emerald-300">
                      Risk: {gateResult.listing_item.risk_level.toUpperCase()}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-surface-900 text-cyan-300">
                      Security: {gateResult.listing_item.security_score}/100
                    </span>
                    <span className="px-2 py-0.5 rounded bg-surface-900 text-amber-300">
                      QA: {gateResult.listing_item.evaluation_score}/5
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-surface-700/60 bg-surface-850/60">
          <div className="text-xs text-surface-400">
            {isPublishing
              ? 'Executing live security red-team and QA evaluation gates...'
              : gateResult?.passed
              ? 'Published to public marketplace!'
              : 'Requires clean security & QA pass.'}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              disabled={isPublishing}
              className="px-4 py-2 rounded-xl text-xs font-medium text-surface-300 hover:text-white hover:bg-surface-800 transition-colors"
            >
              {gateResult?.passed ? 'Done' : 'Cancel'}
            </button>
            {!gateResult?.passed && (
              <button
                type="button"
                onClick={handlePublish}
                disabled={isPublishing || nodes.length === 0}
                className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-bold shadow-md shadow-purple-900/30 flex items-center gap-2 transition-all"
              >
                {isPublishing ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Verifying Dual Gate...</span>
                  </>
                ) : (
                  <>
                    <span>Run Quality Gate & Publish</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
