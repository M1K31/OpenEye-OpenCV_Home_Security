/**
 * v3.10.0: Unified Detections Page
 *
 * Displays all detection types in one unified interface:
 * - People (face recognition)
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

    try {
      // Load different data based on active tab
      if (activeTab === 'all' || activeTab === 'people') {
        await loadFaceDetections();
      }

      if (activeTab === 'all' || ['vehicles', 'animals', 'packages'].includes(activeTab)) {
        await loadObjectDetections();
      }

      // Load identified objects
      await loadIdentifiedObjects();

      // Load statistics
      await loadStatistics();

    } catch (err) {
      console.error('Failed to load detections:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadFaceDetections = async () => {
    try {
      const response = await apiClient.get(`/faces/history?page=${page}&page_size=${pageSize}`);
      const data = response.data;

      // Transform to unified format
      const faceDetections = (data.data || []).map(face => ({
        id: `face-${face.id}`,
        type: 'person',
        subtype: 'face',
        name: face.person_name,
        confidence: face.confidence,
        timestamp: face.detected_at,
        camera_id: face.camera_id,
        snapshot_path: face.snapshot_path,
        identified: face.person_name !== 'Unknown'
      }));

      setDetections(prev => [...prev, ...faceDetections]);
      setTotalPages(data.pagination?.total_pages || 1);
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

      setDetections(prev => [...prev, ...objectDetections]);
      setTotalPages(data.pagination?.total_pages || 1);
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

  const loadStatistics = async () => {
    try {
      const response = await apiClient.get('/objects/detections/statistics');
      const data = response.data;
      setStatistics(data);
    } catch (err) {
      console.error('Failed to load statistics:', err);
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setPage(1);
    setDetections([]); // Clear current detections
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

          {!loading && !error && detections.length === 0 && (
            <div style={styles.empty}>
              <span style={styles.emptyIcon}>🔍</span>
              <h3>No detections found</h3>
              <p>No {activeTab === 'all' ? 'detections' : activeTab} have been detected yet.</p>
            </div>
          )}

          {!loading && !error && detections.length > 0 && (
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
      </div>
    </div>
  );
};

// Styles following Apple HIG (8pt grid, 44px touch targets)
const styles = {
  container: {
    display: 'flex',
    minHeight: '100vh',
    backgroundColor: 'var(--theme-background)',
  },
  mainContent: {
    flex: 1,
    padding: '24px',
    marginLeft: '240px',
    color: 'var(--theme-text)',
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
};

export default DetectionsPage;
