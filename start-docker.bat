@echo off
REM start-docker.bat - Helper script to start the Clerk application with Docker (Windows)

echo 🚀 Starting Clerk Application...
echo.

REM Check if .env file exists
if not exist .env (
    echo ❌ Error: .env file not found!
    echo.
    echo Please create a .env file from .env.docker.example:
    echo   copy .env.docker.example .env
    echo.
    echo Then edit .env and add your Clerk credentials from:
    echo   https://dashboard.clerk.com
    echo.
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Docker is not running!
    echo Please start Docker Desktop and try again.
    echo.
    exit /b 1
)

echo ✅ Environment check passed
echo.

REM Build and start containers
echo 📦 Building and starting containers...
echo This may take a few minutes on first run (installing LaTeX)...
echo.

docker-compose up --build -d

echo.
echo ✅ Containers started successfully!
echo.
echo 📱 Application URLs:
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo.
echo 📋 Useful commands:
echo   View logs:        docker-compose logs -f
echo   Stop services:    docker-compose down
echo   Restart services: docker-compose restart
echo.
echo 🎉 Happy coding!
