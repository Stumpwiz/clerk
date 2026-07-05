#!/bin/bash
# start-docker.sh - Helper script to start the community administration application with Docker

set -e

echo "🚀 Starting Community Administration Application..."
echo ""

# Check if oldEnv file exists
if [ ! -f oldEnv ]; then
    echo "❌ Error: .env file not found!"
    echo ""
    echo "Please create a .env file from .env.docker.example:"
    echo "  cp .env.docker.example .env"
    echo ""
    echo "Then edit .env and add the required database and authentication settings."
    echo ""
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running!"
    echo "Please start Docker Desktop and try again."
    echo ""
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose is not installed!"
    echo "Please install Docker Compose and try again."
    echo ""
    exit 1
fi

echo "✅ Environment check passed"
echo ""

# Build and start containers
echo "📦 Building and starting containers..."
echo "This may take a few minutes on first run (installing LaTeX)..."
echo ""

docker-compose up --build -d

echo ""
echo "✅ Containers started successfully!"
echo ""
echo "📱 Application URLs:"
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo "📋 Useful commands:"
echo "  View logs:        docker-compose logs -f"
echo "  Stop services:    docker-compose down"
echo "  Restart services: docker-compose restart"
echo ""
echo "🎉 Happy coding!"
