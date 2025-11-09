#!/bin/bash

# AGI Assistant - Startup Script
# Run this after restarting Terminal

cd ~/Desktop/Automato

echo "🚀 Starting AGI Assistant..."
echo ""

# Activate virtual environment
source venv/bin/activate

# Start backend
echo "📦 Starting backend..."
nohup python backend/main.py > backend.log 2>&1 &
echo $! > backend.pid
sleep 5

# Start frontend
echo "🎨 Starting frontend..."
nohup npm run dev > frontend.log 2>&1 &
echo $! > frontend.pid
sleep 5

echo ""
echo "✅ AGI Assistant is running!"
echo ""
echo "🌐 Frontend: http://localhost:5173"
echo "🔧 Backend:  http://localhost:8000"
echo ""
echo "📝 Logs:"
echo "   Backend:  tail -f backend.log"
echo "   Frontend: tail -f frontend.log"
echo ""
echo "🎬 Ready to record workflows!"
echo ""

