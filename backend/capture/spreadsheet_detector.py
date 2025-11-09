"""
Spreadsheet Cell Detector - Detects cell positions in Excel/Numbers using OCR
"""

import time
from pathlib import Path
from PIL import Image
import mss
import numpy as np


class SpreadsheetDetector:
    """Detect spreadsheet cell positions using OCR"""
    
    def __init__(self, ocr_engine=None):
        self.ocr_engine = ocr_engine
        self.cell_cache = {}  # Cache detected cell positions
        
    def detect_cell_from_screenshot(self, x, y, screenshot_path=None, app_name=None):
        """
        Detect cell position from screenshot using OCR
        
        Args:
            x, y: Click coordinates
            screenshot_path: Path to screenshot (if None, will capture)
            app_name: Name of spreadsheet app (Excel, Numbers, etc.)
            
        Returns:
            dict with cell info: {'row': 1, 'column': 'A', 'cell': 'A1'} or None
        """
        try:
            # Take a screenshot around the click position if needed
            if not screenshot_path:
                screenshot_path = self._capture_region_around_click(x, y)
                if not screenshot_path:
                    return None
            
            # Use OCR to extract text and find cell references
            if not self.ocr_engine:
                from processing.ocr_engine import get_ocr_engine
                self.ocr_engine = get_ocr_engine()
            
            if not self.ocr_engine.load():
                return None
            
            # Extract text with bounding boxes
            ocr_result = self.ocr_engine.extract_text(screenshot_path, detail_level=1)
            
            if not ocr_result or 'regions' not in ocr_result:
                return None
            
            # Detect column headers (A, B, C, etc.) and row numbers (1, 2, 3, etc.)
            column_headers = []
            row_numbers = []
            
            for region in ocr_result.get('regions', []):
                text = region.get('text', '').strip()
                bbox = region.get('bbox', {})
                
                # Check if it's a column header (A-Z, AA-ZZ, etc.)
                if self._is_column_header(text):
                    column_headers.append({
                        'text': text,
                        'x': bbox.get('x', 0),
                        'y': bbox.get('y', 0),
                        'width': bbox.get('width', 0),
                        'height': bbox.get('height', 0)
                    })
                
                # Check if it's a row number (1, 2, 3, etc.)
                elif self._is_row_number(text):
                    row_numbers.append({
                        'text': text,
                        'x': bbox.get('x', 0),
                        'y': bbox.get('y', 0),
                        'width': bbox.get('width', 0),
                        'height': bbox.get('height', 0)
                    })
            
            # Calculate which cell was clicked
            if column_headers and row_numbers:
                cell_info = self._calculate_cell_position(x, y, column_headers, row_numbers, screenshot_path)
                return cell_info
            
            return None
            
        except Exception as e:
            print(f"⚠️  Error detecting spreadsheet cell: {e}")
            return None
    
    def _is_column_header(self, text):
        """Check if text is a column header (A, B, C, AA, AB, etc.)"""
        if not text:
            return False
        
        # Remove whitespace and check if it's a valid column identifier
        text = text.strip().upper()
        
        # Single letter (A-Z)
        if len(text) == 1 and text.isalpha():
            return True
        
        # Multiple letters (AA-ZZ, etc.)
        if len(text) > 1 and text.isalpha():
            return True
        
        return False
    
    def _is_row_number(self, text):
        """Check if text is a row number (1, 2, 3, etc.)"""
        if not text:
            return False
        
        text = text.strip()
        
        # Check if it's a numeric string
        try:
            num = int(text)
            # Row numbers are typically 1-10000+
            if 1 <= num <= 100000:
                return True
        except:
            pass
        
        return False
    
    def _calculate_cell_position(self, x, y, column_headers, row_numbers, screenshot_path):
        """
        Calculate which cell was clicked based on column headers and row numbers
        
        Args:
            x, y: Click coordinates (in screen coordinates)
            column_headers: List of detected column headers
            row_numbers: List of detected row numbers
            screenshot_path: Path to screenshot
            
        Returns:
            dict with cell info
        """
        try:
            # Load screenshot to get dimensions
            img = Image.open(screenshot_path)
            img_width, img_height = img.size
            
            # Sort column headers by x position
            column_headers.sort(key=lambda h: h['x'])
            
            # Sort row numbers by y position
            row_numbers.sort(key=lambda r: r['y'])
            
            # Find which column header is closest to x
            column = None
            column_index = None
            
            for i, header in enumerate(column_headers):
                header_x = header['x'] + header['width'] / 2
                if x < header_x or i == len(column_headers) - 1:
                    # This is the column
                    column = header['text'].upper()
                    column_index = i
                    break
            
            # Find which row number is closest to y
            row = None
            row_index = None
            
            for i, row_num in enumerate(row_numbers):
                row_y = row_num['y'] + row_num['height'] / 2
                if y < row_y or i == len(row_numbers) - 1:
                    # This is the row
                    try:
                        row = int(row_num['text'].strip())
                        row_index = i
                    except:
                        pass
                    break
            
            if column and row:
                return {
                    'cell': f"{column}{row}",
                    'column': column,
                    'row': row,
                    'column_index': column_index,
                    'row_index': row_index,
                    'detected': True
                }
            
            return None
            
        except Exception as e:
            print(f"⚠️  Error calculating cell position: {e}")
            return None
    
    def _capture_region_around_click(self, x, y, width=800, height=600):
        """
        Capture a region around the click position for OCR analysis
        
        Args:
            x, y: Click coordinates
            width: Width of region to capture
            height: Height of region to capture
            
        Returns:
            Path to saved screenshot or None
        """
        try:
            # Calculate region bounds
            left = max(0, x - width // 2)
            top = max(0, y - height // 2)
            
            # Capture screenshot
            with mss.mss() as sct:
                monitor = {
                    "top": int(top),
                    "left": int(left),
                    "width": width,
                    "height": height
                }
                
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                
                # Save to temp file in project root data directory
                PROJECT_ROOT = Path(__file__).parent.parent.parent
                temp_dir = PROJECT_ROOT / "data" / "temp_screenshots"
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                screenshot_path = temp_dir / f"cell_detect_{int(time.time() * 1000)}.png"
                img.save(screenshot_path)
                
                return str(screenshot_path)
                
        except Exception as e:
            print(f"⚠️  Error capturing region for cell detection: {e}")
            return None


def get_spreadsheet_detector(ocr_engine=None):
    """Get or create spreadsheet detector instance"""
    return SpreadsheetDetector(ocr_engine=ocr_engine)

