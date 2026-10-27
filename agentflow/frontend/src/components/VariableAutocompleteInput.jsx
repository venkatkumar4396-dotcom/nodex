/**
 * VariableAutocompleteInput.jsx
 *
 * Real-time variable interpolation input & textarea with autocomplete dropdown.
 * Activates when the user types `{{` or clicks the inline variable picker chips,
 * allowing instant referencing of upstream node outputs and global inputs.
 */
import { useState, useRef, useEffect, useMemo } from 'react';
import useStore from '../store';
import { IconBolt, IconCheck, IconChevronDown } from './Icons';

export default function VariableAutocompleteInput({
  value = '',
  onChange,
  placeholder = '',
  rows = 4,
  id,
  name,
  className = 'form-textarea',
  nodeId = null,
  isSingleLine = false,
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [filterText, setFilterText] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [triggerPos, setTriggerPos] = useState(null);
  const [chipPickerOpen, setChipPickerOpen] = useState(false);

  const inputRef = useRef(null);
  const dropdownRef = useRef(null);

  const getAvailableVariables = useStore((s) => s.getAvailableVariables);
  const availableVariables = useMemo(() => {
    return getAvailableVariables ? getAvailableVariables(nodeId) : [];
  }, [getAvailableVariables, nodeId]);

  // Filter variables matching filter text
  const filteredVars = useMemo(() => {
    if (!filterText) return availableVariables;
    const q = filterText.toLowerCase();
    return availableVariables.filter(
      (v) =>
        v.variable.toLowerCase().includes(q) ||
        v.label.toLowerCase().includes(q) ||
        v.nodeName.toLowerCase().includes(q)
    );
  }, [availableVariables, filterText]);

  // Handle key navigation in dropdown
  const handleKeyDown = (e) => {
    if (dropdownOpen && filteredVars.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % filteredVars.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + filteredVars.length) % filteredVars.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertVariable(filteredVars[selectedIndex]?.variable || filteredVars[0]?.variable);
        return;
      }
      if (e.key === 'Escape') {
        setDropdownOpen(false);
        return;
      }
    }
  };

  const handleTextChange = (e) => {
    const val = e.target.value;
    onChange(e);

    const cursorPos = e.target.selectionStart;
    const textBeforeCursor = val.slice(0, cursorPos);
    const lastOpenBraces = textBeforeCursor.lastIndexOf('{{');

    if (lastOpenBraces !== -1) {
      const textAfterBraces = textBeforeCursor.slice(lastOpenBraces + 2);
      // Check if closing braces exist before cursor
      if (!textAfterBraces.includes('}}')) {
        setTriggerPos(lastOpenBraces);
        setFilterText(textAfterBraces.trim());
        setSelectedIndex(0);
        setDropdownOpen(true);
        return;
      }
    }

    setDropdownOpen(false);
  };

  const insertVariable = (variableStr) => {
    if (!inputRef.current) return;
    const currentVal = value || '';
    const el = inputRef.current;
    const cursorPos = el.selectionStart || currentVal.length;

    let newVal;
    let newCursor;

    if (triggerPos !== null && triggerPos >= 0) {
      const before = currentVal.slice(0, triggerPos);
      const after = currentVal.slice(cursorPos);
      newVal = `${before}{{${variableStr}}}${after}`;
      newCursor = triggerPos + variableStr.length + 4;
    } else {
      const before = currentVal.slice(0, cursorPos);
      const after = currentVal.slice(cursorPos);
      newVal = `${before}{{${variableStr}}}${after}`;
      newCursor = cursorPos + variableStr.length + 4;
    }

    onChange({ target: { name, value: newVal } });
    setDropdownOpen(false);
    setChipPickerOpen(false);
    setTriggerPos(null);

    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
        inputRef.current.setSelectionRange(newCursor, newCursor);
      }
    }, 10);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target) && !inputRef.current?.contains(e.target)) {
        setDropdownOpen(false);
        setChipPickerOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="af-autocomplete-wrapper" style={{ position: 'relative', width: '100%' }}>
      {isSingleLine ? (
        <input
          ref={inputRef}
          id={id}
          name={name}
          className={className}
          value={value}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
        />
      ) : (
        <textarea
          ref={inputRef}
          id={id}
          name={name}
          className={className}
          value={value}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={rows}
        />
      )}

      {/* Inline Variable Autocomplete Floating Dropdown */}
      {(dropdownOpen || chipPickerOpen) && filteredVars.length > 0 && (
        <div
          ref={dropdownRef}
          className="af-autocomplete-dropdown"
          style={{
            position: 'absolute',
            bottom: isSingleLine ? 'calc(100% + 4px)' : 'calc(100% + 4px)',
            left: 0,
            right: 0,
            maxHeight: 210,
            overflowY: 'auto',
            background: '#121319',
            border: '1px solid #282d3c',
            borderRadius: 7,
            boxShadow: '0 12px 36px rgba(0,0,0,0.85), 0 0 0 1px rgba(255,255,255,0.06)',
            zIndex: 1000,
            padding: 4,
          }}
        >
          <div
            style={{
              padding: '4px 8px',
              fontSize: 10,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: '#94a3b8',
              borderBottom: '1px solid #1e222d',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>Available Variables (Tab to select)</span>
            <span style={{ fontSize: 9, color: '#64748b' }}>ESC to close</span>
          </div>

          {filteredVars.map((v, idx) => (
            <div
              key={v.variable}
              className={`af-autocomplete-item ${idx === selectedIndex ? 'af-autocomplete-item--active' : ''}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 8px',
                borderRadius: 4,
                cursor: 'pointer',
                background: idx === selectedIndex ? 'rgba(99, 102, 241, 0.22)' : 'transparent',
                transition: 'background 0.1s ease',
              }}
              onMouseEnter={() => setSelectedIndex(idx)}
              onClick={() => insertVariable(v.variable)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                <span
                  style={{
                    fontSize: 9,
                    padding: '1px 5px',
                    borderRadius: 3,
                    background: v.isGlobal ? 'rgba(56, 189, 248, 0.2)' : 'rgba(168, 85, 247, 0.2)',
                    color: v.isGlobal ? '#38bdf8' : '#c084fc',
                    fontWeight: 700,
                  }}
                >
                  {v.isGlobal ? 'INPUT' : 'NODE'}
                </span>
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: 'var(--font-mono, monospace)',
                    color: '#e2e8f0',
                    fontWeight: 600,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {`{{${v.variable}}}`}
                </span>
              </div>
              <span
                style={{
                  fontSize: 11,
                  color: '#94a3b8',
                  marginLeft: 8,
                  whiteSpace: 'nowrap',
                }}
              >
                {v.nodeName}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Quick Insert Variable Chip Trigger */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
        <button
          type="button"
          className="af-chip-btn"
          style={{
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.09)',
            borderRadius: 4,
            padding: '2px 8px',
            fontSize: 10.5,
            color: 'var(--text-secondary, #94a3b8)',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            transition: 'all 0.15s ease',
          }}
          onClick={() => {
            setFilterText('');
            setSelectedIndex(0);
            setChipPickerOpen(!chipPickerOpen);
          }}
          title="Insert dynamic variable from upstream node or input"
        >
          <span style={{ color: '#818cf8', fontWeight: 700 }}>{'{{ }}'}</span>
          <span>Insert Variable</span>
          <IconChevronDown size={10} />
        </button>
      </div>
    </div>
  );
}
