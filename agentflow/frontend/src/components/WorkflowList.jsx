/**
 * WorkflowList — Clean, Neat Enterprise Workspace Dashboard.
 *
 * Designed with modern workspace aesthetics (Linear/n8n/Vercel):
 * - Clean status indicators with vector SVG icons and colored dots (Zero emojis)
 * - Metric health cards: Active, Draft, Failed, Total
 * - Filter tabs, search, and tag organization
 * - Grid view with mini-graph topology previews & high-density Table view
 * - Multi-select batch operations (Tag, Status, Duplicate, Delete)
 * - Clean environment switcher (Development / Production / All)
 */
import { useEffect, useMemo, useState } from 'react';
import useStore from '../store';
import MiniGraphPreview from './MiniGraphPreview';
import {
  IconBolt,
  IconPlus,
  IconGrid,
  IconList,
  IconSearch,
  IconTrash,
  IconCopy,
  IconPlay,
  IconRocket,
  IconRefresh,
  IconSparkles,
  IconLayers,
  IconShield,
  IconChart,
  IconTag,
  IconCheck,
  IconClose,
  IconExternalLink,
} from './Icons';

export default function WorkflowList() {
  const workflows = useStore((s) => s.workflows);
  const fetchWorkflows = useStore((s) => s.fetchWorkflows);
  const loadWorkflow = useStore((s) => s.loadWorkflow);
  const deleteWorkflow = useStore((s) => s.deleteWorkflow);
  const duplicateWorkflow = useStore((s) => s.duplicateWorkflow);
  const setView = useStore((s) => s.setView);
  const newWorkflow = useStore((s) => s.newWorkflow);
  const setTemplateModalOpen = useStore((s) => s.setTemplateModalOpen);
  const setAiModalOpen = useStore((s) => s.setAiModalOpen);
  const setAnalyticsModalOpen = useStore((s) => s.setAnalyticsModalOpen);
  const setHitlModalOpen = useStore((s) => s.setHitlModalOpen);
  const pendingApprovals = useStore((s) => s.pendingApprovals);
  const fetchPendingApprovals = useStore((s) => s.fetchPendingApprovals);
  const deployWorkflow = useStore((s) => s.deployWorkflow);

  // Environment & View state
  const environment = useStore((s) => s.environment);
  const setEnvironment = useStore((s) => s.setEnvironment);
  const viewMode = useStore((s) => s.viewMode);
  const setViewMode = useStore((s) => s.setViewMode);
  const selectedTag = useStore((s) => s.selectedTag);
  const setSelectedTag = useStore((s) => s.setSelectedTag);

  // Batch operations state
  const selectedWorkflowIds = useStore((s) => s.selectedWorkflowIds);
  const toggleSelectWorkflow = useStore((s) => s.toggleSelectWorkflow);
  const selectAllWorkflows = useStore((s) => s.selectAllWorkflows);
  const clearSelectedWorkflows = useStore((s) => s.clearSelectedWorkflows);
  const batchDeleteWorkflows = useStore((s) => s.batchDeleteWorkflows);
  const batchTagWorkflows = useStore((s) => s.batchTagWorkflows);
  const batchSetStatus = useStore((s) => s.batchSetStatus);
  const batchDuplicateWorkflows = useStore((s) => s.batchDuplicateWorkflows);
  const cleanupDuplicates = useStore((s) => s.cleanupDuplicates);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // all, active, draft, failed
  const [sortBy, setSortBy] = useState('updated'); // updated, name, nodes
  const [deletingId, setDeletingId] = useState(null);
  const [tagInputModal, setTagInputModal] = useState(false);
  const [newTagText, setNewTagText] = useState('');

  useEffect(() => {
    fetchWorkflows();
    fetchPendingApprovals();
  }, [fetchWorkflows, fetchPendingApprovals]);

  const handleOpen = async (id) => {
    await loadWorkflow(id);
    setView('editor');
  };

  const handleDelete = async (e, id, name) => {
    e.stopPropagation();
    if (window.confirm(`Are you sure you want to delete "${name}"?`)) {
      setDeletingId(id);
      await deleteWorkflow(id);
      setDeletingId(null);
    }
  };

  const handleDuplicate = async (e, id) => {
    e.stopPropagation();
    await duplicateWorkflow(id);
  };

  const handleDeploy = (e, id) => {
    e.stopPropagation();
    deployWorkflow(id, environment);
  };

  const handleRun = async (e, id) => {
    e.stopPropagation();
    await loadWorkflow(id);
    setView('editor');
    setTimeout(() => {
      useStore.getState().triggerRun();
    }, 150);
  };

  // Extract all distinct tags from workflows
  const allAvailableTags = useMemo(() => {
    const tagsSet = new Set();
    workflows.forEach((w) => {
      if (Array.isArray(w.tags)) {
        w.tags.forEach((t) => tagsSet.add(t));
      }
    });
    return Array.from(tagsSet).sort();
  }, [workflows]);

  // Aggregate operational counts
  const counts = useMemo(() => {
    let active = 0;
    let draft = 0;
    let failed = 0;
    workflows.forEach((w) => {
      const s = (w.status || 'draft').toLowerCase();
      if (s === 'active') active++;
      else if (s === 'failed') failed++;
      else draft++;
    });
    return { total: workflows.length, active, draft, failed };
  }, [workflows]);

  // Filtered and sorted workflows
  const filteredWorkflows = useMemo(() => {
    return workflows
      .filter((w) => {
        const matchesSearch =
          w.name.toLowerCase().includes(search.toLowerCase()) ||
          (w.description && w.description.toLowerCase().includes(search.toLowerCase()));

        const matchesTag =
          selectedTag === 'all' ||
          (Array.isArray(w.tags) && w.tags.some((t) => t.toLowerCase() === selectedTag.toLowerCase()));

        const wStatus = (w.status || 'draft').toLowerCase();
        const matchesStatus = statusFilter === 'all' || wStatus === statusFilter;

        const wEnv = (w.environment || 'development').toLowerCase();
        const matchesEnv = environment === 'all' || wEnv === environment.toLowerCase();

        return matchesSearch && matchesTag && matchesStatus && matchesEnv;
      })
      .sort((a, b) => {
        if (sortBy === 'name') return a.name.localeCompare(b.name);
        if (sortBy === 'nodes') return (b.node_count || 0) - (a.node_count || 0);
        return new Date(b.updated_at || 0) - new Date(a.updated_at || 0);
      });
  }, [workflows, search, selectedTag, statusFilter, environment, sortBy]);

  const allFilteredSelected =
    filteredWorkflows.length > 0 &&
    filteredWorkflows.every((w) => selectedWorkflowIds.includes(w.id));

  const handleToggleSelectAll = () => {
    if (allFilteredSelected) {
      clearSelectedWorkflows();
    } else {
      selectAllWorkflows(filteredWorkflows.map((w) => w.id));
    }
  };

  const handleApplyBatchTag = async () => {
    if (!newTagText.trim()) return;
    await batchTagWorkflows([newTagText.trim()], 'add');
    setNewTagText('');
    setTagInputModal(false);
  };

  return (
    <div className="af-workspace">
      {/* ── Top Workspace Header ── */}
      <div className="af-workspace-header">
        <div className="af-workspace-header__left">
          <div className="af-workspace-badge-row">
            <span className="af-workspace-icon">
              <IconBolt size={18} />
            </span>
            <div className="af-workspace-title-group">
              <h1 className="af-workspace-title">Workspace</h1>
              <span className="af-workspace-subtitle">Multi-Agent Workflow Pipelines</span>
            </div>
            <span className="af-workspace-tag">Enterprise</span>
          </div>

          {/* Environment Switcher Segment */}
          <div className="af-workspace-env-toggle">
            <button
              type="button"
              className={`af-workspace-env-btn ${environment === 'development' ? 'active' : ''}`}
              onClick={() => setEnvironment('development')}
            >
              <span className="af-dot af-dot--dev" />
              <span>Development</span>
            </button>
            <button
              type="button"
              className={`af-workspace-env-btn ${environment === 'production' ? 'active' : ''}`}
              onClick={() => setEnvironment('production')}
            >
              <span className="af-dot af-dot--prod" />
              <span>Production</span>
            </button>
            <button
              type="button"
              className={`af-workspace-env-btn ${environment === 'all' ? 'active' : ''}`}
              onClick={() => setEnvironment('all')}
            >
              <span>All Envs</span>
            </button>
          </div>
        </div>

        {/* Right Primary Action Controls */}
        <div className="af-workspace-header__actions">
          <button
            type="button"
            className="af-btn af-btn--ghost"
            onClick={() => setHitlModalOpen(true)}
            title="Human-In-The-Loop Approval Inbox"
          >
            <IconShield size={14} />
            <span>Approvals</span>
            {pendingApprovals.length > 0 && (
              <span className="af-badge af-badge--warning">{pendingApprovals.length}</span>
            )}
          </button>

          <button
            type="button"
            className="af-btn af-btn--ghost"
            onClick={() => setAiModalOpen(true)}
            title="Workflow Architect: Natural language prompt to DAG"
          >
            <IconSparkles size={14} />
            <span>Build with AI</span>
          </button>

          <button
            type="button"
            className="af-btn af-btn--ghost"
            onClick={() => setTemplateModalOpen(true)}
            title="Starter workflow blueprints"
          >
            <IconLayers size={14} />
            <span>Templates</span>
          </button>

          <button
            type="button"
            className="af-btn af-btn--ghost"
            onClick={() => setAnalyticsModalOpen(true)}
            title="Execution telemetry & performance"
          >
            <IconChart size={14} />
            <span>Analytics</span>
          </button>

          <button
            type="button"
            className="af-btn af-btn--primary"
            onClick={() => {
              newWorkflow();
              setView('editor');
            }}
          >
            <IconPlus size={14} />
            <span>New Workflow</span>
          </button>
        </div>
      </div>

      {/* ── Metric Health Cards Strip ── */}
      <div className="af-workspace-metrics">
        <div
          className={`af-metric-card ${statusFilter === 'all' ? 'af-metric-card--active' : ''}`}
          onClick={() => setStatusFilter('all')}
        >
          <div className="af-metric-card__header">
            <span className="af-metric-card__label">Total Workflows</span>
            <IconLayers size={14} className="af-metric-card__icon" />
          </div>
          <div className="af-metric-card__value">{counts.total}</div>
          <div className="af-metric-card__hint">Orchestrated pipelines</div>
        </div>

        <div
          className={`af-metric-card ${statusFilter === 'active' ? 'af-metric-card--active' : ''}`}
          onClick={() => setStatusFilter('active')}
        >
          <div className="af-metric-card__header">
            <span className="af-metric-card__label">Active</span>
            <span className="af-dot af-dot--prod" />
          </div>
          <div className="af-metric-card__value" style={{ color: '#34d399' }}>
            {counts.active}
          </div>
          <div className="af-metric-card__hint">Live in production</div>
        </div>

        <div
          className={`af-metric-card ${statusFilter === 'draft' ? 'af-metric-card--active' : ''}`}
          onClick={() => setStatusFilter('draft')}
        >
          <div className="af-metric-card__header">
            <span className="af-metric-card__label">Draft</span>
            <span className="af-dot af-dot--draft" />
          </div>
          <div className="af-metric-card__value" style={{ color: '#fbbf24' }}>
            {counts.draft}
          </div>
          <div className="af-metric-card__hint">Under development</div>
        </div>

        <div
          className={`af-metric-card ${statusFilter === 'failed' ? 'af-metric-card--active' : ''}`}
          onClick={() => setStatusFilter('failed')}
        >
          <div className="af-metric-card__header">
            <span className="af-metric-card__label">Failed</span>
            <span className="af-dot af-dot--failed" />
          </div>
          <div className="af-metric-card__value" style={{ color: counts.failed > 0 ? '#f87171' : 'var(--text-muted)' }}>
            {counts.failed}
          </div>
          <div className="af-metric-card__hint">Requires attention</div>
        </div>
      </div>

      {/* ── Organization & Control Toolbar ── */}
      <div className="af-workspace-toolbar">
        {/* Status Filter Tabs */}
        <div className="af-workspace-tabs">
          <button
            type="button"
            className={`af-workspace-tab ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => setStatusFilter('all')}
          >
            <span>All</span>
            <span className="af-tab-count">{counts.total}</span>
          </button>
          <button
            type="button"
            className={`af-workspace-tab ${statusFilter === 'active' ? 'active' : ''}`}
            onClick={() => setStatusFilter('active')}
          >
            <span className="af-dot af-dot--prod" />
            <span>Active</span>
            <span className="af-tab-count">{counts.active}</span>
          </button>
          <button
            type="button"
            className={`af-workspace-tab ${statusFilter === 'draft' ? 'active' : ''}`}
            onClick={() => setStatusFilter('draft')}
          >
            <span className="af-dot af-dot--draft" />
            <span>Draft</span>
            <span className="af-tab-count">{counts.draft}</span>
          </button>
          <button
            type="button"
            className={`af-workspace-tab ${statusFilter === 'failed' ? 'active' : ''}`}
            onClick={() => setStatusFilter('failed')}
          >
            <span className="af-dot af-dot--failed" />
            <span>Failed</span>
            <span className="af-tab-count">{counts.failed}</span>
          </button>
        </div>

        {/* Right Filter & View Mode Controls */}
        <div className="af-workspace-toolbar__right">
          {/* Search Box */}
          <div className="af-workspace-search-box">
            <IconSearch size={14} className="af-search-icon" />
            <input
              id="workflow-list-search-input"
              name="workflow_search"
              type="text"
              placeholder="Search workflows, tags..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="af-workspace-search-input"
            />
            {search && (
              <button
                type="button"
                className="af-search-clear-btn"
                onClick={() => setSearch('')}
                title="Clear search"
              >
                <IconClose size={11} />
              </button>
            )}
          </div>

          {/* Sort Dropdown */}
          <select
            className="af-workspace-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            title="Sort workflows"
          >
            <option value="updated">Recently Updated</option>
            <option value="name">Name (A-Z)</option>
            <option value="nodes">Node Count</option>
          </select>

          {/* View Mode Toggle (Grid vs Table) */}
          <div className="af-workspace-view-switch">
            <button
              type="button"
              className={`af-view-btn ${viewMode === 'grid' ? 'active' : ''}`}
              onClick={() => setViewMode('grid')}
              title="Grid View"
            >
              <IconGrid size={14} />
            </button>
            <button
              type="button"
              className={`af-view-btn ${viewMode === 'table' ? 'active' : ''}`}
              onClick={() => setViewMode('table')}
              title="Table View"
            >
              <IconList size={14} />
            </button>
          </div>

          {/* Clean Duplicates Action */}
          <button
            type="button"
            className="af-btn af-btn--ghost af-btn--sm"
            onClick={() => {
              if (window.confirm('Clean up duplicate test workflows? This preserves the latest and removes duplicates.')) {
                cleanupDuplicates();
              }
            }}
            title="Clean older duplicates with identical names"
          >
            <IconRefresh size={12} />
            <span>Clean Duplicates</span>
          </button>
        </div>
      </div>

      {/* ── Tags Organization Strip ── */}
      <div className="af-workspace-tags-strip">
        <span className="af-tags-label">Tags:</span>
        <button
          type="button"
          className={`af-tag-chip ${selectedTag === 'all' ? 'active' : ''}`}
          onClick={() => setSelectedTag('all')}
        >
          All
        </button>
        {allAvailableTags.map((tag) => (
          <button
            key={tag}
            type="button"
            className={`af-tag-chip ${selectedTag.toLowerCase() === tag.toLowerCase() ? 'active' : ''}`}
            onClick={() => setSelectedTag(tag)}
          >
            #{tag}
          </button>
        ))}
        {allAvailableTags.length === 0 && (
          <span className="af-tags-empty">No tags assigned</span>
        )}
      </div>

      {/* ── Floating Batch Operations Bar ── */}
      {selectedWorkflowIds.length > 0 && (
        <div className="af-workspace-batch-bar">
          <div className="af-batch-left">
            <IconCheck size={14} className="af-batch-check" />
            <span className="af-batch-title">
              {selectedWorkflowIds.length} {selectedWorkflowIds.length === 1 ? 'workflow' : 'workflows'} selected
            </span>
          </div>

          <div className="af-batch-actions">
            <button
              type="button"
              className="af-btn af-btn--ghost af-btn--sm"
              onClick={() => setTagInputModal(true)}
            >
              <IconTag size={12} />
              <span>Add Tag</span>
            </button>
            <button
              type="button"
              className="af-btn af-btn--ghost af-btn--sm"
              onClick={() => batchSetStatus('active')}
            >
              <span className="af-dot af-dot--prod" />
              <span>Set Active</span>
            </button>
            <button
              type="button"
              className="af-btn af-btn--ghost af-btn--sm"
              onClick={() => batchSetStatus('draft')}
            >
              <span className="af-dot af-dot--draft" />
              <span>Set Draft</span>
            </button>
            <button
              type="button"
              className="af-btn af-btn--ghost af-btn--sm"
              onClick={batchDuplicateWorkflows}
            >
              <IconCopy size={12} />
              <span>Duplicate</span>
            </button>
            <button
              type="button"
              className="af-btn af-btn--ghost af-btn--danger af-btn--sm"
              onClick={batchDeleteWorkflows}
            >
              <IconTrash size={12} />
              <span>Delete Selected</span>
            </button>
            <button
              type="button"
              className="af-btn af-btn--ghost af-btn--sm"
              onClick={clearSelectedWorkflows}
            >
              <IconClose size={11} />
              <span>Deselect</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Workflows Content (Grid vs Table vs Empty) ── */}
      {filteredWorkflows.length === 0 ? (
        <div className="af-workspace-empty">
          <div className="af-empty-icon-wrap">
            <IconSearch size={28} />
          </div>
          <h3 className="af-empty-title">
            {workflows.length === 0 ? 'No workflows in workspace' : 'No workflows matching current filters'}
          </h3>
          <p className="af-empty-desc">
            {selectedTag !== 'all' || search || statusFilter !== 'all'
              ? 'Try resetting your search query, status, or tag filters.'
              : 'Create a new autonomous agent DAG from scratch or load an enterprise template.'}
          </p>
          <div className="af-empty-actions">
            <button
              type="button"
              className="af-btn af-btn--ghost"
              onClick={() => {
                setSearch('');
                setSelectedTag('all');
                setStatusFilter('all');
              }}
            >
              Reset Filters
            </button>
            <button
              type="button"
              className="af-btn af-btn--primary"
              onClick={() => {
                newWorkflow();
                setView('editor');
              }}
            >
              <IconPlus size={14} />
              <span>New Workflow</span>
            </button>
          </div>
        </div>
      ) : viewMode === 'table' ? (
        /* ── High-Density Table View ── */
        <div className="af-workspace-table-wrap">
          <table className="af-workspace-table">
            <thead>
              <tr>
                <th style={{ width: 40, textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    checked={allFilteredSelected}
                    onChange={handleToggleSelectAll}
                  />
                </th>
                <th>Workflow Name</th>
                <th style={{ width: 110 }}>Status</th>
                <th style={{ width: 100 }}>Environment</th>
                <th>Tags</th>
                <th style={{ width: 130 }}>Graph Topology</th>
                <th style={{ width: 130 }}>Last Run</th>
                <th style={{ width: 190, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredWorkflows.map((wf) => {
                const isSelected = selectedWorkflowIds.includes(wf.id);
                const statusStr = (wf.status || 'draft').toLowerCase();

                return (
                  <tr
                    key={wf.id}
                    className={`af-table-row ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleOpen(wf.id)}
                  >
                    <td style={{ textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelectWorkflow(wf.id)}
                      />
                    </td>
                    <td>
                      <div className="af-table-name">{wf.name}</div>
                      {wf.description && (
                        <div className="af-table-desc">{wf.description}</div>
                      )}
                    </td>
                    <td>
                      <span className={`af-status-badge af-status-badge--${statusStr}`}>
                        <span className={`af-dot af-dot--${statusStr === 'active' ? 'prod' : statusStr === 'failed' ? 'failed' : 'draft'}`} />
                        <span>{statusStr}</span>
                      </span>
                    </td>
                    <td>
                      <span className="af-env-pill">
                        {wf.environment === 'production' ? 'Production' : 'Development'}
                      </span>
                    </td>
                    <td>
                      <div className="af-table-tags">
                        {(wf.tags || []).map((t) => (
                          <span key={t} className="af-table-tag">
                            #{t}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className="af-table-nodes">
                        {wf.node_count || 0} nodes • {wf.edge_count || 0} edges
                      </span>
                    </td>
                    <td>
                      {wf.last_run_at ? (
                        <div className="af-table-run-meta">
                          <span>{new Date(wf.last_run_at).toLocaleDateString()}</span>
                          {typeof wf.success_rate === 'number' && (
                            <span className={wf.success_rate >= 80 ? 'af-rate-good' : 'af-rate-warn'}>
                              {wf.success_rate}% pass
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="af-table-noruns">Never executed</span>
                      )}
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="af-table-actions">
                        <button
                          type="button"
                          className="af-icon-btn af-icon-btn--run"
                          onClick={(e) => handleRun(e, wf.id)}
                          title="Run workflow"
                        >
                          <IconPlay size={11} />
                        </button>
                        <button
                          type="button"
                          className="af-icon-btn"
                          onClick={(e) => handleDeploy(e, wf.id)}
                          title="Deploy endpoint"
                        >
                          <IconRocket size={12} />
                        </button>
                        <button
                          type="button"
                          className="af-icon-btn"
                          onClick={(e) => handleDuplicate(e, wf.id)}
                          title="Duplicate"
                        >
                          <IconCopy size={12} />
                        </button>
                        <button
                          type="button"
                          className="af-icon-btn af-icon-btn--danger"
                          onClick={(e) => handleDelete(e, wf.id, wf.name)}
                          disabled={deletingId === wf.id}
                          title="Delete"
                        >
                          <IconTrash size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        /* ── Modern Workspace Grid Cards View ── */
        <div className="af-workspace-grid">
          {filteredWorkflows.map((wf) => {
            const isSelected = selectedWorkflowIds.includes(wf.id);
            const statusStr = (wf.status || 'draft').toLowerCase();

            return (
              <div
                key={wf.id}
                className={`af-ws-card ${isSelected ? 'selected' : ''}`}
                onClick={() => handleOpen(wf.id)}
              >
                {/* Card Header */}
                <div className="af-ws-card__header">
                  <div className="af-ws-card__title-row">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onClick={(e) => e.stopPropagation()}
                      onChange={() => toggleSelectWorkflow(wf.id)}
                      className="af-ws-card__checkbox"
                    />
                    <div className="af-ws-card__name" title={wf.name}>
                      {wf.name}
                    </div>
                  </div>

                  <div className="af-ws-card__badges">
                    <span className={`af-status-badge af-status-badge--${statusStr}`}>
                      <span className={`af-dot af-dot--${statusStr === 'active' ? 'prod' : statusStr === 'failed' ? 'failed' : 'draft'}`} />
                      <span>{statusStr}</span>
                    </span>
                    <span className="af-version-pill">v{wf.version || 1}</span>
                  </div>
                </div>

                {/* Description */}
                {wf.description && (
                  <p className="af-ws-card__desc">{wf.description}</p>
                )}

                {/* Mini Graph Preview Canvas */}
                <div className="af-ws-card__preview">
                  <MiniGraphPreview
                    nodes={wf.nodes_preview || []}
                    edges={wf.edges_preview || []}
                    height={90}
                  />
                </div>

                {/* Graph Metadata */}
                <div className="af-ws-card__meta">
                  <span className="af-ws-card__topology">
                    {wf.node_count || 0} nodes • {wf.edge_count || 0} edges
                  </span>
                  <span className="af-ws-card__date">
                    {wf.last_run_at
                      ? `Ran ${new Date(wf.last_run_at).toLocaleDateString()}`
                      : `Updated ${new Date(wf.updated_at || Date.now()).toLocaleDateString()}`}
                  </span>
                </div>

                {/* Tag Pills */}
                {Array.isArray(wf.tags) && wf.tags.length > 0 && (
                  <div className="af-ws-card__tags">
                    {wf.tags.slice(0, 3).map((t) => (
                      <span
                        key={t}
                        className="af-card-tag"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedTag(t);
                        }}
                      >
                        #{t}
                      </span>
                    ))}
                    {wf.tags.length > 3 && (
                      <span className="af-card-tag af-card-tag--more">
                        +{wf.tags.length - 3}
                      </span>
                    )}
                  </div>
                )}

                {/* Card Action Footer */}
                <div className="af-ws-card__footer" onClick={(e) => e.stopPropagation()}>
                  <div className="af-ws-card__actions-left">
                    <button
                      type="button"
                      className="af-icon-btn af-icon-btn--run"
                      onClick={(e) => handleRun(e, wf.id)}
                      title="Run workflow now"
                    >
                      <IconPlay size={11} />
                    </button>
                    <button
                      type="button"
                      className="af-icon-btn"
                      onClick={(e) => handleDeploy(e, wf.id)}
                      title="Deploy to REST / Webhook"
                    >
                      <IconRocket size={12} />
                    </button>
                    <button
                      type="button"
                      className="af-icon-btn"
                      onClick={(e) => handleDuplicate(e, wf.id)}
                      title="Duplicate workflow"
                    >
                      <IconCopy size={12} />
                    </button>
                    <button
                      type="button"
                      className="af-icon-btn af-icon-btn--danger"
                      onClick={(e) => handleDelete(e, wf.id, wf.name)}
                      disabled={deletingId === wf.id}
                      title="Delete workflow"
                    >
                      <IconTrash size={12} />
                    </button>
                  </div>

                  <button
                    type="button"
                    className="af-ws-card__open-btn"
                    onClick={() => handleOpen(wf.id)}
                  >
                    <span>Open</span>
                    <IconExternalLink size={11} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Add Tag Batch Modal ── */}
      {tagInputModal && (
        <div className="modal-backdrop" onClick={() => setTagInputModal(false)}>
          <div className="modal-card" style={{ maxWidth: 400 }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 10, color: '#f1f5f9' }}>
              Add Tag to {selectedWorkflowIds.length} Workflows
            </h3>
            <input
              type="text"
              className="form-input"
              placeholder="Tag name (e.g. production, scraper, rag)..."
              value={newTagText}
              onChange={(e) => setNewTagText(e.target.value)}
              style={{ marginBottom: 14 }}
              autoFocus
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => setTagInputModal(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn--primary btn--sm"
                onClick={handleApplyBatchTag}
              >
                Apply Tag
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
