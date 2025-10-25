// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  Trash2, 
  Edit2, 
  Power, 
  PowerOff, 
  Clock, 
  Calendar,
  Camera,
  Bell,
  Video,
  Zap,
  AlertCircle,
  Save,
  X,
  Play
} from 'lucide-react';
import apiClient from '../api/apiClient';
import './AutomationsPage.css';

const AutomationsPage = () => {
  const [rules, setRules] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [knownPeople, setKnownPeople] = useState([]);
  const [cameras, setCameras] = useState([]);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    person_name: '',
    enabled: true,
    cooldown_seconds: 300,
    conditions: {
      cameras: [],
      time_range: null,
      confidence_threshold: 0.85,
      days_of_week: []
    },
    actions: []
  });

  const daysOfWeek = [
    { value: 0, label: 'Mon' },
    { value: 1, label: 'Tue' },
    { value: 2, label: 'Wed' },
    { value: 3, label: 'Thu' },
    { value: 4, label: 'Fri' },
    { value: 5, label: 'Sat' },
    { value: 6, label: 'Sun' }
  ];

  const actionTypes = [
    { value: 'notification', label: 'Notification', icon: Bell },
    { value: 'record', label: 'Record Video', icon: Video },
    { value: 'webhook', label: 'Webhook', icon: Zap },
    { value: 'alert', label: 'Alert', icon: AlertCircle }
  ];

  // Load data
  useEffect(() => {
    loadRules();
    loadStats();
    loadKnownPeople();
    loadCameras();
  }, []);

  const loadRules = async () => {
    try {
      const response = await apiClient.get('/automations/');
      setRules(response.data.rules || []);
    } catch (error) {
      console.error('Failed to load rules:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await apiClient.get('/automations/stats/summary');
      setStats(response.data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const loadKnownPeople = async () => {
    try {
      console.log('[AutomationsPage] Loading known people...');
      const response = await apiClient.get('/faces/people');
      console.log('[AutomationsPage] API response:', response.data);

      // Handle wrapped response format {people: [...], total: N}
      const peopleData = response.data?.people || response.data || [];
      console.log('[AutomationsPage] People data:', peopleData);

      // Extract names from Person objects (each has name, photo_count, path)
      const names = Array.isArray(peopleData)
        ? peopleData.map(person => typeof person === 'string' ? person : person.name)
        : [];

      console.log('[AutomationsPage] Extracted names:', names);
      setKnownPeople(names);
    } catch (error) {
      console.error('[AutomationsPage] Failed to load known people:', error);
      setKnownPeople([]); // Ensure empty array on error
    }
  };

  const loadCameras = async () => {
    try {
      const response = await apiClient.get('/cameras/');
      setCameras(response.data?.cameras || []);
    } catch (error) {
      console.error('Failed to load cameras:', error);
    }
  };

  // CRUD operations
  const handleCreateRule = () => {
    setEditingRule(null);
    setFormData({
      name: '',
      person_name: '',
      enabled: true,
      cooldown_seconds: 300,
      conditions: {
        cameras: [],
        time_range: null,
        confidence_threshold: 0.85,
        days_of_week: []
      },
      actions: []
    });
    setShowModal(true);
  };

  const handleEditRule = (rule) => {
    setEditingRule(rule);
    setFormData({
      name: rule.name,
      person_name: rule.person_name,
      enabled: rule.enabled,
      cooldown_seconds: rule.cooldown_seconds,
      conditions: rule.conditions ? JSON.parse(rule.conditions) : {
        cameras: [],
        time_range: null,
        confidence_threshold: 0.85,
        days_of_week: []
      },
      actions: rule.actions ? JSON.parse(rule.actions) : []
    });
    setShowModal(true);
  };

  const handleSaveRule = async () => {
    try {
      const payload = {
        ...formData,
        conditions: Object.keys(formData.conditions).length > 0 ? formData.conditions : null
      };

      if (editingRule) {
        await apiClient.put(`/automations/${editingRule.id}`, payload);
      } else {
        await apiClient.post('/automations/', payload);
      }

      setShowModal(false);
      loadRules();
      loadStats();
    } catch (error) {
      console.error('Failed to save rule:', error);
      alert(`Failed to save rule: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleDeleteRule = async (ruleId) => {
    if (!confirm('Are you sure you want to delete this rule?')) return;

    try {
      await apiClient.delete(`/automations/${ruleId}`);
      loadRules();
      loadStats();
    } catch (error) {
      console.error('Failed to delete rule:', error);
    }
  };

  const handleToggleRule = async (ruleId) => {
    try {
      await apiClient.post(`/automations/${ruleId}/toggle`);
      loadRules();
      loadStats();
    } catch (error) {
      console.error('Failed to toggle rule:', error);
    }
  };

  const handleTestRule = async (ruleId) => {
    try {
      const response = await apiClient.post(`/automations/${ruleId}/test`, {
        confidence: 0.95,
        skip_cooldown: true
      });

      if (response.data.success) {
        alert(`✓ Rule would trigger!\n\nConditions met: ${response.data.conditions_met}\nActions: ${response.data.actions_executed.length}`);
      } else {
        alert(`✗ Rule would not trigger\n\nReason: ${response.data.message}`);
      }
    } catch (error) {
      console.error('Failed to test rule:', error);
    }
  };

  // Action management
  const handleAddAction = () => {
    setFormData({
      ...formData,
      actions: [...formData.actions, { type: 'notification', config: {} }]
    });
  };

  const handleUpdateAction = (index, field, value) => {
    const newActions = [...formData.actions];
    if (field === 'type') {
      newActions[index] = { type: value, config: {} };
    } else {
      newActions[index].config[field] = value;
    }
    setFormData({ ...formData, actions: newActions });
  };

  const handleRemoveAction = (index) => {
    setFormData({
      ...formData,
      actions: formData.actions.filter((_, i) => i !== index)
    });
  };

  // Render action configuration
  const renderActionConfig = (action, index) => {
    switch (action.type) {
      case 'notification':
        return (
          <div className="action-config">
            <input
              type="text"
              placeholder="Notification message"
              value={action.config.message || ''}
              onChange={(e) => handleUpdateAction(index, 'message', e.target.value)}
              className="form-input"
            />
            <select
              value={action.config.priority || 'normal'}
              onChange={(e) => handleUpdateAction(index, 'priority', e.target.value)}
              className="form-select"
            >
              <option value="low">Low Priority</option>
              <option value="normal">Normal Priority</option>
              <option value="high">High Priority</option>
            </select>
          </div>
        );

      case 'record':
        return (
          <div className="action-config">
            <label>
              Duration (seconds):
              <input
                type="number"
                min="10"
                max="300"
                value={action.config.duration || 30}
                onChange={(e) => handleUpdateAction(index, 'duration', parseInt(e.target.value))}
                className="form-input"
              />
            </label>
            <label>
              Pre-buffer (seconds):
              <input
                type="number"
                min="0"
                max="30"
                value={action.config.pre_buffer || 0}
                onChange={(e) => handleUpdateAction(index, 'pre_buffer', parseInt(e.target.value))}
                className="form-input"
              />
            </label>
          </div>
        );

      case 'webhook':
        return (
          <div className="action-config">
            <input
              type="url"
              placeholder="Webhook URL"
              value={action.config.url || ''}
              onChange={(e) => handleUpdateAction(index, 'url', e.target.value)}
              className="form-input"
            />
            <select
              value={action.config.method || 'POST'}
              onChange={(e) => handleUpdateAction(index, 'method', e.target.value)}
              className="form-select"
            >
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
            </select>
          </div>
        );

      case 'alert':
        return (
          <div className="action-config">
            <input
              type="text"
              placeholder="Alert message"
              value={action.config.message || ''}
              onChange={(e) => handleUpdateAction(index, 'message', e.target.value)}
              className="form-input"
            />
            <select
              value={action.config.alert_type || 'person_detection'}
              onChange={(e) => handleUpdateAction(index, 'alert_type', e.target.value)}
              className="form-select"
            >
              <option value="person_detection">Person Detection</option>
              <option value="security">Security Alert</option>
              <option value="notification">Notification</option>
            </select>
          </div>
        );

      default:
        return null;
    }
  };

  if (loading) {
    return <div className="automations-page loading">Loading automations...</div>;
  }

  return (
    <div className="automations-page">
      <div className="page-header">
        <div>
          <h1>Automation Rules</h1>
          <p>Trigger actions when specific people are detected</p>
        </div>
        <button className="btn btn-primary" onClick={handleCreateRule}>
          <Plus size={20} />
          Create Rule
        </button>
      </div>

      {/* Statistics */}
      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Total Rules</div>
            <div className="stat-value">{stats.total_rules}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Enabled</div>
            <div className="stat-value enabled">{stats.enabled_rules}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Disabled</div>
            <div className="stat-value disabled">{stats.disabled_rules}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Triggers</div>
            <div className="stat-value">{stats.total_triggers}</div>
          </div>
        </div>
      )}

      {/* Rules List */}
      <div className="rules-list">
        {rules.length === 0 ? (
          <div className="empty-state">
            <AlertCircle size={48} />
            <h3>No automation rules yet</h3>
            <p>Create your first rule to get started</p>
            <button className="btn btn-primary" onClick={handleCreateRule}>
              <Plus size={20} />
              Create First Rule
            </button>
          </div>
        ) : (
          rules.map(rule => (
            <div key={rule.id} className={`rule-card ${!rule.enabled ? 'disabled' : ''}`}>
              <div className="rule-header">
                <div className="rule-title">
                  <h3>{rule.name}</h3>
                  <span className="person-badge">{rule.person_name}</span>
                  {!rule.enabled && <span className="status-badge disabled">Disabled</span>}
                </div>
                <div className="rule-actions">
                  <button
                    className="btn-icon"
                    onClick={() => handleTestRule(rule.id)}
                    title="Test rule"
                  >
                    <Play size={18} />
                  </button>
                  <button
                    className={`btn-icon ${rule.enabled ? 'enabled' : 'disabled'}`}
                    onClick={() => handleToggleRule(rule.id)}
                    title={rule.enabled ? 'Disable' : 'Enable'}
                  >
                    {rule.enabled ? <Power size={18} /> : <PowerOff size={18} />}
                  </button>
                  <button
                    className="btn-icon"
                    onClick={() => handleEditRule(rule)}
                    title="Edit"
                  >
                    <Edit2 size={18} />
                  </button>
                  <button
                    className="btn-icon danger"
                    onClick={() => handleDeleteRule(rule.id)}
                    title="Delete"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>

              <div className="rule-details">
                <div className="detail-item">
                  <Clock size={16} />
                  <span>Cooldown: {Math.floor(rule.cooldown_seconds / 60)}m</span>
                </div>
                <div className="detail-item">
                  <Zap size={16} />
                  <span>Triggers: {rule.trigger_count}</span>
                </div>
                {rule.last_triggered_at && (
                  <div className="detail-item">
                    <Calendar size={16} />
                    <span>Last: {new Date(rule.last_triggered_at).toLocaleString()}</span>
                  </div>
                )}
              </div>

              <div className="rule-actions-list">
                <strong>Actions:</strong>
                {JSON.parse(rule.actions).map((action, idx) => (
                  <span key={idx} className="action-badge">
                    {action.type}
                  </span>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editingRule ? 'Edit Rule' : 'Create Rule'}</h2>
              <button className="btn-icon" onClick={() => setShowModal(false)}>
                <X size={24} />
              </button>
            </div>

            <div className="modal-body">
              {/* Basic Info */}
              <div className="form-section">
                <h3>Basic Information</h3>
                <div className="form-group">
                  <label>Rule Name</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., Alert when John arrives"
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Person</label>
                  <select
                    value={formData.person_name}
                    onChange={(e) => setFormData({ ...formData, person_name: e.target.value })}
                    className="form-select"
                  >
                    <option value="">Select person</option>
                    {knownPeople.map(person => (
                      <option key={person} value={person}>{person}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label>Cooldown Period</label>
                  <select
                    value={formData.cooldown_seconds}
                    onChange={(e) => setFormData({ ...formData, cooldown_seconds: parseInt(e.target.value) })}
                    className="form-select"
                  >
                    <option value={60}>1 minute</option>
                    <option value={300}>5 minutes</option>
                    <option value={600}>10 minutes</option>
                    <option value={1800}>30 minutes</option>
                    <option value={3600}>1 hour</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={formData.enabled}
                      onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                    />
                    Enable rule immediately
                  </label>
                </div>
              </div>

              {/* Conditions */}
              <div className="form-section">
                <h3>Conditions (Optional)</h3>
                
                <div className="form-group">
                  <label>Cameras</label>
                  <div className="checkbox-group">
                    {cameras.map(camera => (
                      <label key={camera.camera_id} className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={formData.conditions.cameras.includes(camera.camera_id)}
                          onChange={(e) => {
                            const cameras = e.target.checked
                              ? [...formData.conditions.cameras, camera.camera_id]
                              : formData.conditions.cameras.filter(id => id !== camera.camera_id);
                            setFormData({
                              ...formData,
                              conditions: { ...formData.conditions, cameras }
                            });
                          }}
                        />
                        {camera.camera_id}
                      </label>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label>Time Range</label>
                  <div className="time-range">
                    <input
                      type="time"
                      value={formData.conditions.time_range?.start || ''}
                      onChange={(e) => setFormData({
                        ...formData,
                        conditions: {
                          ...formData.conditions,
                          time_range: {
                            ...formData.conditions.time_range,
                            start: e.target.value
                          }
                        }
                      })}
                      className="form-input"
                    />
                    <span>to</span>
                    <input
                      type="time"
                      value={formData.conditions.time_range?.end || ''}
                      onChange={(e) => setFormData({
                        ...formData,
                        conditions: {
                          ...formData.conditions,
                          time_range: {
                            ...formData.conditions.time_range,
                            end: e.target.value
                          }
                        }
                      })}
                      className="form-input"
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>Days of Week</label>
                  <div className="days-of-week">
                    {daysOfWeek.map(day => (
                      <button
                        key={day.value}
                        type="button"
                        className={`day-button ${formData.conditions.days_of_week.includes(day.value) ? 'active' : ''}`}
                        onClick={() => {
                          const days = formData.conditions.days_of_week.includes(day.value)
                            ? formData.conditions.days_of_week.filter(d => d !== day.value)
                            : [...formData.conditions.days_of_week, day.value];
                          setFormData({
                            ...formData,
                            conditions: { ...formData.conditions, days_of_week: days }
                          });
                        }}
                      >
                        {day.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label>Confidence Threshold: {(formData.conditions.confidence_threshold * 100).toFixed(0)}%</label>
                  <input
                    type="range"
                    min="0.5"
                    max="1.0"
                    step="0.05"
                    value={formData.conditions.confidence_threshold}
                    onChange={(e) => setFormData({
                      ...formData,
                      conditions: { ...formData.conditions, confidence_threshold: parseFloat(e.target.value) }
                    })}
                    className="form-range"
                  />
                </div>
              </div>

              {/* Actions */}
              <div className="form-section">
                <h3>Actions</h3>
                {formData.actions.map((action, index) => (
                  <div key={index} className="action-item">
                    <div className="action-header">
                      <select
                        value={action.type}
                        onChange={(e) => handleUpdateAction(index, 'type', e.target.value)}
                        className="form-select"
                      >
                        {actionTypes.map(type => (
                          <option key={type.value} value={type.value}>
                            {type.label}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="btn-icon danger"
                        onClick={() => handleRemoveAction(index)}
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                    {renderActionConfig(action, index)}
                  </div>
                ))}
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleAddAction}
                >
                  <Plus size={18} />
                  Add Action
                </button>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowModal(false)}>
                Cancel
              </button>
              <button 
                className="btn btn-primary" 
                onClick={handleSaveRule}
                disabled={!formData.name || !formData.person_name || formData.actions.length === 0}
              >
                <Save size={18} />
                Save Rule
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AutomationsPage;
