#!/bin/bash
cd /Users/damndeepesh/Desktop/Automato
source venv/bin/activate

echo "🧪 Testing Python directly..."
echo "👆 CLICK YOUR MOUSE 3 TIMES NOW!"
echo ""

python3 << 'EOF'
import sys
sys.path.insert(0, 'backend')
from capture.action_tracker import ActionTracker
import time

tracker = ActionTracker()
tracker.start()
time.sleep(4)
actions = tracker.stop()

print(f"\n📊 Result: {len(actions)} actions captured\n")

if len(actions) > 0:
    print("✅✅✅ PERMISSIONS WORKING! ✅✅✅\n")
    for i, action in enumerate(actions[:3]):
        print(f"   {i+1}. {action}")
    print("\n🎉 Ready to record real workflows!\n")
else:
    print("❌ Still not working. Try:\n")
    print("1. Open System Settings → Privacy & Security")
    print("2. Look for 'Accessibility' (not just Input Monitoring)")
    print("3. Enable 'python3' and 'Terminal' there too")
    print("\nOR just demo with OCR-only workflows (still impressive!)\n")
EOF

read -p "Press Enter to close..."

