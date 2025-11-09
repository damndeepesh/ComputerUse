#!/usr/bin/env python3
"""
Test the local AI model
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from models.model_manager import get_model_manager


def test_model():
    print("="*60)
    print("TESTING LOCAL AI MODEL")
    print("="*60)
    print()
    
    # Get model manager
    manager = get_model_manager()
    
    # Show model info
    print("Model Information:")
    info = manager.get_model_info()
    for key, value in info.items():
        print(f"  {key}: {value}")
    print()
    
    # Load model
    if not info["is_downloaded"]:
        print("❌ Model not downloaded yet!")
        print("Run: python download_models.py")
        return
    
    print("Loading model...")
    success = manager.load_model()
    
    if not success:
        print("❌ Failed to load model")
        return
    
    print("✅ Model loaded successfully!")
    print()
    
    # Test generation
    print("Testing text generation...")
    print("-" * 60)
    
    prompts = [
        "Generate a workflow name for: opening a text editor and typing hello world",
        "Describe this action: clicking at coordinates (500, 300)",
        "What is the capital of France?",
    ]
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\nTest {i}:")
        print(f"Prompt: {prompt}")
        print(f"Response: ", end="")
        
        response = manager.generate(prompt, max_length=100)
        print(response)
        print("-" * 60)
    
    print("\n✨ All tests completed!")
    
    # Cleanup
    manager.unload_model()
    print("Model unloaded from memory")


if __name__ == "__main__":
    test_model()

