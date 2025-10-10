/*
Copyright (c) 2025 Mikel Smart
This file is part of OpenEye-OpenCV_Home_Security
*/

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import './FirstRunSetup.css';

const FirstRunSetup = ({ onComplete }) => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    username: 'admin',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [checkingSetup, setCheckingSetup] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

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
        password: formData.password
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
        submit: error.response?.data?.detail || 'Failed to complete setup. Please try again.'
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
            <button 
              onClick={() => setStep(2)} 
              className="btn-primary btn-large"
            >
              Get Started →
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="setup-step">
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor="username">Username</label>
                <input
                  type="text"
                  id="username"
                  name="username"
                  value={formData.username}
                  disabled
                  className="input-disabled"
                />
                <small>Default admin username (cannot be changed)</small>
              </div>

              <div className="form-group">
                <label htmlFor="email">Email Address *</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  placeholder="admin@example.com"
                  required
                  className={errors.email ? 'input-error' : ''}
                />
                {errors.email && <span className="error-text">{errors.email}</span>}
              </div>

              <div className="form-group">
                <label htmlFor="password">Password *</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPassword ? "text" : "password"}
                    id="password"
                    name="password"
                    value={formData.password}
                    onChange={handleInputChange}
                    placeholder="Enter a strong password"
                    required
                    className={errors.password ? 'input-error' : ''}
                    style={{ paddingRight: '40px' }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute',
                      right: '10px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '18px',
                      color: 'var(--text-secondary)'
                    }}
                    title={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? '🙈' : '👁️'}
                  </button>
                </div>
                
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
                <label htmlFor="confirmPassword">Confirm Password *</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    id="confirmPassword"
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleInputChange}
                    placeholder="Re-enter your password"
                    required
                    className={errors.confirmPassword ? 'input-error' : ''}
                    style={{ paddingRight: '40px' }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    style={{
                      position: 'absolute',
                      right: '10px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '18px',
                      color: 'var(--text-secondary)'
                    }}
                    title={showConfirmPassword ? "Hide password" : "Show password"}
                  >
                    {showConfirmPassword ? '🙈' : '👁️'}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <span className="error-text">{errors.confirmPassword}</span>
                )}
              </div>

              {errors.submit && (
                <div className="error-banner">
                  {errors.submit}
                </div>
              )}

              <div className="button-group">
                <button 
                  type="button" 
                  onClick={() => setStep(1)}
                  className="btn-secondary"
                  disabled={loading}
                >
                  ← Back
                </button>
                <button 
                  type="submit" 
                  className="btn-primary"
                  disabled={loading}
                >
                  {loading ? 'Creating Account...' : 'Create Admin Account'}
                </button>
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
