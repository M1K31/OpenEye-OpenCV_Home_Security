/*
Copyright (c) 2025 Mikel Smart
This file is part of OpenEye-OpenCV_Home_Security
*/

import React from 'react';
import './ErrorBoundary.css';
import { logger } from '../utils/logger';

/**
 * Error Boundary Component
 *
 * Catches JavaScript errors anywhere in the child component tree,
 * logs those errors, and displays a fallback UI instead of crashing.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <YourComponent />
 *   </ErrorBoundary>
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0
    };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log error details for debugging
    logger.error('ErrorBoundary caught an error:', error, errorInfo);

    this.setState(prevState => ({
      error,
      errorInfo,
      errorCount: prevState.errorCount + 1
    }));

    // You can also log the error to an error reporting service here
    // Example: logErrorToService(error, errorInfo);
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      // Fallback UI
      return (
        <div className="error-boundary">
          <div className="error-boundary-container">
            <div className="error-boundary-icon">⚠️</div>
            <h1 className="error-boundary-title">Oops! Something went wrong</h1>
            <p className="error-boundary-message">
              {this.props.fallbackMessage || "We're sorry, but something unexpected happened. Please try again."}
            </p>

            {this.state.error && (
              <details className="error-boundary-details">
                <summary>Error Details</summary>
                <div className="error-boundary-stack">
                  <strong>Error:</strong> {this.state.error.toString()}
                  <br />
                  <br />
                  <strong>Stack Trace:</strong>
                  <pre>{this.state.errorInfo?.componentStack}</pre>
                </div>
              </details>
            )}

            <div className="error-boundary-actions">
              <button onClick={this.handleReset} className="btn-reset">
                Try Again
              </button>
              <button onClick={this.handleReload} className="btn-reload">
                Reload Page
              </button>
              <button
                onClick={() => window.history.back()}
                className="btn-back"
              >
                Go Back
              </button>
            </div>

            {this.state.errorCount > 2 && (
              <p className="error-boundary-warning">
                ⚠️ This error has occurred {this.state.errorCount} times.
                You may need to clear your browser cache or contact support.
              </p>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
