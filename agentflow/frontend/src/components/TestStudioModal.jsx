/**
 * TestStudioModal — Evaluator (QA) (#4)
 * Generates 8 comprehensive test cases (3 typical, 2 edge, 2 adversarial, 1 failure)
 * and scores workflows across 6 quality dimensions with regression tracking and a verdict.
 */
import { useState, useEffect } from 'react';
import useStore from '../store';
import { IconSparkles, IconClose, IconSearch, IconFolder, IconChart } from './Icons';

export default function TestStudioModal() {
  const testStudioModalOpen = useStore((s) => s.testStudioModalOpen);
  const setTestStudioModalOpen = useStore((s) => s.setTestStudioModalOpen);
  const isEvaluating = useStore((s) => s.evaluatorLoading);
  const evaluatorResult = useStore((s) => s.evaluatorResult);
  const runEvaluator = useStore((s) => s.runEvaluator);
  const nodes = useStore((s) => s.nodes);

  const [activeTab, setActiveTab] = useState('generate');
  const [testCases, setTestCases] = useState([]);

  useEffect(() => {
    if (evaluatorResult?.cases) {
      setTestCases(evaluatorResult.cases);
    }
  }, [evaluatorResult]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isEvaluating) setTestStudioModalOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isEvaluating, setTestStudioModalOpen]);

  if (!testStudioModalOpen) return null;

  const handleGenerate = async () => {
    const res = await runEvaluator({ mode: 'generate' });
    if (res?.cases) {
      setTestCases(res.cases);
      setActiveTab('generate');
    }
  };

  const handleGrade = async () => {
    await runEvaluator({
      mode: 'grade',
      testCases: testCases.length > 0 ? testCases : null,
    });
    setActiveTab('grade');
  };

  const getVerdictStyle = (v) => {
    if (v === 'ship') return { background: '#064e3b', color: '#6ee7b7', border: '1px solid #059669' };
    if (v === 'fix_first') return { background: '#78350f', color: '#fde68a', border: '1px solid #d97706' };
    return { background: '#7f1d1d', color: '#fca5a5', border: '1px solid #dc2626' };
  };

  return (
    <div className="af-modal-backdrop" onClick={() => !isEvaluating && setTestStudioModalOpen(false)}>
      <div
        className="af-edge-modal"
        style={{ width: 840, maxWidth: '95vw', maxHeight: '92vh', display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="af-modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <IconSparkles size={20} style={{ color: 'var(--primary)' }} />
              <h2 className="af-modal-title">Test Studio & QA Evaluator</h2>
              <span className="af-badge af-badge--completed">Meta-Agent #4</span>
            </div>
            <p className="af-modal-subtitle">
              Stress-test workflow quality: generate 8 typical, edge, and adversarial cases, and score output rubrics.
            </p>
          </div>
          <button
            className="af-close-btn"
            onClick={() => !isEvaluating && setTestStudioModalOpen(false)}
            disabled={isEvaluating}
          >
            <IconClose size={13} />
          </button>
        </div>

        {/* Tab Switcher & Action Bar */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 24px',
            borderBottom: '1px solid #21262d',
            background: '#0d1117',
          }}
        >
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              className={`btn btn--sm ${activeTab === 'generate' ? 'btn--primary' : 'btn--ghost'}`}
              onClick={() => setActiveTab('generate')}
            >
              Test Suite ({testCases.length})
            </button>
            <button
              className={`btn btn--sm ${activeTab === 'grade' ? 'btn--primary' : 'btn--ghost'}`}
              onClick={() => setActiveTab('grade')}
            >
              Quality Scorecard & Verdict
            </button>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn btn--ghost btn--sm"
              onClick={handleGenerate}
              disabled={isEvaluating || nodes.length === 0}
            >
              {isEvaluating && activeTab === 'generate' ? 'Generating...' : 'Generate 8 Test Cases'}
            </button>
            <button
              className="btn btn--primary btn--sm"
              onClick={handleGrade}
              disabled={isEvaluating || nodes.length === 0}
            >
              {isEvaluating && activeTab === 'grade' ? 'Scoring...' : 'Run QA Evaluation'}
            </button>
          </div>
        </div>

        {/* Body Content */}
        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
          {isEvaluating && (
            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
                <IconSearch size={36} style={{ color: 'var(--primary)' }} />
              </div>
              <h3 style={{ fontSize: 16, color: '#f0f6fc', marginBottom: 6 }}>
                Evaluator QA Agent Running...
              </h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Synthesizing test boundaries, injecting adversarial cases, and computing rubric metrics.
              </p>
            </div>
          )}

          {/* TAB 1: Test Cases */}
          {!isEvaluating && activeTab === 'generate' && (
            <div>
              {testCases.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                  <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
                    <IconFolder size={32} style={{ color: 'var(--text-muted)' }} />
                  </div>
                  <p>No test cases generated yet. Click "Generate 8 Test Cases" to create typical, edge, adversarial, and failure scenarios.</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {testCases.map((tc, idx) => (
                    <div
                      key={tc.id || idx}
                      style={{
                        background: '#161b22',
                        border: '1px solid #30363d',
                        borderRadius: 8,
                        padding: '12px 16px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <span style={{ fontWeight: 700, fontSize: 13, color: '#58a6ff' }}>
                          Case #{idx + 1}: {tc.id}
                        </span>
                        <span
                          className={`af-badge ${tc.passed || tc.pass ? 'af-badge--completed' : 'af-badge--running'}`}
                          style={{ fontSize: 10 }}
                        >
                          {tc.passed || tc.pass ? 'Ready' : 'Warning'}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: '#e6edf3', marginBottom: 6 }}>
                        <strong>Input:</strong> {typeof tc.input === 'object' ? JSON.stringify(tc.input) : tc.input}
                      </div>
                      <div style={{ fontSize: 12, color: '#8b949e' }}>
                        <strong>Expected Behavior:</strong> {tc.expected_behavior || 'Workflow finishes successfully without errors.'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: Quality Scorecard & Verdict */}
          {!isEvaluating && activeTab === 'grade' && (
            <div>
              {!evaluatorResult ? (
                <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                  <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
                    <IconChart size={32} style={{ color: 'var(--text-muted)' }} />
                  </div>
                  <p>No evaluation report available. Click "Run QA Evaluation" to grade your workflow.</p>
                </div>
              ) : (
                <div>
                  {/* Verdict & Pass Rate Banner */}
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '16px 20px',
                      borderRadius: 10,
                      marginBottom: 20,
                      ...getVerdictStyle(evaluatorResult.verdict),
                    }}
                  >
                    <div>
                      <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                        OVERALL QA VERDICT
                      </span>
                      <h3 style={{ margin: '4px 0 0 0', fontSize: 24, fontWeight: 800 }}>
                        {evaluatorResult.verdict?.toUpperCase()}
                      </h3>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontSize: 12, opacity: 0.9 }}>Pass Rate:</span>
                      <div style={{ fontSize: 22, fontWeight: 800 }}>
                        {(evaluatorResult.pass_rate * 100).toFixed(0)}%
                      </div>
                      <span style={{ fontSize: 11, opacity: 0.8 }}>
                        Score: {evaluatorResult.overall_score?.toFixed(1)} / 5.0
                      </span>
                    </div>
                  </div>

                  {/* Top 3 Fixes */}
                  {evaluatorResult.top_3_fixes?.length > 0 && (
                    <div style={{ marginBottom: 20 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: '#f85149', letterSpacing: '0.04em' }}>
                        RECOMMENDED FIXES TO IMPROVE SCORE:
                      </span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
                        {evaluatorResult.top_3_fixes.map((fix, i) => (
                          <div
                            key={i}
                            style={{
                              background: '#161b22',
                              borderLeft: '3px solid #f85149',
                              padding: '8px 12px',
                              borderRadius: 4,
                              fontSize: 12,
                              color: '#e6edf3',
                            }}
                          >
                            <strong>#{i + 1}:</strong> {fix}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Individual Test Scores */}
                  <div>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#8b949e', letterSpacing: '0.04em' }}>
                      PER-CASE BREAKDOWN:
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                      {(evaluatorResult.cases || []).map((c, i) => (
                        <div
                          key={i}
                          style={{
                            background: '#0d1117',
                            border: '1px solid #30363d',
                            borderRadius: 8,
                            padding: '12px 14px',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                            <span style={{ fontWeight: 600, fontSize: 12, color: '#f0f6fc' }}>
                              Case {c.id}
                            </span>
                            <span
                              className={`af-badge ${c.passed || c.pass ? 'af-badge--completed' : 'af-badge--muted'}`}
                              style={{ fontSize: 10 }}
                            >
                              {c.passed || c.pass ? 'PASS' : 'FAIL'}
                            </span>
                          </div>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, fontSize: 11, color: '#8b949e' }}>
                            <span>Correctness: {c.scores?.correctness ?? 5}/5</span>
                            <span>Completeness: {c.scores?.completeness ?? 5}/5</span>
                            <span>Faithfulness: {c.scores?.faithfulness ?? 5}/5</span>
                            <span>Safety: {c.scores?.safety ?? 5}/5</span>
                            <span>Instruction: {c.scores?.instruction_following ?? 5}/5</span>
                            <span>Format: {c.scores?.format_compliance ?? 5}/5</span>
                          </div>
                          {c.evidence && (
                            <div style={{ marginTop: 6, fontSize: 11, color: '#f85149', background: 'rgba(248,81,73,0.1)', padding: '4px 8px', borderRadius: 4 }}>
                              {c.evidence}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
