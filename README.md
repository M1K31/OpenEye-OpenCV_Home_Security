# OpenCV Surveillance System

An open-source, modern, and feature-rich surveillance system designed as a powerful alternative to MotionEye. This project leverages OpenCV, FastAPI, and React to provide a cross-platform solution with enhanced capabilities, including AI-powered features, two-way audio, and seamless smart home integration.

## About The Project

The core goal of this project is to create a robust and extensible surveillance system that goes beyond traditional motion detection. By combining the power of OpenCV for video processing with a modern web stack, this system aims to offer advanced features in a secure, user-friendly package.

### Core Philosophy
*   **Security by Design:** Implementing end-to-end encryption, secure authentication, and robust data protection.
*   **Modular Architecture:** Building a flexible system where new features and integrations can be easily added.
*   **Performance Optimization:** Ensuring efficient operation, even on resource-constrained devices like a Raspberry Pi.
*   **User-Friendly Interface:** A clean, responsive web UI that makes camera management and event review simple and intuitive.

---

## Phase 1 Features (Complete)

This initial version provides the foundational building blocks of the system. The following features have been implemented:

*   **Project Foundation:**
    *   Complete backend (FastAPI) and frontend (React) project structure.
    *   SQLite database for user management.
*   **User Authentication:**
    *   Secure user login system with JWT-based authentication.
    *   API endpoints for user creation and token generation.
*   **Camera Management:**
    *   A `CameraManager` to handle multiple camera sources.
    *   Support for a **mock camera** for development and testing.
    *   API to add, list, and remove cameras.
*   **Live Video Streaming:**
    *   An **MJPEG streaming endpoint** to provide a real-time video feed from any camera.
    *   A live view in the frontend dashboard that displays the stream after login.
*   **Basic Motion Detection:**
    *   Motion detection using OpenCV's MOG2 background subtraction algorithm.
    *   Visual feedback in the live stream with **bounding boxes** drawn around detected motion.
*   **Motion-Triggered Recording:**
    *   Automatic video recording initiated by motion detection.
    *   Recordings are saved as `.mp4` files in the `opencv-surveillance/recordings/` directory.
    *   A post-motion cooldown period ensures entire events are captured.
    *   A visual indicator on the live stream shows when a recording is in progress.

---

## Getting Started

To get the system up and running locally, follow these steps.

### Prerequisites

*   Python 3.9+
*   Node.js and npm
*   An RTSP stream URL (optional, for testing with a real camera)

### Backend Setup

1.  **Navigate to the backend directory:**
    ```sh
    cd opencv-surveillance/backend
    ```

2.  **Install Python dependencies:**
    It is recommended to use a virtual environment.
    ```sh
    pip install -r ../../requirements.txt
    ```
    *(Note: The `requirements.txt` is at the root level for easy setup)*

3.  **Run the backend server:**
    From the `opencv-surveillance` directory, run:
    ```sh
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    The API will be available at `http://127.0.0.1:8000`.

### Frontend Setup

1.  **Navigate to the frontend directory:**
    ```sh
    cd opencv-surveillance/frontend
    ```

2.  **Install npm packages:**
    ```sh
    npm install
    ```

3.  **Run the frontend development server:**
    ```sh
    npm run dev
    ```
    The web interface will be available at `http://127.0.0.1:5173`.

### Default Login

A default user is not created automatically. You can create one via the API or use the frontend to register. For testing, you can use the following command to create a user:
```sh
curl -X POST "http://127.0.0.1:8000/api/users/" \
-H "Content-Type: application/json" \
-d '{"username": "admin", "password": "password", "email": "admin@example.com"}'
```
You can then log in with these credentials on the web interface.

---

## Project Structure

The project is organized into a monorepo structure with a clear separation between the backend and frontend.

```
opencv-surveillance/
├── backend/        # FastAPI application
├── frontend/       # React application
├── recordings/     # Default directory for saved videos
└── ...
```