import requests
import time
from playwright.sync_api import sync_playwright, Page, expect

# --- Test Setup ---
# Define user credentials and API endpoints
BASE_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5174"
USER = {
    "username": f"testuser_{int(time.time())}",
    "email": f"test_{int(time.time())}@example.com",
    "password": "password"
}

def create_user():
    """Create a new user via the API for testing."""
    try:
        response = requests.post(f"{BASE_URL}/api/users/", json=USER)
        if response.status_code == 200:
            print(f"Successfully created user: {USER['username']}")
            return True
        # Handle case where user might already exist from a previous run
        elif response.status_code == 400 and "already registered" in response.text:
            print(f"User {USER['username']} already exists, proceeding with login.")
            return True
        else:
            print(f"Error creating user: {response.status_code} - {response.text}")
            print("Full response content:")
            print(response.content)
            return False
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error when trying to create user: {e}")
        return False

def run_verification(page: Page):
    """
    This script verifies that a user can log in, navigate to the
    Face Management page, and that the page loads correctly.
    """
    # 1. Arrange: Go to the login page.
    page.goto(f"{FRONTEND_URL}/login")

    # 2. Act: Log in with the newly created user.
    page.get_by_placeholder("Username").fill(USER["username"])
    page.get_by_placeholder("Password").fill(USER["password"])
    page.get_by_role("button", name="Login").click()

    # 3. Assert: Wait for the dashboard to load by checking for the heading.
    expect(page.get_by_role("heading", name="Surveillance Dashboard")).to_be_visible()

    # 4. Act: Navigate to the Face Management page.
    page.get_by_role("button", name="Manage Faces").click()

    # 5. Assert: Confirm the Face Management page has loaded.
    expect(page.get_by_role("heading", name="Face Recognition Management")).to_be_visible()

    # 6. Screenshot: Capture the final result for visual verification.
    screenshot_path = "jules-scratch/verification/face-management-page.png"
    page.screenshot(path=screenshot_path)
    print(f"Screenshot saved to {screenshot_path}")

def main():
    # --- Step 1: Create the user ---
    if not create_user():
        print("Halting verification because user creation failed.")
        return

    # --- Step 2: Run Playwright verification ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            run_verification(page)
        except Exception as e:
            print(f"An error occurred during Playwright verification: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()