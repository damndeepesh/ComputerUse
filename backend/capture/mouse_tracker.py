"""
Independent mouse tracking module
Handles ALL mouse-related tracking: movements, clicks, scrolls
DO NOT MODIFY KEYBOARD OR OTHER FUNCTIONALITY HERE
"""
import time
from datetime import datetime
from pynput import mouse


class MouseTracker:
    """Independent mouse tracking - handles movements, clicks, scrolls"""
    
    def __init__(self, app_tracker=None):
        self.actions = []  # Only mouse actions (move, click, scroll)
        self.mouse_listener = None
        self.is_tracking = False
        
        # Movement tracking settings - optimized for capture
        self.last_recorded_move_position = None
        self.last_move_time = 0
        self.move_cooldown = 0.1  # 100ms between movement recordings
        self.move_distance_threshold = 10  # 10px minimum movement
        
        # Click tracking
        self.last_click_time = None
        self.last_click_position = None
        self.last_click_button = None
        self.last_press_time = None
        self.last_press_position = None
        self.double_click_timeout = 0.8
        self.double_click_distance = 20
        
        # Scroll tracking
        self.last_scroll_time = 0
        self.scroll_threshold = 0.1
        self.scroll_cooldown = 0.2
        
        # Shift+click selection tracking
        self.selection_start_click = None
        self.selection_timeout = 5.0
        self.last_shift_release_time = None
        self.pressed_modifiers = set()  # Track Shift key state
        
        # App context
        self.app_tracker = app_tracker
    
    def start(self):
        """Start mouse tracking"""
        if self.is_tracking:
            return
        
        self.is_tracking = True
        self.actions = []
        self.last_recorded_move_position = None
        self.last_move_time = 0
        self.last_click_time = None
        self.last_click_position = None
        self.last_click_button = None
        self.last_press_time = None
        self.last_press_position = None
        self.selection_start_click = None
        self.last_shift_release_time = None
        
        # Start mouse listener with better error handling
        try:
            self.mouse_listener = mouse.Listener(
                on_move=self._on_mouse_move,
                on_click=self._on_mouse_click,
                on_scroll=self._on_mouse_scroll,
            )
            self.mouse_listener.start()
            
            # Wait a bit to see if listener thread starts successfully
            time.sleep(0.3)
            
            # Check if listener is actually alive
            is_alive = self.mouse_listener.is_alive()
            
            if is_alive:
                print("✅ Mouse tracker started and running")
                # Double-check thread status
                try:
                    if hasattr(self.mouse_listener, '_thread'):
                        thread = self.mouse_listener._thread
                        if thread and thread.is_alive():
                            print("✅ Mouse listener thread verified as alive")
                        else:
                            print("⚠️  Mouse listener thread exists but not alive - permissions issue likely")
                    else:
                        if hasattr(self.mouse_listener, '_native'):
                            print("✅ Mouse listener native handler created")
                        else:
                            print("⚠️  Could not verify mouse listener internal state")
                except Exception as thread_check_error:
                    print(f"⚠️  Could not verify thread status: {thread_check_error}")
            else:
                print("⚠️  Mouse tracker started but listener is NOT running")
                print("⚠️  This usually means Accessibility permissions are missing")
                print("⚠️  SOLUTION: System Settings > Privacy & Security > Accessibility")
                print("⚠️  Enable for Terminal or Python")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Failed to start mouse tracker: {error_msg}")
            print("⚠️  This is usually a permissions issue on macOS")
            print("⚠️  SOLUTION: System Settings > Privacy & Security > Accessibility")
            print("⚠️  Enable for Terminal or Python")
            
            import traceback
            traceback.print_exc()
    
    def stop(self):
        """Stop mouse tracking and return actions"""
        if not self.is_tracking:
            return self.actions.copy()
        
        print("⏹️  Stopping mouse tracking...")
        self.is_tracking = False
        
        # Wait for in-flight events
        time.sleep(0.2)
        
        # Stop listener
        try:
            if self.mouse_listener:
                self.mouse_listener.stop()
        except Exception as e:
            print(f"⚠️  Error stopping mouse listener: {e}")
        
        # Count actions
        move_actions = [a for a in self.actions if a.get("type") == "move"]
        click_actions = [a for a in self.actions if a.get("type") == "click"]
        scroll_actions = [a for a in self.actions if a.get("type") == "scroll"]
        
        print(f"   🖱️  Mouse actions captured: {len(move_actions)} moves, {len(click_actions)} clicks, {len(scroll_actions)} scrolls")
        
        return self.actions.copy()
    
    def set_shift_state(self, is_pressed, release_time=None):
        """Update Shift key state (called from keyboard tracker)"""
        if is_pressed:
            self.pressed_modifiers.add('shift')
        else:
            self.pressed_modifiers.discard('shift')
            if release_time:
                self.last_shift_release_time = release_time
    
    def _on_mouse_move(self, x, y):
        """Handle mouse movement - ALWAYS records first movement"""
        if not self.is_tracking:
            return
        
        # Debug: Log first few movements to verify listener is working
        if not hasattr(self, '_move_count'):
            self._move_count = 0
        self._move_count += 1
        if self._move_count <= 3:
            print(f"🖱️  Mouse move #{self._move_count} detected - listener is working! ({int(x)}, {int(y)})")
        
        current_time = time.time()
        
        # CRITICAL: Always record the first movement
        if self.last_recorded_move_position is None:
            # First movement - always record it
            print(f"🖱️ ✅ Recording FIRST mouse movement: ({int(x)}, {int(y)})")
        else:
            # Check cooldown
            time_since_last_move = current_time - self.last_move_time
            if time_since_last_move < self.move_cooldown:
                return
            
            # Check distance
            last_x, last_y = self.last_recorded_move_position
            distance = ((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5
            if distance < self.move_distance_threshold:
                return
        
        # Record movement
        action = {
            "type": "move",
            "x": x,
            "y": y,
            "timestamp": current_time,
            "timestamp_iso": datetime.now().isoformat(),
        }
        
        # Add app context
        if self.app_tracker:
            try:
                app_context = self.app_tracker.get_current_app()
                if app_context:
                    action['app_name'] = app_context.get('name')
                    action['app_bundle_id'] = app_context.get('bundle_id')
            except:
                pass
        
        self.actions.append(action)
        self.last_recorded_move_position = (x, y)
        self.last_move_time = current_time
        
        # Log first few movements (less verbose)
        move_count = len([a for a in self.actions if a.get("type") == "move"])
        if move_count <= 3:
            print(f"🖱️ ✅ Mouse move #{move_count} recorded: ({int(x)}, {int(y)})")
        elif move_count % 10 == 0:
            # Log every 10th movement to show progress
            print(f"🖱️ ✅ Mouse move #{move_count} recorded: ({int(x)}, {int(y)})")
    
    def _on_mouse_click(self, x, y, button, pressed):
        """Handle mouse click"""
        if not self.is_tracking:
            return
        
        button_name = button.name.lower()
        if button_name == 'button.left':
            button_name = 'left'
        elif button_name == 'button.right':
            button_name = 'right'
        elif button_name == 'button.middle':
            button_name = 'middle'
        
        current_time = time.time()
        
        # Track PRESS for double-click detection
        if pressed:
            self.last_press_time = current_time
            self.last_press_position = (x, y)
            return  # Only record on release
        
        # Record on RELEASE
        shift_pressed = 'shift' in self.pressed_modifiers
        
        # Handle Shift+click selections
        if shift_pressed and self.selection_start_click is not None:
            start_action = self.selection_start_click
            start_x = start_action.get('x', 0)
            start_y = start_action.get('y', 0)
            start_action['is_selection_start'] = True
            start_action['selection_end_x'] = x
            start_action['selection_end_y'] = y
            print(f"📋 Shift+click selection: ({start_x}, {start_y}) to ({x}, {y})")
        elif shift_pressed:
            # First click in selection
            pass
        else:
            # Regular click - clear selection start
            if self.selection_start_click is not None:
                time_since_shift_release = None
                if self.last_shift_release_time:
                    time_since_shift_release = current_time - self.last_shift_release_time
                if time_since_shift_release is None or time_since_shift_release > 1.0:
                    self.selection_start_click = None
        
        # Check for double click
        is_double_click = False
        clicks = 1
        
        if (self.last_click_time is not None and 
            self.last_click_button == button_name and
            self.last_click_position is not None):
            time_since_last_release = current_time - self.last_click_time
            distance = ((x - self.last_click_position[0]) ** 2 + 
                       (y - self.last_click_position[1]) ** 2) ** 0.5
            if (time_since_last_release <= self.double_click_timeout and 
                distance <= self.double_click_distance):
                is_double_click = True
                clicks = 2
        
        # If double click, remove previous single click (if same position)
        if is_double_click and self.actions and self.actions[-1].get("type") == "click":
            last_action = self.actions[-1]
            last_x = last_action.get('x', 0)
            last_y = last_action.get('y', 0)
            last_position_distance = ((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5
            if last_position_distance <= 5:
                self.actions.pop()
                print(f"🔄 ✅ Converted single click to double click!")
        
        # Record click action
        action = {
            "type": "click",
            "x": x,
            "y": y,
            "button": button_name,
            "clicks": clicks,
            "timestamp": current_time,
            "timestamp_iso": datetime.now().isoformat(),
        }
        
        if shift_pressed:
            action['shift_pressed'] = True
            if self.selection_start_click is None:
                self.selection_start_click = action
                print(f"📋 First click in Shift+click selection at ({x}, {y})")
        
        # Add app context
        if self.app_tracker:
            try:
                app_context = self.app_tracker.get_current_app()
                if app_context:
                    action['app_name'] = app_context.get('name')
                    action['app_bundle_id'] = app_context.get('bundle_id')
                    
                    # Detect spreadsheet cell if in spreadsheet app
                    app_name = app_context.get('name', '').lower()
                    spreadsheet_apps = ['excel', 'numbers', 'libreoffice calc', 'google sheets']
                    if any(spreadsheet in app_name for spreadsheet in spreadsheet_apps):
                        action['spreadsheet_context'] = {
                            'is_spreadsheet': True,
                            'app_name': app_context.get('name'),
                            'note': 'Cell position requires OCR analysis'
                        }
            except:
                pass
        
        self.actions.append(action)
        
        # Update tracking
        if not is_double_click:
            self.last_click_time = current_time
            self.last_click_position = (x, y)
            self.last_click_button = button_name
        else:
            self.last_click_time = None
            self.last_click_position = None
            self.last_click_button = None
        
        print(f"🖱️ Click recorded: {button_name} at ({x}, {y}), clicks={clicks}, shift={shift_pressed}")
    
    def _on_mouse_scroll(self, x, y, dx, dy):
        """Handle mouse scroll"""
        if not self.is_tracking:
            return
        
        scroll_magnitude = abs(dx) + abs(dy)
        if scroll_magnitude < self.scroll_threshold:
            return
        
        current_time = time.time()
        if current_time - self.last_scroll_time < self.scroll_cooldown:
            return
        
        action = {
            "type": "scroll",
            "x": x,
            "y": y,
            "dx": dx,
            "dy": dy,
            "timestamp": current_time,
            "timestamp_iso": datetime.now().isoformat(),
        }
        
        # Add app context
        if self.app_tracker:
            try:
                app_context = self.app_tracker.get_current_app()
                if app_context:
                    action['app_name'] = app_context.get('name')
                    action['app_bundle_id'] = app_context.get('bundle_id')
            except:
                pass
        
        self.actions.append(action)
        self.last_scroll_time = current_time
        print(f"🖱️ Scroll recorded at ({x}, {y}): dx={dx}, dy={dy}")

