// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Performance Dashboard Page
 *
 * Admin page for monitoring system performance metrics
 * - View endpoint response times
 * - Identify slow endpoints
 * - Monitor request volume
 * - View recent requests
 * - Reset metrics
 */

import React, { useState, useEffect } from 'react';
import apiClient from '../api/apiClient';
import './PerformanceDashboard.css';

function PerformanceDashboard() {
  const [summary, setSummary] = useState(null);
  const [slowEndpoints, setSlowEndpoints] = useState({});
  const [allMetrics, setAllMetrics] = useState({});
  const [recentRequests, setRecentRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [slowThreshold, setSlowThreshold] = useState(1000);
  const [selectedEndpoint, setSelectedEndpoint] = useState(null);

  useEffect(() => {
    fetchAllData();

    // Auto-refresh every 5 seconds if enabled
    if (autoRefresh) {
      const interval = setInterval(fetchAllData, 5000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, slowThreshold]);

  const fetchAllData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch all metrics in parallel
      const [summaryRes, slowRes, metricsRes, recentRes] = await Promise.all([
        apiClient.get('/metrics/performance/summary'),
        apiClient.get(`/metrics/performance/slow?threshold_ms=${slowThreshold}`),
        apiClient.get('/metrics/performance'),
        apiClient.get('/metrics/performance/recent?limit=50'),
      ]);

      setSummary(summaryRes.data);
      setSlowEndpoints(slowRes.data.slow_endpoints || {});
      setAllMetrics(metricsRes.data.endpoints || {});
      setRecentRequests(recentRes.data.requests || []);

    } catch (err) {
      console.error('Error fetching performance data:', err);
      setError('Failed to load performance metrics');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Are you sure you want to reset all performance metrics? This cannot be undone.')) {
      return;
    }

    try {
      await apiClient.post('/metrics/performance/reset');
      fetchAllData();
      alert('Performance metrics reset successfully');
    } catch (err) {
      alert('Failed to reset metrics: ' + err.message);
    }
  };

  const formatTime = (ms) => {
    if (ms < 1) return `${(ms * 1000).toFixed(2)}µs`;
    if (ms < 1000) return `${ms.toFixed(2)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatNumber = (num) => {
    return num?.toLocaleString() || '0';
  };

  const getStatusColor = (avgTime) => {
    if (avgTime < 100) return 'status-good';
    if (avgTime < 500) return 'status-ok';
    if (avgTime < 1000) return 'status-warning';
    return 'status-critical';
  };

  if (loading && !summary) {
    return (
      <div className="performance-dashboard">
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Loading performance metrics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="performance-dashboard">
      <div className="dashboard-header">
        <div>
          <h1>Performance Dashboard</h1>
          <p className="subtitle">Monitor API endpoint performance and system health</p>
        </div>
        <div className="header-actions">
          <label className="auto-refresh-toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh (5s)
          </label>
          <button onClick={fetchAllData} className="btn-refresh">
            Refresh Now
          </button>
          <button onClick={handleReset} className="btn-reset">
            Reset Metrics
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className="metrics-summary">
          <div className="metric-card">
            <div className="metric-label">Total Requests</div>
            <div className="metric-value">{formatNumber(summary.total_requests)}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Unique Endpoints</div>
            <div className="metric-value">{formatNumber(summary.unique_endpoints)}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Avg Response Time</div>
            <div className={`metric-value ${getStatusColor(summary.overall_avg_time)}`}>
              {formatTime(summary.overall_avg_time)}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Error Rate</div>
            <div className={`metric-value ${summary.error_rate_percent > 1 ? 'status-critical' : 'status-good'}`}>
              {summary.error_rate_percent?.toFixed(2)}%
            </div>
          </div>
          <div className="metric-card metric-card-wide">
            <div className="metric-label">Slowest Endpoint</div>
            <div className="metric-value-small">
              <div>{summary.slowest_endpoint?.path}</div>
              <div className={getStatusColor(summary.slowest_endpoint?.avg_time)}>
                {formatTime(summary.slowest_endpoint?.avg_time)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Slow Endpoints Section */}
      <div className="dashboard-section">
        <div className="section-header">
          <h2>Slow Endpoints</h2>
          <div className="threshold-selector">
            <label>
              Threshold:
              <select value={slowThreshold} onChange={(e) => setSlowThreshold(Number(e.target.value))}>
                <option value={100}>100ms</option>
                <option value={500}>500ms</option>
                <option value={1000}>1000ms</option>
                <option value={2000}>2000ms</option>
              </select>
            </label>
          </div>
        </div>

        {Object.keys(slowEndpoints).length === 0 ? (
          <div className="empty-state">
            No slow endpoints found above {slowThreshold}ms threshold
          </div>
        ) : (
          <div className="endpoints-table">
            <table>
              <thead>
                <tr>
                  <th>Endpoint</th>
                  <th>Avg Time</th>
                  <th>Requests</th>
                  <th>Min Time</th>
                  <th>Max Time</th>
                  <th>Errors</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(slowEndpoints).map(([endpoint, metrics]) => (
                  <tr
                    key={endpoint}
                    onClick={() => setSelectedEndpoint(endpoint)}
                    className={selectedEndpoint === endpoint ? 'selected' : ''}
                  >
                    <td className="endpoint-name">{endpoint}</td>
                    <td className={getStatusColor(metrics.avg_time)}>
                      {formatTime(metrics.avg_time)}
                    </td>
                    <td>{formatNumber(metrics.count)}</td>
                    <td>{formatTime(metrics.min_time)}</td>
                    <td>{formatTime(metrics.max_time)}</td>
                    <td className={metrics.errors > 0 ? 'has-errors' : ''}>
                      {metrics.errors || 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* All Endpoints Section */}
      <div className="dashboard-section">
        <h2>All Endpoints</h2>
        {Object.keys(allMetrics).length === 0 ? (
          <div className="empty-state">
            No metrics collected yet. Metrics will appear as API requests are made.
          </div>
        ) : (
          <div className="endpoints-grid">
            {Object.entries(allMetrics)
              .sort((a, b) => b[1].count - a[1].count)
              .slice(0, 12)
              .map(([endpoint, metrics]) => (
                <div key={endpoint} className="endpoint-card">
                  <div className="endpoint-card-header">
                    <span className="endpoint-path">{endpoint}</span>
                  </div>
                  <div className="endpoint-card-stats">
                    <div className="stat">
                      <span className="stat-label">Requests</span>
                      <span className="stat-value">{formatNumber(metrics.count)}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Avg Time</span>
                      <span className={`stat-value ${getStatusColor(metrics.avg_time)}`}>
                        {formatTime(metrics.avg_time)}
                      </span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Errors</span>
                      <span className={`stat-value ${metrics.errors > 0 ? 'has-errors' : ''}`}>
                        {metrics.errors || 0}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>

      {/* Recent Requests Section */}
      <div className="dashboard-section">
        <h2>Recent Requests (Last 50)</h2>
        {recentRequests.length === 0 ? (
          <div className="empty-state">
            No recent requests recorded
          </div>
        ) : (
          <div className="recent-requests-table">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Endpoint</th>
                  <th>Duration</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {recentRequests.slice(0, 50).map((req, idx) => (
                  <tr key={idx}>
                    <td>{new Date(req.timestamp).toLocaleTimeString()}</td>
                    <td className="endpoint-name">{req.endpoint}</td>
                    <td className={getStatusColor(req.duration_ms)}>
                      {formatTime(req.duration_ms)}
                    </td>
                    <td className={`status-code ${req.status_code >= 400 ? 'error-status' : 'success-status'}`}>
                      {req.status_code}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default PerformanceDashboard;
