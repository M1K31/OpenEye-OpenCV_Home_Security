// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { activateOnKey } from '../utils/a11y';
import { logger } from '../utils/logger';
import apiClient from '../api/apiClient';
import { useNavigate } from 'react-router-dom';
import { Button, TextField, Switch } from '../components/universal';

/**
 * LazyVideo Component
 * Only loads video when it becomes visible in viewport
 * Prevents browser freeze from hundreds of concurrent video requests
 */
const LazyVideo = ({ src, recordingId, style }) => {
  const videoRef = useRef(null);
  const [isVisible, setIsVisible] = useState(false);
  const [shouldLoad, setShouldLoad] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            setIsVisible(true);
            // Delay loading slightly to prevent all videos loading at once
            setTimeout(() => setShouldLoad(true), 100);
          }
        });
      },
      { rootMargin: '200px' } // Start loading when within 200px of viewport
    );

    if (videoRef.current) {
      observer.observe(videoRef.current);
    }

    return () => {
      if (videoRef.current) {
        observer.unobserve(videoRef.current);
      }
    };
  }, []);

  return (
    <div ref={videoRef} style={{ ...style, backgroundColor: '#000' }}>
      {shouldLoad ? (
        <video
          src={src}
          controls
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          preload="metadata"
        />
      ) : (
        <div style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#999',
          fontSize: '3rem'
        }}>
          🎬
        </div>
      )}
    </div>
  );
};

const RecordingsPage = () => {
  const navigate = useNavigate();
  const [recordings, setRecordings] = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('videos'); // 'videos' or 'snapshots'
  const [selectedRecording, setSelectedRecording] = useState(null);
  const [filterCamera, setFilterCamera] = useState('all');
  const [cameras, setCameras] = useState([]);
  const [searchPersonName, setSearchPersonName] = useState(''); // New: person search
  
  // Date range filter state
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  
  // Infinite scroll state (replacing pagination)
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(20);
  const [totalItems, setTotalItems] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  
  // Batch selection state
  const [selectedItems, setSelectedItems] = useState([]);
  const [selectAll, setSelectAll] = useState(false);
  
  // Ref for intersection observer
  const observerTarget = useRef(null);

  // Load cameras once on mount
  useEffect(() => {
    loadCameras();
  }, []);

  // Load data only for active tab when filters change
  useEffect(() => {
    // Reset page when filters change
    setCurrentPage(1);
    setHasMore(true);

    // Only load data for the currently active tab
    if (activeTab === 'videos') {
      setRecordings([]);
      loadRecordings(true);
    } else {
      setSnapshots([]);
      loadSnapshots(true);
    }
  }, [filterCamera, startDate, endDate, searchPersonName, activeTab]); // Reload when filters or tab changes
  
  // Infinite scroll observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading && !loadingMore) {
          loadMoreItems();
        }
      },
      { threshold: 0.1 }
    );

    if (observerTarget.current) {
      observer.observe(observerTarget.current);
    }

    return () => {
      if (observerTarget.current) {
        observer.unobserve(observerTarget.current);
      }
    };
  }, [hasMore, loading, loadingMore, activeTab]);
  
  const loadMoreItems = useCallback(() => {
    if (!hasMore || loadingMore) return;
    
    setCurrentPage(prev => prev + 1);
    if (activeTab === 'videos') {
      loadRecordings(false);
    } else {
      loadSnapshots(false);
    }
  }, [hasMore, loadingMore, activeTab]);

  const loadCameras = async () => {
    try {
      const response = await apiClient.get('/cameras/');
      // Handle both formats: direct array or { cameras: [] }
      setCameras(Array.isArray(response.data) ? response.data : (response.data.cameras || []));
    } catch (err) {
      logger.error('Error loading cameras:', err);
      setCameras([]);
    }
  };

  const loadRecordings = async (reset = false) => {
    try {
      if (reset) {
        setLoading(true);
      } else {
        setLoadingMore(true);
      }
      
      // Build query parameters
      const params = new URLSearchParams();
      if (filterCamera !== 'all') {
        params.append('camera_id', filterCamera);
      }
      if (startDate) {
        // Set to start of day in local timezone, then convert to ISO
        const startDateTime = new Date(startDate);
        startDateTime.setHours(0, 0, 0, 0);
        params.append('start_date', startDateTime.toISOString());
      }
      if (endDate) {
        // Set to end of day in local timezone (don't add extra day - that causes wrong dates)
        const endDateTime = new Date(endDate);
        endDateTime.setHours(23, 59, 59, 999);
        params.append('end_date', endDateTime.toISOString());
      }
      if (searchPersonName) {
        params.append('person_name', searchPersonName);
      }
      params.append('page', (reset ? 1 : currentPage).toString());
      params.append('page_size', itemsPerPage.toString());

      const queryString = params.toString();
      const response = await apiClient.get(`/recordings/${queryString ? '?' + queryString : ''}`);

      // Handle new paginated response format
      const recordingsData = response.data?.data ||
        response.data?.recordings ||  // Legacy format
        (Array.isArray(response.data) ? response.data : []);

      if (reset) {
        setRecordings(recordingsData);
      } else {
        setRecordings(prev => [...prev, ...recordingsData]);
      }

      // Set total count for pagination from new metadata structure
      const pagination = response.data?.pagination;
      const total = pagination?.total || response.data?.total || recordingsData.length;
      setTotalItems(total);

      // Use has_more from new pagination metadata
      const apiHasMore = pagination?.has_more !== undefined
        ? pagination.has_more
        : response.data?.has_more;

      if (apiHasMore !== undefined) {
        setHasMore(apiHasMore);
      } else {
        // Fallback for legacy API responses
        const loadedCount = reset ? recordingsData.length : recordings.length + recordingsData.length;
        setHasMore(loadedCount < total && recordingsData.length === itemsPerPage);
      }
      
      setError('');
    } catch (err) {
      logger.error('Error loading recordings:', err);
      setError('Failed to load recordings');
      if (reset) {
        setRecordings([]);
      }
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  const loadSnapshots = async (reset = false) => {
    try {
      if (reset) {
        setLoading(true);
      } else {
        setLoadingMore(true);
      }
      
      // Build query parameters
      const params = new URLSearchParams();
      if (filterCamera !== 'all') {
        params.append('camera_id', filterCamera);
      }
      if (startDate) {
        // Set to start of day in local timezone, then convert to ISO
        const startDateTime = new Date(startDate);
        startDateTime.setHours(0, 0, 0, 0);
        params.append('start_date', startDateTime.toISOString());
      }
      if (endDate) {
        // Set to end of day in local timezone (don't add extra day)
        const endDateTime = new Date(endDate);
        endDateTime.setHours(23, 59, 59, 999);
        params.append('end_date', endDateTime.toISOString());
      }
      if (searchPersonName) {
        params.append('person_name', searchPersonName);
      }
      // Use page and page_size (not skip/limit) to match backend API
      params.append('page', (reset ? 1 : currentPage).toString());
      params.append('page_size', itemsPerPage.toString());
      
      const queryString = params.toString();
      
      // Load motion events (includes events with AND without face detection)
      const response = await apiClient.get(`/motion-events/${queryString ? '?' + queryString : ''}`);
      // Handle wrapped response (backward compatible with v3.5.2)
      const events = response.data.events || response.data;
      const snapshotsData = Array.isArray(events) ? events : [];
      // Filter only events that have a snapshot_path
      const filtered = snapshotsData.filter(event => event.snapshot_path);

      if (reset) {
        setSnapshots(filtered);
      } else {
        setSnapshots(prev => [...prev, ...filtered]);
      }

      // Use has_more from API if available
      const apiHasMore = response.data?.has_more;
      if (apiHasMore !== undefined) {
        setHasMore(apiHasMore);
      } else {
        // Fallback: check if we got a full page worth of results
        setHasMore(filtered.length === itemsPerPage);
      }

      // Set total count
      const total = response.data?.total || filtered.length;
      setTotalItems(total);
      
      // Check if there are more items
      const loadedCount = reset ? filtered.length : snapshots.length + filtered.length;
      setHasMore(loadedCount < total && filtered.length === itemsPerPage);
    } catch (err) {
      logger.error('Error loading snapshots:', err);
      if (reset) {
        setSnapshots([]);
      }
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  const deleteRecording = async (recordingId) => {
    if (!window.confirm('Are you sure you want to delete this recording?')) {
      return;
    }
    
    try {
      await apiClient.delete(`/recordings/${recordingId}`);
      loadRecordings();
    } catch (err) {
      logger.error('Error deleting recording:', err);
      alert('Failed to delete recording');
    }
  };

  const deleteSnapshot = async (eventId) => {
    if (!window.confirm('Are you sure you want to delete this motion event snapshot?')) {
      return;
    }
    
    try {
      await apiClient.delete(`/motion-events/${eventId}`);
      loadSnapshots();
    } catch (err) {
      logger.error('Error deleting snapshot:', err);
      alert('Failed to delete snapshot');
    }
  };

  // Batch selection handlers
  const toggleSelectAll = () => {
    if (selectAll) {
      setSelectedItems([]);
      setSelectAll(false);
    } else {
      const items = activeTab === 'videos' ? recordings : snapshots;
      setSelectedItems(items.map(item => item.id));
      setSelectAll(true);
    }
  };

  const toggleItemSelection = (itemId) => {
    setSelectedItems(prev => {
      if (prev.includes(itemId)) {
        return prev.filter(id => id !== itemId);
      } else {
        return [...prev, itemId];
      }
    });
  };

  const batchDelete = async () => {
    if (selectedItems.length === 0) {
      alert('No items selected');
      return;
    }

    if (!window.confirm(`Are you sure you want to delete ${selectedItems.length} items?`)) {
      return;
    }

    try {
      const endpoint = activeTab === 'videos' ? '/recordings/' : '/motion-events/';
      
      // Delete all selected items
      await Promise.all(
        selectedItems.map(itemId => apiClient.delete(`${endpoint}${itemId}`))
      );

      // Reload data and clear selection
      if (activeTab === 'videos') {
        loadRecordings(true);
      } else {
        loadSnapshots(true);
      }
      setSelectedItems([]);
      setSelectAll(false);
      alert(`Successfully deleted ${selectedItems.length} items`);
    } catch (err) {
      logger.error('Error batch deleting:', err);
      alert('Failed to delete some items');
    }
  };

  const batchExportZip = async () => {
    if (selectedItems.length === 0) {
      alert('No items selected');
      return;
    }

    try {
      const endpoint = activeTab === 'videos' ? '/recordings/export' : '/snapshots/export';
      const requestBody = activeTab === 'videos' 
        ? { recording_ids: selectedItems }
        : { event_ids: selectedItems };
      
      // Create a temporary link to download the ZIP
      const response = await apiClient.post(endpoint, requestBody, {
        responseType: 'blob'
      });

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      const timestamp = new Date().toISOString().split('T')[0];
      link.setAttribute('download', `${activeTab}_export_${timestamp}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      alert(`Successfully exported ${selectedItems.length} items`);
    } catch (err) {
      logger.error('Error exporting ZIP:', err);
      alert('Failed to export items. This feature may not be implemented on the backend yet.');
    }
  };

  const clearFilters = () => {
    setStartDate('');
    setEndDate('');
    setFilterCamera('all');
    setSearchPersonName('');
    setCurrentPage(1);
  };

  // Pagination handlers
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  
  const goToPage = (page) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  /**
   * Convert file system path to web URL
   * Maps absolute paths to mounted static file endpoints
   *
   * Note: As of v3.5.6, the API returns normalized snapshot paths (just filenames)
   * without directory prefixes for motion events.
   */
  const convertPathToUrl = (filePath) => {
    if (!filePath) return '';

    // If already a properly formatted web URL, return as-is
    if (filePath.startsWith('http://') || filePath.startsWith('https://')) {
      return filePath;
    }

    // If it's already a relative web path (starts with /api/), return as-is
    if (filePath.startsWith('/api/')) {
      return filePath;
    }

    // If it's already a relative web path (starts with /data/ or /legacy/), return as-is
    if (filePath.startsWith('/data/') || filePath.startsWith('/legacy/') || filePath.startsWith('/recordings/') || filePath.startsWith('/faces/')) {
      return filePath;
    }

    // Extract just the filename from the full path
    const filename = filePath.split('/').pop().split('\\').pop(); // Handle both / and \ separators

    // Check if this is a snapshot (in data/snapshots directory) - with or without leading slash
    if (filePath.includes('data/snapshots') || filePath.includes('data\\snapshots')) {
      const url = `/api/snapshots/${filename}`;
      logger.log('🔄 Converting snapshot path:', filePath, '→', url);
      return url;
    }

    // Check if this is a face detection snapshot
    if (filePath.includes('faces') || filePath.includes('Faces')) {
      return `/faces/${filename}`;
    }

    // Check if this is a recording
    if (filePath.includes('recordings') || filePath.includes('Recordings')) {
      return `/recordings/${filename}`;
    }

    // Default: Assume it's a normalized snapshot path (just filename from API)
    // This handles the v3.5.6+ API response format where snapshot_path is just the filename
    logger.log('📸 Treating as normalized snapshot path:', filePath, '→ /api/snapshots/' + filename);
    return `/api/snapshots/${filename}`;
  };

  // Data is already filtered server-side, no need for client filtering
  const displayedRecordings = recordings;
  const displayedSnapshots = snapshots;

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>📼 Recordings & Snapshots</h1>
      </header>

      {/* Tab Selector */}
      <div style={styles.tabContainer}>
        <Button
          variant={activeTab === 'videos' ? 'primary' : 'secondary'}
          size="medium"
          onClick={() => setActiveTab('videos')}
          icon="🎥"
        >
          Videos ({displayedRecordings.length})
        </Button>
        <Button
          variant={activeTab === 'snapshots' ? 'primary' : 'secondary'}
          size="medium"
          onClick={() => setActiveTab('snapshots')}
          icon="📷"
        >
          Snapshots ({displayedSnapshots.length})
        </Button>
      </div>

      {/* Camera Filter */}
      <div style={styles.filterContainer}>
        <label style={styles.filterLabel}>Filter by Camera:</label>
        <select
          value={filterCamera}
          onChange={(e) => setFilterCamera(e.target.value)}
          className="form-input"
        >
          <option value="all">All Cameras</option>
          {cameras.map(camera => (
            <option key={camera.camera_id} value={camera.camera_id}>
              {camera.name || camera.camera_id}
            </option>
          ))}
        </select>
      </div>

      {/* Date Range Filter */}
      <div style={styles.filterContainer}>
        <label style={styles.filterLabel}>Date Range:</label>
        <div style={styles.dateRangeContainer}>
          <input
            type="date"
            value={startDate}
            onChange={(e) => {
              setStartDate(e.target.value);
              setCurrentPage(1); // Reset to page 1 when filter changes
            }}
            className="form-input"
            placeholder="Start Date"
          />
          <span style={styles.dateSeparator}>to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => {
              setEndDate(e.target.value);
              setCurrentPage(1);
            }}
            className="form-input"
            placeholder="End Date"
          />
          {(startDate || endDate || filterCamera !== 'all') && (
            <Button
              variant="secondary"
              size="small"
              onClick={clearFilters}
              icon="🗑️"
            >
              Clear Filters
            </Button>
          )}
        </div>
      </div>

      {/* Person Name Search (for snapshots with face detection) */}
      {activeTab === 'snapshots' && (
        <div style={styles.filterContainer}>
          <label style={styles.filterLabel}>Search by Person:</label>
          <input
            type="text"
            value={searchPersonName}
            onChange={(e) => setSearchPersonName(e.target.value)}
            placeholder="Enter person name..."
            className="form-input"
          />
          {searchPersonName && (
            <Button
              variant="secondary"
              size="small"
              onClick={() => setSearchPersonName('')}
            >
              ✕
            </Button>
          )}
        </div>
      )}

      {/* Batch Actions */}
      {(activeTab === 'videos' ? recordings.length : snapshots.length) > 0 && (
        <div style={styles.batchActionsContainer}>
          <Switch
            checked={selectAll}
            onChange={toggleSelectAll}
            label={`Select All (${selectedItems.length} selected)`}
          />
          {selectedItems.length > 0 && (
            <>
              <Button
                variant="primary"
                size="small"
                onClick={batchExportZip}
                icon="📦"
              >
                Export ZIP ({selectedItems.length})
              </Button>
              <Button
                variant="destructive"
                size="small"
                onClick={batchDelete}
                icon="🗑️"
              >
                Delete Selected ({selectedItems.length})
              </Button>
            </>
          )}
        </div>
      )}

      {loading ? (
        <div style={styles.loading}>Loading...</div>
      ) : error ? (
        <div style={styles.error}>{error}</div>
      ) : (
        <div style={styles.content}>
          {activeTab === 'videos' ? (
            <div style={styles.recordingsGrid}>
              {displayedRecordings.length === 0 ? (
                <div style={styles.empty}>
                  <p>📹 No video recordings found.</p>
                  <p style={styles.emptyHint}>
                    Recordings will appear here when motion is detected and recording is enabled.
                  </p>
                </div>
              ) : (
                displayedRecordings.map((recording) => {
                  // API returns recording_id, not id
                  const recordingId = recording.recording_id || recording.id;
                  return (
                  <div key={recordingId} style={styles.recordingCard}>
                    <div style={styles.recordingHeader}>
                      <input
                        type="checkbox"
                        checked={selectedItems.includes(recordingId)}
                        onChange={() => toggleItemSelection(recordingId)}
                        style={styles.cardCheckbox}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                    <div style={styles.recordingThumbnail}>
                      <LazyVideo
                        src={`/api/recordings/${recordingId}/download`}
                        recordingId={recordingId}
                        style={styles.videoPreview}
                      />
                    </div>
                    <div style={styles.recordingInfo}>
                      <h3 style={styles.recordingTitle}>
                        {recording.camera_id}
                      </h3>
                      <p style={styles.recordingMeta}>
                        📅 {formatDate(recording.started_at)}
                      </p>
                      <p style={styles.recordingMeta}>
                        ⏱️ {recording.duration_seconds ? recording.duration_seconds.toFixed(1) : '0.0'}s
                      </p>
                      <p style={styles.recordingMeta}>
                        💾 {recording.file_size_bytes ? formatFileSize(recording.file_size_bytes) : 'N/A'}
                      </p>
                      {recording.faces_detected > 0 && (
                        <p style={styles.recordingMeta}>
                          👤 {recording.faces_detected} face{recording.faces_detected > 1 ? 's' : ''} detected
                        </p>
                      )}
                    </div>
                    <div style={styles.recordingActions}>
                      <a
                        href={`/api/recordings/${recordingId}/download`}
                        download
                        className="btn btn-primary btn-sm"
                      >
                        ⬇️ Download
                      </a>
                      <Button
                        variant="destructive"
                        size="small"
                        onClick={() => deleteRecording(recordingId)}
                        icon="🗑️"
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                  );
                })
              )}
            </div>
          ) : (
            <div style={styles.snapshotsGrid}>
              {displayedSnapshots.length === 0 ? (
                <div style={styles.empty}>
                  <p>📷 No snapshots found.</p>
                  <p style={styles.emptyHint}>
                    Snapshots are captured during motion events and face detection.
                  </p>
                </div>
              ) : (
                displayedSnapshots.map((snapshot) => {
                  const imageUrl = convertPathToUrl(snapshot.snapshot_path);
                  return (
                  <div key={snapshot.id} style={styles.snapshotCard}>
                    <div style={styles.snapshotHeader}>
                      <input
                        type="checkbox"
                        checked={selectedItems.includes(snapshot.id)}
                        onChange={() => toggleItemSelection(snapshot.id)}
                        style={styles.cardCheckbox}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                    <img
                      src={imageUrl}
                      alt={snapshot.camera_id}
                      style={styles.snapshotImage}
                      loading="lazy"
                      onClick={() => setSelectedRecording(snapshot)}
                      onError={(e) => {
                        logger.error('Failed to load snapshot:', snapshot.snapshot_path, '→ Converted to:', imageUrl, '→ Failed URL:', e.target.src);
                        e.target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="100" height="100"%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%23999"%3E❌%3C/text%3E%3C/svg%3E';
                      }}
                    />
                    <div style={styles.snapshotInfo}>
                      <p style={styles.snapshotCamera}>{snapshot.camera_id}</p>
                      <p style={styles.snapshotDate}>{formatDate(snapshot.detected_at)}</p>
                      {snapshot.faces_detected > 0 && (
                        <p style={styles.snapshotSize}>
                          👤 {snapshot.faces_detected} face{snapshot.faces_detected > 1 ? 's' : ''}
                        </p>
                      )}
                    </div>
                    <div style={styles.snapshotActions}>
                      <a
                        href={imageUrl}
                        download
                        className="btn btn-primary btn-sm"
                      >
                        ⬇️
                      </a>
                      <Button
                        variant="destructive"
                        size="small"
                        onClick={() => deleteSnapshot(snapshot.id)}
                        icon="🗑️"
                      />
                    </div>
                  </div>
                  );
                })
              )}
            </div>
          )}
          
          {/* Infinite Scroll Loader */}
          {!loading && hasMore && (
            <div ref={observerTarget} style={styles.infiniteScrollLoader}>
              {loadingMore ? (
                <div style={styles.loadingMore}>
                  <div style={styles.spinner}>⏳</div>
                  <p>Loading more...</p>
                </div>
              ) : (
                <div style={styles.scrollPrompt}>
                  <p>Scroll down to load more</p>
                </div>
              )}
            </div>
          )}
          
          {/* End of results */}
          {!loading && !hasMore && (activeTab === 'videos' ? recordings.length : snapshots.length) > 0 && (
            <div style={styles.endOfResults}>
              <p>📍 You've reached the end ({totalItems} total items)</p>
            </div>
          )}
        </div>
      )}

      {/* Image Modal */}
      {selectedRecording && selectedRecording.snapshot_path && (
        <div style={styles.modal} onClick={() => setSelectedRecording(null)}
        onKeyDown={activateOnKey(() => setSelectedRecording(null))}
        role="button"
        tabIndex={0}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <Button
              variant="tertiary"
              size="small"
              onClick={() => setSelectedRecording(null)}
            >
              ✕
            </Button>
            <img
              src={convertPathToUrl(selectedRecording.snapshot_path)}
              alt={selectedRecording.camera_id}
              style={styles.modalImage}
              onError={(e) => {
                logger.error('Failed to load modal snapshot:', selectedRecording.snapshot_path);
                e.target.alt = '❌ Image failed to load';
              }}
            />
            <div style={styles.modalInfo}>
              <h3>{selectedRecording.camera_id}</h3>
              <p>{formatDate(selectedRecording.detected_at)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const styles = {
  container: {
    minHeight: '100vh',
    backgroundColor: 'var(--background)',
    color: 'var(--text)',
    padding: '1.25rem',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '1.25rem',
    marginBottom: '1.875rem',
  },
  backButton: {
    padding: '0.625rem 1.25rem',
    backgroundColor: 'var(--primary)',
    color: 'var(--text)',
    border: 'none',
    borderRadius: '0.5rem',
    cursor: 'pointer',
    fontSize: '1rem',
  },
  title: {
    margin: 0,
    fontSize: '2rem',
    fontWeight: 'bold',
  },
  tabContainer: {
    display: 'flex',
    gap: '0.625rem',
    marginBottom: '1.25rem',
    borderBottom: '2px solid var(--border)',
  },
  tab: {
    padding: '0.75rem 1.5rem',
    backgroundColor: 'transparent',
    color: 'var(--text)',
    border: 'none',
    borderBottom: '3px solid transparent',
    cursor: 'pointer',
    fontSize: '1rem',
    fontWeight: '500',
    transition: 'all 0.3s ease',
  },
  activeTab: {
    borderBottomColor: 'var(--primary)',
    color: 'var(--primary)',
  },
  filterContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.625rem',
    marginBottom: '1.25rem',
    padding: '0.9375rem',
    backgroundColor: 'var(--card-background)',
    borderRadius: '0.5rem',
  },
  filterLabel: {
    fontSize: '1rem',
    fontWeight: '500',
  },
  filterSelect: {
    padding: '0.5rem 0.75rem',
    backgroundColor: 'var(--input-background)',
    color: 'var(--text)',
    border: '1px solid var(--border)',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
    cursor: 'pointer',
  },
  content: {
    marginTop: '1.25rem',
  },
  loading: {
    textAlign: 'center',
    fontSize: '1.125rem',
    padding: '2.5rem',
  },
  error: {
    textAlign: 'center',
    color: '#ff4444',
    fontSize: '1.125rem',
    padding: '2.5rem',
  },
  empty: {
    textAlign: 'center',
    padding: '3.75rem 1.25rem',
  },
  emptyHint: {
    fontSize: '0.875rem',
    opacity: 0.7,
    marginTop: '0.625rem',
  },
  recordingsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(21.875rem, 1fr))',
    gap: '1.25rem',
  },
  recordingCard: {
    backgroundColor: 'var(--card-background)',
    borderRadius: '0.75rem',
    overflow: 'hidden',
    boxShadow: '0 0.25rem 0.375rem rgba(0,0,0,0.1)',
    position: 'relative', // For absolute positioning of checkbox
  },
  recordingThumbnail: {
    width: '100%',
    aspectRatio: '16/9',
    backgroundColor: '#000',
  },
  videoPreview: {
    width: '100%',
    height: '100%',
    objectFit: 'contain',
  },
  recordingInfo: {
    padding: '0.9375rem',
  },
  recordingTitle: {
    margin: '0 0 0.625rem 0',
    fontSize: '1.125rem',
    fontWeight: 'bold',
  },
  recordingMeta: {
    margin: '0.3125rem 0',
    fontSize: '0.875rem',
    opacity: 0.8,
  },
  recordingActions: {
    display: 'flex',
    gap: '0.625rem',
    padding: '0.9375rem',
    borderTop: '1px solid var(--border)',
  },
  downloadButton: {
    flex: 1,
    padding: '0.625rem',
    backgroundColor: 'var(--success)',
    color: '#fff',
    textDecoration: 'none',
    textAlign: 'center',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
    fontWeight: '500',
  },
  deleteButton: {
    flex: 1,
    padding: '0.625rem',
    backgroundColor: 'var(--danger)',
    color: '#fff',
    border: 'none',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
    fontWeight: '500',
    cursor: 'pointer',
  },
  snapshotsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(15.625rem, 1fr))',
    gap: '0.9375rem',
  },
  snapshotCard: {
    backgroundColor: 'var(--card-background)',
    borderRadius: '0.75rem',
    overflow: 'hidden',
    boxShadow: '0 0.25rem 0.375rem rgba(0,0,0,0.1)',
    cursor: 'pointer',
    transition: 'transform 0.2s ease',
    position: 'relative', // For absolute positioning of checkbox
  },
  snapshotImage: {
    width: '100%',
    aspectRatio: '4/3',
    objectFit: 'cover',
  },
  snapshotInfo: {
    padding: '0.625rem',
  },
  snapshotCamera: {
    margin: '0 0 0.3125rem 0',
    fontSize: '0.875rem',
    fontWeight: 'bold',
  },
  snapshotDate: {
    margin: '0 0 0.3125rem 0',
    fontSize: '0.75rem',
    opacity: 0.8,
  },
  snapshotSize: {
    margin: 0,
    fontSize: '0.75rem',
    opacity: 0.6,
  },
  snapshotActions: {
    display: 'flex',
    gap: '0.3125rem',
    padding: '0.625rem',
    borderTop: '1px solid var(--border)',
  },
  downloadButtonSmall: {
    flex: 1,
    padding: '0.5rem',
    backgroundColor: 'var(--success)',
    color: '#fff',
    textDecoration: 'none',
    textAlign: 'center',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
  },
  deleteButtonSmall: {
    flex: 1,
    padding: '0.5rem',
    backgroundColor: 'var(--danger)',
    color: '#fff',
    border: 'none',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
    cursor: 'pointer',
  },
  modal: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.9)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modalContent: {
    position: 'relative',
    maxWidth: '90vw',
    maxHeight: '90vh',
    backgroundColor: 'var(--card-background)',
    borderRadius: '0.75rem',
    padding: '1.25rem',
  },
  modalClose: {
    position: 'absolute',
    top: '0.625rem',
    right: '0.625rem',
    backgroundColor: 'rgba(0,0,0,0.5)',
    color: '#fff',
    border: 'none',
    borderRadius: '50%',
    width: '2.5rem',
    height: '2.5rem',
    fontSize: '1.5rem',
    cursor: 'pointer',
  },
  modalImage: {
    maxWidth: '100%',
    maxHeight: '70vh',
    objectFit: 'contain',
  },
  modalInfo: {
    marginTop: '0.9375rem',
    textAlign: 'center',
  },
  // Date range filter styles
  dateRangeContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.625rem',
    flex: 1,
  },
  dateInput: {
    padding: '0.5rem 0.75rem',
    backgroundColor: 'var(--input-background)',
    color: 'var(--text)',
    border: '1px solid var(--border)',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
  },
  dateSeparator: {
    fontSize: '0.875rem',
    opacity: 0.7,
  },
  clearButton: {
    padding: '0.5rem 1rem',
    backgroundColor: 'var(--danger)',
    color: '#fff',
    border: 'none',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  // Batch actions styles
  batchActionsContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.9375rem',
    marginBottom: '1.25rem',
    padding: '0.9375rem',
    backgroundColor: 'var(--card-background)',
    borderRadius: '0.5rem',
    border: '2px solid var(--primary)',
  },
  checkboxLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    cursor: 'pointer',
    fontSize: '0.875rem',
    fontWeight: '500',
  },
  checkbox: {
    width: '1.125rem',
    height: '1.125rem',
    cursor: 'pointer',
  },
  checkboxText: {
    userSelect: 'none',
  },
  batchDeleteButton: {
    padding: '0.625rem 1.25rem',
    backgroundColor: 'var(--danger)',
    color: '#fff',
    border: 'none',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'opacity 0.2s',
  },
  batchExportButton: {
    padding: '0.625rem 1.25rem',
    backgroundColor: 'var(--success)',
    color: '#fff',
    border: 'none',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'opacity 0.2s',
  },
  // Person search styles
  searchInput: {
    flex: 1,
    padding: '0.5rem 0.75rem',
    backgroundColor: 'var(--input-background)',
    color: 'var(--text)',
    border: '1px solid var(--border)',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
  },
  clearSearchButton: {
    padding: '0.5rem 0.75rem',
    backgroundColor: 'var(--danger)',
    color: '#fff',
    border: 'none',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
    cursor: 'pointer',
    fontWeight: '600',
  },
  // Card checkboxes
  recordingHeader: {
    position: 'absolute',
    top: '0.625rem',
    left: '0.625rem',
    zIndex: 10,
  },
  snapshotHeader: {
    position: 'absolute',
    top: '0.625rem',
    left: '0.625rem',
    zIndex: 10,
  },
  cardCheckbox: {
    width: '1.25rem',
    height: '1.25rem',
    cursor: 'pointer',
    accentColor: 'var(--primary)',
  },
  // Pagination styles
  paginationContainer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.9375rem',
    marginTop: '1.875rem',
    padding: '1.25rem',
    backgroundColor: 'var(--card-background)',
    borderRadius: '0.5rem',
  },
  paginationButton: {
    padding: '0.625rem 1.25rem',
    backgroundColor: 'var(--primary)',
    color: '#fff',
    border: 'none',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'opacity 0.2s',
  },
  paginationButtonDisabled: {
    backgroundColor: '#666',
    cursor: 'not-allowed',
    opacity: 0.5,
  },
  paginationInfo: {
    fontSize: '0.875rem',
    fontWeight: '500',
  },
  totalItems: {
    fontSize: '0.75rem',
    opacity: 0.7,
    marginLeft: '0.5rem',
  },
  pageNumbers: {
    display: 'flex',
    gap: '0.3125rem',
  },
  pageNumberButton: {
    padding: '0.5rem 0.75rem',
    backgroundColor: 'var(--card-background)',
    color: 'var(--text)',
    border: '1px solid var(--border)',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
    cursor: 'pointer',
    minWidth: '2.5rem',
    transition: 'all 0.2s',
  },
  pageNumberActive: {
    backgroundColor: 'var(--primary)',
    color: '#fff',
    borderColor: 'var(--primary)',
    fontWeight: '600',
  },
  // Infinite scroll styles
  infiniteScrollLoader: {
    padding: '2.5rem 1.25rem',
    textAlign: 'center',
  },
  loadingMore: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '0.625rem',
    color: 'var(--text-secondary)',
  },
  spinner: {
    fontSize: '2rem',
    animation: 'spin 1s linear infinite',
  },
  scrollPrompt: {
    color: 'var(--text-secondary)',
    fontSize: '0.875rem',
    opacity: 0.6,
  },
  endOfResults: {
    padding: '2.5rem 1.25rem',
    textAlign: 'center',
    color: 'var(--text-secondary)',
    fontSize: '0.875rem',
    fontWeight: '500',
    borderTop: '1px solid var(--border)',
    marginTop: '1.25rem',
  },
};

export default RecordingsPage;
