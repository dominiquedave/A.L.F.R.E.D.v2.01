#!/usr/bin/env python3
"""
Test script for A.L.F.R.E.D. web interface
"""

import sys
import os
import asyncio

# Add project root to Python path
sys.path.append(os.path.dirname(__file__))

def test_imports():
    """Test that all required modules can be imported"""
    print("🔍 Testing imports...")
    
    try:
        from coordinator.core.coordinator import Coordinator
        print("✅ Coordinator import: OK")
    except ImportError as e:
        print(f"❌ Coordinator import failed: {e}")
        return False
    
    try:
        from coordinator.web_interface import WebInterface
        print("✅ WebInterface import: OK")
    except ImportError as e:
        print(f"❌ WebInterface import failed: {e}")
        return False
    
    try:
        import fastapi
        import uvicorn
        import jinja2
        print("✅ FastAPI dependencies: OK")
    except ImportError as e:
        print(f"❌ FastAPI dependencies missing: {e}")
        print("💡 Run: pip install fastapi uvicorn jinja2")
        return False
    
    return True

def test_directory_structure():
    """Test that required directories exist"""
    print("\n🏗️  Testing directory structure...")
    
    required_dirs = [
        'coordinator/web/templates',
        'coordinator/web/static'
    ]
    
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✅ {dir_path}: OK")
        else:
            print(f"❌ {dir_path}: Missing")
            return False
    
    return True

def test_templates():
    """Test that required templates exist"""
    print("\n📄 Testing templates...")
    
    required_templates = [
        'coordinator/web/templates/base.html',
        'coordinator/web/templates/dashboard.html',
        'coordinator/web/templates/command.html',
        'coordinator/web/templates/result.html',
        'coordinator/web/templates/agents.html'
    ]
    
    for template_path in required_templates:
        if os.path.exists(template_path):
            print(f"✅ {os.path.basename(template_path)}: OK")
        else:
            print(f"❌ {os.path.basename(template_path)}: Missing")
            return False
    
    return True

async def test_coordinator_init():
    """Test coordinator initialization"""
    print("\n🤖 Testing coordinator initialization...")
    
    try:
        from coordinator.core.coordinator import Coordinator
        coordinator = Coordinator()
        print("✅ Coordinator initialized: OK")
        return True
    except Exception as e:
        print(f"❌ Coordinator initialization failed: {e}")
        return False

def test_static_assets():
    """Test that static assets exist"""
    print("\n🎨 Testing static assets...")
    
    static_files = [
        'coordinator/web/static/style.css',
        'coordinator/web/static/script.js'
    ]
    
    for asset_path in static_files:
        if os.path.exists(asset_path):
            print(f"✅ {os.path.basename(asset_path)}: OK")
        else:
            print(f"❌ {os.path.basename(asset_path)}: Missing")
            return False
    
    return True

async def main():
    """Run all tests"""
    print("🧪 A.L.F.R.E.D. Web Interface Tests")
    print("===================================")
    
    tests = [
        ("Imports", test_imports),
        ("Directory Structure", test_directory_structure), 
        ("Templates", test_templates),
        ("Static Assets", test_static_assets),
        ("Coordinator Init", test_coordinator_init)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Web interface is ready.")
        print("\n🚀 To start the web interface:")
        print("   python start_web.py")
        print("   OR")
        print("   python coordinator/main.py --interface web")
    else:
        print(f"⚠️  {total - passed} test(s) failed. Please fix the issues above.")
        
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)