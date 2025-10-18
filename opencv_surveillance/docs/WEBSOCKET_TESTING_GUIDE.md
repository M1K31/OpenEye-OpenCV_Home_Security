# WebSocket Testing Guide

## Overview

This guide provides comprehensive testing procedures for the OpenEye WebSocket implementation, including manual testing, automated testing, and troubleshooting.

## Prerequisites

- OpenEye v3.4.0 or higher running
- Valid JWT authentication token
- Browser with WebSocket support (Chrome, Firefox, Safari, Edge)
- Python 3.8+ (for automated testing)

## Manual Testing

### 1. Browser Developer Tools Test

#### Step 1: Open Browser Console
1. Navigate to OpenEye dashboard (http://localhost:3000)
2. Open Developer Tools (F12 or Cmd+Option+I)
3. Go to Console tab

#### Step 2: Check WebSocket Connection
```javascript
// Check if WebSocketService is connected
wsService.getStatus()
// Expected: "connected", "connecting", "disconnected", or "error"

// Check connection details
wsService.isConnected()
// Expected: true or false
```

#### Step 3: Monitor WebSocket Traffic
1. Go to Network tab in Developer Tools
2. Filter by "WS" or "WebSocket"
3. Click on the WebSocket connection
4. View "Messages" tab to see real-time traffic

Expected messages every 5 seconds:
```json
{
  "type": "statistics_update",
  "timestamp": "2025-10-10T12:00:00.000Z",
  "data": { ... }
}
```

#### Step 4: Test Reconnection
1. In Console, disconnect WebSocket:
```javascript
wsService.disconnect()
```
2. Wait 3 seconds
3. Reconnect:
```javascript
const token = localStorage.getItem('token');
wsService.connect(token);
```
4. Verify reconnection successful in Network tab

#### Step 5: Test Fallback to Polling
1. Stop the backend server
2. Observe connection status indicator changes to "Polling"
3. Restart backend server
4. Observe automatic reconnection to WebSocket

### 2. Visual Testing

#### Connection Status Indicator
- **🟢 Live**: WebSocket connected and receiving updates
- **🟡 Connecting**: Attempting to establish WebSocket connection
- **🔵 Polling**: Using HTTP polling fallback

#### Real-Time Updates Test
1. Add a new person to face recognition
2. Observe statistics update within 5 seconds without page refresh
3. Check that "Total People" count increases

#### Multi-Tab Test
1. Open OpenEye in multiple browser tabs
2. Verify each tab maintains its own WebSocket connection
3. Check connection count:
```javascript
// In any tab
fetch('/api/ws/status', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('token')}`
  }
})
.then(r => r.json())
.then(console.log)
```

Expected:
```json
{
  "status": "operational",
  "statistics": {
    "total_connections": 2,
    "total_users": 1,
    "connections_by_user": { "1": 2 }
  },
  "user_connections": 2
}
```

## Automated Testing

### 1. Python WebSocket Client Test

Create a test file `test_websocket.py`:

```python
#!/usr/bin/env python3
"""
OpenEye WebSocket Test Client
"""

import asyncio
import json
import websockets
from datetime import datetime

# Configuration
WS_URL = "ws://localhost:8000/api/ws/statistics"
JWT_TOKEN = "your-jwt-token-here"  # Get from browser localStorage

async def test_websocket_connection():
    """Test WebSocket connection and message receiving."""
    url = f"{WS_URL}?token={JWT_TOKEN}"
    
    print(f"Connecting to {WS_URL}...")
    
    try:
        async with websockets.connect(url) as websocket:
            print("✓ Connected successfully")
            
            # Wait for welcome message
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            print(f"✓ Received welcome message: {welcome_data['type']}")
            assert welcome_data['type'] == 'connection_status'
            
            # Receive statistics updates (10 times)
            for i in range(10):
                message = await websocket.recv()
                data = json.loads(message)
                
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Message {i+1}:")
                print(f"  Type: {data['type']}")
                
                if data['type'] == 'statistics_update':
                    stats = data['data']
                    print(f"  People: {stats.get('face_recognition', {}).get('total_people', 0)}")
                    print(f"  Recognitions Today: {stats.get('face_recognition', {}).get('recognitions_today', 0)}")
                    print(f"  Cameras: {stats.get('cameras', {}).get('total_cameras', 0)}")
            
            print("\n✓ All messages received successfully")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"✗ Connection failed: {e}")
        print("  Check: Is the token valid?")
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")

async def test_ping_pong():
    """Test ping/pong keep-alive."""
    url = f"{WS_URL}?token={JWT_TOKEN}"
    
    print("Testing ping/pong...")
    
    async with websockets.connect(url) as websocket:
        # Wait for welcome
        await websocket.recv()
        
        # Send ping
        ping_message = {
            "type": "ping",
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send(json.dumps(ping_message))
        print("✓ Ping sent")
        
        # Wait for pong
        for _ in range(10):  # Check next 10 messages
            message = await websocket.recv()
            data = json.loads(message)
            if data['type'] == 'pong':
                print("✓ Pong received")
                return
        
        print("✗ Pong not received")

async def test_rate_limiting():
    """Test connection rate limiting."""
    print("Testing rate limiting (max 5 connections)...")
    
    connections = []
    url = f"{WS_URL}?token={JWT_TOKEN}"
    
    try:
        # Try to open 6 connections
        for i in range(6):
            ws = await websockets.connect(url)
            connections.append(ws)
            print(f"✓ Connection {i+1} established")
            
            # Wait for welcome message
            await ws.recv()
    except websockets.exceptions.InvalidStatusCode as e:
        if e.status_code == 1008:  # Policy Violation
            print(f"✓ Rate limit enforced correctly (connection {len(connections) + 1} rejected)")
        else:
            print(f"✗ Unexpected error: {e}")
    finally:
        # Close all connections
        for ws in connections:
            await ws.close()
        print(f"✓ Closed {len(connections)} connections")

async def test_reconnection():
    """Test automatic reconnection."""
    print("Testing reconnection...")
    
    url = f"{WS_URL}?token={JWT_TOKEN}"
    
    async with websockets.connect(url) as websocket:
        print("✓ Initial connection established")
        
        # Wait for welcome
        await websocket.recv()
        
        # Close connection
        await websocket.close()
        print("✓ Connection closed")
    
    # Wait and reconnect
    await asyncio.sleep(2)
    
    async with websockets.connect(url) as websocket:
        print("✓ Reconnection successful")
        await websocket.recv()

async def main():
    """Run all tests."""
    print("=" * 60)
    print("OpenEye WebSocket Test Suite")
    print("=" * 60)
    
    tests = [
        ("Connection and Messages", test_websocket_connection),
        ("Ping/Pong Keep-Alive", test_ping_pong),
        ("Rate Limiting", test_rate_limiting),
        ("Reconnection", test_reconnection),
    ]
    
    for name, test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"Test: {name}")
        print("=" * 60)
        try:
            await test_func()
            print(f"✓ {name} PASSED")
        except Exception as e:
            print(f"✗ {name} FAILED: {e}")
        print()
    
    print("=" * 60)
    print("Test Suite Complete")
    print("=" * 60)

if __name__ == "__main__":
    print("\nNote: Replace JWT_TOKEN with a valid token from browser localStorage")
    print("Get token by running in browser console: localStorage.getItem('token')\n")
    asyncio.run(main())
```

### 2. Run the Test

```bash
# Install websockets library
pip install websockets

# Get JWT token from browser console
# localStorage.getItem('token')

# Update JWT_TOKEN in test_websocket.py

# Run tests
python test_websocket.py
```

### 3. Expected Output

```
===========================================================
OpenEye WebSocket Test Suite
===========================================================

===========================================================
Test: Connection and Messages
===========================================================
Connecting to ws://localhost:8000/api/ws/statistics...
✓ Connected successfully
✓ Received welcome message: connection_status

[12:00:00] Message 1:
  Type: statistics_update
  People: 5
  Recognitions Today: 42
  Cameras: 2

[12:00:05] Message 2:
  Type: statistics_update
  People: 5
  Recognitions Today: 42
  Cameras: 2

...

✓ All messages received successfully
✓ Connection and Messages PASSED

===========================================================
Test: Ping/Pong Keep-Alive
===========================================================
Testing ping/pong...
✓ Ping sent
✓ Pong received
✓ Ping/Pong Keep-Alive PASSED

===========================================================
Test: Rate Limiting
===========================================================
Testing rate limiting (max 5 connections)...
✓ Connection 1 established
✓ Connection 2 established
✓ Connection 3 established
✓ Connection 4 established
✓ Connection 5 established
✓ Rate limit enforced correctly (connection 6 rejected)
✓ Closed 5 connections
✓ Rate Limiting PASSED

===========================================================
Test: Reconnection
===========================================================
Testing reconnection...
✓ Initial connection established
✓ Connection closed
✓ Reconnection successful
✓ Reconnection PASSED

===========================================================
Test Suite Complete
===========================================================
```

## Load Testing

### Apache Bench WebSocket Test

Create `ws_load_test.py`:

```python
#!/usr/bin/env python3
"""Load test for WebSocket connections."""

import asyncio
import websockets
import time
from datetime import datetime

JWT_TOKEN = "your-jwt-token-here"
WS_URL = f"ws://localhost:8000/api/ws/statistics?token={JWT_TOKEN}"
CONCURRENT_CONNECTIONS = 10
DURATION_SECONDS = 60

async def connection_worker(worker_id, stats):
    """Worker that maintains a WebSocket connection."""
    try:
        async with websockets.connect(WS_URL) as websocket:
            stats['connected'] += 1
            print(f"Worker {worker_id}: Connected")
            
            start_time = time.time()
            message_count = 0
            
            while time.time() - start_time < DURATION_SECONDS:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10)
                    message_count += 1
                    stats['messages_received'] += 1
                except asyncio.TimeoutError:
                    print(f"Worker {worker_id}: Timeout")
                    break
            
            stats['avg_messages_per_connection'] += message_count
            print(f"Worker {worker_id}: Received {message_count} messages")
            
    except Exception as e:
        stats['errors'] += 1
        print(f"Worker {worker_id}: Error - {e}")

async def main():
    """Run load test."""
    stats = {
        'connected': 0,
        'messages_received': 0,
        'avg_messages_per_connection': 0,
        'errors': 0
    }
    
    print(f"Starting load test:")
    print(f"  Concurrent connections: {CONCURRENT_CONNECTIONS}")
    print(f"  Duration: {DURATION_SECONDS} seconds")
    print()
    
    start_time = time.time()
    
    # Create workers
    workers = [
        connection_worker(i, stats)
        for i in range(CONCURRENT_CONNECTIONS)
    ]
    
    # Run all workers
    await asyncio.gather(*workers)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Print results
    print("\n" + "=" * 60)
    print("Load Test Results")
    print("=" * 60)
    print(f"Duration: {duration:.2f} seconds")
    print(f"Connections: {stats['connected']}/{CONCURRENT_CONNECTIONS}")
    print(f"Total Messages: {stats['messages_received']}")
    print(f"Messages/Connection: {stats['avg_messages_per_connection'] / max(stats['connected'], 1):.1f}")
    print(f"Messages/Second: {stats['messages_received'] / duration:.2f}")
    print(f"Errors: {stats['errors']}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
```

Run with:
```bash
python ws_load_test.py
```

## Troubleshooting Guide

### Issue: Connection Fails with 403 Forbidden

**Cause**: Invalid or expired JWT token

**Solution**:
1. Get fresh token from browser: `localStorage.getItem('token')`
2. Update token in test script
3. Check token hasn't expired (default: 30 days)

### Issue: Connection Drops After 30 Seconds

**Cause**: Missing ping/pong keep-alive

**Solution**:
- Check WebSocketService is sending pings every 30 seconds
- Verify backend responds with pongs
- Check for network issues or proxies dropping idle connections

### Issue: Rate Limit Exceeded (Connection 6+ Rejected)

**Cause**: More than 5 connections per user

**Solution**:
1. Close unused browser tabs
2. Disconnect old connections before creating new ones
3. Or increase max_connections_per_user in WebSocketConnectionManager

### Issue: Statistics Not Updating

**Cause**: StatisticsBroadcaster not running

**Solution**:
1. Check backend logs for "Statistics broadcaster started"
2. Verify startup_event is being called
3. Check for errors in statistics collection

### Issue: High CPU Usage on Server

**Cause**: Too many connections or frequent broadcasts

**Solution**:
1. Reduce broadcast frequency (default: 5 seconds)
2. Implement connection pooling
3. Optimize statistics collection queries

### Issue: WebSocket Shows as Pending in Browser

**Cause**: Backend not responding to WebSocket upgrade request

**Solution**:
1. Check backend is running
2. Verify WebSocket routes are registered in main.py
3. Check for reverse proxy configuration issues (nginx, apache)

## Best Practices

1. **Always use WSS in production** (WebSocket Secure over TLS)
2. **Implement proper error handling** in message listeners
3. **Monitor connection counts** and set alerts for anomalies
4. **Use ping/pong** for keep-alive (every 30 seconds)
5. **Implement exponential backoff** for reconnection attempts
6. **Fallback to HTTP polling** if WebSocket unavailable
7. **Clean up event listeners** when components unmount
8. **Log all connection lifecycle events** for debugging
9. **Set appropriate timeouts** for message waits
10. **Test with multiple clients** and browsers

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: WebSocket Tests

on: [push, pull_request]

jobs:
  websocket-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Start OpenEye
        run: |
          docker-compose up -d
          sleep 10
      
      - name: Install dependencies
        run: pip install websockets requests
      
      - name: Get JWT token
        run: |
          TOKEN=$(curl -X POST http://localhost:8000/api/login \
            -H "Content-Type: application/json" \
            -d '{"username":"admin","password":"admin"}' \
            | jq -r '.access_token')
          echo "JWT_TOKEN=$TOKEN" >> $GITHUB_ENV
      
      - name: Run WebSocket tests
        run: python test_websocket.py
      
      - name: Cleanup
        if: always()
        run: docker-compose down
```

## Conclusion

This guide covers all aspects of WebSocket testing for OpenEye. For issues not covered here, check the main documentation or open an issue on GitHub.
