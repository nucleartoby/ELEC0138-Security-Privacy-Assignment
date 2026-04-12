"""
Check credential API endpoint
"""
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def check_credential_api(user_id):
    """Check what the credential API returns"""
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
        client = MongoClient(mongo_uri)
        db = client['aegis_kyc']
        
        print(f"🔍 Checking credential for user: {user_id}")
        print("=" * 60)
        
        # Check KYCCredentials collection
        print("\n1️⃣ Checking KYCCredentials collection...")
        cred = db.KYCCredentials.find_one({'user_id': user_id})
        
        if cred:
            print("✅ Credential found in KYCCredentials:")
            print(f"   Credential ID: {cred.get('credential_id')}")
            print(f"   Status: {cred.get('status')}")
            print(f"   Issued At: {cred.get('issued_at')}")
            print(f"   Expiry: {cred.get('expiry_date')}")
            print(f"   Verification Summary: {cred.get('verification_summary')}")
        else:
            print("❌ No credential found in KYCCredentials collection")
        
        # Check user record
        from bson.objectid import ObjectId
        print("\n2️⃣ Checking Users collection...")
        user = db.Users.find_one({'_id': ObjectId(user_id)})
        
        if user:
            kyc_status = user.get('kyc_status', {})
            print("✅ User found:")
            print(f"   KYC Status: {kyc_status.get('current_state')}")
            print(f"   Completion: {kyc_status.get('completion_percent')}%")
            print(f"   Credential ID in user record: {user.get('credential_id', 'None')}")
        
        # Check what collections exist
        print("\n3️⃣ All collections in database:")
        collections = db.list_collection_names()
        for col in collections:
            count = db[col].count_documents({})
            print(f"   {col}: {count} documents")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_credential_api("691c6b3fd63c7a092591b82c")
