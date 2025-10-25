# OpenEye API Reference Guide
**Version**: 3.5.3  
**Last Updated**: 2025-10-18

## Table of Contents
1. [Authentication](#authentication)
2. [Cameras](#cameras)
3. [Recordings](#recordings)
4. [Face Recognition](#face-recognition)
5. [Detection History](#detection-history)
6. [Settings](#settings)
7. [Alerts](#alerts)
8. [System](#system)
9. [Data Models](#data-models)
10. [Error Handling](#error-handling)

---

## Authentication

### POST /api/token
Generate JWT access token (OAuth2 standard)

**Request**:
```http
POST /api/token
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Usage**:
```javascript
const response = await axios.post('/api/token', new URLSearchParams({
  username: 'admin',
  password: 'admin'
}));
localStorage.setItem('token', response.data.access_token);
```

### GET /api/users/me
Get current authenticated user information

**Headers**: `Authorization: Bearer {token}`

**Response**:
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "is_active": true,
  "role": "admin",
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

## Cameras

### GET /api/cameras/
List all cameras with pagination

**Headers**: `Authorization: Bearer {token}`

**Query Parameters**:
- `skip` (int, default=0): Number of records to skip
- `limit` (int, default=100): Maximum records to return
- `active_only` (bool, default=false): Filter active cameras only

**Response**:
```json
{
  "cameras": [
    {
      "camera_id": "front-door",
      "name": "Front Door",
      "camera_type": "rtsp",
      "source": "rtsp://192.168.1.100:554/stream",
      "is_active": true,
      "resolution": "1920x1080",
      "fps_target": 30,
      "face_detection_enabled": true,
      "motion_detection_enabled": true,
      "recording_enabled": true,
      "created_at": "2025-01-01T00:00:00Z",
      "last_active_at": "2025-01-10T12:30:00Z"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 100
}
```

### POST /api/cameras/
Create a new camera

**Headers**: `Authorization: Bearer {token}`

**Request Body**:
```json
{
  "camera_id": "backyard",
  "name": "Backyard Camera",
  "camera_type": "rtsp",
  "source": "rtsp://192.168.1.101:554/stream",
  "face_detection_enabled": true,
  "motion_detection_enabled": true,
  "recording_enabled": true,
  "fps_target": 15,
  "resolution": "1280x720"
}
```

**Response**: Camera object (201 Created)

### GET /api/cameras/{camera_id}
Get specific camera details

**Headers**: `Authorization: Bearer {token}`

**Response**: Single camera object

### PATCH /api/cameras/{camera_id}
Update camera settings

**Headers**: `Authorization: Bearer {token}`

**Request Body** (partial update supported):
```json
{
  "is_active": true,
  "motion_detection_enabled": false,
  "fps_target": 20
}
```

**Response**: Updated camera object

### DELETE /api/cameras/{camera_id}
Delete camera

**Headers**: `Authorization: Bearer {token}`

**Response**: 204 No Content

### GET /api/cameras/{camera_id}/stream
Get MJPEG video stream

**Headers**: `Authorization: Bearer {token}`

**Response**: Multipart JPEG stream

**Usage**:
```html
<img src="/api/cameras/front-door/stream" alt="Live feed" />
```

### GET /api/cameras/{camera_id}/snapshot
Get single frame snapshot

**Headers**: `Authorization: Bearer {token}`

**Response**: JPEG image

---

## Recordings

### GET /api/recordings/
List all recordings

**Headers**: `Authorization: Bearer {token}`

**Query Parameters**:
- `camera_id` (str, optional): Filter by camera
- `start_date` (ISO datetime, optional): Filter from date
- `end_date` (ISO datetime, optional): Filter to date
- `has_faces` (bool, optional): Filter recordings with face detections
- `limit` (int, default=50, max=200): Maximum records

**Response**:
```json
[
  {
    "id": 123,
    "camera_id": "front-door",
    "recording_path": "/recordings/front-door_2025-01-10_12-30-00.mp4",
    "started_at": "2025-01-10T12:30:00Z",
    "ended_at": "2025-01-10T12:35:00Z",
    "duration_seconds": 300.5,
    "file_size_bytes": 15728640,
    "motion_detected": true,
    "faces_detected": 2,
    "known_faces_detected": 1,
    "thumbnail_path": "/snapshots/front-door_2025-01-10_12-30-00.jpg"
  }
]
```

### GET /api/recordings/{recording_id}
Get specific recording details

**Headers**: `Authorization: Bearer {token}`

**Response**: Single recording object

### DELETE /api/recordings/{recording_id}
Delete recording file and database entry

**Headers**: `Authorization: Bearer {token}`

**Response**: 204 No Content

### GET /api/recordings/{recording_id}/download
Download recording file

**Headers**: `Authorization: Bearer {token}`

**Response**: Video file (MP4)

---

## Face Recognition

### GET /api/faces/people
List all enrolled people

**Headers**: `Authorization: Bearer {token}`

**Response**:
```json
[
  {
    "name": "John Doe",
    "photo_count": 5,
    "created_at": "2025-01-01T00:00:00Z",
    "last_seen": "2025-01-10T12:30:00Z"
  }
]
```

### POST /api/faces/people
Create new person

**Headers**: `Authorization: Bearer {token}`

**Request Body**:
```json
{
  "name": "Jane Smith"
}
```

**Response**: Person object (201 Created)

### GET /api/faces/people/{name}
Get person details

**Headers**: `Authorization: Bearer {token}`

**Response**: Person object with photo list

### DELETE /api/faces/people/{name}
Delete person and all their photos

**Headers**: `Authorization: Bearer {token}`

**Response**: 204 No Content

### POST /api/faces/people/{name}/photos
Upload training photos

**Headers**: 
- `Authorization: Bearer {token}`
- `Content-Type: multipart/form-data`

**Request Body**: Form data with `files` field (multiple files)

**Response**:
```json
{
  "message": "Uploaded 3 photos for John Doe",
  "success_count": 3,
  "failed_count": 0
}
```

### POST /api/faces/train
Train face recognition model

**Headers**: `Authorization: Bearer {token}`

**Request Body**: `{}` (empty)

**Response**:
```json
{
  "message": "Model trained successfully with 15 faces",
  "people_count": 3,
  "total_images": 15,
  "training_time_seconds": 2.5
}
```

### GET /api/faces/statistics
Get face recognition statistics

**Headers**: `Authorization: Bearer {token}`

**Response**:
```json
{
  "total_people": 3,
  "total_photos": 15,
  "total_detections_today": 42,
  "most_detected_person": "John Doe",
  "model_trained": true,
  "last_trained_at": "2025-01-10T10:00:00Z"
}
```

---

## Detection History

### GET /api/history/detections
Get face detection history

**Headers**: `Authorization: Bearer {token}`

**Query Parameters**:
- `camera_id` (str, optional): Filter by camera
- `person_name` (str, optional): Filter by person
- `hours` (int, default=24): Hours to look back
- `limit` (int, default=50, max=500): Maximum results

**Response**:
```json
[
  {
    "id": 456,
    "camera_id": "front-door",
    "person_name": "John Doe",
    "confidence": 0.95,
    "detected_at": "2025-01-10T12:30:15Z",
    "location": {
      "top": 100,
      "right": 300,
      "bottom": 400,
      "left": 200
    },
    "motion_detected": true,
    "recording_path": "/recordings/front-door_2025-01-10_12-30-00.mp4",
    "recording_id": 123
  }
]
```

### GET /api/history/statistics
Get detection statistics

**Headers**: `Authorization: Bearer {token}`

**Query Parameters**:
- `days` (int, default=7): Days to analyze

**Response**:
```json
{
  "total_detections": 250,
  "unique_people": 3,
  "most_detected_person": "John Doe",
  "time_period_days": 7,
  "detections_by_person": {
    "John Doe": 150,
    "Jane Smith": 75,
    "Unknown": 25
  }
}
```

---

## Settings

### GET /api/settings
Get all system settings

**Headers**: `Authorization: Bearer {token}`

**Response**:
```json
{
  "recordings_path": "/data/recordings",
  "faces_path": "/data/faces",
  "display_mode": "grid",
  "cycle_interval": 5,
  "max_recording_duration": 300,
  "theme": "dark"
}
```

### PATCH /api/settings
Update system settings (bulk update)

**Headers**: `Authorization: Bearer {token}`

**Request Body** (partial update supported):
```json
{
  "display_mode": "cycle",
  "cycle_interval": 10,
  "theme": "aqua-security"
}
```

**Response**: Updated settings object

### POST /api/settings/validate-path
Validate and create directory path

**Headers**: `Authorization: Bearer {token}`

**Request Body**:
```json
{
  "path": "/data/recordings",
  "create_if_missing": true
}
```

**Response**:
```json
{
  "exists": true,
  "is_directory": true,
  "writable": true,
  "readable": true,
  "absolute_path": "/data/recordings"
}
```

---

## Alerts

### GET /api/alerts/config
Get alert configuration

**Headers**: `Authorization: Bearer {token}`

**Query Parameters**:
- `user_id` (int): User ID

**Response**:
```json
[
  {
    "id": 1,
    "user_id": 1,
    "motion_alerts_enabled": true,
    "face_recognition_alerts_enabled": true,
    "unknown_face_alerts_enabled": true,
    "email_enabled": true,
    "email_address": "admin@example.com",
    "min_seconds_between_alerts": 300,
    "quiet_hours_enabled": false,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "07:00"
  }
]
```

### POST /api/alerts/config
Create alert configuration

**Headers**: `Authorization: Bearer {token}`

**Request Body**: Alert config object

**Response**: Created config (201 Created)

### PUT /api/alerts/config/{id}
Update alert configuration

**Headers**: `Authorization: Bearer {token}`

**Request Body**: Full alert config object

**Response**: Updated config

### POST /api/alerts/test
Send test alert

**Headers**: `Authorization: Bearer {token}`

**Request Body**:
```json
{
  "alert_config_id": 1,
  "channel": "email",
  "message": "Test alert"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Test email sent successfully"
}
```

### GET /api/alerts/logs
Get alert history

**Headers**: `Authorization: Bearer {token}`

**Query Parameters**:
- `limit` (int, default=20): Maximum results

**Response**:
```json
[
  {
    "id": 789,
    "alert_type": "face_detected",
    "message": "Known face detected: John Doe",
    "channel": "email",
    "sent_at": "2025-01-10T12:30:00Z",
    "success": true
  }
]
```

---

## System

### GET /api/setup/status
Check if system is initialized (PUBLIC - No auth required)

**Response**:
```json
{
  "initialized": true,
  "version": "3.5.2",
  "users_exist": true
}
```

### POST /api/setup/initialize
Initialize system with first admin user (PUBLIC - No auth required)

**Request Body**:
```json
{
  "username": "admin",
  "password": "securepassword",
  "email": "admin@example.com"
}
```

**Response**:
```json
{
  "message": "System initialized successfully",
  "user": {
    "username": "admin",
    "email": "admin@example.com"
  }
}
```

### GET /api/health
Health check endpoint

**Response**:
```json
{
  "status": "healthy",
  "version": "3.5.2",
  "uptime_seconds": 3600
}
```

### GET /api/system/info
Get system information

**Headers**: `Authorization: Bearer {token}`

**Response**:
```json
{
  "version": "3.5.2",
  "python_version": "3.11.5",
  "opencv_version": "4.8.1",
  "platform": "macOS-14.0",
  "cameras_active": 2,
  "disk_usage": {
    "total_gb": 500,
    "used_gb": 250,
    "free_gb": 250,
    "percent_used": 50
  }
}
```

---

## Data Models

### Camera
```typescript
{
  camera_id: string;           // Unique identifier
  name: string;                // Display name
  camera_type: string;         // 'rtsp', 'usb', 'mock', 'onvif'
  source: string;              // URL or device path
  is_active: boolean;          // Currently active
  resolution: string;          // e.g., "1920x1080"
  fps_target: number;          // Target FPS
  face_detection_enabled: boolean;
  motion_detection_enabled: boolean;
  recording_enabled: boolean;
  created_at: string;          // ISO datetime
  last_active_at: string;      // ISO datetime
}
```

### RecordingEvent
```typescript
{
  id: number;
  camera_id: string;
  recording_path: string;
  started_at: string;          // ISO datetime
  ended_at: string | null;     // ISO datetime
  duration_seconds: number | null;
  file_size_bytes: number | null;
  motion_detected: boolean;
  faces_detected: number;
  known_faces_detected: number;
  frame_count: number | null;
  thumbnail_path: string | null;
}
```

### FaceDetectionEvent
```typescript
{
  id: number;
  camera_id: string;
  person_name: string;
  confidence: number;          // 0.0 to 1.0
  detected_at: string;         // ISO datetime
  location: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
  motion_detected: boolean;
  recording_path: string | null;
  recording_id: number | null; // Links to RecordingEvent
  snapshot_path: string | null;
}
```

---

## Error Handling

### Standard Error Response
```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Successful GET, PATCH, PUT |
| 201 | Created | Successful POST |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid input data |
| 401 | Unauthorized | Missing or invalid token |
| 403 | Forbidden | Valid token but insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource already exists (duplicate) |
| 422 | Unprocessable Entity | Validation error |
| 500 | Internal Server Error | Server-side error |

### Authentication Errors

**401 Unauthorized** - Token missing, expired, or invalid:
```json
{
  "detail": "Not authenticated"
}
```

**Solution**: Obtain new token via `/api/token` endpoint

### Validation Errors

**422 Unprocessable Entity** - Input validation failed:
```json
{
  "detail": [
    {
      "loc": ["body", "camera_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Frontend Integration

### Using apiClient (Recommended)

```javascript
import apiClient from '../api/apiClient';

// GET request
const cameras = await apiClient.get('/cameras/');

// POST request
const newCamera = await apiClient.post('/cameras/', {
  camera_id: 'new-cam',
  name: 'New Camera',
  camera_type: 'rtsp',
  source: 'rtsp://...'
});

// PATCH request
await apiClient.patch('/cameras/front-door', {
  is_active: false
});

// DELETE request
await apiClient.delete('/cameras/front-door');
```

### Authentication Flow

```javascript
// 1. Login
const response = await axios.post('/api/token', new URLSearchParams({
  username: 'admin',
  password: 'password'
}));
localStorage.setItem('token', response.data.access_token);

// 2. All subsequent requests use apiClient
// (token automatically added by interceptor)
const cameras = await apiClient.get('/cameras/');

// 3. Logout
localStorage.removeItem('token');
window.location.href = '/login';
```

### Error Handling

```javascript
try {
  const response = await apiClient.get('/cameras/');
  setCameras(response.data.cameras);
} catch (error) {
  if (error.response?.status === 401) {
    // Token expired - redirect to login
    window.location.href = '/login';
  } else {
    // Show error message
    console.error('Error:', error.response?.data?.detail || error.message);
  }
}
```

---

## Rate Limiting

Currently **not implemented**. Future versions may include:
- 100 requests per minute per IP
- 1000 requests per hour per user
- Burst allowance: 20 requests

---

## WebSocket API

### Connect to WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data);
};
```

### Event Types

- `face_detected` - New face detection
- `motion_detected` - Motion detected
- `recording_started` - Recording started
- `recording_stopped` - Recording stopped
- `camera_status_changed` - Camera online/offline

**Note**: WebSocket authentication currently has issues (403 errors). Use HTTP polling as fallback.

---

## Changelog

### v3.5.2 (2025-01-12)
- Added `recording_id` FK to FaceDetectionEvent
- Renamed `Camera.last_active` to `last_active_at`
- Migrated all frontend pages to centralized apiClient
- Fixed 401 authentication spam
- Added event-to-recording linking

### v3.5.0 (2025-01-10)
- Initial HIG Split View layout
- Aqua Security theme
- Centralized API client with auth interceptors

---

**For more information, see**:
- [Frontend Developer Guide](./FRONTEND_GUIDE.md)
- [Backend Developer Guide](./BACKEND_GUIDE.md)
- [Deployment Guide](../README.md)
