"""
Delete KYC credential by email and clear from all collections
"""
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv('../.env')

def delete_credential_by_email(email):
    """Delete all KYC records for a user by email"""
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
        client = MongoClient(mongo_uri)
        db = client['aegis_kyc']
        
        print(f"🔍 Searching for KYC records for: {email}")
        print("=" * 60)
        
        # Find all credentials for this email
        credentials = list(db.kyc_credentials.find({'email': email}))
        
        if not credentials:
            print(f"❌ No KYC credentials found for {email}")
            print("\nChecking users collection...")
            user = db.users.find_one({'email': email})
            if user:
                print(f"✓ User found: {user.get('full_name', 'N/A')}")
                if 'credential_id' in user:
                    print(f"  Clearing credential_id: {user['credential_id']}")
                    db.users.update_one(
                        {'email': email},
                        {'$unset': {'credential_id': '', 'kyc_status': ''}}
                    )
                    print("✅ Credential cleared from user record")
            else:
                print("❌ User not found in database")
            return
        
        print(f"✓ Found {len(credentials)} credential(s)")
        
        for cred in credentials:
            credential_id = cred.get('credential_id')
            print(f"\n🗑️  Deleting credential: {credential_id}")
            
            # Delete from all collections
            r1 = db.kyc_credentials.delete_many({'credential_id': credential_id})
            print(f"  ✓ Deleted {r1.deleted_count} from kyc_credentials")
            
            r2 = db.document_analysis.delete_many({'credential_id': credential_id})
            print(f"  ✓ Deleted {r2.deleted_count} from document_analysis")
            
            r3 = db.verification_timeline.delete_many({'credential_id': credential_id})
            print(f"  ✓ Deleted {r3.deleted_count} from verification_timeline")
            
            r4 = db.verification_sessions.delete_many({'credential_id': credential_id})
            print(f"  ✓ Deleted {r4.deleted_count} from verification_sessions")
            
            r5 = db.face_analysis.delete_many({'credential_id': credential_id})
            print(f"  ✓ Deleted {r5.deleted_count} from face_analysis")
            
            r6 = db.video_liveness.delete_many({'credential_id': credential_id})
            print(f"  ✓ Deleted {r6.deleted_count} from video_liveness")
        
        # Clear from user record
        print(f"\n🧹 Clearing credential from user record...")
        result = db.users.update_one(
            {'email': email},
            {'$unset': {'credential_id': '', 'kyc_status': '', 'kyc_completion_date': ''}}
        )
        
        if result.modified_count > 0:
            print("  ✓ User record updated")
        else:
            print("  ⚠️  User record not found or already clear")
        
        print("\n" + "=" * 60)
        print("✅ Cleanup completed successfully!")
        print("\n📝 Next steps:")
        print("   1. Clear browser localStorage (F12 > Console > localStorage.clear())")
        print("   2. Refresh the dashboard page")
        print("   3. Start fresh KYC process")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Get email from command line or use default
    email = sys.argv[1] if len(sys.argv) > 1 else "ishansurdi@gmail.com"
    delete_credential_by_email(email)
