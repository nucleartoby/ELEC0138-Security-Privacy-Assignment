"""
Check user by ID
"""
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def check_user_by_id(user_id):
    """Check user by ID"""
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
        client = MongoClient(mongo_uri)
        db = client['aegis_kyc']
        
        print(f"🔍 Checking user ID: {user_id}")
        print("=" * 60)
        
        # Find user by ObjectId
        user = db.Users.find_one({'_id': ObjectId(user_id)})
        
        if not user:
            print(f"❌ User not found with ID: {user_id}")
            return
        
        print(f"✓ User found!")
        print(f"  Name: {user.get('full_name', 'N/A')}")
        print(f"  Email: {user.get('email', 'N/A')}")
        print(f"  Phone: {user.get('phone', 'N/A')}")
        print(f"  Credential ID: {user.get('credential_id', 'None')}")
        print(f"  KYC Status: {user.get('kyc_status', 'None')}")
        
        # Check verification sessions
        print("\n🔍 Checking verification sessions...")
        sessions = list(db.VerificationSessions.find({'user_id': user_id}))
        
        if sessions:
            print(f"✓ Found {len(sessions)} session(s):")
            for session in sessions[:5]:  # Show last 5
                print(f"\n  Session ID: {session.get('_id')}")
                print(f"  Verification ID: {session.get('verification_id')}")
                print(f"  Status: {session.get('status')}")
                print(f"  Progress: {session.get('progress_percentage', 0)}%")
                print(f"  Current Step: {session.get('current_step', 'N/A')}")
                
                # Check if documents uploaded
                if session.get('documents_uploaded'):
                    print(f"  Documents: {len(session.get('documents_uploaded', []))} uploaded")
        else:
            print("❌ No verification sessions found")
        
        # Check KYC credentials
        print("\n🔍 Checking KYC credentials...")
        credentials = list(db.KYCCredentials.find({'user_id': user_id}))
        
        if credentials:
            print(f"✓ Found {len(credentials)} credential(s):")
            for cred in credentials:
                print(f"\n  Credential ID: {cred.get('credential_id')}")
                print(f"  Status: {cred.get('status')}")
                print(f"  Created: {cred.get('created_at')}")
        else:
            print("❌ No KYC credentials found")
            print("\nℹ️  This means KYC process was started but not completed.")
            print("   User needs to complete the KYC flow to get a credential.")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    check_user_by_id("691c6b3fd63c7a092591b82c")
