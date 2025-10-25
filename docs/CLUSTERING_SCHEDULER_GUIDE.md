# Face Clustering Scheduler Guide

## Overview

The **Clustering Scheduler** is an automated background service that periodically groups unknown faces into clusters, making it easier to identify frequent visitors without manual intervention.

**Location**: `backend/core/clustering_scheduler.py`

---

## How It Works

1. **Runs periodically** (default: every 60 minutes)
2. **Checks threshold** - Only runs if there are enough unknown faces (default: 10+)
3. **Groups similar faces** using DBSCAN algorithm
4. **Tracks statistics** - Success rate, clusters created, faces processed

---

## Configuration

### Default Settings

```python
auto_cluster_enabled = True           # Auto-clustering is enabled
auto_cluster_interval_minutes = 60   # Runs every hour
min_faces_threshold = 10             # Requires 10+ unknown faces
eps = 0.5                            # DBSCAN distance threshold
min_samples = 2                      # Minimum faces per cluster
```

### API Endpoints

#### Get Scheduler Status

```bash
GET /api/clusters/scheduler/status
```

**Response**:
```json
{
  "auto_cluster_enabled": true,
  "interval_minutes": 60,
  "min_faces_threshold": 10,
  "last_run_time": "2025-10-24T10:30:00",
  "is_running": true,
  "statistics": {
    "total_runs": 15,
    "successful_runs": 14,
    "failed_runs": 1,
    "total_clusters_created": 42,
    "total_faces_clustered": 385,
    "last_run_success": true
  }
}
```

#### Manually Trigger Clustering

```bash
POST /api/clusters/scheduler/trigger
```

**Use Case**: Force clustering immediately, bypassing the interval timer.

**Response**:
```json
{
  "success": true,
  "message": "Manual clustering triggered",
  "clusters_created": 3,
  "faces_clustered": 15,
  "clustering_time": 2.45
}
```

#### Update Scheduler Settings

```bash
POST /api/clusters/scheduler/settings?auto_enabled=true&interval_minutes=30&min_faces_threshold=5
```

**Parameters**:
- `auto_enabled` (bool): Enable/disable auto-clustering
- `interval_minutes` (int): Minutes between runs (minimum: 5)
- `min_faces_threshold` (int): Minimum unknown faces to trigger clustering (minimum: 1)

**Response**:
```json
{
  "success": true,
  "settings": {
    "auto_cluster_enabled": true,
    "interval_minutes": 30,
    "min_faces_threshold": 5
  }
}
```

---

## Usage Examples

### Using curl

```bash
# Check status
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/clusters/scheduler/status

# Trigger manual clustering
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/clusters/scheduler/trigger

# Update settings (run every 30 minutes)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/clusters/scheduler/settings?interval_minutes=30&min_faces_threshold=5"

# Disable auto-clustering
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/clusters/scheduler/settings?auto_enabled=false"
```

### Using JavaScript

```javascript
// Get scheduler status
const status = await fetch('/api/clusters/scheduler/status', {
  headers: { 'Authorization': `Bearer ${token}` }
}).then(r => r.json());

console.log(`Last run: ${status.last_run_time}`);
console.log(`Total clusters created: ${status.statistics.total_clusters_created}`);

// Trigger manual clustering
const result = await fetch('/api/clusters/scheduler/trigger', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` }
}).then(r => r.json());

console.log(`Created ${result.clusters_created} new clusters`);

// Update settings
await fetch('/api/clusters/scheduler/settings?interval_minutes=120', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` }
});
```

---

## When Clustering Runs

The scheduler checks if clustering should run based on:

1. **Auto-clustering is enabled** (`auto_cluster_enabled = true`)
2. **Enough unknown faces exist** (>= `min_faces_threshold`)
3. **Interval has elapsed** (>= `interval_minutes` since last run)

**Example Timeline**:
```
10:00 AM - Scheduler starts
10:00 AM - Check: Only 5 unknown faces (< threshold of 10) → Skip
11:00 AM - Check: 15 unknown faces (>= 10) → Run clustering
11:02 AM - Clustering complete: 3 clusters created, 12 faces grouped
12:00 PM - Check: Only 3 unknown faces left → Skip
1:00 PM - Check: 12 new unknown faces → Run clustering
```

---

## Startup Integration

The scheduler starts automatically when the application launches.

**Location**: `backend/main.py`

```python
from backend.core.clustering_scheduler import get_clustering_scheduler

@app.on_event("startup")
async def startup_event():
    # Start clustering scheduler
    scheduler = get_clustering_scheduler()
    await scheduler.start()
    logger.info("Clustering scheduler started")

@app.on_event("shutdown")
async def shutdown_event():
    # Stop clustering scheduler
    scheduler = get_clustering_scheduler()
    await scheduler.stop()
    logger.info("Clustering scheduler stopped")
```

---

## Performance Considerations

### For Small Systems (1-2 cameras)
```python
auto_cluster_interval_minutes = 120  # Every 2 hours
min_faces_threshold = 20             # Wait for more faces
```

**Rationale**: Reduces CPU usage, only clusters when there's enough data for meaningful groups.

### For Large Systems (5+ cameras)
```python
auto_cluster_interval_minutes = 30   # Every 30 minutes
min_faces_threshold = 5              # More frequent clustering
```

**Rationale**: Keeps unknown face count manageable, faster identification of frequent visitors.

### For High-Traffic Areas
```python
auto_cluster_interval_minutes = 15   # Every 15 minutes
min_faces_threshold = 3              # Very frequent clustering
```

**Rationale**: Real-time grouping for busy locations like retail stores or offices.

---

## Monitoring

### Check Scheduler Health

```bash
# View statistics
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/clusters/scheduler/status | jq '.statistics'

# Expected output:
{
  "total_runs": 48,
  "successful_runs": 47,
  "failed_runs": 1,
  "total_clusters_created": 156,
  "total_faces_clustered": 1,234,
  "last_run_success": true
}
```

### Success Rate

Calculate scheduler reliability:
```
Success Rate = (successful_runs / total_runs) * 100
             = (47 / 48) * 100
             = 97.9%
```

**Healthy system**: >95% success rate

**Investigate if**: <90% success rate (check logs for errors)

---

## Troubleshooting

### Scheduler Not Running

**Check Status**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/clusters/scheduler/status | jq '.is_running'
```

**Expected**: `true`

**If `false`**: Restart the application or manually start scheduler via API.

---

### Clustering Never Triggers

**Possible Causes**:
1. **Not enough unknown faces**: Check `total_unknown_faces` in statistics
2. **Auto-clustering disabled**: Verify `auto_cluster_enabled = true`
3. **Threshold too high**: Lower `min_faces_threshold`

**Solution**:
```bash
# Lower threshold to 1 for testing
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/clusters/scheduler/settings?min_faces_threshold=1"

# Manually trigger to test
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/clusters/scheduler/trigger
```

---

### High CPU Usage

**Cause**: Clustering runs too frequently with too many faces.

**Solution**: Increase interval and threshold
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/clusters/scheduler/settings?interval_minutes=120&min_faces_threshold=50"
```

---

### Clustering Failures

**Check Logs**:
```bash
docker logs openeye | grep "clustering"
# or
tail -f opencv_surveillance/logs/app.log | grep clustering
```

**Common Errors**:
- **No face encodings found**: No unknown faces have valid encodings
- **DBSCAN error**: Invalid `eps` or `min_samples` parameters
- **Database locked**: Multiple clustering processes running simultaneously

---

## Future UI Integration

**Planned for v3.6.0+**: Web UI controls for scheduler

**Mockup**:
```
┌─────────────────────────────────────────┐
│ ⚙️ Clustering Scheduler Settings        │
├─────────────────────────────────────────┤
│                                         │
│ [✓] Enable automatic clustering        │
│                                         │
│ Run every: [60] minutes                │
│                                         │
│ Minimum unknown faces: [10]            │
│                                         │
│ DBSCAN eps: [0.5] (0.4-0.6 typical)   │
│ DBSCAN min_samples: [2]                │
│                                         │
│ Last run: 10 minutes ago               │
│ Status: ✓ Running                      │
│                                         │
│ [Trigger Now] [Save Settings]         │
└─────────────────────────────────────────┘
```

**Implementation**: Add to `FaceClusteringPage.jsx` with API calls to `/api/clusters/scheduler/*` endpoints.

---

## Best Practices

### 1. Start Conservative
```python
interval_minutes = 60
min_faces_threshold = 10
```
Then adjust based on usage patterns.

### 2. Monitor Success Rate
Check statistics weekly to ensure >95% success rate.

### 3. Balance Frequency vs. Performance
- **More frequent** = Faster identification, higher CPU usage
- **Less frequent** = Lower CPU usage, slower identification

### 4. Adjust for Business Hours
Use automation rules (future feature) to:
- **Cluster every 15 min during business hours** (9am-5pm)
- **Cluster every 2 hours during off-hours** (5pm-9am)

### 5. Test Before Production
```bash
# Test with minimal threshold
curl -X POST ... "?min_faces_threshold=1"

# Trigger manually
curl -X POST ... /trigger

# Verify clusters created
curl ... /clusters/statistics/summary
```

---

## See Also

- [Face Clustering Implementation](../docs/archived-releases/FACE_CLUSTERING_IMPLEMENTATION_v3.6.0.md)
- [API Documentation](API_DOCUMENTATION.md#face-clustering)
- [User Guide](USER_GUIDE.md#face-clustering)

---

**Last Updated**: 2025-10-24
**Version**: 3.5.7
