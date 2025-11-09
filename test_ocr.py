#!/usr/bin/env python3
"""
Test OCR functionality
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from processing.ocr_engine import test_ocr

if __name__ == "__main__":
    test_ocr()

