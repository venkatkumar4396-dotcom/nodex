/**
 * ExecuteWorkflowButton — n8n-style centered bottom execution control.
 *
 * Matches n8n visual design:
 *   - Bold coral/orange-red pill button docked at canvas bottom center
 *   - Primary action: "Execute workflow"
 *   - Subtitle: "from <Trigger Node Name>"
 *   - Right action split button: configure inputs / cancel / test options
 */
import { useState, useRef, useEffect } from 'react';
import useStore from '../store';
import {
  IconBolt,
  IconPause,
  IconStop,
  IconChevronDown,
  IconSettings,
  IconChart,
} from './Icons';

export default function ExecuteWorkflowButton() {
  const triggerRun = useStore((s) => s.triggerRun);
  const cancelRun = useStore((s) => s.cancelRun);
  const runStatus = useStore((s) => s.runStatus);
  const nodes = useStore((s) => s.nodes);
  const setRunModalOpen = useStore((s) => s.setRunModalOpen);
  const executionDockOpen = useStore((s) => s.executionDockOpen);
  const executionDockFloating = useStore((s) => s.executionDockFloating);
  const setExecutionDockOpen = useStore((s) => s.setExecutionDockOpen);

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  const isRunning = runStatus === 'running';
  const isPaused = runStatus === 'paused';

  // Find primary trigger node for subtitle ("from Manual Test Trigger")
  const triggerNode = nodes.find(
    (n) =>
      n.data?.nodeType?.startsWith('trigger_') ||
      n.id.toLowerCase().includes('trigger') ||
      (n.data?.label && n.data.label.toLowerCase().includes('trigger'))
  );
  const triggerLabel = triggerNode?.data?.label || 'Manual Test Trigger';

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpen]);

  const handleExecute = (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (isRunning) return;
    triggerRun();
  };

  return (
    <div
      className={`af-execute-wrapper ${
        executionDockOpen && !executionDockFloating ? 'af-execute-wrapper--docked' : ''
      }`}
      ref={menuRef}
    >
      <div className={`af-execute-btn-group ${isRunning ? 'af-execute-btn-group--running' : ''}`}>
        {/* Main Execute Button */}
        <button
          type="button"
          className="af-execute-main-btn"
          onClick={handleExecute}
          disabled={isRunning || nodes.length === 0}
          title={
            nodes.length === 0
              ? 'Add nodes to the canvas to execute'
              : `Execute workflow from ${triggerLabel}`
          }
        >
          <span className="af-execute-icon">
            {isRunning ? (
              <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
            ) : isPaused ? (
              <IconPause size={14} />
            ) : (
              <IconBolt size={14} />
            )}
          </span>
          <div className="af-execute-text-col">
            <span className="af-execute-title">
              {isRunning
                ? 'Executing workflow...'
                : isPaused
                ? 'Awaiting Approval'
                : 'Execute workflow'}
            </span>
            <span className="af-execute-subtitle" title={`Starting from ${triggerLabel}`}>
              {isRunning ? 'Running DAG nodes...' : `from ${triggerLabel}`}
            </span>
          </div>
        </button>

        {/* Right Split Button / Options Chevron */}
        <button
          type="button"
          className="af-execute-dropdown-btn"
          onClick={() => setMenuOpen(!menuOpen)}
          title="Run options and parameters"
        >
          <span className={`af-execute-chevron ${menuOpen ? 'af-execute-chevron--open' : ''}`}>
            <IconChevronDown size={11} />
          </span>
        </button>

        {/* Cancel button if actively running */}
        {isRunning && (
          <button
            type="button"
            className="af-execute-cancel-btn"
            onClick={cancelRun}
            title="Cancel execution"
          >
            <IconStop size={12} /> Stop
          </button>
        )}
      </div>

      {/* Popover Options Menu */}
      {menuOpen && (
        <div className="af-execute-menu">
          <button
            type="button"
            className="af-execute-menu-item"
            onClick={() => {
              setMenuOpen(false);
              setRunModalOpen(true);
            }}
          >
            <span className="af-execute-menu-item-icon">
              <IconSettings size={15} />
            </span>
            <div>
              <div className="af-execute-menu-item-title">Configure Test Inputs</div>
              <div className="af-execute-menu-item-desc">Set JSON trigger payload and mock variables</div>
            </div>
          </button>

          <button
            type="button"
            className="af-execute-menu-item"
            onClick={() => {
              setMenuOpen(false);
              setExecutionDockOpen(!executionDockOpen);
            }}
          >
            <span className="af-execute-menu-item-icon">
              <IconChart size={15} />
            </span>
            <div>
              <div className="af-execute-menu-item-title">
                {executionDockOpen ? 'Hide Execution Output Dock' : 'Show Execution Output Dock'}
              </div>
              <div className="af-execute-menu-item-desc">View node inputs, outputs, and execution metrics</div>
            </div>
          </button>

          {isRunning && (
            <button
              type="button"
              className="af-execute-menu-item af-execute-menu-item--danger"
              onClick={() => {
                setMenuOpen(false);
                cancelRun();
              }}
            >
              <span className="af-execute-menu-item-icon">
                <IconStop size={15} />
              </span>
              <div>
                <div className="af-execute-menu-item-title">Cancel Execution</div>
                <div className="af-execute-menu-item-desc">Halt active workflow run</div>
              </div>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
