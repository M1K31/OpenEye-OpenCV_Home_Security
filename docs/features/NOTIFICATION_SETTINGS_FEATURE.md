# In-App Notification Configuration Feature

**Version**: 3.7.0
**Date**: 2025-01-24
**Status**: ✅ Complete

## Overview

OpenEye now supports **in-app configuration** of notification providers, allowing users to set up email, SMS, push notifications, Telegram, Discord, and custom webhooks directly through the web interface - no more editing environment variables or configuration files!

## What's New

### 🎯 Key Features

1. **Visual Provider Configuration**
   - Configure notification providers through a modern, user-friendly UI
   - Support for 6 notification types: Email (SMTP), SMS (Twilio), Push (FCM), Telegram, Discord, Webhook
   - Test notifications before saving
   - Enable/disable providers with a toggle switch

2. **Secure Credential Storage**
   - All credentials encrypted at rest using Fernet (AES-128)
   - Encryption key stored in environment variable `NOTIFICATION_ENCRYPTION_KEY`
   - Credentials never exposed in API responses (masked as `***HIDDEN***`)

3. **Provider Management**
   - Create multiple providers of the same type (e.g., "Gmail Work" and "Gmail Personal")
   - Edit existing configurations
   - Delete unused providers
   - Track usage statistics (sent/failed counts)

4. **Test Functionality**
   - Send test notifications to verify configuration
   - Real-time delivery status and error messages
   - Delivery time tracking

## Architecture

### Backend Components

#### 1. Database Model (`backend/database/alert_models.py`)

**New Table**: `notification_providers`

```sql
CREATE TABLE notification_providers (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    provider_type VARCHAR,  -- 'email', 'sms', 'push', 'telegram', 'discord', 'webhook'
    provider_name VARCHAR,  -- User-friendly name
    enabled BOOLEAN,
    encrypted_config TEXT,  -- Encrypted JSON credentials
    test_status VARCHAR,
    test_error VARCHAR,
    total_sent INTEGER,
    total_failed INTEGER,
    last_tested_at DATETIME,
    last_used_at DATETIME,
    created_at DATETIME,
    updated_at DATETIME
);
```

**Key Methods**:
- `set_config(dict)` - Encrypts and stores configuration
- `get_config()` - Decrypts and returns configuration
- `encrypt_config(dict)` - Static method for encryption
- `decrypt_config()` - Instance method for decryption

#### 2. API Routes (`backend/api/routes/notification_providers.py`)

**Endpoints**:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notification-providers/templates` | Get provider templates |
| GET | `/api/notification-providers/` | List all providers |
| GET | `/api/notification-providers/{id}` | Get specific provider |
| POST | `/api/notification-providers/` | Create new provider |
| PUT | `/api/notification-providers/{id}` | Update provider |
| DELETE | `/api/notification-providers/{id}` | Delete provider |
| POST | `/api/notification-providers/{id}/test` | Test provider |

**Authentication**: All endpoints require authentication via `get_current_active_user()`

#### 3. Pydantic Schemas (`backend/api/schemas/notifications.py`)

- `EmailProviderConfig` - SMTP configuration
- `SMSProviderConfig` - Twilio configuration
- `PushProviderConfig` - FCM configuration
- `TelegramProviderConfig` - Bot token
- `DiscordProviderConfig` - Webhook URL
- `WebhookProviderConfig` - Custom webhook
- `NotificationProviderCreate` - Create request
- `NotificationProviderUpdate` - Update request
- `NotificationProviderResponse` - API response (credentials masked)
- `TestNotificationRequest` - Test request
- `TestNotificationResponse` - Test result

### Frontend Components

#### 1. Service (`frontend/src/services/notificationService.js`)

Handles all API communication:
- `getTemplates()` - Fetch available provider types
- `listProviders()` - Get user's configured providers
- `createProvider(data)` - Add new provider
- `updateProvider(id, updates)` - Modify existing
- `deleteProvider(id)` - Remove provider
- `testProvider(id, recipient)` - Send test notification
- Helper methods for icons, display names, status formatting

#### 2. Page Component (`frontend/src/pages/NotificationSettingsPage.jsx`)

**Features**:
- Template grid showing all available provider types
- Provider cards with status indicators
- Create/Edit modal with dynamic form fields
- Test modal for sending test notifications
- Enable/disable toggle switches
- Real-time status updates

**State Management**:
- `providers` - List of configured providers
- `templates` - Available provider types
- `formData` - Current form data
- `testResult` - Latest test result

#### 3. Styling (`frontend/src/pages/NotificationSettingsPage.css`)

- Responsive grid layouts
- Modern card-based design
- Modal overlays with glassmorphism
- Toggle switches for enable/disable
- Status badges with color coding
- 8pt grid system compliance
- 44px minimum touch targets

## Provider Types

### 1. Email (SMTP)

**Icon**: 📧
**Configuration**:
- SMTP Host (e.g., `smtp.gmail.com`)
- SMTP Port (default: 587)
- Username/Email
- Password (app-specific password recommended)
- From Email (optional)
- Use TLS (checkbox)

**Test Recipient**: Email address

**Example**:
```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "username": "your-email@gmail.com",
  "password": "app-specific-password",
  "use_tls": true
}
```

### 2. SMS (Twilio)

**Icon**: 📱
**Configuration**:
- Account SID
- Auth Token
- From Phone Number (E.164 format)

**Test Recipient**: Phone number (e.g., `+15551234567`)

**Example**:
```json
{
  "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "auth_token": "your-auth-token",
  "from_number": "+15551234567"
}
```

### 3. Push Notifications (FCM)

**Icon**: 🔔
**Configuration**:
- FCM Server Key

**Test Recipient**: Device token

**Example**:
```json
{
  "fcm_server_key": "your-firebase-server-key"
}
```

### 4. Telegram Bot

**Icon**: ✈️
**Configuration**:
- Bot Token

**Test Recipient**: Chat ID

**Example**:
```json
{
  "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
}
```

### 5. Discord Webhook

**Icon**: 💬
**Configuration**:
- Webhook URL

**Test Recipient**: Not required (uses webhook)

**Example**:
```json
{
  "webhook_url": "https://discord.com/api/webhooks/..."
}
```

### 6. Custom Webhook

**Icon**: 🔗
**Configuration**:
- Webhook URL
- HTTP Method (POST, PUT, PATCH)
- Custom Headers (optional)
- Timeout (seconds)

**Test Recipient**: Optional

**Example**:
```json
{
  "url": "https://your-server.com/webhook",
  "method": "POST",
  "headers": {"Authorization": "Bearer token"},
  "timeout": 10
}
```

## Setup Instructions

### Automated Setup (Recommended)

The migration script automatically generates and configures the encryption key for you!

```bash
cd opencv_surveillance
source venv/bin/activate
./venv/bin/python3 scripts/migrate_add_notification_providers.py
```

**That's it!** The script will:
1. ✅ Generate a secure encryption key automatically
2. ✅ Add it to your `.env` file
3. ✅ Create the notification_providers database table
4. ✅ Preserve existing keys if already configured

### Manual Setup (Optional)

If you need to manually generate an encryption key:

```bash
cd opencv_surveillance
./venv/bin/python3 scripts/setup_notification_encryption.py
```

Or generate manually:
```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
# Then add to .env: NOTIFICATION_ENCRYPTION_KEY=<generated-key>
```

### Restart Backend

```bash
cd opencv_surveillance
./venv/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Access Web Interface

Navigate to: **http://localhost:8000/system/notifications**

## Usage Guide

### Adding a Notification Provider

1. Navigate to **Notifications** in the sidebar
2. Click on desired provider type card
3. Fill in configuration details:
   - Provider Name (e.g., "Gmail Account")
   - Provider-specific credentials
   - Enable/disable toggle
4. Click **Create**
5. Click **Test** to verify configuration

### Testing a Provider

1. Click **Test** button on provider card
2. Enter test recipient (email, phone, chat ID, etc.)
3. Click **Send Test**
4. Check delivery status and any error messages

### Editing a Provider

1. Click **Edit** on provider card
2. Modify settings (credentials shown as `***HIDDEN***`)
3. Leave `***HIDDEN***` to keep existing value, or enter new value
4. Click **Save Changes**

### Enabling/Disabling Providers

Use the toggle switch on each provider card to enable/disable without deleting configuration.

### Deleting a Provider

1. Click **Delete** on provider card
2. Confirm deletion
3. Provider and all credentials are permanently removed

## Security Considerations

### Encryption

- **Algorithm**: Fernet (symmetric encryption with AES-128 in CBC mode)
- **Key**: Stored in `NOTIFICATION_ENCRYPTION_KEY` environment variable
- **Storage**: Encrypted credentials stored in database as base64-encoded ciphertext

### Best Practices

1. **Generate Strong Keys**: Use `Fernet.generate_key()` for encryption keys
2. **Environment Variables**: Never commit `.env` files to version control
3. **Production Keys**: Use different keys for dev/production environments
4. **Key Rotation**: Periodically regenerate encryption keys (requires re-entering all credentials)
5. **App-Specific Passwords**: Use app-specific passwords for email (not main account password)
6. **Token Permissions**: Limit permissions on API tokens (Twilio, Telegram, etc.)

### API Security

- **Authentication Required**: All endpoints require valid JWT token
- **User Isolation**: Users can only access their own providers (user_id filter)
- **Credential Masking**: API responses never include plaintext credentials
- **HTTPS Recommended**: Use HTTPS in production to encrypt transit

## Integration with Alert System

The notification providers integrate with OpenEye's existing alert system:

1. **Alert Rules** (`backend/database/alert_models.py` - `AlertConfiguration`)
   - Users configure which events trigger alerts
   - Linked to specific notification providers

2. **Notification Delivery** (`backend/core/alert_notification_system.py`)
   - Loads provider credentials from database
   - Initializes appropriate notifier (EmailNotifier, SMSNotifier, etc.)
   - Sends notifications via configured channels

3. **Usage Tracking**
   - `total_sent` incremented on successful delivery
   - `total_failed` incremented on errors
   - `last_used_at` updated on each notification

## Files Modified

### Backend

- **New**: `backend/database/alert_models.py` (added `NotificationProvider` model)
- **New**: `backend/api/schemas/notifications.py` (Pydantic schemas)
- **New**: `backend/api/routes/notification_providers.py` (API routes)
- **New**: `scripts/migrate_add_notification_providers.py` (migration script)
- **Modified**: `backend/main.py` (registered notification_providers router)

### Frontend

- **New**: `frontend/src/services/notificationService.js` (API service)
- **New**: `frontend/src/pages/NotificationSettingsPage.jsx` (UI component)
- **New**: `frontend/src/pages/NotificationSettingsPage.css` (styles)
- **Modified**: `frontend/src/App.jsx` (added route `/system/notifications`)
- **Modified**: `frontend/src/layouts/Sidebar.jsx` (added Notifications nav item, updated version to 3.7.0)

## Testing Checklist

- [ ] Database migration runs successfully
- [ ] Encryption key generates correctly
- [ ] Backend starts without errors
- [ ] Notification settings page loads
- [ ] Provider templates display correctly
- [ ] Create provider modal opens and validates fields
- [ ] Provider creation succeeds
- [ ] Test notification sends successfully
- [ ] Provider status updates after test
- [ ] Edit provider updates configuration
- [ ] Enable/disable toggle works
- [ ] Delete provider removes from list
- [ ] API masks credentials in responses
- [ ] Multiple providers of same type can be created
- [ ] Frontend handles errors gracefully

## Known Limitations

1. **Key Rotation**: Changing `NOTIFICATION_ENCRYPTION_KEY` invalidates all existing credentials
2. **Concurrent Edits**: No locking mechanism for simultaneous provider updates
3. **Batch Operations**: No bulk enable/disable or bulk testing
4. **Provider Quotas**: No built-in rate limiting or quota tracking per provider
5. **Notification Queue**: No retry mechanism for failed notifications

## Future Enhancements

- [ ] Notification templates and customization
- [ ] Scheduled notification testing
- [ ] Provider health monitoring dashboard
- [ ] Notification delivery reports
- [ ] Batch provider management
- [ ] Provider-specific rate limiting
- [ ] Automatic credential rotation
- [ ] Multi-user provider sharing
- [ ] Notification preview before sending
- [ ] Provider connection pooling

## Troubleshooting

### Error: "NOTIFICATION_ENCRYPTION_KEY not set"

**Solution**: Generate and add encryption key to `.env` file

```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
# Add output to .env as NOTIFICATION_ENCRYPTION_KEY=...
```

### Error: "Could not decrypt config"

**Cause**: Encryption key changed after providers were created

**Solution**: Delete and recreate all providers with new credentials

### Test Fails: "Authentication failed" (Email)

**Causes**:
- Incorrect username/password
- App-specific password required (Gmail)
- Less secure apps disabled

**Solution**: Enable 2FA and generate app-specific password

### Test Fails: "Invalid credentials" (Twilio)

**Causes**:
- Incorrect Account SID or Auth Token
- Phone number not verified

**Solution**: Verify credentials in Twilio console

### Provider Not Appearing

**Causes**:
- Database migration not run
- Backend restart required

**Solution**: Run migration and restart backend

## Version History

### v3.7.0 (2025-01-24)
- ✨ Added in-app notification provider configuration
- ✨ Secure credential encryption with Fernet
- ✨ Support for 6 notification types (Email, SMS, Push, Telegram, Discord, Webhook)
- ✨ Test notification functionality
- ✨ Provider usage tracking
- 🎨 Modern notification settings UI
- 📝 Comprehensive documentation

## Credits

Built with:
- **Backend**: FastAPI, SQLAlchemy, Cryptography (Fernet)
- **Frontend**: React 18, Vite
- **Notification Libraries**: python-jose, requests, smtplib

## License

Copyright (c) 2025 Mikel Smart
Part of OpenEye-OpenCV_Home_Security

---

**Need Help?** Open an issue on GitHub or consult the [API Documentation](docs/API_DOCUMENTATION.md)
