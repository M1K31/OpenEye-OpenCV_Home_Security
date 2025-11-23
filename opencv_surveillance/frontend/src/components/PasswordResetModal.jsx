// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect, useRef, useCallback } from 'react';
import apiClient from '../api/apiClient';
import './Modal.css';

/**
 * Password Reset Modal with 2FA Verification
 *
 * Design: Follows Apple Human Interface Guidelines
 * - 44px minimum touch targets
 * - 8pt grid system spacing
 * - Theme-aware CSS variables
 * - Accessibility (focus trap, ARIA labels, keyboard navigation)
 *
 * Security Features:
 * - Only allows password reset for users with 2FA enabled
 * - Requires valid TOTP code from authenticator app
 * - Multi-step verification process
 * - All tokens revoked after password change
 */
const PasswordResetModal = ({ isOpen, onClose }) => {
  const [step, setStep] = useState(1); // 1: username, 2: totp + password, 3: success
  const [username, setUsername] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const modalRef = useRef(null);
  const previousFocusRef = useRef(null);

  // Reset modal state
  const resetModal = () => {
    setStep(1);
    setUsername('');
    setTotpCode('');
    setNewPassword('');
    setConfirmPassword('');
    setError('');
    setMessage('');
    setLoading(false);
  };

  // Handle close
  const handleClose = () => {
    resetModal();
    onClose();
  };

  // Focus trap and keyboard handling
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      handleClose();
      return;
    }

    if (e.key === 'Tab' && modalRef.current) {
      const focusableElements = modalRef.current.querySelectorAll(
        'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'
      );
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    }
  }, []);

  // Focus management
  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement;
      document.body.style.overflow = 'hidden';
      document.addEventListener('keydown', handleKeyDown);

      setTimeout(() => {
        modalRef.current?.focus();
      }, 100);
    } else {
      if (previousFocusRef.current && previousFocusRef.current.focus) {
        previousFocusRef.current.focus();
      }
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, handleKeyDown]);

  // Step 1: Check if user has 2FA enabled
  const handleCheckUsername = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await apiClient.post('/auth/check-2fa-status', {
        username: username.trim()
      });

      if (response.data.two_factor_enabled) {
        setMessage(response.data.message);
        setStep(2); // Proceed to TOTP + password step
      } else {
        setError(response.data.message);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Error checking username. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Reset password with TOTP verification
  const handleResetPassword = async (e) => {
    e.preventDefault();
    setError('');

    // Validate password match
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    // Validate password length
    if (newPassword.length < 4) {
      setError('Password must be at least 4 characters');
      return;
    }

    // Validate TOTP code
    if (totpCode.length !== 6 || !/^\d+$/.test(totpCode)) {
      setError('TOTP code must be 6 digits');
      return;
    }

    setLoading(true);

    try {
      const response = await apiClient.post('/auth/reset-password', {
        username: username.trim(),
        totp_code: totpCode,
        new_password: newPassword
      });

      if (response.data.success) {
        setMessage(response.data.message);
        setStep(3); // Success step
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Password reset failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      onClick={(e) => e.target === e.currentTarget && handleClose()}
      aria-modal="true"
      role="presentation"
    >
      <div
        ref={modalRef}
        className="modal modal-sm"
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
        role="dialog"
        aria-labelledby="password-reset-title"
      >
        {/* Header */}
        <div className="modal-header">
          <h2 id="password-reset-title" className="modal-title">
            Reset Password
          </h2>
          <button
            className="modal-close"
            onClick={handleClose}
            aria-label="Close modal"
            type="button"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="modal-body">
          {/* Step 1: Enter Username */}
          {step === 1 && (
            <form onSubmit={handleCheckUsername}>
              <p style={{ marginBottom: 'var(--spacing-lg, 24px)', color: 'var(--text-secondary)' }}>
                Password reset is only available for users with Two-Factor Authentication enabled.
              </p>

              <div style={{ marginBottom: 'var(--spacing-lg, 24px)' }}>
                <label style={styles.label} htmlFor="username-input">
                  Username
                </label>
                <input
                  id="username-input"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                  style={styles.input}
                  required
                  autoFocus
                  disabled={loading}
                />
              </div>

              {error && <div className="alert alert-error" style={styles.alert}>{error}</div>}
              {message && <div className="alert alert-success" style={styles.alertSuccess}>{message}</div>}

              <div className="modal-actions">
                <button
                  type="button"
                  onClick={handleClose}
                  className="btn btn-secondary"
                  disabled={loading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading || !username.trim()}
                >
                  {loading ? 'Checking...' : 'Continue'}
                </button>
              </div>
            </form>
          )}

          {/* Step 2: Enter TOTP + New Password */}
          {step === 2 && (
            <form onSubmit={handleResetPassword}>
              <p style={{ marginBottom: 'var(--spacing-lg, 24px)', color: 'var(--text-secondary)' }}>
                Enter the 6-digit code from your authenticator app and your new password.
              </p>

              <div style={{ marginBottom: 'var(--spacing-md, 16px)' }}>
                <label style={styles.label} htmlFor="username-display">
                  Username
                </label>
                <input
                  id="username-display"
                  type="text"
                  value={username}
                  style={{...styles.input, opacity: 0.6, cursor: 'not-allowed'}}
                  disabled
                />
              </div>

              <div style={{ marginBottom: 'var(--spacing-md, 16px)' }}>
                <label style={styles.label} htmlFor="totp-input">
                  2FA Code
                </label>
                <input
                  id="totp-input"
                  type="text"
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  style={{...styles.input, textAlign: 'center', letterSpacing: '0.5em', fontSize: '24px'}}
                  required
                  autoFocus
                  maxLength={6}
                  pattern="\d{6}"
                  disabled={loading}
                  autoComplete="off"
                />
                <small style={styles.hint}>Enter 6-digit code from your authenticator app</small>
              </div>

              <div style={{ marginBottom: 'var(--spacing-md, 16px)' }}>
                <label style={styles.label} htmlFor="new-password-input">
                  New Password
                </label>
                <input
                  id="new-password-input"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password"
                  style={styles.input}
                  required
                  minLength={4}
                  disabled={loading}
                />
              </div>

              <div style={{ marginBottom: 'var(--spacing-lg, 24px)' }}>
                <label style={styles.label} htmlFor="confirm-password-input">
                  Confirm Password
                </label>
                <input
                  id="confirm-password-input"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm new password"
                  style={styles.input}
                  required
                  minLength={4}
                  disabled={loading}
                />
              </div>

              {error && <div className="alert alert-error" style={styles.alert}>{error}</div>}

              <div className="modal-actions">
                <button
                  type="button"
                  onClick={() => {
                    setStep(1);
                    setTotpCode('');
                    setNewPassword('');
                    setConfirmPassword('');
                    setError('');
                  }}
                  className="btn btn-secondary"
                  disabled={loading}
                >
                  Back
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading || !totpCode || !newPassword || !confirmPassword}
                >
                  {loading ? 'Resetting...' : 'Reset Password'}
                </button>
              </div>
            </form>
          )}

          {/* Step 3: Success */}
          {step === 3 && (
            <div style={{ textAlign: 'center', padding: 'var(--spacing-lg, 24px) 0' }}>
              <div style={{
                fontSize: '64px',
                color: 'var(--color-success)',
                marginBottom: 'var(--spacing-lg, 24px)',
                lineHeight: 1,
              }}>
                ✓
              </div>
              <h3 style={{
                color: 'var(--text-primary)',
                marginBottom: 'var(--spacing-md, 16px)',
                fontSize: '20px',
                fontWeight: '600',
              }}>
                Password Reset Successful
              </h3>
              <p style={{
                color: 'var(--color-success)',
                marginBottom: 'var(--spacing-sm, 8px)',
                fontSize: '17px',
              }}>
                {message}
              </p>
              <p style={{
                color: 'var(--text-secondary)',
                marginBottom: 'var(--spacing-xl, 32px)',
              }}>
                You can now log in with your new password.
              </p>
              <button
                onClick={handleClose}
                className="btn btn-primary"
                style={{ width: '100%' }}
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Styles following HIG guidelines
const styles = {
  label: {
    display: 'block',
    marginBottom: 'var(--spacing-sm, 8px)',
    color: 'var(--text-primary)',
    fontWeight: '500',
    fontSize: '14px',
  },
  input: {
    width: '100%',
    padding: 'var(--spacing-sm, 8px) var(--spacing-md, 16px)',
    fontSize: '17px', // Standard input text size
    minHeight: 'var(--touch-target-min, 44px)', // HIG minimum touch target
    border: '1px solid var(--border-input)',
    borderRadius: 'var(--radius-sm, 8px)',
    backgroundColor: 'var(--bg-input)',
    color: 'var(--text-primary)',
    outline: 'none',
    transition: 'border-color var(--anim-fast, 0.15s) ease',
    boxSizing: 'border-box',
  },
  hint: {
    display: 'block',
    marginTop: 'var(--spacing-sm, 8px)',
    fontSize: '14px',
    color: 'var(--text-secondary)',
    fontStyle: 'italic',
  },
  alert: {
    backgroundColor: 'rgba(220, 53, 69, 0.15)',
    color: 'var(--color-error)',
    padding: 'var(--spacing-md, 16px)',
    borderRadius: 'var(--radius-sm, 8px)',
    marginBottom: 'var(--spacing-lg, 24px)',
    border: '1px solid var(--color-error)',
    fontSize: '14px',
    borderLeft: '4px solid var(--color-error)',
  },
  alertSuccess: {
    backgroundColor: 'rgba(40, 167, 69, 0.15)',
    color: 'var(--color-success)',
    padding: 'var(--spacing-md, 16px)',
    borderRadius: 'var(--radius-sm, 8px)',
    marginBottom: 'var(--spacing-lg, 24px)',
    border: '1px solid var(--color-success)',
    fontSize: '14px',
    borderLeft: '4px solid var(--color-success)',
  },
};

export default PasswordResetModal;
