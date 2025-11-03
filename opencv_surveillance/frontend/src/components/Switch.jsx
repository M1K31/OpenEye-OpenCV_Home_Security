// Copyright (c) 2025 Mikel Smart
// Universal Switch Component - Apple HIG Compliant

import React from 'react';
import './Switch.css';

/**
 * Universal Switch Component (iOS-style Toggle)
 *
 * Follows Apple Human Interface Guidelines:
 * - Minimum 44px touch target
 * - Clear on/off visual states
 * - Smooth animations
 * - Theme-aware colors
 *
 * @param {Object} props
 * @param {boolean} props.checked - Current state of the switch
 * @param {Function} props.onChange - Callback when switch is toggled (receives boolean)
 * @param {boolean} props.disabled - Whether the switch is disabled
 * @param {string} props.label - Optional label text
 * @param {'default'|'success'|'destructive'} props.color - Color variant
 * @param {'small'|'medium'} props.size - Switch size
 * @param {string} props.id - Optional ID for the input
 * @param {string} props.className - Additional CSS classes
 */
const Switch = ({
  checked = false,
  onChange,
  disabled = false,
  label = '',
  color = 'default',
  size = 'medium',
  id = '',
  className = '',
  ...props
}) => {
  const switchId = id || `switch-${Math.random().toString(36).substr(2, 9)}`;

  const handleChange = (e) => {
    if (!disabled && onChange) {
      onChange(e.target.checked);
    }
  };

  const handleKeyPress = (e) => {
    if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onChange?.(!checked);
    }
  };

  const classNames = [
    'hig-switch',
    `hig-switch--${size}`,
    `hig-switch--${color}`,
    checked && 'hig-switch--checked',
    disabled && 'hig-switch--disabled',
    className
  ].filter(Boolean).join(' ');

  return (
    <label className={classNames} htmlFor={switchId}>
      <span className="hig-switch__container">
        <input
          id={switchId}
          type="checkbox"
          className="hig-switch__input"
          checked={checked}
          onChange={handleChange}
          onKeyPress={handleKeyPress}
          disabled={disabled}
          role="switch"
          aria-checked={checked}
          aria-label={label || 'Toggle switch'}
          {...props}
        />
        <span className="hig-switch__track">
          <span className="hig-switch__thumb"></span>
        </span>
      </span>
      {label && <span className="hig-switch__label">{label}</span>}
    </label>
  );
};

export default Switch;
