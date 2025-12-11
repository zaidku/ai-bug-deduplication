"""
Sample API usage examples
"""

import json

import requests

# Base URL
BASE_URL = "http://localhost:5000/api"


def submit_bug():
    """Submit a new bug"""
    bug_data = {
        "title": "App crashes when uploading large images",
        "description": "When I try to upload an image larger than 5MB, the app crashes immediately. This happens consistently on my device.",
        "repro_steps": "1. Open the app\n2. Navigate to upload section\n3. Select an image > 5MB\n4. Tap upload\n5. App crashes",
        "logs": "Error: OutOfMemoryException at ImageUploader.java:145",
        "severity": "High",
        "priority": "High",
        "reporter": "qa@example.com",
        "device": "Samsung Galaxy S23",
        "os_version": "Android 14",
        "build_version": "2.1.0",
        "region": "US",
    }

    response = requests.post(f"{BASE_URL}/bugs/", json=bug_data)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    return response.json()


def get_bug(bug_id):
    """Get bug details"""
    response = requests.get(f"{BASE_URL}/bugs/{bug_id}?include_duplicates=true")
    print(json.dumps(response.json(), indent=2))
    return response.json()


def list_bugs():
    """List all bugs"""
    response = requests.get(f"{BASE_URL}/bugs/?page=1&per_page=10")
    print(json.dumps(response.json(), indent=2))
    return response.json()


def get_duplicates(bug_id):
    """Get duplicates of a bug"""
    response = requests.get(f"{BASE_URL}/bugs/{bug_id}/duplicates")
    print(json.dumps(response.json(), indent=2))
    return response.json()


def get_low_quality_queue():
    """Get low quality submissions"""
    response = requests.get(f"{BASE_URL}/qa/low-quality?status=Pending")
    print(json.dumps(response.json(), indent=2))
    return response.json()


def approve_low_quality(item_id):
    """Approve a low quality submission"""
    data = {
        "reviewed_by": "qa@example.com",
        "notes": "Reviewed and approved after clarification",
    }
    response = requests.post(f"{BASE_URL}/qa/low-quality/{item_id}/approve", json=data)
    print(json.dumps(response.json(), indent=2))
    return response.json()


def promote_duplicate(bug_id):
    """Promote a duplicate to independent bug"""
    data = {
        "user": "qa@example.com",
        "reason": "After investigation, this is a different issue with similar symptoms",
    }
    response = requests.post(f"{BASE_URL}/qa/bugs/{bug_id}/promote", json=data)
    print(json.dumps(response.json(), indent=2))
    return response.json()


def get_system_stats():
    """Get system statistics"""
    response = requests.get(f"{BASE_URL}/monitoring/stats")
    print(json.dumps(response.json(), indent=2))
    return response.json()


def get_duplicate_stats():
    """Get duplicate statistics"""
    response = requests.get(f"{BASE_URL}/monitoring/stats/duplicates")
    print(json.dumps(response.json(), indent=2))
    return response.json()


if __name__ == "__main__":
    print("=== Submitting a bug ===")
    result = submit_bug()

    print("\n=== Getting system stats ===")
    get_system_stats()

    print("\n=== Listing bugs ===")
    list_bugs()
