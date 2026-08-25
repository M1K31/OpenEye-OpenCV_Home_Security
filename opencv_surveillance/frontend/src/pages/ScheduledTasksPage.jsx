// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import apiClient from '../api/apiClient';
import { logger } from '../utils/logger';
import { describeApiError } from '../utils/apiError';

/**
 * ScheduledTasksPage - Manage scheduled system tasks
 *
 * Provides UI for:
 * - Model retraining schedule
 * - Retroactive face search
 * - Database and snapshot cleanup
 */
const ScheduledTasksPage = ({ embedded = false }) => {
  const [tasks, setTasks] = useState([]);
  const [taskTypes, setTaskTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState({});
  const [message, setMessage] = useState({ type: '', text: '' });
  const [statistics, setStatistics] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [tasksRes, typesRes, statsRes] = await Promise.all([
        apiClient.get('/scheduled-tasks/tasks'),
        apiClient.get('/scheduled-tasks/task-types'),
        apiClient.get('/scheduled-tasks/statistics')
      ]);
      setTasks(tasksRes.data);
      setTaskTypes(typesRes.data.task_types);
      setStatistics(statsRes.data);
      setLoading(false);
    } catch (error) {
      logger.error('Error loading scheduled tasks:', error);
      setMessage({ type: 'error', text: 'Failed to load scheduled tasks' });
      setLoading(false);
    }
  };

  const handleToggleTask = async (taskType, enabled) => {
    try {
      await apiClient.put(`/scheduled-tasks/tasks/${taskType}`, { enabled });
      setTasks(prev => prev.map(t =>
        t.task_type === taskType ? { ...t, enabled } : t
      ));
      setMessage({
        type: 'success',
        text: `Task ${enabled ? 'enabled' : 'disabled'} successfully`
      });
      setTimeout(() => setMessage({ type: '', text: '' }), 3000);
    } catch (error) {
      logger.error('Error toggling task:', error);
      setMessage({ type: 'error', text: 'Failed to update task' });
    }
  };

  const handleRunTask = async (taskType) => {
    setRunning(prev => ({ ...prev, [taskType]: true }));
    setMessage({ type: '', text: '' });

    try {
      const response = await apiClient.post(`/scheduled-tasks/tasks/${taskType}/run`);
      setMessage({
        type: 'success',
        text: `Task completed: ${JSON.stringify(response.data.result)}`
      });
      loadData(); // Refresh task data
    } catch (error) {
      logger.error('Error running task:', error);
      setMessage({
        type: 'error',
        text: describeApiError(error, 'Task failed')
      });
    } finally {
      setRunning(prev => ({ ...prev, [taskType]: false }));
    }
  };

  const handleTrainAndSearch = async () => {
    setRunning(prev => ({ ...prev, trainAndSearch: true }));
    setMessage({ type: '', text: '' });

    try {
      const response = await apiClient.post('/scheduled-tasks/train-and-search');
      setMessage({
        type: 'success',
        text: `Model trained and retroactive search completed`
      });
      loadData();
    } catch (error) {
      logger.error('Error in train and search:', error);
      setMessage({
        type: 'error',
        text: describeApiError(error, 'Train and search failed')
      });
    } finally {
      setRunning(prev => ({ ...prev, trainAndSearch: false }));
    }
  };

  const getTaskDescription = (taskType) => {
    const type = taskTypes.find(t => t.type === taskType);
    return type?.description || 'No description available';
  };

  const getTaskName = (taskType) => {
    const type = taskTypes.find(t => t.type === taskType);
    return type?.name || taskType;
  };

  const formatLastRun = (lastRun) => {
    if (!lastRun) return 'Never';
    try {
      return new Date(lastRun).toLocaleString();
    } catch {
      return lastRun;
    }
  };

  if (loading) {
    return (
      <div style={styles.loading}>
        <div style={styles.spinner}>⏳</div>
        <p>Loading scheduled tasks...</p>
      </div>
    );
  }

  return (
    <div style={embedded ? {} : styles.container}>
      <div style={styles.content}>
        {!embedded && (
          <h1 style={styles.mainTitle}>⏰ Scheduled Tasks</h1>
        )}

        {message.text && (
          <div className={`alert ${message.type === 'success' ? 'alert-success' : 'alert-error'}`}>
            <span className="alert-icon">{message.type === 'success' ? '✓' : '⚠️'}</span>
            <div className="alert-content">{message.text}</div>
          </div>
        )}

        {/* Quick Actions */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>🚀 Quick Actions</h2>
          <p style={styles.sectionDescription}>
            Run common maintenance tasks immediately.
          </p>

          <button
            onClick={handleTrainAndSearch}
            disabled={running.trainAndSearch}
            className="btn btn-primary"
            style={styles.quickActionButton}
          >
            {running.trainAndSearch ? '⏳ Running...' : '🧠 Train Model & Search Past Events'}
          </button>
          <p style={styles.hint}>
            Trains the face recognition model with any new face images, then searches past detection events
            to update identifications. Run this after adding new people or identifying face clusters.
          </p>
        </div>

        {/* Task List */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>📋 Scheduled Tasks</h2>
          <p style={styles.sectionDescription}>
            Configure automatic maintenance tasks. These run on a schedule to keep your system optimized.
          </p>

          <div style={styles.taskGrid}>
            {tasks.map(task => (
              <div key={task.task_type} style={styles.taskCard}>
                <div style={styles.taskHeader}>
                  <h3 style={styles.taskName}>{getTaskName(task.task_type)}</h3>
                  <label style={styles.toggleLabel}>
                    <input
                      type="checkbox"
                      checked={task.enabled}
                      onChange={(e) => handleToggleTask(task.task_type, e.target.checked)}
                      style={styles.checkbox}
                    />
                    <span style={task.enabled ? styles.statusEnabled : styles.statusDisabled}>
                      {task.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </label>
                </div>

                <p style={styles.taskDescription}>{getTaskDescription(task.task_type)}</p>

                <div style={styles.taskMeta}>
                  <div style={styles.metaRow}>
                    <span style={styles.metaLabel}>Last Run:</span>
                    <span style={styles.metaValue}>{formatLastRun(task.last_run)}</span>
                  </div>
                  {task.schedule_time && (
                    <div style={styles.metaRow}>
                      <span style={styles.metaLabel}>Schedule:</span>
                      <span style={styles.metaValue}>Daily at {task.schedule_time}</span>
                    </div>
                  )}
                  {task.interval_hours && (
                    <div style={styles.metaRow}>
                      <span style={styles.metaLabel}>Interval:</span>
                      <span style={styles.metaValue}>Every {task.interval_hours} hours</span>
                    </div>
                  )}
                  <div style={styles.metaRow}>
                    <span style={styles.metaLabel}>Status:</span>
                    <span style={{
                      ...styles.metaValue,
                      color: task.status === 'idle' ? 'var(--color-success)' : 'var(--color-warning)'
                    }}>
                      {task.status}
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => handleRunTask(task.task_type)}
                  disabled={running[task.task_type]}
                  className="btn btn-secondary"
                  style={styles.runButton}
                >
                  {running[task.task_type] ? '⏳ Running...' : '▶️ Run Now'}
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Statistics */}
        {statistics && (
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>📊 Statistics</h2>
            <div style={styles.statsGrid}>
              <div style={styles.statCard}>
                <span style={styles.statValue}>{statistics.total_tasks || 0}</span>
                <span style={styles.statLabel}>Total Tasks</span>
              </div>
              <div style={styles.statCard}>
                <span style={styles.statValue}>{statistics.enabled_tasks || 0}</span>
                <span style={styles.statLabel}>Enabled</span>
              </div>
              <div style={styles.statCard}>
                <span style={styles.statValue}>{statistics.total_runs || 0}</span>
                <span style={styles.statLabel}>Total Runs</span>
              </div>
            </div>
          </div>
        )}

        <div style={styles.infoBox}>
          <strong>ℹ️ About Scheduled Tasks:</strong>
          <ul style={{ marginTop: '8px', paddingLeft: '20px', lineHeight: '1.6' }}>
            <li><strong>Model Retraining:</strong> Updates face recognition with new face images you've added</li>
            <li><strong>Retroactive Search:</strong> Re-identifies faces in past events with the current model</li>
            <li><strong>Cleanup Tasks:</strong> Remove old data to free up disk space and improve performance</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

const styles = {
  container: {
    backgroundColor: 'var(--bg-main)',
    minHeight: '100vh',
    padding: '20px',
    color: 'var(--text-primary)',
  },
  content: {
    maxWidth: '1000px',
    margin: '0 auto',
  },
  mainTitle: {
    fontSize: '32px',
    fontWeight: '600',
    marginBottom: '20px',
    color: 'var(--text-primary)',
  },
  loading: {
    textAlign: 'center',
    padding: '60px 20px',
    color: 'var(--text-primary)',
  },
  spinner: {
    fontSize: '48px',
    marginBottom: '20px',
  },
  section: {
    backgroundColor: 'var(--bg-panel)',
    borderRadius: '10px',
    padding: '25px',
    marginBottom: '25px',
    border: '1px solid var(--border-panel)',
  },
  sectionTitle: {
    fontSize: '20px',
    fontWeight: '600',
    marginBottom: '10px',
    color: 'var(--text-primary)',
  },
  sectionDescription: {
    fontSize: '14px',
    color: 'var(--text-secondary)',
    marginBottom: '20px',
    lineHeight: '1.6',
  },
  quickActionButton: {
    marginBottom: '10px',
  },
  hint: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    lineHeight: '1.5',
  },
  taskGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: '20px',
  },
  taskCard: {
    backgroundColor: 'var(--bg-main)',
    borderRadius: '8px',
    padding: '20px',
    border: '1px solid var(--border-panel)',
  },
  taskHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '10px',
  },
  taskName: {
    fontSize: '16px',
    fontWeight: '600',
    margin: 0,
    color: 'var(--text-primary)',
  },
  toggleLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    cursor: 'pointer',
  },
  checkbox: {
    width: '18px',
    height: '18px',
    cursor: 'pointer',
  },
  statusEnabled: {
    color: 'var(--color-success)',
    fontSize: '13px',
    fontWeight: '500',
  },
  statusDisabled: {
    color: 'var(--text-secondary)',
    fontSize: '13px',
    fontWeight: '500',
  },
  taskDescription: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    marginBottom: '15px',
    lineHeight: '1.5',
  },
  taskMeta: {
    marginBottom: '15px',
  },
  metaRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '4px 0',
    fontSize: '13px',
  },
  metaLabel: {
    color: 'var(--text-secondary)',
  },
  metaValue: {
    color: 'var(--text-primary)',
    fontWeight: '500',
  },
  runButton: {
    width: '100%',
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '15px',
  },
  statCard: {
    backgroundColor: 'var(--bg-main)',
    borderRadius: '8px',
    padding: '20px',
    textAlign: 'center',
    border: '1px solid var(--border-panel)',
  },
  statValue: {
    display: 'block',
    fontSize: '28px',
    fontWeight: '700',
    color: 'var(--theme-primary)',
    marginBottom: '5px',
  },
  statLabel: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
  },
  infoBox: {
    backgroundColor: 'rgba(var(--theme-primary-rgb), 0.1)',
    borderRadius: '8px',
    padding: '15px 20px',
    fontSize: '14px',
    color: 'var(--text-secondary)',
    lineHeight: '1.5',
  },
};

export default ScheduledTasksPage;
