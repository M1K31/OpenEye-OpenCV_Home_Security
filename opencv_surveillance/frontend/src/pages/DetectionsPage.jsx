/**
 * v3.11.5: Unified Detections Page
 *
 * Displays all detection types in one unified interface:
 * - People (face recognition) - shows unique people with detection counts
 * - Vehicles (YOLO)
 * - Animals (YOLO)
 * - Packages (YOLO)
 *
 * Follows Apple HIG guidelines with 8pt grid and 44px touch targets
 */

import React, { useState, useEffect } from 'react';
import apiClient from '../api/apiClient';
import { Button } from '../components/universal';

const DetectionsPage = () => {
  // State
  const [activeTab, setActiveTab] = useState('all'); // all, people, vehicles, animals, packages
  const [detections, setDetections] = useState([]);
  const [uniquePeople, setUniquePeople] = useState([]); // Unique people with detection counts
  const [selectedPerson, setSelectedPerson] = useState(null); // For viewing person's detections
  const [personDetections, setPersonDetections] = useState([]); // Detections for selected person
  const [identifiedObjects, setIdentifiedObjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statistics, setStatistics] = useState(null);

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalPages, setTotalPages] = useState(1);

  // Load data on mount and when filters change
  useEffect(() => {
    loadData();
  }, [activeTab, page]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    setDetections([]); // Clear previous detections

    try {
      // Load statistics first
      await loadStatistics();

      // Load different data based on active tab
      if (activeTab === 'people') {
        // For people tab, load unique people with detection counts
        await loadUniquePeople();
      } else if (activeTab === 'all') {
        // For all tab, load both face and object detections in parallel
        // Then combine them to avoid race conditions with state updates
        await loadAllDetections();
      } else {
        // For specific object types
        await loadObjectDetections();
      }

      // Load identified objects
      await loadIdentifiedObjects();

    } catch (err) {
      console.error('Failed to load detections:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Load all detections (faces + objects) for the "All" tab
  const loadAllDetections = async () => {
    try {
      // Load both in parallel
      const [faceResponse, objectResponse] = await Promise.allSettled([
        apiClient.get(`/faces/history?page=${page}&page_size=${pageSize}&hours=168`),
        apiClient.get(`/objects/detections/history?page=${page}&page_size=${pageSize}`)
      ]);

      let allDetections = [];

      // Process face detections
      if (faceResponse.status === 'fulfilled') {
        const faceData = faceResponse.value.data;
        console.log('Face detections loaded (All tab):', faceData.data?.length || 0, 'results');

        const faceDetections = (faceData.data || []).map(face => {
          let snapshotPath = face.snapshot_path || '';
          if (snapshotPath.startsWith('data/snapshots/')) {
            snapshotPath = snapshotPath.replace('data/snapshots/', '');
          }
          return {
            id: `face-${face.id}`,
            type: 'person',
            subtype: 'face',
            name: face.person_name,
            confidence: face.confidence,
            timestamp: face.detected_at,
            camera_id: face.camera_id,
            snapshot_path: snapshotPath,
            identified: face.person_name !== 'Unknown'
          };
        });
        allDetections = [...allDetections, ...faceDetections];
      } else {
        console.error('Failed to load face detections:', faceResponse.reason);
      }

      // Process object detections
      if (objectResponse.status === 'fulfilled') {
        const objectData = objectResponse.value.data;
        console.log('Object detections loaded (All tab):', objectData.data?.length || 0, 'results');

        const objectDetections = (objectData.data || []).map(obj => ({
          id: `object-${obj.id}`,
          type: obj.object_class,
          subtype: obj.object_subclass,
          name: obj.identified_object_name || `Unknown ${obj.object_subclass}`,
          confidence: obj.confidence,
          timestamp: obj.detected_at,
          camera_id: obj.camera_id,
          snapshot_path: obj.snapshot_path,
          identified: !!obj.identified_object_id
        }));
        allDetections = [...allDetections, ...objectDetections];
      } else {
        console.error('Failed to load object detections:', objectResponse.reason);
      }

      // Sort all detections by timestamp (most recent first)
      allDetections.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

      console.log('Total combined detections (All tab):', allDetections.length);
      setDetections(allDetections);

    } catch (err) {
      console.error('Failed to load all detections:', err);
    }
  };

  const loadUniquePeople = async () => {
    try {
      // Load all face detections to aggregate by person
      // Use a larger time window and aggregate on the client side
      const response = await apiClient.get('/faces/history?page=1&page_size=1000&hours=168');
      const data = response.data;

      // Aggregate by person name
      const peopleMap = new Map();

      (data.data || []).forEach(face => {
        const personName = face.person_name;
        if (!peopleMap.has(personName)) {
          peopleMap.set(personName, {
            name: personName,
            detectionCount: 0,
            lastSeen: face.detected_at,
            lastCamera: face.camera_id,
            lastSnapshot: face.snapshot_path,
            confidence: face.confidence,
            isKnown: personName !== 'Unknown'
          });
        }

        const person = peopleMap.get(personName);
        person.detectionCount++;

        // Update if this is more recent
        if (new Date(face.detected_at) > new Date(person.lastSeen)) {
          person.lastSeen = face.detected_at;
          person.lastCamera = face.camera_id;
          person.lastSnapshot = face.snapshot_path;
          person.confidence = face.confidence;
        }
      });

      // Convert to array and sort by detection count
      const peopleArray = Array.from(peopleMap.values())
        .sort((a, b) => b.detectionCount - a.detectionCount);

      setUniquePeople(peopleArray);
      setTotalPages(1); // All loaded in one page for unique people view
    } catch (err) {
      console.error('Failed to load unique people:', err);
    }
  };

  const loadPersonDetections = async (personName) => {
    try {
      setSelectedPerson(personName);
      const response = await apiClient.get(`/faces/history/person/${encodeURIComponent(personName)}?limit=100`);
      setPersonDetections(response.data || []);
    } catch (err) {
      console.error('Failed to load person detections:', err);
      setPersonDetections([]);
    }
  };

  const loadFaceDetections = async () => {
    try {
      // Use 168 hours (1 week) to match the statistics time window
      const response = await apiClient.get(`/faces/history?page=${page}&page_size=${pageSize}&hours=168`);
      const data = response.data;

      console.log('Face detections loaded:', data.data?.length || 0, 'results');

      // Transform to unified format
      const faceDetections = (data.data || []).map(face => {
        // Normalize snapshot path - remove leading data/snapshots if present
        let snapshotPath = face.snapshot_path || '';
        if (snapshotPath.startsWith('data/snapshots/')) {
          snapshotPath = snapshotPath.replace('data/snapshots/', '');
        }

        return {
          id: `face-${face.id}`,
          type: 'person',
          subtype: 'face',
          name: face.person_name,
          confidence: face.confidence,
          timestamp: face.detected_at,
          camera_id: face.camera_id,
          snapshot_path: snapshotPath,
          identified: face.person_name !== 'Unknown'
        };
      });

      setDetections(prev => {
        const updated = [...prev, ...faceDetections];
        console.log('Total detections after adding faces:', updated.length);
        return updated;
      });
      setTotalPages(Math.max(data.pagination?.total_pages || 1, totalPages));
    } catch (err) {
      console.error('Failed to load face detections:', err);
    }
  };

  const loadObjectDetections = async () => {
    try {
      // Filter by object class if specific tab selected
      const classFilter = activeTab !== 'all' ? `&object_class=${activeTab.slice(0, -1)}` : '';
      const response = await apiClient.get(
        `/objects/detections/history?page=${page}&page_size=${pageSize}${classFilter}`
      );
      const data = response.data;

      console.log('Object detections loaded:', data.data?.length || 0, 'results');

      // Transform to unified format
      const objectDetections = (data.data || []).map(obj => ({
        id: `object-${obj.id}`,
        type: obj.object_class,
        subtype: obj.object_subclass,
        name: obj.identified_object_name || `Unknown ${obj.object_subclass}`,
        confidence: obj.confidence,
        timestamp: obj.detected_at,
        camera_id: obj.camera_id,
        snapshot_path: obj.snapshot_path,
        identified: !!obj.identified_object_id
      }));

      setDetections(prev => {
        const updated = [...prev, ...objectDetections];
        console.log('Total detections after adding objects:', updated.length);
        return updated;
      });
      setTotalPages(Math.max(data.pagination?.total_pages || 1, totalPages));
    } catch (err) {
      console.error('Failed to load object detections:', err);
    }
  };

  const loadIdentifiedObjects = async () => {
    try {
      const response = await apiClient.get('/objects/identified');
      const data = response.data;
      setIdentifiedObjects(data || []);
    } catch (err) {
      console.error('Failed to load identified objects:', err);
    }
  };

  const handleAddToKnownPerson = async (detection) => {
    const personName = window.prompt('Enter a name for this person:');
    if (!personName || !personName.trim()) {
      return;
    }

    try {
      // Create person if doesn't exist
      await apiClient.post('/faces/people', { name: personName.trim() });
      
      // Download snapshot and upload as photo
      if (detection.snapshot_path) {
        const snapshotUrl = `/data/snapshots/${detection.snapshot_path}`;
        const response = await fetch(snapshotUrl);
        const blob = await response.blob();
        const file = new File([blob], detection.snapshot_path, { type: 'image/jpeg' });
        
        const formData = new FormData();
        formData.append('files', file);
        
        await apiClient.post(`/faces/people/${personName.trim()}/photos`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        
        alert(`Added ${personName} with photo. Please train the model to enable recognition.`);
        window.location.href = '/ai-faces';
      }
    } catch (error) {
      console.error('Error adding to known person:', error);
      alert('Error adding person: ' + (error.response?.data?.detail || error.message));
    }
  };

  const loadStatistics = async () => {
    try {
      // Load both face and object detection statistics
      const [faceStatsResponse, objectStatsResponse] = await Promise.allSettled([
        apiClient.get('/faces/history/statistics?days=7'),
        apiClient.get('/objects/detections/statistics')
      ]);

      let combinedStats = {
        total: 0,
        by_class: {},
        face_stats: null // Store full face stats for detailed display
      };

      // Add face detection stats - use unique_people count, not total_detections
      if (faceStatsResponse.status === 'fulfilled') {
        const faceStats = faceStatsResponse.value.data;
        combinedStats.face_stats = faceStats;
        // Show unique people count (excluding "Unknown")
        combinedStats.by_class.person = faceStats.unique_people || 0;
        combinedStats.total += combinedStats.by_class.person;
        // Also store total detections for reference
        combinedStats.total_face_detections = faceStats.total_detections || 0;
      }

      // Add object detection stats
      if (objectStatsResponse.status === 'fulfilled') {
        const objectStats = objectStatsResponse.value.data;
        if (objectStats.by_class) {
          // Add vehicle, animal, package counts from YOLO
          ['vehicle', 'animal', 'package'].forEach(cls => {
            if (objectStats.by_class[cls]) {
              combinedStats.by_class[cls] = objectStats.by_class[cls];
              combinedStats.total += objectStats.by_class[cls];
            }
          });
        }
      }

      setStatistics(combinedStats);
    } catch (err) {
      console.error('Failed to load statistics:', err);
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setPage(1);
    setDetections([]); // Clear current detections
    setSelectedPerson(null); // Clear selected person
    setPersonDetections([]); // Clear person detections
  };

  const handlePageChange = (newPage) => {
    setPage(newPage);
    setDetections([]); // Clear current detections
  };

  // Group detections by type
  const groupedDetections = detections.reduce((acc, detection) => {
    const key = detection.type;
    if (!acc[key]) acc[key] = [];
    acc[key].push(detection);
    return acc;
  }, {});

  return (
    <div style={styles.container}>
      <div style={styles.mainContent}>
        <div style={styles.header}>
          <h1 style={styles.title}>🔍 Detections</h1>
          <p style={styles.subtitle}>
            Track people, vehicles, animals, and packages across all cameras
          </p>
        </div>

        {/* Statistics Cards */}
        {statistics && (
          <div style={styles.statsGrid}>
            <StatCard
              icon="👤"
              label="People"
              count={statistics.by_class?.person || 0}
              active={activeTab === 'people'}
              onClick={() => handleTabChange('people')}
            />
            <StatCard
              icon="🚗"
              label="Vehicles"
              count={statistics.by_class?.vehicle || 0}
              active={activeTab === 'vehicles'}
              onClick={() => handleTabChange('vehicles')}
            />
            <StatCard
              icon="🐾"
              label="Animals"
              count={statistics.by_class?.animal || 0}
              active={activeTab === 'animals'}
              onClick={() => handleTabChange('animals')}
            />
            <StatCard
              icon="📦"
              label="Packages"
              count={statistics.by_class?.package || 0}
              active={activeTab === 'packages'}
              onClick={() => handleTabChange('packages')}
            />
          </div>
        )}

        {/* Tab Navigation */}
        <div style={styles.tabBar}>
          <Button
            variant={activeTab === 'all' ? 'primary' : 'secondary'}
            size="medium"
            onClick={() => handleTabChange('all')}
          >
            All
          </Button>
          <Button
            variant={activeTab === 'people' ? 'primary' : 'secondary'}
            size="medium"
            onClick={() => handleTabChange('people')}
          >
            People
          </Button>
          <Button
            variant={activeTab === 'vehicles' ? 'primary' : 'secondary'}
            size="medium"
            onClick={() => handleTabChange('vehicles')}
          >
            Vehicles
          </Button>
          <Button
            variant={activeTab === 'animals' ? 'primary' : 'secondary'}
            size="medium"
            onClick={() => handleTabChange('animals')}
          >
            Animals
          </Button>
          <Button
            variant={activeTab === 'packages' ? 'primary' : 'secondary'}
            size="medium"
            onClick={() => handleTabChange('packages')}
          >
            Packages
          </Button>
        </div>

        {/* Content Area */}
        <div style={styles.contentArea}>
          {loading && <div style={styles.loading}>Loading detections...</div>}

          {error && (
            <div style={styles.error}>
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* People Tab - Show unique people view */}
          {!loading && !error && activeTab === 'people' && (
            <>
              {selectedPerson ? (
                // Show selected person's detections
                <div>
                  <div style={styles.personHeader}>
                    <Button
                      variant="secondary"
                      size="medium"
                      onClick={() => {
                        setSelectedPerson(null);
                        setPersonDetections([]);
                      }}
                    >
                      ← Back to People
                    </Button>
                    <h2 style={styles.personTitle}>
                      {selectedPerson === 'Unknown' ? '❓' : '👤'} {selectedPerson}
                    </h2>
                    <span style={styles.detectionCount}>
                      {personDetections.length} detection{personDetections.length !== 1 ? 's' : ''}
                    </span>
                  </div>

                  {personDetections.length === 0 ? (
                    <div style={styles.empty}>
                      <span style={styles.emptyIcon}>🔍</span>
                      <h3>No detections found</h3>
                      <p>No detection history available for {selectedPerson}.</p>
                    </div>
                  ) : (
                    <div style={styles.detectionGrid}>
                      {personDetections.map((detection, index) => {
                        let snapshotPath = detection.snapshot_path || '';
                        if (snapshotPath.startsWith('data/snapshots/')) {
                          snapshotPath = snapshotPath.replace('data/snapshots/', '');
                        }
                        return (
                          <div key={detection.id || index} style={styles.detectionCard}>
                            {snapshotPath && (
                              <div style={styles.detectionImage}>
                                <img
                                  src={`/data/snapshots/${snapshotPath}`}
                                  alt={detection.person_name}
                                  style={styles.detectionImg}
                                  onError={(e) => { e.target.style.display = 'none'; }}
                                />
                              </div>
                            )}
                            <div style={styles.detectionContent}>
                              <div style={styles.detectionMeta}>
                                <div style={styles.detectionMetaItem}>
                                  <span style={styles.metaLabel}>Confidence:</span>
                                  <span style={styles.metaValue}>{(detection.confidence * 100).toFixed(1)}%</span>
                                </div>
                                <div style={styles.detectionMetaItem}>
                                  <span style={styles.metaLabel}>Camera:</span>
                                  <span style={styles.metaValue}>{detection.camera_id}</span>
                                </div>
                                <div style={styles.detectionMetaItem}>
                                  <span style={styles.metaLabel}>Time:</span>
                                  <span style={styles.metaValue}>
                                    {new Date(detection.detected_at).toLocaleString()}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : (
                // Show unique people grid
                <>
                  {uniquePeople.length === 0 ? (
                    <div style={styles.empty}>
                      <span style={styles.emptyIcon}>👤</span>
                      <h3>No people detected</h3>
                      <p>No people have been detected in the last 7 days.</p>
                    </div>
                  ) : (
                    <>
                      <div style={styles.peopleInfo}>
                        <p style={styles.infoText}>
                          Showing {uniquePeople.length} unique {uniquePeople.length === 1 ? 'person' : 'people'} detected in the last 7 days.
                          {statistics?.total_face_detections && (
                            <span style={styles.totalDetections}>
                              ({statistics.total_face_detections.toLocaleString()} total detections)
                            </span>
                          )}
                        </p>
                      </div>
                      <div style={styles.detectionGrid}>
                        {uniquePeople.map((person, index) => (
                          <PersonCard
                            key={person.name || index}
                            person={person}
                            onClick={() => loadPersonDetections(person.name)}
                          />
                        ))}
                      </div>
                    </>
                  )}
                </>
              )}
            </>
          )}

          {/* Other tabs - show regular detections */}
          {!loading && !error && activeTab !== 'people' && detections.length === 0 && (
            <div style={styles.empty}>
              <span style={styles.emptyIcon}>🔍</span>
              <h3>No detections found</h3>
              <p>No {activeTab === 'all' ? 'detections' : activeTab} have been detected yet.</p>
            </div>
          )}

          {!loading && !error && activeTab !== 'people' && detections.length > 0 && (
            <>
              <div style={styles.detectionGrid}>
                {detections.map(detection => (
                  <DetectionCard
                    key={detection.id}
                    detection={detection}
                  />
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div style={styles.pagination}>
                  <Button
                    variant="secondary"
                    size="medium"
                    onClick={() => handlePageChange(page - 1)}
                    disabled={page === 1}
                  >
                    ← Previous
                  </Button>
                  <span style={styles.pageInfo}>
                    Page {page} of {totalPages}
                  </span>
                  <Button
                    variant="secondary"
                    size="medium"
                    onClick={() => handlePageChange(page + 1)}
                    disabled={page === totalPages}
                  >
                    Next →
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// Stat Card Component
const StatCard = ({ icon, label, count, active, onClick }) => (
  <button
    onClick={onClick}
    style={{
      ...styles.statCard,
      ...(active ? styles.statCardActive : {})
    }}
  >
    <div style={styles.statIcon}>{icon}</div>
    <div style={styles.statLabel}>{label}</div>
    <div style={styles.statCount}>{count.toLocaleString()}</div>
  </button>
);

// Detection Card Component
const DetectionCard = ({ detection }) => {
  const getTypeColor = (type) => {
    switch (type) {
      case 'person': return '#007AFF'; // Blue
      case 'vehicle': return '#FFCC00'; // Yellow
      case 'animal': return '#FF3B30'; // Red
      case 'package': return '#34C759'; // Green
      default: return '#8E8E93'; // Gray
    }
  };

  const getTypeIcon = (type) => {
    switch (type) {
      case 'person': return '👤';
      case 'vehicle': return '🚗';
      case 'animal': return '🐾';
      case 'package': return '📦';
      default: return '🔍';
    }
  };

  return (
    <div style={styles.detectionCard}>
      {detection.snapshot_path && (
        <div style={styles.detectionImage}>
          <img
            src={`/data/snapshots/${detection.snapshot_path}`}
            alt={detection.name}
            style={styles.detectionImg}
          />
        </div>
      )}

      <div style={styles.detectionContent}>
        <div style={styles.detectionHeader}>
          <span style={styles.detectionIcon}>{getTypeIcon(detection.type)}</span>
          <span
            style={{
              ...styles.detectionBadge,
              backgroundColor: getTypeColor(detection.type)
            }}
          >
            {detection.type}
          </span>
          {detection.identified && (
            <span style={styles.identifiedBadge}>✓ Identified</span>
          )}
        </div>

        <h3 style={styles.detectionName}>{detection.name}</h3>

        <div style={styles.detectionMeta}>
          <div style={styles.detectionMetaItem}>
            <span style={styles.metaLabel}>Subtype:</span>
            <span style={styles.metaValue}>{detection.subtype}</span>
          </div>
          <div style={styles.detectionMetaItem}>
            <span style={styles.metaLabel}>Confidence:</span>
            <span style={styles.metaValue}>{(detection.confidence * 100).toFixed(1)}%</span>
          </div>
          <div style={styles.detectionMetaItem}>
            <span style={styles.metaLabel}>Camera:</span>
            <span style={styles.metaValue}>{detection.camera_id}</span>
          </div>
          <div style={styles.detectionMetaItem}>
            <span style={styles.metaLabel}>Time:</span>
            <span style={styles.metaValue}>
              {new Date(detection.timestamp).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Management Actions for Unknown Faces */}
        {detection.type === 'person' && !detection.identified && (
          <div style={styles.detectionActions}>
            <Button
              variant="primary"
              size="small"
              onClick={() => handleAddToKnownPerson(detection)}
              style={{ marginRight: '8px' }}
            >
              Add to Known Person
            </Button>
            <Button
              variant="secondary"
              size="small"
              onClick={() => window.location.href = '/face-clustering'}
            >
              View Clusters
            </Button>
          </div>
        )}

        {/* Management Actions for Known Faces */}
        {detection.type === 'person' && detection.identified && (
          <div style={styles.detectionActions}>
            <Button
              variant="secondary"
              size="small"
              onClick={() => window.location.href = `/ai-faces?person=${encodeURIComponent(detection.name)}`}
            >
              Manage Person
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

// Person Card Component - shows unique person with detection count
const PersonCard = ({ person, onClick }) => {
  // Normalize snapshot path
  let snapshotPath = person.lastSnapshot || '';
  if (snapshotPath.startsWith('data/snapshots/')) {
    snapshotPath = snapshotPath.replace('data/snapshots/', '');
  }

  return (
    <button
      onClick={onClick}
      style={styles.personCard}
    >
      {snapshotPath && (
        <div style={styles.detectionImage}>
          <img
            src={`/data/snapshots/${snapshotPath}`}
            alt={person.name}
            style={styles.detectionImg}
            onError={(e) => { e.target.style.display = 'none'; }}
          />
        </div>
      )}

      <div style={styles.personCardContent}>
        <div style={styles.personCardHeader}>
          <span style={styles.personIcon}>
            {person.isKnown ? '👤' : '❓'}
          </span>
          {person.isKnown && (
            <span style={styles.identifiedBadge}>✓ Known</span>
          )}
        </div>

        <h3 style={styles.personCardName}>{person.name}</h3>

        <div style={styles.personCardStats}>
          <div style={styles.personCardStat}>
            <span style={styles.statNumber}>{person.detectionCount}</span>
            <span style={styles.statText}>
              detection{person.detectionCount !== 1 ? 's' : ''}
            </span>
          </div>
        </div>

        <div style={styles.personCardMeta}>
          <div style={styles.detectionMetaItem}>
            <span style={styles.metaLabel}>Last seen:</span>
            <span style={styles.metaValue}>
              {new Date(person.lastSeen).toLocaleString()}
            </span>
          </div>
          <div style={styles.detectionMetaItem}>
            <span style={styles.metaLabel}>Camera:</span>
            <span style={styles.metaValue}>{person.lastCamera}</span>
          </div>
        </div>

        <div style={styles.viewDetailsHint}>
          Click to view all detections →
        </div>
      </div>
    </button>
  );
};

// Styles following Apple HIG (8pt grid, 44px touch targets)
const styles = {
  container: {
    display: 'flex',
    minHeight: '400px',
    backgroundColor: 'var(--bg-main, var(--theme-background))',
  },
  mainContent: {
    flex: 1,
    padding: '0',
    color: 'var(--text-primary, var(--theme-text))',
  },
  header: {
    marginBottom: '24px',
  },
  title: {
    fontSize: '32px',
    fontWeight: '700',
    margin: '0 0 8px 0',
    color: 'var(--theme-text)',
  },
  subtitle: {
    fontSize: '16px',
    color: 'var(--theme-text-secondary)',
    margin: 0,
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '16px',
    marginBottom: '24px',
  },
  statCard: {
    background: 'var(--theme-card-background)',
    border: '2px solid var(--theme-border)',
    borderRadius: '12px',
    padding: '16px',
    textAlign: 'center',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    minHeight: '120px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
  },
  statCardActive: {
    borderColor: 'var(--theme-primary)',
    backgroundColor: 'var(--theme-primary-light)',
    transform: 'scale(1.02)',
  },
  statIcon: {
    fontSize: '32px',
    marginBottom: '8px',
  },
  statLabel: {
    fontSize: '14px',
    color: 'var(--theme-text-secondary)',
    marginBottom: '4px',
  },
  statCount: {
    fontSize: '24px',
    fontWeight: '700',
    color: 'var(--theme-text)',
  },
  tabBar: {
    display: 'flex',
    gap: '8px',
    marginBottom: '24px',
    borderBottom: '1px solid var(--theme-border)',
    paddingBottom: '8px',
  },
  contentArea: {
    minHeight: '400px',
  },
  loading: {
    textAlign: 'center',
    padding: '48px',
    fontSize: '18px',
    color: 'var(--theme-text-secondary)',
  },
  error: {
    backgroundColor: '#ff3b301a',
    border: '1px solid #ff3b30',
    borderRadius: '8px',
    padding: '16px',
    display: 'flex',
    gap: '12px',
    alignItems: 'center',
    color: '#ff3b30',
  },
  empty: {
    textAlign: 'center',
    padding: '64px 24px',
    color: 'var(--theme-text-secondary)',
  },
  emptyIcon: {
    fontSize: '64px',
    display: 'block',
    marginBottom: '16px',
    opacity: 0.5,
  },
  detectionGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
    gap: '16px',
    marginBottom: '24px',
  },
  detectionCard: {
    background: 'var(--theme-card-background)',
    border: '1px solid var(--theme-border)',
    borderRadius: '12px',
    overflow: 'hidden',
    transition: 'all 0.2s ease',
  },
  detectionImage: {
    width: '100%',
    height: '200px',
    overflow: 'hidden',
    backgroundColor: '#000',
  },
  detectionImg: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },
  detectionContent: {
    padding: '16px',
  },
  detectionHeader: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
    marginBottom: '12px',
  },
  detectionIcon: {
    fontSize: '20px',
  },
  detectionBadge: {
    padding: '4px 12px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: '600',
    color: '#fff',
    textTransform: 'capitalize',
  },
  identifiedBadge: {
    padding: '4px 12px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: '600',
    backgroundColor: '#34C759',
    color: '#fff',
    marginLeft: 'auto',
  },
  detectionName: {
    fontSize: '18px',
    fontWeight: '600',
    margin: '0 0 12px 0',
    color: 'var(--theme-text)',
  },
  detectionMeta: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  detectionActions: {
    display: 'flex',
    gap: '8px',
    marginTop: '16px',
    paddingTop: '16px',
    borderTop: '1px solid rgba(255, 255, 255, 0.1)',
  },
  detectionMetaItem: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '14px',
  },
  metaLabel: {
    color: 'var(--theme-text-secondary)',
    fontWeight: '500',
  },
  metaValue: {
    color: 'var(--theme-text)',
    fontWeight: '400',
  },
  pagination: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    gap: '16px',
    marginTop: '32px',
  },
  pageInfo: {
    fontSize: '16px',
    color: 'var(--theme-text-secondary)',
  },
  // Person Card styles
  personCard: {
    background: 'var(--theme-card-background)',
    border: '1px solid var(--theme-border)',
    borderRadius: '12px',
    overflow: 'hidden',
    transition: 'all 0.2s ease',
    cursor: 'pointer',
    width: '100%',
    textAlign: 'left',
    padding: 0,
  },
  personCardContent: {
    padding: '16px',
  },
  personCardHeader: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
    marginBottom: '8px',
  },
  personIcon: {
    fontSize: '24px',
  },
  personCardName: {
    fontSize: '20px',
    fontWeight: '600',
    margin: '0 0 12px 0',
    color: 'var(--theme-text)',
  },
  personCardStats: {
    display: 'flex',
    gap: '16px',
    marginBottom: '12px',
  },
  personCardStat: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '4px',
  },
  statNumber: {
    fontSize: '28px',
    fontWeight: '700',
    color: 'var(--theme-primary)',
  },
  statText: {
    fontSize: '14px',
    color: 'var(--theme-text-secondary)',
  },
  personCardMeta: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    marginBottom: '12px',
  },
  viewDetailsHint: {
    fontSize: '14px',
    color: 'var(--theme-primary)',
    fontWeight: '500',
    paddingTop: '12px',
    borderTop: '1px solid var(--theme-border)',
  },
  // Person header styles (when viewing person's detections)
  personHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    marginBottom: '24px',
    flexWrap: 'wrap',
  },
  personTitle: {
    fontSize: '24px',
    fontWeight: '600',
    margin: 0,
    color: 'var(--theme-text)',
  },
  detectionCount: {
    fontSize: '16px',
    color: 'var(--theme-text-secondary)',
    marginLeft: 'auto',
  },
  // People info section
  peopleInfo: {
    marginBottom: '16px',
  },
  infoText: {
    fontSize: '14px',
    color: 'var(--theme-text-secondary)',
    margin: 0,
  },
  totalDetections: {
    marginLeft: '8px',
    opacity: 0.7,
  },
};

export default DetectionsPage;
