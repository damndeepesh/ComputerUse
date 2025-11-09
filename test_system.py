#!/usr/bin/env python3
"""
System test script - Verify all components are working
"""
import sys
import subprocess
import importlib.util

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print("✅ Python version:", f"{version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print("❌ Python 3.9+ required. You have:", f"{version.major}.{version.minor}.{version.micro}")
        return False

def check_package(package_name, import_name=None):
    """Check if a Python package is installed"""
    if import_name is None:
        import_name = package_name
    
    spec = importlib.util.find_spec(import_name)
    if spec is not None:
        print(f"✅ {package_name} is installed")
        return True
    else:
        print(f"❌ {package_name} is NOT installed")
        return False

def check_ollama():
    """Check if Ollama is running"""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.ok:
            models = response.json().get("models", [])
            has_phi3 = any("phi3" in m.get("name", "") for m in models)
            if has_phi3:
                print("✅ Ollama is running with Phi-3 model")
                return True
            else:
                print("⚠️  Ollama is running but Phi-3 model not found")
                print("   Run: ollama pull phi3")
                return False
        else:
            print("❌ Ollama is not responding")
            return False
    except Exception as e:
        print("❌ Ollama is not running")
        print("   Run: ollama serve")
        return False

def check_node():
    """Check if Node.js is installed"""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ Node.js is installed: {version}")
            return True
        else:
            print("❌ Node.js is not installed")
            return False
    except Exception:
        print("❌ Node.js is not installed")
        return False

def check_npm_packages():
    """Check if npm packages are installed"""
    try:
        import os
        if os.path.exists("node_modules"):
            print("✅ npm packages are installed")
            return True
        else:
            print("❌ npm packages are NOT installed")
            print("   Run: npm install")
            return False
    except Exception:
        print("❌ Could not check npm packages")
        return False

def main():
    """Run all system checks"""
    print("="*60)
    print("AGI ASSISTANT - SYSTEM CHECK")
    print("="*60)
    print()
    
    checks = []
    
    # Python checks
    print("🐍 Python Environment:")
    checks.append(check_python_version())
    
    print("\n📦 Python Packages:")
    required_packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("sqlalchemy", "sqlalchemy"),
        ("pillow", "PIL"),
        ("opencv-python", "cv2"),
        ("pyautogui", "pyautogui"),
        ("mss", "mss"),
        ("pynput", "pynput"),
        ("requests", "requests"),
    ]
    
    for package_name, import_name in required_packages:
        checks.append(check_package(package_name, import_name))
    
    # Ollama check
    print("\n🤖 AI Model:")
    checks.append(check_ollama())
    
    # Node.js checks
    print("\n📱 Frontend Environment:")
    checks.append(check_node())
    checks.append(check_npm_packages())
    
    # Summary
    print("\n" + "="*60)
    passed = sum(checks)
    total = len(checks)
    
    if passed == total:
        print(f"✨ ALL CHECKS PASSED ({passed}/{total})")
        print("\nYou're ready to run the AGI Assistant!")
        print("\nNext steps:")
        print("  1. Start Ollama: ollama serve")
        print("  2. Start backend: python backend/main.py")
        print("  3. Start frontend: npm run dev")
        print("\nOr use the startup script: ./start.sh")
    else:
        print(f"⚠️  SOME CHECKS FAILED ({passed}/{total} passed)")
        print("\nPlease fix the issues above before running the application.")
        print("See SETUP_GUIDE.md for detailed instructions.")
    
    print("="*60)
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


