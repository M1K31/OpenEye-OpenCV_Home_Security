// Copyright (c) 2025 Mikel Smart
// Universal TextField Component - Apple HIG Compliant

import React, { useState, useRef } from 'react';
import './TextField.css';

/**
 * Universal TextField Component
 *
 * Follows Apple Human Interface Guidelines:
 * - Minimum 44px height
 * - Clear focus states
 * - Helper text support
 * - Error handling
 * - Accessible labels
 *
 * @param {Object} props
 * @param {'text'|'password'|'email'|'number'|'search'|'tel'|'url'} props.type - Input type
 * @param {string} props.label - Input label
 * @param {string} props.placeholder - Placeholder text
 * @param {string} props.value - Controlled value
 * @param {Function} props.onChange - Change handler
 * @param {boolean} props.error - Error state
 * @param {string} props.helperText - Helper/error text
 * @param {boolean} props.disabled - Disable input
 * @param {boolean} props.required - Mark as required
 * @param {boolean} props.fullWidth - Take full width
 * @param {React.ReactNode} props.startIcon - Icon at start
 * @param {React.ReactNode} props.endIcon - Icon at end
 * @param {boolean} props.showPasswordToggle - Show/hide password toggle
 * @param {number} props.maxLength - Character limit
 * @param {boolean} props.showCharCount - Show character counter
 */
const TextField = ({
  type = 'text',
  label,
  placeholder,
  value,
  onChange,
  error = false,
  helperText,
  disabled = false,
  required = false,
  fullWidth = false,
  startIcon = null,
  endIcon = null,
  showPasswordToggle = false,
  maxLength,
  showCharCount = false,
  className = '',
  id,
  name,
  ...rest
}) => {
  const [showPassword, setShowPassword] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef(null);

  const inputId = id || `textfield-${Math.random().toString(36).substr(2, 9)}`;
  const inputType = (type === 'password' && showPassword) ? 'text' : type;

  const isSearch = type === 'search';
  const hasStartIcon = startIcon || isSearch;
  const hasEndIcon = endIcon || (showPasswordToggle && type === 'password') || showCharCount;

  const classNames = [
    'hig-textfield',
    fullWidth && 'hig-textfield--full-width',
    error && 'hig-textfield--error',
    disabled && 'hig-textfield--disabled',
    isFocused && 'hig-textfield--focused',
    isSearch && 'hig-textfield--search',
    className
  ].filter(Boolean).join(' ');

  const handleChange = (e) => {
    if (onChange) {
      onChange(e);
    }
  };

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
    // Re-focus input after toggle
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  return (
    <div className={classNames}>
      {label && (
        <label htmlFor={inputId} className="hig-textfield__label">
          {label}
          {required && <span className="hig-textfield__required" aria-label="required">*</span>}
        </label>
      )}

      <div className="hig-textfield__input-wrapper">
        {hasStartIcon && (
          <div className="hig-textfield__start-icon" aria-hidden="true">
            {isSearch ? (
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M9 17A8 8 0 1 0 9 1a8 8 0 0 0 0 16zM18 18l-4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            ) : startIcon}
          </div>
        )}

        <input
          ref={inputRef}
          id={inputId}
          name={name}
          type={inputType}
          value={value}
          onChange={handleChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          maxLength={maxLength}
          aria-invalid={error}
          aria-describedby={helperText ? `${inputId}-helper` : undefined}
          className="hig-textfield__input"
          {...rest}
        />

        {hasEndIcon && (
          <div className="hig-textfield__end-icon">
            {showPasswordToggle && type === 'password' && (
              <button
                type="button"
                onClick={togglePasswordVisibility}
                className="hig-textfield__password-toggle"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                tabIndex={-1}
              >
                {showPassword ? (
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <path d="M2 2l16 16M10 12a2 2 0 1 1 0-4 2 2 0 0 1 0 4z" stroke="currentColor" strokeWidth="2"/>
                    <path d="M10 5C4 5 1 10 1 10s3 5 9 5 9-5 9-5-3-5-9-5z" stroke="currentColor" strokeWidth="2"/>
                  </svg>
                ) : (
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <circle cx="10" cy="10" r="2" stroke="currentColor" strokeWidth="2"/>
                    <path d="M10 5C4 5 1 10 1 10s3 5 9 5 9-5 9-5-3-5-9-5z" stroke="currentColor" strokeWidth="2"/>
                  </svg>
                )}
              </button>
            )}
            {showCharCount && maxLength && (
              <span className="hig-textfield__char-count" aria-live="polite">
                {(value || '').length}/{maxLength}
              </span>
            )}
            {endIcon && !showCharCount && endIcon}
          </div>
        )}
      </div>

      {helperText && (
        <div
          id={`${inputId}-helper`}
          className={`hig-textfield__helper ${error ? 'hig-textfield__helper--error' : ''}`}
          role={error ? 'alert' : 'status'}
        >
          {helperText}
        </div>
      )}
    </div>
  );
};

export default TextField;
