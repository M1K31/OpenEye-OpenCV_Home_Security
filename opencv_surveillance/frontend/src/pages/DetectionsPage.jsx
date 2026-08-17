/**
 * v3.11.6: Unified Detections Page
 *
 * Displays all detection types in one unified interface:
 * - People (face recognition) - shows unique people with detection counts
 * - Vehicles (YOLO)
 * - Animals (YOLO)
 * - Packages (YOLO)
 *
 * Face management overhaul (2026-07-27):
 * - Auto-enumerated "unknownN" placeholders are treated as UNKNOWN, not known.
 * - Any face card / person can be assigned to an existing saved profile OR a new
 *   one (AssignPersonModal), replacing the old new-name-only window.prompt.
 * - Batch multi-select: pick several detections -> save as a new person / add to
 *   an existing profile in one action (photos uploaded with auto_train).
 * - "Manage Person" opens the person's detection history in-page (no dead route).
 *
 * Follows Apple HIG guidelines with 8pt grid and 44px touch targets
 */

import React, { useState, useEffect } from 'react';
import apiClient from '../api/apiClient';
import { Button } from '../components/universal';

// A person is "known" only if they have a real name. Auto-enumerated placeholders
// ("Unknown", "unknown1", "unknown2", ...) produced by clustering are NOT known.
const isKnownPerson = (name) =>
  !!name && !/^unknown\d*$/i.test(String(name).trim());

// Strip any stored mount prefix so `/data/snapshots/${path}` is never doubled.
const normalizeSnapshot = (p) =>
  (p || '').replace(/^\/?(?:data|api)\/snapshots\//, '');

// A detection can legitimately have no image. The capture policy stops saving
// likenesses once a person's cluster is well established, or before a face has
// been seen across enough frames to be worth keeping — the sighting is still
// recorded, because where and when someone was seen is the point, but no
// snapshot is written.
//
// Rendering nothing in that case made a deliberate absence identical to a
// broken image: a blank card, no console error, and nothing to indicate the
// difference. This says so instead.
// Shown where a snapshot would be. A detection without an image is not a
// failure: once a profile is established the capture policy refreshes it at
// most once per day per camera, so most sightings deliberately keep no new
// likeness. Naming the profile matters — "seen, not captured" on its own reads
// as a lost detection, whereas naming who was recognised shows the recognition
// itself worked and only the photograph was skipped.
const SightingPlaceholder = ({ name }) => (
  <div style={styles.detectionImage}>
    <div style={styles.sightingPlaceholder}>
      <span style={styles.sightingIcon}>👁</span>
      {name && <span style={styles.sightingName}>{name}</span>}
      <span style={styles.sightingText}>Seen, not captured</span>
      <span style={styles.sightingHint}>
        Already well recorded, so no new image was saved
      </span>
    </div>
  </div>
);

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

  // Saved profiles (for the "add to existing person" picker)
  const [savedPeople, setSavedPeople] = useState([]);

  // Batch selection: map of stable-key -> detection-like object ({snapshot_path, cluster_id, name})
  const [selected, setSelected] = useState({});
  // Assignment modal: { detections: [...] } or null
  const [assignModal, setAssignModal] = useState(null);
  const [assignBusy, setAssignBusy] = useState(false);

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalPages, setTotalPages] = useState(1);

  // Load data on mount and when filters change
  useEffect(() => {
    loadData();
  }, [activeTab, page]);

  // Load saved profiles once on mount (used by the assign picker)
  useEffect(() => {
    loadSavedPeople();
  }, []);

  const loadSavedPeople = async () => {
    try {
      const response = await apiClient.get('/faces/people');
      const list = response.data?.data || response.data?.people || [];
      setSavedPeople(list.map((p) => p.name).filter(Boolean));
    } catch (err) {
      console.error('Failed to load saved profiles:', err);
    }
  };

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
        const faceDetections = (faceData.data || []).map(face => ({
          id: `face-${face.id}`,
          type: 'person',
          subtype: 'face',
          name: face.person_name,
          confidence: face.confidence,
          timestamp: face.detected_at,
          camera_id: face.camera_id,
          snapshot_path: normalizeSnapshot(face.snapshot_path),
          cluster_id: face.cluster_id,
          identified: isKnownPerson(face.person_name)
        }));
        allDetections = [...allDetections, ...faceDetections];
      } else {
        console.error('Failed to load face detections:', faceResponse.reason);
      }

      // Process object detections
      if (objectResponse.status === 'fulfilled') {
        const objectData = objectResponse.value.data;
        const objectDetections = (objectData.data || []).map(obj => ({
          id: `object-${obj.id}`,
          type: obj.object_class,
          subtype: obj.object_subclass,
          name: obj.identified_object_name || `Unknown ${obj.object_subclass}`,
          confidence: obj.confidence,
          timestamp: obj.detected_at,
          camera_id: obj.camera_id,
          snapshot_path: normalizeSnapshot(obj.snapshot_path),
          identified: !!obj.identified_object_id
        }));
        allDetections = [...allDetections, ...objectDetections];
      } else {
        console.error('Failed to load object detections:', objectResponse.reason);
      }

      // Sort all detections by timestamp (most recent first)
      allDetections.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      setDetections(allDetections);

    } catch (err) {
      console.error('Failed to load all detections:', err);
    }
  };

  const loadUniquePeople = async () => {
    try {
      // Load all face detections to aggregate by person
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
            isKnown: isKnownPerson(personName)
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

      // Convert to array: known people first, then by detection count
      const peopleArray = Array.from(peopleMap.values())
        .sort((a, b) => (b.isKnown - a.isKnown) || (b.detectionCount - a.detectionCount));

      setUniquePeople(peopleArray);
      setTotalPages(1); // All loaded in one page for unique people view
    } catch (err) {
      console.error('Failed to load unique people:', err);
    }
  };

  const loadPersonDetections = async (personName) => {
    try {
      setSelectedPerson(personName);
      setSelected({}); // reset batch selection when entering a person view
      const response = await apiClient.get(`/faces/history/person/${encodeURIComponent(personName)}?limit=100`);
      setPersonDetections(response.data || []);
    } catch (err) {
      console.error('Failed to load person detections:', err);
      setPersonDetections([]);
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
        snapshot_path: normalizeSnapshot(obj.snapshot_path),
        identified: !!obj.identified_object_id
      }));

      setDetections(prev => [...prev, ...objectDetections]);
      setTotalPages(Math.max(data.pagination?.total_pages || 1, totalPages));
    } catch (err) {
      console.error('Failed to load object detections:', err);
    }
  };

  const loadIdentifiedObjects = async () => {
    try {
      const response = await apiClient.get('/objects/identified');
      setIdentifiedObjects(response.data || []);
    } catch (err) {
      console.error('Failed to load identified objects:', err);
    }
  };

  // ---- Batch selection helpers -------------------------------------------
  const toggleSelect = (key, detection) => {
    setSelected(prev => {
      const next = { ...prev };
      if (next[key]) delete next[key];
      else next[key] = detection;
      return next;
    });
  };
  const clearSelection = () => setSelected({});
  const selectedList = Object.values(selected);

  // ---- Assignment ---------------------------------------------------------
  // Open the assign modal for one or more detections.
  const openAssign = (dets) => {
    const arr = Array.isArray(dets) ? dets : [dets];
    if (arr.length === 0) return;
    setAssignModal({ detections: arr });
  };

  // Assign the given detections to a person (existing or newly created).
  // Snapshots are uploaded as training photos with auto_train so recognition
  // works immediately; if any detection belongs to a cluster we also name the
  // cluster (which relabels that identity's whole history).
  const assignDetections = async (dets, personName, isNew) => {
    const name = (personName || '').trim();
    if (!name) return;
    setAssignBusy(true);
    try {
      if (isNew) {
        await apiClient.post('/faces/people', { name });
      }

      // Name any clusters represented in the selection (relabels their history).
      const clusterIds = [...new Set(dets.map(d => d.cluster_id).filter(Boolean))];
      for (const cid of clusterIds) {
        try {
          await apiClient.post(`/clusters/${cid}/assign-name`, { person_name: name });
        } catch (e) {
          console.warn('cluster assign-name failed for', cid, e);
        }
      }

      // Upload each detection's snapshot as a training photo (auto_train=true).
      const formData = new FormData();
      let fileCount = 0;
      for (const d of dets) {
        const p = normalizeSnapshot(d.snapshot_path);
        if (!p) continue;
        try {
          const resp = await fetch(`/data/snapshots/${p}`);
          if (!resp.ok) continue;
          const blob = await resp.blob();
          formData.append('files', new File([blob], p.split('/').pop() || 'face.jpg', {
            type: blob.type || 'image/jpeg',
          }));
          fileCount++;
        } catch (e) {
          console.warn('snapshot fetch failed for', p, e);
        }
      }

      if (fileCount > 0) {
        formData.append('auto_train', 'true');
        await apiClient.post(
          `/faces/people/${encodeURIComponent(name)}/photos`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );
      }

      setAssignModal(null);
      clearSelection();
      await loadSavedPeople();
      alert(
        `Assigned ${dets.length} detection${dets.length !== 1 ? 's' : ''} to "${name}".` +
        (fileCount ? ` Trained on ${fileCount} photo${fileCount !== 1 ? 's' : ''}.` : '')
      );
      // Refresh the current view
      if (activeTab === 'people' && selectedPerson) {
        loadPersonDetections(selectedPerson);
      } else {
        loadData();
      }
    } catch (error) {
      console.error('Error assigning detections:', error);
      alert('Error assigning person: ' + (error.response?.data?.detail || error.message));
    } finally {
      setAssignBusy(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const [faceStatsResponse, objectStatsResponse] = await Promise.allSettled([
        apiClient.get('/faces/history/statistics?days=7'),
        apiClient.get('/objects/detections/statistics')
      ]);

      let combinedStats = { total: 0, by_class: {}, face_stats: null };

      if (faceStatsResponse.status === 'fulfilled') {
        const faceStats = faceStatsResponse.value.data;
        combinedStats.face_stats = faceStats;
        combinedStats.by_class.person = faceStats.unique_people || 0;
        combinedStats.total += combinedStats.by_class.person;
        combinedStats.total_face_detections = faceStats.total_detections || 0;
      }

      if (objectStatsResponse.status === 'fulfilled') {
        const objectStats = objectStatsResponse.value.data;
        if (objectStats.by_class) {
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
    setDetections([]);
    setSelectedPerson(null);
    setPersonDetections([]);
    clearSelection();
  };

  const handlePageChange = (newPage) => {
    setPage(newPage);
    setDetections([]);
    clearSelection();
  };

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
            <StatCard icon="👤" label="People" count={statistics.by_class?.person || 0}
              active={activeTab === 'people'} onClick={() => handleTabChange('people')} />
            <StatCard icon="🚗" label="Vehicles" count={statistics.by_class?.vehicle || 0}
              active={activeTab === 'vehicles'} onClick={() => handleTabChange('vehicles')} />
            <StatCard icon="🐾" label="Animals" count={statistics.by_class?.animal || 0}
              active={activeTab === 'animals'} onClick={() => handleTabChange('animals')} />
            <StatCard icon="📦" label="Packages" count={statistics.by_class?.package || 0}
              active={activeTab === 'packages'} onClick={() => handleTabChange('packages')} />
          </div>
        )}

        {/* Tab Navigation */}
        <div style={styles.tabBar}>
          {['all', 'people', 'vehicles', 'animals', 'packages'].map(tab => (
            <Button key={tab}
              variant={activeTab === tab ? 'primary' : 'secondary'}
              size="medium"
              onClick={() => handleTabChange(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Button>
          ))}
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
                <div>
                  <div style={styles.personHeader}>
                    <Button variant="secondary" size="medium"
                      onClick={() => { setSelectedPerson(null); setPersonDetections([]); clearSelection(); }}>
                      ← Back to People
                    </Button>
                    <h2 style={styles.personTitle}>
                      {isKnownPerson(selectedPerson) ? '👤' : '❓'} {selectedPerson}
                    </h2>
                    <span style={styles.detectionCount}>
                      {personDetections.length} detection{personDetections.length !== 1 ? 's' : ''}
                    </span>
                  </div>

                  {/* Person-level actions: assign this whole identity to a profile */}
                  {personDetections.length > 0 && (
                    <div style={styles.personActions}>
                      <Button variant="primary" size="small"
                        onClick={() => openAssign(personDetections.map(d => ({
                          snapshot_path: d.snapshot_path, cluster_id: d.cluster_id, name: d.person_name,
                        })))}>
                        {isKnownPerson(selectedPerson) ? 'Merge into a profile…' : 'Save all as a person…'}
                      </Button>
                      <span style={styles.hintText}>
                        …or tick individual detections below to assign only those.
                      </span>
                    </div>
                  )}

                  {personDetections.length === 0 ? (
                    <div style={styles.empty}>
                      <span style={styles.emptyIcon}>🔍</span>
                      <h3>No detections found</h3>
                      <p>No detection history available for {selectedPerson}.</p>
                    </div>
                  ) : (
                    <div style={styles.detectionGrid}>
                      {personDetections.map((detection, index) => {
                        const key = `pd-${detection.id ?? index}`;
                        const snapshotPath = normalizeSnapshot(detection.snapshot_path);
                        const sel = !!selected[key];
                        return (
                          <div key={key}
                            style={{ ...styles.detectionCard, ...(sel ? styles.detectionCardSelected : {}) }}>
                            <label style={styles.selectCheckboxWrap}>
                              <input type="checkbox" checked={sel}
                                onChange={() => toggleSelect(key, {
                                  snapshot_path: detection.snapshot_path,
                                  cluster_id: detection.cluster_id,
                                  name: detection.person_name,
                                })}
                                style={styles.selectCheckbox} />
                            </label>
                            {snapshotPath ? (
                              <div style={styles.detectionImage}>
                                <img src={`/data/snapshots/${snapshotPath}`} alt={detection.person_name}
                                  style={styles.detectionImg}
                                  onError={(e) => { e.target.style.display = 'none'; }} />
                              </div>
                            ) : (
                              <SightingPlaceholder name={detection.person_name} />
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
                                  <span style={styles.metaValue}>{new Date(detection.detected_at).toLocaleString()}</span>
                                </div>
                              </div>
                              <div style={styles.detectionActions}>
                                <Button variant="secondary" size="small"
                                  onClick={() => openAssign([{
                                    snapshot_path: detection.snapshot_path,
                                    cluster_id: detection.cluster_id,
                                    name: detection.person_name,
                                  }])}>
                                  Assign to person…
                                </Button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : (
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
                          <PersonCard key={person.name || index} person={person}
                            onClick={() => loadPersonDetections(person.name)} />
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
                {detections.map(detection => {
                  const selectable = detection.type === 'person';
                  return (
                    <DetectionCard
                      key={detection.id}
                      detection={detection}
                      selectable={selectable}
                      selected={!!selected[detection.id]}
                      onToggleSelect={() => toggleSelect(detection.id, {
                        snapshot_path: detection.snapshot_path,
                        cluster_id: detection.cluster_id,
                        name: detection.name,
                      })}
                      onAssign={() => openAssign([{
                        snapshot_path: detection.snapshot_path,
                        cluster_id: detection.cluster_id,
                        name: detection.name,
                      }])}
                      onViewHistory={() => { setActiveTab('people'); loadPersonDetections(detection.name); }}
                    />
                  );
                })}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div style={styles.pagination}>
                  <Button variant="secondary" size="medium"
                    onClick={() => handlePageChange(page - 1)} disabled={page === 1}>
                    ← Previous
                  </Button>
                  <span style={styles.pageInfo}>Page {page} of {totalPages}</span>
                  <Button variant="secondary" size="medium"
                    onClick={() => handlePageChange(page + 1)} disabled={page === totalPages}>
                    Next →
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Sticky batch-selection toolbar */}
      {selectedList.length > 0 && (
        <div style={styles.batchToolbar}>
          <span style={styles.batchCount}>
            {selectedList.length} selected
          </span>
          <Button variant="primary" size="small" onClick={() => openAssign(selectedList)}>
            Assign to person…
          </Button>
          <Button variant="secondary" size="small" onClick={clearSelection}>
            Clear
          </Button>
        </div>
      )}

      {/* Assign-to-person modal */}
      {assignModal && (
        <AssignPersonModal
          count={assignModal.detections.length}
          savedPeople={savedPeople}
          busy={assignBusy}
          onCancel={() => setAssignModal(null)}
          onConfirm={(name, isNew) => assignDetections(assignModal.detections, name, isNew)}
        />
      )}
    </div>
  );
};

// Stat Card Component
const StatCard = ({ icon, label, count, active, onClick }) => (
  <button onClick={onClick} style={{ ...styles.statCard, ...(active ? styles.statCardActive : {}) }}>
    <div style={styles.statIcon}>{icon}</div>
    <div style={styles.statLabel}>{label}</div>
    <div style={styles.statCount}>{count.toLocaleString()}</div>
  </button>
);

// Assign-to-person modal: pick an existing saved profile or create a new one.
const AssignPersonModal = ({ count, savedPeople, busy, onCancel, onConfirm }) => {
  const [mode, setMode] = useState(savedPeople.length > 0 ? 'existing' : 'new');
  const [existing, setExisting] = useState(savedPeople[0] || '');
  const [newName, setNewName] = useState('');

  const canConfirm = mode === 'existing' ? !!existing : !!newName.trim();

  return (
    <div style={styles.modalOverlay} onClick={busy ? undefined : onCancel}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h3 style={styles.modalTitle}>
          Assign {count} detection{count !== 1 ? 's' : ''} to a person
        </h3>

        <div style={styles.modalField}>
          <label style={styles.radioRow}>
            <input type="radio" name="assignMode" checked={mode === 'existing'}
              disabled={savedPeople.length === 0}
              onChange={() => setMode('existing')} />
            <span>Add to an existing profile</span>
          </label>
          {mode === 'existing' && (
            <select style={styles.select} value={existing}
              onChange={(e) => setExisting(e.target.value)} disabled={savedPeople.length === 0}>
              {savedPeople.length === 0 && <option value="">No saved profiles yet</option>}
              {savedPeople.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          )}
        </div>

        <div style={styles.modalField}>
          <label style={styles.radioRow}>
            <input type="radio" name="assignMode" checked={mode === 'new'}
              onChange={() => setMode('new')} />
            <span>Create a new person</span>
          </label>
          {mode === 'new' && (
            <input style={styles.input} type="text" placeholder="Name (e.g. Mikel)"
              value={newName} autoFocus
              onChange={(e) => setNewName(e.target.value)} />
          )}
        </div>

        <div style={styles.modalActions}>
          <Button variant="secondary" size="medium" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" size="medium" disabled={!canConfirm || busy}
            onClick={() => onConfirm(mode === 'existing' ? existing : newName, mode === 'new')}>
            {busy ? 'Assigning…' : 'Assign & train'}
          </Button>
        </div>
      </div>
    </div>
  );
};

// Detection Card Component
const DetectionCard = ({ detection, selectable, selected, onToggleSelect, onAssign, onViewHistory }) => {
  const getTypeColor = (type) => ({
    person: '#007AFF', vehicle: '#FFCC00', animal: '#FF3B30', package: '#34C759',
  }[type] || '#8E8E93');
  const getTypeIcon = (type) => ({
    person: '👤', vehicle: '🚗', animal: '🐾', package: '📦',
  }[type] || '🔍');

  return (
    <div style={{ ...styles.detectionCard, ...(selected ? styles.detectionCardSelected : {}) }}>
      {selectable && (
        <label style={styles.selectCheckboxWrap}>
          <input type="checkbox" checked={selected} onChange={onToggleSelect} style={styles.selectCheckbox} />
        </label>
      )}
      {normalizeSnapshot(detection.snapshot_path) ? (
        <div style={styles.detectionImage}>
          <img src={`/data/snapshots/${normalizeSnapshot(detection.snapshot_path)}`}
            alt={detection.name || detection.person_name}
            style={styles.detectionImg}
            onError={(e) => { e.target.style.display = 'none'; }} />
        </div>
      ) : (
        <SightingPlaceholder name={detection.name || detection.person_name} />
      )}

      <div style={styles.detectionContent}>
        <div style={styles.detectionHeader}>
          <span style={styles.detectionIcon}>{getTypeIcon(detection.type)}</span>
          <span style={{ ...styles.detectionBadge, backgroundColor: getTypeColor(detection.type) }}>
            {detection.type}
          </span>
          {detection.identified && <span style={styles.identifiedBadge}>✓ Identified</span>}
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
            <span style={styles.metaValue}>{new Date(detection.timestamp).toLocaleString()}</span>
          </div>
        </div>

        {/* Face management actions */}
        {detection.type === 'person' && (
          <div style={styles.detectionActions}>
            <Button variant="primary" size="small" onClick={onAssign} style={{ marginRight: '8px' }}>
              {detection.identified ? 'Reassign / add to profile…' : 'Assign to person…'}
            </Button>
            {detection.identified && onViewHistory && (
              <Button variant="secondary" size="small" onClick={onViewHistory}>
                View history
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// Person Card Component - shows unique person with detection count
const PersonCard = ({ person, onClick }) => {
  const snapshotPath = normalizeSnapshot(person.lastSnapshot);
  return (
    <button onClick={onClick} style={styles.personCard}>
      {snapshotPath ? (
        <div style={styles.detectionImage}>
          <img src={`/data/snapshots/${snapshotPath}`} alt={person.name}
            style={styles.detectionImg}
            onError={(e) => { e.target.style.display = 'none'; }} />
        </div>
      ) : (
        <SightingPlaceholder name={person.name} />
      )}

      <div style={styles.personCardContent}>
        <div style={styles.personCardHeader}>
          <span style={styles.personIcon}>{person.isKnown ? '👤' : '❓'}</span>
          {person.isKnown
            ? <span style={styles.identifiedBadge}>✓ Known</span>
            : <span style={styles.unknownBadge}>Unknown</span>}
        </div>

        <h3 style={styles.personCardName}>{person.name}</h3>

        <div style={styles.personCardStats}>
          <div style={styles.personCardStat}>
            <span style={styles.statNumber}>{person.detectionCount}</span>
            <span style={styles.statText}>detection{person.detectionCount !== 1 ? 's' : ''}</span>
          </div>
        </div>

        <div style={styles.personCardMeta}>
          <div style={styles.detectionMetaItem}>
            <span style={styles.metaLabel}>Last seen:</span>
            <span style={styles.metaValue}>{new Date(person.lastSeen).toLocaleString()}</span>
          </div>
          <div style={styles.detectionMetaItem}>
            <span style={styles.metaLabel}>Camera:</span>
            <span style={styles.metaValue}>{person.lastCamera}</span>
          </div>
        </div>

        <div style={styles.viewDetailsHint}>
          {person.isKnown ? 'View & manage detections →' : 'Review & assign detections →'}
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
  mainContent: { flex: 1, padding: '0', color: 'var(--text-primary, var(--theme-text))' },
  header: { marginBottom: '24px' },
  title: { fontSize: '32px', fontWeight: '700', margin: '0 0 8px 0', color: 'var(--theme-text)' },
  subtitle: { fontSize: '16px', color: 'var(--theme-text-secondary)', margin: 0 },
  statsGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '16px', marginBottom: '24px',
  },
  statCard: {
    background: 'var(--theme-card-background)', border: '2px solid var(--theme-border)',
    borderRadius: '12px', padding: '16px', textAlign: 'center', cursor: 'pointer',
    transition: 'all 0.2s ease', minHeight: '120px', display: 'flex',
    flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
  },
  statCardActive: {
    borderColor: 'var(--theme-primary)', backgroundColor: 'var(--theme-primary-light)',
    transform: 'scale(1.02)',
  },
  statIcon: { fontSize: '32px', marginBottom: '8px' },
  statLabel: { fontSize: '14px', color: 'var(--theme-text-secondary)', marginBottom: '4px' },
  statCount: { fontSize: '24px', fontWeight: '700', color: 'var(--theme-text)' },
  tabBar: {
    display: 'flex', gap: '8px', marginBottom: '24px',
    borderBottom: '1px solid var(--theme-border)', paddingBottom: '8px', flexWrap: 'wrap',
  },
  contentArea: { minHeight: '400px' },
  loading: { textAlign: 'center', padding: '48px', fontSize: '18px', color: 'var(--theme-text-secondary)' },
  error: {
    backgroundColor: '#ff3b301a', border: '1px solid #ff3b30', borderRadius: '8px',
    padding: '16px', display: 'flex', gap: '12px', alignItems: 'center', color: '#ff3b30',
  },
  empty: { textAlign: 'center', padding: '64px 24px', color: 'var(--theme-text-secondary)' },
  emptyIcon: { fontSize: '64px', display: 'block', marginBottom: '16px', opacity: 0.5 },
  detectionGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
    gap: '16px', marginBottom: '24px',
  },
  detectionCard: {
    position: 'relative', background: 'var(--theme-card-background)',
    border: '1px solid var(--theme-border)', borderRadius: '12px',
    overflow: 'hidden', transition: 'all 0.2s ease',
  },
  detectionCardSelected: {
    borderColor: 'var(--theme-primary)',
    boxShadow: '0 0 0 2px var(--theme-primary)',
  },
  selectCheckboxWrap: {
    position: 'absolute', top: '8px', left: '8px', zIndex: 2,
    background: 'rgba(0,0,0,0.45)', borderRadius: '6px', padding: '4px',
    display: 'flex', cursor: 'pointer',
  },
  selectCheckbox: { width: '20px', height: '20px', cursor: 'pointer', accentColor: 'var(--theme-primary)' },
  detectionImage: { width: '100%', height: '200px', overflow: 'hidden', backgroundColor: '#000' },
  detectionImg: { width: '100%', height: '100%', objectFit: 'cover' },
  sightingPlaceholder: {
    width: '100%', height: '100%', display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', gap: '6px',
    padding: '12px', textAlign: 'center',
    background: 'var(--bg-input, rgba(127,127,127,0.08))',
    border: '1px dashed var(--border-input, rgba(127,127,127,0.35))',
    boxSizing: 'border-box',
  },
  sightingIcon: { fontSize: '28px', opacity: 0.55, lineHeight: 1 },
  sightingName: { fontSize: '14px', fontWeight: 700, color: 'var(--text-primary, inherit)' },
  sightingText: { fontSize: '13px', fontWeight: 600, color: 'var(--text-primary, inherit)' },
  sightingHint: { fontSize: '11px', opacity: 0.7, color: 'var(--text-secondary, inherit)', lineHeight: 1.3 },
  detectionContent: { padding: '16px' },
  detectionHeader: { display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px' },
  detectionIcon: { fontSize: '20px' },
  detectionBadge: {
    padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: '600',
    color: '#fff', textTransform: 'capitalize',
  },
  identifiedBadge: {
    padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: '600',
    backgroundColor: '#34C759', color: '#fff', marginLeft: 'auto',
  },
  unknownBadge: {
    padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: '600',
    backgroundColor: 'var(--theme-border)', color: 'var(--theme-text-secondary)', marginLeft: 'auto',
  },
  detectionName: { fontSize: '18px', fontWeight: '600', margin: '0 0 12px 0', color: 'var(--theme-text)' },
  detectionMeta: { display: 'flex', flexDirection: 'column', gap: '8px' },
  detectionActions: {
    display: 'flex', gap: '8px', marginTop: '16px', paddingTop: '16px',
    borderTop: '1px solid rgba(128, 128, 128, 0.2)', flexWrap: 'wrap',
  },
  detectionMetaItem: { display: 'flex', justifyContent: 'space-between', fontSize: '14px' },
  metaLabel: { color: 'var(--theme-text-secondary)', fontWeight: '500' },
  metaValue: { color: 'var(--theme-text)', fontWeight: '400' },
  pagination: { display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '16px', marginTop: '32px' },
  pageInfo: { fontSize: '16px', color: 'var(--theme-text-secondary)' },
  personCard: {
    background: 'var(--theme-card-background)', border: '1px solid var(--theme-border)',
    borderRadius: '12px', overflow: 'hidden', transition: 'all 0.2s ease',
    cursor: 'pointer', width: '100%', textAlign: 'left', padding: 0,
  },
  personCardContent: { padding: '16px' },
  personCardHeader: { display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px' },
  personIcon: { fontSize: '24px' },
  personCardName: { fontSize: '20px', fontWeight: '600', margin: '0 0 12px 0', color: 'var(--theme-text)' },
  personCardStats: { display: 'flex', gap: '16px', marginBottom: '12px' },
  personCardStat: { display: 'flex', alignItems: 'baseline', gap: '4px' },
  statNumber: { fontSize: '28px', fontWeight: '700', color: 'var(--theme-primary)' },
  statText: { fontSize: '14px', color: 'var(--theme-text-secondary)' },
  personCardMeta: { display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '12px' },
  viewDetailsHint: {
    fontSize: '14px', color: 'var(--theme-primary)', fontWeight: '500',
    paddingTop: '12px', borderTop: '1px solid var(--theme-border)',
  },
  personHeader: {
    display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px', flexWrap: 'wrap',
  },
  personActions: {
    display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px', flexWrap: 'wrap',
  },
  hintText: { fontSize: '13px', color: 'var(--theme-text-secondary)' },
  personTitle: { fontSize: '24px', fontWeight: '600', margin: 0, color: 'var(--theme-text)' },
  detectionCount: { fontSize: '16px', color: 'var(--theme-text-secondary)', marginLeft: 'auto' },
  peopleInfo: { marginBottom: '16px' },
  infoText: { fontSize: '14px', color: 'var(--theme-text-secondary)', margin: 0 },
  totalDetections: { marginLeft: '8px', opacity: 0.7 },
  // Sticky batch toolbar
  batchToolbar: {
    position: 'fixed', bottom: '24px', left: '50%', transform: 'translateX(-50%)',
    display: 'flex', alignItems: 'center', gap: '12px', zIndex: 50,
    background: 'var(--theme-card-background)', border: '1px solid var(--theme-border)',
    borderRadius: '999px', padding: '10px 20px', boxShadow: '0 6px 24px rgba(0,0,0,0.25)',
  },
  batchCount: { fontSize: '14px', fontWeight: '600', color: 'var(--theme-text)' },
  // Assign modal
  modalOverlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 100,
    display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px',
  },
  modal: {
    width: '100%', maxWidth: '420px', background: 'var(--theme-card-background)',
    border: '1px solid var(--theme-border)', borderRadius: '16px', padding: '24px',
    color: 'var(--theme-text)', boxShadow: '0 12px 48px rgba(0,0,0,0.35)',
  },
  modalTitle: { fontSize: '18px', fontWeight: '700', margin: '0 0 16px 0' },
  modalField: { marginBottom: '16px' },
  radioRow: { display: 'flex', alignItems: 'center', gap: '8px', fontSize: '15px', cursor: 'pointer' },
  select: {
    width: '100%', marginTop: '8px', padding: '10px', borderRadius: '8px',
    border: '1px solid var(--theme-border)', background: 'var(--theme-background)',
    color: 'var(--theme-text)', fontSize: '15px',
  },
  input: {
    width: '100%', marginTop: '8px', padding: '10px', borderRadius: '8px',
    border: '1px solid var(--theme-border)', background: 'var(--theme-background)',
    color: 'var(--theme-text)', fontSize: '15px', boxSizing: 'border-box',
  },
  modalActions: { display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '8px' },
};

export default DetectionsPage;
