// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import Modal from './Modal';
import './KeyboardShortcuts.css';

/**
 * KeyboardShortcuts Component
 * 
 * Displays keyboard shortcuts help panel
 * Press ? to open
 * Theme-aware styling
 */
const KeyboardShortcuts = () => {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handleKeyPress = (e) => {
      // Open shortcuts panel with ? or /
      if ((e.key === '?' || e.key === '/') && !e.target.matches('input, textarea')) {
        e.preventDefault();
        setIsOpen(true);
      }
    };

    document.addEventListener('keydown', handleKeyPress);
    return () => document.removeEventListener('keydown', handleKeyPress);
  }, []);

  const shortcuts = [
    {
      category: '🧭 Navigation',
      items: [
        { keys: ['Tab'], description: 'Move focus forward through interactive elements' },
        { keys: ['Shift', 'Tab'], description: 'Move focus backward' },
        { keys: ['Enter'], description: 'Activate buttons and links' },
        { keys: ['Space'], description: 'Toggle checkboxes and radio buttons' },
        { keys: ['Escape'], description: 'Close modals, dialogs, and dropdowns' },
      ]
    },
    {
      category: '⌨️ General',
      items: [
        { keys: ['?'], description: 'Show keyboard shortcuts help (this panel)' },
        { keys: ['/'], description: 'Show keyboard shortcuts help (alternate)' },
        { keys: ['Cmd', 'K'], description: 'Quick search (if implemented)' },
        { keys: ['Cmd', ','], description: 'Open settings (macOS convention)' },
      ]
    },
    {
      category: '📹 Dashboard',
      items: [
        { keys: ['1', '2', '3'], description: 'Switch between cameras' },
        { keys: ['R'], description: 'Start/stop recording' },
        { keys: ['F'], description: 'Toggle fullscreen (when focused on video)' },
        { keys: ['M'], description: 'Mute/unmute audio' },
      ]
    },
    {
      category: '♿ Accessibility',
      items: [
        { keys: ['Cmd', '+'], description: 'Zoom in (browser)' },
        { keys: ['Cmd', '-'], description: 'Zoom out (browser)' },
        { keys: ['Cmd', '0'], description: 'Reset zoom (browser)' },
        { keys: ['Ctrl', 'U'], description: 'View page source (for screen readers)' },
      ]
    }
  ];

  return (
    <>
      {/* Help icon button - always visible */}
      <button
        className="keyboard-shortcuts-trigger"
        onClick={() => setIsOpen(true)}
        aria-label="Show keyboard shortcuts"
        title="Keyboard shortcuts (Press ?)"
        type="button"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="2" y="4" width="16" height="12" rx="2" />
          <line x1="5" y1="8" x2="5" y2="8" strokeLinecap="round" />
          <line x1="8" y1="8" x2="8" y2="8" strokeLinecap="round" />
          <line x1="11" y1="8" x2="11" y2="8" strokeLinecap="round" />
          <line x1="5" y1="12" x2="15" y2="12" strokeLinecap="round" />
        </svg>
      </button>

      {/* Shortcuts Modal */}
      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="⌨️ Keyboard Shortcuts"
        size="lg"
      >
        <div className="keyboard-shortcuts-content">
          <p className="keyboard-shortcuts-intro">
            Use these keyboard shortcuts to navigate OpenEye more efficiently.
            Press <kbd>?</kbd> anytime to view this panel.
          </p>

          <div className="shortcuts-grid">
            {shortcuts.map((section, index) => (
              <div key={index} className="shortcuts-section">
                <h3 className="shortcuts-category">{section.category}</h3>
                <dl className="shortcuts-list">
                  {section.items.map((item, itemIndex) => (
                    <div key={itemIndex} className="shortcut-item">
                      <dt className="shortcut-keys">
                        {item.keys.map((key, keyIndex) => (
                          <React.Fragment key={keyIndex}>
                            <kbd className="key">{key}</kbd>
                            {keyIndex < item.keys.length - 1 && (
                              <span className="key-separator">+</span>
                            )}
                          </React.Fragment>
                        ))}
                      </dt>
                      <dd className="shortcut-description">{item.description}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>

          <div className="shortcuts-footer">
            <p>
              <strong>💡 Tip:</strong> Most shortcuts work when focus is not in a text input.
              For screen reader users, all functionality is also available through 
              standard navigation.
            </p>
          </div>
        </div>
      </Modal>
    </>
  );
};

/**
 * KeyboardShortcutIndicator - Shows shortcut hint next to buttons
 */
export const ShortcutHint = ({ keys, className = '' }) => (
  <span className={`shortcut-hint ${className}`}>
    {keys.map((key, index) => (
      <React.Fragment key={index}>
        <kbd className="key-small">{key}</kbd>
        {index < keys.length - 1 && <span className="key-separator-small">+</span>}
      </React.Fragment>
    ))}
  </span>
);

export default KeyboardShortcuts;
