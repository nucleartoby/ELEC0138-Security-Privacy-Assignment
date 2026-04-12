# setup_collections.py
import os
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URL")

client = MongoClient(MONGO_URI)
db = client["Aegiskyc"]

# -------- USERS COLLECTION (Main KYC User Data) --------
users = db["Users"]
users.create_index("personal_info.email", unique=True)
users.create_index("personal_info.phone", unique=True)
users.create_index("created_at")
users.create_index("kyc_status.current_state")
users.create_index("risk_engine.fraud_risk_level")

user_doc_template = {
    "_id": "",  # ObjectId
    
    "personal_info": {
        "full_name": "",
        "email": "",
        "phone": "",
        "dob": "",
        "gender": "",
        "address": {
            "line1": "",
            "line2": "",
            "city": "",
            "state": "",
            "country": "",
            "pincode": ""
        }
    },

    "account_credentials": {
        "password_hash": "",
        "salt": "",
        "last_password_change": None,
        "two_factor_enabled": False,
        "two_factor_method": ""  # sms/email/app
    },

    "kyc_status": {
        "current_state": "not_started",  # not_started / in_progress / verified / rejected / flagged
        "completion_percent": 0,
        "last_updated": None,
        "reason_if_rejected": ""
    },

    "document_data": {
        "submitted_docs": [
            {
                "doc_type": "",  # aadhaar/pan/passport/dl/voter
                "file_url": "",
                "upload_time": None,
                "verified": False,
                "verification_result": "",
                "extracted_fields": {
                    "name": "",
                    "dob": "",
                    "id_number": "",
                    "address": ""
                },
                "forgery_score": 0,
                "reflectance_signature": ""
            }
        ],
        "digilocker_used": False,
        "digilocker_metadata": {
            "token_id": "",
            "fetch_timestamp": None
        }
    },

    "biometrics": {
        "face_embedding_vector": [],
        "face_liveness_score": 0,
        "micro_gesture_pattern_id": "",
        "last_face_verification": None
    },

    "behavioral_signals": {
        "typing_pattern_score": 0,
        "camera_stability_score": 0,
        "interaction_speed_score": 0,
        "suspicious_pattern_detected": False
    },

    "risk_engine": {
        "identity_integrity_score": 0,
        "fraud_risk_level": "low",  # low/medium/high
        "device_trust_score": 0,
        "geo_risk_score": 0,
        "previous_flags": []
    },

    "device_metadata": {
        "device_id": "",
        "device_type": "",  # mobile/web/tablet
        "os_version": "",
        "browser": "",
        "screen_resolution": "",
        "ip_address": "",
        "location_coords": "",  # lat,long
        "is_vpn": False
    },

    "consent_log": [
        {
            "timestamp": None,
            "requested_by": "",
            "purpose": "",
            "data_shared": [],
            "approved": False
        }
    ],

    "audit_trail": [
        {
            "event": "",  # login/failed_login/document_upload/kyc_update/etc
            "timestamp": None,
            "ip": "",
            "device": "",
            "notes": ""
        }
    ],

    "security": {
        "encryption_version": "AES-256-GCM",
        "data_checksum": "",
        "failed_login_attempts": 0,
        "account_locked": False,
        "last_activity": None
    },

    "created_at": None,
    "updated_at": None
}

# -------- KYC REQUESTS (Separate tracking for KYC submission workflows) --------
kyc_req = db["KYCRequests"]
kyc_req.create_index("user_id")
kyc_req.create_index("status")
kyc_req.create_index("created_at")
kyc_req.create_index("request_id", unique=True)

kyc_request_template = {
    "user_id": "",
    "request_id": "",
    "submitted_docs": [],
    "risk_level": "unknown",
    "status": "pending",  # pending, verified, rejected
    "reviewer_notes": "",
    "created_at": None,
    "updated_at": None
}

# -------- DOCUMENTS (Separate document storage and metadata) --------
docs = db["Documents"]
docs.create_index("user_id")
docs.create_index("doc_type")
docs.create_index("uploaded_at")
docs.create_index("verified")

document_template = {
    "user_id": "",
    "doc_type": "",  # aadhaar/pan/passport/dl/voter
    "file_url": "",
    "upload_time": None,
    "verified": False,
    "verification_result": "",
    "extracted_fields": {
        "name": "",
        "dob": "",
        "id_number": "",
        "address": ""
    },
    "forgery_score": 0,
    "reflectance_signature": "",
    "metadata": {},
    "uploaded_at": None
}

# -------- BIOMETRICS (Separate collection for biometric data) --------
biometrics = db["Biometrics"]
biometrics.create_index("user_id", unique=True)
biometrics.create_index("last_face_verification")

biometrics_template = {
    "user_id": "",
    "face_embedding_vector": [],
    "face_liveness_score": 0,
    "micro_gesture_pattern_id": "",
    "last_face_verification": None,
    "created_at": None,
    "updated_at": None
}

# -------- RISK SCORES (Enhanced risk assessment) --------
risk_scores = db["RiskScores"]
risk_scores.create_index("user_id", unique=True)
risk_scores.create_index("fraud_risk_level")
risk_scores.create_index("updated_at")

risk_score_template = {
    "user_id": "",
    "identity_integrity_score": 0,
    "behavioral_score": 0,
    "document_score": 0,
    "device_trust_score": 0,
    "geo_risk_score": 0,
    "fraud_risk_level": "low",  # low/medium/high
    "previous_flags": [],
    "final_risk": "unknown",
    "updated_at": None
}

# -------- BEHAVIORAL SIGNALS (Track user behavior patterns) --------
behavioral_signals = db["BehavioralSignals"]
behavioral_signals.create_index("user_id", unique=True)
behavioral_signals.create_index("suspicious_pattern_detected")

behavioral_signals_template = {
    "user_id": "",
    "typing_pattern_score": 0,
    "camera_stability_score": 0,
    "interaction_speed_score": 0,
    "suspicious_pattern_detected": False,
    "created_at": None,
    "updated_at": None
}

# -------- DEVICE METADATA (Enhanced device fingerprinting) --------
device_metadata = db["DeviceMetadata"]
device_metadata.create_index("device_id", unique=True)
device_metadata.create_index("user_id")
device_metadata.create_index("is_vpn")

device_metadata_template = {
    "device_id": "",
    "user_id": "",
    "device_type": "",  # mobile/web/tablet
    "os_version": "",
    "browser": "",
    "screen_resolution": "",
    "ip_address": "",
    "location_coords": "",  # lat,long
    "is_vpn": False,
    "trust_score": 0,
    "ip_history": [],
    "created_at": None,
    "updated_at": None
}

# -------- AUDIT LOGS (Enhanced audit trail) --------
audit_logs = db["AuditLogs"]
audit_logs.create_index("user_id")
audit_logs.create_index("timestamp")
audit_logs.create_index("event")

audit_log_template = {
    "user_id": "",
    "event": "",  # login/failed_login/document_upload/kyc_update/etc
    "timestamp": None,
    "ip": "",
    "device": "",
    "notes": "",
    "metadata": {}
}

# -------- SESSIONS --------
sessions = db["Sessions"]
sessions.create_index("user_id")
sessions.create_index("created_at")
sessions.create_index("session_token", unique=True)

session_template = {
    "user_id": "",
    "session_token": "",
    "ip": "",
    "device_info": "",
    "created_at": None,
    "expires_at": None
}

# -------- CONSENT LEDGER (Enhanced consent tracking) --------
consent = db["ConsentLedger"]
consent.create_index("user_id")
consent.create_index("timestamp")

consent_template = {
    "user_id": "",
    "timestamp": None,
    "requested_by": "",
    "purpose": "",
    "data_shared": [],
    "approved": False,
    "action": "",  # data_sharing, verification, etc
    "target_institution": ""
}

# -------- SECURITY EVENTS (Track security-related events) --------
security_events = db["SecurityEvents"]
security_events.create_index("user_id")
security_events.create_index("event_type")
security_events.create_index("timestamp")

security_events_template = {
    "user_id": "",
    "event_type": "",  # failed_login/account_locked/password_change/2fa_enabled
    "timestamp": None,
    "ip": "",
    "device": "",
    "encryption_version": "AES-256-GCM",
    "data_checksum": "",
    "metadata": {}
}

# -------- ANALYTICS --------
analytics = db["Analytics"]
analytics.create_index("event_name")
analytics.create_index("timestamp")

analytics_template = {
    "event_name": "",
    "count": 0,
    "metadata": {},
    "timestamp": None
}

print("✅ All collections created with indexes successfully!")
print(f"✅ Total collections: {len(db.list_collection_names())}")
print(f"✅ Collections: Users, KYCRequests, Documents, Biometrics, RiskScores, BehavioralSignals, DeviceMetadata, AuditLogs, Sessions, ConsentLedger, SecurityEvents, Analytics")

