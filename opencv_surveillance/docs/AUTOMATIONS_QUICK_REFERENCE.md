# Person-Based Automations - Quick Reference Guide

## What Are Automations?

Automations let you trigger actions automatically when specific people are detected by your camera system. For example:
- Get notified when your kids arrive home from school
- Start recording when an unknown person appears at night
- Send a webhook to your smart home system when you leave

## Getting Started

1. **Navigate to Automations**
   - Click the ⚡ **Automations** icon in the sidebar
   - Or go to: http://localhost:5173/automations

2. **Create Your First Rule**
   - Click **"Create Rule"** button
   - Fill in the form (see below)
   - Click **"Save Rule"**

## Creating a Rule

### Basic Information (Required)

| Field | Description | Example |
|-------|-------------|---------|
| **Rule Name** | Descriptive name for this rule | "Alert when John arrives" |
| **Person** | Who triggers this rule | John |
| **Cooldown Period** | How long to wait between triggers | 5 minutes |
| **Enable immediately** | Start the rule right away | ✓ Checked |

### Conditions (Optional)

Add conditions to make your rule more specific. Leave blank to trigger on every detection.

| Condition | What It Does | Example |
|-----------|--------------|---------|
| **Cameras** | Only trigger on specific cameras | Front Door, Driveway |
| **Time Range** | Only trigger during these hours | 08:00 - 18:00 |
| **Days of Week** | Only trigger on these days | Mon-Fri (work days) |
| **Confidence** | Minimum face recognition confidence | 85% |

### Actions (Required)

Choose what happens when the rule triggers. You can have multiple actions!

#### 📱 Notification
Send an alert message.
- **Message:** What to say
- **Priority:** Low, Normal, or High

#### 🎥 Record Video
Start recording on the camera.
- **Duration:** How long to record (seconds)
- **Pre-buffer:** Include footage from before detection

#### ⚡ Webhook
Send HTTP request to external service.
- **URL:** Where to send the request
- **Method:** GET, POST, or PUT

#### 🚨 Alert
Create an alert in the system.
- **Message:** Alert text
- **Type:** Person Detection, Security, or Notification

## Example Rules

### 1. Welcome Home
```
Name: Welcome Home John
Person: John
Cooldown: 1 hour
Conditions: None (always trigger)
Actions:
  - Notification: "John has arrived home" (Normal)
```

### 2. Security Alert
```
Name: Unknown Person at Night
Person: Unknown
Cooldown: 5 minutes
Conditions:
  - Cameras: Front Door, Back Door
  - Time: 22:00 - 06:00 (overnight)
  - Days: All days
  - Confidence: 90%
Actions:
  - Notification: "Security Alert!" (High)
  - Record: 60 seconds with 5 second pre-buffer
  - Alert: "Unauthorized access attempt" (Security)
```

### 3. Smart Home Integration
```
Name: Turn on lights when arriving
Person: Family Member
Cooldown: 30 minutes
Conditions:
  - Cameras: Driveway
  - Time: 17:00 - 23:00 (evening)
Actions:
  - Webhook: POST to Home Assistant
  - Notification: "Welcome home! Lights on" (Low)
```

## Managing Rules

### View Rules
- Rules are displayed as cards
- **Green badge** = Enabled
- **Gray badge** = Disabled
- Shows trigger count and last activation

### Edit a Rule
1. Click the **Edit** (pencil) icon
2. Modify any fields
3. Click **"Save Rule"**

### Enable/Disable
- Click the **Power** icon to toggle
- Disabled rules won't trigger
- Statistics are preserved

### Test a Rule
1. Click the **Play** icon
2. System simulates detection
3. Shows if rule would trigger
4. Actions are NOT executed (dry run)

### Delete a Rule
1. Click the **Trash** icon
2. Confirm deletion
3. Rule is permanently removed

## Statistics Dashboard

At the top of the page:
- **Total Rules:** How many rules you have
- **Enabled:** Currently active rules
- **Disabled:** Inactive rules
- **Total Triggers:** How many times rules have fired

## Understanding Cooldown

Cooldown prevents spam from repeated detections:
- Person detected → Rule triggers
- Rule enters cooldown period
- Detections during cooldown are ignored
- After cooldown expires → Rule can trigger again

**Example:**
- John walks past camera 5 times in 1 minute
- Cooldown set to 5 minutes
- Rule triggers once (first detection)
- Ignores next 4 detections
- Can trigger again after 5 minutes

## Tips & Best Practices

### 1. Start Simple
- Create basic rules first
- Test them before adding conditions
- Gradually add complexity

### 2. Use Descriptive Names
- ✅ Good: "Alert when kids arrive after school"
- ❌ Bad: "Rule 1"

### 3. Set Appropriate Cooldowns
- **Short (1-5 min):** Security alerts
- **Medium (30-60 min):** Arrival/departure
- **Long (1+ hour):** Daily notifications

### 4. Test Before Enabling
- Click the test button
- Verify conditions are correct
- Check action configuration
- Enable when satisfied

### 5. Use Conditions Wisely
- Camera filter: Focus on relevant areas
- Time range: Avoid nighttime notifications
- Days of week: Work vs weekend patterns
- Confidence: Balance accuracy vs false negatives

### 6. Combine Actions
Multiple actions make rules powerful:
- Notification + Record (evidence)
- Alert + Webhook (integration)
- Multiple notifications (different priority)

## Troubleshooting

### Rule Not Triggering

**Check:**
1. Is rule enabled? (Power icon should be green)
2. Is cooldown active? (Check last trigger time)
3. Are conditions too restrictive?
4. Is confidence threshold too high?
5. Is person in face database?

**Solution:** Click test button to see what's blocking

### Too Many Triggers

**Problem:** Getting spammed with notifications

**Solutions:**
- Increase cooldown period
- Add time range condition
- Add camera filter
- Increase confidence threshold

### Rule Triggers on Wrong Person

**Problem:** Rule fires for similar-looking people

**Solutions:**
- Increase confidence threshold
- Add more training photos
- Re-train face recognition model

### Actions Not Executing

**Note:** Some actions require system integration:
- Notifications need notification service
- Recording needs camera recording enabled
- Webhooks need network access
- Check server logs for errors

## Advanced Features

### Overnight Time Ranges
Time ranges that cross midnight work automatically:
- **22:00 - 06:00** → From 10 PM to 6 AM
- Triggers: 11 PM, 2 AM, 5 AM ✓
- Skips: 8 AM, 3 PM, 9 PM ✗

### Multiple Camera Filtering
Select multiple cameras for broad coverage:
- Front Door + Driveway = "Arrival detection"
- Back Door + Side Gate = "Perimeter security"

### Weekday/Weekend Patterns
Use days of week for scheduling:
- **Mon-Fri (0-4):** Work schedule
- **Sat-Sun (5-6):** Weekend mode
- **Mon-Wed-Fri (0,2,4):** Custom pattern

### Webhook Integration
Connect to external services:
- Home Assistant
- IFTTT
- Custom APIs
- Smart home devices

**Payload sent:**
```json
{
  "person_name": "John",
  "camera_id": "front_door",
  "timestamp": "2025-10-17T12:34:56",
  "event_type": "person_detected"
}
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `C` | Create new rule |
| `Esc` | Close modal |
| `Enter` | Save rule (when in form) |

## API Access

Developers can access the automation API:
- **Base URL:** `http://localhost:8000/api/automations/`
- **Docs:** http://localhost:8000/docs
- **Authentication:** Required (existing auth system)

## Need Help?

1. **Check Documentation:**
   - `docs/PERSON_AUTOMATIONS_IMPLEMENTATION.md`
   - Full technical reference

2. **View Logs:**
   - Backend logs show automation execution
   - Look for "automation" in log messages

3. **Test Mode:**
   - Use test button liberally
   - No side effects, safe to experiment

4. **Statistics:**
   - View trigger counts
   - Check last trigger times
   - Monitor rule usage

---

## Quick Reference Card

```
┌─────────────────────────────────────────┐
│     Person-Based Automations            │
├─────────────────────────────────────────┤
│  CREATE RULE:                           │
│    1. Name it                           │
│    2. Select person                     │
│    3. Add conditions (optional)         │
│    4. Add actions (required)            │
│    5. Set cooldown                      │
│    6. Test it                           │
│    7. Enable it                         │
│                                         │
│  MANAGE RULES:                          │
│    ✏️  Edit    ⚡ Toggle                │
│    🗑️  Delete  ▶️  Test                 │
│                                         │
│  ACTION TYPES:                          │
│    📱 Notification  🎥 Record           │
│    ⚡ Webhook       🚨 Alert            │
│                                         │
│  CONDITIONS:                            │
│    📹 Cameras      🕐 Time Range       │
│    📅 Days         🎯 Confidence       │
└─────────────────────────────────────────┘
```

**Happy Automating!** 🚀
