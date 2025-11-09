"""
Element Finder - Find UI elements using OCR and image matching
"""
import pyautogui
import time
from pathlib import Path
from PIL import Image
import tempfile
from processing.ocr_engine import get_ocr_engine


class ElementFinder:
    """Find UI elements on screen using OCR and visual matching"""
    
    def __init__(self):
        self.ocr_engine = None
        self.screen_width, self.screen_height = pyautogui.size()
    
    def _get_ocr_engine(self):
        """Lazy load OCR engine"""
        if self.ocr_engine is None:
            self.ocr_engine = get_ocr_engine()
            self.ocr_engine.load()
        return self.ocr_engine
    
    def take_screenshot(self):
        """Take a screenshot and return path"""
        screenshot = pyautogui.screenshot()
        temp_path = Path(tempfile.gettempdir()) / f"screenshot_{int(time.time() * 1000)}.png"
        screenshot.save(str(temp_path))
        return str(temp_path)
    
    def find_text(self, search_text, timeout=5, screenshot_path=None):
        """
        Find text on screen using OCR
        
        Args:
            search_text: Text to search for
            timeout: Maximum time to wait (seconds)
            screenshot_path: Optional path to existing screenshot
            
        Returns:
            dict with 'found': bool, 'bbox': dict with x, y, width, height, 'center': (x, y)
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Take screenshot if not provided
                if screenshot_path is None or not Path(screenshot_path).exists():
                    screenshot_path = self.take_screenshot()
                
                # Use OCR to find text
                ocr = self._get_ocr_engine()
                matches = ocr.find_text_location(screenshot_path, search_text)
                
                if matches:
                    # Choose the best match (already sorted by OCR for relevance)
                    match = matches[0]
                    bbox = match['bbox']
                    center_x = bbox['x'] + (bbox['width'] // 2)
                    center_y = bbox['y'] + (bbox['height'] // 2)
                    
                    # Cleanup temp screenshot
                    if screenshot_path.startswith(tempfile.gettempdir()):
                        try:
                            Path(screenshot_path).unlink()
                        except:
                            pass
                    
                    return {
                        'found': True,
                        'bbox': bbox,
                        'center': (center_x, center_y),
                        'text': match['text'],
                        'confidence': match.get('confidence', 1.0)
                    }
                
                # Cleanup temp screenshot
                if screenshot_path.startswith(tempfile.gettempdir()):
                    try:
                        Path(screenshot_path).unlink()
                    except:
                        pass
                
                # If not found and timeout not reached, wait a bit and retry
                if time.time() - start_time < timeout - 0.5:
                    time.sleep(0.5)
                    screenshot_path = None  # Take new screenshot
                
            except Exception as e:
                print(f"Error finding text '{search_text}': {e}")
                break
        
        return {
            'found': False,
            'bbox': None,
            'center': None,
            'text': None,
            'confidence': 0.0
        }
    
    def wait_for_text(self, search_text, timeout=10, check_interval=0.5):
        """
        Wait for text to appear on screen
        
        Args:
            search_text: Text to wait for
            timeout: Maximum time to wait (seconds)
            check_interval: How often to check (seconds)
            
        Returns:
            dict with 'found': bool, 'bbox': dict, 'center': (x, y)
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self.find_text(search_text, timeout=check_interval)
            if result['found']:
                return result
            time.sleep(check_interval)
        
        return {
            'found': False,
            'bbox': None,
            'center': None,
            'text': None,
            'confidence': 0.0
        }
    
    def wait_for_text_disappear(self, search_text, timeout=10, check_interval=0.5):
        """
        Wait for text to disappear from screen
        
        Args:
            search_text: Text to wait for disappearance
            timeout: Maximum time to wait (seconds)
            check_interval: How often to check (seconds)
            
        Returns:
            bool: True if text disappeared, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self.find_text(search_text, timeout=check_interval)
            if not result['found']:
                return True  # Text disappeared
            time.sleep(check_interval)
        
        return False  # Timeout - text still visible
    
    def click_text(self, search_text, button='left', timeout=5, retries=3):
        """
        Find and click text on screen
        
        Args:
            search_text: Text to find and click
            button: Mouse button ('left', 'right', 'middle')
            timeout: Time to search for text
            retries: Number of retry attempts
            
        Returns:
            dict with 'success': bool, 'clicked_at': (x, y) or None
        """
        for attempt in range(retries):
            print(f"   🔍 Searching for text '{search_text}' (attempt {attempt + 1}/{retries})...")
            
            result = self.find_text(search_text, timeout=timeout)
            
            if result['found']:
                center_x, center_y = result['center']
                print(f"   ✅ Found '{search_text}' at ({center_x}, {center_y})")
                
                # Click at center of text
                pyautogui.moveTo(center_x, center_y, duration=0.3)
                time.sleep(0.1)
                pyautogui.click(button=button)
                
                print(f"   👆 Clicked '{search_text}' at ({center_x}, {center_y})")
                
                return {
                    'success': True,
                    'clicked_at': (center_x, center_y),
                    'text': result['text'],
                    'confidence': result['confidence']
                }
            else:
                print(f"   ⚠️  Text '{search_text}' not found (attempt {attempt + 1}/{retries})")
                if attempt < retries - 1:
                    time.sleep(0.5)  # Brief pause before retry
        
        return {
            'success': False,
            'clicked_at': None,
            'text': None,
            'confidence': 0.0
        }
    
    def find_image(self, image_path, confidence=0.8, timeout=5):
        """
        Find image on screen using template matching
        
        Args:
            image_path: Path to template image
            confidence: Minimum confidence (0-1)
            timeout: Maximum time to wait (seconds)
            
        Returns:
            dict with 'found': bool, 'center': (x, y), 'confidence': float
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                screenshot = pyautogui.screenshot()
                
                # Use pyautogui's locateOnScreen
                location = pyautogui.locateOnScreen(image_path, confidence=confidence)
                
                if location:
                    center_x = location.left + (location.width // 2)
                    center_y = location.top + (location.height // 2)
                    
                    return {
                        'found': True,
                        'center': (center_x, center_y),
                        'bbox': {
                            'x': location.left,
                            'y': location.top,
                            'width': location.width,
                            'height': location.height
                        },
                        'confidence': confidence
                    }
                
                time.sleep(0.5)
                
            except pyautogui.ImageNotFoundException:
                if time.time() - start_time < timeout - 0.5:
                    time.sleep(0.5)
                    continue
                break
            except Exception as e:
                print(f"Error finding image: {e}")
                break
        
        return {
            'found': False,
            'center': None,
            'bbox': None,
            'confidence': 0.0
        }


# Global instance
_element_finder = None


def get_element_finder():
    """Get the global element finder instance"""
    global _element_finder
    if _element_finder is None:
        _element_finder = ElementFinder()
    return _element_finder

