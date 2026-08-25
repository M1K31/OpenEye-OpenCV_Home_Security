// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect, lazy, Suspense } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import apiClient from '../api/apiClient';
import HelpButton from '../components/HelpButton';
import PersonDetectionsModal from '../components/PersonDetectionsModal';
import { HELP_CONTENT } from '../utils/helpContent';
import { logger } from '../utils/logger';
import './FaceManagementPage.css';
import { describeApiError } from '../utils/apiError';

// Lazy load sub-pages for tab content
const FaceClusteringPage = lazy(() => import('./FaceClusteringPage'));
const DetectionsPage = lazy(() => import('./DetectionsPage'));

// Tab definitions
const TABS = [
  { id: 'profiles', label: 'Profiles', icon: '👤' },
  { id: 'clustering', label: 'Face Clustering', icon: '🔗' },
  { id: 'detections', label: 'All Detections', icon: '🔍' },
];

const FaceManagementPage = ({ embedded = false }) => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'profiles');
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
  const [viewingDetections, setViewingDetections] = useState(null);
  const [trainingPerson, setTrainingPerson] = useState(null); // Track which person is being trained

  // Retroactive search state
  const [searchingPerson, setSearchingPerson] = useState(null);
  const [searchTolerance, setSearchTolerance] = useState(0.4); // Default to strict
  const [searchHoursBack, setSearchHoursBack] = useState(168); // 1 week
  const [searchResults, setSearchResults] = useState(null);
  const [isSearching, setIsSearching] = useState(false);

  // Load data on component mount
  useEffect(() => {
    loadPeople();
    loadStatistics();
    loadSettings();

    // Refresh statistics every 10 seconds
    const interval = setInterval(loadStatistics, 10000);
    return () => clearInterval(interval);
  }, []);

  // Follow training that is already running, wherever it was started.
  //
  // Training now fires from several places — an upload, a reassignment, a
  // clustering pass — so an indicator driven only by this page's own actions
  // would be wrong more often than right. /faces/training-status has existed
  // and gone unused; it reports the truth for all of them.
  const followTraining = async () => {
    setIsTraining(true);
    const deadline = Date.now() + 5 * 60 * 1000;   // give up after 5 minutes
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 2000));
      try {
        const { data } = await apiClient.get('/faces/training-status');
        if (!data.training_in_progress) break;
      } catch {
        break;   // if the check itself fails, stop claiming to know
      }
    }
    setIsTraining(false);
    loadPeople();
    loadStatistics();
  };

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
      showMessage('Error adding person: ' + (describeApiError(error)), 'error');
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

  // Image compression utility
  const compressImage = (file, maxWidth = 1920, maxHeight = 1920, quality = 0.85) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
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
        };
        img.onerror = reject;
        img.src = e.target.result;
      };
      reader.onerror = reject;
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

    // Process files asynchronously with compression
    setLoading(true);
    showMessage(`Processing ${validFiles.length} file(s)...`, 'warning');

    try {
      const processedFiles = await Promise.all(
        validFiles.map(async (file) => {
          // Only compress if file is larger than 2MB
          if (file.size > 2 * 1024 * 1024) {
            return await compressImage(file);
          }
          return file;
        })
      );

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
      // Upload files in batches to avoid overwhelming the server
      const BATCH_SIZE = 5;
      const batches = [];
      
      for (let i = 0; i < uploadFiles.length; i += BATCH_SIZE) {
        batches.push(uploadFiles.slice(i, i + BATCH_SIZE));
      }

      let totalUploaded = 0;
      
      for (let batchIndex = 0; batchIndex < batches.length; batchIndex++) {
        const batch = batches[batchIndex];
        const formData = new FormData();
        
        batch.forEach(file => {
          formData.append('files', file);
        });

        // Train once, after the last batch. The server trains by default, and
        // training after every batch would re-encode the whole person each time
        // — five batches meaning five full passes to learn one set of photos.
        const isLastBatch = batchIndex === batches.length - 1;
        formData.append('auto_train', isLastBatch ? 'true' : 'false');

        showMessage(
          `Uploading batch ${batchIndex + 1}/${batches.length} (${totalUploaded + batch.length}/${uploadFiles.length} files)...`,
          'warning'
        );

        const response = await apiClient.post(`/faces/people/${personName}/photos`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 60000 // 60 second timeout per batch
        });

        totalUploaded += batch.length;
        logger.log(`[FaceManagement] Batch ${batchIndex + 1} uploaded:`, response.data);
      }

      showMessage(
        `Uploaded ${totalUploaded} photo(s) — learning ${personName}'s face now. ` +
        `Recognition will use them shortly.`,
        'success'
      );
      setUploadFiles([]);
      setSelectedPerson(null);
      loadPeople();
      followTraining();
    } catch (error) {
      logger.error('[FaceManagement] Upload error:', error);
      logger.error('[FaceManagement] Error response:', error.response?.data);
      showMessage('Error uploading photos: ' + (describeApiError(error)), 'error');
    } finally {
      setLoading(false);
    }
  };

  // Train a specific person only (faster than full model training)
  const trainPerson = async (personName) => {
    setTrainingPerson(personName);
    showMessage(`🔄 Training ${personName}...`, 'warning');
    try {
      const response = await apiClient.post(`/faces/people/${encodeURIComponent(personName)}/train`);
      const result = response.data;
      showMessage(
        `✅ Trained ${result.encodings_added} encoding(s) for "${personName}" in ${result.training_time?.toFixed(1) || '?'}s`,
        'success'
      );
      loadStatistics();
    } catch (error) {
      showMessage('❌ Error training: ' + (describeApiError(error)), 'error');
    } finally {
      setTrainingPerson(null);
    }
  };

  // Search past events for a specific person
  const searchPastEvents = async () => {
    if (!searchingPerson) return;

    setIsSearching(true);
    setSearchResults(null);
    showMessage(`🔍 Searching past events for ${searchingPerson}...`, 'warning');

    try {
      const response = await apiClient.post(
        `/scheduled/search-person/${encodeURIComponent(searchingPerson)}`,
        {
          tolerance: searchTolerance,
          hours_back: searchHoursBack,
          max_events: 5000
        }
      );

      const result = response.data.result;
      setSearchResults(result);

      if (result.matches_found > 0) {
        showMessage(
          `✅ Found ${result.matches_found} match(es) for "${searchingPerson}" out of ${result.events_searched} events searched`,
          'success'
        );
        loadStatistics(); // Refresh statistics
      } else {
        showMessage(
          `No matches found for "${searchingPerson}" in ${result.events_searched} events`,
          'warning'
        );
      }
    } catch (error) {
      showMessage(
        '❌ Search failed: ' + (describeApiError(error)),
        'error'
      );
      setSearchResults(null);
    } finally {
      setIsSearching(false);
    }
  };

  // Get tolerance label for display
  const getToleranceLabel = (value) => {
    if (value <= 0.3) return 'Very Strict';
    if (value <= 0.4) return 'Strict';
    if (value <= 0.5) return 'Moderate';
    if (value <= 0.6) return 'Normal';
    return 'Lenient';
  };

  // Get hours back label for display
  const getHoursLabel = (hours) => {
    if (hours <= 24) return '24 hours';
    if (hours <= 48) return '2 days';
    if (hours <= 72) return '3 days';
    if (hours <= 168) return '1 week';
    if (hours <= 336) return '2 weeks';
    return '1 month';
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

  // Handle tab change
  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    setSearchParams({ tab: tabId });
  };

  // Render tab content based on active tab
  const renderTabContent = () => {
    switch (activeTab) {
      case 'clustering':
        return (
          <Suspense fallback={<div className="tab-loading">Loading Face Clustering...</div>}>
            <FaceClusteringPage />
          </Suspense>
        );
      case 'detections':
        return (
          <Suspense fallback={<div className="tab-loading">Loading Detections...</div>}>
            <DetectionsPage />
          </Suspense>
        );
      default:
        return renderProfilesTab();
    }
  };

  // Render the profiles tab content (existing content)
  const renderProfilesTab = () => (
    <>
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
          {/* The "Train Model" button is gone.
              It retrained EVERY person to add photographs of one — 1,062 images
              on one installation — and nothing in the interface said so. Worse,
              it was a required step nobody was told about: uploads did not train,
              so a person added photographs, saw "Photos: 3", and wondered why
              recognition never improved.
              Uploading now trains that person automatically, in the background.
              The per-person Train button below remains as a repair tool for when
              something has drifted. */}
          {isTraining && (
            <span className="training-indicator">
              <span className="spinner">◐</span> Learning faces…
            </span>
          )}
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
                    onClick={() => {
                      logger.log('[FaceManagement] View Detections clicked for:', person.name);
                      setViewingDetections(person.name);
                    }}
                    className="btn btn-secondary btn-sm"
                    disabled={loading}
                  >
                    View Detections
                  </button>
                  <button
                    onClick={() => trainPerson(person.name)}
                    className="btn btn-warning btn-sm"
                    disabled={loading || trainingPerson === person.name || person.photo_count === 0}
                    title={person.photo_count === 0 ? 'Add photos first' : 'Train this person only'}
                  >
                    {trainingPerson === person.name ? '◐' : 'Train'}
                  </button>
                  <button
                    onClick={() => {
                      setSearchingPerson(person.name);
                      setSearchResults(null);
                    }}
                    className="btn btn-info btn-sm"
                    disabled={loading || person.photo_count === 0}
                    title={person.photo_count === 0 ? 'Train first to enable search' : 'Search past events for this person'}
                  >
                    Search
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

      {/* Instructions */}
      <section className="instructions-section">
        <h2>Quick Guide</h2>
        <ol>
          <li>Add a person by entering their name</li>
          <li>Upload 3-5 clear photos of their face from different angles</li>
          <li>That is it — their face is learned automatically as the photos upload</li>
          <li>Face recognition then works on your camera streams</li>
        </ol>
        <div className="tips">
          <strong>Tips:</strong>
          <ul>
            <li>Use high-quality, well-lit photos</li>
            <li>Include photos with/without glasses if they wear them</li>
            <li>Retrain the model whenever you add new photos</li>
            <li>Use "View Detections" to review and correct face recognition results</li>
          </ul>
        </div>
      </section>
    </>
  );

  return (
    <div className="face-management-container">
      <header className="page-header">
        <h1>
          AI & Faces
          <HelpButton
            title={HELP_CONTENT.FACE_RECOGNITION.title}
            description={HELP_CONTENT.FACE_RECOGNITION.description}
          />
        </h1>
      </header>

      {/* Tab Navigation */}
      <nav className="tab-navigation">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => handleTabChange(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
          </button>
        ))}
      </nav>

      {/* Alert Messages (show on all tabs) */}
      {message && (
        <div className={`alert alert-${message.type}`}>
          <span className="alert-icon">
            {message.type === 'success' ? '✓' : message.type === 'error' ? '⚠️' : 'ℹ️'}
          </span>
          <div className="alert-content">{message.text}</div>
        </div>
      )}

      {/* Tab Content */}
      <div className="tab-content">
        {renderTabContent()}
      </div>

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
                  background: 'var(--button-primary-bg)',
                  color: 'var(--button-primary-text)',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  marginBottom: '10px',
                  fontSize: '16px',
                  fontWeight: 'bold',
                  border: 'none',
                  transition: 'background 0.3s ease'
                }}
                onMouseOver={(e) => e.target.style.background = 'var(--button-primary-hover-bg, var(--button-primary-bg))'}
                onMouseOut={(e) => e.target.style.background = 'var(--button-primary-bg)'}
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
            <li>Use "View Detections" to review and correct face recognition results</li>
            <li>Use "Search" to find past detections that match a person</li>
          </ul>
        </div>
      </section>

      {/* Search Past Events Modal */}
      {searchingPerson && (
        <div
          className="modal-overlay"
          onClick={() => {
            if (!isSearching) {
              setSearchingPerson(null);
              setSearchResults(null);
            }
          }}
        >
          <div
            className="modal-content search-modal"
            onClick={(e) => e.stopPropagation()}
            style={{
              backgroundColor: 'var(--bg-panel)',
              padding: '24px',
              borderRadius: '12px',
              maxWidth: '500px',
              width: '90%',
              boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
              border: '1px solid var(--border-panel)'
            }}
          >
            <h2 style={{ color: 'var(--text-primary)', marginTop: 0, marginBottom: '16px' }}>
              Search Past Events for {searchingPerson}
            </h2>

            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '20px' }}>
              Search through past "Unknown" face detections to find matches for this person.
              This will update matching events with the person's name.
            </p>

            {/* Tolerance Slider */}
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', color: 'var(--text-primary)', fontWeight: '500', marginBottom: '8px' }}>
                Matching Strictness: <strong>{getToleranceLabel(searchTolerance)}</strong>
              </label>
              <input
                type="range"
                min="0.2"
                max="0.7"
                step="0.05"
                value={searchTolerance}
                onChange={(e) => setSearchTolerance(parseFloat(e.target.value))}
                style={{ width: '100%', cursor: 'pointer' }}
                disabled={isSearching}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                <span>Stricter (fewer matches)</span>
                <span>Tolerance: {searchTolerance.toFixed(2)}</span>
                <span>Lenient (more matches)</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '8px' }}>
                Stricter matching reduces false positives. Recommended: 0.35-0.45 for manual searches.
              </p>
            </div>

            {/* Time Range Slider */}
            <div style={{ marginBottom: '24px' }}>
              <label style={{ display: 'block', color: 'var(--text-primary)', fontWeight: '500', marginBottom: '8px' }}>
                Search Period: <strong>{getHoursLabel(searchHoursBack)}</strong>
              </label>
              <input
                type="range"
                min="24"
                max="720"
                step="24"
                value={searchHoursBack}
                onChange={(e) => setSearchHoursBack(parseInt(e.target.value))}
                style={{ width: '100%', cursor: 'pointer' }}
                disabled={isSearching}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                <span>24 hours</span>
                <span>1 week</span>
                <span>1 month</span>
              </div>
            </div>

            {/* Results */}
            {searchResults && (
              <div
                style={{
                  backgroundColor: searchResults.matches_found > 0 ? 'rgba(76, 175, 80, 0.1)' : 'rgba(255, 152, 0, 0.1)',
                  border: `1px solid ${searchResults.matches_found > 0 ? 'var(--color-success)' : 'var(--color-warning)'}`,
                  borderRadius: '8px',
                  padding: '16px',
                  marginBottom: '20px'
                }}
              >
                <h4 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)' }}>
                  Search Results
                </h4>
                <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                  <p style={{ margin: '4px 0' }}>Events searched: <strong>{searchResults.events_searched}</strong></p>
                  <p style={{ margin: '4px 0' }}>Matches found: <strong style={{ color: searchResults.matches_found > 0 ? 'var(--color-success)' : 'inherit' }}>{searchResults.matches_found}</strong></p>
                  <p style={{ margin: '4px 0' }}>Events updated: <strong>{searchResults.events_updated}</strong></p>
                  {searchResults.errors > 0 && (
                    <p style={{ margin: '4px 0', color: 'var(--color-error)' }}>Errors: {searchResults.errors}</p>
                  )}
                </div>
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => {
                  setSearchingPerson(null);
                  setSearchResults(null);
                }}
                className="btn btn-secondary"
                disabled={isSearching}
              >
                {searchResults ? 'Close' : 'Cancel'}
              </button>
              <button
                onClick={searchPastEvents}
                className="btn btn-primary"
                disabled={isSearching}
              >
                {isSearching ? (
                  <>
                    <span className="spinner">◐</span> Searching...
                  </>
                ) : searchResults ? 'Search Again' : 'Start Search'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Person Detections Modal */}
      {viewingDetections && (
        <PersonDetectionsModal
          personName={viewingDetections}
          allPeople={people}
          onClose={() => setViewingDetections(null)}
          onUpdate={() => {
            loadStatistics();
          }}
        />
      )}
    </div>
  );
};

export default FaceManagementPage;