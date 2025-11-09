#!/bin/bash

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         🔍 macOS Permissions Diagnostic Tool 🔍          ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

echo "📍 Working directory: $(pwd)"
echo ""

# Activate venv
echo "1️⃣  Activating virtual environment..."
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "   ✅ Virtual environment activated"
else
    echo "   ❌ Virtual environment not found!"
    exit 1
fi
echo ""

# Check pynput installation
echo "2️⃣  Checking pynput installation..."
if python3 -c "import pynput" 2>/dev/null; then
    echo "   ✅ pynput is installed"
else
    echo "   ❌ pynput NOT installed!"
    echo "   Installing now..."
    pip install pynput
fi
echo ""

# Check pyobjc installation
echo "3️⃣  Checking pyobjc (for app tracking)..."
if python3 -c "from AppKit import NSWorkspace" 2>/dev/null; then
    echo "   ✅ pyobjc is installed"
else
    echo "   ❌ pyobjc NOT installed!"
    echo "   Installing now..."
    pip install pyobjc-framework-Cocoa
fi
echo ""

# Test action tracking
echo "4️⃣  Testing Action Capture..."
echo "   ⏳ Please CLICK YOUR MOUSE 3 TIMES in the next 5 seconds!"
echo ""
sleep 1

python3 << 'EOF'
import sys
sys.path.insert(0, 'backend')

from capture.action_tracker import ActionTracker
import time

tracker = ActionTracker()
tracker.start()

print("   ⏱️  Listening for 5 seconds...")
time.sleep(5)

actions = tracker.stop()

print(f"\n   📊 Result: Captured {len(actions)} actions")

if len(actions) > 0:
    print("   ✅ SUCCESS! Action tracking works!")
    print(f"\n   Actions captured:")
    for i, action in enumerate(actions[:5]):
        print(f"      {i+1}. {action.get('type')} at {action.get('x', 'N/A')}, {action.get('y', 'N/A')}")
    exit(0)
else:
    print("   ❌ FAILED! No actions captured.")
    print("\n   🔧 This means macOS is blocking input monitoring.")
    exit(1)
EOF

RESULT=$?
echo ""

if [ $RESULT -eq 0 ]; then
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║              ✅ ALL TESTS PASSED! ✅                      ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
    echo "🎉 Your system is ready to record workflows!"
    echo ""
    echo "Next steps:"
    echo "  1. Start recording: http://localhost:5173"
    echo "  2. Perform some actions"
    echo "  3. Stop recording"
    echo "  4. Check the workflow JSON for actual actions!"
    echo ""
else
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║           ⚠️  PERMISSIONS ISSUE DETECTED ⚠️               ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
    echo "🔧 FIX INSTRUCTIONS:"
    echo ""
    echo "1. Open System Settings"
    echo "2. Go to: Privacy & Security → Input Monitoring"
    echo "3. Look for 'Terminal' in the list"
    echo "4. If not there:"
    echo "   → Click '+' button"
    echo "   → Navigate to /Applications/Utilities/Terminal.app"
    echo "   → Click 'Open'"
    echo "5. If already there:"
    echo "   → Toggle it OFF"
    echo "   → Toggle it back ON"
    echo ""
    echo "6. CRITICAL: Quit Terminal completely (Cmd+Q)"
    echo "7. Reopen Terminal"
    echo "8. Run this test again:"
    echo "   cd ~/Desktop/Automato"
    echo "   bash test_permissions.sh"
    echo ""
    echo "📱 Quick link to settings:"
    echo "   open 'x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent'"
    echo ""
fi

