"""
OCR Engine - Extract text from screenshots
Supports both EasyOCR and Tesseract
"""
import os
from pathlib import Path
from PIL import Image
import numpy as np


class OCREngine:
    """Extract text from images using OCR"""
    
    def __init__(self, engine="easyocr"):
        """
        Initialize OCR engine
        
        Args:
            engine: "easyocr" (default, more accurate) or "tesseract" (faster)
        """
        self.engine = engine
        self.reader = None
        self.models_dir = Path("models/ocr")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🔍 OCR Engine initialized: {engine}")
    
    def load(self):
        """Load OCR models"""
        if self.reader is not None:
            return True
        
        try:
            if self.engine == "easyocr":
                import easyocr
                print("📥 Loading EasyOCR models...")
                self.reader = easyocr.Reader(
                    ['en'],  # English only for now
                    gpu=False,  # Use CPU (set True if GPU available)
                    model_storage_directory=str(self.models_dir),
                    download_enabled=True
                )
                print("✅ EasyOCR loaded successfully!")
                
            elif self.engine == "tesseract":
                import pytesseract
                # Check if tesseract is installed
                try:
                    pytesseract.get_tesseract_version()
                    self.reader = pytesseract
                    print("✅ Tesseract loaded successfully!")
                except Exception as e:
                    print(f"❌ Tesseract not found. Install with: brew install tesseract (macOS)")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading OCR engine: {e}")
            return False
    
    def extract_text(self, image_path, detail_level=1):
        """
        Extract text from an image
        
        Args:
            image_path: Path to image file
            detail_level: 0=simple, 1=detailed (with coordinates)
            
        Returns:
            dict with 'text' and optionally 'regions' with bounding boxes
        """
        if not self.reader:
            if not self.load():
                return {"text": "", "regions": []}
        
        try:
            if self.engine == "easyocr":
                return self._extract_easyocr(image_path, detail_level)
            elif self.engine == "tesseract":
                return self._extract_tesseract(image_path, detail_level)
        except Exception as e:
            print(f"Error extracting text: {e}")
            return {"text": "", "regions": []}
    
    def _extract_easyocr(self, image_path, detail_level):
        """Extract text using EasyOCR"""
        # Read image
        results = self.reader.readtext(str(image_path))
        
        # Extract text
        all_text = []
        regions = []
        
        for (bbox, text, confidence) in results:
            all_text.append(text)
            
            if detail_level > 0:
                # Get bounding box coordinates
                x_min = int(min([p[0] for p in bbox]))
                y_min = int(min([p[1] for p in bbox]))
                x_max = int(max([p[0] for p in bbox]))
                y_max = int(max([p[1] for p in bbox]))
                
                regions.append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": {
                        "x": x_min,
                        "y": y_min,
                        "width": x_max - x_min,
                        "height": y_max - y_min
                    }
                })
        
        return {
            "text": " ".join(all_text),
            "regions": regions if detail_level > 0 else []
        }
    
    def _extract_tesseract(self, image_path, detail_level):
        """Extract text using Tesseract"""
        import pytesseract
        from pytesseract import Output
        
        # Open image
        img = Image.open(image_path)
        
        if detail_level > 0:
            # Get detailed data with bounding boxes
            data = pytesseract.image_to_data(img, output_type=Output.DICT)
            
            all_text = []
            regions = []
            
            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                if text:
                    all_text.append(text)
                    
                    regions.append({
                        "text": text,
                        "confidence": data['conf'][i],
                        "bbox": {
                            "x": data['left'][i],
                            "y": data['top'][i],
                            "width": data['width'][i],
                            "height": data['height'][i]
                        }
                    })
            
            return {
                "text": " ".join(all_text),
                "regions": regions
            }
        else:
            # Simple text extraction
            text = pytesseract.image_to_string(img)
            return {
                "text": text.strip(),
                "regions": []
            }
    
    def extract_from_region(self, image_path, x, y, width, height):
        """
        Extract text from a specific region of an image
        
        Args:
            image_path: Path to image
            x, y, width, height: Region coordinates
        """
        try:
            img = Image.open(image_path)
            
            # Crop to region
            region = img.crop((x, y, x + width, y + height))
            
            # Save temporary cropped image
            temp_path = "temp_region.png"
            region.save(temp_path)
            
            # Extract text
            result = self.extract_text(temp_path, detail_level=0)
            
            # Cleanup
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            return result
            
        except Exception as e:
            print(f"Error extracting text from region: {e}")
            return {"text": "", "regions": []}
    
    def find_text_location(self, image_path, search_text):
        """
        Find the location of specific text in an image
        
        Args:
            image_path: Path to image
            search_text: Text to search for
            
        Returns:
            List of bounding boxes where text was found
        """
        result = self.extract_text(image_path, detail_level=1)
        
        matches = []
        search_lower = (search_text or "").strip().lower()
        if not search_lower:
            return []
        
        # Tokenize search to allow partial but prioritize full phrase
        search_tokens = [t for t in search_lower.split() if t]
        
        for region in result.get("regions", []):
            region_text = (region.get("text", "") or "").strip()
            region_lower = region_text.lower()
            if not region_text:
                continue
            
            full_phrase_match = search_lower in region_lower
            token_hits = sum(1 for t in search_tokens if t and t in region_lower)
            if full_phrase_match or token_hits > 0:
                bbox = region.get("bbox", {})
                area = max(1, int(bbox.get("width", 0)) * int(bbox.get("height", 0)))
                confidence = float(region.get("confidence", 0) or 0)
                matches.append({
                    **region,
                    "_score": (
                        (2 if full_phrase_match else 1) * 1000
                        + token_hits * 100
                        + int(confidence * 10)
                        + min(area // 1000, 100)  # slight bias toward larger readable text
                    )
                })
        
        # Sort best-first: score desc, confidence desc, area desc
        matches.sort(key=lambda r: (
            r.get("_score", 0),
            float(r.get("confidence", 0) or 0),
            (r.get("bbox", {}).get("width", 0) * r.get("bbox", {}).get("height", 0))
        ), reverse=True)
        
        return matches
    
    def unload(self):
        """Unload OCR models from memory"""
        self.reader = None
        print("OCR models unloaded")


# Global instance
_ocr_engine = None


def get_ocr_engine(engine="easyocr"):
    """Get the global OCR engine instance"""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine(engine=engine)
    return _ocr_engine


def test_ocr():
    """Test OCR on a sample image"""
    print("="*60)
    print("OCR ENGINE TEST")
    print("="*60)
    print()
    
    # Create a test image with text
    from PIL import Image, ImageDraw, ImageFont
    
    print("Creating test image...")
    img = Image.new('RGB', (400, 100), color='white')
    d = ImageDraw.Draw(img)
    
    # Use default font
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 30)
    except:
        font = ImageFont.load_default()
    
    d.text((10, 30), "Hello, AGI Assistant!", fill='black', font=font)
    
    test_path = "test_ocr.png"
    img.save(test_path)
    print(f"✅ Test image created: {test_path}")
    print()
    
    # Test OCR
    ocr = get_ocr_engine()
    print("Testing OCR...")
    result = ocr.extract_text(test_path, detail_level=1)
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"\nExtracted Text: '{result['text']}'")
    print(f"\nNumber of regions: {len(result['regions'])}")
    
    for i, region in enumerate(result['regions'], 1):
        print(f"\nRegion {i}:")
        print(f"  Text: '{region['text']}'")
        print(f"  Confidence: {region['confidence']:.2f}")
        print(f"  Position: ({region['bbox']['x']}, {region['bbox']['y']})")
    
    # Cleanup
    if os.path.exists(test_path):
        os.remove(test_path)
    
    print("\n✨ OCR test completed!")


if __name__ == "__main__":
    test_ocr()

