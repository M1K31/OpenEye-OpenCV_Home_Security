// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import twoFactorService from '../services/twoFactorService';
import { Button, TextField } from '../components/universal';

const TwoFactorSettings = ({ embedded = false }) => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Enable 2FA state
  const [showEnableFlow, setShowEnableFlow] = useState(false);
  const [qrCode, setQrCode] = useState('');
  const [secret, setSecret] = useState('');
  const [backupCodes, setBackupCodes] = useState([]);
  const [verifyToken, setVerifyToken] = useState('');

  // Disable 2FA state
  const [showDisableConfirm, setShowDisableConfirm] = useState(false);
  const [disablePassword, setDisablePassword] = useState('');

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const data = await twoFactorService.getStatus();
      setStatus(data);
    } catch (err) {
      setError('Failed to load 2FA status');
    } finally {
      setLoading(false);
    }
  };

  const handleEnable = async () => {
    try {
      setError('');
      setSuccess('');
      const data = await twoFactorService.enable();
      setQrCode(data.qr_code);
      setSecret(data.secret);
      setBackupCodes(data.backup_codes);
      setShowEnableFlow(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to enable 2FA');
    }
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    try {
      setError('');
      await twoFactorService.verify(verifyToken);
      setSuccess('Two-factor authentication enabled successfully!');
      setShowEnableFlow(false);
      setVerifyToken('');
      fetchStatus(); // Refresh status
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid verification code');
    }
  };

  const handleDisable = async (e) => {
    e.preventDefault();
    try {
      setError('');
      setSuccess('');
      await twoFactorService.disable(disablePassword);
      setSuccess('Two-factor authentication disabled successfully');
      setShowDisableConfirm(false);
      setDisablePassword('');
      fetchStatus(); // Refresh status
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to disable 2FA');
    }
  };

  const handleCopySecret = () => {
    navigator.clipboard.writeText(secret);
    setSuccess('Secret key copied to clipboard!');
    setTimeout(() => setSuccess(''), 3000);
  };

  const handleDownloadBackupCodes = () => {
    const content = `OpenEye Two-Factor Authentication Backup Codes\n\nGenerated: ${new Date().toLocaleString()}\n\n${backupCodes.map((code, i) => `${i + 1}. ${code}`).join('\n')}\n\nKeep these codes in a safe place. Each code can only be used once.`;
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `openeye-2fa-backup-codes-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div style={embedded ? {} : styles.container}>
        <div style={styles.card}>
          <p style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div style={embedded ? {} : styles.container}>
      <div style={styles.card}>
        {!embedded && <h1 style={styles.title}>Two-Factor Authentication</h1>}

        {error && <div style={styles.error}>{error}</div>}
        {success && <div style={styles.success}>{success}</div>}

        {!showEnableFlow && !showDisableConfirm && (
          <div style={styles.statusSection}>
            <div style={styles.statusRow}>
              <span style={styles.statusLabel}>Status:</span>
              <span style={{
                ...styles.statusBadge,
                backgroundColor: status?.two_factor_enabled ? 'var(--color-success, #28a745)' : 'var(--color-warning, #ffc107)',
                color: '#fff'
              }}>
                {status?.two_factor_enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>

            {status?.two_factor_enabled && (
              <>
                <div style={styles.statusRow}>
                  <span style={styles.statusLabel}>Enrolled:</span>
                  <span style={styles.statusValue}>
                    {status.enrolled_at ? new Date(status.enrolled_at).toLocaleDateString() : 'Unknown'}
                  </span>
                </div>
                <div style={styles.statusRow}>
                  <span style={styles.statusLabel}>Backup Codes Remaining:</span>
                  <span style={styles.statusValue}>
                    {status.backup_codes_remaining !== null ? status.backup_codes_remaining : 'Unknown'}
                  </span>
                </div>
              </>
            )}

            <div style={styles.buttonGroup}>
              {!status?.two_factor_enabled ? (
                <Button onClick={handleEnable} variant="primary" size="medium">
                  Enable Two-Factor Authentication
                </Button>
              ) : (
                <Button onClick={() => setShowDisableConfirm(true)} variant="destructive" size="medium">
                  Disable Two-Factor Authentication
                </Button>
              )}
            </div>

            <div style={styles.infoBox}>
              <h3 style={{ margin: '0 0 var(--spacing-sm, 8px) 0', fontSize: '16px' }}>What is Two-Factor Authentication?</h3>
              <p style={{ margin: 0, fontSize: '14px', lineHeight: '1.6' }}>
                Two-factor authentication (2FA) adds an extra layer of security to your account.
                When enabled, you'll need to enter a code from your authenticator app in addition to your password when logging in.
              </p>
            </div>
          </div>
        )}

        {showEnableFlow && (
          <div style={styles.enableFlow}>
            <div style={styles.step}>
              <h3 style={styles.stepTitle}>Step 1: Scan QR Code</h3>
              <p style={styles.stepDescription}>
                Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)
              </p>
              <div style={styles.qrContainer}>
                <img src={qrCode} alt="2FA QR Code" style={styles.qrCode} />
              </div>
              <div style={styles.secretBox}>
                <p style={{ margin: '0 0 var(--spacing-xs, 4px) 0', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Or enter this code manually:
                </p>
                <code style={styles.secretCode}>{secret}</code>
                <Button onClick={handleCopySecret} variant="primary" size="small">
                  Copy
                </Button>
              </div>
            </div>

            <div style={styles.step}>
              <h3 style={styles.stepTitle}>Step 2: Save Backup Codes</h3>
              <p style={styles.stepDescription}>
                Save these backup codes in a safe place. You can use them to access your account if you lose your authenticator device.
              </p>
              <div style={styles.backupCodesContainer}>
                {backupCodes.map((code, index) => (
                  <div key={index} style={styles.backupCode}>
                    {code}
                  </div>
                ))}
              </div>
              <Button onClick={handleDownloadBackupCodes} variant="secondary" size="medium">
                Download Backup Codes
              </Button>
            </div>

            <div style={styles.step}>
              <h3 style={styles.stepTitle}>Step 3: Verify Setup</h3>
              <p style={styles.stepDescription}>
                Enter the 6-digit code from your authenticator app to complete setup:
              </p>
              <form onSubmit={handleVerify} style={styles.verifyForm}>
                <TextField
                  type="text"
                  placeholder="000000"
                  value={verifyToken}
                  onChange={(e) => setVerifyToken(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  required
                  fullWidth
                  label="Verification Code"
                  maxLength={6}
                  pattern="\d{6}"
                  autoFocus
                  style={{ textAlign: 'center', letterSpacing: '0.3em', fontFamily: 'monospace', fontSize: '24px' }}
                />
                <div style={styles.buttonGroup}>
                  <Button
                    type="button"
                    onClick={() => {
                      setShowEnableFlow(false);
                      setVerifyToken('');
                    }}
                    variant="secondary"
                    size="medium"
                  >
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary" size="medium">
                    Verify & Enable
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {showDisableConfirm && (
          <div style={styles.disableFlow}>
            <div style={styles.warningBox}>
              <h3 style={{ margin: '0 0 var(--spacing-sm, 8px) 0', fontSize: '16px' }}>⚠️ Disable Two-Factor Authentication?</h3>
              <p style={{ margin: 0, fontSize: '14px', lineHeight: '1.6' }}>
                This will make your account less secure. You'll only need your password to log in.
              </p>
            </div>

            <form onSubmit={handleDisable} style={styles.disableForm}>
              <TextField
                type="password"
                value={disablePassword}
                onChange={(e) => setDisablePassword(e.target.value)}
                required
                fullWidth
                label="Enter your password to confirm"
                autoFocus
              />

              <div style={styles.buttonGroup}>
                <Button
                  type="button"
                  onClick={() => {
                    setShowDisableConfirm(false);
                    setDisablePassword('');
                  }}
                  variant="secondary"
                  size="medium"
                >
                  Cancel
                </Button>
                <Button type="submit" variant="destructive" size="medium">
                  Disable 2FA
                </Button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

const styles = {
  container: {
    backgroundColor: 'var(--bg-main)',
    minHeight: 'calc(100vh - 64px)',
    padding: 'var(--spacing-xl, 32px)',
  },
  card: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border-panel)',
    borderRadius: 'var(--radius-lg, 16px)',
    padding: 'var(--spacing-2xl, 48px)',
    maxWidth: '800px',
    margin: '0 auto',
  },
  title: {
    color: 'var(--text-primary)',
    marginBottom: 'var(--spacing-xl, 32px)',
    fontSize: '28px',
    fontWeight: '600',
  },
  statusSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--spacing-lg, 24px)',
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 'var(--spacing-md, 16px)',
    backgroundColor: 'var(--bg-secondary, rgba(0,0,0,0.02))',
    borderRadius: 'var(--radius-sm, 8px)',
  },
  statusLabel: {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--text-primary)',
  },
  statusValue: {
    fontSize: '14px',
    color: 'var(--text-secondary)',
  },
  statusBadge: {
    padding: 'var(--spacing-xs, 4px) var(--spacing-md, 16px)',
    borderRadius: 'var(--radius-full, 9999px)',
    fontSize: '12px',
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  buttonGroup: {
    display: 'flex',
    gap: 'var(--spacing-md, 16px)',
    marginTop: 'var(--spacing-lg, 24px)',
  },
  infoBox: {
    padding: 'var(--spacing-lg, 24px)',
    backgroundColor: 'var(--bg-secondary, rgba(0, 123, 255, 0.1))',
    borderRadius: 'var(--radius-sm, 8px)',
    borderLeft: '4px solid var(--theme-primary)',
    color: 'var(--text-secondary)',
  },
  warningBox: {
    padding: 'var(--spacing-lg, 24px)',
    backgroundColor: 'rgba(255, 193, 7, 0.15)',
    borderRadius: 'var(--radius-sm, 8px)',
    borderLeft: '4px solid var(--color-warning, #ffc107)',
    color: 'var(--text-primary)',
    marginBottom: 'var(--spacing-lg, 24px)',
  },
  error: {
    color: 'var(--color-error)',
    marginBottom: 'var(--spacing-lg, 24px)',
    padding: 'var(--spacing-md, 16px)',
    backgroundColor: 'rgba(220, 53, 69, 0.15)',
    borderRadius: 'var(--radius-sm, 8px)',
    borderLeft: '4px solid var(--color-error)',
  },
  success: {
    color: 'var(--color-success, #28a745)',
    marginBottom: 'var(--spacing-lg, 24px)',
    padding: 'var(--spacing-md, 16px)',
    backgroundColor: 'rgba(40, 167, 69, 0.15)',
    borderRadius: 'var(--radius-sm, 8px)',
    borderLeft: '4px solid var(--color-success)',
  },
  enableFlow: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--spacing-2xl, 48px)',
  },
  step: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--spacing-md, 16px)',
  },
  stepTitle: {
    fontSize: '20px',
    fontWeight: '600',
    color: 'var(--text-primary)',
    margin: 0,
  },
  stepDescription: {
    fontSize: '14px',
    color: 'var(--text-secondary)',
    margin: 0,
  },
  qrContainer: {
    display: 'flex',
    justifyContent: 'center',
    padding: 'var(--spacing-lg, 24px)',
    backgroundColor: '#fff',
    borderRadius: 'var(--radius-md, 12px)',
  },
  qrCode: {
    maxWidth: '256px',
    width: '100%',
    height: 'auto',
  },
  secretBox: {
    display: 'flex',
    flexDirection: 'column',
    padding: 'var(--spacing-md, 16px)',
    backgroundColor: 'var(--bg-secondary, rgba(0,0,0,0.02))',
    borderRadius: 'var(--radius-sm, 8px)',
  },
  secretCode: {
    fontFamily: 'monospace',
    fontSize: '18px',
    fontWeight: '600',
    color: 'var(--text-primary)',
    padding: 'var(--spacing-sm, 8px)',
    backgroundColor: 'var(--bg-input)',
    borderRadius: 'var(--radius-sm, 8px)',
    marginBottom: 'var(--spacing-sm, 8px)',
  },
  backupCodesContainer: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: 'var(--spacing-sm, 8px)',
    padding: 'var(--spacing-md, 16px)',
    backgroundColor: 'var(--bg-secondary, rgba(0,0,0,0.02))',
    borderRadius: 'var(--radius-sm, 8px)',
  },
  backupCode: {
    fontFamily: 'monospace',
    fontSize: '14px',
    padding: 'var(--spacing-sm, 8px)',
    backgroundColor: 'var(--bg-input)',
    borderRadius: 'var(--radius-sm, 8px)',
    textAlign: 'center',
    color: 'var(--text-primary)',
  },
  verifyForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--spacing-md, 16px)',
  },
  disableFlow: {
    display: 'flex',
    flexDirection: 'column',
  },
  disableForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--spacing-lg, 24px)',
  },
};

export default TwoFactorSettings;
