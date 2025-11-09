"""
Independent keyboard tracking module
Handles ALL keyboard-related tracking: text input, hotkeys
DO NOT MODIFY MOUSE OR OTHER FUNCTIONALITY HERE
"""
import time
from datetime import datetime
from pynput import keyboard

# Import clipboard monitoring (macOS/Windows compatible)
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    print("⚠️  pyperclip not available - clipboard tracking disabled")


class KeyboardTracker:
    """Independent keyboard tracking - handles text input and hotkeys"""
    
    def __init__(self, app_tracker=None):
        self.actions = []  # Only keyboard actions (type, hotkey)
        self.keyboard_listener = None
        self.is_tracking = False
        
        # Text capture settings
        self.typed_text = []
        self.text_flush_interval = 0.15  # Flush every 0.15s
        self.text_idle_timeout = 0.2  # Flush after 0.2s idle
        self.last_text_flush_time = time.time()
        self.last_char_time = time.time()
        self.last_typed_action_index = None
        
        # Key tracking
        self.pressed_modifiers = set()
        self.key_sequence = []
        self.active_keys = {}
        self.key_combination_timeout = 2.0  # Increased to capture keys pressed simultaneously
        self.pending_hotkey = None
        
        # Clipboard tracking
        self.last_clipboard_content = None
        self.pending_copy = None
        self.pending_paste = None
        
        # Spreadsheet context tracking
        self.spreadsheet_apps = ['excel', 'numbers', 'libreoffice calc', 'google sheets']
        
        # App context
        self.app_tracker = app_tracker
        
        # Callback for Shift state updates (for mouse tracker)
        self.shift_state_callback = None
    
    def set_shift_state_callback(self, callback):
        """Set callback to notify mouse tracker of Shift state changes"""
        self.shift_state_callback = callback
    
    def start(self):
        """Start keyboard tracking"""
        if self.is_tracking:
            return
        
        self.is_tracking = True
        self.actions = []
        self.typed_text = []
        self.last_text_flush_time = time.time()
        self.last_char_time = time.time()
        self.last_typed_action_index = None
        self.key_sequence = []
        self.active_keys = {}
        self.pressed_modifiers = set()
        self.pending_hotkey = None
        
        # Start keyboard listener with better error handling
        try:
            self.keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
                suppress=False  # Don't suppress events, just monitor
            )
            self.keyboard_listener.start()
            
            # Wait a bit to see if listener thread starts successfully
            time.sleep(0.3)
            
            # Check if listener is actually alive
            is_alive = self.keyboard_listener.is_alive()
            
            if is_alive:
                print("✅ Keyboard tracker started and running")
                # Double-check thread status
                try:
                    if hasattr(self.keyboard_listener, '_thread'):
                        thread = self.keyboard_listener._thread
                        if thread and thread.is_alive():
                            print("✅ Keyboard listener thread verified as alive")
                        else:
                            print("⚠️  Keyboard listener thread exists but not alive - permissions issue likely")
                            print("⚠️  The listener may have crashed silently due to missing permissions")
                    else:
                        # Try alternative attribute name
                        if hasattr(self.keyboard_listener, '_native'):
                            print("✅ Keyboard listener native handler created")
                        else:
                            print("⚠️  Could not verify keyboard listener internal state")
                except Exception as thread_check_error:
                    print(f"⚠️  Could not verify thread status: {thread_check_error}")
            else:
                print("⚠️  Keyboard tracker started but listener is NOT running")
                print("⚠️  This usually means Input Monitoring permissions are missing")
                print("⚠️  The listener thread may have crashed silently")
                print("⚠️  SOLUTION: System Settings > Privacy & Security > Input Monitoring")
                print("⚠️  Enable for Terminal or Python")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Failed to start keyboard tracker: {error_msg}")
            print("⚠️  This is usually a permissions issue on macOS")
            print("⚠️  Check Input Monitoring permissions in System Settings > Privacy & Security")
            print("⚠️  On macOS: System Settings > Privacy & Security > Input Monitoring")
            print("⚠️  Make sure Terminal/Python is enabled for Input Monitoring")
            
            # Check for specific pynput errors
            if 'CFMachPortCreateRunLoopSource' in error_msg or 'KeyError' in error_msg:
                print("⚠️  macOS-specific error detected - Input Monitoring permission required")
                print("⚠️  Try: System Settings > Privacy & Security > Input Monitoring > Enable for Terminal")
            
            import traceback
            traceback.print_exc()
            
            # Don't set is_tracking to False - allow it to continue but warn user
    
    def stop(self):
        """Stop keyboard tracking and return actions"""
        if not self.is_tracking:
            return self.actions.copy()
        
        print("⏹️  Stopping keyboard tracking...")
        
        # CRITICAL: Flush remaining text MULTIPLE times
        for attempt in range(3):
            if self.typed_text:
                final_text = ''.join(self.typed_text)
                print(f"📝 Flushing remaining text (attempt {attempt + 1}): '{final_text}' ({len(final_text)} chars)")
                self._flush_typed_text()
                time.sleep(0.1)
            else:
                break
        
        # Wait for in-flight events
        time.sleep(0.3)
        
        # Flush again after wait
        if self.typed_text:
            flush_text = ''.join(self.typed_text)
            print(f"📝 Flush after wait: '{flush_text}'")
            self._flush_typed_text()
        
        self.is_tracking = False
        
        # Stop listener
        try:
            if self.keyboard_listener:
                self.keyboard_listener.stop()
        except Exception as e:
            print(f"⚠️  Error stopping keyboard listener: {e}")
        
        # Wait briefly
        time.sleep(0.1)
        
        # Final flush
        if self.typed_text:
            flush_text = ''.join(self.typed_text)
            print(f"📝 Final flush: '{flush_text}'")
            self._flush_typed_text()
        
        # Count actions
        typed_actions = [a for a in self.actions if a.get("type") == "type"]
        hotkey_actions = [a for a in self.actions if a.get("type") == "hotkey"]
        total_chars = sum(len(a.get("text", "")) for a in typed_actions)
        
        print(f"   📝 Keyboard actions captured: {len(typed_actions)} text segments ({total_chars} chars), {len(hotkey_actions)} hotkeys")
        
        if len(typed_actions) == 0 and len(hotkey_actions) == 0:
            print(f"   ⚠️  WARNING: No keyboard actions captured!")
            print(f"   ⚠️  Check Input Monitoring permissions in System Settings > Privacy & Security")
        
        return self.actions.copy()
    
    def _on_key_press(self, key):
        """Handle key press - with error handling to prevent silent failures"""
        try:
            if not self.is_tracking:
                return
            
            # Debug: Log first few key presses to verify listener is working
            if not hasattr(self, '_key_press_count'):
                self._key_press_count = 0
            self._key_press_count += 1
            if self._key_press_count <= 3:
                print(f"⌨️  Key press #{self._key_press_count} detected - listener is working!")
            
            current_time = time.time()
            key_id = id(key)
            key_info = self._key_to_identifier(key)
            
            # Track active keys
            self.active_keys[key_id] = {
                'key': key,
                'key_info': key_info,
                'press_time': current_time
            }
            
            # Add to key sequence
            self.key_sequence.append({
                'event': 'press',
                'key_info': key_info,
                'timestamp': current_time,
                'key_id': key_id
            })
            
            # Detect and track modifiers (cross-platform: macOS cmd = Windows Windows key)
            modifier_key = None
            # On macOS: cmd is Command key, on Windows: cmd is Windows key
            # Both should be tracked as 'cmd' for cross-platform compatibility
            if key == keyboard.Key.cmd or key == keyboard.Key.cmd_l or key == keyboard.Key.cmd_r:
                modifier_key = 'cmd'
                self.pressed_modifiers.add('cmd')
            elif key == keyboard.Key.ctrl or key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                modifier_key = 'ctrl'
                self.pressed_modifiers.add('ctrl')
            elif key == keyboard.Key.alt or key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                modifier_key = 'alt'
                self.pressed_modifiers.add('alt')
            elif key == keyboard.Key.shift or key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                modifier_key = 'shift'
                self.pressed_modifiers.add('shift')
                # Notify mouse tracker of Shift state
                if self.shift_state_callback:
                    self.shift_state_callback(True, None)
            
            # If this is a modifier, set up pending hotkey but DON'T return early
            # We need to wait for the final key in the combination
            if modifier_key and modifier_key in ['cmd', 'ctrl', 'alt']:
                    self._flush_typed_text()
                    self.pending_hotkey = {
                        'modifiers': set(self.pressed_modifiers),
                        'timestamp': current_time
                    }
                # Don't return - continue to check if we have a complete combination
            
            # Get character
            char = None
            try:
                if hasattr(key, 'char') and key.char is not None:
                    char = key.char
                    if not isinstance(char, str) or len(char) != 1:
                        char = None
            except:
                char = None
            
            # Handle special keys
            key_name = None
            if key == keyboard.Key.enter:
                key_name = 'enter'
            elif key == keyboard.Key.tab:
                key_name = 'tab'
            elif key == keyboard.Key.space:
                key_name = 'space'
            elif key == keyboard.Key.backspace:
                key_name = 'backspace'
            elif key == keyboard.Key.delete:
                key_name = 'delete'
            elif key == keyboard.Key.esc:
                key_name = 'escape'
            
            # Check if we have non-shift modifiers pressed (cmd/ctrl/alt)
            # Shift alone with a character should just produce a capital letter, not a hotkey
            non_shift_modifiers = {m for m in self.pressed_modifiers if m != 'shift'}
            has_non_shift_modifiers = len(non_shift_modifiers) > 0
            has_any_modifiers = len(self.pressed_modifiers) > 0
            
            # Handle character input
            if char is not None:
                if has_non_shift_modifiers:
                    # Key combination with cmd/ctrl/alt - include ALL modifiers (including shift if present)
                    self._flush_typed_text()
                    # Use all pressed modifiers, including shift if it's part of the combination
                    self._record_hotkey(char, current_time, set(self.pressed_modifiers))
                else:
                    # Regular character - add to buffer
                    self.typed_text.append(char)
                    
                    if self.last_char_time is None or len(self.typed_text) == 1:
                        self.last_char_time = current_time
                        self.last_text_flush_time = current_time
                    else:
                        self.last_char_time = current_time
                    
                    # Only log every 5th character to reduce noise
                    if len(self.typed_text) % 5 == 1 or len(self.typed_text) <= 3:
                        print(f"📝 Character captured: '{char}' (buffer: {len(self.typed_text)} chars)")
                    
                    # Check if should flush
                    time_since_last_flush = current_time - self.last_text_flush_time
                    time_since_last_char = current_time - self.last_char_time if self.last_char_time else 0
                    should_flush_interval = time_since_last_flush >= self.text_flush_interval and len(self.typed_text) > 0
                    should_flush_idle = (self.last_char_time and time_since_last_char >= self.text_idle_timeout) and len(self.typed_text) > 0
                    should_flush_char_count = len(self.typed_text) >= 10
                    
                    if should_flush_interval or should_flush_idle or should_flush_char_count:
                        reason = "interval" if should_flush_interval else ("idle timeout" if should_flush_idle else "char count")
                        print(f"📝 Flushing after {reason}: {len(self.typed_text)} chars")
                        self._flush_typed_text()
                    return
            
            # Handle special keys
            if key_name:
                if key_name == 'space':
                    if has_non_shift_modifiers:
                        # Space with cmd/ctrl/alt modifiers is a hotkey
                        self._flush_typed_text()
                        self._record_hotkey(key_name, current_time, set(self.pressed_modifiers))
                    else:
                        self.typed_text.append(' ')
                        self.last_char_time = current_time
                        if current_time - self.last_text_flush_time >= self.text_flush_interval or len(self.typed_text) >= 10:
                            self._flush_typed_text()
                elif key_name == 'backspace':
                    # Flush any pending typed text first
                    self._flush_typed_text()
                    # Record backspace as a separate action so it can be replayed
                    action = {
                        "type": "backspace",
                        "timestamp": current_time,
                        "timestamp_iso": datetime.now().isoformat(),
                    }
                    # Add app context
                    app_context = self._get_app_context()
                    if app_context:
                        action['app_name'] = app_context.get('name')
                        action['app_bundle_id'] = app_context.get('bundle_id')
                    self.actions.append(action)
                    print(f"⌫ Backspace recorded")
                elif key_name in ['enter', 'tab']:
                    self._flush_typed_text()
                    if has_non_shift_modifiers:
                        # Enter/Tab with cmd/ctrl/alt modifiers is a hotkey
                        print(f"⌨️  {key_name.capitalize()} with modifiers recorded as hotkey")
                        self._record_hotkey(key_name, current_time, set(self.pressed_modifiers))
                    else:
                        # Enter/Tab alone is a hotkey
                        print(f"⌨️  {key_name.capitalize()} key recorded as hotkey")
                        self._record_hotkey(key_name, current_time, set())
                else:
                    # Other special keys (escape, delete, etc.)
                    self._flush_typed_text()
                    self._record_hotkey(key_name, current_time, set(self.pressed_modifiers))
        except Exception as e:
            print(f"❌ ERROR in _on_key_press: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_key_release(self, key):
        """Handle key release - with error handling to prevent silent failures"""
        try:
            key_id = id(key)
            key_info = self._key_to_identifier(key)
        except Exception as e:
            print(f"❌ ERROR in _on_key_release: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Add to key sequence
        self.key_sequence.append({
            'event': 'release',
            'key_info': key_info,
            'timestamp': time.time(),
            'key_id': key_id
        })
        
        # Remove from active keys
        if key_id in self.active_keys:
            del self.active_keys[key_id]
        
        # Remove modifier (cross-platform: macOS cmd = Windows Windows key)
        if key == keyboard.Key.cmd or key == keyboard.Key.cmd_l or key == keyboard.Key.cmd_r:
            self.pressed_modifiers.discard('cmd')
        elif key == keyboard.Key.ctrl or key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            self.pressed_modifiers.discard('ctrl')
        elif key == keyboard.Key.alt or key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            self.pressed_modifiers.discard('alt')
        elif key == keyboard.Key.shift or key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
            self.pressed_modifiers.discard('shift')
            # Notify mouse tracker of Shift release
            if self.shift_state_callback:
                self.shift_state_callback(False, time.time())
    
    def _record_hotkey(self, char_or_key, current_time, modifiers):
        """Record a hotkey action - captures all active keys in the combination"""
        # Use a longer timeout to capture keys pressed simultaneously
        combination_start = current_time - self.key_combination_timeout
        recent_keys = [e for e in self.key_sequence if e['timestamp'] >= combination_start and e['event'] == 'press']
        key_sequence_data = [e['key_info'] for e in recent_keys]
        
        # Build keys list from modifiers, ensuring proper order
        # Standard order: cmd/ctrl, alt, shift, then the key
        ordered_modifiers = []
        if 'cmd' in modifiers:
            ordered_modifiers.append('cmd')
        elif 'ctrl' in modifiers:
            ordered_modifiers.append('ctrl')
        if 'alt' in modifiers:
            ordered_modifiers.append('alt')
        if 'shift' in modifiers:
            ordered_modifiers.append('shift')
        
        # Add any remaining modifiers not in the standard list
        for mod in sorted(modifiers):
            if mod not in ordered_modifiers:
                ordered_modifiers.append(mod)
        
        # Add the final key
        final_key = char_or_key.lower() if isinstance(char_or_key, str) and len(char_or_key) == 1 else char_or_key
        keys = ordered_modifiers + [final_key]
        
        # Detect copy/paste/cut
        char_lower = char_or_key.lower() if isinstance(char_or_key, str) and len(char_or_key) == 1 else char_or_key
        is_copy = (char_lower == 'c' and ('cmd' in keys or 'ctrl' in keys))
        is_paste = (char_lower == 'v' and ('cmd' in keys or 'ctrl' in keys))
        is_cut = (char_lower == 'x' and ('cmd' in keys or 'ctrl' in keys))
        
        action = {
            "type": "hotkey",
            "keys": keys,
            "key_sequence": key_sequence_data,
            "timestamp": current_time,
            "timestamp_iso": datetime.now().isoformat(),
        }
        
        if is_copy:
            action['operation'] = 'copy'
        elif is_paste:
            action['operation'] = 'paste'
        elif is_cut:
            action['operation'] = 'cut'
        
        # Add app context
        app_context = self._get_app_context()
        if app_context:
            action['app_name'] = app_context.get('name')
            action['app_bundle_id'] = app_context.get('bundle_id')
        
        self.actions.append(action)
        self.pending_hotkey = None
        # Don't clear the key sequence too aggressively - keep recent keys for potential multi-key combinations
        self.key_sequence = [e for e in self.key_sequence if e['timestamp'] >= combination_start - 0.5]
        
        print(f"⌨️  Hotkey recorded: {'+'.join(keys)} ({len(keys)} keys)")
    
    def _flush_typed_text(self):
        """Flush accumulated text as a type action"""
        if not self.typed_text:
            self.last_text_flush_time = time.time()
            return
        
        text = ''.join(self.typed_text)
        if not text:
            self.typed_text = []
            self.last_text_flush_time = time.time()
            self.last_char_time = None
            return
        
        action = {
            "type": "type",
            "text": text,
            "timestamp": time.time(),
            "timestamp_iso": datetime.now().isoformat(),
        }
        
        # Add app context
        app_context = self._get_app_context()
        if app_context:
            action['app_name'] = app_context.get('name')
            action['app_bundle_id'] = app_context.get('bundle_id')
            
            app_name = app_context.get('name', '').lower()
            if any(spreadsheet in app_name for spreadsheet in self.spreadsheet_apps):
                action['spreadsheet_context'] = {
                    'is_spreadsheet': True,
                    'app_name': app_context.get('name'),
                    'note': 'Cell position requires OCR analysis'
                }
        
        self.actions.append(action)
        self.last_typed_action_index = len(self.actions) - 1
        
        print(f"📝 ✅ Flushed text: '{text[:50]}...' ({len(text)} chars)")
        
        self.typed_text = []
        current_time = time.time()
        self.last_text_flush_time = current_time
        self.last_char_time = None
    
    def get_actions(self):
        """Get current list of keyboard actions"""
        return self.actions.copy()
    
    def _get_app_context(self):
        """Get current app context from app_tracker"""
        if self.app_tracker:
            try:
                return self.app_tracker.get_current_app()
            except:
                pass
        return None
    
    def _key_to_identifier(self, key):
        """Convert key to identifier (cross-platform compatible)"""
        try:
            if hasattr(key, 'char') and key.char is not None:
                return {'type': 'char', 'value': key.char}
            
            # Cross-platform key mapping
            # On macOS: cmd = Command key, on Windows: cmd = Windows key
            # Both are tracked as 'cmd' for consistency
            key_map = {
                keyboard.Key.cmd: 'cmd',
                keyboard.Key.cmd_l: 'cmd',
                keyboard.Key.cmd_r: 'cmd',
                keyboard.Key.ctrl: 'ctrl',
                keyboard.Key.ctrl_l: 'ctrl',
                keyboard.Key.ctrl_r: 'ctrl',
                keyboard.Key.alt: 'alt',
                keyboard.Key.alt_l: 'alt',
                keyboard.Key.alt_r: 'alt',
                keyboard.Key.shift: 'shift',
                keyboard.Key.shift_l: 'shift',
                keyboard.Key.shift_r: 'shift',
                keyboard.Key.enter: 'enter',
                keyboard.Key.tab: 'tab',
                keyboard.Key.space: 'space',
                keyboard.Key.backspace: 'backspace',
                keyboard.Key.delete: 'delete',
                keyboard.Key.esc: 'escape',
            }
            
            if key in key_map:
                return {'type': 'key', 'value': key_map[key]}
            
            return {'type': 'unknown', 'value': str(key)}
        except:
            return {'type': 'unknown', 'value': str(key)}

