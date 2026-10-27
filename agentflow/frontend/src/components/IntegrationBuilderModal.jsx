/**
 * IntegrationBuilderModal — Integration Builder (#2)
 * Generates custom connectors from API docs / OpenAPI specs and registers them as tools.
 */
import { useState, useEffect } from 'react';
import useStore from '../store';
import { IconLayers, IconClose } from './Icons';

const PRESET_APIS = [
  {
    icon: 'support_swarm',
    name: 'Slack Messages API',
    goal: 'Send notifications and formatted messages to Slack channels with bot token.',
    docs: `POST https://slack.com/api/chat.postMessage
Authorization: Bearer <SLACK_BOT_TOKEN>
Content-Type: application/json

Body parameters:
- channel (string, required): Channel ID or name (e.g. C1234567890 or #general)
- text (string, required): Main fallback text message
- blocks (array of objects, optional): Block Kit structured UI blocks

Response:
{
  "ok": true,
  "channel": "C1234567890",
  "ts": "1503435956.000247",
  "message": { "text": "Hello world" }
}

Errors: 429 rate limit with Retry-After header, 500 internal server error.`,
  },
  {
    icon: 'finance',
    name: 'Stripe Customer Search',
    goal: 'Search customers by email and retrieve active subscription metadata.',
    docs: `GET https://api.stripe.com/v1/customers/search
Authorization: Bearer <STRIPE_API_KEY>

Query parameters:
- query (string, required): Search query formatted as key:value, e.g. "email:'user@example.com'"
- limit (integer, optional, default 10): Number of results (max 100)
- page (string, optional): Pagination cursor

Response:
{
  "object": "search_result",
  "data": [
    {
      "id": "cus_123456",
      "email": "user@example.com",
      "name": "Jane Doe",
      "currency": "usd",
      "created": 1600000000
    }
  ],
  "has_more": false
}`,
  },
  {
    icon: 'github',
    name: 'GitHub Create Issue',
    goal: 'Create an issue on a GitHub repository when a workflow error occurs.',
    docs: `POST https://api.github.com/repos/{owner}/{repo}/issues
Authorization: Bearer <GITHUB_TOKEN>
Accept: application/vnd.github+json

Body parameters:
- title (string, required): The title of the issue
- body (string, optional): The contents of the issue in markdown
- labels (array of strings, optional): Labels to associate with this issue
- assignees (array of strings, optional): User logins to assign

Response 201 Created:
{
  "id": 1,
  "node_id": "MDU6SXNzdWUx",
  "url": "https://api.github.com/repos/octocat/Hello-World/issues/1347",
  "number": 1347,
  "state": "open",
  "title": "Found a bug"
}`,
  },
];

export default function IntegrationBuilderModal() {
  const isOpen = useStore((s) => s.integrationBuilderModalOpen);
  const setIsOpen = useStore((s) => s.setIntegrationBuilderModalOpen);
  const isBuilding = useStore((s) => s.integrationLoading);
  const result = useStore((s) => s.integrationResult);
  const buildIntegration = useStore((s) => s.buildIntegration);
  const registerConnectorAsTools = useStore((s) => s.registerConnectorAsTools);

  const [goal, setGoal] = useState('');
  const [apiDocs, setApiDocs] = useState('');
  const [activeTab, setActiveTab] = useState('input'); // 'input' | 'actions' | 'tests' | 'json'

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isBuilding) setIsOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isBuilding, setIsOpen]);

  if (!isOpen) return null;

  const handlePreset = (preset) => {
    setGoal(preset.goal);
    setApiDocs(preset.docs);
  };

  const handleBuild = async (e) => {
    e?.preventDefault();
    if (!goal.trim() || !apiDocs.trim() || isBuilding) return;
    const res = await buildIntegration(apiDocs.trim(), goal.trim());
    if (res) setActiveTab('actions');
  };

  const handleRegister = async () => {
    if (!result) return;
    await registerConnectorAsTools(result);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="flex flex-col w-full max-w-4xl max-h-[90vh] bg-surface-900 border border-surface-700/80 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-700/60 bg-surface-850/60">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 font-bold shadow-sm">
              <IconLayers size={20} className="text-cyan-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white">Integration Builder</h2>
                <span className="px-2 py-0.5 text-xs font-semibold bg-cyan-500/20 text-cyan-300 rounded-full border border-cyan-500/30">
                  Agent #2
                </span>
              </div>
              <p className="text-xs text-surface-400">
                Paste API docs or OpenAPI spec &rarr; Instant custom tool connector with retry policies & security guards
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            disabled={isBuilding}
            className="p-1.5 text-surface-400 hover:text-white rounded-lg hover:bg-surface-700/50 transition-colors"
          >
            <IconClose size={13} />
          </button>
        </div>

        {/* Tab switcher */}
        <div className="flex items-center gap-2 px-6 pt-3 border-b border-surface-700/60 bg-surface-850/30 text-xs">
          <button
            onClick={() => setActiveTab('input')}
            className={`pb-2.5 px-3 font-medium transition-colors border-b-2 ${
              activeTab === 'input'
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-surface-400 hover:text-surface-200'
            }`}
          >
            Specification & Goal
          </button>
          {result && (
            <>
              <button
                onClick={() => setActiveTab('actions')}
                className={`pb-2.5 px-3 font-medium transition-colors border-b-2 ${
                  activeTab === 'actions'
                    ? 'border-cyan-500 text-cyan-400'
                    : 'border-transparent text-surface-400 hover:text-surface-200'
                }`}
              >
                Actions ({result.actions?.length || 0})
              </button>
              <button
                onClick={() => setActiveTab('tests')}
                className={`pb-2.5 px-3 font-medium transition-colors border-b-2 ${
                  activeTab === 'tests'
                    ? 'border-cyan-500 text-cyan-400'
                    : 'border-transparent text-surface-400 hover:text-surface-200'
                }`}
              >
                Test Cases ({result.tests?.length || 0})
              </button>
              <button
                onClick={() => setActiveTab('json')}
                className={`pb-2.5 px-3 font-medium transition-colors border-b-2 ${
                  activeTab === 'json'
                    ? 'border-cyan-500 text-cyan-400'
                    : 'border-transparent text-surface-400 hover:text-surface-200'
                }`}
              >
                Raw Connector JSON
              </button>
            </>
          )}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {activeTab === 'input' && (
            <div className="space-y-5">
              {/* Presets */}
              <div>
                <label className="block text-xs font-semibold text-surface-300 uppercase tracking-wider mb-2">
                  Try Quick Presets
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {PRESET_APIS.map((p) => (
                    <button
                      key={p.name}
                      type="button"
                      onClick={() => handlePreset(p)}
                      className="p-3 text-left rounded-xl bg-surface-800/80 hover:bg-surface-750 border border-surface-700 hover:border-cyan-500/50 transition-all group"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-base">{p.icon}</span>
                        <span className="text-xs font-semibold text-white group-hover:text-cyan-400 transition-colors">
                          {p.name}
                        </span>
                      </div>
                      <p className="text-[11px] text-surface-400 line-clamp-2">{p.goal}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Goal Input */}
              <div>
                <label className="block text-xs font-semibold text-surface-300 mb-1">
                  What do your agents need to do with this API? <span className="text-cyan-400">*</span>
                </label>
                <input
                  type="text"
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  placeholder="e.g. Send customer notifications, search CRM records, create GitHub issues"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-surface-800 border border-surface-700 text-white text-sm focus:outline-none focus:border-cyan-500 transition-colors"
                />
              </div>

              {/* API Docs Textarea */}
              <div>
                <label className="block text-xs font-semibold text-surface-300 mb-1">
                  API Documentation / OpenAPI Specification / Curl Snippets <span className="text-cyan-400">*</span>
                </label>
                <textarea
                  rows={8}
                  value={apiDocs}
                  onChange={(e) => setApiDocs(e.target.value)}
                  placeholder="Paste endpoints, parameters, sample responses, and auth headers here..."
                  className="w-full px-3.5 py-2.5 rounded-xl bg-surface-800 border border-surface-700 text-white text-xs font-mono focus:outline-none focus:border-cyan-500 transition-colors resize-none"
                />
              </div>
            </div>
          )}

          {activeTab === 'actions' && result && (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-xl bg-surface-800/80 border border-surface-700">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>Connector:</span>
                    <span className="font-mono text-cyan-400">{result.connector_name}</span>
                  </h3>
                  <p className="text-xs text-surface-400 mt-0.5">
                    Base URL: <code className="text-surface-300">{result.base_url || 'https://api.example.com'}</code> • Auth: <span className="text-cyan-300">{result.auth?.type || 'Bearer'}</span>
                  </p>
                </div>
                <button
                  onClick={handleRegister}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-bold shadow-md shadow-cyan-900/30 flex items-center gap-1.5 transition-all"
                >
                  <span>Register as Executable Tools</span>
                </button>
              </div>

              {/* Action List */}
              <div className="space-y-3">
                {(result.actions || []).map((action, idx) => (
                  <div
                    key={action.name || idx}
                    className="p-4 rounded-xl bg-surface-800/60 border border-surface-700/80 space-y-2.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <span
                          className={`px-2 py-0.5 text-[11px] font-bold rounded ${
                            action.method === 'GET'
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                              : action.method === 'POST'
                              ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                              : action.method === 'DELETE'
                              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                              : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                          }`}
                        >
                          {action.method}
                        </span>
                        <span className="text-sm font-bold text-white font-mono">{action.name}</span>
                        <code className="text-xs text-surface-400">{action.path}</code>
                      </div>
                      {action.destructive && (
                        <span className="px-2 py-0.5 text-[10px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 rounded-full flex items-center gap-1">
                          Destructive Write
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-surface-300">{action.description}</p>

                    {/* Parameters schema */}
                    <div className="p-2.5 rounded-lg bg-surface-900/60 border border-surface-800">
                      <div className="text-[10px] font-semibold text-surface-400 uppercase tracking-wider mb-1">
                        Parameters JSON Schema
                      </div>
                      <pre className="text-[11px] text-cyan-300/90 font-mono overflow-x-auto">
                        {JSON.stringify(action.args_schema, null, 2)}
                      </pre>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'tests' && result && (
            <div className="space-y-3">
              {(result.tests || []).map((test, idx) => (
                <div key={idx} className="p-4 rounded-xl bg-surface-800/60 border border-surface-700/80 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-white">
                    <span className="text-cyan-400">Action:</span>
                    <code className="font-mono bg-surface-900 px-2 py-0.5 rounded text-cyan-300">{test.action}</code>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-2.5 rounded-lg bg-surface-900/60 border border-surface-800">
                      <div className="text-[10px] font-semibold text-surface-400 uppercase mb-1">Sample Input</div>
                      <pre className="text-[11px] text-surface-200 font-mono overflow-x-auto">
                        {JSON.stringify(test.sample_input, null, 2)}
                      </pre>
                    </div>
                    <div className="p-2.5 rounded-lg bg-surface-900/60 border border-surface-800">
                      <div className="text-[10px] font-semibold text-surface-400 uppercase mb-1">Expected Output Shape</div>
                      <pre className="text-[11px] text-surface-200 font-mono overflow-x-auto">
                        {JSON.stringify(test.expected_output_shape, null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'json' && result && (
            <div className="p-4 rounded-xl bg-surface-900 border border-surface-800">
              <pre className="text-xs text-cyan-300 font-mono overflow-x-auto max-h-[500px]">
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-surface-700/60 bg-surface-850/60">
          <div className="text-xs text-surface-400">
            {isBuilding ? 'Synthesizing connector with strict safety guards...' : 'Ready to generate.'}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              disabled={isBuilding}
              className="px-4 py-2 rounded-xl text-xs font-medium text-surface-300 hover:text-white hover:bg-surface-800 transition-colors"
            >
              Close
            </button>
            <button
              type="button"
              onClick={handleBuild}
              disabled={!goal.trim() || !apiDocs.trim() || isBuilding}
              className="px-5 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-xs font-bold shadow-md shadow-cyan-900/30 flex items-center gap-2 transition-all"
            >
              {isBuilding ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Synthesizing Connector...</span>
                </>
              ) : (
                <>
                  <span>Synthesize Connector</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
