/**
 * MarketplaceModal — Full AgentFlow Marketplace
 * Features:
 *   - Search & filtering (category, risk badge, tags)
 *   - Rich template cards with runs, rating, cost per run, risk level
 *   - Template detail modal:
 *     - 1-Click Install with credential input prompts (replaces placeholders)
 *     - Sandbox test run with sample data before installing
 *     - Fork & Remix
 *     - Star rating submission
 *     - Security Red-Team & QA Evaluator certified badges
 */
import { useState, useEffect } from 'react';
import useStore from '../store';
import { IconLayers, IconClose, IconSearch, IconStar, IconShield, IconSparkles } from './Icons';

const CATEGORIES = ['All', 'Sales', 'Engineering', 'Monitoring', 'Autonomous', 'E-commerce', 'DevOps'];
const RISK_FILTERS = ['All', 'Low', 'Medium', 'High'];

export default function MarketplaceModal() {
  const isOpen = useStore((s) => s.marketplaceModalOpen);
  const setIsOpen = useStore((s) => s.setMarketplaceModalOpen);
  const templates = useStore((s) => s.marketplaceTemplates);
  const isLoading = useStore((s) => s.marketplaceLoading);
  const fetchTemplates = useStore((s) => s.fetchMarketplaceTemplates);
  const installTemplate = useStore((s) => s.installMarketplaceTemplate);
  const runSandboxTest = useStore((s) => s.runSandboxTest);
  const sandboxResult = useStore((s) => s.sandboxResult);
  const isSandboxRunning = useStore((s) => s.sandboxLoading);
  const forkTemplate = useStore((s) => s.forkMarketplaceTemplate);
  const rateTemplate = useStore((s) => s.rateMarketplaceTemplate);

  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [selectedRisk, setSelectedRisk] = useState('All');
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'credentials' | 'sandbox'
  const [userCredentials, setUserCredentials] = useState({});
  const [userRating, setUserRating] = useState(5);

  useEffect(() => {
    if (isOpen) {
      fetchTemplates();
    }
  }, [isOpen, fetchTemplates]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (selectedTemplate) setSelectedTemplate(null);
        else setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedTemplate, setIsOpen]);

  if (!isOpen) return null;

  const filteredTemplates = templates.filter((tpl) => {
    const matchesSearch =
      !search ||
      tpl.title.toLowerCase().includes(search.toLowerCase()) ||
      tpl.description.toLowerCase().includes(search.toLowerCase()) ||
      (tpl.tags || []).some((t) => t.toLowerCase().includes(search.toLowerCase()));

    const matchesCat =
      selectedCategory === 'All' ||
      (tpl.categories || []).some((c) => c.toLowerCase() === selectedCategory.toLowerCase());

    const matchesRisk =
      selectedRisk === 'All' || tpl.risk_level.toLowerCase() === selectedRisk.toLowerCase();

    return matchesSearch && matchesCat && matchesRisk;
  });

  const handleSelectTemplate = (tpl) => {
    setSelectedTemplate(tpl);
    setActiveTab('overview');
    // Pre-populate credential placeholders
    const credMap = {};
    (tpl.credentials_needed || []).forEach((c) => {
      credMap[c] = '';
    });
    setUserCredentials(credMap);
  };

  const handleInstall = async () => {
    if (!selectedTemplate) return;
    await installTemplate(selectedTemplate.id, userCredentials, selectedTemplate.title);
  };

  const handleRunSandbox = async () => {
    if (!selectedTemplate) return;
    await runSandboxTest(selectedTemplate.id, selectedTemplate.sample_inputs);
  };

  const handleFork = async () => {
    if (!selectedTemplate) return;
    await forkTemplate(selectedTemplate.id);
  };

  const handleRate = async () => {
    if (!selectedTemplate) return;
    await rateTemplate(selectedTemplate.id, userRating);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="flex flex-col w-full max-w-5xl h-[88vh] bg-surface-900 border border-surface-700/80 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-700/60 bg-gradient-to-r from-blue-900/30 via-surface-850 to-purple-900/20">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xl font-bold shadow-sm">
              <IconLayers size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white">AgentFlow Marketplace</h2>
                <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-500/20 text-emerald-300 rounded-full border border-emerald-500/30 flex items-center gap-1">
                  <IconShield size={11} /> Certified Safe DAGs
                </span>
              </div>
              <p className="text-xs text-surface-400">
                Community & verified multi-agent templates with 1-click install, sandbox dry-run, and security audits
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="p-1.5 text-surface-400 hover:text-white rounded-lg hover:bg-surface-700/50 transition-colors"
          >
            <IconClose size={14} />
          </button>
        </div>

        {/* Content Area */}
        <div className="flex flex-1 overflow-hidden">
          {/* Main Catalog View (or Left Column) */}
          <div className="flex-1 flex flex-col overflow-hidden border-r border-surface-700/60">
            {/* Search and Filters */}
            <div className="p-4 border-b border-surface-700/60 bg-surface-850/50 space-y-3">
              <div className="flex items-center gap-3">
                <div className="relative flex-1">
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search workflows, agents, keywords (e.g. lead, scraper, github)..."
                    className="w-full pl-9 pr-3.5 py-2 rounded-xl bg-surface-800 border border-surface-700 text-white text-xs focus:outline-none focus:border-blue-500 transition-colors"
                  />
                  <span className="absolute left-3 top-2.5 text-surface-400 text-xs flex items-center">
                    <IconSearch size={12} />
                  </span>
                </div>
                {/* Risk Filter */}
                <div className="flex items-center gap-1 text-xs text-surface-400">
                  <span>Risk:</span>
                  <select
                    value={selectedRisk}
                    onChange={(e) => setSelectedRisk(e.target.value)}
                    className="bg-surface-800 border border-surface-700 rounded-lg px-2 py-1 text-surface-200 text-xs focus:outline-none"
                  >
                    {RISK_FILTERS.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Category Pills */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={`px-3 py-1 rounded-lg font-medium whitespace-nowrap transition-colors ${
                      selectedCategory === cat
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'bg-surface-800 text-surface-400 hover:text-surface-200 hover:bg-surface-750'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            {/* Template Cards Grid */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {filteredTemplates.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-surface-400 text-xs">
                  <span>No templates match your criteria.</span>
                </div>
              ) : (
                filteredTemplates.map((tpl) => (
                  <div
                    key={tpl.id}
                    onClick={() => handleSelectTemplate(tpl)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                      selectedTemplate?.id === tpl.id
                        ? 'bg-blue-950/30 border-blue-500 shadow-md shadow-blue-900/20'
                        : 'bg-surface-800/80 hover:bg-surface-800 border-surface-700 hover:border-surface-600'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-bold text-white hover:text-blue-400 transition-colors">
                            {tpl.title}
                          </h3>
                          <span className="text-[10px] font-mono text-surface-400 bg-surface-900 px-1.5 py-0.5 rounded">
                            v{tpl.version}
                          </span>
                        </div>
                        <p className="text-xs text-blue-300/90 mt-0.5 font-medium">{tpl.tagline}</p>
                      </div>

                      {/* Risk Badge */}
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider shrink-0 border ${
                          tpl.risk_level === 'low'
                            ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                            : tpl.risk_level === 'medium'
                            ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                            : 'bg-rose-500/10 text-rose-300 border-rose-500/30'
                        }`}
                      >
                        {tpl.risk_level} Risk
                      </span>
                    </div>

                    <p className="text-xs text-surface-400 mt-2 line-clamp-2">{tpl.description}</p>

                    {/* Metadata Badges */}
                    <div className="flex items-center justify-between mt-3 pt-2.5 border-t border-surface-700/60 text-[11px] text-surface-400">
                      <div className="flex items-center gap-3">
                        <span className="flex items-center gap-1 text-amber-400 font-semibold">
                          <IconStar size={11} fill="currentColor" /> {tpl.rating} <span className="text-surface-500 font-normal">({tpl.rating_count})</span>
                        </span>
                        <span>{tpl.run_count} runs</span>
                        <span>{tpl.fork_count} forks</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-cyan-400 font-mono">{tpl.cost_estimate}</span>
                        <span className="text-surface-500">•</span>
                        <span className="text-surface-300">{tpl.author}</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right Column: Template Detail & Action Panel */}
          {selectedTemplate ? (
            <div className="w-[420px] flex flex-col overflow-hidden bg-surface-850/80">
              {/* Detail Tabs */}
              <div className="flex items-center gap-2 px-4 pt-3 border-b border-surface-700/60 bg-surface-850 text-xs">
                <button
                  onClick={() => setActiveTab('overview')}
                  className={`pb-2 px-2.5 font-medium transition-colors border-b-2 ${
                    activeTab === 'overview'
                      ? 'border-blue-500 text-blue-400'
                      : 'border-transparent text-surface-400 hover:text-surface-200'
                  }`}
                >
                  Overview
                </button>
                <button
                  onClick={() => setActiveTab('credentials')}
                  className={`pb-2 px-2.5 font-medium transition-colors border-b-2 ${
                    activeTab === 'credentials'
                      ? 'border-blue-500 text-blue-400'
                      : 'border-transparent text-surface-400 hover:text-surface-200'
                  }`}
                >
                  Credentials ({selectedTemplate.credentials_needed?.length || 0})
                </button>
                <button
                  onClick={() => setActiveTab('sandbox')}
                  className={`pb-2 px-2.5 font-medium transition-colors border-b-2 ${
                    activeTab === 'sandbox'
                      ? 'border-blue-500 text-blue-400'
                      : 'border-transparent text-surface-400 hover:text-surface-200'
                  }`}
                >
                  Sandbox Run
                </button>
              </div>

              {/* Detail Body */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
                {activeTab === 'overview' && (
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-sm font-bold text-white">{selectedTemplate.title}</h3>
                      <p className="text-xs text-blue-400 mt-0.5">{selectedTemplate.tagline}</p>
                      <p className="text-xs text-surface-300 mt-2">{selectedTemplate.description}</p>
                    </div>

                    {/* Dual Quality Gate Badges */}
                    <div className="grid grid-cols-2 gap-2">
                      <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/30">
                        <div className="text-[10px] uppercase font-bold text-purple-400">Security Red-Team</div>
                        <div className="text-sm font-bold text-white mt-0.5 flex items-center gap-1.5">
                          <IconShield size={13} className="text-purple-400" /> {selectedTemplate.security_score}/100
                        </div>
                      </div>
                      <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30">
                        <div className="text-[10px] uppercase font-bold text-cyan-400">QA Evaluator</div>
                        <div className="text-sm font-bold text-white mt-0.5 flex items-center gap-1.5">
                          <IconSparkles size={13} className="text-cyan-400" /> {selectedTemplate.evaluation_score}/5.0
                        </div>
                      </div>
                    </div>

                    {/* Inputs & Outputs */}
                    <div className="space-y-2">
                      <div className="text-[11px] font-bold text-surface-400 uppercase">Input Requirements</div>
                      <div className="p-2.5 rounded-lg bg-surface-900 border border-surface-800 space-y-1">
                        {(selectedTemplate.inputs_schema || []).map((inp, idx) => (
                          <div key={idx} className="flex justify-between font-mono text-[11px]">
                            <span className="text-cyan-300">{inp.name}</span>
                            <span className="text-surface-500">{inp.type}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* External Actions & Safety */}
                    <div className="p-3 rounded-lg bg-surface-900 border border-surface-800 space-y-1.5">
                      <div className="text-[11px] font-bold text-surface-400 uppercase">Safety & Permissions</div>
                      <div className="text-surface-300">
                        External Actions: {(selectedTemplate.external_actions || []).join(', ') || 'None'}
                      </div>
                      {(selectedTemplate.safety_concerns || []).map((c, i) => (
                        <div key={i} className="text-surface-400 text-[11px]">
                          • {c}
                        </div>
                      ))}
                    </div>

                    {/* Rating Submission */}
                    <div className="p-3 rounded-lg bg-surface-800/80 border border-surface-700 flex items-center justify-between">
                      <span className="text-surface-300">Rate this workflow:</span>
                      <div className="flex items-center gap-1">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <button
                            key={star}
                            onClick={() => setUserRating(star)}
                            className={`p-1 ${userRating >= star ? 'text-amber-400' : 'text-surface-600'}`}
                          >
                            <IconStar size={13} fill={userRating >= star ? 'currentColor' : 'none'} />
                          </button>
                        ))}
                        <button
                          onClick={handleRate}
                          className="ml-2 px-2 py-0.5 rounded bg-surface-700 hover:bg-surface-600 text-white text-[10px] font-semibold"
                        >
                          Submit
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === 'credentials' && (
                  <div className="space-y-3">
                    <p className="text-xs text-surface-400">
                      Supply credentials now to auto-bind them upon install, or leave blank to keep{' '}
                      <code className="text-cyan-400 font-mono">{'{{credentials.NAME}}'}</code> placeholders.
                    </p>
                    {(selectedTemplate.credentials_needed || []).length === 0 ? (
                      <div className="p-4 rounded-xl bg-surface-900 text-center text-surface-400">
                        No external credentials required! Zero setup needed.
                      </div>
                    ) : (
                      selectedTemplate.credentials_needed.map((cred) => (
                        <div key={cred}>
                          <label className="block text-xs font-mono font-semibold text-surface-300 mb-1">
                            {cred}
                          </label>
                          <input
                            type="password"
                            value={userCredentials[cred] || ''}
                            onChange={(e) =>
                              setUserCredentials({ ...userCredentials, [cred]: e.target.value })
                            }
                            placeholder={`Enter ${cred} or leave blank`}
                            className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-surface-700 text-white text-xs font-mono focus:outline-none focus:border-blue-500"
                          />
                        </div>
                      ))
                    )}
                  </div>
                )}

                {activeTab === 'sandbox' && (
                  <div className="space-y-3">
                    <p className="text-xs text-surface-400">
                      Test-run this workflow with isolated mock data before mounting it on your canvas.
                    </p>
                    <button
                      onClick={handleRunSandbox}
                      disabled={isSandboxRunning}
                      className="w-full py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold flex items-center justify-center gap-2 shadow-sm"
                    >
                      {isSandboxRunning ? (
                        <>
                          <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          <span>Simulating Sandbox Run...</span>
                        </>
                      ) : (
                        <span>Execute Sandbox Dry-Run</span>
                      )}
                    </button>

                    {sandboxResult && (
                      <div className="p-3 rounded-xl bg-surface-900 border border-surface-800 space-y-2">
                        <div className="flex items-center justify-between text-[11px] font-bold text-emerald-400">
                          <span>Status: Completed</span>
                          <span>Nodes: {sandboxResult.total_nodes_simulated}</span>
                        </div>
                        <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                          {(sandboxResult.execution_trace || []).map((tr, idx) => (
                            <div key={idx} className="p-2 rounded bg-surface-800/60 border border-surface-750 text-[10px]">
                              <div className="flex justify-between font-bold text-white">
                                <span>{tr.label} [{tr.type}]</span>
                                <span className="text-cyan-400">{tr.duration_ms}ms</span>
                              </div>
                              <p className="text-surface-400 mt-0.5">{tr.output?.message}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="p-4 border-t border-surface-700/60 bg-surface-850 space-y-2">
                <button
                  onClick={handleInstall}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-bold shadow-md shadow-blue-900/30 flex items-center justify-center gap-2 transition-all"
                >
                  <span>1-Click Install to Canvas</span>
                </button>
                <div className="flex gap-2">
                  <button
                    onClick={handleFork}
                    className="flex-1 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-750 border border-surface-700 text-surface-200 text-xs font-semibold flex items-center justify-center gap-1 transition-colors"
                  >
                    <span>Fork & Remix</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="w-[320px] flex flex-col items-center justify-center p-6 text-center text-surface-500 text-xs border-l border-surface-800">
              <IconLayers size={28} className="text-surface-600 mb-2" />
              <span>Select any template on the left to preview details, test in sandbox, or 1-click install.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
