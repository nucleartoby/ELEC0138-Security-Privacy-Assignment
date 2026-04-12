"""
Check and update user KYC status
"""
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def check_user_status(email):
    """Check user's KYC status and credentials"""
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
        client = MongoClient(mongo_uri)
        db = client['aegis_kyc']
        
        print(f"🔍 Checking status for: {email}")
        print("=" * 60)
        
        # Find user by email hash (since data is encrypted)
        from app.utils.encryption import EncryptionService
        email_hash = EncryptionService.generate_checksum(email.lower())
        user = db.Users.find_one({'email_hash': email_hash})
        
        if not user:
            print(f"❌ User not found: {email}")
            return
        
        print(f"✓ User found!")
        print(f"  User ID: {user.get('_id')}")
        user_id = str(user.get('_id'))
        
        # Decrypt personal info to display
        from app.utils.encryption import EncryptionService
        decrypted = EncryptionService.decrypt_pii_data(user)
        personal_info = decrypted.get('personal_info', {})
        
        print(f"  Name: {personal_info.get('full_name', 'N/A')}")
        print(f"  Email: {personal_info.get('email', 'N/A')}")
        
        # Check KYC status
        kyc_status = user.get('kyc_status', {})
        print(f"  KYC Status: {kyc_status.get('current_state', 'N/A')}")
        print(f"  Completion: {kyc_status.get('completion_percent', 0)}%")
        
        # Check KYC credentials
        print("\n🔍 Checking KYC credentials...")
        credentials = list(db.KYCCredentials.find({'user_id': user_id}))
        
        if credentials:
            print(f"✓ Found {len(credentials)} credential(s):")
            for cred in credentials:
                print(f"  - Credential ID: {cred.get('credential_id')}")
                print(f"    Status: {cred.get('status')}")
                print(f"    Created: {cred.get('created_at')}")
        else:
            print("❌ No KYC credentials found")
            
        # Check verification sessions
        print("\n🔍 Checking verification sessions...")
        sessions = list(db.VerificationSessions.find({'user_id': user_id}))
        
        if sessions:
            print(f"✓ Found {len(sessions)} session(s):")
            for session in sessions:
                print(f"  - Verification ID: {session.get('verification_id')}")
                print(f"    Status: {session.get('status')}")
                print(f"    Progress: {session.get('progress_percentage', 0)}%")
        else:
            print("❌ No verification sessions found")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    check_user_status("ishansurdi2105@gmail.com")
