#!/usr/bin/env python3
"""
Quick test script for Schedule Management API endpoints
"""
import requests
import json
from datetime import datetime, timedelta

API_BASE = "http://localhost:8000/schedule-management"

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
        response = requests.post(f"{API_BASE}/feedback", json=feedback_data)
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ Feedback submitted successfully!")
        print(f"📝 Feedback ID: {result.get('message', '')}")
        print(f"\n📱 WhatsApp Message Preview:")
        print("-" * 60)
        print(result.get('whatsapp_message', '')[:300] + "...")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_get_feedback_stats():
    """Test getting feedback statistics"""
    print("\n" + "="*60)
    print("Testing Feedback Statistics")
    print("="*60)
    
    try:
        response = requests.get(f"{API_BASE}/feedback/stats/summary")
        response.raise_for_status()
        stats = response.json()
        
        print(f"✅ Statistics retrieved successfully!")
        print(f"📊 Total Feedback: {stats['total_feedback']}")
        print(f"⏳ Pending: {stats['pending']}")
        print(f"🔄 In Progress: {stats['in_progress']}")
        print(f"✅ Resolved: {stats['resolved']}")
        print(f"📈 Resolution Rate: {stats['resolution_rate']}%")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
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
        response = requests.post(f"{API_BASE}/announcements", json=announcement_data)
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ Announcement created successfully!")
        print(f"📢 Title: {result['title']}")
        print(f"👤 Author: {result['author']}")
        print(f"🔴 Priority: {result['priority'].upper()}")
        print(f"👥 Audience: {result['target_audience']}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_get_announcements():
    """Test getting announcements"""
    print("\n" + "="*60)
    print("Testing Get Announcements")
    print("="*60)
    
    try:
        response = requests.get(f"{API_BASE}/announcements?active_only=true")
        response.raise_for_status()
        announcements = response.json()
        
        print(f"✅ Retrieved {len(announcements)} active announcement(s)")
        
        for idx, ann in enumerate(announcements[:3], 1):
            print(f"\n{idx}. {ann['title']}")
            print(f"   Author: {ann['author']}")
            print(f"   Priority: {ann['priority']}")
            print(f"   Created: {ann['created_at']}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_all_feedback():
    """Test getting all feedback"""
    print("\n" + "="*60)
    print("Testing Get All Feedback")
    print("="*60)
    
    try:
        response = requests.get(f"{API_BASE}/feedback")
        response.raise_for_status()
        feedbacks = response.json()
        
        print(f"✅ Retrieved {len(feedbacks)} feedback submission(s)")
        
        for idx, fb in enumerate(feedbacks[:3], 1):
            print(f"\n{idx}. {fb['issue_type']}")
            print(f"   By: {fb['name']} ({fb['roll_number']})")
            print(f"   Status: {fb['status'].upper()}")
            print(f"   Submitted: {fb['created_at']}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("\n🚀 Starting Schedule Management API Tests")
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
            print(f"\n❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed successfully!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")

if __name__ == "__main__":
    main()
