# Process Cleanup Issue - Service Not Stopping Properly

**Date**: October 13, 2025  
**Issue**: Python services remain running after server shutdown, requiring force quit  
**Severity**: High - Causes port conflicts and resource leaks

---

## 🐛 Problem Identified

### Symptoms
- Server appears to shut down but processes remain active
- `ps aux | grep python` shows orphaned processes
- Port 8000 remains occupied after shutdown
- Need to manually `pkill` or force quit processes
- Process shows as running from project directory

### Root Causes

#### 1. **Daemon Threads Not Stopping** ❌
**File**: `backend/core/facial_recognition_system.py` (line 211-212)
```python
self._processing_thread = threading.Thread(
    target=self._process_queue, daemon=True
)
```

**File**: `backend/core/cloud_storage_system.py` (line 446-447)
```python
self.upload_thread = threading.Thread(
    target=self._upload_worker, daemon=True)
```

**Problem**: Daemon threads marked as `daemon=True` should terminate when the main thread exits, BUT they don't always stop cleanly if:
- They're blocked on I/O operations
- They're in infinite loops without proper shutdown flags
- The event loop is still processing async tasks

#### 2. **Incomplete Shutdown Sequence** ❌
**File**: `backend/main.py` (line 196-212)
```python
@app.on_event("shutdown")
async def shutdown_event():
    """
    On shutdown, clean up resources.
    """
    logger.info("Shutting down OpenEye Surveillance System...")

    # Stop statistics broadcaster
    logger.info("Stopping statistics broadcaster...")
    broadcaster = get_broadcaster()
    await broadcaster.stop()

    # Stop all cameras
    for camera_id in list(camera_manager.cameras.keys()):
        camera_manager.remove_camera(camera_id)

    logger.info("OpenEye Surveillance System shutdown complete")
```

**Missing**:
- ❌ No cleanup for facial recognition threads
- ❌ No cleanup for cloud storage upload threads
- ❌ No cleanup for WebSocket connections
- ❌ No cleanup for alert manager
- ❌ No cleanup for database sessions
- ❌ No signal handlers for SIGTERM/SIGINT
- ❌ No graceful timeout for thread termination

#### 3. **Camera Stop Methods Don't Release All Resources** ❌
**File**: `backend/core/camera_manager.py`

```python
def stop(self):
    if self.recorder.is_recording:
        self.recorder.stop()
    if self.is_running and self.capture:
        self.capture.release()
    self.is_running = False
    print("RTSP camera stopped.")
```

**Missing**:
- ❌ No cleanup for motion detector threads (if any)
- ❌ No cleanup for face detector threads
- ❌ No cleanup for video processor resources
- ❌ No cleanup for alert callbacks

#### 4. **Uvicorn --reload Mode** ⚠️
The server is started with `--reload` flag which uses a file watcher process:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

This creates:
- Main uvicorn process (PID 24567)
- Resource tracker process (PID 24572)
- **Problem**: Resource tracker doesn't clean up when parent is killed

---

## ✅ Solutions

### 1. Add Proper Shutdown Handlers

**File**: `backend/main.py`

```python
import signal
import sys

# Global cleanup flag
_shutting_down = False

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global _shutting_down
    if _shutting_down:
        logger.warning("Force shutdown - killing process")
        sys.exit(1)
    
    _shutting_down = True
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    
    # Trigger FastAPI shutdown
    asyncio.create_task(shutdown_event())

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Kill command

@app.on_event("shutdown")
async def shutdown_event():
    """
    Enhanced shutdown with complete cleanup.
    """
    global _shutting_down
    _shutting_down = True
    
    logger.info("=" * 50)
    logger.info("Shutting down OpenEye Surveillance System...")
    logger.info("=" * 50)

    # 1. Stop statistics broadcaster
    logger.info("1/7 Stopping statistics broadcaster...")
    try:
        broadcaster = get_broadcaster()
        await asyncio.wait_for(broadcaster.stop(), timeout=5.0)
        logger.info("  ✓ Statistics broadcaster stopped")
    except asyncio.TimeoutError:
        logger.warning("  ⚠ Statistics broadcaster stop timeout")
    except Exception as e:
        logger.error(f"  ✗ Error stopping broadcaster: {e}")

    # 2. Close all WebSocket connections
    logger.info("2/7 Closing WebSocket connections...")
    try:
        from backend.core.websocket_manager import ws_manager
        await asyncio.wait_for(ws_manager.disconnect_all(), timeout=5.0)
        logger.info("  ✓ WebSocket connections closed")
    except asyncio.TimeoutError:
        logger.warning("  ⚠ WebSocket close timeout")
    except Exception as e:
        logger.error(f"  ✗ Error closing WebSockets: {e}")

    # 3. Stop all cameras and release resources
    logger.info("3/7 Stopping cameras...")
    try:
        camera_ids = list(camera_manager.cameras.keys())
        for camera_id in camera_ids:
            try:
                camera_manager.remove_camera(camera_id)
                logger.info(f"  ✓ Camera '{camera_id}' stopped")
            except Exception as e:
                logger.error(f"  ✗ Error stopping camera '{camera_id}': {e}")
    except Exception as e:
        logger.error(f"  ✗ Error stopping cameras: {e}")

    # 4. Stop facial recognition processing threads
    logger.info("4/7 Stopping facial recognition threads...")
    try:
        from backend.core.facial_recognition_system import get_recognition_manager
        recognition_manager = get_recognition_manager()
        recognition_manager.stop_processing()
        logger.info("  ✓ Facial recognition stopped")
    except Exception as e:
        logger.error(f"  ✗ Error stopping facial recognition: {e}")

    # 5. Stop cloud storage upload threads
    logger.info("5/7 Stopping cloud storage uploads...")
    try:
        from backend.core.cloud_storage_system import get_storage_manager
        storage_manager = get_storage_manager()
        storage_manager.stop_upload_worker()
        logger.info("  ✓ Cloud storage stopped")
    except Exception as e:
        logger.error(f"  ✗ Error stopping cloud storage: {e}")

    # 6. Close database connections
    logger.info("6/7 Closing database connections...")
    try:
        from backend.database import engine
        engine.dispose()
        logger.info("  ✓ Database connections closed")
    except Exception as e:
        logger.error(f"  ✗ Error closing database: {e}")

    # 7. Wait for background tasks to complete
    logger.info("7/7 Waiting for background tasks...")
    try:
        # Give tasks 3 seconds to finish
        await asyncio.sleep(1.0)
        
        # Cancel remaining tasks
        tasks = [t for t in asyncio.all_tasks() if not t.done()]
        if tasks:
            logger.info(f"  ⚠ Cancelling {len(tasks)} remaining tasks...")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("  ✓ Background tasks completed")
    except Exception as e:
        logger.error(f"  ✗ Error waiting for tasks: {e}")

    logger.info("=" * 50)
    logger.info("✅ OpenEye Surveillance System shutdown complete")
    logger.info("=" * 50)
```

### 2. Add Stop Methods to Thread-Based Classes

**File**: `backend/core/facial_recognition_system.py`

```python
class FacialRecognitionManager:
    def __init__(self):
        self._processing_thread = None
        self._processing_queue = queue.Queue()
        self._stop_event = threading.Event()  # ADD THIS
        
    def start_processing(self):
        """Start background processing thread"""
        if self._processing_thread and self._processing_thread.is_alive():
            return
            
        self._stop_event.clear()  # ADD THIS
        self._processing_thread = threading.Thread(
            target=self._process_queue, daemon=True
        )
        self._processing_thread.start()
    
    def stop_processing(self):  # ADD THIS METHOD
        """Stop background processing thread"""
        if not self._processing_thread or not self._processing_thread.is_alive():
            return
            
        logger.info("Stopping facial recognition processing thread...")
        self._stop_event.set()
        
        # Add sentinel value to queue to unblock the thread
        self._processing_queue.put(None)
        
        # Wait for thread to finish (with timeout)
        self._processing_thread.join(timeout=5.0)
        
        if self._processing_thread.is_alive():
            logger.warning("Facial recognition thread did not stop gracefully")
        else:
            logger.info("Facial recognition thread stopped successfully")
    
    def _process_queue(self):
        """Process face recognition requests from queue"""
        while not self._stop_event.is_set():  # MODIFY THIS
            try:
                # Use timeout to allow checking stop event
                item = self._processing_queue.get(timeout=1.0)
                
                # Check for sentinel value
                if item is None:
                    break
                    
                # Process the item
                # ... existing processing code ...
                
                self._processing_queue.task_done()
            except queue.Empty:
                continue  # Check stop event and continue
            except Exception as e:
                logger.error(f"Error processing face recognition: {e}")
```

**File**: `backend/core/cloud_storage_system.py`

```python
class CloudStorageManager:
    def start_upload_worker(self):
        """Start upload worker thread"""
        if self.upload_thread and self.upload_thread.is_alive():
            return
            
        self.running = True
        self.upload_thread = threading.Thread(
            target=self._upload_worker, daemon=True)
        self.upload_thread.start()
        logger.info("Upload worker started")

    def stop_upload_worker(self):
        """Stop upload worker"""
        if not self.upload_thread or not self.upload_thread.is_alive():
            return
            
        logger.info("Stopping upload worker thread...")
        self.running = False
        
        # Wait for thread to finish
        self.upload_thread.join(timeout=5.0)
        
        if self.upload_thread.is_alive():
            logger.warning("Upload worker thread did not stop gracefully")
        else:
            logger.info("Upload worker thread stopped successfully")
```

### 3. Add WebSocket Disconnect All Method

**File**: `backend/core/websocket_manager.py`

```python
class WebSocketConnectionManager:
    async def disconnect_all(self):
        """Disconnect all WebSocket connections gracefully"""
        logger.info(f"Disconnecting all WebSocket connections ({len(self.active_connections)} total)...")
        
        # Create a copy of connections to avoid modification during iteration
        connections_to_close = list(self.active_connections)
        
        for connection in connections_to_close:
            try:
                await connection.close(code=1000, reason="Server shutting down")
            except Exception as e:
                logger.error(f"Error closing WebSocket connection: {e}")
        
        self.active_connections.clear()
        self.user_connections.clear()
        
        logger.info("All WebSocket connections closed")
```

### 4. Add Camera Resource Cleanup

**File**: `backend/core/camera_manager.py`

```python
class Camera(ABC):
    def stop(self):
        """Stop camera and cleanup all resources"""
        logger.info(f"Stopping camera {self.camera_id}...")
        
        # Stop recording if active
        if hasattr(self, 'recorder') and self.recorder.is_recording:
            try:
                self.recorder.stop()
            except Exception as e:
                logger.error(f"Error stopping recorder: {e}")
        
        # Release capture
        if hasattr(self, 'capture') and self.capture:
            try:
                self.capture.release()
            except Exception as e:
                logger.error(f"Error releasing capture: {e}")
        
        # Stop face detector
        if hasattr(self, 'face_detector'):
            try:
                # If face detector has cleanup method
                pass
            except Exception as e:
                logger.error(f"Error stopping face detector: {e}")
        
        self.is_running = False
        logger.info(f"Camera {self.camera_id} stopped successfully")
```

### 5. Create Graceful Stop Script

**File**: `stop-server.sh`

```bash
#!/bin/bash
# Graceful shutdown script for OpenEye

echo "🛑 Stopping OpenEye Surveillance System..."

# Find the uvicorn process
UVICORN_PID=$(ps aux | grep "uvicorn backend.main:app" | grep -v grep | awk '{print $2}' | head -1)

if [ -z "$UVICORN_PID" ]; then
    echo "❌ No running OpenEye server found"
    exit 0
fi

echo "📍 Found server process: PID $UVICORN_PID"

# Send SIGTERM for graceful shutdown
echo "🔄 Sending graceful shutdown signal (SIGTERM)..."
kill -TERM $UVICORN_PID

# Wait up to 10 seconds for graceful shutdown
for i in {1..10}; do
    if ! ps -p $UVICORN_PID > /dev/null 2>&1; then
        echo "✅ Server stopped gracefully"
        exit 0
    fi
    echo "⏳ Waiting for shutdown... ($i/10)"
    sleep 1
done

# Force kill if still running
if ps -p $UVICORN_PID > /dev/null 2>&1; then
    echo "⚠️  Graceful shutdown failed, forcing termination..."
    kill -9 $UVICORN_PID
    
    # Kill any remaining python processes from this project
    pkill -9 -f "backend.main:app"
    
    echo "⚡ Server force stopped"
else
    echo "✅ Server stopped"
fi

# Clean up any orphaned processes
echo "🧹 Cleaning up orphaned processes..."
ps aux | grep "backend.main" | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null

echo "✅ Cleanup complete"
```

Make executable:
```bash
chmod +x stop-server.sh
```

### 6. Update start-local.sh to Use Graceful Stop

**File**: `start-local.sh`

Add trap for clean shutdown:

```bash
#!/bin/bash

# Trap Ctrl+C and call cleanup function
trap cleanup EXIT INT TERM

cleanup() {
    echo ""
    echo "🛑 Stopping OpenEye..."
    
    # Send SIGTERM to uvicorn
    if [ ! -z "$UVICORN_PID" ]; then
        kill -TERM $UVICORN_PID 2>/dev/null
        wait $UVICORN_PID 2>/dev/null
    fi
    
    echo "✅ OpenEye stopped"
}

# ... existing startup code ...

# Start uvicorn and capture PID
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
UVICORN_PID=$!

# Wait for uvicorn process
wait $UVICORN_PID
```

---

## 🔍 Verification

### Check for Running Processes
```bash
# Before fix - orphaned processes
ps aux | grep -E "(python|uvicorn)" | grep backend.main

# After fix - clean shutdown
./stop-server.sh
ps aux | grep -E "(python|uvicorn)" | grep backend.main  # Should return nothing
```

### Test Graceful Shutdown
```bash
# Start server
./start-local.sh

# In another terminal, check processes
ps aux | grep backend.main

# Stop server
./stop-server.sh

# Verify all processes stopped
ps aux | grep backend.main  # Should be empty
lsof -i :8000  # Should be empty
```

### Check Logs for Clean Shutdown
```bash
# Should show:
# ==========================================
# Shutting down OpenEye Surveillance System...
# ==========================================
# 1/7 Stopping statistics broadcaster...
#   ✓ Statistics broadcaster stopped
# 2/7 Closing WebSocket connections...
#   ✓ WebSocket connections closed
# 3/7 Stopping cameras...
#   ✓ Camera 'camera_1' stopped
# 4/7 Stopping facial recognition threads...
#   ✓ Facial recognition stopped
# 5/7 Stopping cloud storage uploads...
#   ✓ Cloud storage stopped
# 6/7 Closing database connections...
#   ✓ Database connections closed
# 7/7 Waiting for background tasks...
#   ✓ Background tasks completed
# ==========================================
# ✅ OpenEye Surveillance System shutdown complete
# ==========================================
```

---

## 📋 Implementation Checklist

- [ ] Add signal handlers to `main.py`
- [ ] Enhance `shutdown_event()` with 7-step cleanup
- [ ] Add `stop_processing()` to `facial_recognition_system.py`
- [ ] Add `stop_event` check to processing loop
- [ ] Add `stop_upload_worker()` to `cloud_storage_system.py`
- [ ] Add `disconnect_all()` to `websocket_manager.py`
- [ ] Enhance camera `stop()` methods with full cleanup
- [ ] Create `stop-server.sh` graceful shutdown script
- [ ] Update `start-local.sh` with trap handler
- [ ] Test graceful shutdown
- [ ] Test force kill fallback
- [ ] Verify no orphaned processes
- [ ] Document new shutdown procedures

---

## 🎯 Expected Results After Fix

✅ **Clean Shutdown**:
- No orphaned Python processes
- Port 8000 immediately available after shutdown
- All threads properly terminated
- Database connections closed
- WebSocket connections gracefully closed

✅ **Graceful Degradation**:
- 10-second timeout for graceful shutdown
- Automatic force kill if timeout exceeded
- Clear logging of shutdown progress

✅ **Developer Experience**:
- `Ctrl+C` works correctly
- `./stop-server.sh` cleanly stops server
- No need for manual `pkill` or force quit

---

**Created**: October 13, 2025  
**Priority**: High  
**Status**: Ready for Implementation
