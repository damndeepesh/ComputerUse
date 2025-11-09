#!/bin/bash
cd /Users/damndeepesh/Desktop/Automato
source venv/bin/activate

echo "🧪 Testing if permissions work..."
echo "👆 CLICK YOUR MOUSE NOW! (3 seconds)"

python3 << 'PYTHON_EOF'
import sys
sys.path.insert(0, 'backend')
from capture.action_tracker import ActionTracker
import time

tracker = ActionTracker()
tracker.start()
time.sleep(3)
actions = tracker.stop()

print(f"\n📊 Captured: {len(actions)} actions")

if len(actions) > 0:
    print("✅✅✅ IT WORKS! ✅✅✅")
    print(f"Sample: {actions[0]}")
else:
    print("❌ Still blocked - did you restart Terminal?")
PYTHON_EOF
