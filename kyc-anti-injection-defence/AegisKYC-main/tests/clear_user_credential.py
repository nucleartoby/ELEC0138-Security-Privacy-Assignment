"""
Clear credential_id from user record
"""
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def clear_user_credential(email):
    """Clear credential_id from user record"""
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
        client = MongoClient(mongo_uri)
        db = client['aegis_kyc']
        
        print(f"🔍 Looking for user: {email}")
        print("=" * 60)
        
        # Find user
        user = db.users.find_one({'email': email})
        
        if not user:
            print(f"❌ User not found: {email}")
            return
        
        print(f"✓ User found: {user.get('name', 'N/A')}")
        print(f"  Current credential_id: {user.get('credential_id', 'None')}")
        print(f"  Current kyc_status: {user.get('kyc_status', 'None')}")
        
        # Clear credential fields
        result = db.users.update_one(
            {'email': email},
            {
                '$unset': {
                    'credential_id': '',
                    'kyc_status': '',
                    'kyc_completion_date': ''
                }
            }
        )
        
        if result.modified_count > 0:
            print("\n✅ Credential cleared successfully!")
            print("   The user can now start fresh KYC")
        else:
            print("\n⚠️  No changes made (fields already empty)")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    clear_user_credential("ishansurdi@gmail.com")
