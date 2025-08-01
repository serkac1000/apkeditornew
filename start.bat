@echo off
set "PYTHON_PATH=C:\Users\serka\AppData\Local\Programs\Python\Python312\python.exe"
title APK Editor Server
color 0A

echo ============================================================
echo                    APK Editor Web Application
echo ============================================================
echo.

REM Check if Python is installed
"%PYTHON_PATH%" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not found at %PYTHON_PATH%
    echo Please install Python 3.11+ from https://python.org or update the path in this script.
    echo.
    pause
    exit /b 1
)

echo Checking Python version...
"%PYTHON_PATH%" --version

REM Check if required files exist
if not exist "main.py" (
    echo ERROR: main.py not found in current directory
    echo Please make sure you're running this script from the APK Editor directory
    echo.
    pause
    exit /b 1
)

echo.
echo Installing/Updating dependencies...
echo ============================================================

REM Install required packages
"%PYTHON_PATH%" -m pip install flask flask-sqlalchemy werkzeug gunicorn psycopg2-binary email-validator pillow

if errorlevel 1 (
    echo.
    echo WARNING: Some packages failed to install
    echo The application may still work with basic functionality
    echo.
)

echo.
echo Creating necessary directories...
if not exist "projects" mkdir projects
if not exist "uploads" mkdir uploads
if not exist "temp" mkdir temp
if not exist "static" mkdir static
if not exist "templates" mkdir templates

echo.
echo Starting APK Editor Server...
echo ============================================================
echo Server will be available at: http://127.0.0.1:5000
echo Press Ctrl+C to stop the server
echo ============================================================
echo.

REM Start the application
"%PYTHON_PATH%" main.py

echo.
echo Server stopped.
pause