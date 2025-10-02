import requests
import time
from playwright.sync_api import sync_playwright, expect

# --- 1. Setup: Create a user via API ---
BASE_URL = "http://127.0.0.1:8000"
USER = {
    "username": "testuser",
    "password": "password123",
    "email": "test@example.com"
}

def create_user():
    """Creates a user via API to enable login for testing."""
    try:
        # The user might already exist from a previous run, which is fine.
        requests.post(f"{BASE_URL}/api/users/", json=USER)
        print(f"User '{USER['username']}' created or already exists.")
    except requests.exceptions.RequestException as e:
        print(f"Could not connect to the backend to create user: {e}")
        print("Please ensure the backend server is running on port 8000.")
        exit(1)

def run_verification():
    """Runs the Playwright verification script."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # --- 2. Login ---
            print("Navigating to login page...")
            page.goto("http://127.0.0.1:5173/login")

            print("Filling in login credentials...")
            page.get_by_placeholder("Username").fill(USER["username"])
            page.get_by_placeholder("Password").fill(USER["password"])
            page.get_by_role("button", name="Login").click()

            # --- 3. Verify Dashboard ---
            print("Verifying dashboard is loaded...")
            # Expect the main heading of the dashboard to be visible
            dashboard_heading = page.get_by_role("heading", name="Surveillance Dashboard")
            expect(dashboard_heading).to_be_visible(timeout=5000)

            # Expect the video stream element to be present
            video_stream = page.get_by_alt_text("Live camera stream")
            expect(video_stream).to_be_visible()

            print("Dashboard verified successfully.")

            # --- 4. Take Screenshot ---
            screenshot_path = "jules-scratch/verification/verification.png"
            page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"An error occurred during Playwright verification: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    # Wait a moment for servers to be ready
    time.sleep(5)
    create_user()
    run_verification()