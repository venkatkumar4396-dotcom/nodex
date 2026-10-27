/**
 * SettingsModal — In-app API Key and LLM Provider configuration.
 * Allows users to store and verify API keys for Moonshot, OpenAI, Anthropic, and Gemini.
 */
import { useState, useEffect } from 'react';
import useStore from '../store';
import { IconSettings, IconClose } from './Icons';

export default function SettingsModal() {
  const settingsModalOpen = useStore((s) => s.settingsModalOpen);
  const setSettingsModalOpen = useStore((s) => s.setSettingsModalOpen);
  const apiKeysStatus = useStore((s) => s.apiKeysStatus);
  const fetchApiKeysStatus = useStore((s) => s.fetchApiKeysStatus);
  const saveApiKeys = useStore((s) => s.saveApiKeys);
  const testApiKey = useStore((s) => s.testApiKey);
  const isTestingKey = useStore((s) => s.isTestingKey);

  const [openrouterKey, setOpenrouterKey] = useState('');
  const [openrouterBackupKey, setOpenrouterBackupKey] = useState('');
  const [openrouterTertiaryKey, setOpenrouterTertiaryKey] = useState('');
  const [moonshotKey, setMoonshotKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [anthropicKey, setAnthropicKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [defaultModel, setDefaultModel] = useState('openrouter/free');
  const [showKeys, setShowKeys] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [testingProvider, setTestingProvider] = useState(null);

  useEffect(() => {
    if (settingsModalOpen) {
      fetchApiKeysStatus();
    }
  }, [settingsModalOpen, fetchApiKeysStatus]);

  useEffect(() => {
    if (apiKeysStatus) {
      if (apiKeysStatus.default_model) {
        setDefaultModel(apiKeysStatus.default_model);
      }
    }
  }, [apiKeysStatus]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isSaving) {
        setSettingsModalOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSaving, setSettingsModalOpen]);

  if (!settingsModalOpen) return null;

  const handleSave = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    const payload = {
      default_model: defaultModel,
    };
    if (openrouterKey.trim()) payload.openrouter_api_key = openrouterKey.trim();
    if (openrouterBackupKey.trim()) payload.openrouter_api_key_backup = openrouterBackupKey.trim();
    if (openrouterTertiaryKey.trim()) payload.openrouter_api_key_tertiary = openrouterTertiaryKey.trim();
    if (moonshotKey.trim()) payload.moonshot_api_key = moonshotKey.trim();
    if (openaiKey.trim()) payload.openai_api_key = openaiKey.trim();
    if (anthropicKey.trim()) payload.anthropic_api_key = anthropicKey.trim();
    if (geminiKey.trim()) payload.gemini_api_key = geminiKey.trim();

    await saveApiKeys(payload);
    setIsSaving(false);
    setOpenrouterKey('');
    setOpenrouterBackupKey('');
    setOpenrouterTertiaryKey('');
    setMoonshotKey('');
    setOpenaiKey('');
    setAnthropicKey('');
    setGeminiKey('');
  };

  const handleTest = async (provider) => {
    setTestingProvider(provider);
    await testApiKey(provider);
    setTestingProvider(null);
  };

  return (
    <div className="af-modal-backdrop" onClick={() => !isSaving && setSettingsModalOpen(false)}>
      <div
        className="af-edge-modal"
        style={{ width: 620, maxWidth: '94vw', maxHeight: '90vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="af-modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <IconSettings size={18} />
              </div>
              <h2 className="af-modal-title">Settings & LLM API Keys</h2>
            </div>
            <p className="af-modal-subtitle">
              Manage your model provider credentials. Keys are encrypted and stored in runtime environment.
            </p>
          </div>
          <button
            className="af-close-btn"
            onClick={() => !isSaving && setSettingsModalOpen(false)}
            disabled={isSaving}
          >
            <IconClose size={13} />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
            
            {/* Show/Hide and Status Banner */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--text-muted)' }}>
                PROVIDER CREDENTIALS
              </span>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => setShowKeys(!showKeys)}
                style={{ fontSize: 11 }}
              >
                {showKeys ? 'Hide Keys' : 'Show Inputs'}
              </button>
            </div>

            {/* OpenRouter */}
            <div className="form-group" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <label className="form-label" style={{ marginBottom: 0 }}>
                  OpenRouter API Key (Active Primary)
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {apiKeysStatus?.openrouter_api_key_configured ? (
                    <span className="af-badge af-badge--completed" title={apiKeysStatus.openrouter_api_key_preview}>
                      Configured ({apiKeysStatus.openrouter_api_key_preview})
                    </span>
                  ) : (
                    <span className="af-badge af-badge--muted">Not Set</span>
                  )}
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    onClick={() => handleTest('openrouter')}
                    disabled={isTestingKey}
                    style={{ fontSize: 10, padding: '2px 6px' }}
                  >
                    {testingProvider === 'openrouter' ? 'Testing...' : 'Test Ping'}
                  </button>
                </div>
              </div>
              <input
                type={showKeys ? 'text' : 'password'}
                className="form-input"
                placeholder={apiKeysStatus?.openrouter_api_key_configured ? 'Enter new key to update...' : 'sk-or-v1-...'}
                value={openrouterKey}
                onChange={(e) => setOpenrouterKey(e.target.value)}
              />
            </div>

            {/* OpenRouter Backup Key (Auto-fallback) */}
            <div className="form-group" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <label className="form-label" style={{ marginBottom: 0 }}>
                  OpenRouter Backup Key (Auto-fallback on rate limits)
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {apiKeysStatus?.openrouter_api_key_backup_configured ? (
                    <span className="af-badge af-badge--completed" title={apiKeysStatus.openrouter_api_key_backup_preview}>
                      Configured ({apiKeysStatus.openrouter_api_key_backup_preview})
                    </span>
                  ) : (
                    <span className="af-badge af-badge--muted">Not Set</span>
                  )}
                </div>
              </div>
              <input
                type={showKeys ? 'text' : 'password'}
                className="form-input"
                placeholder={apiKeysStatus?.openrouter_api_key_backup_configured ? 'Enter backup key to update...' : 'sk-or-v1-...'}
                value={openrouterBackupKey}
                onChange={(e) => setOpenrouterBackupKey(e.target.value)}
              />
            </div>

            {/* OpenRouter 3rd Backup Key */}
            <div className="form-group" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <label className="form-label" style={{ marginBottom: 0 }}>
                  OpenRouter 3rd Key (Final fallback)
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {apiKeysStatus?.openrouter_api_key_tertiary_configured ? (
                    <span className="af-badge af-badge--completed" title={apiKeysStatus.openrouter_api_key_tertiary_preview}>
                      Configured ({apiKeysStatus.openrouter_api_key_tertiary_preview})
                    </span>
                  ) : (
                    <span className="af-badge af-badge--muted">Not Set</span>
                  )}
                </div>
              </div>
              <input
                type={showKeys ? 'text' : 'password'}
                className="form-input"
                placeholder={apiKeysStatus?.openrouter_api_key_tertiary_configured ? 'Enter 3rd backup key to update...' : 'sk-or-v1-...'}
                value={openrouterTertiaryKey}
                onChange={(e) => setOpenrouterTertiaryKey(e.target.value)}
              />
            </div>

            {/* Moonshot / Kimi */}
            <div className="form-group" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <label className="form-label" style={{ marginBottom: 0 }}>
                  Moonshot / Kimi AI API Key
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {apiKeysStatus?.moonshot_api_key_configured ? (
                    <span className="af-badge af-badge--completed" title={apiKeysStatus.moonshot_api_key_preview}>
                      Configured ({apiKeysStatus.moonshot_api_key_preview})
                    </span>
                  ) : (
                    <span className="af-badge af-badge--muted">Not Set</span>
                  )}
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    onClick={() => handleTest('moonshot')}
                    disabled={isTestingKey}
                    style={{ fontSize: 10, padding: '2px 6px' }}
                  >
                    {testingProvider === 'moonshot' ? 'Testing...' : 'Test Ping'}
                  </button>
                </div>
              </div>
              <input
                type={showKeys ? 'text' : 'password'}
                className="form-input"
                placeholder={apiKeysStatus?.moonshot_api_key_configured ? 'Enter new key to update...' : 'sk-...'}
                value={moonshotKey}
                onChange={(e) => setMoonshotKey(e.target.value)}
              />
            </div>

            {/* OpenAI */}
            <div className="form-group" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <label className="form-label" style={{ marginBottom: 0 }}>
                  OpenAI API Key
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {apiKeysStatus?.openai_api_key_configured ? (
                    <span className="af-badge af-badge--completed" title={apiKeysStatus.openai_api_key_preview}>
                      Configured ({apiKeysStatus.openai_api_key_preview})
                    </span>
                  ) : (
                    <span className="af-badge af-badge--muted">Not Set</span>
                  )}
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    onClick={() => handleTest('openai')}
                    disabled={isTestingKey}
                    style={{ fontSize: 10, padding: '2px 6px' }}
                  >
                    {testingProvider === 'openai' ? 'Testing...' : 'Test Ping'}
                  </button>
                </div>
              </div>
              <input
                type={showKeys ? 'text' : 'password'}
                className="form-input"
                placeholder={apiKeysStatus?.openai_api_key_configured ? 'Enter new key to update...' : 'sk-proj-...'}
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
              />
            </div>

            {/* Anthropic */}
            <div className="form-group" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <label className="form-label" style={{ marginBottom: 0 }}>
                  Anthropic Claude API Key
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {apiKeysStatus?.anthropic_api_key_configured ? (
                    <span className="af-badge af-badge--completed" title={apiKeysStatus.anthropic_api_key_preview}>
                      Configured ({apiKeysStatus.anthropic_api_key_preview})
                    </span>
                  ) : (
                    <span className="af-badge af-badge--muted">Not Set</span>
                  )}
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    onClick={() => handleTest('anthropic')}
                    disabled={isTestingKey}
                    style={{ fontSize: 10, padding: '2px 6px' }}
                  >
                    {testingProvider === 'anthropic' ? 'Testing...' : 'Test Ping'}
                  </button>
                </div>
              </div>
              <input
                type={showKeys ? 'text' : 'password'}
                className="form-input"
                placeholder={apiKeysStatus?.anthropic_api_key_configured ? 'Enter new key to update...' : 'sk-ant-...'}
                value={anthropicKey}
                onChange={(e) => setAnthropicKey(e.target.value)}
              />
            </div>

            {/* Google Gemini */}
            <div className="form-group" style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <label className="form-label" style={{ marginBottom: 0 }}>
                  Google Gemini API Key
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {apiKeysStatus?.gemini_api_key_configured ? (
                    <span className="af-badge af-badge--completed" title={apiKeysStatus.gemini_api_key_preview}>
                      Configured ({apiKeysStatus.gemini_api_key_preview})
                    </span>
                  ) : (
                    <span className="af-badge af-badge--muted">Not Set</span>
                  )}
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    onClick={() => handleTest('gemini')}
                    disabled={isTestingKey}
                    style={{ fontSize: 10, padding: '2px 6px' }}
                  >
                    {testingProvider === 'gemini' ? 'Testing...' : 'Test Ping'}
                  </button>
                </div>
              </div>
              <input
                type={showKeys ? 'text' : 'password'}
                className="form-input"
                placeholder={apiKeysStatus?.gemini_api_key_configured ? 'Enter new key to update...' : 'AIzaSy...'}
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
              />
            </div>

            {/* Default Studio Model */}
            <div className="form-group">
              <label className="form-label">Default Execution Model</label>
              <select
                className="form-select"
                value={defaultModel}
                onChange={(e) => setDefaultModel(e.target.value)}
              >
                <optgroup label="OpenRouter (Active Provider)">
                  <option value="openrouter/free">openrouter/free (Auto Free Tier - Recommended)</option>
                  <option value="openrouter/google/gemini-2.0-flash-exp:free">gemini-2.0-flash-exp:free</option>
                  <option value="openrouter/meta-llama/llama-3.2-3b-instruct:free">llama-3.2-3b-instruct:free</option>
                  <option value="openrouter/openai/gpt-4o-mini">openrouter/openai/gpt-4o-mini</option>
                  <option value="openrouter/anthropic/claude-3.5-sonnet">openrouter/anthropic/claude-3.5-sonnet</option>
                  <option value="openrouter/deepseek/deepseek-chat">openrouter/deepseek/deepseek-chat</option>
                </optgroup>
                <optgroup label="Moonshot AI">
                  <option value="moonshot/moonshot-v1-8k">moonshot-v1-8k (Fast)</option>
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
          </div>

          {/* Footer */}
          <div className="af-modal-footer" style={{ padding: '14px 24px', margin: 0, background: '#080808' }}>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setSettingsModalOpen(false)}
              disabled={isSaving}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn--primary" disabled={isSaving}>
              {isSaving ? 'Saving Keys...' : 'Save & Apply Keys'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
