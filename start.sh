#!/bin/bash

# AGI Assistant - Complete Startup Script
# This script starts both the backend and frontend services

# Note: We don't use set -e here to allow graceful error handling during dependency installation

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${BLUE}🚀 Starting AGI Assistant...${NC}"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a port is in use
port_in_use() {
    lsof -ti:$1 >/dev/null 2>&1
}

# Function to kill process on port
kill_port() {
    local port=$1
    if port_in_use $port; then
        echo -e "${YELLOW}⚠️  Port $port is in use. Killing existing process...${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

# Check prerequisites
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

# Check Python
if ! command_exists python3; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

# Check Node.js
if ! command_exists node; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    exit 1
fi

# Check npm
if ! command_exists npm; then
    echo -e "${RED}❌ npm is not installed${NC}"
    exit 1
fi

# Check virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

# Check node_modules
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠️  Node modules not found. Installing...${NC}"
    npm install
    echo -e "${GREEN}✅ Node modules installed${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}🔧 Activating virtual environment...${NC}"
source venv/bin/activate

# Install Python dependencies if needed
if [ ! -f "venv/.installed" ]; then
    echo -e "${YELLOW}⚠️  Installing Python dependencies...${NC}"
    
    # Upgrade pip and setuptools first
    pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || true
    
    # Install Pillow first with pre-built wheels to avoid build issues
    echo -e "${BLUE}Installing Pillow...${NC}"
    pip install --upgrade --only-binary :all: pillow >/dev/null 2>&1 || \
    pip install --upgrade --no-build-isolation pillow >/dev/null 2>&1 || \
    pip install --upgrade pillow >/dev/null 2>&1 || true
    
    # Install remaining requirements
    echo -e "${BLUE}Installing other packages...${NC}"
    if pip install -r requirements.txt 2>&1; then
        touch venv/.installed
        echo -e "${GREEN}✅ Python dependencies installed${NC}"
    else
        echo -e "${YELLOW}⚠️  Some packages had issues. Checking if critical packages are installed...${NC}"
        # Check if critical packages are installed
        python3 -c "import fastapi, uvicorn, sqlalchemy, PIL" 2>/dev/null && {
            touch venv/.installed
            echo -e "${GREEN}✅ Critical dependencies are installed${NC}"
        } || {
            echo -e "${RED}❌ Critical dependencies missing. Run ./fix_dependencies.sh to fix${NC}"
            echo -e "${YELLOW}Or manually run: pip install -r requirements.txt${NC}"
        }
    fi
fi

# Check if AI model exists (optional)
if [ ! -d "models/models--microsoft--phi-2" ]; then
    echo -e "${YELLOW}⚠️  AI model not found. It will be downloaded on first use.${NC}"
fi

# Clean up any existing processes
echo -e "${BLUE}🧹 Cleaning up existing processes...${NC}"
pkill -f "python.*main.py" 2>/dev/null || true
pkill -f "electron" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 2

# Kill ports if in use
kill_port 8000
kill_port 5173

# Create necessary directories
echo -e "${BLUE}📁 Creating data directories...${NC}"
mkdir -p data/screenshots
mkdir -p data/recordings
mkdir -p data/transcripts
echo -e "${GREEN}✅ Directories ready${NC}"

# Start backend
echo ""
echo -e "${BLUE}📡 Starting backend server (port 8000)...${NC}"
cd backend
python main.py > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..
echo $BACKEND_PID > backend.pid
echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"

# Wait for backend to be ready
echo -e "${BLUE}⏳ Waiting for backend to initialize...${NC}"
for i in {1..30}; do
    # Try multiple endpoints to check if backend is ready
    if curl -s http://localhost:8000/docs >/dev/null 2>&1 || \
       curl -s http://localhost:8000/api/workflows >/dev/null 2>&1 || \
       curl -s http://localhost:8000/ >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        # Check if process is still running
        if ps -p $BACKEND_PID > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Backend is running but not responding yet. It may still be initializing.${NC}"
            echo -e "${BLUE}   Check backend.log for details. Continuing anyway...${NC}"
        else
            echo -e "${RED}❌ Backend process died. Check backend.log for errors.${NC}"
            exit 1
        fi
        break
    fi
    sleep 1
done

# Start frontend
echo ""
echo -e "${BLUE}🖥️  Starting frontend (Vite + Electron)...${NC}"
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > frontend.pid
echo -e "${GREEN}✅ Frontend started (PID: $FRONTEND_PID)${NC}"

# Wait a bit for frontend to start
sleep 3

# Display status
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ AGI Assistant is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📊 Service Status:${NC}"
echo -e "   Backend API:  ${GREEN}http://localhost:8000${NC}"
echo -e "   Frontend Dev: ${GREEN}http://localhost:5173${NC}"
echo -e "   Electron App: ${GREEN}Should open automatically${NC}"
echo ""
echo -e "${BLUE}📝 Logs:${NC}"
echo -e "   Backend:  ${YELLOW}backend.log${NC}"
echo -e "   Frontend: ${YELLOW}frontend.log${NC}"
echo ""
echo -e "${BLUE}🛑 To stop services:${NC}"
echo -e "   Run: ${YELLOW}./stop.sh${NC} or press Ctrl+C"
echo ""
echo -e "${BLUE}💡 Tips:${NC}"
echo -e "   - Check logs if services don't start properly"
echo -e "   - Make sure ports 8000 and 5173 are available"
echo -e "   - Electron window should open automatically"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down services...${NC}"
    
    if [ -f backend.pid ]; then
        BACKEND_PID=$(cat backend.pid)
        kill $BACKEND_PID 2>/dev/null || true
        rm backend.pid
    fi
    
    if [ -f frontend.pid ]; then
        FRONTEND_PID=$(cat frontend.pid)
        kill $FRONTEND_PID 2>/dev/null || true
        rm frontend.pid
    fi
    
    # Kill any remaining processes
    pkill -f "python.*main.py" 2>/dev/null || true
    pkill -f "electron" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    
    echo -e "${GREEN}✅ Services stopped${NC}"
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Wait for user interrupt or keep running
echo -e "${BLUE}⏳ Services are running. Press Ctrl+C to stop...${NC}"
echo ""

# Keep script running
wait
