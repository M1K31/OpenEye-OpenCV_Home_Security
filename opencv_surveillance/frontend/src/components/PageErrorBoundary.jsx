/*
Copyright (c) 2025 Mikel Smart
This file is part of OpenEye-OpenCV_Home_Security
*/

import React from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { logger } from '../utils/logger';
import './PageErrorBoundary.css';

/**
 * Page-Level Error Boundary Component
 *
 * A lightweight error boundary optimized for individual pages.
 * Unlike the root ErrorBoundary, this allows navigation to other pages
 * and provides page-specific recovery options.
 *
 * Features:
 * - Isolates errors to specific pages
 * - Allows navigation to other pages
 * - Provides "Go Home" and "Retry" options
 * - Logs errors without crashing entire app
 *
 * Usage:
 *   <PageErrorBoundary pageName="Dashboard">
 *     <DashboardPage />
 *   </PageErrorBoundary>
 */
class PageErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log error details for debugging
    logger.error(`PageErrorBoundary caught error in ${this.props.pageName}:`, error, errorInfo);

    this.setState({
      error,
      errorInfo,
    });

    // Optionally send to error reporting service
    // Example: logErrorToService(error, errorInfo, { page: this.props.pageName });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  handleGoHome = () => {
    // Reset error state and navigate home
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });

    // Use navigate if available (passed via props)
    if (this.props.onNavigateHome) {
      this.props.onNavigateHome();
    } else {
      window.location.href = '/';
    }
  };

  render() {
    if (this.state.hasError) {
      const pageName = this.props.pageName || 'Page';

      // Compact fallback UI for page-level errors
      return (
        <div className="page-error-boundary">
          <div className="page-error-container">
            <div className="page-error-icon">⚠️</div>
            <h2 className="page-error-title">Unable to load {pageName}</h2>
            <p className="page-error-message">
              {this.props.fallbackMessage ||
                `We encountered an error while loading this page. Your other pages should still work normally.`}
            </p>

            {/* Error details (collapsible) */}
            {this.state.error && this.props.showDetails && (
              <details className="page-error-details">
                <summary>Technical Details</summary>
                <div className="page-error-stack">
                  <p><strong>Error:</strong> {this.state.error.toString()}</p>
                  {this.state.errorInfo?.componentStack && (
                    <>
                      <p><strong>Component Stack:</strong></p>
                      <pre>{this.state.errorInfo.componentStack}</pre>
                    </>
                  )}
                </div>
              </details>
            )}

            {/* Recovery actions */}
            <div className="page-error-actions">
              <button onClick={this.handleReset} className="btn-retry">
                Try Again
              </button>
              <button onClick={this.handleGoHome} className="btn-home">
                Go to Dashboard
              </button>
              {window.history.length > 1 && (
                <button
                  onClick={() => window.history.back()}
                  className="btn-back"
                >
                  Go Back
                </button>
              )}
            </div>

            {/* Optional support message */}
            {this.props.supportMessage && (
              <p className="page-error-support">
                {this.props.supportMessage}
              </p>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// PropTypes validation - PageErrorBoundary
PageErrorBoundary.propTypes = {
  /** Page name for error message */
  pageName: PropTypes.string,

  /** Child components to render */
  children: PropTypes.node.isRequired,

  /** Custom fallback error message */
  fallbackMessage: PropTypes.string,

  /** Show technical error details (for development) */
  showDetails: PropTypes.bool,

  /** Optional support/contact message */
  supportMessage: PropTypes.string,

  /** Callback when navigating home */
  onNavigateHome: PropTypes.func,
};

PageErrorBoundary.defaultProps = {
  pageName: 'Page',
  fallbackMessage: undefined,
  showDetails: false,
  supportMessage: undefined,
  onNavigateHome: undefined,
};

/**
 * Functional wrapper for PageErrorBoundary with React Router support
 *
 * Usage:
 *   <PageErrorBoundaryWithRouter pageName="Dashboard">
 *     <DashboardPage />
 *   </PageErrorBoundaryWithRouter>
 */
export function PageErrorBoundaryWithRouter({ children, ...props }) {
  const navigate = useNavigate();

  return (
    <PageErrorBoundary
      {...props}
      onNavigateHome={() => navigate('/')}
    >
      {children}
    </PageErrorBoundary>
  );
}

// PropTypes validation - PageErrorBoundaryWithRouter
PageErrorBoundaryWithRouter.propTypes = {
  /** Page name for error message */
  pageName: PropTypes.string,

  /** Child components to render */
  children: PropTypes.node.isRequired,

  /** Custom fallback error message */
  fallbackMessage: PropTypes.string,

  /** Show technical error details (for development) */
  showDetails: PropTypes.bool,

  /** Optional support/contact message */
  supportMessage: PropTypes.string,
};

PageErrorBoundaryWithRouter.defaultProps = {
  pageName: 'Page',
  fallbackMessage: undefined,
  showDetails: false,
  supportMessage: undefined,
};

export default PageErrorBoundary;
