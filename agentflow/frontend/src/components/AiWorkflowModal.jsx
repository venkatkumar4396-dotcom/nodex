/**
 * AiWorkflowModal — Natural Language AI Workflow Generator.
 * Phase 7: Automatically designs and provisions complete DAG workflows from user prompts.
 */
import { useState, useEffect } from 'react';
import useStore from '../store';
import { IconSparkles, IconClose } from './Icons';

const PRESET_PROMPTS = [
  {
    icon: 'security_redteam',
    title: 'Human Review & Approval Gate',
    prompt: 'Create a customer discount and credit request approval pipeline with research analysis, human manager sign-off gate, and executive email notification.',
  },
  {
    icon: 'rag',
    title: 'RAG Knowledge Retrieval & QA',
    prompt: 'Build a RAG pipeline that retrieves relevant passages from knowledge base docs, synthesizes answers, and runs a hallucination quality audit.',
  },
  {
    icon: 'supervisor',
    title: 'Autonomous Supervisor Team',
    prompt: 'Supervisor multi-agent team that breaks down complex market expansion objectives into parallel research and code tasks, then synthesizes a master report.',
  },
  {
    icon: 'code',
    title: 'Code Review & Security Audit',
    prompt: 'Webhook-triggered code review workflow that scans git commits for bugs, requires senior developer sign-off, and posts formatted PR release notes.',
  },
  {
    icon: 'synthesizer',
    title: 'B2B Lead Intelligence & Outreach',
    prompt: 'Deep web research on company leads, automated qualification scoring, and personalized outreach drafting with compliance validation.',
  },
];

export default function AiWorkflowModal() {
  const aiModalOpen = useStore((s) => s.aiModalOpen);
  const setAiModalOpen = useStore((s) => s.setAiModalOpen);
  const generateWorkflow = useStore((s) => s.generateWorkflow);
  const isGenerating = useStore((s) => s.isGeneratingWorkflow);

  const [prompt, setPrompt] = useState('');
  const [customName, setCustomName] = useState('');

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isGenerating) setAiModalOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isGenerating, setAiModalOpen]);

  if (!aiModalOpen) return null;

  const handleGenerate = async (e) => {
    e?.preventDefault();
    if (!prompt.trim() || isGenerating) return;
    await generateWorkflow(prompt.trim(), customName.trim() || null);
  };

  const handleSelectPreset = (preset) => {
    setPrompt(preset.prompt);
    setCustomName(preset.title);
  };

  return (
    <div className="modal-backdrop" onClick={() => !isGenerating && setAiModalOpen(false)}>
      <div
        className="modal modal--ai-generator"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: 720, width: '92%' }}
      >
        {/* Header */}
        <div className="modal__header" style={{ alignItems: 'flex-start' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <IconSparkles size={20} style={{ color: 'var(--primary)' }} />
              <h3 className="modal__title" style={{ fontSize: 18, fontWeight: 700 }}>
                AI Workflow Generator
              </h3>
              <span className="af-badge af-badge--primary" style={{ fontSize: 10 }}>
                Phase 7
              </span>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)' }}>
              Describe your objective in natural language. AgentFlow will architect nodes, connections, and system prompts automatically.
            </p>
          </div>
          <button
            className="modal__close"
            onClick={() => !isGenerating && setAiModalOpen(false)}
            disabled={isGenerating}
          >
            <IconClose size={13} />
          </button>
        </div>

        {/* Body */}
        <div className="modal__body" style={{ padding: '20px 24px' }}>
          {/* Quick Presets */}
          <div style={{ marginBottom: 18 }}>
            <label className="form-label" style={{ fontSize: 12, marginBottom: 8, color: 'var(--text-secondary)' }}>
              Quick Starter Archetypes
            </label>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                gap: 8,
              }}
            >
              {PRESET_PROMPTS.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="ai-preset-chip"
                  onClick={() => handleSelectPreset(p)}
                  disabled={isGenerating}
                >
                  <span style={{ fontSize: 15 }}>{p.icon}</span>
                  <div style={{ textAlign: 'left' }}>
                    <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-primary)' }}>
                      {p.title}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleGenerate}>
            {/* Custom Workflow Name (Optional) */}
            <div className="form-group" style={{ marginBottom: 14 }}>
              <label className="form-label" style={{ fontSize: 12 }}>
                Workflow Title <span style={{ opacity: 0.6 }}>(Optional)</span>
              </label>
              <input
                id="ai-workflow-title-input"
                name="workflow_title"
                className="form-input"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder="e.g., Enterprise Compliance & Review Pipeline"
                disabled={isGenerating}
              />
            </div>

            {/* Prompt Textarea */}
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="form-label" style={{ fontSize: 12 }}>
                Workflow Description & Requirements
              </label>
              <textarea
                id="ai-workflow-prompt-textarea"
                name="workflow_prompt"
                className="form-input"
                rows={4}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g. Create a pipeline that analyzes customer tickets with AI, requires human manager approval for churn risks, and drafts resolution messages with citations..."
                style={{ resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.5 }}
                disabled={isGenerating}
                required
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>
                <span>Include details like agents, tools, or approval steps desired</span>
                <span>{prompt.length} chars</span>
              </div>
            </div>

            {/* Generation Progress Indicator */}
            {isGenerating && (
              <div className="ai-generating-banner">
                <div className="spinner" style={{ width: 18, height: 18 }} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--primary-color, #6366f1)' }}>
                    Synthesizing Multi-Agent Architecture...
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                    Generating node topologies, edge logic, and system prompts
                  </div>
                </div>
              </div>
            )}

            {/* Footer Buttons */}
            <div className="modal__footer" style={{ padding: '16px 0 0', margin: 0 }}>
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => setAiModalOpen(false)}
                disabled={isGenerating}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn--primary"
                disabled={isGenerating || !prompt.trim()}
                style={{ minWidth: 160 }}
              >
                {isGenerating ? (
                  <>
                    <span className="spinner" style={{ width: 14, height: 14 }} />
                    Architecting DAG...
                  </>
                ) : (
                  'Generate Workflow'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
