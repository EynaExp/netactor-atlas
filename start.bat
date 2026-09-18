@echo off
echo ===================================
echo   NetActor - AI Pentest Framework
echo ===================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not installed.
    echo Please install Docker from https://docs.docker.com/get-docker/
    pause
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker Compose is not installed.
    echo Please install Docker Compose from https://docs.docker.com/compose/install/
    pause
    exit /b 1
)

echo Starting NetActor...
echo.
echo Backend will be available at: http://localhost:8000
echo Frontend will be available at: http://localhost:3000
echo.

cd docker
docker-compose up --build

echo.
echo NetActor is running!
echo Open http://localhost:3000 in your browser
pause
