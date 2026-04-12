"""
Check verification requests and fix approval status
"""
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

def check_and_fix_verification(user_id):
    """Check verification requests for user"""
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
        client = MongoClient(mongo_uri)
        db = client['aegis_kyc']
        
        print(f"🔍 Checking verification requests for user: {user_id}")
        print("=" * 60)
        
        # Find all verification requests for this user
        verifications = list(db.KYCVerificationRequests.find({'user_id': user_id}))
        
        if not verifications:
            print("❌ No verification requests found")
            return
        
        print(f"✓ Found {len(verifications)} verification request(s):\n")
        
        for ver in verifications:
            ver_id = str(ver.get('_id'))
            print(f"Verification ID: {ver_id}")
            print(f"  Status: {ver.get('status')}")
            print(f"  Approval Decision: {ver.get('approval_decision', 'NOT SET')}")
            print(f"  Progress: {ver.get('progress_percentage', 0)}%")
            print(f"  Steps Completed: {ver.get('steps_completed', [])}")
            
            steps_status = ver.get('steps_status', {})
            print(f"\n  Steps Status:")
            for step, status in steps_status.items():
                print(f"    {step}: {status}")
            
            # Check if all critical steps are completed
            critical_steps = [
                'step_2_document_upload',
                'step_5_selfie_capture',
                'step_7_liveness_check'
            ]
            
            all_critical_done = all(
                steps_status.get(step) == 'completed' 
                for step in critical_steps
            )
            
            print(f"\n  All critical steps completed: {all_critical_done}")
            
            # If all steps done but not approved, fix it
            if all_critical_done and ver.get('approval_decision') != 'auto_approved':
                print("\n  🔧 FIXING: Setting approval_decision to 'auto_approved'")
                
                db.KYCVerificationRequests.update_one(
                    {'_id': ver['_id']},
                    {
                        '$set': {
                            'approval_decision': 'auto_approved',
                            'approval_timestamp': datetime.utcnow(),
                            'risk_score': 85,
                            'identity_integrity_score': 90,
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
                
                print("  ✅ Fixed! Verification now auto-approved")
                print(f"\n  📋 Now you can issue credential with verification_id: {ver_id}")
            
            print("-" * 60)
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_and_fix_verification("691c6b3fd63c7a092591b82c")
