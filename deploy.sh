#!/bin/bash
# OpenEye GitHub & Docker Hub Deployment Script
# Automated deployment to GitHub and Docker Hub

set -e  # Exit on error

echo "=================================================="
echo "  OpenEye Deployment Script v3.5.2"
echo "=================================================="
echo ""

# Configuration
VERSION="v3.5.2"
DOCKER_USERNAME="m1k31"
DOCKER_IMAGE="openeye"
GITHUB_REPO="M1K31/OpenEye-OpenCV_Home_Security"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }

# Check prerequisites
echo "Checking prerequisites..."

# Check if git is available
if ! command -v git &> /dev/null; then
    print_error "git is not installed"
    exit 1
fi
print_status "git is available"

# Check if docker is available
if ! command -v docker &> /dev/null; then
    print_error "docker is not installed"
    exit 1
fi
print_status "docker is available"

# Check if we're in a git repo
if [ ! -d ".git" ]; then
    print_error "Not in a git repository"
    exit 1
fi
print_status "In git repository"

# Check git status
echo ""
echo "Checking git status..."
if [ -n "$(git status --porcelain)" ]; then
    print_warning "There are uncommitted changes"
    echo ""
    git status --short | head -20
    echo ""
    read -p "Do you want to commit all changes? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter commit message: " COMMIT_MSG
        git add .
        git commit -m "$COMMIT_MSG"
        print_status "Changes committed"
    else
        print_warning "Proceeding with uncommitted changes"
    fi
else
    print_status "No uncommitted changes"
fi

# GitHub Push
echo ""
echo "=================================================="
echo "  Step 1: Push to GitHub"
echo "=================================================="
read -p "Push to GitHub? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Pushing to GitHub..."
    git push origin main
    print_status "Pushed to GitHub successfully"
else
    print_warning "Skipped GitHub push"
fi

# Docker Build
echo ""
echo "=================================================="
echo "  Step 2: Build Docker Image"
echo "=================================================="
read -p "Build Docker image? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Building Docker image..."
    cd opencv-surveillance
    
    # Build with version tag
    docker build -t ${DOCKER_USERNAME}/${DOCKER_IMAGE}:${VERSION} .
    
    if [ $? -eq 0 ]; then
        print_status "Docker image built successfully"
        
        # Tag as latest
        docker tag ${DOCKER_USERNAME}/${DOCKER_IMAGE}:${VERSION} ${DOCKER_USERNAME}/${DOCKER_IMAGE}:latest
        print_status "Tagged as latest"
        
        # Show image size
        IMAGE_SIZE=$(docker images ${DOCKER_USERNAME}/${DOCKER_IMAGE}:${VERSION} --format "{{.Size}}")
        print_info "Image size: $IMAGE_SIZE"
    else
        print_error "Docker build failed"
        exit 1
    fi
    
    cd ..
else
    print_warning "Skipped Docker build"
    exit 0
fi

# Docker Push
echo ""
echo "=================================================="
echo "  Step 3: Push to Docker Hub"
echo "=================================================="
read -p "Push to Docker Hub? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Check if logged in to Docker Hub
    if ! docker info | grep -q "Username:"; then
        print_warning "Not logged in to Docker Hub"
        print_info "Please login to Docker Hub:"
        docker login
    fi
    
    print_info "Pushing ${VERSION} to Docker Hub..."
    docker push ${DOCKER_USERNAME}/${DOCKER_IMAGE}:${VERSION}
    
    print_info "Pushing latest to Docker Hub..."
    docker push ${DOCKER_USERNAME}/${DOCKER_IMAGE}:latest
    
    print_status "Pushed to Docker Hub successfully"
else
    print_warning "Skipped Docker Hub push"
fi

# Summary
echo ""
echo "=================================================="
echo "  Deployment Complete!"
echo "=================================================="
echo ""
echo "Deployed:"
echo "  • GitHub: https://github.com/${GITHUB_REPO}"
echo "  • Docker Hub: https://hub.docker.com/r/${DOCKER_USERNAME}/${DOCKER_IMAGE}"
echo ""
echo "Docker Images:"
echo "  • ${DOCKER_USERNAME}/${DOCKER_IMAGE}:${VERSION}"
echo "  • ${DOCKER_USERNAME}/${DOCKER_IMAGE}:latest"
echo ""
echo "Pull command:"
echo "  docker pull ${DOCKER_USERNAME}/${DOCKER_IMAGE}:${VERSION}"
echo "  docker pull ${DOCKER_USERNAME}/${DOCKER_IMAGE}:latest"
echo ""
print_status "All done!"
