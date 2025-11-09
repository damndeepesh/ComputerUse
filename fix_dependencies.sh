#!/bin/bash

# Fix Dependencies Script
# Fixes Pillow and other dependency installation issues

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Fixing dependencies...${NC}"

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

source venv/bin/activate

# Upgrade pip and build tools
echo -e "${BLUE}Upgrading pip, setuptools, and wheel...${NC}"
pip install --upgrade pip setuptools wheel

# Install Pillow with pre-built wheels (avoids build issues)
echo -e "${BLUE}Installing Pillow (this may take a moment)...${NC}"
pip install --upgrade --only-binary :all: pillow || \
pip install --upgrade --no-build-isolation pillow || \
pip install --upgrade pillow

# Verify Pillow installation
python3 -c "import PIL; print(f'Pillow {PIL.__version__} installed successfully')" && \
echo -e "${GREEN}✅ Pillow installed successfully${NC}" || \
echo -e "${YELLOW}⚠️  Pillow installation may have issues${NC}"

# Install remaining requirements
echo -e "${BLUE}Installing remaining requirements...${NC}"
pip install -r requirements.txt

echo -e "${GREEN}✅ Dependencies fixed!${NC}"
echo -e "${BLUE}You can now run ./start.sh${NC}"

