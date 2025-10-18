// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import clusteringService from '../services/clusteringService';
import ClusterCard from '../components/ClusterCard';
import ClusterDetailModal from '../components/ClusterDetailModal';
import AssignNameModal from '../components/AssignNameModal';
import MergeClustersModal from '../components/MergeClustersModal';
import './FaceClusteringPage.css';

/**
 * Face Clustering Page
 * AI-powered face grouping interface for managing unknown faces
 */
const FaceClusteringPage = () => {
  // State management
  const [clusters, setClusters] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [clustering, setClustering] = useState(false);
  const [error, setError] = useState(null);
  const [selectedClusters, setSelectedClusters] = useState([]);
  
  // Modal states
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [assignNameModalOpen, setAssignNameModalOpen] = useState(false);
  const [mergeModalOpen, setMergeModalOpen] = useState(false);
  const [selectedClusterId, setSelectedClusterId] = useState(null);
  
  // Pagination
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const ITEMS_PER_PAGE = 20;
  
  // Clustering parameters
  const [clusteringParams, setClusteringParams] = useState({
    eps: 0.5,
    min_samples: 2,
    recalculate: false,
  });

  // Load clusters and statistics
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [clustersData, statsData] = await Promise.all([
        clusteringService.getClusters(0, ITEMS_PER_PAGE),
        clusteringService.getStatistics(),
      ]);
      
      setClusters(clustersData.clusters || []);
      setStatistics(statsData);
      setHasMore((clustersData.clusters?.length || 0) >= ITEMS_PER_PAGE);
      setPage(0);
    } catch (err) {
      console.error('Error loading data:', err);
      setError('Failed to load clusters. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Load more clusters (infinite scroll)
  const loadMore = async () => {
    if (!hasMore || loading) return;
    
    try {
      setLoading(true);
      const skip = (page + 1) * ITEMS_PER_PAGE;
      const data = await clusteringService.getClusters(skip, ITEMS_PER_PAGE);
      
      setClusters(prev => [...prev, ...(data.clusters || [])]);
      setHasMore((data.clusters?.length || 0) >= ITEMS_PER_PAGE);
      setPage(prev => prev + 1);
    } catch (err) {
      console.error('Error loading more clusters:', err);
    } finally {
      setLoading(false);
    }
  };

  // Trigger clustering algorithm
  const handleCluster = async () => {
    try {
      setClustering(true);
      setError(null);
      
      const result = await clusteringService.clusterFaces(clusteringParams);
      
      // Show success message
      const message = result.clusters_created > 0
        ? `✅ Created ${result.clusters_created} clusters from ${result.faces_clustered} faces`
        : `ℹ️ No new clusters created. ${result.total_unknown_faces} unknown faces found.`;
      
      alert(message);
      
      // Reload data
      await loadData();
    } catch (err) {
      console.error('Error clustering faces:', err);
      setError('Failed to cluster faces. Please try again.');
    } finally {
      setClustering(false);
    }
  };

  // Handle cluster selection for merging
  const toggleClusterSelection = (clusterId) => {
    setSelectedClusters(prev => {
      if (prev.includes(clusterId)) {
        return prev.filter(id => id !== clusterId);
      } else {
        return [...prev, clusterId];
      }
    });
  };

  // Open cluster detail modal
  const handleViewCluster = (clusterId) => {
    setSelectedClusterId(clusterId);
    setDetailModalOpen(true);
  };

  // Open assign name modal
  const handleAssignName = (clusterId) => {
    setSelectedClusterId(clusterId);
    setAssignNameModalOpen(true);
  };

  // Handle name assignment success
  const handleNameAssigned = async () => {
    setAssignNameModalOpen(false);
    await loadData();
  };

  // Open merge modal
  const handleMerge = () => {
    if (selectedClusters.length < 2) {
      alert('Please select at least 2 clusters to merge');
      return;
    }
    setMergeModalOpen(true);
  };

  // Handle merge success
  const handleMergeSuccess = async () => {
    setMergeModalOpen(false);
    setSelectedClusters([]);
    await loadData();
  };

  // Handle cluster deletion
  const handleDelete = async (clusterId) => {
    if (!confirm('Are you sure you want to delete this cluster? Faces will be reset to "Unknown".')) {
      return;
    }
    
    try {
      await clusteringService.deleteCluster(clusterId, true);
      await loadData();
    } catch (err) {
      console.error('Error deleting cluster:', err);
      alert('Failed to delete cluster. Please try again.');
    }
  };

  return (
    <div className="face-clustering-page">
      {/* Header */}
      <div className="page-header">
        <div className="header-content">
          <h1>Face Clustering</h1>
          <p>AI-powered grouping of unknown faces</p>
        </div>
        
        <div className="header-actions">
          <button
            className="btn btn-primary"
            onClick={handleCluster}
            disabled={clustering || loading}
          >
            {clustering ? '🔄 Clustering...' : '🤖 Run Clustering'}
          </button>
          
          {selectedClusters.length > 0 && (
            <button
              className="btn btn-secondary"
              onClick={handleMerge}
              disabled={selectedClusters.length < 2}
            >
              🔗 Merge Selected ({selectedClusters.length})
            </button>
          )}
          
          <button
            className="btn btn-outline"
            onClick={loadData}
            disabled={loading}
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Statistics Dashboard */}
      {statistics && (
        <div className="statistics-dashboard">
          <div className="stat-card">
            <div className="stat-value">{statistics.total_clusters}</div>
            <div className="stat-label">Total Clusters</div>
          </div>
          
          <div className="stat-card">
            <div className="stat-value">{statistics.identified_clusters}</div>
            <div className="stat-label">Identified</div>
          </div>
          
          <div className="stat-card">
            <div className="stat-value">{statistics.unidentified_clusters}</div>
            <div className="stat-label">Unidentified</div>
          </div>
          
          <div className="stat-card">
            <div className="stat-value">{statistics.clustered_faces}</div>
            <div className="stat-label">Clustered Faces</div>
          </div>
          
          <div className="stat-card">
            <div className="stat-value">{statistics.clustering_rate.toFixed(1)}%</div>
            <div className="stat-label">Clustering Rate</div>
          </div>
        </div>
      )}

      {/* Clustering Parameters */}
      <div className="clustering-params">
        <h3>Clustering Parameters</h3>
        <div className="params-grid">
          <div className="param-input">
            <label htmlFor="eps">
              Distance Threshold (eps)
              <span className="tooltip" title="Lower = stricter clustering (0.4-0.6 range)">ⓘ</span>
            </label>
            <input
              type="number"
              id="eps"
              min="0.3"
              max="0.8"
              step="0.05"
              value={clusteringParams.eps}
              onChange={(e) => setClusteringParams(prev => ({
                ...prev,
                eps: parseFloat(e.target.value)
              }))}
            />
          </div>
          
          <div className="param-input">
            <label htmlFor="min_samples">
              Min Faces per Cluster
              <span className="tooltip" title="Minimum faces needed to form a cluster">ⓘ</span>
            </label>
            <input
              type="number"
              id="min_samples"
              min="2"
              max="10"
              step="1"
              value={clusteringParams.min_samples}
              onChange={(e) => setClusteringParams(prev => ({
                ...prev,
                min_samples: parseInt(e.target.value)
              }))}
            />
          </div>
          
          <div className="param-input">
            <label htmlFor="recalculate">
              <input
                type="checkbox"
                id="recalculate"
                checked={clusteringParams.recalculate}
                onChange={(e) => setClusteringParams(prev => ({
                  ...prev,
                  recalculate: e.target.checked
                }))}
              />
              Recalculate existing clusters
            </label>
          </div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="error-message">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Clusters Grid */}
      {loading && clusters.length === 0 ? (
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading clusters...</p>
        </div>
      ) : clusters.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📦</div>
          <h3>No Clusters Yet</h3>
          <p>Click "Run Clustering" to group similar unknown faces</p>
          {statistics && statistics.total_unknown_faces > 0 && (
            <p className="hint">
              Found {statistics.total_unknown_faces} unknown faces ready for clustering
            </p>
          )}
        </div>
      ) : (
        <>
          <div className="clusters-grid">
            {clusters.map(cluster => (
              <ClusterCard
                key={cluster.id}
                cluster={cluster}
                selected={selectedClusters.includes(cluster.id)}
                onSelect={toggleClusterSelection}
                onView={handleViewCluster}
                onAssignName={handleAssignName}
                onDelete={handleDelete}
              />
            ))}
          </div>
          
          {hasMore && (
            <div className="load-more">
              <button
                className="btn btn-outline"
                onClick={loadMore}
                disabled={loading}
              >
                {loading ? 'Loading...' : 'Load More Clusters'}
              </button>
            </div>
          )}
        </>
      )}

      {/* Modals */}
      {detailModalOpen && (
        <ClusterDetailModal
          clusterId={selectedClusterId}
          onClose={() => setDetailModalOpen(false)}
          onAssignName={() => {
            setDetailModalOpen(false);
            handleAssignName(selectedClusterId);
          }}
        />
      )}
      
      {assignNameModalOpen && (
        <AssignNameModal
          clusterId={selectedClusterId}
          onClose={() => setAssignNameModalOpen(false)}
          onSuccess={handleNameAssigned}
        />
      )}
      
      {mergeModalOpen && (
        <MergeClustersModal
          clusterIds={selectedClusters}
          onClose={() => setMergeModalOpen(false)}
          onSuccess={handleMergeSuccess}
        />
      )}
    </div>
  );
};

export default FaceClusteringPage;
