#!/usr/bin/env python
"""Test script to verify backend imports"""
import sys
sys.path.insert(0, '.')

try:
    from backend.main import app
    print("✓ Backend imports successfully")
    print(f"✓ FastAPI app created: {app.title}")
    print(f"✓ Routes configured: {len(app.routes)} routes")
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
