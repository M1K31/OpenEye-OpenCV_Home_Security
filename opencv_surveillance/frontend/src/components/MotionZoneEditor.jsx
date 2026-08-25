import React, { useState, useEffect, useRef } from 'react';
import { activateOnKey } from '../utils/a11y';
import motionZonesService from '../services/motionZonesService';
import Switch from './Switch';
import './MotionZoneEditor.css';

const MotionZoneEditor = ({ cameraId, onClose }) => {
  const canvasRef = useRef(null);
  const [zones, setZones] = useState([]);
  const [selectedZone, setSelectedZone] = useState(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [currentPoints, setCurrentPoints] = useState([]);
  const [newZoneName, setNewZoneName] = useState('');
  const [newZoneColor, setNewZoneColor] = useState('#00FF00');
  const [isExclusionZone, setIsExclusionZone] = useState(false);
  const [sensitivityMultiplier, setSensitivityMultiplier] = useState(1.0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load zones on mount
  useEffect(() => {
    loadZones();
  }, [cameraId]);

  // Redraw canvas when zones change
  useEffect(() => {
    if (canvasRef.current) {
      drawCanvas();
    }
  }, [zones, selectedZone, currentPoints, isDrawing]);

  const loadZones = async () => {
    try {
      setLoading(true);
      const data = await motionZonesService.getZones(cameraId, true);
      setZones(data.zones || []);
      setError(null);
    } catch (err) {
      console.error('Failed to load zones:', err);
      setError('Failed to load zones');
    } finally {
      setLoading(false);
    }
  };

  const drawCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const cellWidth = width / 10;
    const cellHeight = height / 10;

    // Clear canvas (keeping it transparent to show video underneath)
    ctx.clearRect(0, 0, width, height);

    // Draw semi-transparent grid for reference (only when drawing)
    if (isDrawing) {
      // Draw grid lines
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.lineWidth = 1;
      for (let i = 0; i <= 10; i++) {
        const x = (width / 10) * i;
        const y = (height / 10) * i;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Highlight grid cells where points are placed
      currentPoints.forEach(point => {
        const cellX = Math.floor(point.x * 10);
        const cellY = Math.floor(point.y * 10);
        const x = cellX * cellWidth;
        const y = cellY * cellHeight;

        // Fill the grid cell with semi-transparent color
        ctx.fillStyle = `${newZoneColor}40`; // 40 = 25% opacity in hex
        ctx.fillRect(x, y, cellWidth, cellHeight);

        // Add a border to the highlighted cell
        ctx.strokeStyle = newZoneColor;
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, cellWidth, cellHeight);
      });
    }

    // Draw existing zones
    zones.forEach(zone => {
      try {
        const coords = JSON.parse(zone.coordinates);
        if (!coords || coords.length < 3) return;

        const isSelected = selectedZone?.id === zone.id;

        ctx.beginPath();
        coords.forEach((point, index) => {
          const x = point.x * width;
          const y = point.y * height;
          if (index === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        });
        ctx.closePath();

        // Fill
        ctx.fillStyle = zone.is_active
          ? `${zone.color}${Math.floor(zone.opacity * 255).toString(16).padStart(2, '0')}`
          : 'rgba(128, 128, 128, 0.2)';
        ctx.fill();

        // Stroke
        ctx.strokeStyle = isSelected ? '#FFD700' : zone.color;
        ctx.lineWidth = isSelected ? 3 : 2;
        ctx.stroke();

        // Draw zone label
        if (coords.length > 0) {
          const centerX = coords.reduce((sum, p) => sum + p.x, 0) / coords.length * width;
          const centerY = coords.reduce((sum, p) => sum + p.y, 0) / coords.length * height;

          ctx.fillStyle = zone.color;
          ctx.font = 'bold 14px Arial';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(zone.name, centerX, centerY);
        }

        // Draw vertex points if selected
        if (isSelected) {
          coords.forEach(point => {
            const x = point.x * width;
            const y = point.y * height;
            ctx.fillStyle = '#FFD700';
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, Math.PI * 2);
            ctx.fill();
          });
        }
      } catch (err) {
        console.error('Error drawing zone:', zone, err);
      }
    });

    // Draw current drawing points
    if (isDrawing && currentPoints.length > 0) {
      ctx.beginPath();
      currentPoints.forEach((point, index) => {
        const x = point.x * width;
        const y = point.y * height;
        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }

        // Draw point markers
        ctx.fillStyle = newZoneColor;
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();
      });

      ctx.strokeStyle = newZoneColor;
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  };

  const handleCanvasClick = (event) => {
    if (!isDrawing) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;

    setCurrentPoints([...currentPoints, { x, y }]);
  };

  const startDrawing = () => {
    if (!newZoneName.trim()) {
      alert('Please enter a zone name first');
      return;
    }
    setIsDrawing(true);
    setCurrentPoints([]);
    setSelectedZone(null);
  };

  const finishDrawing = async () => {
    if (currentPoints.length < 3) {
      alert('Please draw at least 3 points to create a zone');
      return;
    }

    try {
      const zoneData = {
        name: newZoneName,
        zone_type: 'polygon',
        coordinates: JSON.stringify(currentPoints),
        color: newZoneColor,
        opacity: 0.3,
        is_active: true,
        is_exclusion_zone: isExclusionZone,
        sensitivity_multiplier: sensitivityMultiplier
      };

      await motionZonesService.createZone(cameraId, zoneData);
      await loadZones();

      // Reset drawing state
      setIsDrawing(false);
      setCurrentPoints([]);
      setNewZoneName('');
      setNewZoneColor('#00FF00');
      setIsExclusionZone(false);
      setSensitivityMultiplier(1.0);
    } catch (err) {
      console.error('Failed to create zone:', err);
      alert('Failed to create zone: ' + err.message);
    }
  };

  const cancelDrawing = () => {
    setIsDrawing(false);
    setCurrentPoints([]);
  };

  const deleteZone = async (zoneId) => {
    if (!confirm('Are you sure you want to delete this zone?')) return;

    try {
      await motionZonesService.deleteZone(cameraId, zoneId);
      await loadZones();
      if (selectedZone?.id === zoneId) {
        setSelectedZone(null);
      }
    } catch (err) {
      console.error('Failed to delete zone:', err);
      alert('Failed to delete zone');
    }
  };

  const toggleZoneActive = async (zoneId) => {
    try {
      await motionZonesService.toggleZone(cameraId, zoneId);
      await loadZones();
    } catch (err) {
      console.error('Failed to toggle zone:', err);
      alert('Failed to toggle zone');
    }
  };

  return (
    <div className="zone-editor-container">
      <div className="zone-editor-header">
        <h2 className="zone-editor-title">Motion Detection Zones - {cameraId}</h2>
        <button className="zone-editor-close" onClick={onClose}>&times;</button>
      </div>

      {error && (
        <div style={{ padding: '12px', background: 'var(--danger-color)', color: 'var(--text-on-status)', borderRadius: '4px' }}>
          {error}
        </div>
      )}

      <div className="zone-editor-content">
        {/* Canvas Section */}
        <div className="zone-canvas-section">
          {/* Instructions */}
          <div className="zone-instructions">
            <h4 className="zone-instructions-title">How to Draw Motion Detection Zones</h4>
            <ul className="zone-instructions-list">
              <li><strong>Click</strong> on the camera view to place points - each click places a dot that defines the zone boundary</li>
              <li><strong>Grid cells light up</strong> when you place a dot - highlighted cells show where motion will be detected</li>
              <li><strong>Motion is detected</strong> only inside the area enclosed by your dots (the polygon you draw)</li>
              <li><strong>At least 3 points</strong> are required to create a detection zone</li>
              <li><strong>Exclusion zones</strong> ignore motion - useful for trees, flags, or busy roads you want to exclude</li>
              <li><strong>Multiple zones</strong> can be created with different sensitivity levels</li>
            </ul>
          </div>
          <div className="zone-canvas-wrapper">
            {/* Live camera feed background */}
            <img
              src={`/api/cameras/${cameraId}/stream`}
              alt="Camera Feed"
              className="zone-camera-feed"
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                zIndex: 1,
              }}
            />
            {/* Canvas overlay for drawing zones */}
            <canvas
              ref={canvasRef}
              className={`zone-canvas ${isDrawing ? 'drawing' : ''}`}
              width={1280}
              height={720}
              onClick={handleCanvasClick}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                zIndex: 2,
              }}
            />
            {isDrawing && (
              <div className="zone-canvas-overlay">
                Click to add points • {currentPoints.length} points placed
              </div>
            )}
          </div>

          <div className="zone-drawing-controls">
            {!isDrawing ? (
              <button className="zone-control-btn primary" onClick={startDrawing}>
                ✏️ Start Drawing Zone
              </button>
            ) : (
              <>
                <button className="zone-control-btn primary" onClick={finishDrawing} disabled={currentPoints.length < 3}>
                  ✓ Finish Zone ({currentPoints.length} points)
                </button>
                <button className="zone-control-btn danger" onClick={cancelDrawing}>
                  ✕ Cancel
                </button>
              </>
            )}
          </div>

          {/* Zone Form */}
          {isDrawing || !selectedZone ? (
            <div className="zone-form">
              <div className="zone-form-group">
                <label className="zone-form-label">Zone Name</label>
                <input
                  type="text"
                  className="zone-form-input"
                  value={newZoneName}
                  onChange={(e) => setNewZoneName(e.target.value)}
                  placeholder="e.g., Front Door, Driveway"
                  disabled={isDrawing}
                />
              </div>

              <div className="zone-form-group">
                <label className="zone-form-label">Zone Color</label>
                <input
                  type="color"
                  className="zone-form-input"
                  value={newZoneColor}
                  onChange={(e) => setNewZoneColor(e.target.value)}
                  disabled={isDrawing}
                />
              </div>

              <div className="zone-form-group">
                <label className="zone-form-label">Sensitivity Multiplier ({sensitivityMultiplier.toFixed(1)}x)</label>
                <input
                  type="range"
                  min="0.1"
                  max="5.0"
                  step="0.1"
                  value={sensitivityMultiplier}
                  onChange={(e) => setSensitivityMultiplier(parseFloat(e.target.value))}
                  disabled={isDrawing}
                />
                <small style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                  &lt;1.0 = less sensitive, &gt;1.0 = more sensitive
                </small>
              </div>

              <div className="zone-form-group">
                <Switch
                  checked={isExclusionZone}
                  onChange={setIsExclusionZone}
                  disabled={isDrawing}
                  label="Exclusion Zone (ignore motion in this area)"
                  color="warning"
                />
              </div>
            </div>
          ) : null}
        </div>

        {/* Zones List Section */}
        <div className="zones-list-section">
          <div className="zones-list-header">
            <h3 className="zones-list-title">Zones ({zones.length})</h3>
          </div>

          <div className="zones-list">
            {zones.length === 0 ? (
              <div className="zones-empty-state">
                <div className="zones-empty-icon">📍</div>
                <div className="zones-empty-text">
                  No zones created yet.
                  <br />
                  Draw your first zone to get started!
                </div>
              </div>
            ) : (
              zones.map(zone => (
                <div
                  key={zone.id}
                  className={`zone-item ${selectedZone?.id === zone.id ? 'selected' : ''}`}
                  onClick={() => setSelectedZone(zone)}
                  onKeyDown={activateOnKey(() => setSelectedZone(zone))}
                  role="button"
                  tabIndex={0}
                >
                  <div className="zone-item-header">
                    <div className="zone-item-name">
                      <span className="zone-color-indicator" style={{ backgroundColor: zone.color }} />
                      {zone.name}
                    </div>
                    <div className="zone-item-actions">
                      <button
                        className="zone-action-btn"
                        onClick={(e) => { e.stopPropagation(); toggleZoneActive(zone.id); }}
                        title={zone.is_active ? 'Deactivate' : 'Activate'}
                      >
                        {zone.is_active ? '👁️' : '🚫'}
                      </button>
                      <button
                        className="zone-action-btn danger"
                        onClick={(e) => { e.stopPropagation(); deleteZone(zone.id); }}
                        title="Delete Zone"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>

                  <div className="zone-item-details">
                    <div className="zone-detail-row">
                      <span>Type:</span>
                      <span>{zone.zone_type}</span>
                    </div>
                    <div className="zone-detail-row">
                      <span>Sensitivity:</span>
                      <span>{zone.sensitivity_multiplier}x</span>
                    </div>
                    <div className="zone-detail-row">
                      <span>Events:</span>
                      <span>{zone.motion_events_count || 0}</span>
                    </div>
                    <div className="zone-detail-row">
                      <span>Status:</span>
                      <span>
                        <span className={`zone-badge ${zone.is_active ? 'active' : 'inactive'}`}>
                          {zone.is_active ? 'Active' : 'Inactive'}
                        </span>
                        {zone.is_exclusion_zone && (
                          <span className="zone-badge exclusion" style={{ marginLeft: '4px' }}>
                            Exclusion
                          </span>
                        )}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MotionZoneEditor;
