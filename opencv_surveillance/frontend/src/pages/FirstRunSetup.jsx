/*
Copyright (c) 2025 Mikel Smart
This file is part of OpenEye-OpenCV_Home_Security
*/

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button, TextField } from '../components/universal';
import './FirstRunSetup.css';
import { describeApiError } from '../utils/apiError';

const FirstRunSetup = ({ onComplete }) => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    username: 'admin',
    email: '',
    password: '',
    confirmPassword: '',
    hubRole: 'auto',
    aupAccepted: false,
    baselineSelfScan: false,
    designateAutoScan: false
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [checkingSetup, setCheckingSetup] = useState(true);

  // Password strength requirements
  const passwordRequirements = {
    minLength: 8,  // Reduced from 12 to match bcrypt 72-byte limit
    maxLength: 72,  // Bcrypt byte limit
    requireUppercase: true,
    requireLowercase: true,
    requireNumbers: true,
    requireSpecialChars: true
  };

  // Check if first-run setup is needed
  useEffect(() => {
    checkSetupStatus();
  }, []);

  const checkSetupStatus = async () => {
    try {
      const response = await axios.get('/api/setup/status');
      if (response.data.setup_complete) {
        // Setup already complete, redirect to login
        navigate('/login');
      } else {
        setCheckingSetup(false);
      }
    } catch (error) {
      console.error('Error checking setup status:', error);
      setCheckingSetup(false);
    }
  };

  const validatePassword = (password) => {
    const errors = [];
    
    // Note: We don't reject passwords based on byte length here.
    // The backend hash_password() function will automatically truncate to 72 bytes if necessary.
    // This provides a better user experience than rejecting valid passwords.
    
    if (password.length < passwordRequirements.minLength) {
      errors.push(`Password must be at least ${passwordRequirements.minLength} characters long`);
    }
    
    if (passwordRequirements.requireUppercase && !/[A-Z]/.test(password)) {
      errors.push('Password must contain at least one uppercase letter');
    }
    
    if (passwordRequirements.requireLowercase && !/[a-z]/.test(password)) {
      errors.push('Password must contain at least one lowercase letter');
    }
    
    if (passwordRequirements.requireNumbers && !/[0-9]/.test(password)) {
      errors.push('Password must contain at least one number');
    }
    
    if (passwordRequirements.requireSpecialChars && !/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
      errors.push('Password must contain at least one special character (!@#$%^&*()_+-=[]{};\':"|,.<>?/)');
    }
    
    return errors;
  };

  const getPasswordStrength = (password) => {
    let strength = 0;
    
    if (password.length >= passwordRequirements.minLength) strength += 25;
    if (/[A-Z]/.test(password)) strength += 15;
    if (/[a-z]/.test(password)) strength += 15;
    if (/[0-9]/.test(password)) strength += 15;
    if (/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) strength += 15;
    if (password.length >= 16) strength += 15;
    
    if (strength <= 25) return { label: 'Weak', color: '#f44336', percent: strength };
    if (strength <= 50) return { label: 'Fair', color: '#ff9800', percent: strength };
    if (strength <= 75) return { label: 'Good', color: '#2196f3', percent: strength };
    return { label: 'Strong', color: '#4caf50', percent: strength };
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    
    // Clear error for this field
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  const validateForm = () => {
    const newErrors = {};
    
    if (!formData.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address';
    }
    
    const passwordErrors = validatePassword(formData.password);
    if (passwordErrors.length > 0) {
      newErrors.password = passwordErrors;
    }
    
    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await axios.post('/api/setup/initialize', {
        username: formData.username,
        email: formData.email,
        password: formData.password,
        hub_role: formData.hubRole,
        aup_accepted: formData.aupAccepted,
        baseline_self_scan: formData.baselineSelfScan,
        designate_auto_scan: formData.designateAutoScan
      });
      
      if (response.data.success) {
        setStep(3); // Show completion screen
        setTimeout(() => {
          // Force a full page reload to make App.jsx re-check setup status
          window.location.href = '/login';
        }, 2000);
      }
    } catch (error) {
      setErrors({
        submit: describeApiError(error, 'Failed to complete setup. Please try again.')
      });
    } finally {
      setLoading(false);
    }
  };

  if (checkingSetup) {
    return (
      <div className="first-run-container">
        <div className="setup-card">
          <div className="loading-spinner"></div>
          <p>Checking setup status...</p>
        </div>
      </div>
    );
  }

  const passwordStrength = formData.password ? getPasswordStrength(formData.password) : null;

  return (
    <div className="first-run-container">
      <div className="setup-card">
        <div className="setup-header">
          <h1>🔒 Welcome to OpenEye</h1>
          <p className="setup-subtitle">Let's set up your admin account</p>
        </div>

        {step === 1 && (
          <div className="setup-step">
            <div className="info-section">
              <h2>Create Admin Account</h2>
              <p>
                You're setting up OpenEye for the first time. Let's create a secure admin account
                to protect your surveillance system.
              </p>
              <div className="security-notice">
                <strong>🔐 Security Requirements:</strong>
                <ul>
                  <li>Between {passwordRequirements.minLength}-{passwordRequirements.maxLength} characters</li>
                  <li>At least one uppercase letter (A-Z)</li>
                  <li>At least one lowercase letter (a-z)</li>
                  <li>At least one number (0-9)</li>
                  <li>At least one special character (!@#$%^&*)</li>
                </ul>
              </div>
            </div>
            <Button
              variant="primary"
              size="large"
              onClick={() => setStep(2)}
              fullWidth
            >
              Get Started →
            </Button>
          </div>
        )}

        {step === 2 && (
          <div className="setup-step">
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <TextField
                  type="text"
                  label="Username"
                  value={formData.username}
                  disabled
                  helperText="Default admin username (cannot be changed)"
                  fullWidth
                />
              </div>

              <div className="form-group">
                <TextField
                  type="email"
                  label="Email Address *"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  placeholder="admin@example.com"
                  error={!!errors.email}
                  helperText={errors.email}
                  fullWidth
                />
              </div>

              <div className="form-group">
                <TextField
                  type="password"
                  label="Password *"
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  placeholder="Enter a strong password"
                  error={!!errors.password}
                  fullWidth
                />

                {passwordStrength && (
                  <div className="password-strength">
                    <div className="strength-label">
                      Password Strength: <span style={{ color: passwordStrength.color }}>
                        {passwordStrength.label}
                      </span>
                    </div>
                    <div className="strength-bar">
                      <div
                        className="strength-bar-fill"
                        style={{
                          width: `${passwordStrength.percent}%`,
                          backgroundColor: passwordStrength.color
                        }}
                      ></div>
                    </div>
                  </div>
                )}

                {errors.password && (
                  <div className="error-text">
                    {Array.isArray(errors.password) ? (
                      <ul className="error-list">
                        {errors.password.map((err, idx) => (
                          <li key={idx}>{err}</li>
                        ))}
                      </ul>
                    ) : (
                      errors.password
                    )}
                  </div>
                )}
              </div>

              <div className="form-group">
                <TextField
                  type="password"
                  label="Confirm Password *"
                  name="confirmPassword"
                  value={formData.confirmPassword}
                  onChange={handleInputChange}
                  placeholder="Re-enter your password"
                  error={!!errors.confirmPassword}
                  helperText={errors.confirmPassword}
                  fullWidth
                />
              </div>

              <div className="ecosystem-consent-section" style={{
                marginTop: '1.5rem',
                marginBottom: '1.5rem',
                padding: '1rem',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '8px',
                backgroundColor: 'rgba(255, 255, 255, 0.03)',
                fontSize: '0.9rem'
              }}>
                <h3 style={{ margin: '0 0 0.75rem 0', fontSize: '1rem' }}>🌐 Ecosystem Mesh & Policy Governance</h3>
                <div className="form-group" style={{ marginBottom: '1rem' }}>
                  <label htmlFor="hubRole" style={{ display: 'block', marginBottom: '0.4rem', fontWeight: 500 }}>
                    Ecosystem Mesh Role:
                  </label>
                  <select
                    id="hubRole"
                    name="hubRole"
                    value={formData.hubRole}
                    onChange={(e) => setFormData(prev => ({ ...prev, hubRole: e.target.value }))}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      borderRadius: '6px',
                      backgroundColor: 'rgba(0, 0, 0, 0.4)',
                      color: 'inherit',
                      border: '1px solid rgba(255, 255, 255, 0.2)',
                      minHeight: '44px'
                    }}
                  >
                    <option value="auto">Auto (Participate & elect best Hub host)</option>
                    <option value="host">Host (Prioritize hosting the Ecosystem Hub)</option>
                    <option value="join">Join (Client only, connect to existing Hub)</option>
                    <option value="standalone">Standalone (Local only, no mesh peering)</option>
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem', minHeight: '44px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      name="aupAccepted"
                      checked={formData.aupAccepted}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setFormData(prev => ({
                          ...prev,
                          aupAccepted: checked,
                          baselineSelfScan: checked ? prev.baselineSelfScan : false,
                          designateAutoScan: checked ? prev.designateAutoScan : false
                        }));
                      }}
                      style={{ marginTop: '0.2rem', minWidth: '20px', minHeight: '20px' }}
                    />
                    <span>
                      <strong>Accept Ecosystem Acceptable Use Policy (AUP v1.0)</strong>
                      <br />
                      <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>
                        Authorizes local cryptographic device enrollment for security telemetry and policy enforcement.
                      </span>
                    </span>
                  </label>

                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem', minHeight: '44px', opacity: formData.aupAccepted ? 1 : 0.5, cursor: formData.aupAccepted ? 'pointer' : 'not-allowed' }}>
                    <input
                      type="checkbox"
                      name="baselineSelfScan"
                      disabled={!formData.aupAccepted}
                      checked={formData.baselineSelfScan}
                      onChange={(e) => setFormData(prev => ({ ...prev, baselineSelfScan: e.target.checked }))}
                      style={{ marginTop: '0.2rem', minWidth: '20px', minHeight: '20px' }}
                    />
                    <span>
                      <strong>Opt-in to initial baseline self-scan</strong>
                      <br />
                      <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>
                        Runs a read-only Zero-Breach-Toolkit self-audit upon completion to establish device baseline.
                      </span>
                    </span>
                  </label>

                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem', minHeight: '44px', opacity: formData.aupAccepted ? 1 : 0.5, cursor: formData.aupAccepted ? 'pointer' : 'not-allowed' }}>
                    <input
                      type="checkbox"
                      name="designateAutoScan"
                      disabled={!formData.aupAccepted}
                      checked={formData.designateAutoScan}
                      onChange={(e) => setFormData(prev => ({ ...prev, designateAutoScan: e.target.checked }))}
                      style={{ marginTop: '0.2rem', minWidth: '20px', minHeight: '20px' }}
                    />
                    <span>
                      <strong>Designate for periodic automated scans</strong>
                      <br />
                      <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>
                        Grants explicit cryptographically bound authorization for scheduled quick scans by mesh peers.
                      </span>
                    </span>
                  </label>
                </div>
              </div>

              {errors.submit && (
                <div className="error-banner">
                  {errors.submit}
                </div>
              )}

              <div className="button-group">
                <Button
                  type="button"
                  variant="secondary"
                  size="medium"
                  onClick={() => setStep(1)}
                  disabled={loading}
                >
                  ← Back
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="medium"
                  disabled={loading}
                  loading={loading}
                >
                  Create Admin Account
                </Button>
              </div>
            </form>
          </div>
        )}

        {step === 3 && (
          <div className="setup-step completion-step">
            <div className="success-icon">✓</div>
            <h2>Setup Complete!</h2>
            <p>Your admin account has been created successfully.</p>
            <p className="redirect-message">Redirecting to login page...</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default FirstRunSetup;
