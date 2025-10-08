// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import HelpButton from '../components/HelpButton';
import { HELP_CONTENT } from '../utils/helpContent';
import './FaceManagementPage.css';

const FaceManagementPage = ({ embedded = false }) => {
  const navigate = useNavigate();
  const [people, setPeople] = useState([]);
  const [statistics, setStatistics] = useState({});
  const [settings, setSettings] = useState({
    detection_method: 'hog',
    recognition_threshold: 0.6
  });
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
      const response = await axios.get('/api/faces/people');
      setPeople(response.data);
    } catch (error) {
      showMessage('Error loading people: ' + error.message, 'error');
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await axios.get('/api/faces/statistics');
      setStatistics(response.data);
    } catch (error) {
      console.error('Error loading statistics:', error);
    }
  };

  const loadSettings = async () => {
    try {
      const response = await axios.get('/api/faces/settings');
      setSettings(response.data);
    } catch (error) {
      console.error('Error loading settings:', error);
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
      await axios.post('/api/faces/people', { name: newPersonName });
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
      await axios.delete(`/api/faces/people/${personName}`);
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
    setUploadFiles(Array.from(e.target.files));
  };

  const uploadPhotos = async (personName) => {
    if (uploadFiles.length === 0) {
      showMessage('Please select photos to upload', 'error');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    uploadFiles.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post(`/api/faces/people/${personName}/photos`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      showMessage(response.data.message, 'success');
      setUploadFiles([]);
      setSelectedPerson(null);
      loadPeople();
    } catch (error) {
      showMessage('Error uploading photos: ' + error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const trainModel = async () => {
    setIsTraining(true);
    showMessage('🔄 Training model... This may take a minute.', 'warning');
    try {
      const response = await axios.post('/api/faces/train', {});
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
      await axios.put('/api/faces/settings', settings);
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
        {!embedded && (
          <button onClick={() => navigate('/')} className="btn-secondary">Back to Dashboard</button>
        )}
      </header>

      {message && (
        <div className={`message message-${message.type}`}>
          {message.text}
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
        <div className="settings-form">
          <div className="form-group">
            <label>Detection Method:</label>
            <select
              value={settings.detection_method}
              onChange={(e) => setSettings({ ...settings, detection_method: e.target.value })}
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
          <button onClick={updateSettings} disabled={loading} className="btn-primary">
            Save Settings
          </button>
        </div>
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
          />
          <button type="submit" disabled={loading} className="btn-success">
            Add Person
          </button>
        </form>
      </section>

      {/* People List Section */}
      <section className="people-section">
        <div className="section-header">
          <h2>People ({people.length})</h2>
          <button onClick={trainModel} disabled={isTraining || people.length === 0} className="btn-warning">
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
                    onClick={() => setSelectedPerson(person.name)}
                    className="btn-small btn-primary"
                    disabled={loading}
                  >
                    Add Photos
                  </button>
                  <button
                    onClick={() => deletePerson(person.name)}
                    className="btn-small btn-danger"
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
        <div className="modal-overlay" onClick={() => setSelectedPerson(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Add Photos for {selectedPerson}</h2>
            <input
              type="file"
              multiple
              accept="image/jpeg,image/jpg,image/png"
              onChange={handleFileSelect}
            />
            {uploadFiles.length > 0 && (
              <p>{uploadFiles.length} file(s) selected</p>
            )}
            <div className="modal-actions">
              <button
                onClick={() => uploadPhotos(selectedPerson)}
                disabled={loading || uploadFiles.length === 0}
                className="btn-success"
              >
                Upload
              </button>
              <button onClick={() => {
                setSelectedPerson(null);
                setUploadFiles([]);
              }} className="btn-secondary">
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