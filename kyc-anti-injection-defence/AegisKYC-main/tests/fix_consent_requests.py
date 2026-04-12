"""
Fix existing consent requests to populate missing user_name and user_email
"""
from pymongo import MongoClient
from bson import ObjectId
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'app'))

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['aegis_kyc_db']

consent_requests = db['ConsentRequests']
users = db['Users']

print("\n=== FIXING CONSENT REQUESTS ===\n")

# Get all consent requests
all_requests = list(consent_requests.find({}))
print(f"Found {len(all_requests)} consent requests to check\n")

fixed_count = 0
for req in all_requests:
    user_id = req.get('user_id')
    current_name = req.get('user_name', '')
    current_email = req.get('user_email', '')
    
    # Check if name or email is missing
    if not current_name or not current_email or current_name.strip() == '':
        print(f"Request {req.get('request_id')} needs fixing:")
        print(f"  Current name: '{current_name}'")
        print(f"  Current email: '{current_email}'")
        
        # Get user details
        try:
            if isinstance(user_id, str):
                try:
                    user_id = ObjectId(user_id)
                except:
                    pass
            
            user = users.find_one({'_id': user_id})
            
            if user:
                # Get user details
                first_name = user.get('first_name', '')
                last_name = user.get('last_name', '')
                email = user.get('email', '')
                
                # Try to decrypt if encrypted
                if user.get('encrypted_first_name') or user.get('encrypted_last_name'):
                    try:
                        from services.encryption_service import EncryptionService
                        encryption_service = EncryptionService()
                        
                        if user.get('encrypted_first_name'):
                            first_name = encryption_service.decrypt(user['encrypted_first_name'])
                        if user.get('encrypted_last_name'):
                            last_name = encryption_service.decrypt(user['encrypted_last_name'])
                    except Exception as e:
                        print(f"  Decryption warning: {str(e)}")
                        first_name = first_name or 'User'
                        last_name = last_name or ''
                
                user_full_name = f"{first_name} {last_name}".strip() or "Unknown User"
                
                # Update the consent request
                result = consent_requests.update_one(
                    {'_id': req['_id']},
                    {
                        '$set': {
                            'user_name': user_full_name,
                            'user_email': email
                        }
                    }
                )
                
                if result.modified_count > 0:
                    print(f"  ✓ Updated - Name: {user_full_name}, Email: {email}")
                    fixed_count += 1
                else:
                    print(f"  ✗ Update failed")
            else:
                print(f"  ✗ User not found for ID: {user_id}")
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
        
        print()

print(f"\n=== COMPLETE ===")
print(f"Fixed {fixed_count} consent requests")

# Show updated requests
print("\nUpdated consent requests:")
updated_requests = list(consent_requests.find({}))
for req in updated_requests:
    print(f"  {req.get('request_id')}: {req.get('user_name')} ({req.get('user_email')})")
