# Motion Detection Event Model Addition
**Date**: October 12, 2025

## Problem
The system currently has:
- `FaceDetectionEvent` - Tracks when faces are detected
- `RecordingEvent` - Tracks video recordings

But it's missing:
- `MotionDetectionEvent` - Tracks motion events (with or without faces)

This means the timeline cannot show motion-only events where no face was detected.

## Solution

### 1. Add MotionDetectionEvent Model

Add to `backend/database/models.py`:

```python
class MotionDetectionEvent(Base):
    """
    Motion detection event model
    Tracks all motion events, including those without face detection
    """
    
    __tablename__ = "motion_detection_events"
    
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Motion details
    motion_area = Column(Integer)  # Size of motion area in pixels
    motion_percentage = Column(Float)  # Percentage of frame with motion
    contour_count = Column(Integer)  # Number of motion contours detected
    
    # Snapshot information
    snapshot_path = Column(String, nullable=True)
    frame_width = Column(Integer, nullable=True)
    frame_height = Column(Integer, nullable=True)
    
    # Recording linkage
    recording_id = Column(Integer, ForeignKey('recording_events.id'), nullable=True, index=True)
    recording_path = Column(String, nullable=True)
    
    # Face detection context
    faces_detected = Column(Integer, default=0)  # How many faces were in this motion event
    face_detection_ids = Column(String, nullable=True)  # JSON array of face detection IDs
    
    # Motion zone information (which zones triggered)
    triggered_zones = Column(String, nullable=True)  # JSON array of zone indices
    
    def __repr__(self):
        return f"<MotionDetection(camera={self.camera_id}, area={self.motion_area}, time={self.detected_at})>"
```

### 2. Create Database Migration

Create `backend/database/migrations/add_motion_detection_events.py`:

```python
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Database migration: Add motion_detection_events table
Tracks all motion events including those without faces
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from sqlalchemy import create_engine, text
from backend.database.session import DATABASE_URL

def upgrade():
    """Add motion_detection_events table"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Create motion_detection_events table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS motion_detection_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                
                motion_area INTEGER,
                motion_percentage REAL,
                contour_count INTEGER,
                
                snapshot_path TEXT,
                frame_width INTEGER,
                frame_height INTEGER,
                
                recording_id INTEGER,
                recording_path TEXT,
                
                faces_detected INTEGER DEFAULT 0,
                face_detection_ids TEXT,
                
                triggered_zones TEXT,
                
                FOREIGN KEY (recording_id) REFERENCES recording_events (id)
            )
        """))
        
        # Create indexes
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_motion_camera_id 
            ON motion_detection_events(camera_id)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_motion_detected_at 
            ON motion_detection_events(detected_at)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_motion_recording_id 
            ON motion_detection_events(recording_id)
        """))
        
        conn.commit()
        print("✅ motion_detection_events table created successfully")

def downgrade():
    """Remove motion_detection_events table"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS motion_detection_events"))
        conn.commit()
        print("✅ motion_detection_events table dropped")

if __name__ == "__main__":
    print("Running migration: Add motion_detection_events table")
    upgrade()
    print("Migration complete!")
```

### 3. Create Motion Events Schema

Create `backend/api/schemas/motion.py`:

```python
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Pydantic schemas for Motion Detection Events
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class MotionEventBase(BaseModel):
    """Base motion event schema"""
    camera_id: str
    motion_area: Optional[int] = None
    motion_percentage: Optional[float] = None
    contour_count: Optional[int] = None
    snapshot_path: Optional[str] = None
    recording_path: Optional[str] = None
    faces_detected: int = 0
    triggered_zones: Optional[str] = None


class MotionEventCreate(MotionEventBase):
    """Schema for creating motion event"""
    pass


class MotionEventResponse(MotionEventBase):
    """Schema for motion event response"""
    id: int
    detected_at: datetime
    recording_id: Optional[int] = None
    frame_width: Optional[int] = None
    frame_height: Optional[int] = None
    face_detection_ids: Optional[str] = None
    
    class Config:
        from_attributes = True


class MotionEventListResponse(BaseModel):
    """Wrapped response for motion events list"""
    events: List[MotionEventResponse]
    total: int
    limit: int = 100
    offset: int = 0
```

### 4. Create Motion Events API Endpoints

Create `backend/api/routes/motion_events.py`:

```python
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
API routes for Motion Detection Events
Separate from face detection events
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from backend.database.session import get_db
from backend.database import models
from backend.api.schemas.motion import (
    MotionEventResponse,
    MotionEventListResponse,
    MotionEventCreate
)

router = APIRouter()


@router.get("/motion-events/", response_model=MotionEventListResponse)
def list_motion_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    camera_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    has_faces: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Get list of motion detection events with pagination
    
    - **skip**: Number of events to skip (default: 0)
    - **limit**: Maximum events to return (default: 100, max: 500)
    - **camera_id**: Filter by specific camera
    - **start_date**: Filter events after this date
    - **end_date**: Filter events before this date
    - **has_faces**: Filter by whether faces were detected (True/False)
    """
    query = db.query(models.MotionDetectionEvent)
    
    # Apply filters
    if camera_id:
        query = query.filter(models.MotionDetectionEvent.camera_id == camera_id)
    
    if start_date:
        query = query.filter(models.MotionDetectionEvent.detected_at >= start_date)
    
    if end_date:
        query = query.filter(models.MotionDetectionEvent.detected_at <= end_date)
    
    if has_faces is not None:
        if has_faces:
            query = query.filter(models.MotionDetectionEvent.faces_detected > 0)
        else:
            query = query.filter(models.MotionDetectionEvent.faces_detected == 0)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and order
    events = query.order_by(
        models.MotionDetectionEvent.detected_at.desc()
    ).offset(skip).limit(limit).all()
    
    return MotionEventListResponse(
        events=events,
        total=total,
        limit=limit,
        offset=skip
    )


@router.get("/motion-events/{event_id}", response_model=MotionEventResponse)
def get_motion_event(event_id: int, db: Session = Depends(get_db)):
    """Get specific motion event by ID"""
    event = db.query(models.MotionDetectionEvent).filter(
        models.MotionDetectionEvent.id == event_id
    ).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Motion event not found")
    
    return event


@router.delete("/motion-events/{event_id}")
def delete_motion_event(event_id: int, db: Session = Depends(get_db)):
    """Delete motion event and associated snapshot"""
    event = db.query(models.MotionDetectionEvent).filter(
        models.MotionDetectionEvent.id == event_id
    ).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Motion event not found")
    
    # Delete snapshot file if exists
    if event.snapshot_path:
        from pathlib import Path
        snapshot_file = Path(event.snapshot_path)
        if snapshot_file.exists():
            try:
                snapshot_file.unlink()
            except Exception as e:
                print(f"Warning: Could not delete snapshot file: {e}")
    
    # Delete from database
    db.delete(event)
    db.commit()
    
    return {"message": "Motion event deleted successfully", "id": event_id}


@router.post("/motion-events/cleanup")
def cleanup_old_motion_events(
    days: int = Query(30, ge=1, le=365),
    camera_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Clean up motion events older than specified days
    
    - **days**: Delete events older than this many days (default: 30)
    - **camera_id**: Optionally limit to specific camera
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(models.MotionDetectionEvent).filter(
        models.MotionDetectionEvent.detected_at < cutoff_date
    )
    
    if camera_id:
        query = query.filter(models.MotionDetectionEvent.camera_id == camera_id)
    
    # Get events to delete (for file cleanup)
    events_to_delete = query.all()
    
    # Delete snapshot files
    deleted_snapshots = 0
    for event in events_to_delete:
        if event.snapshot_path:
            from pathlib import Path
            snapshot_file = Path(event.snapshot_path)
            if snapshot_file.exists():
                try:
                    snapshot_file.unlink()
                    deleted_snapshots += 1
                except Exception as e:
                    print(f"Warning: Could not delete snapshot {event.snapshot_path}: {e}")
    
    # Delete from database
    deleted_count = query.delete()
    db.commit()
    
    return {
        "message": f"Cleaned up {deleted_count} motion events older than {days} days",
        "deleted_events": deleted_count,
        "deleted_snapshots": deleted_snapshots,
        "cutoff_date": cutoff_date.isoformat()
    }


@router.get("/motion-events/statistics/summary")
def get_motion_statistics(
    days: int = Query(7, ge=1, le=365),
    camera_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get motion detection statistics
    
    - **days**: Statistics for last N days (default: 7)
    - **camera_id**: Optionally filter by camera
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(models.MotionDetectionEvent).filter(
        models.MotionDetectionEvent.detected_at >= cutoff_date
    )
    
    if camera_id:
        query = query.filter(models.MotionDetectionEvent.camera_id == camera_id)
    
    events = query.all()
    
    total_events = len(events)
    events_with_faces = len([e for e in events if e.faces_detected > 0])
    events_without_faces = total_events - events_with_faces
    
    # Calculate per-camera breakdown
    camera_breakdown = {}
    for event in events:
        if event.camera_id not in camera_breakdown:
            camera_breakdown[event.camera_id] = {
                "total": 0,
                "with_faces": 0,
                "without_faces": 0
            }
        camera_breakdown[event.camera_id]["total"] += 1
        if event.faces_detected > 0:
            camera_breakdown[event.camera_id]["with_faces"] += 1
        else:
            camera_breakdown[event.camera_id]["without_faces"] += 1
    
    return {
        "period_days": days,
        "total_motion_events": total_events,
        "events_with_faces": events_with_faces,
        "events_without_faces": events_without_faces,
        "camera_breakdown": camera_breakdown,
        "start_date": cutoff_date.isoformat(),
        "end_date": datetime.utcnow().isoformat()
    }
```

### 5. Register Routes in main.py

Add to `backend/main.py`:

```python
from backend.api.routes import (
    users,
    cameras,
    faces,
    face_history,
    alerts,
    integrations,
    recordings,
    analytics,
    discovery,
    setup,
    websockets,
    settings,
    motion_events,  # NEW
)

# ... later in the file ...

app.include_router(
    motion_events.router,
    prefix="/api",
    tags=["Motion Detection Events"]
)
```

### 6. Update RecordingsPage to Use Motion Events

The RecordingsPage should now use the correct endpoint:

```javascript
const loadSnapshots = async () => {
  try {
    // Load motion events (includes events with and without faces)
    const response = await apiClient.get('/motion-events/?limit=100');
    // Handle wrapped response
    const events = response.data.events || response.data;
    const snapshotsData = Array.isArray(events) ? events : [];
    // Filter only events that have a snapshot_path
    const filtered = snapshotsData.filter(event => event.snapshot_path);
    setSnapshots(filtered);
  } catch (err) {
    console.error('Error loading snapshots:', err);
    setSnapshots([]);
  }
};

const deleteSnapshot = async (eventId) => {
  if (!window.confirm('Are you sure you want to delete this snapshot?')) {
    return;
  }
  
  try {
    await apiClient.delete(`/motion-events/${eventId}`);
    loadSnapshots();
  } catch (err) {
    console.error('Error deleting snapshot:', err);
    alert('Failed to delete snapshot');
  }
};
```

## Timeline View Logic

For a complete timeline showing ALL events:

1. **Motion-only events** (no faces): Pull from `/api/motion-events/?has_faces=false`
2. **Face detection events**: Pull from `/api/history/detections`
3. **Recording events**: Pull from `/api/recordings/`

Merge and sort by timestamp to create unified timeline.

## Implementation Priority

1. ✅ Create migration script
2. ✅ Add MotionDetectionEvent model
3. ✅ Create motion events API endpoints
4. ✅ Update RecordingsPage frontend
5. ⏳ Run migration to create table
6. ⏳ Update motion detection code to log events
7. ⏳ Test timeline with mixed events

## Benefits

- ✅ Separate tracking of motion vs face detection
- ✅ Can show timeline of all activity (not just faces)
- ✅ Better analytics (motion events with/without faces)
- ✅ Proper snapshot management
- ✅ Cleanup capabilities for old motion events
