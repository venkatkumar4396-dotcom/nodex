/**
 * Sidebar — searchable agent & node palette with categorization.
 */
import { useState, useEffect, useMemo, useRef } from 'react';
import useStore from '../store';
import { renderNodeIcon, IconClose, IconSearch } from './Icons';

const CATEGORY_ORDER = [
  'Triggers',
  'Core Reasoning',
  'Autonomous Actions',
  'Decision & Flow',
  'Human Oversight',
  'Computation & Code',
  'Protocols & MCP',
  'Synthesis & Output',
  'trigger',
  'control',
  'information',
  'processing',
  'quality',
  'action',
  'memory',
];

const CATEGORY_LABELS = {
  'Triggers': 'Triggers',
  'Core Reasoning': 'Core Reasoning',
  'Autonomous Actions': 'Autonomous Actions',
  'Decision & Flow': 'Decision & Routing',
  'Human Oversight': 'Human Oversight & Safety',
  'Computation & Code': 'Computation & Data',
  'Protocols & MCP': 'Knowledge, Memory & MCP',
  'Synthesis & Output': 'Synthesis & Swarm',
  trigger: 'Triggers',
  control: 'Decision & Routing',
  information: 'Information & Search',
  processing: 'Processing & Creation',
  quality: 'Quality & Review',
  action: 'External Actions',
  memory: 'Memory & State',
};

export default function Sidebar() {
  const agentTypes = useStore((s) => s.agentTypes);
  const fetchAgentTypes = useStore((s) => s.fetchAgentTypes);
  const fetchAvailableTools = useStore((s) => s.fetchAvailableTools);
  const addNode = useStore((s) => s.addNode);
  const selectNode = useStore((s) => s.selectNode);
  const setActivePanel = useStore((s) => s.setActivePanel);
  const nodes = useStore((s) => s.nodes);
  const setTemplateModalOpen = useStore((s) => s.setTemplateModalOpen);
  const mobileSidebarOpen = useStore((s) => s.mobileSidebarOpen);
  const setMobileSidebarOpen = useStore((s) => s.setMobileSidebarOpen);

  const [search, setSearch] = useState('');
  const searchInputRef = useRef(null);

  useEffect(() => {
    fetchAgentTypes();
    fetchAvailableTools();
  }, [fetchAgentTypes, fetchAvailableTools]);

  // Press '/' to search
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === '/' && document.activeElement !== searchInputRef.current && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const grouped = useMemo(() => {
    const filtered = agentTypes.filter(
      (at) =>
        at.label.toLowerCase().includes(search.toLowerCase()) ||
        at.type.toLowerCase().includes(search.toLowerCase())
    );

    const groups = {};
    for (const at of filtered) {
      const cat = at.category || 'other';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(at);
    }

    const knownCategories = CATEGORY_ORDER.filter((c) => groups[c]);
    const extraCategories = Object.keys(groups).filter((c) => !CATEGORY_ORDER.includes(c));
    return [...knownCategories, ...extraCategories].map((c) => ({
      category: c,
      label: CATEGORY_LABELS[c] || c.toUpperCase(),
      items: groups[c],
    }));
  }, [agentTypes, search]);

  const onDragStart = (event, agentType) => {
    event.dataTransfer.setData(
      'application/agentflow-node',
      JSON.stringify(agentType)
    );
    event.dataTransfer.effectAllowed = 'move';
  };

  const handleNodeClick = (agentType) => {
    const offset = (nodes.length % 6) * 35;
    const nodeId = addNode(
      agentType.type,
      agentType.label,
      agentType.color,
      agentType.icon,
      { x: 260 + offset, y: 150 + offset }
    );
    selectNode(nodeId);
    setActivePanel('config');
    if (mobileSidebarOpen) {
      setMobileSidebarOpen(false);
    }
  };

  return (
    <>
      {mobileSidebarOpen && (
        <div
          className="af-mobile-backdrop"
          onClick={() => setMobileSidebarOpen(false)}
          aria-hidden="true"
        />
      )}
      <div className={`sidebar ${mobileSidebarOpen ? 'sidebar--mobile-open' : ''}`}>
        {/* ── Search Bar ── */}
        <div className="sidebar__header">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span className="sidebar__title">Node Library</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="af-badge af-badge--muted">{agentTypes.length} types</span>
              <button
                type="button"
                className="sidebar__mobile-close-btn"
                onClick={() => setMobileSidebarOpen(false)}
                title="Close palette"
                aria-label="Close palette"
              >
                <IconClose size={13} />
              </button>
            </div>
          </div>
        <div style={{ position: 'relative' }}>
          <input
            id="sidebar-agent-search-input"
            name="agent_search"
            ref={searchInputRef}
            className="sidebar__search"
            type="text"
            placeholder="Search agents... (press /)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              style={{
                position: 'absolute',
                right: 8,
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 4,
              }}
              title="Clear search"
            >
              <IconClose size={12} />
            </button>
          )}
        </div>
      </div>

      {/* ── Categorized Agent Palette ── */}
      <div className="sidebar__content">
        {grouped.map(({ category, label, items }) => (
          <div key={category} className="sidebar__category">
            <div className="sidebar__category-header">
              <span>{label}</span>
              <span className="sidebar__category-count">{items.length}</span>
            </div>
            {items.map((at) => (
              <div
                key={at.type}
                className="palette-node"
                draggable
                onDragStart={(e) => onDragStart(e, at)}
                onClick={() => handleNodeClick(at)}
                title={at.description ? `${at.label}: ${at.description} (Click to place or drag onto canvas)` : 'Click to place or drag onto canvas'}
              >
                <div
                  className="palette-node__icon"
                  style={{ background: `${at.color}20`, color: at.color, borderColor: `${at.color}40` }}
                >
                  {renderNodeIcon(at.type, at.label, 14)}
                </div>
                <div className="palette-node__info">
                  <div className="palette-node__label">{at.label}</div>
                  <div className="palette-node__desc" title={at.description}>{at.description || at.type}</div>
                </div>
                <span className="palette-node__add-btn" title="Add to canvas">
                  +
                </span>
              </div>
            ))}
          </div>
        ))}

        {grouped.length === 0 && (
          <div className="empty-state" style={{ padding: '30px 16px' }}>
            <div className="empty-state__icon">
              <IconSearch size={22} />
            </div>
            <div className="empty-state__text">
              {agentTypes.length === 0 ? 'Loading agent library...' : `No nodes matching "${search}"`}
            </div>
          </div>
        )}
      </div>

      {/* ── Sidebar Footer ── */}
      <div className="sidebar__footer">
        <button
          className="btn btn--ghost btn--sm"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={() => setTemplateModalOpen(true)}
        >
          Explore Templates
        </button>
      </div>
    </div>
  </>
  );
}
