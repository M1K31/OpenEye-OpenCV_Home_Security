// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const LoginPage = ({ setToken }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Clear any expired or invalid tokens when login page loads
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        // Decode JWT token to check expiration
        const payload = JSON.parse(atob(token.split('.')[1]));
        const isExpired = Date.now() > payload.exp * 1000;
        
        if (isExpired) {
          console.log('Clearing expired token');
          localStorage.removeItem('token');
          localStorage.removeItem('token_timestamp');
          setError('Your session has expired. Please log in again.');
        }
      } catch (e) {
        // Token is malformed, clear it
        console.log('Clearing invalid token');
        localStorage.removeItem('token');
        localStorage.removeItem('token_timestamp');
      }
    }
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');

    try {
      const response = await axios.post('/api/token', new URLSearchParams({
        username,
        password,
      }), {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      if (response.data.access_token) {
        setToken(response.data.access_token);
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

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>OpenEye Login</h1>
        <form onSubmit={handleLogin} style={styles.form}>
          <div style={styles.formGroup}>
            <label style={styles.label}>Username</label>
            <input
              type="text"
              placeholder="Enter username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              style={styles.input}
            />
          </div>
          <div style={styles.formGroup}>
            <label style={styles.label}>Password</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? "text" : "password"}
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{...styles.input, paddingRight: 'var(--spacing-2xl, 48px)'}}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: 'var(--spacing-sm, 8px)',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '18px',
                  color: 'var(--text-secondary)',
                  minWidth: 'var(--touch-target-min, 44px)',
                  minHeight: 'var(--touch-target-min, 44px)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                title={showPassword ? "Hide password" : "Show password"}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>
          <button type="submit" style={styles.button}>Login</button>
        </form>
        {error && <div style={styles.error}>{error}</div>}
      </div>
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
    lineHeight: '1.5',
  },
};

export default LoginPage;