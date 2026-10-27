/**
 * TemplateModal — starter templates library.
 * Allows users to preview and load rich multi-agent DAG architectures in one click.
 */
import { useEffect } from 'react';
import useStore, { BUILTIN_TEMPLATES } from '../store';
import { IconSparkles, IconClose, IconLayers } from './Icons';

export default function TemplateModal() {
  const templateModalOpen = useStore((s) => s.templateModalOpen);
  const setTemplateModalOpen = useStore((s) => s.setTemplateModalOpen);
  const loadTemplate = useStore((s) => s.loadTemplate);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setTemplateModalOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [setTemplateModalOpen]);

  if (!templateModalOpen) return null;

  return (
    <div className="af-modal-backdrop" onClick={() => setTemplateModalOpen(false)}>
      <div className="af-template-modal" onClick={(e) => e.stopPropagation()}>
        <div className="af-modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <IconSparkles size={18} />
              </div>
              <h2 className="af-modal-title">AgentFlow Template Library</h2>
            </div>
            <p className="af-modal-subtitle">
              Kickstart production-grade multi-agent architectures with pre-configured loops, tools, and conditions.
            </p>
          </div>
          <button className="af-close-btn" onClick={() => setTemplateModalOpen(false)} title="Close">
            <IconClose size={13} />
          </button>
        </div>

        <div className="af-template-grid">
          {BUILTIN_TEMPLATES.map((tpl) => (
            <div key={tpl.key} className="af-template-card">
              <div className="af-template-card__header">
                <div className="af-template-card__icon">
                  <IconLayers size={18} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span className="af-template-card__title">{tpl.name}</span>
                    {tpl.badge && <span className="af-badge af-badge--accent">{tpl.badge}</span>}
                  </div>
                  <span className="af-template-card__cat">{tpl.category}</span>
                </div>
              </div>

              <p className="af-template-card__desc">{tpl.description}</p>

              <div className="af-template-card__stats">
                <span>{tpl.nodes.length} Nodes</span>
                <span>{tpl.edges.length} Edges</span>
                <span>Live Tool Hooks</span>
              </div>

              <div className="af-template-card__preview">
                {tpl.nodes.slice(0, 4).map((n, idx) => (
                  <span key={n.id} className="af-template-chip">
                    {idx > 0 && <span style={{ opacity: 0.4, margin: '0 4px' }}>→</span>}
                    {n.data.icon} {n.data.label}
                  </span>
                ))}
                {tpl.nodes.length > 4 && <span className="af-template-chip">+{tpl.nodes.length - 4} more</span>}
              </div>

              <button
                className="btn btn--primary"
                style={{ width: '100%', marginTop: 16 }}
                onClick={() => loadTemplate(tpl.key)}
              >
                Use This Template →
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
