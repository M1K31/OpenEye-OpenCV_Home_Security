import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

from backend.database.session import engine
from backend.database import models
from backend.api.routes import users, cameras
from backend.core.camera_manager import manager as camera_manager

# Load environment variables from .env file
load_dotenv()

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="OpenCV Surveillance System")

@app.on_event("startup")
def startup_event():
    """
    On startup, add a default mock camera for testing.
    """
    if not camera_manager.get_camera("mock_cam_1"):
        camera_manager.add_camera(camera_id="mock_cam_1", camera_type="mock", source="mock")

app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(cameras.router, prefix="/api", tags=["cameras"])

@app.get("/")
async def read_root():
    return {"message": "Welcome to the OpenCV Surveillance System API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)