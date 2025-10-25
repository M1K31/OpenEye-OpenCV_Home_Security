/**
 * Notification Settings Page
 * Configure notification providers (email, SMS, push, webhooks)
 */

import React, { useState, useEffect } from 'react';
import notificationService from '../services/notificationService';
import './NotificationSettingsPage.css';

const NotificationSettingsPage = () => {
  const [providers, setProviders] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState('create'); // 'create' or 'edit'
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  // Form state
  const [formData, setFormData] = useState({
    provider_name: '',
    enabled: true,
    config: {}
  });

  // Test modal state
  const [showTestModal, setShowTestModal] = useState(false);
  const [testProvider, setTestProvider] = useState(null);
  const [testRecipient, setTestRecipient] = useState('');
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [providersData, templatesData] = await Promise.all([
        notificationService.listProviders(),
        notificationService.getTemplates()
      ]);

      setProviders(providersData.providers || []);
      setTemplates(templatesData.templates || []);
    } catch (err) {
      console.error('Error loading notification settings:', err);
      setError('Failed to load notification settings. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = (template) => {
    setSelectedTemplate(template);
    setModalMode('create');
    setFormData({
      provider_name: '',
      enabled: true,
      config: {}
    });

    // Initialize config with default values
    const config = {};
    template.config_fields.forEach(field => {
      if (field.default !== undefined) {
        config[field.name] = field.default;
      } else if (field.type === 'checkbox') {
        config[field.name] = false;
      } else {
        config[field.name] = '';
      }
    });
    setFormData(prev => ({ ...prev, config }));

    setShowModal(true);
  };

  const openEditModal = (provider) => {
    const template = templates.find(t => t.provider_type === provider.provider_type);
    setSelectedProvider(provider);
    setSelectedTemplate(template);
    setModalMode('edit');

    // Populate form with existing values
    setFormData({
      provider_name: provider.provider_name,
      enabled: provider.enabled,
      config: provider.config_summary || {}
    });

    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedProvider(null);
    setSelectedTemplate(null);
    setFormData({ provider_name: '', enabled: true, config: {} });
  };

  const handleFormChange = (field, value) => {
    if (field.startsWith('config.')) {
      const configField = field.replace('config.', '');
      setFormData(prev => ({
        ...prev,
        config: { ...prev.config, [configField]: value }
      }));
    } else {
      setFormData(prev => ({ ...prev, [field]: value }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      const payload = {
        ...formData,
        provider_type: selectedTemplate.provider_type
      };

      if (modalMode === 'create') {
        await notificationService.createProvider(payload);
      } else {
        await notificationService.updateProvider(selectedProvider.id, {
          provider_name: formData.provider_name,
          enabled: formData.enabled,
          config: formData.config
        });
      }

      await loadData();
      closeModal();
    } catch (err) {
      console.error('Error saving provider:', err);
      alert(`Failed to save provider: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleDelete = async (providerId) => {
    if (!confirm('Are you sure you want to delete this notification provider?')) {
      return;
    }

    try {
      await notificationService.deleteProvider(providerId);
      await loadData();
    } catch (err) {
      console.error('Error deleting provider:', err);
      alert('Failed to delete provider. Please try again.');
    }
  };

  const openTestModal = (provider) => {
    setTestProvider(provider);
    setTestRecipient('');
    setTestResult(null);
    setShowTestModal(true);
  };

  const closeTestModal = () => {
    setShowTestModal(false);
    setTestProvider(null);
    setTestRecipient('');
    setTestResult(null);
  };

  const handleTest = async (e) => {
    e.preventDefault();

    try {
      setTestLoading(true);
      setTestResult(null);

      const result = await notificationService.testProvider(testProvider.id, {
        recipient: testRecipient,
        subject: 'Test Notification from OpenEye',
        message: 'This is a test notification. If you received this, your notification provider is configured correctly!'
      });

      setTestResult(result);

      // Reload providers to update test status
      setTimeout(() => loadData(), 1000);
    } catch (err) {
      console.error('Error testing provider:', err);
      setTestResult({
        success: false,
        message: 'Test failed',
        error: err.response?.data?.detail || err.message
      });
    } finally {
      setTestLoading(false);
    }
  };

  const renderConfigField = (field) => {
    const value = formData.config[field.name] ?? '';

    if (field.type === 'checkbox') {
      return (
        <label key={field.name} className="checkbox-field">
          <input
            type="checkbox"
            checked={!!formData.config[field.name]}
            onChange={(e) => handleFormChange(`config.${field.name}`, e.target.checked)}
          />
          <span>{field.label}</span>
        </label>
      );
    }

    if (field.type === 'select') {
      return (
        <div key={field.name} className="form-group">
          <label>{field.label} {field.required && <span className="required">*</span>}</label>
          <select
            value={value}
            onChange={(e) => handleFormChange(`config.${field.name}`, e.target.value)}
            required={field.required}
          >
            {field.options.map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </div>
      );
    }

    return (
      <div key={field.name} className="form-group">
        <label>{field.label} {field.required && <span className="required">*</span>}</label>
        <input
          type={field.type}
          value={value}
          onChange={(e) => handleFormChange(`config.${field.name}`, e.target.value)}
          placeholder={field.placeholder}
          required={field.required}
        />
        {field.sensitive && modalMode === 'edit' && value === '***HIDDEN***' && (
          <small className="help-text">Leave as ***HIDDEN*** to keep existing value, or enter new value to update</small>
        )}
      </div>
    );
  };

  if (loading) {
    return <div className="loading-container"><div className="spinner"></div><p>Loading notification settings...</p></div>;
  }

  return (
    <div className="notification-settings-page">
      <div className="page-header">
        <h1>Notification Settings</h1>
        <p className="subtitle">Configure email, SMS, push notifications, and webhooks</p>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>⚠️</span>
          <p>{error}</p>
        </div>
      )}

      {/* Provider Templates (Add New) */}
      <section className="templates-section">
        <h2>Add Notification Provider</h2>
        <div className="template-grid">
          {templates.map(template => (
            <div key={template.provider_type} className="template-card" onClick={() => openCreateModal(template)}>
              <div className="template-icon">{template.icon}</div>
              <h3>{template.display_name}</h3>
              <p>{template.description}</p>
              <button className="btn btn-primary">Configure</button>
            </div>
          ))}
        </div>
      </section>

      {/* Existing Providers */}
      {providers.length > 0 && (
        <section className="providers-section">
          <h2>Configured Providers ({providers.length})</h2>
          <div className="providers-list">
            {providers.map(provider => {
              const testStatus = notificationService.formatTestStatus(provider.test_status);
              return (
                <div key={provider.id} className="provider-card">
                  <div className="provider-header">
                    <div className="provider-info">
                      <span className="provider-icon">{notificationService.getProviderIcon(provider.provider_type)}</span>
                      <div>
                        <h3>{provider.provider_name}</h3>
                        <p className="provider-type">{notificationService.getProviderDisplayName(provider.provider_type)}</p>
                      </div>
                    </div>
                    <div className="provider-actions">
                      <label className="toggle-switch">
                        <input
                          type="checkbox"
                          checked={provider.enabled}
                          onChange={async (e) => {
                            await notificationService.updateProvider(provider.id, { enabled: e.target.checked });
                            loadData();
                          }}
                        />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>
                  </div>

                  <div className="provider-status">
                    <div className="status-item">
                      <span className="status-label">Status:</span>
                      <span className="status-badge" style={{ backgroundColor: testStatus.color }}>
                        {testStatus.icon} {testStatus.text}
                      </span>
                    </div>
                    {provider.total_sent > 0 && (
                      <div className="status-item">
                        <span className="status-label">Sent:</span>
                        <span>{provider.total_sent} ({provider.total_failed} failed)</span>
                      </div>
                    )}
                  </div>

                  <div className="provider-buttons">
                    <button className="btn btn-sm btn-secondary" onClick={() => openTestModal(provider)}>
                      Test
                    </button>
                    <button className="btn btn-sm btn-secondary" onClick={() => openEditModal(provider)}>
                      Edit
                    </button>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(provider.id)}>
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Create/Edit Modal */}
      {showModal && selectedTemplate && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{modalMode === 'create' ? 'Add' : 'Edit'} {selectedTemplate.display_name}</h2>
              <button className="modal-close" onClick={closeModal}>&times;</button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Provider Name <span className="required">*</span></label>
                  <input
                    type="text"
                    value={formData.provider_name}
                    onChange={(e) => handleFormChange('provider_name', e.target.value)}
                    placeholder="e.g., Gmail Account, Work Twilio"
                    required
                  />
                  <small className="help-text">Give this provider a friendly name to identify it</small>
                </div>

                <div className="form-divider"></div>

                <h3>Configuration</h3>
                {selectedTemplate.config_fields.map(field => renderConfigField(field))}

                <div className="form-group">
                  <label className="checkbox-field">
                    <input
                      type="checkbox"
                      checked={formData.enabled}
                      onChange={(e) => handleFormChange('enabled', e.target.checked)}
                    />
                    <span>Enable this provider</span>
                  </label>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={closeModal}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {modalMode === 'create' ? 'Create' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Test Modal */}
      {showTestModal && testProvider && (
        <div className="modal-overlay" onClick={closeTestModal}>
          <div className="modal-content modal-sm" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Test {testProvider.provider_name}</h2>
              <button className="modal-close" onClick={closeTestModal}>&times;</button>
            </div>

            <form onSubmit={handleTest}>
              <div className="modal-body">
                <p>Send a test notification to verify your configuration is working.</p>

                <div className="form-group">
                  <label>
                    {testProvider.provider_type === 'email' && 'Email Address'}
                    {testProvider.provider_type === 'sms' && 'Phone Number'}
                    {testProvider.provider_type === 'telegram' && 'Chat ID'}
                    {testProvider.provider_type === 'push' && 'Device Token'}
                    {(testProvider.provider_type === 'discord' || testProvider.provider_type === 'webhook') && 'Recipient (optional)'}
                    <span className="required">*</span>
                  </label>
                  <input
                    type="text"
                    value={testRecipient}
                    onChange={(e) => setTestRecipient(e.target.value)}
                    placeholder={
                      testProvider.provider_type === 'email' ? 'your-email@example.com' :
                      testProvider.provider_type === 'sms' ? '+15551234567' :
                      testProvider.provider_type === 'telegram' ? '123456789' :
                      'Recipient'
                    }
                    required={testProvider.provider_type !== 'discord' && testProvider.provider_type !== 'webhook'}
                  />
                </div>

                {testResult && (
                  <div className={`alert ${testResult.success ? 'alert-success' : 'alert-error'}`}>
                    <span>{testResult.success ? '✅' : '❌'}</span>
                    <div>
                      <p><strong>{testResult.message}</strong></p>
                      {testResult.error && <p className="error-detail">{testResult.error}</p>}
                      {testResult.delivery_time && <p className="delivery-time">Delivered in {testResult.delivery_time.toFixed(2)}s</p>}
                    </div>
                  </div>
                )}
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={closeTestModal}>
                  Close
                </button>
                <button type="submit" className="btn btn-primary" disabled={testLoading}>
                  {testLoading ? 'Sending...' : 'Send Test'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationSettingsPage;
