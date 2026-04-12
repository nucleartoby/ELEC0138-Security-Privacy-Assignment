"""
Verify MongoDB collections and consent request data
"""
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['aegis_kyc_db']

print("=" * 60)
print("DATABASE VERIFICATION")
print("=" * 60)

# List all collections
print("\n[Collections]")
collections = db.list_collection_names()
for coll in collections:
    count = db[coll].count_documents({})
    print(f"  - {coll}: {count} documents")

# Check ConsentRequests collection
print("\n[ConsentRequests Collection]")
consent_requests = db['ConsentRequests']
total = consent_requests.count_documents({})
print(f"Total consent requests: {total}")

if total > 0:
    print("\nSample consent requests:")
    for req in consent_requests.find().limit(5):
        print(f"\n  Request ID: {req.get('request_id', 'N/A')}")
        print(f"  Organization: {req.get('organization_name', 'N/A')}")
        print(f"  User ID: {req.get('user_id')} (type: {type(req.get('user_id')).__name__})")
        print(f"  Status: {req.get('consent_status', 'N/A')}")
        print(f"  Purpose: {req.get('purpose', 'N/A')}")
        print(f"  Created: {req.get('created_at', 'N/A')}")

# Check for specific user
print("\n[User Lookup]")
TEST_USER_ID = "691c6b3fd63c7a092591b82c"
try:
    user_obj_id = ObjectId(TEST_USER_ID)
    print(f"Searching for user_id as ObjectId: {user_obj_id}")
    
    requests_obj = list(consent_requests.find({'user_id': user_obj_id}))
    print(f"Found {len(requests_obj)} requests with ObjectId")
    
    requests_str = list(consent_requests.find({'user_id': TEST_USER_ID}))
    print(f"Found {len(requests_str)} requests with String")
    
except Exception as e:
    print(f"Error: {str(e)}")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
