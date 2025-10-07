# 🐳 Docker Setup Guide for OpenEye

## Quick Start

### 1. Local Development

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 2. Pull from Docker Hub

```bash
# TODO: Replace 'your-dockerhub-username' with your actual username
docker pull your-dockerhub-username/openeye-surveillance:latest

# Run the container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --name openeye \
  your-dockerhub-username/openeye-surveillance:latest
```

## Setup Instructions

### Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- Docker Hub account (for pushing images)

### Environment Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and fill in your credentials:
```bash
nano .env
```

### Building the Image

```bash
# Development build
docker build -f Dockerfile.dev -t openeye:dev .

# Production build
docker build -t openeye:latest .
```

## GitHub Actions Setup

### Setting up Docker Hub Integration

1. **Create Docker Hub Access Token**
   - Go to https://hub.docker.com/settings/security
   - Click "New Access Token"
   - Name it "GitHub Actions"
   - Copy the token (you won't see it again!)

2. **Add Secrets to GitHub**
   - Go to your repo: `Settings > Secrets and variables > Actions`
   - Click "New repository secret"
   - Add these secrets:

   | Name | Value |
   |------|-------|
   | `DOCKERHUB_USERNAME` | Your Docker Hub username |
   | `DOCKERHUB_TOKEN` | The access token you created |

3. **Update Workflow File**
   - Edit `.github/workflows/docker-hub-push.yml`
   - Replace `your-dockerhub-username` with your actual username on line 11

### Workflow Triggers

The workflow automatically runs on:
- Push to `main` or `develop` branches
- New version tags (e.g., `v1.0.0`)
- Pull requests to `main`

### Manual Trigger

```bash
# Tag and push to trigger build
git tag v1.0.0
git push origin v1.0.0
```

## Manual Push to Docker Hub

### Using the Script

```bash
# Make script executable
chmod +x scripts/docker-push.sh

# Edit the script and add your username
nano scripts/docker-push.sh
# Change line 6: DOCKER_USERNAME="your-dockerhub-username"

# Run the script
./scripts/docker-push.sh v1.0.0
```

### Using Docker Commands

```bash
# Login to Docker Hub
docker login -u your-dockerhub-username

# Build image
docker build -t your-dockerhub-username/openeye-surveillance:latest .

# Push to Docker Hub
docker push your-dockerhub-username/openeye-surveillance:latest
```

## Docker Compose Usage

### Development Environment

```bash
# Start with hot-reload
docker-compose up -d

# Rebuild after code changes
docker-compose up -d --build

# View logs
docker-compose logs -f openeye

# Execute commands in container
docker-compose exec openeye bash
```

### Production Environment

```bash
# Build production image
docker-compose -f docker-compose.prod.yml build

# Start production services
docker-compose -f docker-compose.prod.yml up -d

# Scale the application
docker-compose -f docker-compose.prod.yml up -d --scale openeye=3
```

## Useful Commands

```bash
# Check running containers
docker ps

# View container logs
docker logs openeye-surveillance

# Execute command in container
docker exec -it openeye-surveillance bash

# Check resource usage
docker stats openeye-surveillance

# Remove all stopped containers
docker container prune

# Remove unused images
docker image prune -a
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs openeye-surveillance

# Check if port is already in use
lsof -i :8000
```

### Permission issues

```bash
# Fix data directory permissions
sudo chown -R 1000:1000 ./data
```

### Database connection issues

```bash
# Check if database container is running
docker ps | grep postgres

# Test database connection
docker exec openeye-surveillance python -c "from backend.database.session import engine; print(engine.url)"
```

### Image build fails

```bash
# Build without cache
docker build --no-cache -t openeye:latest .

# Check Docker disk space
docker system df
```

## Security Notes

- Never commit `.env` file to git
- Use Docker secrets for sensitive data in production
- Run containers as non-root user (already configured)
- Keep base images updated: `docker pull python:3.11-slim`
- Scan images for vulnerabilities: `docker scan openeye:latest`

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Hub](https://hub.docker.com/)
- [GitHub Actions for Docker](https://docs.github.com/en/actions/publishing-packages/publishing-docker-images)
