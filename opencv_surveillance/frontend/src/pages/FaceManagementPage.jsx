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
  const [showMergeDialog, setShowMergeDialog] = useState(false);
  const [existingPersonInfo, setExistingPersonInfo] = useState(null);

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

  const addPerson = async (e, mergeIfExists = false, overwriteIfExists = false) => {
    e.preventDefault();
    if (!newPersonName.trim()) {
      showMessage('Please enter a person name', 'error');
      return;
    }

    setLoading(true);
    try {
      const response = await apiClient.post('/faces/people', {
        name: newPersonName,
        merge_if_exists: mergeIfExists,
        overwrite_if_exists: overwriteIfExists
      });
      
      // Check if person already existed (has photos)
      if (response.data.photo_count > 0 && !mergeIfExists && !overwriteIfExists) {
        // Show merge dialog
        setExistingPersonInfo(response.data);
        setShowMergeDialog(true);
      } else {
        showMessage(`Added person: ${newPersonName}`, 'success');
        setNewPersonName('');
        loadPeople();
      }
    } catch (error) {
      showMessage('Error adding person: ' + (error.response?.data?.detail || error.message), 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleMergeChoice = async (choice) => {
    setShowMergeDialog(false);
    if (choice === 'merge') {
      await addPerson({ preventDefault: () => {} }, true, false);
    } else if (choice === 'overwrite') {
      if (window.confirm(`Are you sure you want to delete all existing photos for ${newPersonName}? This cannot be undone.`)) {
        await addPerson({ preventDefault: () => {} }, false, true);
      }
    } else {
      // Cancel - do nothing
      setNewPersonName('');
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

  // Image compression utility with timeout and error handling
  const compressImage = (file, maxWidth = 1920, maxHeight = 1920, quality = 0.85) => {
    return new Promise((resolve, reject) => {
      // Add timeout to prevent hanging
      const timeout = setTimeout(() => {
        reject(new Error('Image compression timeout'));
      }, 30000); // 30 second timeout

      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          try {
            const canvas = document.createElement('canvas');
            let width = img.width;
            let height = img.height;

            // Calculate new dimensions
            if (width > maxWidth || height > maxHeight) {
              if (width > height) {
                height = (height / width) * maxWidth;
                width = maxWidth;
              } else {
                width = (width / height) * maxHeight;
                height = maxHeight;
              }
            }

            canvas.width = width;
            canvas.height = height;

            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, width, height);

            canvas.toBlob(
              (blob) => {
                clearTimeout(timeout);
                if (blob) {
                  const compressedFile = new File([blob], file.name, {
                    type: 'image/jpeg',
                    lastModified: Date.now()
                  });
                  resolve(compressedFile);
                } else {
                  reject(new Error('Failed to compress image'));
                }
              },
              'image/jpeg',
              quality
            );
          } catch (error) {
            clearTimeout(timeout);
            reject(error);
          }
        };
        img.onerror = () => {
          clearTimeout(timeout);
          reject(new Error('Failed to load image'));
        };
        img.src = e.target.result;
      };
      reader.onerror = () => {
        clearTimeout(timeout);
        reject(new Error('Failed to read file'));
      };
      reader.readAsDataURL(file);
    });
  };

  const handleFileSelect = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) {
      return;
    }

    // File size and count limits
    const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB per file
    const MAX_FILES = 20;
    const MAX_TOTAL_SIZE = 50 * 1024 * 1024; // 50MB total

    // Validate file count
    if (files.length > MAX_FILES) {
      showMessage(`Maximum ${MAX_FILES} files allowed. Please select fewer files.`, 'error');
      e.target.value = ''; // Reset input
      return;
    }

    // Validate file types and sizes
    const validFiles = [];
    let totalSize = 0;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      
      // Check file type
      if (!file.type.match(/^image\/(jpeg|jpg|png)$/i)) {
        showMessage(`Skipping ${file.name}: Only JPEG and PNG images are allowed.`, 'error');
        continue;
      }

      // Check file size
      if (file.size > MAX_FILE_SIZE) {
        showMessage(`Skipping ${file.name}: File size exceeds ${MAX_FILE_SIZE / 1024 / 1024}MB limit.`, 'error');
        continue;
      }

      totalSize += file.size;
      if (totalSize > MAX_TOTAL_SIZE) {
        showMessage(`Total file size exceeds ${MAX_TOTAL_SIZE / 1024 / 1024}MB limit.`, 'error');
        break;
      }

      validFiles.push(file);
    }

    if (validFiles.length === 0) {
      showMessage('No valid files selected.', 'error');
      e.target.value = ''; // Reset input
      return;
    }

    // Process files asynchronously with compression (one at a time to avoid blocking)
    setLoading(true);
    showMessage(`Processing ${validFiles.length} file(s)...`, 'warning');

    try {
      const processedFiles = [];
      
      // Process files one at a time with yielding to prevent UI freeze
      for (let i = 0; i < validFiles.length; i++) {
        const file = validFiles[i];
        
        // Yield control to browser every file to prevent freezing
        await new Promise(resolve => setTimeout(resolve, 0));
        
        try {
          // Only compress if file is larger than 2MB
          if (file.size > 2 * 1024 * 1024) {
            const compressed = await compressImage(file);
            processedFiles.push(compressed);
          } else {
            processedFiles.push(file);
          }
          
          // Update progress
          showMessage(`Processing ${i + 1}/${validFiles.length} files...`, 'warning');
        } catch (error) {
          logger.error(`[FaceManagement] Error processing file ${file.name}:`, error);
          // Skip this file but continue with others
          showMessage(`Skipping ${file.name}: ${error.message}`, 'error');
        }
      }

      setUploadFiles(processedFiles);
      showMessage(`Ready to upload ${processedFiles.length} file(s)`, 'success');
    } catch (error) {
      logger.error('[FaceManagement] Error processing files:', error);
      showMessage('Error processing files: ' + error.message, 'error');
      setUploadFiles([]);
    } finally {
      setLoading(false);
    }
  };

  const uploadPhotos = async (personName) => {
    if (uploadFiles.length === 0) {
      showMessage('Please select photos to upload', 'error');
      return;
    }

    setLoading(true);
    showMessage(`Uploading ${uploadFiles.length} photo(s)...`, 'warning');

    try {
      // Upload files in smaller batches to avoid overwhelming the server
      const BATCH_SIZE = 3; // Reduced batch size
      const batches = [];
      
      for (let i = 0; i < uploadFiles.length; i += BATCH_SIZE) {
        batches.push(uploadFiles.slice(i, i + BATCH_SIZE));
      }

      let totalUploaded = 0;
      
      // Process batches one at a time with yielding
      for (let batchIndex = 0; batchIndex < batches.length; batchIndex++) {
        const batch = batches[batchIndex];
        
        // Yield control to browser before each batch
        await new Promise(resolve => setTimeout(resolve, 100));
        
        const formData = new FormData();
        
        batch.forEach(file => {
          formData.append('files', file);
        });

        showMessage(
          `Uploading batch ${batchIndex + 1}/${batches.length} (${totalUploaded + batch.length}/${uploadFiles.length} files)...`,
          'warning'
        );

        try {
          const response = await apiClient.post(`/faces/people/${personName}/photos`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 120000 // 120 second timeout per batch
          });

          totalUploaded += batch.length;
          logger.log(`[FaceManagement] Batch ${batchIndex + 1} uploaded:`, response.data);
        } catch (error) {
          logger.error(`[FaceManagement] Error uploading batch ${batchIndex + 1}:`, error);
          // Continue with next batch even if one fails
          showMessage(`Error uploading batch ${batchIndex + 1}, continuing...`, 'error');
        }
      }

      if (totalUploaded > 0) {
        showMessage(`Successfully uploaded ${totalUploaded} photo(s)`, 'success');
        setUploadFiles([]);
        setSelectedPerson(null);
        loadPeople();
      } else {
        showMessage('No photos were uploaded. Please try again.', 'error');
      }
    } catch (error) {
      logger.error('[FaceManagement] Upload error:', error);
      logger.error('[FaceManagement] Error response:', error.response?.data);
      showMessage('Error uploading photos: ' + (error.response?.data?.detail || error.message), 'error');
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
                {person.preview_photo_url ? (
                  <div className="person-photo-preview">
                    <img 
                      src={person.preview_photo_url} 
                      alt={person.name}
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.nextSibling.style.display = 'block';
                      }}
                    />
                    <div className="person-photo-placeholder" style={{display: 'none'}}>
                      👤
                    </div>
                  </div>
                ) : (
                  <div className="person-photo-placeholder">👤</div>
                )}
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
                disabled={loading}
              />
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '8px', marginBottom: '8px' }}>
              Max 20 files, 10MB per file, 50MB total. Large images will be automatically compressed.
            </p>
            {loading && uploadFiles.length === 0 && (
              <p style={{ color: 'var(--text-primary)' }}>
                ⏳ Processing files...
              </p>
            )}
            {uploadFiles.length > 0 && (
              <div>
                <p style={{ color: 'var(--text-primary)', marginBottom: '8px' }}>
                  ✅ {uploadFiles.length} file(s) ready to upload
                </p>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Total size: {(uploadFiles.reduce((sum, f) => sum + f.size, 0) / 1024 / 1024).toFixed(2)} MB
                </div>
              </div>
            )}
            {loading && uploadFiles.length > 0 && (
              <div style={{ marginTop: '12px', padding: '8px', background: 'var(--bg-main)', borderRadius: '4px', border: '1px solid var(--border-panel)' }}>
                <p style={{ color: 'var(--text-primary)', fontSize: '14px', margin: 0 }}>
                  ⏳ Uploading... Please wait, do not close this window
                </p>
              </div>
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

      {/* Merge/Overwrite Dialog */}
      {showMergeDialog && existingPersonInfo && (
        <div className="modal-overlay" onClick={() => handleMergeChoice('cancel')}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Person Already Exists</h2>
            <p>
              A person folder for <strong>{existingPersonInfo.name}</strong> already exists 
              with <strong>{existingPersonInfo.photo_count}</strong> photo(s).
            </p>
            <p>What would you like to do?</p>
            <div className="modal-actions" style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
              <button
                onClick={() => handleMergeChoice('merge')}
                className="btn btn-primary"
              >
                Merge (Keep Existing Photos)
              </button>
              <button
                onClick={() => handleMergeChoice('overwrite')}
                className="btn btn-danger"
              >
                Overwrite (Delete Existing)
              </button>
              <button
                onClick={() => handleMergeChoice('cancel')}
                className="btn btn-secondary"
              >
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