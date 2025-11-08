# Statistics Polling Alternatives - Technical Analysis

**Version:** 3.3.8  
**Date:** October 9, 2025  
**Author:** OpenEye Development Team

---

## Current Implementation: Polling

### How It Works
```javascript
// DashboardPage.jsx - Current polling implementation
useEffect(() => {
  fetchStatistics(); // Initial fetch
  const interval = setInterval(fetchStatistics, 5000); // Poll every 5 seconds
  return () => clearInterval(interval);
}, []);
```

### Pros
- ✅ Simple to implement
- ✅ Works with all browsers (no special features required)
- ✅ Easy to debug and maintain
- ✅ Server doesn't need to maintain connections
- ✅ Works behind any proxy/load balancer

### Cons
- ❌ Inefficient: Makes requests even when nothing changed
- ❌ Higher latency: Updates delayed by polling interval
- ❌ Wastes bandwidth: Repeated full responses
- ❌ Server load: Constant requests even during idle periods
- ❌ Battery drain on mobile devices

---

## Alternative 1: WebSockets (RECOMMENDED)

### How It Works
WebSockets provide **real-time, bidirectional communication** over a single TCP connection.

```python
# Backend: backend/api/routes/websocket.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import List

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    async def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast_statistics(self, data: dict):
        """Push statistics to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except:
                await self.disconnect(connection)

manager = ConnectionManager()

@router.websocket("/ws/statistics")
async def statistics_websocket(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Trigger statistics push when events occur
async def on_motion_detected(camera_id: str):
    stats = await get_current_statistics()
    await manager.broadcast_statistics(stats)
```

```javascript
// Frontend: src/services/websocketService.js
class StatisticsWebSocket {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.callbacks = [];
  }
  
  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/statistics`;
    
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    };
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.callbacks.forEach(callback => callback(data));
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket closed');
      this.attemptReconnect();
    };
  }
  
  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
      console.log(`Reconnecting in ${delay}ms...`);
      setTimeout(() => this.connect(), delay);
    }
  }
  
  subscribe(callback) {
    this.callbacks.push(callback);
  }
  
  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

export const statsWebSocket = new StatisticsWebSocket();

// DashboardPage.jsx
import { statsWebSocket } from '../services/websocketService';

useEffect(() => {
  statsWebSocket.connect();
  statsWebSocket.subscribe((data) => {
    setStatistics(data);
  });
  
  return () => {
    statsWebSocket.disconnect();
  };
}, []);
```

### Pros
- ✅ **Real-time updates**: Instant push when events occur
- ✅ **Efficient**: Only sends data when something changes
- ✅ **Low latency**: No polling delay
- ✅ **Bidirectional**: Server can push, client can request
- ✅ **Lower bandwidth**: No repeated full responses
- ✅ **Better battery life**: No constant polling
- ✅ **Event-driven**: Updates tied to actual events (motion, recording, etc.)

### Cons
- ❌ More complex to implement
- ❌ Requires WebSocket support (all modern browsers do)
- ❌ Some proxies/firewalls may block WebSocket connections
- ❌ Connection management overhead (reconnection logic)
- ❌ Server must maintain open connections

### Security Considerations
```python
# Add JWT authentication to WebSocket
@router.websocket("/ws/statistics")
async def statistics_websocket(websocket: WebSocket, token: str = Query(...)):
    try:
        payload = verify_jwt_token(token)
        await manager.connect(websocket)
        # ... rest of code
    except:
        await websocket.close(code=1008)  # Policy violation
```

---

## Alternative 2: Server-Sent Events (SSE)

### How It Works
SSE provides **one-way push** from server to client over HTTP.

```python
# Backend: backend/api/routes/sse.py
from fastapi import Request
from sse_starlette.sse import EventSourceResponse
import asyncio

@router.get("/api/statistics/stream")
async def statistics_stream(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            
            # Get current statistics
            stats = await get_current_statistics()
            
            yield {
                "event": "statistics",
                "data": json.dumps(stats)
            }
            
            # Wait for next event or timeout
            await asyncio.sleep(1)  # Check every second for changes
    
    return EventSourceResponse(event_generator())
```

```javascript
// Frontend: src/services/sseService.js
class StatisticsSSE {
  constructor() {
    this.eventSource = null;
  }
  
  connect(onMessage) {
    const token = localStorage.getItem('token');
    const url = `/api/statistics/stream?token=${token}`;
    
    this.eventSource = new EventSource(url);
    
    this.eventSource.addEventListener('statistics', (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    });
    
    this.eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      this.eventSource.close();
      // Attempt reconnect
      setTimeout(() => this.connect(onMessage), 5000);
    };
  }
  
  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
    }
  }
}

// DashboardPage.jsx
useEffect(() => {
  const sse = new StatisticsSSE();
  sse.connect((data) => {
    setStatistics(data);
  });
  
  return () => sse.disconnect();
}, []);
```

### Pros
- ✅ Simpler than WebSockets (HTTP-based)
- ✅ Automatic reconnection built-in
- ✅ Works through most proxies (uses HTTP)
- ✅ Real-time server → client updates
- ✅ Lower latency than polling

### Cons
- ❌ One-way only (server → client)
- ❌ HTTP/1.1 connection limit (6 per domain)
- ❌ Still maintains open connections
- ❌ Not as efficient as WebSockets

---

## Alternative 3: Long Polling

### How It Works
Client makes request, server holds it open until data changes or timeout.

```python
# Backend
@router.get("/api/statistics/longpoll")
async def statistics_longpoll(last_update: Optional[float] = None):
    timeout = 30  # seconds
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        current_stats = await get_current_statistics()
        
        if last_update is None or current_stats['timestamp'] > last_update:
            return current_stats
        
        await asyncio.sleep(0.5)  # Check every 500ms
    
    # Timeout - return current stats anyway
    return await get_current_statistics()
```

```javascript
// Frontend
async function longPollStatistics() {
  let lastUpdate = null;
  
  while (true) {
    try {
      const response = await axios.get(`/api/statistics/longpoll`, {
        params: { last_update: lastUpdate }
      });
      
      setStatistics(response.data);
      lastUpdate = response.data.timestamp;
    } catch (error) {
      console.error('Long poll error:', error);
      await new Promise(resolve => setTimeout(resolve, 5000));
    }
  }
}
```

### Pros
- ✅ More efficient than regular polling
- ✅ Works with standard HTTP
- ✅ Lower latency than polling

### Cons
- ❌ Still less efficient than WebSockets
- ❌ Connection overhead for each request
- ❌ Server holds connections open
- ❌ More complex than simple polling

---

## Alternative 4: GraphQL Subscriptions

### How It Works
GraphQL subscriptions use WebSockets under the hood.

```python
# Backend: backend/api/graphql.py
import strawberry
from typing import AsyncGenerator

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def statistics(self) -> AsyncGenerator[Statistics, None]:
        async for stats in statistics_stream():
            yield stats
```

```javascript
// Frontend
import { useSubscription } from '@apollo/client';

const STATISTICS_SUBSCRIPTION = gql`
  subscription OnStatisticsUpdate {
    statistics {
      totalCameras
      activeCameras
      totalRecordings
      storageUsed
    }
  }
`;

function Dashboard() {
  const { data } = useSubscription(STATISTICS_SUBSCRIPTION);
  
  return <div>{/* Display statistics */}</div>;
}
```

### Pros
- ✅ Unified GraphQL API
- ✅ Type-safe
- ✅ Real-time updates
- ✅ Flexible querying

### Cons
- ❌ Requires GraphQL setup (major change)
- ❌ More complex architecture
- ❌ Overkill for simple statistics

---

## Recommendation Matrix

| Use Case | Recommended Solution | Why |
|----------|---------------------|-----|
| **Production (Recommended)** | **WebSockets** | Best balance of efficiency, real-time updates, and complexity |
| Quick prototype | Polling | Simplest to implement |
| One-way updates only | SSE | Simpler than WebSockets |
| Maximum compatibility | Long Polling | Works everywhere |
| Full API rewrite | GraphQL Subscriptions | If rebuilding anyway |

---

## Implementation Plan for WebSockets

### Phase 1: Backend Setup (2-3 hours)
1. Install WebSocket dependencies:
   ```bash
   pip install websockets
   ```

2. Create WebSocket connection manager
3. Add WebSocket endpoint
4. Hook into existing event system:
   - Motion detection events
   - Recording start/stop
   - Face detection events
   - Camera status changes

### Phase 2: Frontend Setup (2-3 hours)
1. Create WebSocket service
2. Add reconnection logic
3. Update DashboardPage to use WebSocket
4. Add connection status indicator
5. Fallback to polling if WebSocket fails

### Phase 3: Testing (1-2 hours)
1. Test real-time updates
2. Test reconnection after network failure
3. Test authentication
4. Test with multiple simultaneous connections
5. Performance testing

### Phase 4: Deployment (1 hour)
1. Update Docker configuration
2. Update documentation
3. Add migration guide
4. Deploy and monitor

**Total Estimated Time:** 6-9 hours

---

## Code Example: Full WebSocket Implementation

### Backend Structure
```
opencv-surveillance/
├── backend/
│   ├── core/
│   │   └── websocket_manager.py  # NEW
│   ├── api/
│   │   └── routes/
│   │       └── websocket.py      # NEW
│   └── main.py                    # UPDATE
```

### Frontend Structure
```
opencv-surveillance/frontend/
├── src/
│   ├── services/
│   │   └── websocketService.js   # NEW
│   └── pages/
│       └── DashboardPage.jsx     # UPDATE
```

---

## Performance Comparison

### Current Polling (5-second interval)
- **Requests/hour:** 720
- **Bandwidth (idle):** ~360 KB/hour (assuming 500 bytes per response)
- **Latency:** 0-5 seconds
- **Server load:** Constant

### WebSocket Implementation
- **Requests/hour:** 1 (initial connection) + events
- **Bandwidth (idle):** ~1 KB/hour (just keepalive pings)
- **Latency:** <100ms
- **Server load:** Minimal when idle, spikes only on events

**Efficiency Gain:** ~99% reduction in bandwidth during idle periods!

---

## Security Best Practices

### 1. Authentication
```python
async def authenticate_websocket(websocket: WebSocket, token: str):
    try:
        payload = verify_jwt_token(token)
        return payload['user_id']
    except:
        await websocket.close(code=1008)
        return None
```

### 2. Rate Limiting
```python
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, max_connections_per_user=3):
        self.connections = defaultdict(int)
        self.max_connections = max_connections_per_user
    
    def can_connect(self, user_id: str) -> bool:
        return self.connections[user_id] < self.max_connections
    
    def add_connection(self, user_id: str):
        self.connections[user_id] += 1
    
    def remove_connection(self, user_id: str):
        self.connections[user_id] -= 1
```

### 3. Message Validation
```python
async def handle_client_message(message: str):
    try:
        data = json.loads(message)
        # Validate schema
        if not validate_message_schema(data):
            return {"error": "Invalid message format"}
        # Process message
        return await process_message(data)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON"}
```

---

## Migration Strategy

### Option A: Gradual Migration (RECOMMENDED)
1. Add WebSocket alongside existing polling
2. Feature flag to enable WebSocket for testing
3. Monitor performance and stability
4. Gradually roll out to users
5. Remove polling after successful validation

### Option B: Big Bang Migration
1. Implement WebSocket fully
2. Test thoroughly in staging
3. Deploy to production
4. Keep polling as emergency fallback

---

## Conclusion

**For OpenEye v3.4.0, I recommend implementing WebSockets** because:

1. ✅ **Significant efficiency gains**: 99% bandwidth reduction
2. ✅ **Real-time experience**: Instant updates on motion/events
3. ✅ **Better UX**: No stale data, immediate feedback
4. ✅ **Scalability**: Less server load as user base grows
5. ✅ **Modern standard**: WebSockets are widely supported and battle-tested

The implementation complexity is justified by the substantial benefits, especially as OpenEye grows in popularity and users run multiple cameras with frequent events.

---

## Additional Resources

- [MDN WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [WebSocket Security](https://owasp.org/www-community/vulnerabilities/Web_Socket_Security)
- [SSE vs WebSocket Comparison](https://ably.com/topic/server-sent-events-vs-websockets)

---

**Next Steps:**
1. Review this analysis
2. Decide on implementation approach
3. Create feature branch for WebSocket implementation
4. Schedule development time
5. Plan rollout strategy

Would you like me to start implementing the WebSocket solution for v3.4.0?
