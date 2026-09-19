#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv/bin/python"

echo "==================================="
echo "  NetActor - Starting services"
echo "==================================="

# Kill any existing processes
fuser -k 3000/tcp 2>/dev/null || true
fuser -k 3001/tcp 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
sleep 1

# 1. Toolbox MCP Server
echo "[1/3] Starting Toolbox MCP Server..."
cd "$DIR/toolbox/mcp-server"
setsid node index.js > /tmp/toolbox.log 2>&1 &
sleep 2
if curl -s http://localhost:3001/health > /dev/null 2>&1; then
    echo "  ✓ Toolbox running on port 3001"
else
    echo "  ✗ Toolbox failed to start"
fi

# 2. Backend API
echo "[2/3] Starting Backend API..."
cd "$DIR/backend"
setsid "$VENV" -m uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
sleep 3
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "  ✓ Backend running on port 8000"
else
    echo "  ✗ Backend failed to start"
fi

# 3. Frontend
echo "[3/3] Starting Frontend..."
cd "$DIR/frontend"
setsid npx vite --host 0.0.0.0 --port 3000 > /tmp/frontend.log 2>&1 &
sleep 3
if curl -s http://localhost:3000/ > /dev/null 2>&1; then
    echo "  ✓ Frontend running on port 3000"
else
    echo "  ✗ Frontend failed to start"
fi

echo ""
echo "==================================="
echo "  All services started!"
echo "==================================="
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo "  Toolbox:   http://localhost:3001"
echo "  Login:     admin / admin123"
echo "==================================="
