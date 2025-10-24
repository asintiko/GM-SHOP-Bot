#!/bin/bash

# GM SHOP Bot - Quick Start Script

echo "🚀 Starting GM SHOP Bot..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Build and start services
echo "📦 Building and starting services..."
docker-compose up --build -d

# Wait for services to be healthy
echo "⏳ Waiting for database to be ready..."
sleep 5

# Show logs
echo "📋 Bot logs:"
docker-compose logs -f bot
