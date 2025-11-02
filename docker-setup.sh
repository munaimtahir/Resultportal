#!/bin/bash
# Quick setup script for Result Portal Docker environment

set -e

echo "========================================="
echo "Result Portal - Docker Quick Setup"
echo "========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed."
    echo "Please install Docker from https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ Error: Docker Compose is not available."
    echo "Please install Docker Compose v2 or update Docker Desktop."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.docker..."
    cp .env.docker .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  Note: You can edit .env to configure Google OAuth credentials"
else
    echo "ℹ️  .env file already exists, skipping..."
fi
echo ""

# Build and start services
echo "🏗️  Building Docker containers..."
docker compose build

echo ""
echo "🚀 Starting services..."
docker compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check if services are running
if docker compose ps | grep -q "Up"; then
    echo "✅ Services are running!"
    echo ""
    echo "========================================="
    echo "🎉 Setup Complete!"
    echo "========================================="
    echo ""
    echo "Your Result Portal is now running at:"
    echo "  🌐 http://localhost:8000"
    echo ""
    echo "Useful commands:"
    echo "  📊 View logs:           docker compose logs -f web"
    echo "  👤 Create superuser:    docker compose exec web python manage.py createsuperuser"
    echo "  🧪 Run tests:           docker compose exec web pytest"
    echo "  🛑 Stop services:       docker compose down"
    echo "  🗑️  Clean everything:    docker compose down -v"
    echo ""
    echo "For more information, see README.md"
else
    echo "❌ Error: Services failed to start"
    echo "Check logs with: docker compose logs"
    exit 1
fi
