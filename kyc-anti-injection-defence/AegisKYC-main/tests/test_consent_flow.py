"""
Test script to verify consent request flow
"""
import requests
import json

BASE_URL = "http://localhost:5000"

# Test user credentials (from previous context)
TEST_USER_ID = "691c6b3fd63c7a092591b82c"
TEST_CREDENTIAL_ID = "KYC-CC30052F62A0979F"
TEST_EMAIL = "ishansurdi2105@gmail.com"

print("=" * 60)
print("CONSENT REQUEST FLOW TEST")
print("=" * 60)

# Step 1: Check if consent requests exist for user
print("\n[1] Checking consent requests for user...")
response = requests.get(f"{BASE_URL}/api/user/consent-requests/{TEST_USER_ID}")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

if response.status_code == 200:
    data = response.json()
    if data.get('success'):
        requests_list = data.get('requests', [])
        print(f"\n✓ Found {len(requests_list)} consent request(s)")
        
        for i, req in enumerate(requests_list, 1):
            print(f"\nRequest {i}:")
            print(f"  - Organization: {req.get('organization_name')}")
            print(f"  - Purpose: {req.get('purpose')}")
            print(f"  - Status: {req.get('consent_status')}")
            print(f"  - Created: {req.get('created_at')}")
    else:
        print("✗ Failed to fetch consent requests")
else:
    print("✗ Error fetching consent requests")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
