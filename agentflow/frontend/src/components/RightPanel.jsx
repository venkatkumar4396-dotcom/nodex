/**
 * RightPanel — contextual panel for node configuration, edge configuration, and live execution logs.
 */
import useStore, { DEFAULT_SYSTEM_PROMPTS } from '../store';
import {
  renderNodeIcon,
  IconSettings,
  IconLink,
  IconFileText,
  IconChart,
  IconSearch,
  IconGlobe,
  IconEdit,
  IconFork,
  IconMail,
  IconCode,
  IconShield,
  IconDatabase,
  IconClose,
  IconCheck,
} from './Icons';
import VariableAutocompleteInput from './VariableAutocompleteInput';

export default function RightPanel() {
  const activePanel = useStore((s) => s.activePanel);
  const setActivePanel = useStore((s) => s.setActivePanel);
  const selectedNodeId = useStore((s) => s.selectedNodeId);
  const selectedEdgeId = useStore((s) => s.selectedEdgeId);
  const nodes = useStore((s) => s.nodes);
  const edges = useStore((s) => s.edges);
  const updateNodeData = useStore((s) => s.updateNodeData);
  const updateNodeConfig = useStore((s) => s.updateNodeConfig);
  const deleteNode = useStore((s) => s.deleteNode);
  const updateEdgeData = useStore((s) => s.updateEdgeData);
  const deleteEdge = useStore((s) => s.deleteEdge);
  const runEvents = useStore((s) => s.runEvents);
  const runStatus = useStore((s) => s.runStatus);
  const availableTools = useStore((s) => s.availableTools);
  const openNodeInspector = useStore((s) => s.openNodeInspector);
  const openEdgeModal = useStore((s) => s.openEdgeModal);

  if (!activePanel) return null;

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId);

  return (
    <>
      <div
        className="af-mobile-backdrop af-mobile-backdrop--right-panel"
        onClick={() => setActivePanel(null)}
        aria-hidden="true"
      />
      <div className="right-panel right-panel--active">
        {/* ── Tab Bar ── */}
      <div className="right-panel__header">
        <div className="tab-bar">
          <button
            className={`tab-bar__tab ${activePanel === 'config' ? 'tab-bar__tab--active' : ''}`}
            onClick={() => setActivePanel('config')}
          >
            <IconSettings size={13} style={{ marginRight: 5, verticalAlign: 'middle' }} />
            Node
          </button>
          <button
            className={`tab-bar__tab ${activePanel === 'edge' ? 'tab-bar__tab--active' : ''}`}
            onClick={() => setActivePanel('edge')}
          >
            <IconLink size={13} style={{ marginRight: 5, verticalAlign: 'middle' }} />
            Edge
          </button>
          <button
            className={`tab-bar__tab ${activePanel === 'logs' ? 'tab-bar__tab--active' : ''}`}
            onClick={() => setActivePanel('logs')}
          >
            <IconFileText size={13} style={{ marginRight: 5, verticalAlign: 'middle' }} />
            Logs
            {runEvents.length > 0 && (
              <span className="af-tab-counter">
                {runEvents.length}
              </span>
            )}
          </button>
          <button
            className={`tab-bar__tab ${activePanel === 'trace' ? 'tab-bar__tab--active' : ''}`}
            onClick={() => setActivePanel('trace')}
          >
            <IconChart size={13} style={{ marginRight: 5, verticalAlign: 'middle' }} />
            Trace
          </button>
        </div>
        <button
          className="right-panel__close"
          onClick={() => setActivePanel(null)}
          title="Close panel"
        >
          <IconClose size={13} />
        </button>
      </div>

      {/* ── Panel Body ── */}
      <div className="right-panel__body">
        {activePanel === 'config' && selectedNode && (
          <NodeConfigForm
            node={selectedNode}
            availableTools={availableTools}
            onUpdateData={updateNodeData}
            onUpdateConfig={updateNodeConfig}
            onDelete={deleteNode}
            onInspect={openNodeInspector}
          />
        )}

        {activePanel === 'config' && !selectedNode && (
          <div className="empty-state" style={{ padding: '40px 16px' }}>
            <div className="empty-state__icon"><IconSettings size={30} /></div>
            <div className="empty-state__text">
              Select a node on the canvas to edit its prompt, model, and tools.
            </div>
          </div>
        )}

        {activePanel === 'edge' && selectedEdge && (
          <EdgeConfigForm
            edge={selectedEdge}
            nodes={nodes}
            onUpdate={updateEdgeData}
            onDelete={deleteEdge}
            onOpenModal={openEdgeModal}
          />
        )}

        {activePanel === 'edge' && !selectedEdge && (
          <div className="empty-state" style={{ padding: '40px 16px' }}>
            <div className="empty-state__icon"><IconLink size={30} /></div>
            <div className="empty-state__text">
              Click any arrow connection on the canvas to configure conditions, loops, or fallbacks.
            </div>
          </div>
        )}

        {activePanel === 'logs' && (
          <RunLogPanel events={runEvents} status={runStatus} onInspect={openNodeInspector} />
        )}

        {activePanel === 'trace' && (
          <TraceTimelineView
            nodes={nodes}
            runEvents={runEvents}
            onInspect={openNodeInspector}
          />
        )}
      </div>
    </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Node Config Form
// ═══════════════════════════════════════════════════════════════════════════

function NodeConfigForm({ node, availableTools, onUpdateData, onUpdateConfig, onDelete, onInspect }) {
  const { id, data } = node;
  const { label, config, nodeType, color, status, output } = data;
  const currentTools = config?.tools || [];
  const extra = config?.extra || {};

  const handleToolToggle = (toolName) => {
    const nextTools = currentTools.includes(toolName)
      ? currentTools.filter((t) => t !== toolName)
      : [...currentTools, toolName];
    onUpdateConfig(id, { tools: nextTools });
  };

  const handleExtraChange = (key, value) => {
    onUpdateConfig(id, {
      extra: {
        ...extra,
        [key]: value,
      },
    });
  };

  const handlePromptPreset = (presetText) => {
    onUpdateConfig(id, { system_prompt: presetText });
  };

  const handleResetToDefaultPrompt = () => {
    const defaultPrompt = DEFAULT_SYSTEM_PROMPTS[nodeType] || '';
    onUpdateConfig(id, { system_prompt: defaultPrompt });
  };

  return (
    <div>
      {/* Node identity */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 16,
          padding: '12px',
          background: `${color || '#6366f1'}15`,
          borderRadius: 'var(--radius-md)',
          border: `1px solid ${color || '#6366f1'}35`,
        }}
      >
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: `${color || '#6366f1'}20`,
            color: color || '#6366f1',
          }}
        >
          {renderNodeIcon(nodeType, label, 18)}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {label}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {nodeType?.replace(/_/g, ' ')} • <span style={{ opacity: 0.6 }}>{id}</span>
          </div>
        </div>
        {status && (
          <button
            className="btn btn--ghost btn--sm"
            onClick={() => onInspect(id)}
            title="Inspect Data Output"
          >
            <IconSearch size={12} style={{ marginRight: 4 }} />
            View Data
          </button>
        )}
      </div>

      {/* Label */}
      <div className="form-group">
        <label className="form-label">Node Label</label>
        <input
          id="node-label-input"
          name="node_label"
          className="form-input"
          value={label}
          onChange={(e) => onUpdateData(id, { label: e.target.value })}
        />
      </div>

      {/* ── Node Task & Input Parameters (User Direct Input) ── */}
      <div
        className="af-task-card"
        style={{
          background: 'var(--bg-elevated)',
          padding: '12px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-color)',
          marginBottom: 16,
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
          {nodeType === 'research' || nodeType === 'scraper' || nodeType === 'tool' ? (
            <IconGlobe size={14} />
          ) : nodeType === 'writer' ? (
            <IconEdit size={14} />
          ) : nodeType === 'router' || nodeType === 'classifier' ? (
            <IconFork size={14} />
          ) : nodeType === 'email' ? (
            <IconMail size={14} />
          ) : nodeType === 'code' ? (
            <IconCode size={14} />
          ) : (
            <IconEdit size={14} />
          )}
          <span>
            {nodeType === 'research' || nodeType === 'scraper' || nodeType === 'tool'
              ? 'Target URL & Research Goal'
              : nodeType === 'writer'
              ? 'Topic & Copywriting Instructions'
              : nodeType === 'router' || nodeType === 'classifier'
              ? 'Routing Rules & Conditions'
              : nodeType === 'email'
              ? 'Email Recipient & Subject'
              : nodeType === 'code'
              ? 'Python Transformation Code'
              : 'Node Task & Instructions'}
          </span>
        </div>

        {/* Dynamic fields based on node type */}
        {(nodeType === 'research' || nodeType === 'scraper' || nodeType === 'tool') && (
          <div>
            <div style={{ marginBottom: 10 }}>
              <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
                Target URL(s) to Investigate / Scrape
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="https://example.com/company or https://news.ycombinator.com"
                value={extra.target_url || extra.url || ''}
                onChange={(e) => handleExtraChange('target_url', e.target.value)}
              />
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
                Enter the website or link for this agent to read, scrape, or investigate.
              </div>
            </div>

            <div>
              <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
                Specific Research Objective or Query
              </label>
              <textarea
                className="form-textarea"
                rows={2}
                placeholder="e.g. Extract company mission, executive team, recent updates, and pricing tiers..."
                value={extra.user_task || extra.query || ''}
                onChange={(e) => handleExtraChange('user_task', e.target.value)}
              />
            </div>
          </div>
        )}

        {nodeType === 'writer' && (
          <div>
            <div style={{ marginBottom: 10 }}>
              <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
                What should this agent write? (Goal / Topic)
              </label>
              <textarea
                className="form-textarea"
                rows={2}
                placeholder="e.g. Personalized cold email introducing our enterprise AI platform based on research findings..."
                value={extra.user_task || extra.purpose || ''}
                onChange={(e) => handleExtraChange('user_task', e.target.value)}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>Tone</label>
                <select
                  className="form-select"
                  value={extra.tone || 'professional'}
                  onChange={(e) => handleExtraChange('tone', e.target.value)}
                >
                  <option value="professional">Professional</option>
                  <option value="direct">Direct & Concise</option>
                  <option value="friendly">Warm & Friendly</option>
                  <option value="persuasive">Persuasive</option>
                </select>
              </div>
              <div>
                <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>Target Max Words</label>
                <input
                  type="number"
                  className="form-input"
                  placeholder="150"
                  value={extra.max_words || 150}
                  onChange={(e) => handleExtraChange('max_words', Number(e.target.value))}
                />
              </div>
            </div>
          </div>
        )}

        {(nodeType === 'router' || nodeType === 'classifier') && (
          <div>
            <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
              Branching Rules & Criteria
            </label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder="e.g. If qualification score >= 7, route to 'high_priority'. If score between 4 and 6, route to 'standard'. Otherwise route to 'nurture'."
              value={extra.user_task || extra.criteria || ''}
              onChange={(e) => handleExtraChange('user_task', e.target.value)}
            />
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
              Evaluated against incoming node output data.
            </div>
          </div>
        )}

        {nodeType === 'email' && (
          <div>
            <div style={{ marginBottom: 8 }}>
              <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
                Recipient Email (To)
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. lead@company.com or {{lead_email}}"
                value={extra.recipient || ''}
                onChange={(e) => handleExtraChange('recipient', e.target.value)}
              />
            </div>
            <div>
              <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
                Subject Line
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Follow-up regarding architecture demo"
                value={extra.subject || ''}
                onChange={(e) => handleExtraChange('subject', e.target.value)}
              />
            </div>
          </div>
        )}

        {nodeType === 'code' && (
          <div>
            <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
              Python Transformation Logic
            </label>
            <textarea
              className="form-textarea"
              rows={4}
              style={{ fontFamily: 'monospace', fontSize: 12 }}
              placeholder="# Available variables: input_data&#10;output = {&#10;  'score': input_data.get('score', 0) * 1.5,&#10;  'processed': True&#10;}"
              value={extra.script || extra.user_task || ''}
              onChange={(e) => handleExtraChange('script', e.target.value)}
            />
          </div>
        )}

        {!['research', 'scraper', 'tool', 'writer', 'router', 'classifier', 'email', 'code'].includes(nodeType) && (
          <div>
            <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
              Instructions / Task for this Node
            </label>
            <textarea
              className="form-textarea"
              rows={2}
              placeholder="Enter what this node should specifically do with the incoming data..."
              value={extra.user_task || ''}
              onChange={(e) => handleExtraChange('user_task', e.target.value)}
            />
          </div>
        )}
      </div>

      {/* Model */}
      <div className="form-group">
        <label className="form-label">LLM Provider & Model</label>
        <select
          id="node-model-select"
          name="node_model"
          className="form-select"
          value={config?.model || 'openrouter/free'}
          onChange={(e) => onUpdateConfig(id, { model: e.target.value })}
        >
          <optgroup label="OpenRouter (Active Provider)">
            <option value="openrouter/free">openrouter/free (Auto Free Tier - Recommended)</option>
            <option value="openrouter/google/gemini-2.0-flash-exp:free">gemini-2.0-flash-exp:free</option>
            <option value="openrouter/meta-llama/llama-3.2-3b-instruct:free">llama-3.2-3b-instruct:free</option>
            <option value="openrouter/openai/gpt-4o-mini">openrouter/openai/gpt-4o-mini</option>
            <option value="openrouter/anthropic/claude-3.5-sonnet">openrouter/anthropic/claude-3.5-sonnet</option>
            <option value="openrouter/deepseek/deepseek-chat">openrouter/deepseek/deepseek-chat</option>
          </optgroup>
          <optgroup label="Kimi / Moonshot AI">
            <option value="moonshot/moonshot-v1-8k">moonshot-v1-8k (Fast & Efficient)</option>
            <option value="moonshot/moonshot-v1-32k">moonshot-v1-32k (Balanced)</option>
            <option value="moonshot/moonshot-v1-128k">moonshot-v1-128k (Long Context)</option>
          </optgroup>
          <optgroup label="OpenAI">
            <option value="gpt-4o-mini">GPT-4o Mini</option>
            <option value="gpt-4o">GPT-4o</option>
          </optgroup>
          <optgroup label="Anthropic">
            <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
          </optgroup>
          <optgroup label="Google">
            <option value="gemini/gemini-1.5-flash">Gemini 1.5 Flash</option>
            <option value="gemini/gemini-1.5-pro">Gemini 1.5 Pro</option>
          </optgroup>
        </select>
      </div>

      {/* ── System Methodology (Pre-configured Default Prompt) ── */}
      <div className="form-group">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <label className="form-label" style={{ marginBottom: 0 }}>System Methodology</label>
            <span className="af-badge af-badge--status af-badge--completed" style={{ fontSize: 10, padding: '1px 6px' }}>
              Pre-configured Default
            </span>
          </div>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            style={{ fontSize: 11, padding: '2px 6px', height: 'auto' }}
            onClick={handleResetToDefaultPrompt}
            title="Reset to factory default system prompt"
          >
            Reset to Default
          </button>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
          Pre-configured operational prompt defining agent execution, fact extraction, and structure.
        </div>
        <VariableAutocompleteInput
          id="node-system-prompt-textarea"
          name="node_system_prompt"
          className="form-textarea"
          nodeId={id}
          value={config?.system_prompt || ''}
          onChange={(e) => onUpdateConfig(id, { system_prompt: e.target.value })}
          placeholder="Define this agent's behavioral persona, directives, and output expectations... Type {{ for variables"
          rows={5}
        />
        {/* Quick Methodology Presets (no emojis) */}
        <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
          <button
            className="af-condition-pill"
            onClick={() => handlePromptPreset('You are a structured analytical reasoning agent. Break down inputs methodically, extract key facts, and return precise output.')}
          >
            Reasoning
          </button>
          <button
            className="af-condition-pill"
            onClick={() => handlePromptPreset(DEFAULT_SYSTEM_PROMPTS.research || '')}
          >
            Deep Research
          </button>
          <button
            className="af-condition-pill"
            onClick={() => handlePromptPreset(DEFAULT_SYSTEM_PROMPTS.scraper || '')}
          >
            Web Scraper
          </button>
          <button
            className="af-condition-pill"
            onClick={() => handlePromptPreset(DEFAULT_SYSTEM_PROMPTS.tool || '')}
          >
            Tool Loop
          </button>
          <button
            className="af-condition-pill"
            onClick={() => handlePromptPreset(DEFAULT_SYSTEM_PROMPTS.sql || '')}
          >
            SQL Agent
          </button>
          <button
            className="af-condition-pill"
            onClick={() => handlePromptPreset(DEFAULT_SYSTEM_PROMPTS.guardrail || '')}
          >
            Guardrail
          </button>
          <button
            className="af-condition-pill"
            onClick={() => handlePromptPreset(DEFAULT_SYSTEM_PROMPTS.validator || '')}
          >
            Validator
          </button>
          <button
            className="af-condition-pill"
            onClick={() => handlePromptPreset(DEFAULT_SYSTEM_PROMPTS.router || '')}
          >
            Router
          </button>
          <button
            className="af-condition-pill"
            onClick={() => handlePromptPreset(DEFAULT_SYSTEM_PROMPTS.synthesizer || '')}
          >
            Synthesizer
          </button>
        </div>
      </div>

      {/* ── Tools Checklist ── */}
      <div className="form-group">
        <label className="form-label">Attached Tools & Capabilities</label>
        <div className="af-tools-list">
          {availableTools && availableTools.length > 0 ? (
            availableTools.map((t) => {
              const checked = currentTools.includes(t.name);
              return (
                <div
                  key={t.name}
                  className={`af-tool-item ${checked ? 'af-tool-item--checked' : ''}`}
                  onClick={() => handleToolToggle(t.name)}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => {}}
                    style={{ pointerEvents: 'none', accentColor: 'var(--accent-primary)' }}
                  />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12 }}>{t.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{t.description}</div>
                  </div>
                </div>
              );
            })
          ) : (
            <>
              <div
                className={`af-tool-item ${currentTools.includes('web_search') ? 'af-tool-item--checked' : ''}`}
                onClick={() => handleToolToggle('web_search')}
              >
                <input type="checkbox" checked={currentTools.includes('web_search')} onChange={() => {}} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 12 }}>web_search</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Search Google/Brave for current live web data</div>
                </div>
              </div>
              <div
                className={`af-tool-item ${currentTools.includes('http_tool') ? 'af-tool-item--checked' : ''}`}
                onClick={() => handleToolToggle('http_tool')}
              >
                <input type="checkbox" checked={currentTools.includes('http_tool')} onChange={() => {}} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 12 }}>http_tool</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Fetch live web pages and execute REST APIs</div>
                </div>
              </div>
              <div
                className={`af-tool-item ${currentTools.includes('email_tool') ? 'af-tool-item--checked' : ''}`}
                onClick={() => handleToolToggle('email_tool')}
              >
                <input type="checkbox" checked={currentTools.includes('email_tool')} onChange={() => {}} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 12 }}>email_tool</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Send emails via SendGrid or SMTP</div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Autonomy & Tool Governance (Phase 1) ── */}
      <div className="form-group" style={{ marginTop: 14, marginBottom: 16 }}>
        <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Autonomy Level</span>
          <span style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--accent-primary)', fontWeight: 600 }}>
            Phase 1
          </span>
        </label>
        <select
          id="node-autonomy-select"
          name="node_autonomy"
          className="form-select"
          value={config?.autonomy || 'ask_first'}
          onChange={(e) => onUpdateConfig(id, { autonomy: e.target.value })}
        >
          <option value="suggest">Suggest — generate plan/call but do not execute</option>
          <option value="ask_first">Ask First — pause & await human confirmation</option>
          <option value="act">Act — execute autonomously within limits</option>
        </select>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
          {config?.autonomy === 'act'
            ? 'Fully autonomous execution. Destructive actions run immediately.'
            : config?.autonomy === 'suggest'
            ? 'Safe observation mode. Destructive actions return a proposal without running.'
            : 'Human-in-the-loop: destructive operations pause workflow execution for approval.'}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 10 }}>
          <div>
            <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
              Max Tool Rounds
            </label>
            <input
              type="number"
              min={1}
              max={50}
              className="form-input"
              value={config?.max_tool_rounds ?? 10}
              onChange={(e) => onUpdateConfig(id, { max_tool_rounds: parseInt(e.target.value, 10) || 10 })}
            />
          </div>
          <div>
            <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
              Tool Timeout (s)
            </label>
            <input
              type="number"
              min={1}
              max={300}
              className="form-input"
              value={config?.tool_timeout_seconds ?? 30}
              onChange={(e) => onUpdateConfig(id, { tool_timeout_seconds: parseFloat(e.target.value) || 30 })}
            />
          </div>
        </div>
      </div>

      {/* ── Specialized Node Type Configurations ── */}

      {/* 1. Code Agent: Hybrid Execution (Deterministic vs LLM) */}
      {nodeType === 'code' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(16, 185, 129, 0.08)', borderRadius: 8, border: '1px solid rgba(16, 185, 129, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#10b981', marginBottom: 8 }}>
            Hybrid Execution Engine
          </div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
            <button
              type="button"
              className={`btn btn--xs ${config?.extra?.execution_mode === 'deterministic' ? 'btn--primary' : 'btn--ghost'}`}
              style={{ flex: 1, background: config?.extra?.execution_mode === 'deterministic' ? '#10b981' : undefined }}
              onClick={() => onUpdateConfig(id, { extra: { ...(config?.extra || {}), execution_mode: 'deterministic' } })}
            >
              Deterministic Python
            </button>
            <button
              type="button"
              className={`btn btn--xs ${config?.extra?.execution_mode !== 'deterministic' ? 'btn--primary' : 'btn--ghost'}`}
              style={{ flex: 1 }}
              onClick={() => onUpdateConfig(id, { extra: { ...(config?.extra || {}), execution_mode: 'llm' } })}
            >
              LLM Transformation
            </button>
          </div>

          {config?.extra?.execution_mode === 'deterministic' && (
            <div>
              <label className="form-label" style={{ fontSize: 11, marginBottom: 4 }}>
                Python Transformation Script
              </label>
              <textarea
                className="form-textarea af-code-font"
                rows={5}
                placeholder={"# Access 'data' or 'inputs'\nresult = {\n  'total': len(data),\n  'status': 'transformed'\n}"}
                value={config?.extra?.script || ''}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), script: e.target.value } })}
              />
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                Runs deterministically in a secured sandbox without LLM hallucinations.
              </div>
            </div>
          )}
        </div>
      )}

      {/* 2. MCP Client Node Configuration */}
      {nodeType === 'mcp_client' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(6, 182, 212, 0.08)', borderRadius: 8, border: '1px solid rgba(6, 182, 212, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#06b6d4', marginBottom: 8 }}>
            Native MCP Client Node
          </div>
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label className="form-label" style={{ fontSize: 11 }}>MCP Resource Protocol</label>
            <select
              className="form-select"
              value={config?.extra?.mode || 'sqlite'}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), mode: e.target.value } })}
            >
              <option value="sqlite">SQLite Database Resource</option>
              <option value="filesystem">Local Filesystem Resource</option>
              <option value="custom">Standard MCP Tool Server</option>
            </select>
          </div>

          {(config?.extra?.mode || 'sqlite') === 'sqlite' && (
            <div>
              <div className="form-group" style={{ marginBottom: 8 }}>
                <label className="form-label" style={{ fontSize: 11 }}>Database Path</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder=":memory: or ./data.db"
                  value={config?.extra?.database_path || ''}
                  onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), database_path: e.target.value } })}
                />
              </div>
              <div className="form-group">
                <label className="form-label" style={{ fontSize: 11 }}>SQL Query</label>
                <textarea
                  className="form-textarea af-code-font"
                  rows={3}
                  placeholder="SELECT * FROM leads WHERE status = 'active';"
                  value={config?.extra?.query || ''}
                  onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), query: e.target.value } })}
                />
              </div>
            </div>
          )}

          {config?.extra?.mode === 'filesystem' && (
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 11 }}>Target File Path</label>
              <input
                type="text"
                className="form-input"
                placeholder="/path/to/schema.json or README.md"
                value={config?.extra?.file_path || ''}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), file_path: e.target.value } })}
              />
            </div>
          )}
        </div>
      )}

      {/* 3. Webhook Trigger Configuration */}
      {nodeType === 'trigger_webhook' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(59, 130, 246, 0.08)', borderRadius: 8, border: '1px solid rgba(59, 130, 246, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#3b82f6', marginBottom: 8 }}>
            Webhook Endpoint Configuration
          </div>
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label className="form-label" style={{ fontSize: 11 }}>Endpoint Route</label>
            <input
              type="text"
              className="form-input af-code-font"
              readOnly
              value={`/api/webhooks/v1/trigger-${id}`}
              style={{ background: '#111', color: 'var(--text-secondary)' }}
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>HTTP Method</label>
              <select
                className="form-select"
                value={config?.extra?.webhook_method || 'POST'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), webhook_method: e.target.value } })}
              >
                <option value="POST">POST (Standard)</option>
                <option value="PUT">PUT</option>
              </select>
            </div>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Secret Token Header</label>
              <input
                type="text"
                className="form-input"
                placeholder="X-Webhook-Secret"
                value={config?.extra?.secret_header || 'X-Webhook-Secret'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), secret_header: e.target.value } })}
              />
            </div>
          </div>
        </div>
      )}

      {/* 4. Scheduled / Cron Trigger Configuration */}
      {nodeType === 'trigger_cron' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(139, 92, 246, 0.08)', borderRadius: 8, border: '1px solid rgba(139, 92, 246, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#8b5cf6', marginBottom: 8 }}>
            Automated Cron Schedule
          </div>
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label className="form-label" style={{ fontSize: 11 }}>Schedule Frequency</label>
            <select
              className="form-select"
              value={config?.extra?.cron_preset || '0 9 * * 1-5'}
              onChange={(e) => {
                const preset = e.target.value;
                onUpdateConfig(id, { extra: { ...(config?.extra || {}), cron_preset: preset, cron_expr: preset } });
              }}
            >
              <option value="*/15 * * * *">Every 15 minutes</option>
              <option value="0 * * * *">Every hour</option>
              <option value="0 9 * * 1-5">Every weekday at 9:00 AM</option>
              <option value="0 9 * * *">Every day at 9:00 AM</option>
              <option value="0 0 * * 0">Weekly on Sunday midnight</option>
              <option value="custom">Custom Cron Expression</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 11 }}>Cron Expression (5-part)</label>
            <input
              type="text"
              className="form-input af-code-font"
              value={config?.extra?.cron_expr || config?.extra?.cron_preset || '0 9 * * 1-5'}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), cron_expr: e.target.value } })}
              placeholder="0 9 * * 1-5"
            />
          </div>
        </div>
      )}

      {/* 5. Deep Research Agent Configuration */}
      {nodeType === 'research' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(14, 165, 233, 0.08)', borderRadius: 8, border: '1px solid rgba(14, 165, 233, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#0ea5e9', marginBottom: 8 }}>
            Deep Research Investigation Parameters
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Investigation Depth</label>
              <select
                className="form-select"
                value={config?.extra?.research_depth || 'deep'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), research_depth: e.target.value } })}
              >
                <option value="fast">Quick Snapshot (3 sources)</option>
                <option value="deep">Deep Investigation (10 sources)</option>
                <option value="exhaustive">Exhaustive Intelligence</option>
              </select>
            </div>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Max Web Sources</label>
              <input
                type="number"
                className="form-input"
                min={1}
                max={25}
                value={config?.extra?.max_sources || 5}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), max_sources: parseInt(e.target.value) || 5 } })}
              />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 11 }}>Domain or Organization Filter</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. bloomberg.com, sec.gov, or all web"
              value={config?.extra?.domain_filter || ''}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), domain_filter: e.target.value } })}
            />
          </div>
        </div>
      )}

      {/* 6. Web Scraper Agent Configuration */}
      {nodeType === 'scraper' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(249, 115, 22, 0.08)', borderRadius: 8, border: '1px solid rgba(249, 115, 22, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#f97316', marginBottom: 8 }}>
            Web Scraper & Article Extractor
          </div>
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label className="form-label" style={{ fontSize: 11 }}>Extraction Target URL or Variable</label>
            <input
              type="text"
              className="form-input"
              placeholder="https://example.com or {{input.target_url}}"
              value={config?.extra?.target_url || ''}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), target_url: e.target.value } })}
            />
          </div>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 11 }}>Extraction Output Format</label>
            <select
              className="form-select"
              value={config?.extra?.extract_format || 'markdown'}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), extract_format: e.target.value } })}
            >
              <option value="markdown">Clean Markdown (De-noised text)</option>
              <option value="tables">Structured Data & HTML Tables</option>
              <option value="raw">Raw DOM Document</option>
            </select>
          </div>
        </div>
      )}

      {/* 7. Database & SQL Agent Configuration */}
      {nodeType === 'sql' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(2, 132, 199, 0.08)', borderRadius: 8, border: '1px solid rgba(2, 132, 199, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#0284c7', marginBottom: 8 }}>
            SQL Engine & Query Controls
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Database Dialect</label>
              <select
                className="form-select"
                value={config?.extra?.sql_dialect || 'postgresql'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), sql_dialect: e.target.value } })}
              >
                <option value="postgresql">PostgreSQL</option>
                <option value="sqlite">SQLite</option>
                <option value="mysql">MySQL</option>
                <option value="snowflake">Snowflake</option>
                <option value="bigquery">Google BigQuery</option>
              </select>
            </div>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Max Rows Returned</label>
              <input
                type="number"
                className="form-input"
                min={10}
                max={5000}
                value={config?.extra?.max_rows || 100}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), max_rows: parseInt(e.target.value) || 100 } })}
              />
            </div>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={config?.extra?.read_only !== false}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), read_only: e.target.checked } })}
              style={{ accentColor: 'var(--accent-primary)' }}
            />
            <span>Enforce Read-Only Mode (Restrict to SELECT queries only)</span>
          </label>
        </div>
      )}

      {/* 8. Document & PDF Parser Configuration */}
      {nodeType === 'document_parser' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(139, 92, 246, 0.08)', borderRadius: 8, border: '1px solid rgba(139, 92, 246, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#8b5cf6', marginBottom: 8 }}>
            Document & PDF Extraction Rules
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Document Type</label>
              <select
                className="form-select"
                value={config?.extra?.doc_type || 'pdf'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), doc_type: e.target.value } })}
              >
                <option value="pdf">PDF Document / Report</option>
                <option value="invoice">Scanned Invoice / Receipt</option>
                <option value="contract">Legal Agreement / Contract</option>
                <option value="spreadsheet">CSV / Excel Sheet</option>
              </select>
            </div>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Extraction Target</label>
              <select
                className="form-select"
                value={config?.extra?.extraction_target || 'tables'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), extraction_target: e.target.value } })}
              >
                <option value="tables">Financial & Data Tables</option>
                <option value="key_values">Key-Value Form Pairs</option>
                <option value="full_text">Full Text & Headings</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* 9. Multimodal Vision Agent Configuration */}
      {nodeType === 'vision' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(244, 63, 94, 0.08)', borderRadius: 8, border: '1px solid rgba(244, 63, 94, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#f43f5e', marginBottom: 8 }}>
            Multimodal Visual Reasoning
          </div>
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label className="form-label" style={{ fontSize: 11 }}>Visual Task Preset</label>
            <select
              className="form-select"
              value={config?.extra?.vision_task || 'ui_review'}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), vision_task: e.target.value } })}
            >
              <option value="ui_review">UI/UX Wireframe & Screenshot Review</option>
              <option value="chart_analysis">Chart & Graph Numeric Trend Extraction</option>
              <option value="doc_ocr">Scanned Document & Receipt OCR</option>
              <option value="general_inspection">General Visual Object Description</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 11 }}>Image Input Source / Key</label>
            <input
              type="text"
              className="form-input"
              placeholder="{{input.image_url}} or {{input.screenshot_base64}}"
              value={config?.extra?.image_source || '{{input.image_url}}'}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), image_source: e.target.value } })}
            />
          </div>
        </div>
      )}

      {/* 10. AI Guardrail & Safety Gate Configuration */}
      {nodeType === 'guardrail' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(225, 29, 72, 0.08)', borderRadius: 8, border: '1px solid rgba(225, 29, 72, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#e11d48', marginBottom: 8 }}>
            AI Safety & Policy Guardrails
          </div>
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label className="form-label" style={{ fontSize: 11 }}>Enforcement Action on Violation</label>
            <select
              className="form-select"
              value={config?.extra?.guard_action || 'redact_and_proceed'}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), guard_action: e.target.value } })}
            >
              <option value="redact_and_proceed">Redact Sensitive Values & Proceed</option>
              <option value="block_and_fail">Block Execution & Trigger Error Branch</option>
              <option value="flag_in_output">Flag Warnings in Output Payload</option>
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
              <input type="checkbox" defaultChecked style={{ accentColor: '#e11d48' }} />
              <span>Redact PII (SSN, credit cards, emails, phone numbers)</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
              <input type="checkbox" defaultChecked style={{ accentColor: '#e11d48' }} />
              <span>Detect Prompt Injections & System Directive Overrides</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
              <input type="checkbox" defaultChecked style={{ accentColor: '#e11d48' }} />
              <span>Verify Factuality & Detect Hallucinated URLs</span>
            </label>
          </div>
        </div>
      )}

      {/* 11. Schema & Quality Validator Configuration */}
      {nodeType === 'validator' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(5, 150, 105, 0.08)', borderRadius: 8, border: '1px solid rgba(5, 150, 105, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#059669', marginBottom: 8 }}>
            Schema Validation & Quality Gate
          </div>
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label className="form-label" style={{ fontSize: 11 }}>Validation Strategy</label>
            <select
              className="form-select"
              value={config?.extra?.validation_mode || 'json_schema'}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), validation_mode: e.target.value } })}
            >
              <option value="json_schema">Strict JSON Schema Enforcement</option>
              <option value="required_keys">Required Fields & Non-Empty Check</option>
              <option value="type_coercion">Data Type Validation & Formatting</option>
            </select>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={config?.extra?.auto_repair !== false}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), auto_repair: e.target.checked } })}
              style={{ accentColor: '#059669' }}
            />
            <span>Auto-repair payload via LLM reflection if validation fails</span>
          </label>
        </div>
      )}

      {/* 12. REST / HTTP API Node Configuration */}
      {nodeType === 'http_api' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(37, 99, 235, 0.08)', borderRadius: 8, border: '1px solid rgba(37, 99, 235, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#2563eb', marginBottom: 8 }}>
            REST API Request Dispatcher
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '90px 1fr', gap: 8, marginBottom: 8 }}>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Method</label>
              <select
                className="form-select"
                value={config?.extra?.http_method || 'POST'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), http_method: e.target.value } })}
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="DELETE">DELETE</option>
              </select>
            </div>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Target URL</label>
              <input
                type="text"
                className="form-input af-code-font"
                placeholder="https://api.service.com/v1/resource"
                value={config?.extra?.api_url || ''}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), api_url: e.target.value } })}
              />
            </div>
          </div>
        </div>
      )}

      {/* 13. Email Dispatcher Configuration */}
      {nodeType === 'email' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(5, 150, 105, 0.08)', borderRadius: 8, border: '1px solid rgba(5, 150, 105, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#059669', marginBottom: 8 }}>
            Email Notification Dispatcher
          </div>
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label className="form-label" style={{ fontSize: 11 }}>Recipient Email Variable</label>
            <input
              type="text"
              className="form-input"
              placeholder="{{input.email}} or team@company.com"
              value={config?.extra?.recipient || '{{input.email}}'}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), recipient: e.target.value } })}
            />
          </div>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 11 }}>Subject Line Template</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. Action Required: [Report] {{input.topic}}"
              value={config?.extra?.subject || ''}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), subject: e.target.value } })}
            />
          </div>
        </div>
      )}

      {/* 14. Messaging (Slack & Teams) Configuration */}
      {nodeType === 'messaging' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(79, 70, 229, 0.08)', borderRadius: 8, border: '1px solid rgba(79, 70, 229, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#4f46e5', marginBottom: 8 }}>
            Team Chat & Channel Dispatcher
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Platform</label>
              <select
                className="form-select"
                value={config?.extra?.chat_platform || 'slack'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), chat_platform: e.target.value } })}
              >
                <option value="slack">Slack</option>
                <option value="discord">Discord</option>
                <option value="teams">Microsoft Teams</option>
              </select>
            </div>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Card Style</label>
              <select
                className="form-select"
                value={config?.extra?.card_style || 'executive'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), card_style: e.target.value } })}
              >
                <option value="executive">Executive Card</option>
                <option value="compact">Compact Alert</option>
                <option value="markdown">Raw Markdown</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* 15. RAG Knowledge Agent Configuration */}
      {nodeType === 'rag' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(6, 182, 212, 0.08)', borderRadius: 8, border: '1px solid rgba(6, 182, 212, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#06b6d4', marginBottom: 8 }}>
            RAG Knowledge Retrieval Settings
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Knowledge Collection</label>
              <input
                type="text"
                className="form-input"
                placeholder="documentation"
                value={config?.extra?.collection || 'documentation'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), collection: e.target.value } })}
              />
            </div>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Top-K Chunks</label>
              <input
                type="number"
                className="form-input"
                min={1}
                max={20}
                value={config?.extra?.top_k || 5}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), top_k: parseInt(e.target.value) || 5 } })}
              />
            </div>
          </div>
        </div>
      )}

      {/* 16. Persistent Memory Bank Configuration */}
      {nodeType === 'memory' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(217, 70, 239, 0.08)', borderRadius: 8, border: '1px solid rgba(217, 70, 239, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#d946ef', marginBottom: 8 }}>
            Cross-Session Memory Bank
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Memory Operation</label>
              <select
                className="form-select"
                value={config?.extra?.mem_op || 'recall'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), mem_op: e.target.value } })}
              >
                <option value="recall">Recall Facts</option>
                <option value="store">Store Knowledge</option>
                <option value="clear">Clear State</option>
              </select>
            </div>
            <div>
              <label className="form-label" style={{ fontSize: 11 }}>Namespace / Scope</label>
              <input
                type="text"
                className="form-input"
                placeholder="user_preferences"
                value={config?.extra?.namespace || 'user_preferences'}
                onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), namespace: e.target.value } })}
              />
            </div>
          </div>
        </div>
      )}

      {/* 17. Supervisor Swarm Configuration */}
      {nodeType === 'supervisor' && (
        <div style={{ marginBottom: 16, padding: 12, background: 'rgba(124, 58, 237, 0.08)', borderRadius: 8, border: '1px solid rgba(124, 58, 237, 0.25)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#7c3aed', marginBottom: 8 }}>
            Swarm Orchestration Strategy
          </div>
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label className="form-label" style={{ fontSize: 11 }}>Coordination Model</label>
            <select
              className="form-select"
              value={config?.extra?.swarm_strategy || 'autonomous_swarm'}
              onChange={(e) => onUpdateConfig(id, { extra: { ...(config?.extra || {}), swarm_strategy: e.target.value } })}
            >
              <option value="autonomous_swarm">Autonomous Worker Swarm</option>
              <option value="sequential">Sequential Work Breakdown</option>
              <option value="consensus">Consensus Multi-Model Voting</option>
            </select>
          </div>
        </div>
      )}

      {/* 3. Self-Healing Fallback Models */}
      <div className="form-group" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <label className="form-label" style={{ marginBottom: 0 }}>Self-Healing Fallbacks</label>
          <span style={{ fontSize: 10, color: 'var(--text-accent)' }}>Auto-recover on API limits</span>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {['openrouter/free', 'gemini/gemini-1.5-flash', 'gpt-4o-mini', 'moonshot/moonshot-v1-32k'].map((fbModel) => {
            const currentFallbacks = config?.fallback_models || [];
            const isChecked = currentFallbacks.includes(fbModel);
            return (
              <button
                key={fbModel}
                type="button"
                className={`btn btn--xs ${isChecked ? 'btn--primary' : 'btn--ghost'}`}
                style={{ fontSize: 11, padding: '3px 8px' }}
                onClick={() => {
                  const updated = isChecked
                    ? currentFallbacks.filter((m) => m !== fbModel)
                    : [...currentFallbacks, fbModel];
                  onUpdateConfig(id, { fallback_models: updated });
                }}
              >
                {isChecked ? '• ' : '+ '}
                {fbModel.split('/').pop()}
              </button>
            );
          })}
        </div>
      </div>

      {/* Timeout & Policies */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div className="form-group">
          <label className="form-label">Timeout (sec)</label>
          <input
            id="node-timeout-input"
            name="node_timeout"
            className="form-input"
            type="number"
            min={1}
            max={600}
            value={config?.timeout_seconds || 60}
            onChange={(e) =>
              onUpdateConfig(id, { timeout_seconds: parseInt(e.target.value) || 60 })
            }
          />
        </div>
        <div className="form-group">
          <label className="form-label">Max Iterations</label>
          <input
            id="node-max-loop-iterations-input"
            name="node_max_loop_iterations"
            className="form-input"
            type="number"
            min={1}
            max={20}
            value={config?.max_loop_iterations || 3}
            onChange={(e) =>
              onUpdateConfig(id, { max_loop_iterations: parseInt(e.target.value) || 3 })
            }
          />
        </div>
      </div>

      {/* Join Policy */}
      <div className="form-group">
        <label className="form-label">Fan-In Join Policy</label>
        <select
          className="form-select"
          value={config?.join_policy || 'wait_all'}
          onChange={(e) => onUpdateConfig(id, { join_policy: e.target.value })}
        >
          <option value="wait_all">Wait All (synchronize incoming paths)</option>
          <option value="wait_any">Wait Any (race first completed path)</option>
        </select>
      </div>

      {/* Inspect button if executed */}
      {output && (
        <button
          className="btn btn--ghost"
          style={{ width: '100%', marginBottom: 12, justifyContent: 'center' }}
          onClick={() => onInspect(id)}
        >
          Open Step Data Inspector
        </button>
      )}

      {/* Delete button */}
      <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border-medium)' }}>
        <button
          className="btn btn--danger btn--sm"
          style={{ width: '100%' }}
          onClick={() => onDelete(id)}
        >
          Delete Node
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Edge Config Form
// ═══════════════════════════════════════════════════════════════════════════

function EdgeConfigForm({ edge, nodes, onUpdate, onDelete, onOpenModal }) {
  const sourceNode = nodes.find((n) => n.id === edge.source);
  const targetNode = nodes.find((n) => n.id === edge.target);

  const isFeedback = edge.data?.is_feedback || false;
  const isDefault = edge.data?.is_default || false;
  const isErrorHandler = edge.data?.is_error_handler || false;

  return (
    <div>
      <div className="af-edge-flow-info" style={{ marginBottom: 16 }}>
        <span className="af-edge-flow-node">{sourceNode?.data?.label || edge.source}</span>
        <span className="af-edge-flow-arrow">→</span>
        <span className="af-edge-flow-node">{targetNode?.data?.label || edge.target}</span>
      </div>

      {/* Branch Type Selector */}
      <div className="form-group" style={{ marginBottom: 14 }}>
        <label className="form-label">Branch Type</label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          <button
            className={`btn btn--sm ${!isFeedback && !isDefault && !isErrorHandler ? 'btn--primary' : 'btn--ghost'}`}
            onClick={() => onUpdate(edge.id, { is_feedback: false, is_default: false, is_error_handler: false })}
          >
            Standard
          </button>
          <button
            className={`btn btn--sm ${isFeedback ? 'btn--amber' : 'btn--ghost'}`}
            onClick={() => onUpdate(edge.id, { is_feedback: true, is_default: false, is_error_handler: false })}
          >
            Loop
          </button>
          <button
            className={`btn btn--sm ${isDefault ? 'btn--purple' : 'btn--ghost'}`}
            onClick={() => onUpdate(edge.id, { is_feedback: false, is_default: true, is_error_handler: false })}
          >
            Default
          </button>
          <button
            className={`btn btn--sm ${isErrorHandler ? 'btn--danger' : 'btn--ghost'}`}
            onClick={() => onUpdate(edge.id, { is_feedback: false, is_default: false, is_error_handler: true })}
          >
            Error
          </button>
        </div>
      </div>

      {/* Label */}
      <div className="form-group">
        <label className="form-label">Label on Canvas</label>
        <input
          id="panel-edge-label-input"
          name="edge_label"
          className="form-input"
          value={edge.data?.label || edge.label || ''}
          onChange={(e) => onUpdate(edge.id, { label: e.target.value })}
          placeholder="e.g. Score ≥ 7"
        />
      </div>

      {/* Condition Expression */}
      {!isDefault && (
        <div className="form-group">
          <label className="form-label">Condition Expression</label>
          <input
            id="panel-edge-condition-input"
            name="edge_condition"
            className="form-input af-code-font"
            value={edge.data?.condition || ''}
            onChange={(e) => onUpdate(edge.id, { condition: e.target.value })}
            placeholder="e.g. output.score >= 7"
          />
        </div>
      )}

      {/* Feedback Max Iterations */}
      {isFeedback && (
        <div className="form-group">
          <label className="form-label">Max Iterations Override</label>
          <input
            id="panel-edge-max-iterations-input"
            name="edge_max_iterations"
            className="form-input"
            type="number"
            min={1}
            max={20}
            value={edge.data?.max_iterations || 3}
            onChange={(e) => onUpdate(edge.id, { max_iterations: parseInt(e.target.value) || 3 })}
          />
        </div>
      )}

      {/* Advanced modal launcher & delete buttons */}
      <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 16, borderTop: '1px solid var(--border-medium)' }}>
        <button
          className="btn btn--ghost btn--sm"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={onOpenModal}
          title="Open advanced mapping and presets modal"
        >
          Advanced Modal View
        </button>
        <button
          className="btn btn--danger btn--sm"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={() => onDelete(edge.id)}
        >
          Delete Connection
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Run Log Panel
// ═══════════════════════════════════════════════════════════════════════════

function RunLogPanel({ events, status, onInspect }) {
  const retryNode = useStore((s) => s.retryNode);

  if (!events || events.length === 0) {
    return (
      <div className="empty-state" style={{ padding: '40px 16px' }}>
        <div className="empty-state__icon">
          <IconFileText size={28} />
        </div>
        <div className="empty-state__text">
          No execution events yet. Run the workflow DAG to inspect live logs.
        </div>
      </div>
    );
  }

  const statusColorMap = {
    node_started: 'running',
    node_completed: 'completed',
    node_failed: 'failed',
    node_skipped: 'skipped',
    run_started: 'running',
    run_completed: 'completed',
    run_failed: 'failed',
  };

  return (
    <div>
      {/* Run status banner */}
      {status && (
        <div style={{ marginBottom: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className={`badge badge--${status}`} style={{ fontSize: 12, padding: '4px 10px' }}>
            {status === 'running' && 'Executing DAG...'}
            {status === 'completed' && 'Run Completed'}
            {status === 'failed' && 'Run Failed'}
          </span>
          {status === 'failed' && (
            <button
              type="button"
              className="btn btn--danger btn--xs"
              style={{ fontWeight: 700 }}
              onClick={() => useStore.getState().diagnoseRun()}
            >
              Fix with AI (Doctor)
            </button>
          )}
        </div>
      )}

      <div className="run-log">
        {events.map((evt, idx) => {
          const evtClass = statusColorMap[evt.event] || 'pending';
          const time = evt.timestamp
            ? new Date(evt.timestamp * 1000).toLocaleTimeString()
            : '';

          const hasOutputOrInput = evt.data?.output || evt.data?.input;
          const isFailedOrSkipped =
            evt.event === 'node_failed' ||
            evt.event === 'node_skipped' ||
            evt.data?.status === 'failed' ||
            evt.data?.status === 'timed_out' ||
            evt.data?.status === 'skipped';

          return (
            <div key={idx} className={`run-log__event run-log__event--${evtClass}`}>
              <div className="run-log__event-header">
                <span className="run-log__event-type">
                  {evt.event?.replace(/_/g, ' ')}
                </span>
                <span className="run-log__event-time">{time}</span>
              </div>

              {evt.node_id && (
                <div
                  className="run-log__event-detail"
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}
                >
                  <span>
                    Node: <strong>{evt.node_id}</strong>
                  </span>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {isFailedOrSkipped && (
                      <button
                        className="af-inspect-btn"
                        style={{ borderColor: 'var(--accent-primary)', color: 'var(--accent-primary)' }}
                        onClick={() => retryNode && retryNode(evt.node_id)}
                        title="Retry this node using cached inputs"
                      >
                        Retry Node
                      </button>
                    )}
                    {hasOutputOrInput && (
                      <button
                        className="af-inspect-btn"
                        onClick={() => onInspect(evt.node_id)}
                        title="Inspect Step Input & Output"
                      >
                        Inspect
                      </button>
                    )}
                  </div>
                </div>
              )}

              {evt.data?.output && (
                <div className="run-log__event-detail" style={{ marginTop: 6 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 2 }}>
                    Output:
                  </div>
                  <pre
                    style={{
                      fontSize: 10,
                      background: 'var(--bg-base)',
                      padding: '6px 8px',
                      borderRadius: 4,
                      maxHeight: 90,
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {JSON.stringify(evt.data.output, null, 2)}
                  </pre>
                </div>
              )}

              {evt.data?.error && (
                <div
                  className="run-log__event-detail"
                  style={{ marginTop: 4, color: 'var(--status-failed)', fontWeight: 600 }}
                >
                  Error: {evt.data.error}
                </div>
              )}

              {evt.data?.tokens > 0 && (
                <div className="run-log__event-detail" style={{ marginTop: 4, opacity: 0.8, fontSize: 11 }}>
                  Tokens: {evt.data.tokens} • Duration: {evt.data.latency_ms}ms • Cost: ${evt.data.cost_usd?.toFixed(4)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Time-Travel Debugging & Trace Timeline Inspector
// ═══════════════════════════════════════════════════════════════════════════

function TraceTimelineView({ nodes, runEvents, onInspect }) {
  const retryNode = useStore((s) => s.retryNode);

  // Aggregate node completion traces
  const traces = runEvents.filter(
    (e) => (e.event === 'node_completed' || e.event === 'node_failed') && e.node_id
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h3 style={{ fontSize: 13, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
            Step-by-Step Execution Traces
          </h3>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Time-travel inspection across latency, tokens, cost, and variable state.
          </div>
        </div>
        <span className="af-badge af-badge--muted">{traces.length} steps recorded</span>
      </div>

      {traces.length === 0 ? (
        <div className="empty-state" style={{ padding: '40px 16px' }}>
          <div className="empty-state__icon">
            <IconChart size={28} />
          </div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>No execution traces yet</div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '6px 0 0' }}>
            Execute this workflow to inspect step-by-step state snapshots and traces.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {traces.map((trace, idx) => {
            const node = nodes.find((n) => n.id === trace.node_id);
            const isFailed = trace.event === 'node_failed' || trace.data?.status === 'timed_out';
            const statusColor = isFailed ? '#ef4444' : '#10b981';

            return (
              <div
                key={`${trace.node_id}-${idx}`}
                style={{
                  background: 'rgba(255,255,255,0.02)',
                  border: `1px solid ${statusColor}30`,
                  borderRadius: 8,
                  padding: 12,
                  position: 'relative',
                }}
              >
                {/* Step Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 800,
                        padding: '1px 5px',
                        borderRadius: 4,
                        background: `${statusColor}20`,
                        color: statusColor,
                      }}
                    >
                      Step #{idx + 1}
                    </span>
                    <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>
                      {node?.data?.label || trace.node_id}
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: 4 }}>
                    {isFailed && (
                      <button
                        className="btn btn--ghost btn--xs"
                        style={{ color: 'var(--accent-primary)', borderColor: 'var(--accent-primary)' }}
                        onClick={() => retryNode && retryNode(trace.node_id)}
                        title="Retry this step"
                      >
                        Retry
                      </button>
                    )}
                    <button
                      className="btn btn--ghost btn--xs"
                      onClick={() => onInspect(trace.node_id)}
                      title="Deep Inspect Variables"
                    >
                      Inspect State
                    </button>
                  </div>
                </div>

                {/* Telemetry stats pill row */}
                <div style={{ display: 'flex', gap: 8, fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
                  <span>Duration: {trace.data?.latency_ms || 0}ms</span>
                  <span>Tokens: {trace.data?.tokens || 0}</span>
                  <span>Cost: ${(trace.data?.cost_usd || 0).toFixed(5)}</span>
                  <span>Type: {trace.data?.agent_type || node?.data?.nodeType || 'agent'}</span>
                </div>

                {/* Output Snippet */}
                {trace.data?.output && (
                  <div style={{ background: '#09090b', borderRadius: 6, padding: '6px 10px', fontSize: 11 }}>
                    <div style={{ color: 'var(--text-muted)', fontSize: 10, marginBottom: 2 }}>Output Preview:</div>
                    <pre style={{ margin: 0, maxHeight: 60, overflow: 'hidden', textOverflow: 'ellipsis', color: '#e4e4e7', whiteSpace: 'pre-wrap' }}>
                      {typeof trace.data.output === 'string'
                        ? trace.data.output.slice(0, 180)
                        : JSON.stringify(trace.data.output).slice(0, 180)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
