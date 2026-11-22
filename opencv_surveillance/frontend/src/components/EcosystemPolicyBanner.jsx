import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { getToken } from '../api/apiClient';

let uiAssetsLoaded = false;

function ensurePolicyUiAssets() {
  if (uiAssetsLoaded || typeof document === 'undefined') return;
  uiAssetsLoaded = true;

  if (!document.getElementById('ecosystem-theme-css')) {
    const link = document.createElement('link');
    link.id = 'ecosystem-theme-css';
    link.rel = 'stylesheet';
    link.href = '/ui/ecosystem-theme.css';
    document.head.appendChild(link);
  }

  if (!document.getElementById('ecosystem-ui-controls-js')) {
    const script = document.createElement('script');
    script.id = 'ecosystem-ui-controls-js';
    script.src = '/ui/ecosystem-ui-controls.js';
    script.async = true;
    document.head.appendChild(script);
  }
}

export default function EcosystemPolicyBanner({ viewMode = 'ambient' }) {
  const barRef = useRef(null);
  const modalRef = useRef(null);
  const [totpCode, setTotpCode] = useState('');
  const [notice, setNotice] = useState(null);
  const [approvals, setApprovals] = useState([]);
  const [isAdmin, setIsAdmin] = useState(false);

  const flashNotice = useCallback((msg) => {
    setNotice(msg);
    window.setTimeout(() => setNotice((cur) => (cur === msg ? null : cur)), 6000);
  }, []);

  const authedHeaders = useCallback(() => {
    const token = getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }, []);

  // Check if current user is admin
  useEffect(() => {
    const checkRole = async () => {
      try {
        const token = getToken();
        if (!token) return;
        const res = await axios.get('/api/users/me');
        if (res.data && res.data.role === 'admin') {
          setIsAdmin(true);
        }
      } catch {
        /* ignore */
      }
    };
    checkRole();
  }, []);

  const refreshPolicy = useCallback(async () => {
    try {
      const headers = authedHeaders();
      const [pRes, aRes] = await Promise.all([
        fetch('/api/ecosystem/policy/state', { headers }),
        fetch('/api/ecosystem/approvals?status_filter=pending', { headers }),
      ]);
      if (pRes.ok && barRef.current) {
        barRef.current.policyState = await pRes.json();
      }
      if (aRes.ok) {
        const data = await aRes.json();
        setApprovals(Array.isArray(data.approvals) ? data.approvals : []);
      }
    } catch {
      /* offline / unauthenticated fallback */
    }
  }, [authedHeaders]);

  useEffect(() => {
    ensurePolicyUiAssets();
    refreshPolicy();
    const timer = window.setInterval(() => refreshPolicy(), 8000);
    return () => window.clearInterval(timer);
  }, [refreshPolicy]);

  useEffect(() => {
    const bar = barRef.current;
    const modal = modalRef.current;
    if (!bar) return;
    if (modal) {
      modal.availableApps = ['openeye', 'aegissiem', 'aegissiem_daemon', 'ai_for_survival'];
    }

    const onManage = () => modal?.open?.();
    const onRestore = async () => {
      const r = await fetch('/api/ecosystem/policy/restrictions/on', {
        method: 'POST',
        headers: authedHeaders(),
        body: JSON.stringify({}),
      });
      if (r.ok) {
        flashNotice('Conservative Restrictions: On restored');
        refreshPolicy();
      }
    };
    const onFreeze = async () => {
      const r = await fetch('/api/ecosystem/policy/freeze', {
        method: 'POST',
        headers: authedHeaders(),
        body: JSON.stringify({
          channel: 'openeye_ui',
          reason: 'Emergency Freeze triggered from OpenEye',
        }),
      });
      if (r.ok) {
        flashNotice('Ecosystem Freeze engaged');
        refreshPolicy();
      }
    };
    const onResume = async () => {
      const r = await fetch('/api/ecosystem/policy/resume', {
        method: 'POST',
        headers: authedHeaders(),
        body: JSON.stringify({
          totp_code: totpCode.trim(),
          reason: 'Operator resumed normal operation from OpenEye',
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        flashNotice(data.detail || 'Enter 6-digit TOTP step-up code to Resume');
        return;
      }
      setTotpCode('');
      flashNotice('Normal policy operation resumed');
      refreshPolicy();
    };
    const onSubmitOverride = async (ev) => {
      const d = ev.detail || {};
      const r = await fetch('/api/ecosystem/policy/restrictions/off', {
        method: 'POST',
        headers: authedHeaders(),
        body: JSON.stringify({
          scope: d.scope,
          duration: d.duration,
          until_revoked: d.untilRevoked,
          reason: d.reason,
          totp_code: d.stepUpCredential,
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        flashNotice(data.detail || 'Step-up verification required for Restrictions: Off');
        return;
      }
      flashNotice('Signed scoped Restrictions: Off grant active');
      refreshPolicy();
    };

    bar.addEventListener('ecosystem-manage-overrides', onManage);
    bar.addEventListener('ecosystem-restore-restrictions', onRestore);
    bar.addEventListener('ecosystem-freeze-request', onFreeze);
    bar.addEventListener('ecosystem-resume-request', onResume);
    modal?.addEventListener('ecosystem-override-submit', onSubmitOverride);

    return () => {
      bar.removeEventListener('ecosystem-manage-overrides', onManage);
      bar.removeEventListener('ecosystem-restore-restrictions', onRestore);
      bar.removeEventListener('ecosystem-freeze-request', onFreeze);
      bar.removeEventListener('ecosystem-resume-request', onResume);
      modal?.removeEventListener('ecosystem-override-submit', onSubmitOverride);
    };
  }, [authedHeaders, flashNotice, refreshPolicy, totpCode]);

  const handleApprove = async (id) => {
    const r = await fetch(`/api/ecosystem/approvals/${encodeURIComponent(id)}/approve`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({ totp_code: totpCode.trim() }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
      flashNotice(d.detail || 'Step-up 6-digit TOTP required to approve');
      return;
    }
    flashNotice(`Approval ${id} approved`);
    refreshPolicy();
  };

  const handleDeny = async (id) => {
    const r = await fetch(`/api/ecosystem/approvals/${encodeURIComponent(id)}/deny`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({ totp_code: totpCode.trim() }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
      flashNotice(d.detail || 'Step-up 6-digit TOTP required to deny');
      return;
    }
    flashNotice(`Approval ${id} denied`);
    refreshPolicy();
  };

  const effectiveMode = isAdmin ? 'admin' : viewMode;

  return (
    <div className="ecosystem-policy-container" style={{ width: '100%' }}>
      <ecosystem-policy-bar
        ref={barRef}
        view-mode={effectiveMode}
        confirm-freeze-tap="true"
        style={{ display: 'block', width: '100%' }}
      />
      <ecosystem-override-modal ref={modalRef} />

      {notice && (
        <div
          role="status"
          aria-live="polite"
          style={{
            margin: '0.25rem 1rem',
            padding: '0.5rem 0.75rem',
            background: 'var(--color-bg-secondary, #2c2c2e)',
            color: 'var(--color-text-primary, #ffffff)',
            borderRadius: '6px',
            fontSize: '0.82rem',
            borderLeft: '3px solid var(--color-accent, #0a84ff)',
          }}
        >
          {notice}
        </div>
      )}

      {isAdmin && (
        <div
          className="ecosystem-step-up-bar"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.35rem 1rem',
            fontSize: '0.8rem',
            background: 'rgba(0,0,0,0.25)',
          }}
        >
          <label htmlFor="openeye-policy-totp" style={{ opacity: 0.85 }}>
            Operator 2FA TOTP:
          </label>
          <input
            id="openeye-policy-totp"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            placeholder="6-digit code"
            value={totpCode}
            onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            style={{
              width: '110px',
              minHeight: '44px',
              padding: '0.25rem 0.5rem',
              borderRadius: '6px',
              border: '1px solid rgba(255,255,255,0.25)',
              background: 'rgba(0,0,0,0.5)',
              color: '#fff',
              fontSize: '0.9rem',
              letterSpacing: '0.1em',
              textAlign: 'center',
            }}
          />

          {approvals.length > 0 && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                marginLeft: 'auto',
              }}
            >
              <span
                style={{
                  background: 'var(--color-warning, #ff9f0a)',
                  color: '#000',
                  padding: '0.15rem 0.5rem',
                  borderRadius: '12px',
                  fontWeight: 600,
                  fontSize: '0.75rem',
                }}
              >
                {approvals.length} Pending Approval{approvals.length > 1 ? 's' : ''}
              </span>
              {approvals.slice(0, 2).map((appr) => (
                <span
                  key={appr.approval_id}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.25rem',
                    background: 'rgba(255,255,255,0.08)',
                    padding: '0.2rem 0.5rem',
                    borderRadius: '4px',
                  }}
                >
                  <span style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {appr.action}: {appr.summary}
                  </span>
                  <button
                    onClick={() => handleApprove(appr.approval_id)}
                    style={{
                      minHeight: '44px',
                      padding: '0 0.5rem',
                      background: 'var(--color-success, #30d158)',
                      border: 'none',
                      borderRadius: '4px',
                      color: '#000',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    ✓
                  </button>
                  <button
                    onClick={() => handleDeny(appr.approval_id)}
                    style={{
                      minHeight: '44px',
                      padding: '0 0.5rem',
                      background: 'var(--color-danger, #ff453a)',
                      border: 'none',
                      borderRadius: '4px',
                      color: '#fff',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    ✗
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

