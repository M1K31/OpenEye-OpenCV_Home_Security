#!/usr/bin/env python3
"""
WebSocket Connection Test Script
Tests WebSocket authentication and connection to /api/ws/statistics

Usage:
    python test_websocket_connection.py <username> <password>
"""

import asyncio
import sys
import websockets
import json
import requests
from urllib.parse import urlencode


def get_auth_token(base_url, username, password):
    """Get JWT token from the API"""
    print(f"Authenticating as {username}...")

    # Login endpoint
    login_url = f"{base_url}/api/token"

    # OAuth2 password flow expects form data
    data = {
        "username": username,
        "password": password
    }

    try:
        response = requests.post(login_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        token = token_data.get("access_token")

        if token:
            print(f"✓ Successfully obtained token: {token[:20]}...")
            return token
        else:
            print("✗ No access_token in response")
            print(f"Response: {token_data}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"✗ Authentication failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return None


async def test_websocket_connection(ws_url, token):
    """Test WebSocket connection with authentication"""
    print(f"\nConnecting to WebSocket...")
    print(f"URL: {ws_url}")

    try:
        async with websockets.connect(ws_url) as websocket:
            print("✓ WebSocket connected!")

            # Wait for welcome message
            print("\nWaiting for welcome message...")
            welcome_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            welcome_data = json.loads(welcome_message)
            print(f"✓ Received welcome message:")
            print(json.dumps(welcome_data, indent=2))

            # Send a ping
            print("\nSending ping...")
            ping_message = {
                "type": "ping",
                "timestamp": "2025-10-18T12:00:00"
            }
            await websocket.send(json.dumps(ping_message))
            print("✓ Ping sent")

            # Wait for pong
            print("\nWaiting for pong...")
            pong_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            pong_data = json.loads(pong_message)
            print(f"✓ Received pong:")
            print(json.dumps(pong_data, indent=2))

            # Listen for a few statistics updates
            print("\nListening for statistics updates (max 5 seconds)...")
            try:
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    message_type = data.get('type', 'unknown')
                    print(f"✓ Received {message_type} message")

                    if message_type == 'statistics_update':
                        print(f"  Statistics: {data.get('data', {})}")
            except asyncio.TimeoutError:
                print("\nTimeout reached (no more messages)")

            print("\n✓ WebSocket test completed successfully!")
            return True

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"\n✗ WebSocket connection failed with status code: {e.status_code}")
        print(f"Headers: {e.headers}")
        return False
    except asyncio.TimeoutError:
        print(f"\n✗ Timeout waiting for WebSocket message")
        return False
    except Exception as e:
        print(f"\n✗ WebSocket test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function"""
    if len(sys.argv) != 3:
        print("Usage: python test_websocket_connection.py <username> <password>")
        print("\nExample:")
        print("  python test_websocket_connection.py admin mypassword")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    # Configuration
    base_url = "http://localhost:8000"
    ws_base_url = "ws://localhost:8000"

    print("=" * 60)
    print("WebSocket Connection Test")
    print("=" * 60)

    # Step 1: Get authentication token
    token = get_auth_token(base_url, username, password)
    if not token:
        print("\n✗ Cannot proceed without valid token")
        sys.exit(1)

    # Step 2: Test WebSocket connection
    ws_url = f"{ws_base_url}/api/ws/statistics?token={token}"

    success = asyncio.run(test_websocket_connection(ws_url, token))

    print("\n" + "=" * 60)
    if success:
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        sys.exit(0)
    else:
        print("✗ TESTS FAILED")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
