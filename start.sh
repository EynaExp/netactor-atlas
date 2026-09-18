#!/bin/bash

echo "==================================="
echo "  NetActor - AI Pentest Framework"
echo "==================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    echo "Please install Docker from https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed."
    echo "Please install Docker Compose from https://docs.docker.com/compose/install/"
    exit 1
fi

echo "Starting NetActor..."
echo ""
echo "App will be available at: http://localhost"
echo "Backend API at: http://localhost:8000"
echo ""

cd docker
docker-compose up --build

echo ""
echo "NetActor is running!"
echo "Open http://localhost in your browser"
