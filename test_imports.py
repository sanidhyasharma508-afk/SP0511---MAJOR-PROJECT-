#!/usr/bin/env python
"""Test script to verify backend imports"""
import sys
sys.path.insert(0, '.')

try:
    from backend.main import app
    print("[OK] Backend imports successfully")
    print(f"[OK] FastAPI app created: {app.title}")
    print(f"[OK] Routes configured: {len(app.routes)} routes")
except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    import traceback
    traceback.print_exc()
