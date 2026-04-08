#!/usr/bin/env bash
# ChaosMesh Arena — Multi-Arch Build & Push (Task 3.8)
# Builds the Docker image for amd64 and arm64, and pushes to a container registry.

set -euo pipefail

IMAGE_NAME=${1:-"your-registry/chaosmesh-arena"}
TAG=${2:-"latest"}

echo "==============================================="
echo "⚡ ChaosMesh Arena: Multi-Arch Docker Build"
echo "Target: ${IMAGE_NAME}:${TAG}"
echo "==============================================="

# Ensure buildx is available and created
if ! docker buildx inspect chaosmesh-builder > /dev/null 2>&1; then
    echo "Creating new docker buildx builder instance..."
    docker buildx create --name chaosmesh-builder --use
else
    docker buildx use chaosmesh-builder
fi

# Multi-arch build and push
echo "Building and pushing for linux/amd64 and linux/arm64..."
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --target production \
    -t "${IMAGE_NAME}:${TAG}" \
    --push \
    .

echo "==============================================="
echo "✅ Build & Push Complete!"
echo "Image available at: ${IMAGE_NAME}:${TAG}"
echo "==============================================="
