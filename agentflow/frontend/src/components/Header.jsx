/**
 * Header.jsx — Streamlined 3-Cluster Enterprise Navigation Bar
 *
 * Left Cluster: Context & Identity (Breadcrumbs, Name Input, Version, Autosave indicator)
 * Center Cluster: Canvas Editing Tools (Undo, Redo, Dagre Auto-Format, Mini-Map) + Live execution status
 * Right Cluster: Lifecycle & Execution (Run, Export, Deploy, and "More ⋯" secondary dropdown)
 */
import { useState, useEffect, useRef } from 'react';
import useStore from '../store';
import {
  IconBolt,
  IconPlay,
  IconDownload,
  IconMap,
  IconUndo,
  IconRedo,
  IconMore,
  IconCheck,
  IconSettings,
  IconChart,
  IconLayers,
  IconSparkles,
  IconChevronRight,
  IconChevronDown,
  IconSun,
  IconMoon,
  IconMenu,
} from './Icons';

export default function Header() {
  const workflowName = useStore((s) => s.workflowName);
  const workflowVersion = useStore((s) => s.workflowVersion);
  const setWorkflowName = useStore((s) => s.setWorkflowName);
  const saveWorkflow = useStore((s) => s.saveWorkflow);
  const triggerRun = useStore((s) => s.triggerRun);
  const runStatus = useStore((s) => s.runStatus);
  const runMetrics = useStore((s) => s.runMetrics);
  const setActivePanel = useStore((s) => s.setActivePanel);
  const view = useStore((s) => s.view);
  const setView = useStore((s) => s.setView);
  const setTemplateModalOpen = useStore((s) => s.setTemplateModalOpen);
  const setBuildWithAiModalOpen = useStore((s) => s.setBuildWithAiModalOpen);
  const setTestStudioModalOpen = useStore((s) => s.setTestStudioModalOpen);
  const setIntegrationBuilderModalOpen = useStore((s) => s.setIntegrationBuilderModalOpen);
  const setPublishModalOpen = useStore((s) => s.setPublishModalOpen);
  const setMarketplaceModalOpen = useStore((s) => s.setMarketplaceModalOpen);
  const setAnalyticsModalOpen = useStore((s) => s.setAnalyticsModalOpen);
  const setSettingsModalOpen = useStore((s) => s.setSettingsModalOpen);
  const undo = useStore((s) => s.undo);
  const redo = useStore((s) => s.redo);
  const canUndo = useStore((s) => s.historyPast.length > 0);
  const canRedo = useStore((s) => s.historyFuture.length > 0);
  const autoLayout = useStore((s) => s.autoLayout);
  const exportWorkflow = useStore((s) => s.exportWorkflow);
  const showMiniMap = useStore((s) => s.showMiniMap);
  const toggleMiniMap = useStore((s) => s.toggleMiniMap);
  const environment = useStore((s) => s.environment);
  const setEnvironment = useStore((s) => s.setEnvironment);
  const deployWorkflow = useStore((s) => s.deployWorkflow);
  const workflowId = useStore((s) => s.workflowId);
  const theme = useStore((s) => s.theme);
  const toggleTheme = useStore((s) => s.toggleTheme);
  const toggleMobileSidebar = useStore((s) => s.toggleMobileSidebar);

  const [saving, setSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const moreMenuRef = useRef(null);

  // Global Ctrl+S shortcut to save
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Close more menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target)) {
        setMoreMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    await saveWorkflow();
    setSaving(false);
    setHasUnsavedChanges(false);
  };

  const handleDeploy = () => {
    if (workflowId) {
      deployWorkflow(workflowId, environment);
    } else {
      handleSave().then(() => deployWorkflow(useStore.getState().workflowId, environment));
    }
  };

  return (
    <header className="app-header">
      {/* ═══════════════════════════════════════════════════════════════════════
          CLUSTER 1: Left (Context & Identity)
          Breadcrumbs + Back to Workspace + Autosave status pill
         ═══════════════════════════════════════════════════════════════════════ */}
      <div className="app-header__left" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {view === 'editor' && (
          <button
            type="button"
            className="af-mobile-hamburger-btn"
            onClick={toggleMobileSidebar}
            title="Open Node Library"
            aria-label="Toggle node library menu"
          >
            <IconMenu size={18} />
          </button>
        )}

        <div
          className="app-header__logo-icon"
          onClick={() => setView('home')}
          style={{ cursor: 'pointer' }}
          title="Return to Workflows Dashboard"
        >
          <IconBolt size={18} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            className="app-header__brand"
            onClick={() => setView('home')}
            style={{ cursor: 'pointer', fontWeight: 700 }}
          >
            AgentFlow
          </span>

          {view === 'editor' && (
            <>
              <span style={{ color: 'var(--text-muted, #64748b)', margin: '0 2px' }}>/</span>
              <button
                type="button"
                className="btn btn--ghost btn--xs"
                style={{ color: '#94a3b8', padding: '2px 6px', fontSize: 11 }}
                onClick={() => setView('home')}
                title="Back to Workspace"
              >
                Workflows
              </button>
              <span style={{ color: 'var(--text-muted, #64748b)', margin: '0 2px' }}>/</span>

              <input
                id="app-header-workflow-name-input"
                name="workflow_name"
                className="app-header__workflow-name-input"
                value={workflowName}
                onChange={(e) => {
                  setWorkflowName(e.target.value);
                  setHasUnsavedChanges(true);
                }}
                placeholder="Workflow name..."
                title="Click to rename workflow"
              />

              <span className="af-badge af-badge--version">v{workflowVersion || 1}</span>

              {/* Autosave status indicator pill */}
              <div
                className="af-autosave-pill"
                onClick={handleSave}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  padding: '2px 8px',
                  borderRadius: 12,
                  fontSize: 10.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: saving ? 'rgba(56, 189, 248, 0.12)' : hasUnsavedChanges ? 'rgba(245, 158, 11, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                  color: saving ? '#38bdf8' : hasUnsavedChanges ? '#f59e0b' : '#10b981',
                  border: `1px solid ${saving ? 'rgba(56, 189, 248, 0.25)' : hasUnsavedChanges ? 'rgba(245, 158, 11, 0.25)' : 'rgba(16, 185, 129, 0.25)'}`,
                  marginLeft: 4,
                }}
                title={hasUnsavedChanges ? 'Unsaved changes (Click or Ctrl+S to save)' : 'Saved to database'}
              >
                {saving ? (
                  <>
                    <span className="spinner" style={{ width: 8, height: 8 }} />
                    <span>Saving</span>
                  </>
                ) : hasUnsavedChanges ? (
                  <>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f59e0b' }} />
                    <span>Unsaved</span>
                  </>
                ) : (
                  <>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />
                    <span>Saved</span>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════
          CLUSTER 2: Center (Canvas Editing Tools)
          Undo, Redo, Dagre Layout, Mini-Map + Live Run Status Ticker
         ═══════════════════════════════════════════════════════════════════════ */}
      {view === 'editor' && (
        <div className="app-header__center" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Grouped Editing Toolset */}
          <div
            className="af-header-edit-tools"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 6,
              padding: '2px',
            }}
          >
            <button
              type="button"
              className="btn btn--ghost btn--xs"
              style={{ opacity: canUndo ? 1 : 0.35, padding: '4px 7px' }}
              onClick={undo}
              disabled={!canUndo}
              title="Undo (Ctrl+Z)"
            >
              <IconUndo size={13} />
            </button>
            <button
              type="button"
              className="btn btn--ghost btn--xs"
              style={{ opacity: canRedo ? 1 : 0.35, padding: '4px 7px' }}
              onClick={redo}
              disabled={!canRedo}
              title="Redo (Ctrl+Y)"
            >
              <IconRedo size={13} />
            </button>
            <div style={{ width: 1, height: 14, background: 'rgba(255,255,255,0.12)', margin: '0 2px' }} />
            <button
              type="button"
              className="btn btn--ghost btn--xs"
              style={{ padding: '4px 8px', fontSize: 11, fontWeight: 600 }}
              onClick={() => autoLayout()}
              title="Auto-Format / Dagre Layout (LR)"
            >
              Format
            </button>
            <button
              type="button"
              className="btn btn--ghost btn--xs"
              style={{
                padding: '4px 7px',
                color: showMiniMap ? 'var(--accent-primary, #6366f1)' : '#94a3b8',
              }}
              onClick={toggleMiniMap}
              title="Toggle Mini-Map"
            >
              <IconMap size={13} />
            </button>
          </div>

          {/* Execution Status Pill & Live Token Ticker */}
          {runStatus && (
            <div
              className={`af-status-pill af-status-pill--${runStatus}`}
              onClick={() => setActivePanel('logs')}
              title="Click to view run event logs"
              style={{ cursor: 'pointer' }}
            >
              {runStatus === 'running' && <span className="spinner-dots" />}
              {runStatus === 'running' && 'Executing DAG...'}
              {runStatus === 'paused' && 'Awaiting Approval'}
              {runStatus === 'completed' && 'Run Succeeded'}
              {runStatus === 'failed' && 'Run Failed'}
              {runStatus === 'cancelled' && 'Cancelled'}
            </div>
          )}

          {runMetrics && runMetrics.tokens > 0 && (
            <div className="af-metrics-ticker">
              <span title="Tokens consumed">{runMetrics.tokens.toLocaleString()} tok</span>
              <span style={{ opacity: 0.4 }}>•</span>
              <span title="Estimated cost">${runMetrics.cost_usd?.toFixed(4)}</span>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════
          CLUSTER 3: Right (Lifecycle & Execution + More Dropdown)
         ═══════════════════════════════════════════════════════════════════════ */}
      <div className="app-header__actions" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {view === 'editor' ? (
          <>
            {/* Primary Action 1: Run Workflow */}
            <button
              type="button"
              className="btn btn--sm"
              style={{
                background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                color: '#ffffff',
                fontWeight: 700,
                boxShadow: '0 2px 10px rgba(99, 102, 241, 0.4)',
                border: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
              }}
              onClick={() => triggerRun()}
              title="Execute DAG"
            >
              <IconPlay size={12} />
              <span>Test / Run</span>
            </button>

            {/* Primary Action 2: Export JSON */}
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={exportWorkflow}
              title="Export Workflow definition as JSON"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}
            >
              <IconDownload size={13} />
              <span>Export</span>
            </button>

            {/* Primary Action 3: Accent Deploy Button */}
            <button
              type="button"
              className="btn btn--sm"
              style={{
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#34d399',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                fontWeight: 600,
              }}
              onClick={handleDeploy}
              title="Deploy as live authenticated endpoint"
            >
              Deploy
            </button>

            {/* Clean More (⋯) Secondary Dropdown Menu */}
            <div ref={moreMenuRef} style={{ position: 'relative' }}>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                style={{ padding: '6px 8px' }}
                onClick={() => setMoreMenuOpen(!moreMenuOpen)}
                title="More Studio Tools & Configuration"
              >
                <IconMore size={15} />
              </button>

              {moreMenuOpen && (
                <div
                  className="af-more-dropdown-menu"
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 6px)',
                    right: 0,
                    width: 210,
                    background: '#13141b',
                    border: '1px solid #282c3c',
                    borderRadius: 8,
                    boxShadow: '0 12px 32px rgba(0,0,0,0.8), 0 0 0 1px rgba(255,255,255,0.06)',
                    padding: 5,
                    zIndex: 1000,
                  }}
                >
                  <button
                    type="button"
                    className="af-more-dropdown-item"
                    onClick={() => {
                      setMoreMenuOpen(false);
                      setBuildWithAiModalOpen(true);
                    }}
                  >
                    <IconSparkles size={13} style={{ color: '#818cf8' }} />
                    <span>Build with AI</span>
                  </button>
                  <button
                    type="button"
                    className="af-more-dropdown-item"
                    onClick={() => {
                      setMoreMenuOpen(false);
                      setIntegrationBuilderModalOpen(true);
                    }}
                  >
                    <IconBolt size={13} style={{ color: '#06b6d4' }} />
                    <span>Connectors</span>
                  </button>
                  <button
                    type="button"
                    className="af-more-dropdown-item"
                    onClick={() => {
                      setMoreMenuOpen(false);
                      setTemplateModalOpen(true);
                    }}
                  >
                    <IconLayers size={13} />
                    <span>Templates</span>
                  </button>
                  <button
                    type="button"
                    className="af-more-dropdown-item"
                    onClick={() => {
                      setMoreMenuOpen(false);
                      setTestStudioModalOpen(true);
                    }}
                  >
                    <IconCheck size={13} style={{ color: '#38bdf8' }} />
                    <span>Test Studio</span>
                  </button>
                  <button
                    type="button"
                    className="af-more-dropdown-item"
                    onClick={() => {
                      setMoreMenuOpen(false);
                      setMarketplaceModalOpen(true);
                    }}
                  >
                    <IconLayers size={13} style={{ color: '#3b82f6' }} />
                    <span>Marketplace</span>
                  </button>
                  <button
                    type="button"
                    className="af-more-dropdown-item"
                    onClick={() => {
                      setMoreMenuOpen(false);
                      setAnalyticsModalOpen(true);
                    }}
                  >
                    <IconChart size={13} />
                    <span>Analytics</span>
                  </button>
                  <div style={{ height: 1, background: '#222533', margin: '4px 0' }} />
                  <button
                    type="button"
                    className="af-more-dropdown-item"
                    onClick={() => {
                      setMoreMenuOpen(false);
                      setSettingsModalOpen(true);
                    }}
                  >
                    <IconSettings size={13} />
                    <span>Settings & API Keys</span>
                  </button>
                </div>
              )}
            </div>
          </>
        ) : (
          /* Dashboard Home Global Controls */
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <div
              style={{
                display: 'inline-flex',
                background: 'rgba(0,0,0,0.5)',
                padding: '2px 4px',
                borderRadius: 16,
                border: '1px solid rgba(255,255,255,0.1)',
                marginRight: 4,
              }}
            >
              <button
                className={`btn btn--xs ${environment === 'development' ? 'btn--primary' : 'btn--ghost'}`}
                style={{ borderRadius: 12, fontSize: 11, padding: '2px 8px' }}
                onClick={() => setEnvironment('development')}
              >
                Dev
              </button>
              <button
                className={`btn btn--xs ${environment === 'production' ? 'btn--primary' : 'btn--ghost'}`}
                style={{
                  borderRadius: 12,
                  fontSize: 11,
                  padding: '2px 8px',
                  background: environment === 'production' ? '#10b981' : 'transparent',
                }}
                onClick={() => setEnvironment('production')}
              >
                Prod
              </button>
            </div>

            <button
              className="btn btn--ghost btn--sm"
              onClick={() => setIntegrationBuilderModalOpen(true)}
              style={{ color: '#06b6d4', fontWeight: 600 }}
              title="Integration Builder: Synthesize custom API connectors"
            >
              Connectors
            </button>
            <button
              className="btn btn--ghost btn--sm"
              onClick={() => setMarketplaceModalOpen(true)}
              style={{ color: '#3b82f6', fontWeight: 600 }}
              title="Browse Marketplace workflow catalog"
            >
              Marketplace
            </button>
            <button
              className="btn btn--ghost btn--sm"
              onClick={() => setTestStudioModalOpen(true)}
              style={{ color: '#38bdf8', fontWeight: 600 }}
              title="Evaluator QA: Generate 8 test cases & grade output rubrics"
            >
              Test Studio
            </button>
            <button
              className="btn btn--ghost btn--sm"
              onClick={() => setSettingsModalOpen(true)}
              title="Configure LLM API Keys"
            >
              API Keys
            </button>
          </div>
        )}

        {/* Global Sun/Moon Theme Toggle Button */}
        <button
          type="button"
          className="btn btn--ghost btn--sm af-theme-toggle-btn"
          onClick={toggleTheme}
          title={theme === 'light' ? 'Switch to Dark Obsidian Theme' : 'Switch to Clean Warm White Theme'}
          aria-label="Toggle Bright / Dark theme"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 9px' }}
        >
          {theme === 'light' ? <IconMoon size={14} /> : <IconSun size={14} />}
          <span className="af-theme-toggle-text">{theme === 'light' ? 'Dark' : 'Light'}</span>
        </button>
      </div>
    </header>
  );
}
