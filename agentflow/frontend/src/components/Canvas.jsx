/**
 * Canvas — React Flow canvas with custom controls, directional arrows, and DAG management.
 */
import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import {
  ReactFlow,
  MiniMap,
  Background,
  BackgroundVariant,
  useReactFlow,
  MarkerType,
  ConnectionLineType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import AgentNode from './AgentNode';
import ApprovalBanner from './ApprovalBanner';
import ExecuteWorkflowButton from './ExecuteWorkflowButton';
import ExecutionDock from './ExecutionDock';
import useStore, { BUILTIN_TEMPLATES } from '../store';
import {
  IconBolt,
  IconSparkles,
  IconLayers,
  IconPlay,
  IconClose,
  IconSettings,
  IconZoomIn,
  IconZoomOut,
  IconMaximize,
  IconDownload,
  IconUpload,
  IconMap,
} from './Icons';

const nodeTypes = { agentNode: AgentNode };

export default function Canvas() {
  const reactFlowWrapper = useRef(null);
  const fileInputRef = useRef(null);

  const nodes = useStore((s) => s.nodes);
  const edges = useStore((s) => s.edges);
  const onNodesChange = useStore((s) => s.onNodesChange);
  const onEdgesChange = useStore((s) => s.onEdgesChange);
  const onConnect = useStore((s) => s.onConnect);
  const addNode = useStore((s) => s.addNode);
  const selectNode = useStore((s) => s.selectNode);
  const selectEdge = useStore((s) => s.selectEdge);
  const openEdgeModal = useStore((s) => s.openEdgeModal);
  const setActivePanel = useStore((s) => s.setActivePanel);
  const compactMode = useStore((s) => s.compactMode);
  const toggleCompactMode = useStore((s) => s.toggleCompactMode);
  const autoLayout = useStore((s) => s.autoLayout);
  const exportWorkflow = useStore((s) => s.exportWorkflow);
  const importWorkflow = useStore((s) => s.importWorkflow);
  const setAiModalOpen = useStore((s) => s.setAiModalOpen);
  const setBuildWithAiModalOpen = useStore((s) => s.setBuildWithAiModalOpen);
  const setTemplateModalOpen = useStore((s) => s.setTemplateModalOpen);
  const loadTemplate = useStore((s) => s.loadTemplate);
  const diagnoseRun = useStore((s) => s.diagnoseRun);
  const runStatus = useStore((s) => s.runStatus);
  const undo = useStore((s) => s.undo);
  const redo = useStore((s) => s.redo);
  const canUndo = useStore((s) => s.historyPast.length > 0);
  const canRedo = useStore((s) => s.historyFuture.length > 0);
  const executionDockOpen = useStore((s) => s.executionDockOpen);
  const executionDockFloating = useStore((s) => s.executionDockFloating);
  const setExecutionDockOpen = useStore((s) => s.setExecutionDockOpen);
  const runEvents = useStore((s) => s.runEvents);
  const showMiniMap = useStore((s) => s.showMiniMap);
  const toggleMiniMap = useStore((s) => s.toggleMiniMap);

  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const isDocked = executionDockOpen && !executionDockFloating;

  // Dynamic execution state syncing for React Flow edges
  const styledEdges = useMemo(() => {
    const nodeStatusMap = new Map(nodes.map((n) => [n.id, n.data?.status || 'idle']));
    return edges.map((e) => {
      const srcStatus = nodeStatusMap.get(e.source) || 'idle';
      const tgtStatus = nodeStatusMap.get(e.target) || 'idle';

      let strokeColor = '#6366f1';
      let isAnimated = false;
      let strokeDasharray = undefined;
      let opacity = 1;

      if (srcStatus === 'running') {
        strokeColor = '#38bdf8'; // Active electric cyan flow
        isAnimated = true;
        strokeDasharray = '5 5';
      } else if (tgtStatus === 'skipped') {
        strokeColor = '#64748b'; // Dead-path eliminated slate
        strokeDasharray = '4 4';
        opacity = 0.35;
      } else if (srcStatus === 'completed' || srcStatus === 'success') {
        strokeColor = '#10b981'; // Vibrant emerald satisfied flow
      } else if (srcStatus === 'failed') {
        strokeColor = '#ef4444'; // Crimson failed branch
      } else if (srcStatus === 'timed_out') {
        strokeColor = '#f59e0b'; // Amber timed-out branch
      }

      return {
        ...e,
        animated: isAnimated || Boolean(e.animated),
        style: {
          ...(e.style || {}),
          stroke: strokeColor,
          strokeWidth: isAnimated ? 2.5 : 2,
          strokeDasharray,
          opacity,
          transition: 'stroke 0.3s ease, opacity 0.3s ease',
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 16,
          height: 16,
          color: strokeColor,
        },
      };
    });
  }, [edges, nodes]);

  // Initial fit view with nice margin once canvas renders
  useEffect(() => {
    const timer = setTimeout(() => {
      fitView({ duration: 400, padding: 0.18 });
    }, 150);
    return () => clearTimeout(timer);
  }, [fitView]);

  // Handle drop from sidebar palette
  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      const data = event.dataTransfer.getData('application/agentflow-node');
      if (!data) return;

      const agentType = JSON.parse(data);
      const bounds = reactFlowWrapper.current?.getBoundingClientRect();
      if (!bounds) return;

      const position = {
        x: event.clientX - bounds.left - 130,
        y: event.clientY - bounds.top - 40,
      };

      const nodeId = addNode(
        agentType.type,
        agentType.label,
        agentType.color,
        agentType.icon,
        position
      );
      selectNode(nodeId);
      setActivePanel('config');
    },
    [addNode, selectNode, setActivePanel]
  );

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onNodeClick = useCallback(
    (_event, node) => {
      selectNode(node.id);
      setActivePanel('config');
    },
    [selectNode, setActivePanel]
  );

  const onEdgeClick = useCallback(
    (_event, edge) => {
      selectEdge(edge.id);
      setActivePanel('edge');
    },
    [selectEdge, setActivePanel]
  );

  const onEdgeDoubleClick = useCallback(
    (_event, edge) => {
      selectEdge(edge.id);
      openEdgeModal();
    },
    [selectEdge, openEdgeModal]
  );

  const onPaneClick = useCallback(() => {
    selectNode(null);
    selectEdge(null);
  }, [selectNode, selectEdge]);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      importWorkflow(evt.target.result);
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  return (
    <div className="canvas" ref={reactFlowWrapper}>
      {/* Hidden file input for import */}
      <input
        id="canvas-import-file-input"
        name="import_workflow_file"
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        accept=".json"
        onChange={handleFileChange}
      />

      {/* SVG definitions for custom connection arrows */}
      <svg style={{ position: 'absolute', width: 0, height: 0, pointerEvents: 'none' }}>
        <defs>
          <marker
            id="af-connecting-arrow"
            viewBox="0 0 10 10"
            refX="6"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 9 5 L 0 9 z" fill="#6366f1" />
          </marker>
        </defs>
      </svg>

      <ApprovalBanner />

      {/* Empty Canvas Quick-Start Guide */}
      {nodes.length === 0 && (
        <div className="af-empty-canvas">
          <div className="af-empty-canvas__card">
            <div className="af-empty-canvas__icon">
              <IconBolt size={26} />
            </div>
            <h2 className="af-empty-canvas__title">AgentFlow Visual Studio</h2>
            <p className="af-empty-canvas__desc">
              Design, orchestrate, and deploy multi-agent intelligence. Pick a quick action below or drag agent nodes from the left library.
            </p>
            <div className="af-empty-canvas__actions">
              <button
                type="button"
                className="af-empty-action-card"
                onClick={() => setBuildWithAiModalOpen(true)}
              >
                <span className="af-empty-action-card__icon">
                  <IconSparkles size={16} />
                </span>
                <span className="af-empty-action-card__title">Build with AI</span>
                <span className="af-empty-action-card__subtitle">Workflow Architect Meta-Agent</span>
              </button>
              <button
                type="button"
                className="af-empty-action-card"
                onClick={() => setTemplateModalOpen(true)}
              >
                <span className="af-empty-action-card__icon">
                  <IconLayers size={16} />
                </span>
                <span className="af-empty-action-card__title">Browse Templates</span>
                <span className="af-empty-action-card__subtitle">Curated production DAGs</span>
              </button>
              <button
                type="button"
                className="af-empty-action-card"
                onClick={() => loadTemplate(BUILTIN_TEMPLATES[0].key)}
              >
                <span className="af-empty-action-card__icon">
                  <IconPlay size={16} />
                </span>
                <span className="af-empty-action-card__title">Load Starter DAG</span>
                <span className="af-empty-action-card__subtitle">B2B Lead Outreach loop</span>
              </button>
            </div>
            <div className="af-empty-canvas__hint">
              <span className="af-empty-canvas__hint-icon">
                <IconSettings size={14} />
              </span>
              <span>Drag any agent from the Node Library on the left onto the canvas to start building manually.</span>
            </div>
          </div>
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={styledEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onEdgeDoubleClick={onEdgeDoubleClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        snapToGrid
        snapGrid={[16, 16]}
        deleteKeyCode={['Backspace', 'Delete']}
        connectionLineType={ConnectionLineType.SmoothStep}
        connectionLineStyle={{
          stroke: '#6366f1',
          strokeWidth: 2,
          strokeDasharray: '4 4',
          markerEnd: 'url(#af-connecting-arrow)',
        }}
        defaultEdgeOptions={{
          type: 'smoothstep',
          style: { stroke: '#6366f1', strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 18,
            height: 18,
            color: '#6366f1',
          },
        }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1.2}
          color="rgba(255, 255, 255, 0.06)"
        />

        {showMiniMap && (
          <MiniMap
            nodeColor={(n) => n.data?.color || '#6366f1'}
            maskColor="rgba(0, 0, 0, 0.88)"
            style={{
              background: '#0a0a0a',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 8,
            }}
            pannable
            zoomable
          />
        )}
      </ReactFlow>

      {/* Run Failure Doctor Banner */}
      {(runStatus === 'failed' || nodes.some((n) => n.data?.status === 'failed' || n.data?.status === 'timed_out' || n.data?.error)) && (
        <div
          style={{
            position: 'absolute',
            bottom: 70,
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'rgba(127, 29, 29, 0.95)',
            backdropFilter: 'blur(8px)',
            border: '1px solid #ef4444',
            borderRadius: 8,
            padding: '8px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            zIndex: 10,
            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          }}
        >
          <span style={{ fontSize: 13, color: '#fee2e2' }}>
            <strong>Run Failed:</strong> Error detected in workflow execution.
          </span>
          <button
            type="button"
            className="btn btn--sm"
            style={{ background: '#f87171', color: '#000', fontWeight: 700 }}
            onClick={() => diagnoseRun()}
          >
            Fix with AI (Run Doctor)
          </button>
        </div>
      )}

      {/* Floating Canvas Controls Toolbar */}
      <div className={`af-canvas-toolbar ${isDocked ? 'af-canvas-toolbar--docked' : ''}`}>
        <button
          className="af-canvas-btn"
          onClick={() => zoomIn({ duration: 250 })}
          title="Zoom In"
        >
          <IconZoomIn size={13} />
        </button>
        <button
          className="af-canvas-btn"
          onClick={() => zoomOut({ duration: 250 })}
          title="Zoom Out"
        >
          <IconZoomOut size={13} />
        </button>
        <button
          className="af-canvas-btn"
          onClick={() => fitView({ duration: 300, padding: 0.2 })}
          title="Fit to Screen"
        >
          <IconMaximize size={13} />
        </button>
        <div className="af-toolbar-divider" />
        <button
          className="af-canvas-btn"
          onClick={autoLayout}
          title="Auto-Layout / Format DAG cleanly (Dagre LR)"
        >
          Format
        </button>
        <button
          className="af-canvas-btn"
          onClick={toggleMiniMap}
          title="Toggle MiniMap"
          style={{ color: showMiniMap ? '#38bdf8' : 'inherit', opacity: showMiniMap ? 1 : 0.6 }}
        >
          <IconMap size={13} />
        </button>
        <button
          className="af-canvas-btn"
          onClick={toggleCompactMode}
          title={compactMode ? 'Standard Size' : 'Compact Size'}
          style={{ color: compactMode ? '#38bdf8' : 'inherit' }}
        >
          {compactMode ? 'Normal' : 'Compact'}
        </button>
        <div className="af-toolbar-divider" />
        <button
          className="af-canvas-btn"
          onClick={exportWorkflow}
          title="Export Workflow as JSON"
        >
          <IconDownload size={13} />
          <span>Export</span>
        </button>
        <button
          className="af-canvas-btn"
          onClick={() => fileInputRef.current?.click()}
          title="Import Workflow from JSON"
        >
          <IconUpload size={13} />
          <span>Import</span>
        </button>
      </div>

      {/* ── Bottom-Left Logs Toggle Button (Photo 1 & 2) ── */}
      <div className={`af-canvas-bottom-left ${isDocked ? 'af-canvas-bottom-left--docked' : ''}`}>
        <button
          type="button"
          className={`af-bottom-logs-btn ${executionDockOpen ? 'af-bottom-logs-btn--active' : ''}`}
          onClick={() => setExecutionDockOpen(!executionDockOpen)}
          title="Toggle Execution Logs & Output Dock"
        >
          <span className="af-dock-dot" />
          <span>Logs</span>
          {runEvents.length > 0 && (
            <span className="af-bottom-logs-badge">{runEvents.length}</span>
          )}
        </button>
      </div>

      {/* ── n8n-style Centered Bottom Execute Workflow Button (Photo 1 & 2) ── */}
      {nodes.length > 0 && <ExecuteWorkflowButton />}

      {/* ── n8n-style Bottom Execution Output Dock (Photo 2) ── */}
      <ExecutionDock />
    </div>
  );
}
