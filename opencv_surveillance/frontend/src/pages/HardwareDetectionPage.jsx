// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import { useCachedApi } from '../hooks/useCachedApi';
import { CacheTTL } from '../services/apiCache';
import LoadingSkeleton from '../components/LoadingSkeleton';
import { Button } from '../components/universal';
import './HardwareDetectionPage.css';

/**
 * Hardware Detection Page
 *
 * Displays system hardware capabilities and provides feature recommendations
 * based on detected hardware.
 */
const HardwareDetectionPage = () => {
  const [selectedTab, setSelectedTab] = useState('overview'); // 'overview', 'features', 'recommendations'

  // Fetch hardware information
  const {
    data: hardwareInfo,
    loading: hardwareLoading,
    error: hardwareError,
    refetch: refetchHardware
  } = useCachedApi('/hardware/info', {
    ttl: CacheTTL.LONG, // 1 minute cache
  });

  // Fetch hardware tier
  const {
    data: tierInfo,
    loading: tierLoading
  } = useCachedApi('/hardware/tier', {
    ttl: CacheTTL.LONG,
  });

  // Fetch optimal configuration
  const {
    data: optimalConfig,
    loading: configLoading
  } = useCachedApi('/features/optimal-config', {
    ttl: CacheTTL.LONG,
  });

  // Fetch all available features
  const {
    data: allFeatures,
    loading: featuresLoading
  } = useCachedApi('/features/all', {
    ttl: CacheTTL.VERY_LONG, // 5 minutes cache (features don't change often)
  });

  const isLoading = hardwareLoading || tierLoading || configLoading;

  // Format bytes to GB
  const formatGB = (gb) => gb ? gb.toFixed(1) : '0.0';

  // Format MHz to GHz
  const formatGHz = (mhz) => mhz ? (mhz / 1000).toFixed(2) : '0.00';

  // Get tier badge color
  const getTierColor = (tier) => {
    switch (tier) {
      case 'high_end':
        return 'tier-high';
      case 'medium':
        return 'tier-medium';
      case 'low':
        return 'tier-low';
      default:
        return 'tier-minimal';
    }
  };

  // Render hardware overview tab
  const renderOverview = () => (
    <div className="hardware-overview">
      <div className="hardware-section">
        <h3 className="section-heading">System Information</h3>
        <div className="info-grid">
          <div className="info-card">
            <div className="info-icon">💻</div>
            <div className="info-content">
              <div className="info-label">Platform</div>
              <div className="info-value">{hardwareInfo?.platform || 'Unknown'}</div>
            </div>
          </div>
          <div className="info-card">
            <div className="info-icon">🐍</div>
            <div className="info-content">
              <div className="info-label">Python Version</div>
              <div className="info-value">{hardwareInfo?.python_version || 'Unknown'}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="hardware-section">
        <h3 className="section-heading">CPU</h3>
        <div className="info-grid">
          <div className="info-card">
            <div className="info-icon">⚙️</div>
            <div className="info-content">
              <div className="info-label">Model</div>
              <div className="info-value">{hardwareInfo?.cpu_model || 'Unknown'}</div>
            </div>
          </div>
          <div className="info-card">
            <div className="info-icon">🔢</div>
            <div className="info-content">
              <div className="info-label">Cores / Threads</div>
              <div className="info-value">
                {hardwareInfo?.cpu_cores || 0} / {hardwareInfo?.cpu_threads || 0}
              </div>
            </div>
          </div>
          <div className="info-card">
            <div className="info-icon">⚡</div>
            <div className="info-content">
              <div className="info-label">Frequency</div>
              <div className="info-value">
                {formatGHz(hardwareInfo?.cpu_frequency_mhz)} GHz
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="hardware-section">
        <h3 className="section-heading">Memory (RAM)</h3>
        <div className="info-grid">
          <div className="info-card">
            <div className="info-icon">💾</div>
            <div className="info-content">
              <div className="info-label">Total RAM</div>
              <div className="info-value">{formatGB(hardwareInfo?.ram_total_gb)} GB</div>
            </div>
          </div>
          <div className="info-card">
            <div className="info-icon">📊</div>
            <div className="info-content">
              <div className="info-label">Available</div>
              <div className="info-value">{formatGB(hardwareInfo?.ram_available_gb)} GB</div>
            </div>
          </div>
          <div className="info-card">
            <div className="info-icon">📈</div>
            <div className="info-content">
              <div className="info-label">Usage</div>
              <div className="info-value">
                {hardwareInfo?.ram_used_percent?.toFixed(1) || 0}%
              </div>
            </div>
          </div>
        </div>
        {hardwareInfo && (
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${hardwareInfo.ram_used_percent}%` }}
            />
          </div>
        )}
      </div>

      <div className="hardware-section">
        <h3 className="section-heading">GPU</h3>
        {hardwareInfo?.gpu_available ? (
          <div className="info-grid">
            <div className="info-card">
              <div className="info-icon">🎮</div>
              <div className="info-content">
                <div className="info-label">Model</div>
                <div className="info-value">{hardwareInfo.gpu_name}</div>
              </div>
            </div>
            <div className="info-card">
              <div className="info-icon">💾</div>
              <div className="info-content">
                <div className="info-label">VRAM</div>
                <div className="info-value">
                  {(hardwareInfo.gpu_memory_total_mb / 1024).toFixed(1)} GB
                </div>
              </div>
            </div>
            {hardwareInfo.cuda_version && (
              <div className="info-card">
                <div className="info-icon">🔧</div>
                <div className="info-content">
                  <div className="info-label">CUDA Version</div>
                  <div className="info-value">{hardwareInfo.cuda_version}</div>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="empty-state-small">
            <span className="empty-icon">⚠️</span>
            <p>No GPU detected</p>
            <p className="text-small">CPU-only features will be used</p>
          </div>
        )}
      </div>

      <div className="hardware-section">
        <h3 className="section-heading">Storage</h3>
        <div className="info-grid">
          <div className="info-card">
            <div className="info-icon">💿</div>
            <div className="info-content">
              <div className="info-label">Total Space</div>
              <div className="info-value">{formatGB(hardwareInfo?.disk_total_gb)} GB</div>
            </div>
          </div>
          <div className="info-card">
            <div className="info-icon">📦</div>
            <div className="info-content">
              <div className="info-label">Free Space</div>
              <div className="info-value">{formatGB(hardwareInfo?.disk_free_gb)} GB</div>
            </div>
          </div>
          <div className="info-card">
            <div className="info-icon">📊</div>
            <div className="info-content">
              <div className="info-label">Usage</div>
              <div className="info-value">
                {hardwareInfo?.disk_used_percent?.toFixed(1) || 0}%
              </div>
            </div>
          </div>
        </div>
        {hardwareInfo && (
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${hardwareInfo.disk_used_percent}%` }}
            />
          </div>
        )}
      </div>
    </div>
  );

  // Render features tab
  const renderFeatures = () => {
    if (!optimalConfig?.features) return null;

    const featureEntries = Object.entries(optimalConfig.features);
    const enabledFeatures = featureEntries.filter(([_, config]) => config.recommended);
    const disabledFeatures = featureEntries.filter(([_, config]) => !config.recommended);

    return (
      <div className="features-list">
        <div className="features-section">
          <h3 className="section-heading">✅ Recommended Features ({enabledFeatures.length})</h3>
          {enabledFeatures.length === 0 ? (
            <div className="empty-state-small">
              <p>No features recommended for current hardware</p>
            </div>
          ) : (
            <div className="feature-grid">
              {enabledFeatures.map(([featureId, config]) => {
                const featureDetails = allFeatures?.features?.find(f => f.feature_id === featureId);
                return (
                  <div key={featureId} className="feature-card recommended">
                    <div className="feature-header">
                      <h4>{featureDetails?.name || featureId}</h4>
                      {config.use_gpu && <span className="badge badge-gpu">GPU</span>}
                      {config.use_cpu && <span className="badge badge-cpu">CPU</span>}
                    </div>
                    <p className="feature-description">
                      {featureDetails?.description || 'No description available'}
                    </p>
                    {featureDetails?.performance_warning && (
                      <div className="feature-warning">
                        ⚠️ {featureDetails.performance_warning}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="features-section">
          <h3 className="section-heading">❌ Not Recommended ({disabledFeatures.length})</h3>
          <div className="feature-grid">
            {disabledFeatures.map(([featureId, config]) => {
              const featureDetails = allFeatures?.features?.find(f => f.feature_id === featureId);
              return (
                <div key={featureId} className="feature-card not-recommended">
                  <div className="feature-header">
                    <h4>{featureDetails?.name || featureId}</h4>
                  </div>
                  <p className="feature-description">
                    {featureDetails?.description || 'No description available'}
                  </p>
                  {config.warnings && config.warnings.length > 0 && (
                    <div className="feature-warnings">
                      {config.warnings.map((warning, idx) => (
                        <div key={idx} className="feature-warning">
                          ⚠️ {warning}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  };

  // Render recommendations tab
  const renderRecommendations = () => {
    if (!tierInfo || !optimalConfig) return null;

    return (
      <div className="recommendations-section">
        <div className="tier-banner">
          <h3>Your Hardware Tier</h3>
          <div className={`tier-badge ${getTierColor(tierInfo.tier)}`}>
            {tierInfo.tier?.replace('_', ' ').toUpperCase()}
          </div>
          <p className="tier-description">
            {tierInfo.tier === 'high_end' && 'Your hardware can run all features at maximum quality'}
            {tierInfo.tier === 'medium' && 'Your hardware can handle most features comfortably'}
            {tierInfo.tier === 'low' && 'Your hardware is suitable for basic surveillance features'}
            {tierInfo.tier === 'minimal' && 'Consider hardware upgrades for better performance'}
          </p>
        </div>

        <div className="recommendations-grid">
          <div className="recommendation-card">
            <h4>Recommended Cameras</h4>
            <div className="recommendation-value">{tierInfo.max_cameras}</div>
            <p className="recommendation-note">Maximum number of cameras your system can handle</p>
          </div>
          <div className="recommendation-card">
            <h4>Processing Resolution</h4>
            <div className="recommendation-value">{tierInfo.processing_resolution}</div>
            <p className="recommendation-note">Optimal resolution for detection processing</p>
          </div>
        </div>

        {optimalConfig.recommendations && optimalConfig.recommendations.length > 0 && (
          <div className="recommendations-list">
            <h3 className="section-heading">Recommendations</h3>
            {optimalConfig.recommendations.map((recommendation, idx) => (
              <div key={idx} className="recommendation-item">
                <span className="recommendation-icon">💡</span>
                <span className="recommendation-text">{recommendation}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="hardware-detection-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Hardware Detection</h1>
          <p className="page-subtitle">
            View your system capabilities and get optimized feature recommendations
          </p>
        </div>
        <Button
          variant="primary"
          size="medium"
          onClick={() => refetchHardware()}
          disabled={isLoading}
          icon="🔄"
        >
          Refresh
        </Button>
      </div>

      {hardwareError && (
        <div className="error-banner">
          <span>⚠️</span>
          <span>Failed to load hardware information: {hardwareError.message}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="tabs">
        <Button
          variant={selectedTab === 'overview' ? 'primary' : 'tertiary'}
          size="medium"
          onClick={() => setSelectedTab('overview')}
        >
          Overview
        </Button>
        <Button
          variant={selectedTab === 'features' ? 'primary' : 'tertiary'}
          size="medium"
          onClick={() => setSelectedTab('features')}
        >
          Features
        </Button>
        <Button
          variant={selectedTab === 'recommendations' ? 'primary' : 'tertiary'}
          size="medium"
          onClick={() => setSelectedTab('recommendations')}
        >
          Recommendations
        </Button>
      </div>

      {/* Tab Content */}
      <div className="tab-content">
        {isLoading ? (
          <div className="loading-container">
            <LoadingSkeleton variant="card" height={200} count={3} />
          </div>
        ) : (
          <>
            {selectedTab === 'overview' && renderOverview()}
            {selectedTab === 'features' && renderFeatures()}
            {selectedTab === 'recommendations' && renderRecommendations()}
          </>
        )}
      </div>
    </div>
  );
};

export default HardwareDetectionPage;
