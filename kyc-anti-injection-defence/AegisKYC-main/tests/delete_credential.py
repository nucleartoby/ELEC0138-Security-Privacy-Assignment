"""
Delete all records for a specific credential ID
"""
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv('../.env')

def delete_credential(credential_id):
    """Delete all records for a given credential ID"""
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
        client = MongoClient(mongo_uri)
        db = client['aegis_kyc']
        
        print(f"🗑️  Deleting all records for Credential: {credential_id}")
        print("=" * 60)
        
        # Delete from kyc_credentials
        result1 = db.kyc_credentials.delete_many({'credential_id': credential_id})
        print(f"✓ Deleted {result1.deleted_count} record(s) from kyc_credentials")
        
        # Delete from document_analysis
        result2 = db.document_analysis.delete_many({'credential_id': credential_id})
        print(f"✓ Deleted {result2.deleted_count} record(s) from document_analysis")
        
        # Delete from verification_timeline
        result3 = db.verification_timeline.delete_many({'credential_id': credential_id})
        print(f"✓ Deleted {result3.deleted_count} record(s) from verification_timeline")
        
        # Delete from verification_sessions
        result4 = db.verification_sessions.delete_many({'credential_id': credential_id})
        print(f"✓ Deleted {result4.deleted_count} record(s) from verification_sessions")
        
        # Delete from face_analysis
        result5 = db.face_analysis.delete_many({'credential_id': credential_id})
        print(f"✓ Deleted {result5.deleted_count} record(s) from face_analysis")
        
        # Delete from video_liveness
        result6 = db.video_liveness.delete_many({'credential_id': credential_id})
        print(f"✓ Deleted {result6.deleted_count} record(s) from video_liveness")
        
        print("=" * 60)
        total = (result1.deleted_count + result2.deleted_count + result3.deleted_count + 
                 result4.deleted_count + result5.deleted_count + result6.deleted_count)
        print(f"🎯 Total records deleted: {total}")
        print("✅ Cleanup completed successfully!")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Delete specific credential
    delete_credential("KYC-811987C4256DB444")
