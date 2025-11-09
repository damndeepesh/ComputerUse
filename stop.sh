#!/bin/bash

# AGI Assistant - Stop Script
# This script stops all running services

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${BLUE}🛑 Stopping AGI Assistant...${NC}"
echo ""

# Stop processes by PID files
if [ -f backend.pid ]; then
    BACKEND_PID=$(cat backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo -e "${YELLOW}Stopping backend (PID: $BACKEND_PID)...${NC}"
        kill $BACKEND_PID 2>/dev/null || true
        rm backend.pid
        echo -e "${GREEN}✅ Backend stopped${NC}"
    else
        rm backend.pid
    fi
fi

if [ -f frontend.pid ]; then
    FRONTEND_PID=$(cat frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo -e "${YELLOW}Stopping frontend (PID: $FRONTEND_PID)...${NC}"
        kill $FRONTEND_PID 2>/dev/null || true
        rm frontend.pid
        echo -e "${GREEN}✅ Frontend stopped${NC}"
    else
        rm frontend.pid
    fi
fi

# Kill any remaining processes
echo -e "${BLUE}🧹 Cleaning up remaining processes...${NC}"

# Kill by process name
pkill -f "python.*main.py" 2>/dev/null && echo -e "${GREEN}✅ Backend processes cleaned${NC}" || true
pkill -f "electron" 2>/dev/null && echo -e "${GREEN}✅ Electron processes cleaned${NC}" || true
pkill -f "vite" 2>/dev/null && echo -e "${GREEN}✅ Vite processes cleaned${NC}" || true

# Kill by port
if lsof -ti:8000 >/dev/null 2>&1; then
    echo -e "${YELLOW}Killing process on port 8000...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
fi

if lsof -ti:5173 >/dev/null 2>&1; then
    echo -e "${YELLOW}Killing process on port 5173...${NC}"
    lsof -ti:5173 | xargs kill -9 2>/dev/null || true
fi

sleep 1

echo ""
echo -e "${GREEN}✅ All services stopped${NC}"
echo ""

