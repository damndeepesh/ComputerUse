"""
Action Tracker - Wrapper that combines MouseTracker and KeyboardTracker
This file coordinates both trackers but doesn't contain their logic
"""
import time
from capture.mouse_tracker import MouseTracker
from capture.keyboard_tracker import KeyboardTracker


class ActionTracker:
    """Tracks mouse and keyboard actions during recording - uses independent trackers"""
    
    def __init__(self, app_tracker=None):
        self.app_tracker = app_tracker
        
        # Initialize independent trackers
        self.mouse_tracker = MouseTracker(app_tracker)
        self.keyboard_tracker = KeyboardTracker(app_tracker)
        
        # Connect Shift state between trackers
        self.keyboard_tracker.set_shift_state_callback(self.mouse_tracker.set_shift_state)
        
        self.is_tracking = False
        
    def start(self):
        """Start tracking user actions"""
        if self.is_tracking:
            return
        
        self.is_tracking = True
        
        # Start both independent trackers
        self.mouse_tracker.start()
        self.keyboard_tracker.start()
        
        print("✅ Action tracking started (mouse + keyboard)")
    
    def stop(self):
        """Stop tracking and return combined actions"""
        if not self.is_tracking:
            # Get actions from both trackers even if not tracking
            mouse_actions = self.mouse_tracker.stop()
            keyboard_actions = self.keyboard_tracker.stop()
            return mouse_actions + keyboard_actions
        
        print("⏹️  Stopping action tracking...")
        self.is_tracking = False
        
        # Stop both trackers
        mouse_actions = self.mouse_tracker.stop()
        keyboard_actions = self.keyboard_tracker.stop()
        
        # Combine actions
        all_actions = mouse_actions + keyboard_actions
        
        # Sort by timestamp
        all_actions.sort(key=lambda a: a.get('timestamp', 0))
        
        # Count actions
        action_types = {}
        for action in all_actions:
            action_type = action.get("type", "unknown")
            action_types[action_type] = action_types.get(action_type, 0) + 1
        
        print(f"✅ Action tracking stopped. Captured {len(all_actions)} total actions")
        print(f"   📊 Action breakdown: {action_types}")
        
        return all_actions
    
    def get_actions(self):
        """Get current list of actions from both trackers"""
        mouse_actions = self.mouse_tracker.actions.copy()
        keyboard_actions = self.keyboard_tracker.get_actions()
        all_actions = mouse_actions + keyboard_actions
        all_actions.sort(key=lambda a: a.get('timestamp', 0))
        return all_actions
