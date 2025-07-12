#!/bin/bash

# Docker network testing script for diskcache_rs
set -e

echo "🐳 Starting Docker network filesystem tests..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running"
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed or not in PATH"
    exit 1
fi

# Create test directories
echo "📁 Creating test directories..."
mkdir -p test-exports test-shares

# Cleanup function
cleanup() {
    echo "🧹 Cleaning up Docker containers and volumes..."
    docker-compose -f docker-compose.test.yml down -v --remove-orphans || true
    docker system prune -f || true
    rm -rf test-exports test-shares || true
}

# Set trap for cleanup
trap cleanup EXIT

# Start test environment
echo "🚀 Starting test environment..."
docker-compose -f docker-compose.test.yml up -d nfs-server smb-server

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
if ! docker-compose -f docker-compose.test.yml ps | grep -q "Up"; then
    echo "❌ Failed to start test services"
    docker-compose -f docker-compose.test.yml logs
    exit 1
fi

echo "✅ Test services are running"

# Run tests
echo "🧪 Running Docker network tests..."
if docker-compose -f docker-compose.test.yml run --rm test-runner; then
    echo "✅ All Docker network tests passed!"
else
    echo "❌ Some Docker network tests failed"
    exit 1
fi

echo "🎉 Docker network testing completed successfully!"
