# OpenEye Surveillance System - Changelog

All notable changes to the OpenEye Surveillance System project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.3.0] - 2025-10-08

### Fixed
- **Async/Await Context Issues**: Fixed `asyncio.create_task()` being called from synchronous camera threads by using `asyncio.run_coroutine_threadsafe()` instead
- **Missing camera_id Attribute**: Camera instances now properly store their ID on both camera and recorder objects
- **Password Hashing Consistency**: Standardized all password hashing to use `auth.hash_password()` throughout the codebase
- **Missing Directory Creation**: Added automatic creation of required directories (recordings, faces, data, snapshots, thumbnails) on startup
- **Thread Safety**: Implemented `threading.Lock()` for all CameraManager dictionary operations to prevent race conditions
- **Face Detection Logging**: Face detection data now properly logged to recorder metadata during recording sessions
- **Database Schema Verification**: Added runtime assertion to ensure Base classes are identical across models

### Changed
- Improved error handling for motion alert triggering
- Enhanced thread-safe camera management
- Better metadata tracking for face detections in recordings

### Technical Details
- Fixed RuntimeError exceptions in motion alert system
- Camera identification now works correctly throughout application
- All user creation flows use consistent password hashing
- Application works on fresh installations without manual directory creation
- Thread-safe camera management prevents crashes and race conditions
- Recording metadata includes all detected faces with timestamps and frame numbers

---

## [3.2.9] - 2025-10-07

### Fixed
- **Theme System**: Complete rewrite of theme system to fix CSS specificity conflicts
- **Import Order**: Fixed CSS import order in main.jsx (themes.css before index.css)
- **Theme Application**: Themes now properly apply to `<html>` element instead of wrapper div
- **CSS Variables**: Unified all theme CSS variables under single themes.css file
- **Theme Switching**: Removed conflicts between global-theme.css and themes.css

### Changed
- Removed wrapper div from ThemeContext for cleaner DOM structure
- Applied themes to document.documentElement for maximum CSS specificity
- Cleaned up index.css to remove all hardcoded colors
- All 8 themes now fully functional with proper color application

---

## [3.2.8] - 2025-10-07

### Fixed
- Alert Settings Page CSS corruption causing spinning text boxes
- SMTP configuration code block styling (dark background)
- Method description text color (uses var(--text-primary))
- No-logs message color (uses #88c0d0)
- Help text and link styling

### Added
- Comprehensive macOS USB camera limitations documentation
- Four workarounds for macOS USB camera issues:
  - Use Network/IP Cameras (Recommended)
  - Run Backend Natively on macOS
  - USB/IP Forwarding (Experimental)
  - Use Linux Development Environment

### Documentation
- Created DOCKER_HUB_DESCRIPTION.md with complete overview
- Updated README with USB camera limitations
- Improved Docker Hub description

---

## [3.2.0] - 2025-10-06

### Changed
- **Major UI/UX Restructure**: Complete overhaul of frontend interface
- Improved navigation and user experience
- Enhanced component organization
- Better responsive design

---

## [3.1.3] - 2025-10-05

### Fixed
- **Bcrypt Truncation Issue**: Properly handle bcrypt's 72-byte limit
- Password truncation now done transparently in hash_password()
- No more silent password length errors
- Updated documentation with password limits

### Security
- Enhanced password hashing security
- Better error messages for password issues

---

## [3.1.2] - 2025-10-05

### Fixed
- **Password Validation**: Fixed password validation errors
- **White Screen Issue**: Resolved blank screen on startup
- Frontend routing issues
- Database initialization problems

### Changed
- Improved error handling in authentication flow
- Better user feedback for login issues

---

## [3.1.1] - 2025-10-05

### Fixed
- **Frontend Serving**: Fixed React frontend not being served correctly
- Static file serving configuration
- Build output path issues

### Changed
- Updated Dockerfile to properly copy frontend build
- Improved static file handling in FastAPI

---

## [3.1.0] - 2025-10-05

### Added - Camera Discovery
- **USB Camera Detection**: Automatic scanning of USB webcams (indices 0-10)
- **Network RTSP Scanning**: Discovers IP cameras on local subnets
- **Pre-Add Testing**: Validate camera connections before adding
- **Auto-Configuration**: Automatically generates camera configs with resolution/FPS
- **One-Click Addition**: Quick-add discovered cameras
- New CameraDiscovery service
- API endpoints for camera discovery:
  - `GET /api/cameras/discover/usb` - Discover USB cameras
  - `GET /api/cameras/discover/network` - Discover network cameras

### Added - Camera Management
- Complete camera management interface
- Three-tab interface (List, Discovery, Manual)
- Live camera status indicators
- Enable/disable camera toggle
- Delete cameras with confirmation
- Common RTSP URL templates
- Form validation and error handling
- API endpoints:
  - `GET /api/cameras/` - List all cameras
  - `POST /api/cameras/` - Add new camera
  - `GET /api/cameras/{id}` - Get camera details
  - `PUT /api/cameras/{id}` - Update camera
  - `DELETE /api/cameras/{id}` - Remove camera

### Added - Theme System
- 8 superhero-inspired themes:
  - Default (Dark Professional)
  - Superman (Classic red/blue)
  - Batman (Dark knight)
  - Wonder Woman (Warrior princess)
  - Flash (Speed force)
  - Aquaman (Ocean depths)
  - Cyborg (Tech enhanced)
  - Green Lantern (Willpower)
- Custom color palettes and typography per theme
- Animated overlays and effects
- Persistent theme selection (localStorage)
- Live theme preview
- Theme selector page

### Added - Help System
- 36+ inline help entries
- Context-sensitive help
- Modal help dialogs
- Comprehensive documentation for all features

### Added - First-Run Setup
- Setup wizard for first-time users
- Admin account creation
- Security key generation
- Database initialization
- Guided setup process

### Documentation
- Complete Docker deployment guide
- Camera discovery usage guide
- Web dashboard documentation
- Theme system documentation
- Updated README with all new features

---

## [3.0.0] - 2025-10-01

### Added - Core Features (Phases 1-2)
- Multi-camera support (RTSP streams and mock cameras)
- Motion detection using OpenCV MOG2 background subtraction
- Automatic motion-triggered recording
- Live MJPEG streaming with real-time overlays
- Face recognition with dlib
- Face management interface
- Detection history tracking
- SQLite database persistence
- User authentication and authorization

### Added - Notifications (Phase 3)
- Email alerts via SMTP
- SMS alerts (Twilio integration)
- Push notifications (Firebase)
- Webhook support
- Alert throttling to prevent spam
- Configurable notification channels

### Added - Smart Home Integration (Phase 4)
- Home Assistant MQTT integration
- Apple HomeKit bridge
- Google Nest integration
- Automation triggers

### Added - Cloud & Mobile (Phase 5)
- Cloud storage support (AWS S3, Google Cloud Storage, Azure Blob)
- MinIO support for self-hosted cloud storage
- React Native mobile app foundation
- WebSocket real-time streaming
- Remote access via WireGuard/Tailscale

### Added - Advanced Features (Phase 6)
- Recording management (search, download, stream)
- Advanced analytics (hourly/daily activity breakdown)
- Storage management with automatic cleanup
- Multi-user system (Admin, User, Viewer roles)
- Rate limiting for API protection
- SQL injection protection
- PostgreSQL support for production
- Docker containerization

### Added - API
- Complete REST API with FastAPI
- JWT authentication
- API documentation (Swagger/ReDoc)
- Rate limiting
- CORS support

### Added - Frontend
- React-based web interface
- Real-time video streaming
- Face management UI
- Camera configuration
- Settings and preferences
- Responsive design

### Security
- JWT-based authentication
- Bcrypt password hashing
- API rate limiting
- SQL injection protection
- CORS configuration
- Environment variable configuration

---

## Future Work

### Planned Features
- [ ] Advanced face recognition training options
- [ ] License plate recognition (ALPR)
- [ ] Object detection (YOLO integration)
- [ ] Timeline playback system
- [ ] Two-way audio support
- [ ] Advanced analytics dashboard
- [ ] Mobile app completion
- [ ] Multi-server support
- [ ] Kubernetes deployment guide
- [ ] Advanced automation rules
- [ ] Integration with more smart home platforms
- [ ] Custom alert rules engine
- [ ] Video analytics (people counting, dwell time)
- [ ] Heat map generation
- [ ] PTZ camera control
- [ ] Audio event detection
- [ ] Cloud backup automation
- [ ] Multi-language support
- [ ] Dark/light mode toggle
- [ ] Custom dashboard widgets

### Known Limitations
- macOS Docker USB camera support limited (requires native backend or network cameras)
- Face recognition is CPU-intensive (GPU acceleration recommended for multiple cameras)
- SQLite has limitations for >5 concurrent users (use PostgreSQL for production)
- dlib installation requires system dependencies (cmake, libopenblas-dev, liblapack-dev)

---

## Links

- **GitHub Repository**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security
- **Docker Hub**: https://hub.docker.com/r/im1k31s/openeye-opencv_home_security
- **Documentation**: See README.md
- **Issues**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues

---

*For detailed installation instructions, usage examples, and troubleshooting, see the [README.md](README.md)*