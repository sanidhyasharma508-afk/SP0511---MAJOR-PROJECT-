#!/usr/bin/env python3
"""
Quick test script for Schedule Management API endpoints
Supports testing against a live server or in-process TestClient.
"""
import sys
import json
from datetime import datetime, timedelta

class APIClientWrapper:
    def __init__(self):
        self.use_live = False
        self.base_url = "http://localhost:8000/schedule-management"
        try:
            import requests
            r = requests.get("http://localhost:8000/health", timeout=1)
            if r.status_code == 200:
                self.use_live = True
                self.requests = requests
        except Exception:
            self.use_live = False

        if not self.use_live:
            from starlette.testclient import TestClient
            from backend.main import app
            self.client = TestClient(app)

    def get(self, path):
        if self.use_live:
            return self.requests.get(f"{self.base_url}{path}")
        else:
            return self.client.get(f"/schedule-management{path}")

    def post(self, path, json_data):
        if self.use_live:
            return self.requests.post(f"{self.base_url}{path}", json=json_data)
        else:
            return self.client.post(f"/schedule-management{path}", json=json_data)

api_client = APIClientWrapper()

def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, 'encoding', 'ascii') or 'ascii'
        print(msg.encode(enc, errors='replace').decode(enc))

def test_feedback_submission():
    """Test submitting feedback"""
    print("\n" + "="*60)
    print("Testing Feedback Submission")
    print("="*60)
    
    feedback_data = {
        "name": "Rahul Sharma",
        "roll_number": "21BCS101",
        "issue_type": "Class Timing Clash",
        "preferred_timing": "2:00 PM - 4:00 PM on Wednesdays",
        "additional_comments": "Thursday's project session clashes with mess schedule. Moving it to Wednesday would be much better."
    }
    
    try:
        response = api_client.post("/feedback", feedback_data)
        assert response.status_code == 201 or response.status_code == 200, f"Status: {response.status_code}"
        result = response.json()
        
        print("[OK] Feedback submitted successfully!")
        print(f"[INFO] Feedback ID: {result.get('message', '')}")
        print("\nWhatsApp Message Preview:")
        print("-" * 60)
        safe_print(result.get('whatsapp_message', '')[:300] + "...")
        
        return True
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

def test_get_feedback_stats():
    """Test getting feedback statistics"""
    print("\n" + "="*60)
    print("Testing Feedback Statistics")
    print("="*60)
    
    try:
        response = api_client.get("/feedback/stats/summary")
        assert response.status_code == 200, f"Status: {response.status_code}"
        stats = response.json()
        
        print("[OK] Statistics retrieved successfully!")
        print(f"[STATS] Total Feedback: {stats['total_feedback']}")
        print(f"[STATS] Pending: {stats['pending']}")
        print(f"[STATS] In Progress: {stats['in_progress']}")
        print(f"[STATS] Resolved: {stats['resolved']}")
        print(f"[STATS] Resolution Rate: {stats['resolution_rate']}%")
        
        return True
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

def test_announcement_creation():
    """Test creating an announcement"""
    print("\n" + "="*60)
    print("Testing Announcement Creation")
    print("="*60)
    
    announcement_data = {
        "title": "Lab Session Rescheduled",
        "content": "The Data Structures lab scheduled for tomorrow has been moved to Friday 2:00 PM due to faculty unavailability. Please adjust your schedules accordingly.",
        "author": "Dr. Amit Verma",
        "priority": "high",
        "target_audience": "CS 3rd Year",
        "expires_at": (datetime.now() + timedelta(days=7)).isoformat()
    }
    
    try:
        response = api_client.post("/announcements", announcement_data)
        assert response.status_code == 201 or response.status_code == 200, f"Status: {response.status_code}"
        result = response.json()
        
        print("[OK] Announcement created successfully!")
        print(f"[INFO] Title: {result['title']}")
        print(f"[INFO] Author: {result['author']}")
        print(f"[INFO] Priority: {result['priority'].upper()}")
        print(f"[INFO] Audience: {result['target_audience']}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

def test_get_announcements():
    """Test getting announcements"""
    print("\n" + "="*60)
    print("Testing Get Announcements")
    print("="*60)
    
    try:
        response = api_client.get("/announcements?active_only=true")
        assert response.status_code == 200, f"Status: {response.status_code}"
        announcements = response.json()
        
        print(f"[OK] Retrieved {len(announcements)} active announcement(s)")
        
        for idx, ann in enumerate(announcements[:3], 1):
            print(f"\n{idx}. {ann['title']}")
            print(f"   Author: {ann['author']}")
            print(f"   Priority: {ann['priority']}")
            print(f"   Created: {ann['created_at']}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

def test_all_feedback():
    """Test getting all feedback"""
    print("\n" + "="*60)
    print("Testing Get All Feedback")
    print("="*60)
    
    try:
        response = api_client.get("/feedback")
        assert response.status_code == 200, f"Status: {response.status_code}"
        feedbacks = response.json()
        
        print(f"[OK] Retrieved {len(feedbacks)} feedback submission(s)")
        
        for idx, fb in enumerate(feedbacks[:3], 1):
            print(f"\n{idx}. {fb['issue_type']}")
            print(f"   By: {fb['name']} ({fb['roll_number']})")
            print(f"   Status: {fb['status'].upper()}")
            print(f"   Submitted: {fb['created_at']}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

def main():
    """Run all tests"""
    mode = "Live Server" if api_client.use_live else "In-Process TestClient"
    print(f"\n[START] Starting Schedule Management API Tests ({mode})")
    print("=" * 60)
    
    tests = [
        ("Feedback Submission", test_feedback_submission),
        ("Feedback Statistics", test_get_feedback_stats),
        ("Announcement Creation", test_announcement_creation),
        ("Get Announcements", test_get_announcements),
        ("Get All Feedback", test_all_feedback),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n[FAIL] {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASSED]" if result else "[FAILED]"
        print(f"{status} - {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nAll tests passed successfully!")
        return 0
    else:
        print(f"\n{total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
