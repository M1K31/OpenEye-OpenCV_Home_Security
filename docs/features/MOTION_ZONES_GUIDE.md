# Motion Detection Zones Guide (v3.6.2+)

## Overview

Motion Detection Zones allow you to define specific areas in your camera's field of view for targeted motion detection. This powerful feature enables you to:

- **Focus on important areas** - Only detect motion where it matters (e.g., doorways, driveways)
- **Exclude busy zones** - Ignore motion in areas with constant activity (e.g., trees, roads)
- **Fine-tune sensitivity** - Apply different sensitivity multipliers per zone
- **Reduce false positives** - Dramatically improve motion detection accuracy

## Key Concepts

### Zone Types

1. **Inclusion Zones** (Default)
   - Motion is **only detected** within these zones
   - Perfect for focusing on specific areas of interest
   - Example: Doorway detection zone

2. **Exclusion Zones**
   - Motion **is ignored** within these zones
   - Perfect for filtering out irrelevant motion
   - Example: Busy street or tree branches

### Coordinate System

Zones use **normalized coordinates** (0.0 to 1.0) which are:
- **Resolution-independent** - Work across any camera resolution
- **Portable** - Zones remain valid if camera resolution changes
- **Precise** - Coordinates are converted to pixels at runtime

Example:
- `x: 0.5, y: 0.5` = Center of frame
- `x: 0.0, y: 0.0` = Top-left corner
- `x: 1.0, y: 1.0` = Bottom-right corner

## How to Use Motion Zones

### Step 1: Access Zone Editor

1. Navigate to **Camera Management** page
2. Find the camera you want to configure
3. Click the **"📍 Zones"** button on the camera card

### Step 2: Draw Your First Zone

1. **Enter zone name** - Give it a descriptive name (e.g., "Front Door")
2. **Choose zone color** - Pick a color for visualization
3. **Set sensitivity** - Use slider to adjust (0.1x to 10.0x)
4. **Click "Start Drawing Zone"**
5. **Click on canvas** to add polygon points (minimum 3 points)
6. **Click "Finish Zone"** to save

### Step 3: Configure Zone Properties

**Sensitivity Multiplier:**
- `< 1.0` = Less sensitive (larger motion required)
- `= 1.0` = Normal sensitivity (default)
- `> 1.0` = More sensitive (smaller motion detected)

**Exclusion Zone:**
- Check this box to make the zone ignore motion
- Useful for filtering out trees, roads, busy areas

### Step 4: Manage Existing Zones

- **View zones** - See all zones in the sidebar
- **Toggle active/inactive** - Click 👁️ or 🚫 icon
- **Delete zone** - Click 🗑️ icon
- **Select zone** - Click zone in list to highlight on canvas

## Use Cases & Examples

### Example 1: Doorway Monitoring

**Goal:** Only detect motion near the front door

1. Create inclusion zone covering doorway area
2. Draw polygon around door (30-50% of frame)
3. Set sensitivity to 1.5x for better detection
4. Result: Motion only triggers when someone approaches door

### Example 2: Driveway with Busy Street

**Goal:** Detect cars in driveway, ignore traffic on street

1. Create **inclusion zone** covering driveway
2. Create **exclusion zone** covering street area
3. Result: Street traffic ignored, driveway motion detected

### Example 3: Tree Branch Filtering

**Goal:** Ignore swaying tree branches in corner

1. Create **exclusion zone** over tree area
2. Result: Wind-blown branches don't trigger motion

### Example 4: Multi-Zone Coverage

**Goal:** Monitor multiple entrances with different sensitivity

1. Create zone 1 for main entrance (sensitivity 1.0x)
2. Create zone 2 for side door (sensitivity 2.0x - more sensitive)
3. Result: Each entrance monitored with appropriate settings

## Technical Details

### Zone Filtering Logic

The motion detector applies zones in this order:

1. **Detect motion** - Background subtraction finds moving objects
2. **Find contours** - OpenCV identifies motion areas
3. **Apply exclusion zones** - Remove contours in exclusion zones
4. **Apply inclusion zones** - Keep only contours in inclusion zones
5. **Update statistics** - Increment event count for triggered zones

### Point-in-Polygon Algorithm

The system uses OpenCV's `pointPolygonTest()` to determine if motion contours intersect with zones:

```python
# Convert normalized zone coordinates to pixels
zone_points = [(x * width, y * height) for x, y in zone['coordinates']]

# Check if contour centroid is inside polygon
result = cv2.pointPolygonTest(zone_polygon, contour_centroid, False)

# result >= 0 means inside or on edge
if result >= 0:
    motion_is_in_zone = True
```

### Zone Statistics

Each zone tracks:
- **motion_events_count** - Total motion detections in this zone
- **last_motion_at** - Timestamp of most recent detection

Statistics are displayed in the zone list sidebar and updated in real-time.

### Database Schema

```sql
CREATE TABLE motion_zones (
    id INTEGER PRIMARY KEY,
    camera_id TEXT NOT NULL,
    name TEXT NOT NULL,
    zone_type TEXT DEFAULT 'polygon',
    coordinates TEXT NOT NULL,  -- JSON array of {x, y}
    is_active BOOLEAN DEFAULT TRUE,
    is_exclusion_zone BOOLEAN DEFAULT FALSE,
    sensitivity_multiplier REAL DEFAULT 1.0,
    color TEXT DEFAULT '#00FF00',
    opacity REAL DEFAULT 0.3,
    motion_events_count INTEGER DEFAULT 0,
    last_motion_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## API Reference

### List Camera Zones

```http
GET /api/cameras/{camera_id}/zones?include_inactive=false
```

Response:
```json
{
  "camera_id": "front_door",
  "zones": [
    {
      "id": 1,
      "name": "Doorway Zone",
      "zone_type": "polygon",
      "coordinates": "[{\"x\":0.3,\"y\":0.3},{\"x\":0.7,\"y\":0.3}...]",
      "is_active": true,
      "is_exclusion_zone": false,
      "sensitivity_multiplier": 1.5,
      "color": "#00FF00",
      "motion_events_count": 42,
      "last_motion_at": "2025-10-26T12:00:00Z"
    }
  ],
  "total": 1
}
```

### Create Zone

```http
POST /api/cameras/{camera_id}/zones
Content-Type: application/json

{
  "name": "Front Door",
  "zone_type": "polygon",
  "coordinates": "[{\"x\":0.3,\"y\":0.3},{\"x\":0.7,\"y\":0.3},{\"x\":0.7,\"y\":0.7},{\"x\":0.3,\"y\":0.7}]",
  "is_active": true,
  "is_exclusion_zone": false,
  "sensitivity_multiplier": 1.0,
  "color": "#00FF00",
  "opacity": 0.3
}
```

### Update Zone

```http
PUT /api/cameras/{camera_id}/zones/{zone_id}
Content-Type: application/json

{
  "sensitivity_multiplier": 2.0,
  "is_active": true
}
```

### Delete Zone

```http
DELETE /api/cameras/{camera_id}/zones/{zone_id}
```

### Toggle Zone Active Status

```http
POST /api/cameras/{camera_id}/zones/{zone_id}/toggle
```

## Best Practices

### Zone Design

1. **Start simple** - Begin with one or two zones
2. **Test and iterate** - Monitor a zone for a day before adding more
3. **Use exclusion zones sparingly** - Only for persistent false positives
4. **Keep polygons simple** - 3-6 points is usually enough
5. **Don't overlap inclusion zones** - Can cause duplicate detections

### Sensitivity Tuning

1. **Start with 1.0x** - Default sensitivity
2. **Increase for small motion** - Use 1.5x - 2.0x for distant objects
3. **Decrease for large areas** - Use 0.5x - 0.8x to reduce noise
4. **Monitor statistics** - Check motion_events_count to gauge effectiveness

### Performance Considerations

1. **Limit zone count** - Each zone adds processing overhead
2. **Keep zones active** - Inactive zones still load but don't filter
3. **Use exclusion zones to reduce processing** - Fewer contours = faster detection

## Troubleshooting

### Motion not detected in zone

**Possible causes:**
- Zone sensitivity too low - Increase multiplier
- Zone polygon doesn't cover motion area - Redraw zone
- Temporal filter blocking detection - Wait for 2-3 consecutive frames
- Motion too small - Increase global motion sensitivity

**Solution:**
1. Check zone statistics to see if events are being counted
2. Temporarily disable temporal filtering for testing
3. Verify zone coordinates cover the intended area

### Too many false positives

**Possible causes:**
- Zone sensitivity too high - Decrease multiplier
- No exclusion zones for busy areas - Add exclusion zones
- Zone too large - Make zone more specific

**Solution:**
1. Add exclusion zones for trees, roads, shadows
2. Reduce sensitivity multiplier to 0.5x - 0.8x
3. Make inclusion zones smaller and more focused

### Zones not loading

**Possible causes:**
- Camera not started - Zones only load when camera starts
- Database connection issue - Check logs
- Invalid zone coordinates - Verify JSON format

**Solution:**
1. Restart camera via Camera Management page
2. Check backend logs for errors
3. Verify zones exist in database: `SELECT * FROM motion_zones WHERE camera_id='...'`

## Migration from Grid-Based Zones

If you were using the legacy grid-based zone system:

**Old system (Grid):**
```json
{
  "width": 8,
  "height": 6,
  "zones": [[1,1,1,0,0,0,0,0], ...]
}
```

**New system (Polygon):**
```json
[
  {"x": 0.0, "y": 0.0},
  {"x": 0.375, "y": 0.0},
  {"x": 0.375, "y": 0.33},
  {"x": 0.0, "y": 0.33}
]
```

**Benefits of new system:**
- More precise control (pixel-level vs grid-level)
- Unlimited zone complexity (not limited to rectangles)
- Better visualization (actual polygons vs grid overlay)
- Per-zone statistics tracking

## Changelog

### v3.6.2 - Initial Release (October 2025)

**Added:**
- Polygon-based motion zones with database storage
- Interactive canvas zone drawing UI
- Zone CRUD API endpoints
- Point-in-polygon motion filtering
- Per-zone sensitivity multipliers
- Zone statistics tracking (event count, last motion time)
- Inclusion/exclusion zone support

**Changed:**
- Motion detector now loads zones from database on camera start
- Zones integrated into camera management workflow

**Deprecated:**
- Legacy grid-based zone system (still supported for backward compatibility)

## Additional Resources

- **API Documentation**: See `docs/API_DOCUMENTATION.md`
- **Testing Guide**: Run `test_motion_zones.py` for comprehensive tests
- **Example Code**: See `backend/core/motion_detector.py` for implementation

## Support

If you encounter issues or have questions:

1. Check backend logs: `logs/backend.log`
2. Run test suite: `./venv/bin/python3 test_motion_zones.py`
3. File an issue: https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues

---

**Version**: 3.6.2
**Last Updated**: October 26, 2025
**Author**: OpenEye Development Team
