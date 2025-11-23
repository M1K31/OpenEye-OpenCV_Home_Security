// Copyright (c) 2025 Mikel Smart
// Universal Button Component - Apple HIG Compliant

import React from 'react';
import PropTypes from 'prop-types';
import './Button.css';

/**
 * Universal Button Component
 *
 * Follows Apple Human Interface Guidelines:
 * - Minimum 44x44px touch target
 * - Clear visual hierarchy
 * - Smooth animations
 * - Accessible by default
 *
 * @param {Object} props
 * @param {'primary'|'secondary'|'tertiary'|'destructive'} props.variant - Button style variant
 * @param {'small'|'medium'|'large'} props.size - Button size
 * @param {boolean} props.loading - Show loading state
 * @param {boolean} props.disabled - Disable button
 * @param {React.ReactNode} props.icon - Optional icon (left side)
 * @param {React.ReactNode} props.endIcon - Optional icon (right side)
 * @param {boolean} props.fullWidth - Take full width of container
 * @param {string} props.className - Additional CSS classes
 * @param {Function} props.onClick - Click handler
 * @param {React.ReactNode} props.children - Button label/content
 */
const Button = ({
  variant = 'primary',
  size = 'medium',
  loading = false,
  disabled = false,
  icon = null,
  endIcon = null,
  fullWidth = false,
  className = '',
  onClick,
  type = 'button',
  children,
  ...rest
}) => {
  const classNames = [
    'hig-button',
    `hig-button--${variant}`,
    `hig-button--${size}`,
    fullWidth && 'hig-button--full-width',
    loading && 'hig-button--loading',
    disabled && 'hig-button--disabled',
    className
  ].filter(Boolean).join(' ');

  const handleClick = (e) => {
    if (!disabled && !loading && onClick) {
      onClick(e);
    }
  };

  return (
    <button
      type={type}
      className={classNames}
      onClick={handleClick}
      disabled={disabled || loading}
      aria-disabled={disabled || loading}
      aria-busy={loading}
      {...rest}
    >
      {loading && (
        <span className="hig-button__loader" aria-hidden="true">
          <span className="hig-button__spinner"></span>
        </span>
      )}
      {!loading && icon && (
        <span className="hig-button__icon" aria-hidden="true">
          {icon}
        </span>
      )}
      <span className="hig-button__label">
        {children}
      </span>
      {!loading && endIcon && (
        <span className="hig-button__end-icon" aria-hidden="true">
          {endIcon}
        </span>
      )}
    </button>
  );
};

// PropTypes validation
Button.propTypes = {
  /** Button style variant */
  variant: PropTypes.oneOf(['primary', 'secondary', 'tertiary', 'destructive']),

  /** Button size */
  size: PropTypes.oneOf(['small', 'medium', 'large']),

  /** Show loading spinner */
  loading: PropTypes.bool,

  /** Disable button */
  disabled: PropTypes.bool,

  /** Optional icon on the left */
  icon: PropTypes.node,

  /** Optional icon on the right */
  endIcon: PropTypes.node,

  /** Take full width of container */
  fullWidth: PropTypes.bool,

  /** Additional CSS classes */
  className: PropTypes.string,

  /** Click event handler */
  onClick: PropTypes.func,

  /** Button type attribute */
  type: PropTypes.oneOf(['button', 'submit', 'reset']),

  /** Button label/content */
  children: PropTypes.node.isRequired,
};

// Default props
Button.defaultProps = {
  variant: 'primary',
  size: 'medium',
  loading: false,
  disabled: false,
  icon: null,
  endIcon: null,
  fullWidth: false,
  className: '',
  onClick: undefined,
  type: 'button',
};

export default Button;
