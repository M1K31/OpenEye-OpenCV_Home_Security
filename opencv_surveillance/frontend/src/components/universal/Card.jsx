// Copyright (c) 2025 Mikel Smart
// Universal Card Component - Apple HIG Compliant

import React from 'react';
import PropTypes from 'prop-types';
import './Card.css';

/**
 * Universal Card Component
 *
 * Follows Apple Human Interface Guidelines:
 * - Rounded corners (16px)
 * - Subtle elevation
 * - Smooth hover transitions
 * - Optional header/footer
 *
 * @param {Object} props
 * @param {'standard'|'interactive'|'elevated'} props.variant - Card style variant
 * @param {boolean} props.clickable - Make card clickable
 * @param {Function} props.onClick - Click handler (for clickable cards)
 * @param {React.ReactNode} props.header - Optional card header
 * @param {React.ReactNode} props.footer - Optional card footer
 * @param {boolean} props.loading - Show loading skeleton
 * @param {boolean} props.fullWidth - Take full width
 * @param {string} props.className - Additional CSS classes
 * @param {React.ReactNode} props.children - Card content
 */
const Card = ({
  variant = 'standard',
  clickable = false,
  onClick,
  header = null,
  footer = null,
  loading = false,
  fullWidth = false,
  className = '',
  children,
  ...rest
}) => {
  const isInteractive = clickable || onClick;

  const classNames = [
    'hig-card',
    `hig-card--${variant}`,
    isInteractive && 'hig-card--interactive',
    loading && 'hig-card--loading',
    fullWidth && 'hig-card--full-width',
    className
  ].filter(Boolean).join(' ');

  const handleClick = (e) => {
    if (isInteractive && onClick) {
      onClick(e);
    }
  };

  const handleKeyPress = (e) => {
    if (isInteractive && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onClick?.(e);
    }
  };

  const CardElement = isInteractive ? 'button' : 'div';

  return (
    <CardElement
      className={classNames}
      onClick={isInteractive ? handleClick : undefined}
      onKeyPress={isInteractive ? handleKeyPress : undefined}
      tabIndex={isInteractive ? 0 : undefined}
      role={isInteractive ? 'button' : undefined}
      {...rest}
    >
      {loading && (
        <div className="hig-card__loading-overlay" aria-live="polite" aria-busy="true">
          <div className="hig-card__spinner"></div>
        </div>
      )}

      {header && (
        <div className="hig-card__header">
          {header}
        </div>
      )}

      <div className="hig-card__content">
        {children}
      </div>

      {footer && (
        <div className="hig-card__footer">
          {footer}
        </div>
      )}
    </CardElement>
  );
};

/**
 * Card Header Component
 * Pre-styled header for cards
 */
export const CardHeader = ({ title, subtitle, action, className = '' }) => (
  <div className={`hig-card-header ${className}`}>
    <div className="hig-card-header__content">
      {title && <h3 className="hig-card-header__title">{title}</h3>}
      {subtitle && <p className="hig-card-header__subtitle">{subtitle}</p>}
    </div>
    {action && (
      <div className="hig-card-header__action">
        {action}
      </div>
    )}
  </div>
);

/**
 * Card Footer Component
 * Pre-styled footer for cards
 */
export const CardFooter = ({ children, className = '', align = 'right' }) => (
  <div className={`hig-card-footer hig-card-footer--${align} ${className}`}>
    {children}
  </div>
);

// PropTypes validation - Card
Card.propTypes = {
  /** Card style variant */
  variant: PropTypes.oneOf(['standard', 'interactive', 'elevated']),

  /** Make card clickable */
  clickable: PropTypes.bool,

  /** Click event handler */
  onClick: PropTypes.func,

  /** Optional card header */
  header: PropTypes.node,

  /** Optional card footer */
  footer: PropTypes.node,

  /** Show loading state */
  loading: PropTypes.bool,

  /** Take full width of container */
  fullWidth: PropTypes.bool,

  /** Additional CSS classes */
  className: PropTypes.string,

  /** Card content */
  children: PropTypes.node.isRequired,
};

Card.defaultProps = {
  variant: 'standard',
  clickable: false,
  onClick: undefined,
  header: null,
  footer: null,
  loading: false,
  fullWidth: false,
  className: '',
};

// PropTypes validation - CardHeader
CardHeader.propTypes = {
  /** Header title */
  title: PropTypes.string,

  /** Header subtitle */
  subtitle: PropTypes.string,

  /** Action button/element */
  action: PropTypes.node,

  /** Additional CSS classes */
  className: PropTypes.string,
};

CardHeader.defaultProps = {
  title: undefined,
  subtitle: undefined,
  action: undefined,
  className: '',
};

// PropTypes validation - CardFooter
CardFooter.propTypes = {
  /** Footer content */
  children: PropTypes.node.isRequired,

  /** Additional CSS classes */
  className: PropTypes.string,

  /** Footer alignment */
  align: PropTypes.oneOf(['left', 'center', 'right']),
};

CardFooter.defaultProps = {
  className: '',
  align: 'right',
};

export default Card;
