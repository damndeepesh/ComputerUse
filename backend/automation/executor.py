import pyautogui
import time
import platform
from automation.element_finder import get_element_finder


class WorkflowExecutor:
    def __init__(self):
        # Set up PyAutoGUI safety features
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort
        pyautogui.PAUSE = 0.5  # Pause between actions
        
        # Get screen size
        self.screen_width, self.screen_height = pyautogui.size()
        
        # Element finder for visual detection
        self.element_finder = get_element_finder()
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds between retries
        
    def execute_step(self, step, retry_count=0, continue_on_error=False):
        """
        Execute a single workflow step with retry logic
        
        Args:
            step: Step dictionary to execute
            retry_count: Current retry attempt (internal use)
            continue_on_error: If True, don't raise on error, just log it
        """
        action = step.get("action", "").lower()
        
        print(f"🎯 Executing: {action} - {step.get('description', 'No description')}")
        
        try:
            if action == "click":
                # Check if we should find by text or use coordinates
                if step.get("find_by_text"):
                    self._execute_click_text(step)
                else:
                    self._execute_click(step)
                time.sleep(0.3)  # Brief pause after click
            elif action == "type":
                self._execute_type(step)
                time.sleep(0.2)  # Brief pause after typing
            elif action == "wait":
                self._execute_wait(step)
            elif action == "wait_for_text":
                self._execute_wait_for_text(step)
            elif action == "wait_for_text_disappear":
                self._execute_wait_for_text_disappear(step)
            elif action == "hotkey":
                self._execute_hotkey(step)
                time.sleep(0.3)  # Brief pause after hotkey
            elif action == "scroll":
                self._execute_scroll(step)
                time.sleep(0.2)  # Brief pause after scroll
            elif action == "screenshot":
                # Screenshot steps are now converted to "wait" actions
                # But handle legacy screenshot steps
                duration = step.get("duration", 0.5)
                time.sleep(duration)
            else:
                # Default: just wait a bit
                print(f"⚠️  Unknown action type: {action}")
                time.sleep(0.3)
            
            # Return success
            return True
                
        except pyautogui.FailSafeException:
            print("🛑 FAILSAFE TRIGGERED: Mouse moved to corner")
            if not continue_on_error:
                raise
        except Exception as e:
            error_msg = f"❌ Error executing step: {e}"
            print(error_msg)
            
            # Retry logic
            if retry_count < self.max_retries:
                print(f"   🔄 Retrying ({retry_count + 1}/{self.max_retries}) after {self.retry_delay}s...")
                time.sleep(self.retry_delay)
                return self.execute_step(step, retry_count=retry_count + 1, continue_on_error=continue_on_error)
            else:
                if continue_on_error:
                    print(f"   ⚠️  Max retries reached, continuing with next step...")
                    import traceback
                    traceback.print_exc()
                    return False  # Step failed but continue
                else:
                    import traceback
                    traceback.print_exc()
                    raise
    
    def _execute_click(self, step):
        """Execute a mouse click - supports left, right, and middle clicks"""
        x = step.get("x")
        y = step.get("y")
        button = step.get("button", "left")
        clicks = step.get("clicks", 1)
        
        if x is not None and y is not None:
            # Ensure coordinates are within screen bounds
            x = int(max(0, min(x, self.screen_width - 1)))
            y = int(max(0, min(y, self.screen_height - 1)))
            
            print(f"   🖱️  Moving to ({x}, {y})...")
            # Move to position
            pyautogui.moveTo(x, y, duration=0.8)
            
            # Brief pause before clicking
            time.sleep(0.2)
            
            # Normalize button name
            button_normalized = button.lower()
            if 'right' in button_normalized:
                button_normalized = 'right'
            elif 'middle' in button_normalized:
                button_normalized = 'middle'
            else:
                button_normalized = 'left'  # Default to left
            
            # Click
            print(f"   👆 Clicking {button_normalized} button...")
            if clicks == 2:
                pyautogui.doubleClick(button=button_normalized)
            else:
                pyautogui.click(button=button_normalized)
            
            print(f"   ✅ Clicked at ({x}, {y})")
        else:
            print("   ⚠️  Warning: Click coordinates not provided")
    
    def _execute_click_text(self, step):
        """Execute click by finding text on screen using OCR"""
        search_text = step.get("find_by_text") or step.get("text")
        button = step.get("button", "left")
        timeout = step.get("timeout", 5)
        retries = step.get("retries", 3)
        
        if not search_text:
            print("   ⚠️  Warning: No text specified for find_by_text")
            return
        
        print(f"   🔍 Finding and clicking text: '{search_text}'...")
        result = self.element_finder.click_text(
            search_text=search_text,
            button=button,
            timeout=timeout,
            retries=retries
        )
        
        if result['success']:
            print(f"   ✅ Successfully clicked '{search_text}'")
        else:
            raise Exception(f"Could not find text '{search_text}' on screen after {retries} attempts")
    
    def _execute_wait_for_text(self, step):
        """Wait for text to appear on screen"""
        search_text = step.get("text") or step.get("wait_for_text")
        timeout = step.get("timeout", 10)
        check_interval = step.get("check_interval", 0.5)
        
        if not search_text:
            print("   ⚠️  Warning: No text specified for wait_for_text")
            return
        
        print(f"   ⏳ Waiting for text '{search_text}' to appear (timeout: {timeout}s)...")
        result = self.element_finder.wait_for_text(
            search_text=search_text,
            timeout=timeout,
            check_interval=check_interval
        )
        
        if result['found']:
            print(f"   ✅ Text '{search_text}' appeared!")
        else:
            raise Exception(f"Text '{search_text}' did not appear within {timeout} seconds")
    
    def _execute_wait_for_text_disappear(self, step):
        """Wait for text to disappear from screen"""
        search_text = step.get("text") or step.get("wait_for_text_disappear")
        timeout = step.get("timeout", 10)
        check_interval = step.get("check_interval", 0.5)
        
        if not search_text:
            print("   ⚠️  Warning: No text specified for wait_for_text_disappear")
            return
        
        print(f"   ⏳ Waiting for text '{search_text}' to disappear (timeout: {timeout}s)...")
        disappeared = self.element_finder.wait_for_text_disappear(
            search_text=search_text,
            timeout=timeout,
            check_interval=check_interval
        )
        
        if disappeared:
            print(f"   ✅ Text '{search_text}' disappeared!")
        else:
            raise Exception(f"Text '{search_text}' did not disappear within {timeout} seconds")
    
    def _execute_type(self, step):
        """Execute keyboard typing"""
        text = step.get("text", "")
        interval = step.get("interval", 0.08)
        
        if text:
            print(f"   ⌨️  Typing: '{text}'...")
            pyautogui.write(text, interval=interval)
            print(f"   ✅ Typed: '{text}'")
        else:
            print("   ⚠️  Warning: No text to type")
    
    def _execute_wait(self, step):
        """Wait for specified duration"""
        duration = step.get("duration", 1.0)
        time.sleep(duration)
        print(f"Waited {duration} seconds")
    
    def _execute_hotkey(self, step):
        """Execute keyboard hotkey combination"""
        keys = step.get("keys", [])
        
        if keys:
            # Convert to list if string
            if isinstance(keys, str):
                keys = keys.split("+")
            
            pyautogui.hotkey(*keys)
            print(f"Pressed hotkey: {'+'.join(keys)}")
        else:
            print("Warning: No keys specified for hotkey")
    
    def _execute_scroll(self, step):
        """Execute mouse scroll"""
        amount = step.get("amount", 0)
        dy = step.get("dy", 0)
        x = step.get("x")
        y = step.get("y")
        
        # Convert dy to scroll amount if amount not provided
        if amount == 0 and dy != 0:
            amount = int(dy * 100)
        
        if x is not None and y is not None:
            print(f"   🖱️  Moving to ({x}, {y}) for scroll...")
            pyautogui.moveTo(x, y, duration=0.3)
        
        print(f"   🔄 Scrolling {amount} units...")
        pyautogui.scroll(amount)
        print(f"   ✅ Scrolled {amount} units")
    
    def get_current_mouse_position(self):
        """Get current mouse position"""
        return pyautogui.position()
    
    def take_screenshot(self, filename=None):
        """Take a screenshot"""
        screenshot = pyautogui.screenshot()
        if filename:
            screenshot.save(filename)
        return screenshot

