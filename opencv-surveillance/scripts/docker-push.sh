#!/bin/bash
# Manual script to build and push Docker images to Docker Hub

set -e

# TODO: Set your Docker Hub credentials
DOCKER_USERNAME="your-dockerhub-username"  # <- CHANGE THIS
IMAGE_NAME="openeye-surveillance"
VERSION=${1:-latest}

echo "🐳 Building and pushing OpenEye Docker image..."
echo "================================================"
echo "Username: $DOCKER_USERNAME"
echo "Image: $IMAGE_NAME"
echo "Version: $VERSION"
echo "================================================"

# Login to Docker Hub
echo "🔐 Logging in to Docker Hub..."
echo "Please enter your Docker Hub credentials:"
# TODO: Replace with your Docker Hub username and password/token
docker login -u "$DOCKER_USERNAME"

# Build the image
echo "🔨 Building Docker image..."
docker build -t $DOCKER_USERNAME/$IMAGE_NAME:$VERSION .

# Tag as latest if this is a version tag
if [[ $VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "🏷️  Tagging as latest..."
    docker tag $DOCKER_USERNAME/$IMAGE_NAME:$VERSION $DOCKER_USERNAME/$IMAGE_NAME:latest
fi

# Push to Docker Hub
echo "⬆️  Pushing to Docker Hub..."
docker push $DOCKER_USERNAME/$IMAGE_NAME:$VERSION

if [[ $VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    docker push $DOCKER_USERNAME/$IMAGE_NAME:latest
fi

echo "✅ Successfully pushed to Docker Hub!"
echo "Image: $DOCKER_USERNAME/$IMAGE_NAME:$VERSION"
echo ""
echo "To pull this image:"
echo "  docker pull $DOCKER_USERNAME/$IMAGE_NAME:$VERSION"
