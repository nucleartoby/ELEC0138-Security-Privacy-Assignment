"""
Enhanced MongoDB Collections for Complete KYC Verification System
Includes all fields for 10-step verification process
"""
import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv
from datetime import datetime

# Load .env from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
dotenv_path = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(dotenv_path)

MONGO_URI = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URI)
db = client["Aegiskyc"]

def create_enhanced_collections():
    """Create all collections with proper indexes"""
    
    print("Creating enhanced collections for KYC verification system...")
    
    # ============ KYC VERIFICATION REQUESTS COLLECTION ============
    kyc_requests = db["KYCVerificationRequests"]
    kyc_requests.create_index([("user_id", ASCENDING)])
    kyc_requests.create_index([("status", ASCENDING)])
    kyc_requests.create_index([("created_at", DESCENDING)])
    kyc_requests.create_index([("current_step", ASCENDING)])
    
    print("✓ KYCVerificationRequests collection created")
    
    # ============ STEP 0: PRE-VERIFICATION CHECKS ============
    pre_verification = db["PreVerificationChecks"]
    pre_verification.create_index([("user_id", ASCENDING)])
    pre_verification.create_index([("device_fingerprint", ASCENDING)])
    pre_verification.create_index([("risk_level", ASCENDING)])
    pre_verification.create_index([("timestamp", DESCENDING)])
    
    print("✓ PreVerificationChecks collection created")
    
    # ============ STEP 1-2: DOCUMENT ANALYSIS ============
    document_analysis = db["DocumentAnalysis"]
    document_analysis.create_index([("user_id", ASCENDING)])
    document_analysis.create_index([("document_type", ASCENDING)])
    document_analysis.create_index([("authenticity_score", DESCENDING)])
    document_analysis.create_index([("verification_status", ASCENDING)])
    
    print("✓ DocumentAnalysis collection created")
    
    # ============ STEP 3: FACE VERIFICATION ============
    face_verification = db["FaceVerification"]
    face_verification.create_index([("user_id", ASCENDING)])
    face_verification.create_index([("liveness_score", DESCENDING)])
    face_verification.create_index([("face_match_score", DESCENDING)])
    face_verification.create_index([("timestamp", DESCENDING)])
    
    print("✓ FaceVerification collection created")
    
    # ============ STEP 4: ADDRESS VERIFICATION ============
    address_verification = db["AddressVerification"]
    address_verification.create_index([("user_id", ASCENDING)])
    address_verification.create_index([("verification_status", ASCENDING)])
    
    print("✓ AddressVerification collection created")
    
    # ============ STEP 5: VIDEO VERIFICATION ============
    video_verification = db["VideoVerification"]
    video_verification.create_index([("user_id", ASCENDING)])
    video_verification.create_index([("lipsync_score", DESCENDING)])
    video_verification.create_index([("deepfake_detection_score", DESCENDING)])
    
    print("✓ VideoVerification collection created")
    
    # ============ STEP 6: AML & FRAUD SCREENING ============
    aml_screening = db["AMLScreening"]
    aml_screening.create_index([("user_id", ASCENDING)])
    aml_screening.create_index([("risk_level", ASCENDING)])
    aml_screening.create_index([("sanctions_hit", ASCENDING)])
    aml_screening.create_index([("timestamp", DESCENDING)])
    
    print("✓ AMLScreening collection created")
    
    # ============ STEP 7: RISK SCORING ============
    risk_scores = db["RiskScores"]
    risk_scores.create_index([("user_id", ASCENDING)])
    risk_scores.create_index([("identity_integrity_score", DESCENDING)])
    risk_scores.create_index([("final_risk_level", ASCENDING)])
    risk_scores.create_index([("timestamp", DESCENDING)])
    
    print("✓ RiskScores collection created")
    
    # ============ STEP 9: KYC CREDENTIALS ============
    kyc_credentials = db["KYCCredentials"]
    kyc_credentials.create_index([("user_id", ASCENDING)], unique=True)
    kyc_credentials.create_index([("credential_id", ASCENDING)], unique=True)
    kyc_credentials.create_index([("issued_at", DESCENDING)])
    kyc_credentials.create_index([("expiry_date", ASCENDING)])
    
    print("✓ KYCCredentials collection created")
    
    # ============ VERIFICATION TIMELINE (Audit Trail) ============
    verification_timeline = db["VerificationTimeline"]
    verification_timeline.create_index([("user_id", ASCENDING)])
    verification_timeline.create_index([("step", ASCENDING)])
    verification_timeline.create_index([("timestamp", DESCENDING)])
    
    print("✓ VerificationTimeline collection created")
    
    print("\n✅ All enhanced collections created successfully!")
    print(f"Database: {db.name}")
    print(f"Collections: {db.list_collection_names()}")

if __name__ == "__main__":
    create_enhanced_collections()
