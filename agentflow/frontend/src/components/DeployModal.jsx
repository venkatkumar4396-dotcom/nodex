/**
 * DeployModal — 1-Click Production Deployment Modal.
 *
 * Exposes production REST endpoint, webhook URL, API Key, and ready-to-copy
 * integration snippets (cURL, Python, JavaScript, and Embeddable Widget).
 */
import { useState } from 'react';
import useStore from '../store';
import { IconBolt, IconClose, IconCopy, IconCheck } from './Icons';

export default function DeployModal() {
  const deployModalOpen = useStore((s) => s.deployModalOpen);
  const setDeployModalOpen = useStore((s) => s.setDeployModalOpen);
  const deployDetail = useStore((s) => s.deployDetail);
  const addToast = useStore((s) => s.addToast);

  const [activeTab, setActiveTab] = useState('curl');
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedSnippet, setCopiedSnippet] = useState(false);

  if (!deployModalOpen || !deployDetail) return null;

  const copyToClipboard = (text, isKey = false) => {
    navigator.clipboard.writeText(text);
    if (isKey) {
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
      addToast('API Key copied to clipboard', 'success', 2000);
    } else {
      setCopiedSnippet(true);
      setTimeout(() => setCopiedSnippet(false), 2000);
      addToast('Snippet copied to clipboard', 'success', 2000);
    }
  };

  const getActiveCode = () => {
    switch (activeTab) {
      case 'curl':
        return deployDetail.curl_example;
      case 'python':
        return deployDetail.python_example;
      case 'js':
        return deployDetail.js_example;
      case 'widget':
        return deployDetail.widget_snippet;
      default:
        return deployDetail.curl_example;
    }
  };

  return (
    <div className="modal-backdrop" onClick={() => setDeployModalOpen(false)}>
      <div
        className="modal-card"
        style={{ maxWidth: 760, width: '92%', maxHeight: '88vh', display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <IconBolt size={18} />
            </div>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Deploy Workflow to Production</h2>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Target: {deployDetail.workflow_name}
              </div>
            </div>
          </div>
          <button className="btn btn--ghost btn--sm" onClick={() => setDeployModalOpen(false)}>
            <IconClose size={13} />
          </button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {/* Endpoint Details Box */}
          <div
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              padding: 14,
              marginBottom: 16,
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr auto', gap: 10, alignItems: 'center', marginBottom: 10 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>REST Endpoint:</span>
              <code style={{ fontSize: 12, color: '#38bdf8', wordBreak: 'break-all' }}>
                http://localhost:8000{deployDetail.endpoint_url}
              </code>
              <button
                className="btn btn--ghost btn--sm"
                onClick={() => copyToClipboard(`http://localhost:8000${deployDetail.endpoint_url}`)}
                title="Copy REST Endpoint"
              >
                <IconCopy size={13} />
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr auto', gap: 10, alignItems: 'center' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>API Token:</span>
              <code style={{ fontSize: 12, color: '#10b981', letterSpacing: '0.05em' }}>
                {deployDetail.api_key}
              </code>
              <button
                className="btn btn--ghost btn--sm"
                onClick={() => copyToClipboard(deployDetail.api_key, true)}
                title="Copy API Token"
              >
                {copiedKey ? <IconCheck size={13} /> : <IconCopy size={13} />}
              </button>
            </div>
          </div>

          {/* Snippet Tabs */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
            {[
              { id: 'curl', label: 'cURL' },
              { id: 'js', label: 'JavaScript / Fetch' },
              { id: 'python', label: 'Python Requests' },
              { id: 'widget', label: 'React / HTML Widget' },
            ].map((tab) => (
              <button
                key={tab.id}
                className={`btn btn--sm ${activeTab === tab.id ? 'btn--primary' : 'btn--ghost'}`}
                style={{ fontSize: 12 }}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Code Viewer */}
          <div style={{ position: 'relative' }}>
            <pre
              style={{
                background: '#09090b',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 8,
                padding: '14px 16px',
                fontSize: 12,
                color: '#e4e4e7',
                fontFamily: 'monospace',
                overflowX: 'auto',
                minHeight: 180,
                margin: 0,
              }}
            >
              {getActiveCode()}
            </pre>

            <button
              className="btn btn--ghost btn--sm"
              style={{ position: 'absolute', top: 8, right: 8, background: 'rgba(255,255,255,0.08)', display: 'inline-flex', alignItems: 'center', gap: 5 }}
              onClick={() => copyToClipboard(getActiveCode())}
            >
              {copiedSnippet ? <><IconCheck size={12} /> Copied</> : <><IconCopy size={12} /> Copy Code</>}
            </button>
          </div>
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
          <button className="btn btn--primary" onClick={() => setDeployModalOpen(false)}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
