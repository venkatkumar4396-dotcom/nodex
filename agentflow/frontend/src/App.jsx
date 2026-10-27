/**
 * App — root component that orchestrates the studio layout & modals.
 */
import { useEffect } from 'react';
import { ReactFlowProvider } from '@xyflow/react';

import Header from './components/Header';
import Sidebar from './components/Sidebar';
import Canvas from './components/Canvas';
import RightPanel from './components/RightPanel';
import WorkflowList from './components/WorkflowList';
import NodeInspectorModal from './components/NodeInspectorModal';
import EdgeInspectorModal from './components/EdgeInspectorModal';
import RunModal from './components/RunModal';
import TemplateModal from './components/TemplateModal';
import AiWorkflowModal from './components/AiWorkflowModal';
import BuildWithAiModal from './components/BuildWithAiModal';
import RunDoctorModal from './components/RunDoctorModal';
import TestStudioModal from './components/TestStudioModal';
import IntegrationBuilderModal from './components/IntegrationBuilderModal';
import PublishWorkflowModal from './components/PublishWorkflowModal';
import MarketplaceModal from './components/MarketplaceModal';
import AnalyticsModal from './components/AnalyticsModal';
import SettingsModal from './components/SettingsModal';
import HitlInboxModal from './components/HitlInboxModal';
import DeployModal from './components/DeployModal';
import ToastContainer from './components/ToastContainer';
import useStore from './store';

export default function App() {
  const view = useStore((s) => s.view);
  const undo = useStore((s) => s.undo);
  const redo = useStore((s) => s.redo);
  const theme = useStore((s) => s.theme);

  // Sync theme attribute with documentElement (default 'light')
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme || 'light');
  }, [theme]);

  // Global Ctrl+Z (Undo) and Ctrl+Y / Ctrl+Shift+Z (Redo)
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Don't intercept when user is typing in form inputs or textareas
      if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;

      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const cmdOrCtrl = isMac ? e.metaKey : e.ctrlKey;

      if (cmdOrCtrl && (e.key === 'z' || e.key === 'Z')) {
        e.preventDefault();
        if (e.shiftKey) {
          redo();
        } else {
          undo();
        }
      } else if (cmdOrCtrl && (e.key === 'y' || e.key === 'Y')) {
        e.preventDefault();
        redo();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo]);

  return (
    <ReactFlowProvider>
      <div className="app-layout">
        <Header />

        {view === 'home' ? (
          <WorkflowList />
        ) : (
          <div className="app-main">
            <Sidebar />
            <Canvas />
            <RightPanel />
          </div>
        )}

        {/* Global Modals & Notifications */}
        <NodeInspectorModal />
        <EdgeInspectorModal />
        <RunModal />
        <TemplateModal />
        <AiWorkflowModal />
        <BuildWithAiModal />
        <RunDoctorModal />
        <TestStudioModal />
        <IntegrationBuilderModal />
        <PublishWorkflowModal />
        <MarketplaceModal />
        <AnalyticsModal />
        <SettingsModal />
        <HitlInboxModal />
        <DeployModal />
        <ToastContainer />
      </div>
    </ReactFlowProvider>
  );
}
