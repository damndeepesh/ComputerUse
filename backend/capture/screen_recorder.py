import time
import os
from datetime import datetime
from pathlib import Path
import mss
from PIL import Image
import threading


class ScreenRecorder:
    def __init__(self):
        self.is_recording = False
        self.screenshots = []
        self.recording_thread = None
        self.screenshot_interval = 1.0  # Take screenshot every 1 second (reduced from 2s to capture more screenshots)
        
        # Get project root data directory
        PROJECT_ROOT = Path(__file__).parent.parent.parent
        self.data_dir = PROJECT_ROOT / "data" / "screenshots"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def start(self):
        """Start recording screenshots"""
        if self.is_recording:
            print("⚠️  Screen recorder already recording, resetting...")
            self.is_recording = False
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=1.0)
        
        print("📸 Starting screen recording...")
        self.is_recording = True
        self.screenshots = []
        
        # Ensure directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.recording_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.recording_thread.start()
        print(f"✅ Screen recording started (is_recording={self.is_recording}, thread alive={self.recording_thread.is_alive()})")
    
    def stop(self):
        """Stop recording and return list of screenshot paths"""
        print(f"📸 Stopping screen recorder (is_recording={self.is_recording}, currently has {len(self.screenshots)} screenshots)...")
        
        if not self.is_recording:
            print(f"📸 Screen recorder was not recording, returning {len(self.screenshots)} existing screenshots")
            return self.screenshots.copy()
        
        # Mark as not recording FIRST
        self.is_recording = False
        
        # Wait for recording thread to finish (give it enough time to capture final screenshot)
        if self.recording_thread and self.recording_thread.is_alive():
            print("⏳ Waiting for screenshot thread to finish (max 3s for final screenshot)...")
            # Wait up to 3 seconds (screenshot interval is 1s, so 3s ensures we get the final capture)
            self.recording_thread.join(timeout=3.0)
            if self.recording_thread.is_alive():
                print("⚠️  Screenshot thread did not finish in time, but continuing...")
                # Force stop by setting is_recording again (in case thread is stuck)
                self.is_recording = False
            else:
                print("✅ Screenshot thread finished")
        
        final_count = len(self.screenshots)
        print(f"📸 Screen recording stopped. Captured {final_count} screenshots total")
        
        # Verify screenshots were actually saved
        if final_count > 0:
            existing_count = sum(1 for s in self.screenshots if os.path.exists(s))
            if existing_count < final_count:
                print(f"⚠️  WARNING: Only {existing_count} of {final_count} screenshot files exist on disk!")
        
        return self.screenshots.copy()
    
    def _record_loop(self):
        """Main recording loop - continues until is_recording is False"""
        print(f"📸 Screenshot loop starting (is_recording={self.is_recording})")
        screenshot_count = 0
        error_count = 0
        last_success_time = time.time()
        
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                print(f"📸 Monitor configured: {monitor}")
                
                # Capture at least one screenshot even if recording stops immediately
                capture_one_more = True
                
                while self.is_recording or capture_one_more:
                    try:
                        # Capture screenshot
                        screenshot = sct.grab(monitor)
                        
                        if screenshot is None:
                            print("❌ Screenshot capture returned None")
                            error_count += 1
                            time.sleep(0.5)
                            continue
                        
                        # Convert to PIL Image
                        img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
                        
                        # Resize to reduce file size
                        img.thumbnail((1280, 720), Image.Resampling.LANCZOS)
                        
                        # Save to file
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        filename = f"screenshot_{timestamp}.png"
                        filepath = self.data_dir / filename
                        
                        # Ensure directory exists
                        self.data_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Save image
                        img.save(filepath, optimize=True, quality=85)
                        
                        # Verify file was saved
                        if not os.path.exists(filepath):
                            print(f"❌ ERROR: Screenshot file was not saved: {filepath}")
                            error_count += 1
                            continue
                        
                        self.screenshots.append(filepath)
                        screenshot_count += 1
                        error_count = 0  # Reset error count on success
                        last_success_time = time.time()
                        
                        # Log every 5th screenshot to avoid spam, but always log first few and last one
                        if screenshot_count <= 3 or screenshot_count % 5 == 0 or not self.is_recording:
                            file_size = os.path.getsize(filepath) / 1024  # Size in KB
                            print(f"📸 Captured screenshot #{screenshot_count}: {filename} ({file_size:.1f}KB, total: {len(self.screenshots)}, is_recording={self.is_recording})")
                        
                        # If recording stopped, we've captured the final screenshot - exit
                        if not self.is_recording:
                            print(f"📸 Captured final screenshot after stop signal ({screenshot_count} total)")
                            capture_one_more = False
                            break
                        
                        # Wait for next capture
                        time.sleep(self.screenshot_interval)
                        
                    except Exception as e:
                        error_count += 1
                        print(f"❌ Error capturing screenshot #{error_count}: {e}")
                        import traceback
                        traceback.print_exc()
                        
                        # Check if recording was stopped (might be why we're getting errors)
                        if not self.is_recording:
                            print(f"📸 Recording stopped - exiting loop")
                            break
                        
                        # If too many errors, log but continue
                        if error_count > 10:
                            print(f"⚠️  Too many screenshot errors ({error_count}), but continuing...")
                            # Check if we're still supposed to be recording
                            if time.time() - last_success_time > 10:
                                print(f"⚠️  No successful screenshots for 10+ seconds, but is_recording={self.is_recording}")
                        
                        # Wait before retrying (shorter wait on error to catch up)
                        time.sleep(0.5)
        except Exception as e:
            print(f"❌ Fatal error in screenshot loop: {e}")
            import traceback
            traceback.print_exc()
            # Ensure is_recording is set to False on fatal error
            self.is_recording = False
        
        print(f"📸 Screenshot loop ended (captured {len(self.screenshots)} total screenshots, {screenshot_count} in this session, is_recording={self.is_recording})")
    
    def get_latest_screenshot(self):
        """Get the most recent screenshot path"""
        return self.screenshots[-1] if self.screenshots else None


