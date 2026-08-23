// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import twoFactorService from '../services/twoFactorService';
import PasswordResetModal from '../components/PasswordResetModal';
import { Button, TextField } from '../components/universal';

const LoginPage = ({ setToken }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [requires2FA, setRequires2FA] = useState(false);
  const [totpToken, setTotpToken] = useState('');
  const [backupCode, setBackupCode] = useState('');
  const [useBackupCode, setUseBackupCode] = useState(false);
  const [showPasswordResetModal, setShowPasswordResetModal] = useState(false);

  // Clear any expired or invalid tokens when login page loads.
  //
  // This read 'token' until 2026-08-23, a key the application stopped writing
  // when v3.8.0 moved to 'access_token' for refresh-token rotation. It
  // therefore never found anything and never ran: an expired token was left
  // in place and the 'your session has expired' message never appeared. The
  // authService tests would have caught it, but that file failed to load, so
  // nothing exercised the key name.
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      try {
        // Decode JWT token to check expiration
        const payload = JSON.parse(atob(token.split('.')[1]));
        const isExpired = Date.now() > payload.exp * 1000;
        
        if (isExpired) {
          console.log('Clearing expired token');
          localStorage.removeItem('access_token');
          localStorage.removeItem('token_timestamp');
          localStorage.removeItem('token_expires_at');
          setError('Your session has expired. Please log in again.');
        }
      } catch (e) {
        // Token is malformed, clear it
        console.log('Clearing invalid token');
        localStorage.removeItem('access_token');
        localStorage.removeItem('token_timestamp');
      }
    }
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');

    try {
      // Use 2FA service for login
      const response = await twoFactorService.login(
        username,
        password,
        useBackupCode ? null : totpToken,
        useBackupCode ? backupCode : null
      );

      if (response.access_token) {
        // v3.8.0: Store both access_token and refresh_token
        setToken(response.access_token);

        // Store refresh_token if provided
        if (response.refresh_token) {
          localStorage.setItem('refresh_token', response.refresh_token);
        }

        // Store token expiration time
        if (response.expires_in) {
          const expiresAt = Date.now() + (response.expires_in * 1000);
          localStorage.setItem('token_expires_at', expiresAt.toString());
        }

        // Store username
        localStorage.setItem('username', username);
      } else if (response.requires_2fa) {
        // 2FA is required - show 2FA input
        setRequires2FA(true);
      } else {
        setError('Login failed: No token received.');
      }
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError('An unexpected error occurred.');
      }
    }
  };

  const handleBack = () => {
    setRequires2FA(false);
    setTotpToken('');
    setBackupCode('');
    setUseBackupCode(false);
    setError('');
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>OpenEye Login</h1>
        <form onSubmit={handleLogin} style={styles.form}>
          {!requires2FA ? (
            // Step 1: Username and Password
            <>
              <div style={styles.formGroup}>
                <TextField
                  type="text"
                  label="Username"
                  placeholder="Enter username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  fullWidth
                />
              </div>
              <div style={styles.formGroup}>
                <TextField
                  type="password"
                  label="Password"
                  placeholder="Enter password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  fullWidth
                />
              </div>
              <Button type="submit" variant="primary" size="medium" fullWidth>
                Login
              </Button>
              <Button
                type="button"
                variant="tertiary"
                size="small"
                onClick={() => setShowPasswordResetModal(true)}
                fullWidth
              >
                Forgot Password?
              </Button>
            </>
          ) : (
            // Step 2: Two-Factor Authentication
            <>
              <div style={styles.info}>
                <p style={{ margin: 0, fontSize: '14px', lineHeight: '1.5' }}>
                  Two-factor authentication is enabled for this account. Please enter your authentication code.
                </p>
              </div>

              {!useBackupCode ? (
                <div style={styles.formGroup}>
                  <TextField
                    type="text"
                    label="Authenticator Code"
                    placeholder="000000"
                    value={totpToken}
                    onChange={(e) => setTotpToken(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    fullWidth
                  />
                  <Button
                    type="button"
                    variant="tertiary"
                    size="small"
                    onClick={() => setUseBackupCode(true)}
                    fullWidth
                  >
                    Use backup code instead
                  </Button>
                </div>
              ) : (
                <div style={styles.formGroup}>
                  <TextField
                    type="text"
                    label="Backup Code"
                    placeholder="XXXX-XXXX-XXXX"
                    value={backupCode}
                    onChange={(e) => setBackupCode(e.target.value.toUpperCase())}
                    fullWidth
                  />
                  <Button
                    type="button"
                    variant="tertiary"
                    size="small"
                    onClick={() => setUseBackupCode(false)}
                    fullWidth
                  >
                    Use authenticator code instead
                  </Button>
                </div>
              )}

              <div style={{ display: 'flex', gap: 'var(--spacing-md, 16px)' }}>
                <Button
                  type="button"
                  variant="secondary"
                  size="medium"
                  onClick={handleBack}
                  fullWidth
                >
                  Back
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="medium"
                  fullWidth
                >
                  Verify
                </Button>
              </div>
            </>
          )}
        </form>
        {error && <div style={styles.error}>{error}</div>}
      </div>

      {/* Password Reset Modal */}
      <PasswordResetModal
        isOpen={showPasswordResetModal}
        onClose={() => setShowPasswordResetModal(false)}
      />
    </div>
  );
};

const styles = {
  container: {
    backgroundColor: 'var(--bg-main)',
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 'var(--spacing-lg, 24px)', // 8pt grid aligned
  },
  card: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border-panel)',
    borderRadius: 'var(--radius-lg, 16px)', // Rounded corners for visual softness
    padding: 'var(--spacing-2xl, 48px)', // 8pt grid aligned
    maxWidth: '400px',
    width: '100%',
    boxShadow: 'var(--shadow-lg)', // Elevation for card
  },
  title: {
    color: 'var(--text-primary)',
    textAlign: 'center',
    marginBottom: 'var(--spacing-xl, 32px)', // 8pt grid aligned
    fontSize: '28px', // Title 1
    fontWeight: '600',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--spacing-lg, 24px)', // 8pt grid aligned
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--spacing-sm, 8px)', // 8pt grid aligned
  },
  label: {
    color: 'var(--text-primary)',
    fontWeight: '500',
    fontSize: '14px',
  },
  input: {
    backgroundColor: 'var(--bg-input)',
    border: '1px solid var(--border-input)',
    color: 'var(--text-primary)',
    padding: 'var(--spacing-sm, 8px) var(--spacing-md, 16px)', // 8pt grid aligned
    borderRadius: 'var(--radius-sm, 8px)',
    fontSize: '17px', // Standard input text size
    minHeight: 'var(--touch-target-min, 44px)', // Minimum touch target for accessibility
    transition: 'border-color var(--anim-fast, 0.15s) ease',
  },
  button: {
    backgroundColor: 'var(--theme-primary)',
    color: '#ffffff',
    padding: 'var(--spacing-md, 16px)', // 8pt grid aligned
    border: 'none',
    borderRadius: 'var(--radius-md, 12px)',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '17px', // Standard button text size
    minHeight: 'var(--touch-target-min, 44px)', // Minimum touch target for accessibility
    transition: 'transform var(--anim-fast, 0.15s) ease, box-shadow var(--anim-fast, 0.15s) ease',
    boxShadow: 'var(--shadow-md)',
  },
  error: {
    color: 'var(--color-error)',
    marginTop: 'var(--spacing-lg, 24px)', // 8pt grid aligned
    padding: 'var(--spacing-md, 16px)', // 8pt grid aligned
    backgroundColor: 'rgba(220, 53, 69, 0.15)',
    borderRadius: 'var(--radius-sm, 8px)',
    borderLeft: '4px solid var(--color-error)',
    fontSize: '14px',
  },
  info: {
    color: 'var(--text-secondary)',
    padding: 'var(--spacing-md, 16px)',
    backgroundColor: 'var(--bg-secondary, rgba(0, 123, 255, 0.1))',
    borderRadius: 'var(--radius-sm, 8px)',
    borderLeft: '4px solid var(--theme-primary)',
    fontSize: '14px',
  },
  linkButton: {
    background: 'none',
    border: 'none',
    color: 'var(--theme-primary)',
    cursor: 'pointer',
    fontSize: '14px',
    padding: 'var(--spacing-sm, 8px) 0',
    textDecoration: 'underline',
    marginTop: 'var(--spacing-sm, 8px)',
  },
  secondaryButton: {
    backgroundColor: 'var(--bg-secondary, #6c757d)',
    flex: 1,
    lineHeight: '1.5',
  },
  forgotPasswordLink: {
    background: 'none',
    border: 'none',
    color: 'var(--theme-primary)',
    cursor: 'pointer',
    fontSize: '14px',
    padding: 'var(--spacing-sm, 8px) 0',
    textDecoration: 'underline',
    textAlign: 'center',
    marginTop: 'var(--spacing-sm, 8px)',
  },
};

export default LoginPage;