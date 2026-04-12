"""
List all users in database
"""
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def list_all_users():
    """List all users in database"""
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
        client = MongoClient(mongo_uri)
        db = client['aegis_kyc']
        
        print("🔍 Listing all users in database...")
        print("=" * 60)
        
        users = list(db.Users.find())
        
        if not users:
            print("❌ No users found in database!")
            print("\nℹ️  This means signup is not persisting to MongoDB.")
        else:
            print(f"✓ Found {len(users)} user(s):\n")
            for user in users:
                print(f"ID: {user.get('_id')}")
                print(f"  Name: {user.get('full_name', 'N/A')}")
                print(f"  Email: {user.get('email', 'N/A')}")
                print(f"  Phone: {user.get('phone', 'N/A')}")
                print(f"  Credential ID: {user.get('credential_id', 'None')}")
                print(f"  KYC Status: {user.get('kyc_status', 'None')}")
                print(f"  Created: {user.get('created_at', 'N/A')}")
                print("-" * 60)
        
        # Also check verification sessions
        print("\n🔍 Checking verification sessions...")
        sessions = list(db.VerificationSessions.find())
        print(f"✓ Found {len(sessions)} session(s)")
        
        for session in sessions[:5]:
            print(f"\n  User ID: {session.get('user_id')}")
            print(f"  Verification ID: {session.get('verification_id')}")
            print(f"  Status: {session.get('status')}")
        
        # Check credentials
        print("\n🔍 Checking KYC credentials...")
        credentials = list(db.KYCCredentials.find())
        print(f"✓ Found {len(credentials)} credential(s)")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    list_all_users()
