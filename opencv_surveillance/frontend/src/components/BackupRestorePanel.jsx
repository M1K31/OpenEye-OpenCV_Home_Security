// Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useCallback, useEffect, useRef, useState } from 'react';
import apiClient from '../api/apiClient';
import { describeApiError } from '../utils/apiError';

/**
 * Backing up, and putting a backup back.
 *
 * A backup holds the database and the face galleries — people, clusters,
 * cameras, settings, and the photographs and encodings recognition is built
 * from. Snapshots and recordings are not included: they run to gigabytes, are
 * already governed by retention rules, and a detection whose image is missing
 * degrades on its own.
 *
 * Restore replaces everything recorded since the backup was taken, so it asks
 * twice: once to show what the file contains, and once to confirm against that.
 * Nothing is destroyed between those two steps.
 */
const BackupRestorePanel = () => {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState(null);
  const [pending, setPending] = useState(null);   // an inspected upload
  const fileInput = useRef(null);
  const pendingFile = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/backups');
      setBackups(response.data.backups || []);
    } catch (error) {
      setMessage({ type: 'error', text: describeApiError(error, 'Could not list backups.') });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const backUpNow = async () => {
    setBusy('backup');
    setMessage(null);
    try {
      const { data } = await apiClient.post('/backups');
      setMessage({
        type: 'success',
        text: `Backed up ${describeContents(data.contents)} — `
            + `${(data.bytes / 1e6).toFixed(1)} MB in ${data.seconds}s.`,
      });
      await load();
    } catch (error) {
      setMessage({ type: 'error', text: describeApiError(error, 'Backup failed.') });
    } finally {
      setBusy('');
    }
  };

  // Step one of a restore: describe the file, change nothing.
  const inspectChosenFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    pendingFile.current = file;
    setBusy('inspect');
    setMessage(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const { data } = await apiClient.post('/backups/inspect', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPending({ file, details: data });
    } catch (error) {
      pendingFile.current = null;
      setMessage({ type: 'error', text: describeApiError(error, 'That file could not be read.') });
    } finally {
      setBusy('');
      if (fileInput.current) fileInput.current.value = '';
    }
  };

  // Step two: only now is anything replaced.
  const confirmRestore = async () => {
    const file = pendingFile.current;
    if (!file) return;
    setBusy('restore');
    try {
      const form = new FormData();
      form.append('file', file);
      const { data } = await apiClient.post('/backups/restore', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPending(null);
      pendingFile.current = null;
      setMessage({
        type: 'success',
        text: 'Restored. Restart OpenEye to finish — until then it keeps using '
            + `the previous data. Your previous state was saved as ${basename(data.safety_copy)}.`,
      });
      await load();
    } catch (error) {
      setMessage({ type: 'error', text: describeApiError(error, 'Restore failed.') });
    } finally {
      setBusy('');
    }
  };

  const restoreStored = async (entry) => {
    if (!window.confirm(
      `Restore from ${entry.name}?\n\n`
      + 'Everything recorded since it was taken will be replaced. Your current '
      + 'data is saved first, so this can be undone.')) return;

    setBusy(entry.name);
    setMessage(null);
    try {
      const { data } = await apiClient.post(
        `/backups/${encodeURIComponent(entry.name)}/restore`);
      setMessage({
        type: 'success',
        text: 'Restored. Restart OpenEye to finish. Your previous state was '
            + `saved as ${basename(data.safety_copy)}.`,
      });
      await load();
    } catch (error) {
      setMessage({ type: 'error', text: describeApiError(error, 'Restore failed.') });
    } finally {
      setBusy('');
    }
  };

  return (
    <div style={styles.panel}>
      <p style={styles.blurb}>
        A backup holds your people, clusters, cameras and settings, together with
        the photographs and face data recognition is built from. Recordings and
        detection snapshots are not included — they run to gigabytes and expire
        on their own schedule.
      </p>

      {message && (
        <div style={message.type === 'error' ? styles.error : styles.success}>
          {message.text}
        </div>
      )}

      <div style={styles.actions}>
        <button style={styles.primary} onClick={backUpNow} disabled={!!busy}>
          {busy === 'backup' ? 'Backing up…' : 'Back up now'}
        </button>

        <button
          style={styles.secondary}
          onClick={() => fileInput.current?.click()}
          disabled={!!busy}
        >
          {busy === 'inspect' ? 'Reading…' : 'Restore from a file…'}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".gz,.tar.gz,application/gzip"
          onChange={inspectChosenFile}
          style={{ display: 'none' }}
        />
      </div>

      {/* What the chosen file contains, before anything is replaced. */}
      {pending && (
        <div style={styles.confirm}>
          <h4 style={styles.confirmTitle}>Restore from {pending.file.name}?</h4>
          <dl style={styles.details}>
            <dt style={styles.dt}>Taken</dt>
            <dd style={styles.dd}>{formatWhen(pending.details.created_at)}</dd>
            <dt style={styles.dt}>Contains</dt>
            <dd style={styles.dd}>{describeContents(pending.details.contents)}</dd>
            <dt style={styles.dt}>Face galleries</dt>
            <dd style={styles.dd}>
              {pending.details.includes_faces ? 'included' : 'not included'}
            </dd>
          </dl>
          <p style={styles.warning}>
            Everything recorded since then will be replaced. Your current data is
            saved first, so this can be undone.
          </p>
          <div style={styles.actions}>
            <button style={styles.danger} onClick={confirmRestore} disabled={!!busy}>
              {busy === 'restore' ? 'Restoring…' : 'Replace my data'}
            </button>
            <button
              style={styles.secondary}
              onClick={() => { setPending(null); pendingFile.current = null; }}
              disabled={!!busy}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <h4 style={styles.listTitle}>Backups on this system</h4>
      {loading ? (
        <p style={styles.muted}>Loading…</p>
      ) : backups.length === 0 ? (
        <p style={styles.muted}>
          None yet. One is taken automatically each night at 3:30.
        </p>
      ) : (
        <ul style={styles.list}>
          {backups.map(entry => (
            <li key={entry.name} style={styles.item}>
              <div>
                <span style={styles.itemName}>{entry.name}</span>
                {entry.kind === 'pre-restore' && (
                  <span style={styles.tag}>saved before a restore</span>
                )}
                <div style={styles.muted}>
                  {formatWhen(entry.created_at)} · {(entry.bytes / 1e6).toFixed(1)} MB
                </div>
              </div>
              <button
                style={styles.small}
                onClick={() => restoreStored(entry)}
                disabled={!!busy}
              >
                {busy === entry.name ? 'Restoring…' : 'Restore'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

function describeContents(contents) {
  if (!contents) return 'an unknown amount of data';
  const people = contents.persons ?? 0;
  const detections = contents.face_detection_events ?? 0;
  const cameras = contents.cameras ?? 0;
  return `${people} ${people === 1 ? 'person' : 'people'}, `
       + `${detections.toLocaleString()} detections, `
       + `${cameras} ${cameras === 1 ? 'camera' : 'cameras'}`;
}

function formatWhen(iso) {
  if (!iso) return 'an unknown time';
  const when = new Date(iso);
  return Number.isNaN(when.getTime()) ? iso : when.toLocaleString();
}

function basename(path) {
  return String(path || '').split('/').pop();
}

const styles = {
  panel: { display: 'flex', flexDirection: 'column', gap: '14px' },
  blurb: { margin: 0, fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.5 },
  actions: { display: 'flex', gap: '10px', flexWrap: 'wrap' },
  primary: {
    padding: '9px 16px', borderRadius: 'var(--radius-md, 8px)', cursor: 'pointer',
    background: 'var(--button-primary-bg)', color: 'var(--button-primary-text)',
    border: '1px solid var(--button-primary-bg)', fontSize: '14px',
  },
  secondary: {
    padding: '9px 16px', borderRadius: 'var(--radius-md, 8px)', cursor: 'pointer',
    background: 'var(--bg-input)', color: 'var(--text-primary)',
    border: '1px solid var(--border-panel)', fontSize: '14px',
  },
  danger: {
    padding: '9px 16px', borderRadius: 'var(--radius-md, 8px)', cursor: 'pointer',
    background: 'var(--danger-color)', color: 'var(--text-on-status)',
    border: '1px solid var(--danger-color)', fontSize: '14px',
  },
  small: {
    padding: '6px 12px', borderRadius: 'var(--radius-md, 8px)', cursor: 'pointer',
    background: 'var(--bg-input)', color: 'var(--text-primary)',
    border: '1px solid var(--border-panel)', fontSize: '13px', whiteSpace: 'nowrap',
  },
  confirm: {
    padding: '16px', borderRadius: 'var(--radius-md, 8px)',
    background: 'var(--bg-panel)', border: '1px solid var(--danger-color)',
  },
  confirmTitle: { margin: '0 0 12px 0', fontSize: '15px', color: 'var(--text-primary)' },
  details: { margin: '0 0 12px 0', display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 16px' },
  dt: { fontSize: '13px', color: 'var(--text-secondary)' },
  dd: { margin: 0, fontSize: '13px', color: 'var(--text-primary)' },
  warning: { margin: '0 0 12px 0', fontSize: '13px', color: 'var(--warning-color)' },
  listTitle: { margin: '6px 0 0 0', fontSize: '15px', color: 'var(--text-primary)' },
  list: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '8px' },
  item: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px',
    padding: '10px 12px', borderRadius: 'var(--radius-md, 8px)',
    background: 'var(--bg-panel)', border: '1px solid var(--border-panel)',
  },
  itemName: { fontSize: '14px', color: 'var(--text-primary)' },
  tag: {
    marginLeft: '8px', padding: '2px 8px', fontSize: '11px',
    borderRadius: 'var(--radius-pill, 999px)',
    background: 'var(--bg-input)', color: 'var(--text-secondary)',
  },
  muted: { fontSize: '12px', color: 'var(--text-secondary)', margin: '2px 0 0 0' },
  error: {
    padding: '10px 12px', borderRadius: 'var(--radius-md, 8px)',
    background: 'var(--danger-bg)', color: 'var(--danger-color)', fontSize: '13px',
  },
  success: {
    padding: '10px 12px', borderRadius: 'var(--radius-md, 8px)',
    background: 'var(--success-bg)', color: 'var(--success-color)', fontSize: '13px',
  },
};

export default BackupRestorePanel;
