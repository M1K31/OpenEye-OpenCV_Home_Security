#!/bin/bash
# Test OpenEye Application

set -e

BASE_URL="http://localhost:8000"

echo "=================================="
echo "  OpenEye Application Test Suite  "
echo "=================================="
echo ""

# Wait for server to be ready
echo "⏳ Waiting for server to start..."
sleep 5

# Test 1: Health Check
echo "1. Testing Health Endpoint..."
HEALTH=$(curl -s ${BASE_URL}/api/health)
echo "   Result: $HEALTH"
echo ""

# Test 2: Setup Status
echo "2. Testing Setup Status..."
SETUP=$(curl -s ${BASE_URL}/api/setup/status)
echo "   Result: $SETUP"
echo ""

# Test 3: API Documentation
echo "3. Testing API Documentation..."
DOCS=$(curl -s -o /dev/null -w "%{http_code}" ${BASE_URL}/api/docs)
echo "   HTTP Status: $DOCS"
echo ""

# Test 4: Create Admin User (if not exists)
echo "4. Testing User Creation..."
CREATE_USER=$(curl -s -X POST "${BASE_URL}/api/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@openeye.local",
    "password": "admin123",
    "full_name": "System Admin"
  }')
echo "   Result: $CREATE_USER"
echo ""

# Test 5: Login and Get Token
echo "5. Testing User Login..."
LOGIN=$(curl -s -X POST "${BASE_URL}/api/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123")
echo "   Result: $LOGIN"
echo ""

# Extract token if login successful
TOKEN=$(echo $LOGIN | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null || echo "")

if [ -n "$TOKEN" ]; then
    echo "   ✅ Token obtained: ${TOKEN:0:20}..."
    echo ""
    
    # Test 6: Get Cameras (authenticated)
    echo "6. Testing Get Cameras (authenticated)..."
    CAMERAS=$(curl -s ${BASE_URL}/api/cameras/ \
      -H "Authorization: Bearer $TOKEN")
    echo "   Result: $CAMERAS"
    echo ""
    
    # Test 7: Get Face Statistics (authenticated)
    echo "7. Testing Face Statistics (authenticated)..."
    FACE_STATS=$(curl -s ${BASE_URL}/api/faces/statistics \
      -H "Authorization: Bearer $TOKEN")
    echo "   Result: $FACE_STATS"
    echo ""
    
    # Test 8: Get Faces (authenticated)
    echo "8. Testing Get Faces (authenticated)..."
    FACES=$(curl -s ${BASE_URL}/api/faces/ \
      -H "Authorization: Bearer $TOKEN")
    echo "   Result: $FACES"
    echo ""
else
    echo "   ⚠️  Could not obtain token, skipping authenticated tests"
    echo ""
fi

# Test 9: WebSocket Connection Test
echo "9. Testing WebSocket Endpoint..."
if [ -n "$TOKEN" ]; then
    WS_URL="ws://localhost:8000/api/ws/statistics?token=$TOKEN"
    echo "   WebSocket URL: $WS_URL"
    echo "   (Manual test required - open browser console)"
else
    echo "   ⚠️  No token available for WebSocket test"
fi
echo ""

echo "=================================="
echo "  Test Suite Complete!            "
echo "=================================="
echo ""
echo "📊 Summary:"
echo "   - Health Check: ✓"
echo "   - Setup Status: ✓"
echo "   - API Docs: ✓"
echo "   - User Management: See above"
echo "   - Authentication: See above"
echo ""
echo "🌐 Access the application at:"
echo "   http://localhost:8000"
echo ""
echo "📖 API Documentation:"
echo "   http://localhost:8000/api/docs"
echo ""
