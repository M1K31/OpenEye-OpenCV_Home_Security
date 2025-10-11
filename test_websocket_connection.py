#!/usr/bin/env python3
"""
Quick WebSocket connection test for OpenEye v3.4.0
Tests if WebSocket endpoint is accessible and broadcasting statistics
"""
import asyncio
import websockets
import json

async def test_websocket():
    # Note: This will fail without authentication token
    # This is expected - we're just testing if the endpoint is accessible
    uri = "ws://localhost:8000/api/ws/statistics"
    
    print("🔍 Testing WebSocket endpoint accessibility...")
    print(f"   URI: {uri}")
    print()
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connection established!")
            
            # Try to receive a message
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
            print(f"✅ Received message: {data.get('type', 'unknown')}")
            print(f"   Data: {json.dumps(data, indent=2)}")
            
    except websockets.exceptions.InvalidStatusCode as e:
        if e.status_code == 403:
            print("✅ WebSocket endpoint is accessible!")
            print("⚠️  Authentication required (expected behavior)")
            print("   Status: 403 Forbidden")
        else:
            print(f"❌ Unexpected status code: {e.status_code}")
            
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket error: {e}")
        
    except asyncio.TimeoutError:
        print("⏰ Timeout waiting for message (may need authentication)")
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("OpenEye v3.4.0 - WebSocket Connection Test")
    print("=" * 60)
    print()
    
    asyncio.run(test_websocket())
    
    print()
    print("=" * 60)
    print("Test completed!")
    print("=" * 60)
