#!/bin/bash
# Test Apple HIG Accessibility Settings API
# OpenEye v3.5.3

echo "🧪 Testing Apple HIG Accessibility Settings API"
echo "================================================"
echo ""

# Base URL
BASE_URL="http://localhost:8000/api"

# Login first to get token
echo "📝 Step 1: Login to get auth token..."
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin")

TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "❌ Login failed. Make sure server is running and credentials are correct."
  exit 1
fi

echo "✅ Login successful"
echo ""

# Test 1: Get current settings
echo "📥 Step 2: Get current settings..."
GET_RESPONSE=$(curl -s -X GET "$BASE_URL/settings" \
  -H "Authorization: Bearer $TOKEN")

echo "Current settings:"
echo "$GET_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$GET_RESPONSE"
echo ""

# Test 2: Update with reduce_motion
echo "📤 Step 3: Enable reduce_motion setting..."
UPDATE_RESPONSE=$(curl -s -X PATCH "$BASE_URL/settings" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reduce_motion": true}')

echo "Update response:"
echo "$UPDATE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$UPDATE_RESPONSE"
echo ""

# Test 3: Update multiple accessibility settings
echo "📤 Step 4: Enable all accessibility features..."
UPDATE_ALL=$(curl -s -X PATCH "$BASE_URL/settings" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reduce_motion": true,
    "use_8pt_grid": true,
    "enhanced_touch_targets": true,
    "show_focus_indicators": true
  }')

echo "Update response:"
echo "$UPDATE_ALL" | python3 -m json.tool 2>/dev/null || echo "$UPDATE_ALL"
echo ""

# Test 4: Verify settings persisted
echo "🔍 Step 5: Verify settings persisted..."
VERIFY_RESPONSE=$(curl -s -X GET "$BASE_URL/settings" \
  -H "Authorization: Bearer $TOKEN")

echo "Final settings:"
echo "$VERIFY_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$VERIFY_RESPONSE"
echo ""

# Check if accessibility settings are present
if echo "$VERIFY_RESPONSE" | grep -q "reduce_motion"; then
  echo "✅ SUCCESS: reduce_motion setting found in response"
else
  echo "❌ FAIL: reduce_motion setting not found in response"
fi

if echo "$VERIFY_RESPONSE" | grep -q "use_8pt_grid"; then
  echo "✅ SUCCESS: use_8pt_grid setting found in response"
else
  echo "❌ FAIL: use_8pt_grid setting not found in response"
fi

if echo "$VERIFY_RESPONSE" | grep -q "enhanced_touch_targets"; then
  echo "✅ SUCCESS: enhanced_touch_targets setting found in response"
else
  echo "❌ FAIL: enhanced_touch_targets setting not found in response"
fi

if echo "$VERIFY_RESPONSE" | grep -q "show_focus_indicators"; then
  echo "✅ SUCCESS: show_focus_indicators setting found in response"
else
  echo "❌ FAIL: show_focus_indicators setting not found in response"
fi

echo ""
echo "================================================"
echo "✅ API Test Complete!"
echo ""
echo "Next Steps:"
echo "1. Open browser to http://localhost:8000"
echo "2. Navigate to System & Alerts → System tab"
echo "3. Scroll to 'UI Accessibility (Apple HIG)' section"
echo "4. Toggle accessibility settings and click Save"
echo "5. Refresh page to verify settings persist"
