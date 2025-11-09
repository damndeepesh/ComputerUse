@echo off
REM AGI Assistant Startup Script for Windows

echo Starting AGI Assistant...

REM Check if virtual environment exists
if not exist "venv" (
    echo Virtual environment not found. Please run: python -m venv venv
    exit /b 1
)

REM Check if node_modules exists
if not exist "node_modules" (
    echo Node modules not found. Please run: npm install
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start backend in background
echo Starting backend server...
start /B python backend\main.py

REM Wait for backend to start
timeout /t 3 /nobreak

REM Start frontend
echo Starting frontend application...
npm run dev

pause


