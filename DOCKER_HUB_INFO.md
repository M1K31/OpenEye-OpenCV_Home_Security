# Docker Hub Information

## Repository Details

- **Docker Hub URL**: https://hub.docker.com/r/im1k31s/openeye-opencv_home_security
- **Username**: `im1k31s`
- **Repository Name**: `openeye-opencv_home_security`
- **Full Image Name**: `im1k31s/openeye-opencv_home_security`

## Available Tags

### Latest Versions
- `latest` - Always points to the most recent stable release
- `v3.5.2` - Current release (October 2025)
- `v3.5.1.4` - Previous release
- `v3.4.0` - Earlier release
- `v3.3.8` - Earlier release
- `v3.3.0` - Earlier release

## Pull Commands

```bash
# Pull latest version
docker pull im1k31s/openeye-opencv_home_security:latest

# Pull specific version
docker pull im1k31s/openeye-opencv_home_security:v3.5.2
```

## Run Commands

```bash
# Run with default ports
docker run -d -p 8000:8000 im1k31s/openeye-opencv_home_security:latest

# Run with custom configuration
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/recordings:/app/recordings \
  -v $(pwd)/faces:/app/faces \
  --name openeye \
  im1k31s/openeye-opencv_home_security:latest
```

## Push Commands (for maintainers)

```bash
# Tag new version
docker tag local-image:latest im1k31s/openeye-opencv_home_security:v3.5.2
docker tag local-image:latest im1k31s/openeye-opencv_home_security:latest

# Push to Docker Hub
docker push im1k31s/openeye-opencv_home_security:v3.5.2
docker push im1k31s/openeye-opencv_home_security:latest
```

## Automated Deployment

Use the deployment script:
```bash
./deploy.sh
```

This script will:
1. Commit and push changes to GitHub
2. Build the Docker image with correct tags
3. Push to Docker Hub with authentication

## Image Information

- **Base Image**: python:3.11-slim
- **Size**: ~2GB uncompressed (~600-800MB compressed on Docker Hub)
- **Architecture**: Multi-platform (amd64, arm64 supported)
- **Build Type**: Multi-stage build (optimized)

## Notes

- Images are automatically compressed by Docker Hub (30-40% reduction)
- Multi-stage builds minimize image size
- Frontend assets are pre-built and included
- Python dependencies are pre-installed
