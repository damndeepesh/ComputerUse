#!/usr/bin/env python3
"""
Download AI models locally - No Ollama required!
Run this script to download Phi-2 model from Hugging Face
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from models.model_manager import download_models_cli

if __name__ == "__main__":
    download_models_cli()

