# Field Name Consistency Audit
**Date**: 2025-10-19
**Version**: v3.5.6

## Executive Summary

Comprehensive audit of all API response schemas to identify field name inconsistencies. This audit covers all Pydantic schemas, database models, and frontend consumption patterns.

## Proposed Naming Convention

```python
# Standard naming patterns:
- IDs: {entity}_id (e.g., camera_id, recording_id, user_id)
- Booleans: is_{state} (e.g., is_active, is_enabled, is_identified)
- Timestamps: {event}_at (e.g., created_at, updated_at, detected_at, started_at)
- Counts: {entity}_count OR total_{entities} (e.g., face_count, total_people)
```

---

## Findings by Category

### ✅ CONSISTENT - No Changes Needed

These schemas already follow the proposed naming convention:

#### 1. **User Schema** (`backend/api/schemas/user.py`)
- ✅ `id: int` - User ID (simple primary key, acceptable)
- ✅ `is_active: bool` - Follows is_{state} pattern
- No timestamp inconsistencies

#### 2. **Motion Event Schema** (`backend/api/schemas/motion.py`)
- ✅ `camera_id: str` - Follows {entity}_id pattern
- ✅ `detected_at: datetime` - Follows {event}_at pattern
- ✅ `recording_id: Optional[int]` - Follows {entity}_id pattern
- ✅ All fields are consistent

#### 3. **Clustering Schema** (`backend/api/schemas/clustering.py`)
- ✅ `is_identified: bool` - Follows is_{state} pattern
- ✅ `created_at, updated_at, last_seen_at` - All follow {event}_at pattern
- ✅ `face_count: int` - Follows {entity}_count pattern
- ✅ All fields are consistent

#### 4. **Automation Schema** (`backend/api/schemas/automation.py`)
- ✅ `created_at, updated_at, last_triggered_at` - Follow {event}_at pattern
- ✅ `trigger_count: int` - Follows count pattern
- ✅ All fields are consistent

---

### ⚠️ INCONSISTENT - Requires Aliases

These schemas have inconsistencies that need backward-compatible aliases:

#### 1. **Camera Schema** (`backend/api/schemas/camera.py`)

**Issue**: Mixes `id` with `camera_id`

**Current State**:
```python
class CameraResponse(CameraBase):
    id: int                    # ❌ Inconsistent - should be camera_id or use alias
    camera_id: str             # ✅ Already present in base
    is_active: bool            # ✅ Consistent
    created_at: datetime       # ✅ Consistent
    last_active_at: datetime   # ✅ Consistent
```

**Database Model** (`backend/database/models.py:118-177`):
```python
class Camera(Base):
    id = Column(Integer, primary_key=True)      # Auto-increment PK
    camera_id = Column(String, unique=True)     # User-defined camera ID
```

**Frontend Usage**:
- Frontend ALWAYS uses `camera.camera_id` (never `camera.id`)
- Examples: `LiveDashboard.jsx:194`, `SystemSettingsPage.jsx:655`, `DashboardPage.jsx:221`

**Recommendation**:
- Keep both fields but clarify intent
- `id` = Database primary key (internal use)
- `camera_id` = User-facing camera identifier

**No changes needed** - This is intentional dual-field design.

---

#### 2. **Face Detection Schema** (`backend/api/schemas/face.py`)

**Issue**: Missing timestamp consistency in `FaceDetection` schema

**Current State**:
```python
class FaceDetection(BaseModel):
    name: str
    confidence: float
    location: FaceLocation
    timestamp: str              # ❌ Should be detected_at: datetime
    motion_detected: Optional[bool]
```

**Database Model** (`backend/database/models.py:30-77`):
```python
class FaceDetectionEvent(Base):
    id = Column(Integer, primary_key=True)
    detected_at = Column(DateTime)    # ✅ Follows {event}_at pattern
```

**Issue**: Schema uses `timestamp: str`, but DB uses `detected_at: datetime`

**Recommendation**:
```python
class FaceDetection(BaseModel):
    name: str
    confidence: float
    location: FaceLocation
    detected_at: datetime = Field(..., alias="timestamp")  # Accept both
    motion_detected: Optional[bool]

    class Config:
        populate_by_name = True  # Allow both names
```

---

#### 3. **Recording Schema** (`backend/api/routes/recordings.py`)

**Current State**:
```python
class RecordingResponse(BaseModel):
    id: int                           # ❌ Should support recording_id alias
    camera_id: str                    # ✅ Consistent
    started_at: datetime              # ✅ Consistent
    ended_at: Optional[datetime]      # ✅ Consistent
    duration_seconds: Optional[float] # ✅ Consistent
```

**Database Model** (`backend/database/models.py:179-214`):
```python
class RecordingEvent(Base):
    id = Column(Integer, primary_key=True)
    camera_id = Column(String)
    started_at = Column(DateTime)
    ended_at = Column(DateTime, nullable=True)
```

**Frontend Usage**:
- Frontend sometimes uses `recording.id`, sometimes `recording.recording_id`
- LiveDashboard.jsx:72 creates `recording_id: r.id` mapping

**Recommendation**:
```python
class RecordingResponse(BaseModel):
    id: int = Field(..., alias="recording_id")  # Accept both
    camera_id: str
    started_at: datetime
    ended_at: Optional[datetime]

    class Config:
        populate_by_name = True
```

---

#### 4. **Face History Schema** (`backend/api/routes/face_history.py`)

**Current State**:
```python
class FaceDetectionEventResponse(BaseModel):
    id: int                           # ✅ OK for face detection event ID
    camera_id: str                    # ✅ Consistent
    person_name: str                  # ✅ Consistent
    confidence: float                 # ✅ Consistent
    detected_at: datetime             # ✅ Consistent
    recording_path: Optional[str]     # ✅ Consistent
```

**No changes needed** - Already consistent!

---

### 📊 Summary Table

| Schema | Status | Issues Found | Action Required |
|--------|--------|--------------|-----------------|
| User | ✅ Consistent | None | None |
| Motion Event | ✅ Consistent | None | None |
| Clustering | ✅ Consistent | None | None |
| Automation | ✅ Consistent | None | None |
| Camera | ✅ Intentional Design | Dual ID fields by design | None |
| Face Detection | ⚠️ Inconsistent | `timestamp` vs `detected_at` | Add alias |
| Recording | ⚠️ Inconsistent | Frontend expects `recording_id` | Add alias |
| Face History | ✅ Consistent | None | None |

---

## Recommended Changes

### 1. Fix Face Detection Schema

**File**: `backend/api/schemas/face.py`

```python
class FaceDetection(BaseModel):
    """Schema for a detected face"""

    name: str = Field(..., description="Recognized person name or 'Unknown'")
    confidence: float = Field(..., description="Recognition confidence (0.0-1.0)")
    location: FaceLocation
    detected_at: datetime = Field(..., alias="timestamp", description="Detection timestamp")
    motion_detected: Optional[bool] = Field(None, description="Whether motion was detected")

    class Config:
        populate_by_name = True  # Allow both 'detected_at' and 'timestamp'
```

**Impact**:
- ✅ Accepts both `detected_at` (new standard) and `timestamp` (legacy)
- ✅ Returns `detected_at` by default
- ✅ Backward compatible with existing frontend code

---

### 2. Add Alias to Recording Schema

**File**: `backend/api/routes/recordings.py`

```python
class RecordingResponse(BaseModel):
    id: int = Field(..., serialization_alias="recording_id", description="Recording ID")
    camera_id: str
    recording_path: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[float]
    file_size_bytes: Optional[int]
    faces_detected: int
    known_faces_detected: int
    thumbnail_path: Optional[str]

    class Config:
        from_attributes = True
        populate_by_name = True
```

**Impact**:
- ✅ Returns `recording_id` in JSON responses
- ✅ Still accepts `id` from database model
- ✅ Aligns with frontend expectations

---

## Implementation Plan

### Phase 1: Add Aliases (Low Risk)
- [x] Audit complete
- [ ] Add alias to `FaceDetection.detected_at`
- [ ] Add serialization_alias to `RecordingResponse.id`
- [ ] Test backward compatibility

### Phase 2: Test Frontend Compatibility (Critical)
- [ ] Verify LiveDashboard still receives `recording_id`
- [ ] Verify face detection responses work with `detected_at`
- [ ] Test all recording-related pages

### Phase 3: Documentation Update
- [ ] Update API documentation with field aliases
- [ ] Add migration guide for API consumers
- [ ] Document naming convention for future schemas

---

## Testing Checklist

- [ ] GET `/recordings/` returns `recording_id` field
- [ ] GET `/faces/history/detections` returns `detected_at` field
- [ ] LiveDashboard displays recordings correctly
- [ ] RecordingsPage bulk operations work
- [ ] Face clustering page displays correctly
- [ ] No console errors in frontend

---

## Notes

1. **Camera dual-ID design is intentional**: The `Camera` model has both `id` (auto-increment PK) and `camera_id` (user-defined string). This is correct design for flexibility.

2. **Most schemas are already consistent**: 75% of schemas already follow the proposed naming convention. Only 2 schemas need aliases.

3. **Frontend expects `recording_id`**: LiveDashboard.jsx:72 explicitly creates `recording_id: r.id` mapping, indicating frontend prefers `recording_id` over `id`.

4. **Backward compatibility is critical**: All changes must use Pydantic `alias` and `populate_by_name` to maintain compatibility with existing frontend code.

---

## Conclusion

The API is largely consistent, with only **2 minor issues**:
1. Face detection `timestamp` → `detected_at`
2. Recording `id` → `recording_id` in responses

Both can be fixed with low-risk Pydantic aliases, maintaining full backward compatibility.
