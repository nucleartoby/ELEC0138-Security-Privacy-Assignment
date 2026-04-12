"""
Quick check of ConsentRequests in MongoDB
"""
from pymongo import MongoClient
from bson import ObjectId

client = MongoClient('mongodb://localhost:27017/')
db = client['aegis_kyc_db']

print("\n=== CONSENT REQUESTS CHECK ===\n")

# Get all consent requests
consent_requests = list(db['ConsentRequests'].find({}))
print(f"Total consent requests in database: {len(consent_requests)}\n")

if consent_requests:
    for i, req in enumerate(consent_requests, 1):
        print(f"Request #{i}:")
        print(f"  _id: {req.get('_id')}")
        print(f"  request_id: {req.get('request_id')}")
        print(f"  organization_id: {req.get('organization_id')} (type: {type(req.get('organization_id')).__name__})")
        print(f"  organization_name: {req.get('organization_name')}")
        print(f"  user_id: {req.get('user_id')} (type: {type(req.get('user_id')).__name__})")
        print(f"  user_name: {req.get('user_name')}")
        print(f"  user_email: {req.get('user_email')}")
        print(f"  credential_id: {req.get('credential_id')}")
        print(f"  purpose: {req.get('purpose')}")
        print(f"  consent_status: {req.get('consent_status')}")
        print(f"  created_at: {req.get('created_at')}")
        print()
else:
    print("No consent requests found in database!\n")

# Check organizations
orgs = list(db['Organizations'].find({}))
print(f"Total organizations: {len(orgs)}")
if orgs:
    for org in orgs:
        print(f"\nOrganization:")
        print(f"  _id: {org.get('_id')} (type: {type(org.get('_id')).__name__})")
        print(f"  name: {org.get('organization_name')}")
        print(f"  email: {org.get('admin_email')}")

print("\n" + "="*50)
