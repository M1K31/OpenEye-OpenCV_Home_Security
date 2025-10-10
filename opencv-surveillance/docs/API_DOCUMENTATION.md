# OpenEye API Documentation

**Version:** 3.3.7  
**Last Updated:** October 2025

## Table of Contents
- [Overview](#overview)
- [Authentication](#authentication)
- [Base URL](#base-url)
- [API Endpoints](#api-endpoints)
  - [Authentication](#authentication-endpoints)
  - [Cameras](#camera-endpoints)
  - [Face Recognition](#face-recognition-endpoints)
  - [Alerts & Notifications](#alerts--notifications-endpoints)
  - [Recordings](#recordings-endpoints)
  - [Analytics](#analytics-endpoints)
  - [System](#system-endpoints)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Examples](#examples)

---

## Overview

The OpenEye API provides programmatic access to all surveillance system features including camera management, face recognition, alerts, and analytics. The API follows RESTful principles and uses JSON for request/response payloads.

### Key Features
- JWT-based authentication
- Real-time camera streaming
- Face recognition training and detection
- Alert configuration and history
- Recording management
- Advanced analytics

---

## Authentication

All API endpoints (except `/api/token` and `/api/setup/*`) require JWT authentication.

### Obtaining a Token

**Endpoint:** `POST /api/token`  
**Content-Type:** `application/x-www-form-urlencoded`

**Request Body:**
```
username=admin&password=your_password
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Using the Token

Include the token in the `Authorization` header for all subsequent requests:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Example with cURL:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/cameras
```

**Example with Python:**
```python
import requests

# Get token
response = requests.post('http://localhost:8000/api/token', 
    data={'username': 'admin', 'password': 'your_password'})
token = response.json()['access_token']

# Use token
headers = {'Authorization': f'Bearer {token}'}
cameras = requests.get('http://localhost:8000/api/cameras', headers=headers)
print(cameras.json())
```

---

## Base URL

**Local Development:** `http://localhost:8000`  
**Production:** `http://your-server-ip:8000`

All endpoints are prefixed with `/api`

---

## API Endpoints

### Authentication Endpoints

#### Login
```http
POST /api/token
Content-Type: application/x-www-form-urlencoded

username=admin&password=your_password
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

---

### Camera Endpoints

#### List All Cameras
```http
GET /api/cameras
Authorization: Bearer {token}
```

**Response:**
```json
{
  "cameras": [
    {
      "id": 1,
      "name": "Front Door",
      "type": "rtsp",
      "source": "rtsp://192.168.1.100:554/stream",
      "enabled": true,
      "created_at": "2025-10-01T10:00:00"
    }
  ],
  "total": 1
}
```

#### Add Camera
```http
POST /api/cameras
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Front Door",
  "type": "rtsp",
  "source": "rtsp://192.168.1.100:554/stream",
  "enabled": true
}
```

**Camera Types:**
- `rtsp` - RTSP stream URL
- `usb` - USB camera (e.g., `/dev/video0` or `0`)
- `http` - HTTP MJPEG stream

#### Get Camera Details
```http
GET /api/cameras/{camera_id}
Authorization: Bearer {token}
```

#### Update Camera
```http
PUT /api/cameras/{camera_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Updated Name",
  "enabled": true
}
```

#### Delete Camera
```http
DELETE /api/cameras/{camera_id}
Authorization: Bearer {token}
```

#### Camera Stream
```http
GET /api/cameras/{camera_id}/stream
Authorization: Bearer {token}
```

Returns MJPEG stream. Use in `<img>` tag:
```html
<img src="http://localhost:8000/api/cameras/1/stream" />
```

#### Camera Snapshot
```http
GET /api/cameras/{camera_id}/snapshot
Authorization: Bearer {token}
```

Returns single JPEG image.

---

### Face Recognition Endpoints

#### List People
```http
GET /api/faces/people
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "name": "John Doe",
    "photo_count": 5,
    "last_seen": "2025-10-09T15:30:00"
  }
]
```

#### Add Person
```http
POST /api/faces/people
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "John Doe"
}
```

#### Upload Photos for Person
```http
POST /api/faces/people/{person_name}/photos
Authorization: Bearer {token}
Content-Type: multipart/form-data

files: [file1.jpg, file2.jpg, file3.jpg]
```

**cURL Example:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@photo1.jpg" \
  -F "files=@photo2.jpg" \
  -F "files=@photo3.jpg" \
  http://localhost:8000/api/faces/people/JohnDoe/photos
```

**Python Example:**
```python
files = [
    ('files', open('photo1.jpg', 'rb')),
    ('files', open('photo2.jpg', 'rb')),
    ('files', open('photo3.jpg', 'rb'))
]
response = requests.post(
    'http://localhost:8000/api/faces/people/JohnDoe/photos',
    headers={'Authorization': f'Bearer {token}'},
    files=files
)
```

#### Train Face Recognition Model
```http
POST /api/faces/train
Authorization: Bearer {token}
```

**Response:**
```json
{
  "message": "Training complete",
  "total_people": 3,
  "total_encodings": 15,
  "training_time": 45.2
}
```

#### Get Face Detection Statistics
```http
GET /api/faces/statistics
Authorization: Bearer {token}
```

**Response:**
```json
{
  "total_people": 3,
  "total_photos": 15,
  "model_trained": true,
  "last_training": "2025-10-09T14:00:00"
}
```

#### Face Detection History
```http
GET /api/faces/detections?limit=50&offset=0
Authorization: Bearer {token}
```

**Response:**
```json
{
  "detections": [
    {
      "id": 123,
      "person_name": "John Doe",
      "confidence": 0.95,
      "camera_id": 1,
      "timestamp": "2025-10-09T15:30:00",
      "image_path": "/snapshots/detection_123.jpg"
    }
  ],
  "total": 100
}
```

#### Delete Person
```http
DELETE /api/faces/people/{person_name}
Authorization: Bearer {token}
```

---

### Alerts & Notifications Endpoints

#### Get Alert Configuration
```http
GET /api/alerts/config
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": 1,
  "email_enabled": true,
  "email_address": "admin@example.com",
  "sms_enabled": false,
  "phone_number": null,
  "push_enabled": false,
  "push_token": null,
  "webhook_url": null
}
```

#### Create/Update Alert Configuration
```http
POST /api/alerts/config
Authorization: Bearer {token}
Content-Type: application/json

{
  "email_enabled": true,
  "email_address": "alerts@example.com",
  "sms_enabled": false,
  "push_enabled": false
}
```

#### Test Alert
```http
POST /api/alerts/test
Authorization: Bearer {token}
Content-Type: application/json

{
  "channel": "email",
  "recipient": "test@example.com"
}
```

**Channels:** `email`, `sms`, `push`, `webhook`

#### Get Alert History
```http
GET /api/alerts/logs?limit=50&offset=0
Authorization: Bearer {token}
```

**Response:**
```json
{
  "logs": [
    {
      "id": 456,
      "alert_type": "motion_detected",
      "message": "Motion detected on Front Door",
      "camera_id": 1,
      "timestamp": "2025-10-09T15:45:00",
      "sent_via": ["email"],
      "status": "delivered"
    }
  ],
  "total": 250
}
```

---

### Recordings Endpoints

#### List Recordings
```http
GET /api/recordings?camera_id=1&start_time=2025-10-01T00:00:00&end_time=2025-10-09T23:59:59
Authorization: Bearer {token}
```

**Response:**
```json
{
  "recordings": [
    {
      "id": 789,
      "camera_id": 1,
      "camera_name": "Front Door",
      "start_time": "2025-10-09T14:00:00",
      "end_time": "2025-10-09T14:30:00",
      "duration": 1800,
      "file_size": 104857600,
      "file_path": "/recordings/camera1_20251009_140000.mp4",
      "event_type": "motion"
    }
  ],
  "total": 45
}
```

#### Get Recording
```http
GET /api/recordings/{recording_id}
Authorization: Bearer {token}
```

Returns video file (MP4).

#### Delete Recording
```http
DELETE /api/recordings/{recording_id}
Authorization: Bearer {token}
```

---

### Analytics Endpoints

#### Get Dashboard Statistics
```http
GET /api/analytics/dashboard
Authorization: Bearer {token}
```

**Response:**
```json
{
  "active_cameras": 3,
  "total_detections_today": 45,
  "storage_used": "2.5 GB",
  "storage_available": "47.5 GB",
  "system_uptime": "5 days, 3 hours"
}
```

#### Get Detection Timeline
```http
GET /api/analytics/timeline?camera_id=1&date=2025-10-09
Authorization: Bearer {token}
```

**Response:**
```json
{
  "date": "2025-10-09",
  "events": [
    {
      "time": "08:15:00",
      "type": "person_detected",
      "person": "John Doe",
      "confidence": 0.95
    },
    {
      "time": "12:30:00",
      "type": "motion_detected"
    }
  ]
}
```

---

### System Endpoints

#### Health Check
```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "active_cameras": 3,
  "face_recognition": "available",
  "database": "connected"
}
```

#### Setup Status
```http
GET /api/setup/status
```

**Response:**
```json
{
  "setup_complete": true,
  "admin_exists": true
}
```

#### Complete First-Run Setup
```http
POST /api/setup/complete
Content-Type: application/json

{
  "username": "admin",
  "email": "admin@example.com",
  "password": "SecurePassword123!"
}
```

---

## Error Handling

### HTTP Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Missing or invalid authentication token
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Validation Error Example:**
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Rate Limiting

Currently, there are no rate limits enforced. This may change in future versions.

**Recommendations:**
- Limit camera stream requests to avoid bandwidth issues
- Use webhooks instead of polling for real-time updates
- Cache responses when appropriate

---

## Examples

### Complete Python Integration Example

```python
import requests
import time

class OpenEyeClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.token = self._login(username, password)
        
    def _login(self, username, password):
        """Authenticate and get token"""
        response = requests.post(
            f'{self.base_url}/api/token',
            data={'username': username, 'password': password}
        )
        response.raise_for_status()
        return response.json()['access_token']
    
    def _headers(self):
        """Get auth headers"""
        return {'Authorization': f'Bearer {self.token}'}
    
    def get_cameras(self):
        """List all cameras"""
        response = requests.get(
            f'{self.base_url}/api/cameras',
            headers=self._headers()
        )
        return response.json()
    
    def add_camera(self, name, camera_type, source):
        """Add a new camera"""
        response = requests.post(
            f'{self.base_url}/api/cameras',
            headers=self._headers(),
            json={
                'name': name,
                'type': camera_type,
                'source': source,
                'enabled': True
            }
        )
        return response.json()
    
    def train_face_recognition(self, person_name, photo_paths):
        """Upload photos and train model"""
        # Upload photos
        files = [('files', open(path, 'rb')) for path in photo_paths]
        response = requests.post(
            f'{self.base_url}/api/faces/people/{person_name}/photos',
            headers=self._headers(),
            files=files
        )
        for _, f in files:
            f.close()
        
        # Train model
        response = requests.post(
            f'{self.base_url}/api/faces/train',
            headers=self._headers()
        )
        return response.json()
    
    def get_recent_detections(self, limit=10):
        """Get recent face detections"""
        response = requests.get(
            f'{self.base_url}/api/faces/detections',
            headers=self._headers(),
            params={'limit': limit, 'offset': 0}
        )
        return response.json()

# Usage
client = OpenEyeClient('http://localhost:8000', 'admin', 'password')

# List cameras
cameras = client.get_cameras()
print(f"Active cameras: {cameras['total']}")

# Add a camera
new_camera = client.add_camera(
    'Backyard', 
    'rtsp', 
    'rtsp://192.168.1.101:554/stream'
)
print(f"Added camera: {new_camera['name']}")

# Train face recognition
result = client.train_face_recognition(
    'John Doe',
    ['photo1.jpg', 'photo2.jpg', 'photo3.jpg']
)
print(f"Trained {result['total_encodings']} face encodings")

# Get recent detections
detections = client.get_recent_detections(limit=5)
for detection in detections['detections']:
    print(f"{detection['timestamp']}: {detection['person_name']} "
          f"({detection['confidence']*100:.1f}%)")
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

class OpenEyeClient {
  constructor(baseUrl, username, password) {
    this.baseUrl = baseUrl;
    this.token = null;
    this.login(username, password);
  }
  
  async login(username, password) {
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);
    
    const response = await axios.post(
      `${this.baseUrl}/api/token`, 
      params
    );
    this.token = response.data.access_token;
  }
  
  headers() {
    return {
      'Authorization': `Bearer ${this.token}`
    };
  }
  
  async getCameras() {
    const response = await axios.get(
      `${this.baseUrl}/api/cameras`,
      { headers: this.headers() }
    );
    return response.data;
  }
  
  async getDetections(limit = 10) {
    const response = await axios.get(
      `${this.baseUrl}/api/faces/detections`,
      { 
        headers: this.headers(),
        params: { limit, offset: 0 }
      }
    );
    return response.data;
  }
}

// Usage
(async () => {
  const client = new OpenEyeClient(
    'http://localhost:8000', 
    'admin', 
    'password'
  );
  
  await client.login('admin', 'password');
  
  const cameras = await client.getCameras();
  console.log(`Active cameras: ${cameras.total}`);
  
  const detections = await client.getDetections(5);
  detections.detections.forEach(d => {
    console.log(`${d.timestamp}: ${d.person_name} (${(d.confidence*100).toFixed(1)}%)`);
  });
})();
```

### Webhook Integration Example

Configure a webhook URL in alert settings to receive real-time notifications:

**Your webhook endpoint should accept:**
```http
POST https://your-server.com/webhook
Content-Type: application/json

{
  "event_type": "person_detected",
  "person_name": "John Doe",
  "confidence": 0.95,
  "camera_id": 1,
  "camera_name": "Front Door",
  "timestamp": "2025-10-09T15:30:00",
  "image_url": "http://localhost:8000/api/snapshots/detection_123.jpg"
}
```

**Express.js webhook handler:**
```javascript
app.post('/webhook', (req, res) => {
  const event = req.body;
  
  if (event.event_type === 'person_detected') {
    console.log(`${event.person_name} detected at ${event.camera_name}`);
    // Send custom notification, log to database, etc.
  }
  
  res.status(200).send('OK');
});
```

---

## Environment Variables for Notifications

To enable SMTP, SMS, and Push notifications, set these environment variables:

### SMTP (Email)
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_ADDRESS=openeye@yourdomain.com
```

### SMS (Twilio)
```bash
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

### Push Notifications
```bash
PUSH_SERVICE_URL=https://your-push-service.com/send
PUSH_SERVICE_KEY=your_api_key
```

**Note:** A UI for configuring these will be added in a future version. Currently, set them in your docker-compose.yml or deployment environment.

---

## Support & Resources

- **GitHub:** https://github.com/M1K31/OpenEye-OpenCV_Home_Security
- **Documentation:** `/docs` folder in repository
- **Issues:** GitHub Issues
- **Docker Hub:** https://hub.docker.com/r/im1k31s/openeye-opencv_home_security

---

**OpenEye** - Open Source Home Security with AI Face Recognition  
**License:** MIT  
**Copyright © 2025 Mikel Smart**
