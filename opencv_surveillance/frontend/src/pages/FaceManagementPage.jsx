// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/apiClient';
import HelpButton from '../components/HelpButton';
import { HELP_CONTENT } from '../utils/helpContent';
import { logger } from '../utils/logger';
import './FaceManagementPage.css';

const FaceManagementPage = ({ embedded = false }) => {
  const navigate = useNavigate();
  const [people, setPeople] = useState([]);
  const [statistics, setStatistics] = useState({});
  const [settings, setSettings] = useState(null); // Start with null to show loading state
  const [newPersonName, setNewPersonName] = useState('');
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [uploadFiles, setUploadFiles] = useState([]);
  const [isTraining, setIsTraining] = useState(false);
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(false);

  // Load data on component mount
  useEffect(() => {
    loadPeople();
    loadStatistics();
    loadSettings();

    // Refresh statistics every 10 seconds
    const interval = setInterval(loadStatistics, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadPeople = async () => {
    try {
      const response = await apiClient.get('/faces/people');
      // Handle new paginated response format
      const peopleData = response.data?.data ||
        response.data?.people ||  // Legacy format
        (Array.isArray(response.data) ? response.data : []);
      setPeople(peopleData);
    } catch (error) {
      showMessage('Error loading people: ' + error.message, 'error');
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await apiClient.get('/faces/statistics');
      setStatistics(response.data);
    } catch (error) {
      logger.error('Error loading statistics:', error);
    }
  };

  const loadSettings = async () => {
    try {
      const response = await apiClient.get('/faces/settings');
      setSettings(response.data);
    } catch (error) {
      logger.error('Error loading settings:', error);
    }
  };

  const addPerson = async (e) => {
    e.preventDefault();
    if (!newPersonName.trim()) {
      showMessage('Please enter a person name', 'error');
      return;
    }

    setLoading(true);
    try {
      await apiClient.post('/faces/people', { name: newPersonName });
      showMessage(`Added person: ${newPersonName}`, 'success');
      setNewPersonName('');
      loadPeople();
    } catch (error) {
      showMessage('Error adding person: ' + error.response?.data?.detail || error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const deletePerson = async (personName) => {
    if (!window.confirm(`Delete ${personName} and all their photos?`)) {
      return;
    }

    setLoading(true);
    try {
      await apiClient.delete(`/faces/people/${personName}`);
      showMessage(`Deleted person: ${personName}`, 'success');
      loadPeople();
      loadStatistics();
    } catch (error) {
      showMessage('Error deleting person: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e) => {
    logger.log('[FaceManagement] File input changed');
    logger.log('[FaceManagement] Files selected:', e.target.files);
    logger.log('[FaceManagement] Number of files:', e.target.files.length);
    const filesArray = Array.from(e.target.files);
    logger.log('[FaceManagement] Files array:', filesArray);
    setUploadFiles(filesArray);
  };

  const uploadPhotos = async (personName) => {
    logger.log('[FaceManagement] uploadPhotos called for:', personName);
    logger.log('[FaceManagement] uploadFiles:', uploadFiles);
    logger.log('[FaceManagement] uploadFiles.length:', uploadFiles.length);
    
    if (uploadFiles.length === 0) {
      showMessage('Please select photos to upload', 'error');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    uploadFiles.forEach(file => {
      logger.log('[FaceManagement] Appending file:', file.name, 'Size:', file.size);
      formData.append('files', file);
    });

    logger.log('[FaceManagement] FormData created, sending to API...');
    
    try {
      const response = await apiClient.post(`/faces/people/${personName}/photos`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      logger.log('[FaceManagement] Upload response:', response.data);
      showMessage(response.data.message, 'success');
      setUploadFiles([]);
      setSelectedPerson(null);
      loadPeople();
    } catch (error) {
      logger.error('[FaceManagement] Upload error:', error);
      logger.error('[FaceManagement] Error response:', error.response?.data);
      showMessage('Error uploading photos: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const trainModel = async () => {
    setIsTraining(true);
    showMessage('🔄 Training model... This may take a minute.', 'warning');
    try {
      const response = await apiClient.post('/faces/train', {});
      showMessage('✅ ' + response.data.message, 'success');
      loadStatistics();
    } catch (error) {
      showMessage('❌ Error training model: ' + error.message, 'error');
    } finally {
      setIsTraining(false);
    }
  };

  const updateSettings = async () => {
    setLoading(true);
    try {
      await apiClient.put('/faces/settings', settings);
      showMessage('Settings updated successfully', 'success');
    } catch (error) {
      showMessage('Error updating settings: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const showMessage = (text, type) => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  return (
    <div className="face-management-container">
      <header className="page-header">
        <h1>
          Face Recognition Management
          <HelpButton 
            title={HELP_CONTENT.FACE_RECOGNITION.title}
            description={HELP_CONTENT.FACE_RECOGNITION.description}
          />
        </h1>
      </header>

      {message && (
        <div className={`alert alert-${message.type}`}>
          <span className="alert-icon">
            {message.type === 'success' ? '✓' : message.type === 'error' ? '⚠️' : 'ℹ️'}
          </span>
          <div className="alert-content">{message.text}</div>
        </div>
      )}

      {/* Statistics Section */}
      <section className="statistics-section">
        <h2>Statistics</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{statistics.total_people || 0}</div>
            <div className="stat-label">People</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{statistics.total_encodings || 0}</div>
            <div className="stat-label">Face Encodings</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{statistics.recognitions_today || 0}</div>
            <div className="stat-label">Recognitions Today</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">
              {statistics.last_recognition ? new Date(statistics.last_recognition).toLocaleTimeString() : 'Never'}
            </div>
            <div className="stat-label">Last Recognition</div>
          </div>
        </div>
      </section>

      {/* Settings Section */}
      <section className="settings-section">
        <h2>Settings</h2>
        {!settings ? (
          <p>Loading settings...</p>
        ) : (
          <div className="settings-form">
            <div className="form-group">
              <label>Detection Method:</label>
              <select
                value={settings.detection_method}
                onChange={(e) => setSettings({ ...settings, detection_method: e.target.value })}
                className="form-input"
              >
                <option value="hog">HOG (CPU, Faster)</option>
                <option value="cnn">CNN (GPU, More Accurate)</option>
              </select>
              <small>HOG recommended for Raspberry Pi</small>
            </div>
            <div className="form-group">
              <label>Recognition Threshold: {settings.recognition_threshold.toFixed(2)}</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={settings.recognition_threshold}
                onChange={(e) => setSettings({ ...settings, recognition_threshold: parseFloat(e.target.value) })}
              />
              <small>Lower = stricter (fewer false positives)</small>
            </div>
            <button
              onClick={updateSettings}
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? (
                <>
                  <span className="spinner">◐</span> Saving...
                </>
              ) : 'Save Settings'}
            </button>
          </div>
        )}
      </section>

      {/* Add Person Section */}
      <section className="add-person-section">
        <h2>Add New Person</h2>
        <form onSubmit={addPerson} className="add-person-form">
          <input
            type="text"
            placeholder="Person's name"
            value={newPersonName}
            onChange={(e) => setNewPersonName(e.target.value)}
            disabled={loading}
            className="form-input"
          />
          <button type="submit" disabled={loading} className="btn btn-success">
            Add Person
          </button>
        </form>
      </section>

      {/* People List Section */}
      <section className="people-section">
        <div className="section-header">
          <h2>People ({people.length})</h2>
          <button onClick={trainModel} disabled={isTraining || people.length === 0} className="btn btn-warning">
            {isTraining ? (
              <>
                <span className="spinner">◐</span> Training Model...
              </>
            ) : 'Train Model'}
          </button>
        </div>

        {people.length === 0 ? (
          <p className="no-people">No people added yet. Add a person to get started.</p>
        ) : (
          <div className="people-grid">
            {people.map(person => (
              <div key={person.name} className="person-card">
                <h3>{person.name}</h3>
                <p>Photos: {person.photo_count}</p>
                <div className="person-actions">
                  <button
                    onClick={() => {
                      logger.log('[FaceManagement] Add Photos clicked for:', person.name);
                      setSelectedPerson(person.name);
                    }}
                    className="btn btn-primary btn-sm"
                    disabled={loading}
                  >
                    Add Photos
                  </button>
                  <button
                    onClick={() => deletePerson(person.name)}
                    className="btn btn-danger btn-sm"
                    disabled={loading}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Photo Upload Modal */}
      {selectedPerson && (
        <div 
          className="modal-overlay" 
          onClick={() => {
            logger.log('[FaceManagement] Modal overlay clicked, closing modal');
            setSelectedPerson(null);
          }}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
          }}
        >
          <div 
            className="modal-content" 
            onClick={(e) => {
              logger.log('[FaceManagement] Modal content clicked');
              e.stopPropagation();
            }}
            style={{
              backgroundColor: 'var(--bg-panel)',
              padding: '30px',
              borderRadius: '10px',
              maxWidth: '500px',
              width: '90%',
              boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
              border: '1px solid var(--border-panel)'
            }}
          >
            <h2 style={{ color: 'var(--text-primary)', marginTop: 0 }}>
              Add Photos for {selectedPerson}
            </h2>
            {logger.log('[FaceManagement] Modal is rendering for person:', selectedPerson)}
            <div style={{ margin: '20px 0' }}>
              <label 
                htmlFor="photo-upload" 
                style={{
                  display: 'inline-block',
                  padding: '12px 24px',
                  background: '#007bff',
                  color: '#ffffff',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  marginBottom: '10px',
                  fontSize: '16px',
                  fontWeight: 'bold',
                  border: 'none',
                  transition: 'background 0.3s ease'
                }}
                onMouseOver={(e) => e.target.style.background = '#0056b3'}
                onMouseOut={(e) => e.target.style.background = '#007bff'}
                onClick={() => logger.log('[FaceManagement] Choose Photos label clicked')}
              >
                📁 Choose Photos
              </label>
              <input
                id="photo-upload"
                type="file"
                multiple
                accept="image/jpeg,image/jpg,image/png"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
            </div>
            {uploadFiles.length > 0 && (
              <p style={{ color: 'var(--text-primary)' }}>
                ✅ {uploadFiles.length} file(s) selected
              </p>
            )}
            <div className="modal-actions">
              <button
                onClick={() => uploadPhotos(selectedPerson)}
                disabled={loading || uploadFiles.length === 0}
                className="btn btn-success"
              >
                Upload
              </button>
              <button onClick={() => {
                setSelectedPerson(null);
                setUploadFiles([]);
              }} className="btn btn-secondary">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Instructions */}
      <section className="instructions-section">
        <h2>Quick Guide</h2>
        <ol>
          <li>Add a person by entering their name</li>
          <li>Upload 3-5 clear photos of their face from different angles</li>
          <li>Click "Train Model" to generate face encodings</li>
          <li>Face recognition will now work automatically on your camera streams</li>
        </ol>
        <div className="tips">
          <strong>Tips:</strong>
          <ul>
            <li>Use high-quality, well-lit photos</li>
            <li>Include photos with/without glasses if they wear them</li>
            <li>Retrain the model whenever you add new photos</li>
          </ul>
        </div>
      </section>
    </div>
  );
};

export default FaceManagementPage;