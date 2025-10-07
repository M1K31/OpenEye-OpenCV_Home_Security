/*
Copyright (c) 2025 Mikel Smart
This file is part of OpenEye-OpenCV_Home_Security
*/

export const HELP_CONTENT = {
  // Camera Management
  CAMERA_DISCOVERY: {
    title: "Camera Discovery",
    description: "Automatically detect USB webcams and network RTSP cameras. Click 'Scan for USB Cameras' for local devices or 'Scan Network' to find IP cameras on your local network (Hikvision, Dahua, Amcrest, Reolink, etc.)."
  },
  CAMERA_MANUAL: {
    title: "Manual Camera Configuration",
    description: "Add cameras manually by entering RTSP URL, HTTP stream, or USB device path. Use provided templates for common camera brands. Configure via the 'Cameras' → 'Manual' tab in the dashboard."
  },
  CAMERA_TYPES: {
    title: "Supported Camera Types",
    description: "RTSP streams (rtsp://), HTTP streams (http://), USB cameras (/dev/video0), and mock cameras for testing. Most IP cameras support RTSP."
  },

  // Motion Detection & Recording
  MOTION_DETECTION: {
    title: "Motion Detection",
    description: "Uses OpenCV MOG2 background subtraction algorithm. Automatically configured - no manual setup required. Adjust sensitivity in Alert Settings if needed."
  },
  AUTO_RECORDING: {
    title: "Automatic Recording",
    description: "Recordings start automatically when motion is detected. Duration is configurable (default 300 seconds). Set MAX_RECORDING_DURATION environment variable in Docker Compose."
  },
  RECORDING_MANAGEMENT: {
    title: "Recording Management",
    description: "View, search, download, and stream recordings through the dashboard. Auto-cleanup can be configured. Access via API at /api/recordings."
  },

  // Face Recognition
  FACE_RECOGNITION: {
    title: "Face Recognition",
    description: "AI-powered person identification using dlib library. Upload face images via 'Face Management' page. Enable/disable with ENABLE_FACE_RECOGNITION environment variable."
  },
  FACE_UPLOAD: {
    title: "Register Faces",
    description: "Go to Dashboard → 'Faces' → Upload image with person's name. System will extract face encodings. Multiple photos per person improve accuracy."
  },

  // Notifications - Email
  EMAIL_NOTIFICATIONS: {
    title: "Email Notifications (FREE with Gmail)",
    description: "Configure recipient email in Alert Settings page. Set SMTP server details in Docker environment: SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD. Use Gmail App Password for security."
  },

  // Notifications - SMS
  SMS_TELEGRAM: {
    title: "SMS via Telegram Bot (FREE!)",
    description: "1. Message @BotFather on Telegram to create bot. 2. Get bot token. 3. Message your bot and get chat ID from @userinfobot. 4. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Docker environment. 100% FREE!"
  },
  SMS_TWILIO: {
    title: "SMS via Twilio (Paid)",
    description: "Configure phone number in Alert Settings page. Set Twilio credentials in Docker environment: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER. Costs apply per message."
  },

  // Notifications - Push
  PUSH_NTFY: {
    title: "Push Notifications via ntfy.sh (FREE!)",
    description: "1. Choose unique topic name. 2. Download ntfy app (iOS/Android). 3. Subscribe to your topic in app. 4. Set NTFY_TOPIC and NTFY_SERVER=https://ntfy.sh in Docker environment. Open source and FREE!"
  },
  PUSH_FIREBASE: {
    title: "Push Notifications via Firebase",
    description: "1. Create Firebase project. 2. Download service account JSON. 3. Set FIREBASE_CREDENTIALS_PATH in Docker environment. 4. Configure device token in Alert Settings. Free tier available."
  },

  // Notifications - Webhooks
  WEBHOOKS: {
    title: "Webhook Notifications",
    description: "Send HTTP POST requests to custom URLs on events. Configure webhook URL in Alert Settings page. Useful for integrating with custom systems, Zapier, IFTTT, etc."
  },

  // Alert Configuration
  ALERT_THROTTLING: {
    title: "Alert Throttling",
    description: "Minimum seconds between alerts (60-3600s). Prevents spam when motion is continuous. Configure via slider in Alert Settings page."
  },
  QUIET_HOURS: {
    title: "Quiet Hours",
    description: "Disable alerts during specified time periods (e.g., nighttime). Enable and set start/end times in Alert Settings page."
  },

  // Smart Home Integration
  HOME_ASSISTANT: {
    title: "Home Assistant Integration (FREE!)",
    description: "MQTT integration for Home Assistant. Set environment variables: MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD. Events automatically published to HA. No UI configuration needed."
  },
  HOMEKIT: {
    title: "Apple HomeKit Integration (FREE!)",
    description: "Bridge OpenEye cameras to Apple Home app. Set environment variables: HOMEKIT_ENABLED=true, HOMEKIT_PIN=123-45-678. Cameras appear in Home app automatically. No UI configuration needed."
  },
  NEST: {
    title: "Google Nest Integration",
    description: "Integrate with Google Nest ecosystem. Requires Google Cloud project and API access. Set environment variables: NEST_PROJECT_ID, NEST_CLIENT_ID, NEST_CLIENT_SECRET. No UI configuration needed."
  },

  // Cloud Storage
  CLOUD_STORAGE_MINIO: {
    title: "MinIO Cloud Storage (FREE Self-Hosted!)",
    description: "Self-hosted S3-compatible storage. Install MinIO server, then set environment variables: MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET. 100% FREE unlimited storage!"
  },
  CLOUD_STORAGE_S3: {
    title: "AWS S3 Cloud Storage",
    description: "Store recordings in Amazon S3. Set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET, AWS_REGION. Costs apply per GB stored."
  },
  CLOUD_STORAGE_GCS: {
    title: "Google Cloud Storage",
    description: "Store recordings in Google Cloud. Download service account JSON and set: GCS_BUCKET, GCS_CREDENTIALS_PATH in environment. Costs apply per GB stored."
  },

  // Database
  DATABASE_SQLITE: {
    title: "SQLite Database (Default)",
    description: "Default database - no configuration needed! Lightweight and perfect for home use. Data stored in /app/data/openeye.db volume."
  },
  DATABASE_POSTGRES: {
    title: "PostgreSQL Database",
    description: "Production-grade database for larger deployments. Set DATABASE_URL environment variable: postgresql://user:password@host:5432/openeye. See Docker Compose example in docs."
  },

  // Security & Users
  MULTI_USER: {
    title: "Multi-User System",
    description: "Create admin, user, and viewer roles. Default admin account created on first run. Add users via API (/api/users/). Configure usernames, passwords, and roles. No UI page yet - use API."
  },
  JWT_AUTH: {
    title: "JWT Authentication",
    description: "Secure API access with JSON Web Tokens. Set JWT_SECRET_KEY environment variable (required!). Tokens automatically managed - no manual configuration needed."
  },
  RATE_LIMITING: {
    title: "Rate Limiting",
    description: "API abuse protection automatically enabled. Prevents excessive requests. Configured in backend - no manual setup required."
  },

  // Remote Access
  REMOTE_ACCESS_VPN: {
    title: "Remote Access via VPN (FREE!)",
    description: "Access OpenEye remotely using WireGuard, Tailscale, or ZeroTier VPN. All are FREE! Install VPN on your server, connect from anywhere securely. See User Guide for setup instructions. No OpenEye configuration needed."
  },

  // Themes
  THEMES: {
    title: "Superhero Themes",
    description: "Choose from 8 superhero-inspired themes: Sman (Classic red/blue), Bman (Dark knight), W Woman (Warrior gold), Flah (Speed red), Aman (Ocean teal), Cy (Tech silver), G Lantern (Willpower green), and Default (Professional blue). Access via Dashboard → 'Themes'. Theme persists across sessions."
  },

  // Live Streaming
  LIVE_STREAMING: {
    title: "Live Streaming",
    description: "MJPEG streams with real-time overlays (motion detection, face recognition boxes). Access at /api/cameras/{camera_id}/stream. View in dashboard camera list."
  },

  // Analytics
  ANALYTICS: {
    title: "Advanced Analytics",
    description: "Activity tracking and statistics. View notification success rates, recent alerts, and event logs in Alert Settings page. More analytics coming in future versions."
  }
};

// Feature UI availability matrix
export const FEATURE_UI_STATUS = {
  // Has complete UI configuration
  HAS_UI: [
    'Camera Discovery',
    'Manual Camera Configuration',
    'Email Notifications',
    'SMS Notifications (Telegram & Twilio)',
    'Push Notifications (ntfy.sh & Firebase)',
    'Webhook Notifications',
    'Alert Throttling',
    'Quiet Hours',
    'Face Registration',
    'Recording Management',
    'Live Streaming',
    'Theme Selection',
    'Analytics (Partial)'
  ],
  
  // Environment variables only (no UI)
  ENV_VARS_ONLY: [
    'Motion Detection Sensitivity',
    'Recording Duration (MAX_RECORDING_DURATION)',
    'Home Assistant (MQTT)',
    'Apple HomeKit',
    'Google Nest',
    'Cloud Storage (MinIO/S3/GCS)',
    'Database Selection (SQLite/PostgreSQL)',
    'Multi-User Management',
    'JWT Secrets',
    'Remote Access VPN',
    'SMTP Server Settings',
    'Telegram Bot Credentials',
    'Firebase Credentials'
  ],
  
  // Automatic (no configuration needed)
  AUTOMATIC: [
    'Motion Detection (MOG2)',
    'Rate Limiting',
    'Face Recognition Engine',
    'Auto Recording on Motion',
    'Default Admin User Creation'
  ]
};
