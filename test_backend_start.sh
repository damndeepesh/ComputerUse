#!/bin/bash
echo "Testing backend startup..."
cd "/Applications/AGI Assistant.app/Contents/Resources/backend" 2>/dev/null || cd "backend"
echo "Backend directory: $(pwd)"
echo "Python path: $(which python3)"
echo "Python version: $(python3 --version 2>&1)"
echo ""
echo "Checking dependencies..."
python3 -c "import fastapi, uvicorn, sqlalchemy" 2>&1 && echo "✅ Dependencies OK" || echo "❌ Dependencies MISSING"
echo ""
echo "Testing backend start..."
python3 main.py 2>&1 | head -20
