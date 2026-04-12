"""
Authentication Service
Handles user registration with enterprise-grade security
- AES-256-GCM encryption for PII
- PBKDF2 password hashing
- GDPR/CCPA compliant data handling
- Audit trail logging
"""
import os
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.encryption import EncryptionService
from utils.validators import Validators

# Load .env from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
dotenv_path = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(dotenv_path)

MONGO_URI = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["aegis_kyc"]


class AuthService:
    """
    Handles user authentication and registration
    Implements bank-grade security standards
    """
    
    @staticmethod
    def check_existing_user(email: str, phone: str) -> dict:
        """
        Check if user already exists (on encrypted data)
        """
        # We need to encrypt the email/phone to search
        # For now, we'll use a hash index approach
        email_hash = EncryptionService.generate_checksum(email.lower())
        phone_hash = EncryptionService.generate_checksum(phone)
        
        existing = db["Users"].find_one({
            "$or": [
                {"email_hash": email_hash},
                {"phone_hash": phone_hash}
            ]
        })
        
        return {
            "exists": existing is not None,
            "user_id": str(existing["_id"]) if existing else None
        }
    
    @staticmethod
    def register_user(signup_data: dict, device_info: dict = None, ip_address: str = None) -> dict:
        """
        Register new user with comprehensive security measures
        
        Args:
            signup_data: User registration data from frontend
            device_info: Device fingerprint information
            ip_address: User's IP address
        
        Returns:
            {success: bool, user_id: str, message: str, errors: dict}
        """
        try:
            # Step 1: Validate input data
            validation = Validators.validate_signup_data(signup_data)
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": "Validation failed",
                    "errors": validation["errors"]
                }
            
            # Step 2: Sanitize inputs
            full_name = Validators.sanitize_string(signup_data["full_name"], 100)
            email = signup_data["email"].lower().strip()
            phone = signup_data["phone"].strip()
            
            # Step 3: Check for existing user
            existing = AuthService.check_existing_user(email, phone)
            if existing["exists"]:
                return {
                    "success": False,
                    "message": "User already exists with this email or phone",
                    "errors": {"email": "Email or phone already registered"}
                }
            
            # Step 4: Hash password using PBKDF2
            password_data = EncryptionService.hash_password(signup_data["password"])
            
            # Step 5: Prepare user document structure
            now = datetime.utcnow()
            
            user_document = {
                "_id": ObjectId(),
                
                "personal_info": {
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "dob": signup_data["dob"],
                    "gender": signup_data["gender"],
                    "address": {
                        "line1": Validators.sanitize_string(signup_data["address"]["line1"], 255),
                        "line2": Validators.sanitize_string(signup_data["address"].get("line2", ""), 255),
                        "city": Validators.sanitize_string(signup_data["address"]["city"], 100),
                        "state": Validators.sanitize_string(signup_data["address"]["state"], 100),
                        "country": Validators.sanitize_string(signup_data["address"]["country"], 100),
                        "pincode": signup_data["address"]["pincode"]
                    }
                },
                
                "account_credentials": {
                    "password_hash": password_data["password_hash"],
                    "salt": password_data["salt"],
                    "last_password_change": now,
                    "two_factor_enabled": False,
                    "two_factor_method": ""
                },
                
                "kyc_status": {
                    "current_state": "not_started",
                    "completion_percent": 0,
                    "last_updated": now,
                    "reason_if_rejected": ""
                },
                
                "document_data": {
                    "submitted_docs": [],
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
                    "fraud_risk_level": "low",
                    "device_trust_score": 0,
                    "geo_risk_score": 0,
                    "previous_flags": []
                },
                
                "device_metadata": {
                    "device_id": device_info.get("device_id", "") if device_info else "",
                    "device_type": device_info.get("device_type", "") if device_info else "",
                    "os_version": device_info.get("os_version", "") if device_info else "",
                    "browser": device_info.get("browser", "") if device_info else "",
                    "screen_resolution": device_info.get("screen_resolution", "") if device_info else "",
                    "ip_address": ip_address or "",
                    "location_coords": "",
                    "is_vpn": False
                },
                
                "consent_log": [
                    {
                        "timestamp": now,
                        "requested_by": "AegisKYC Platform",
                        "purpose": "Account Registration and KYC Verification",
                        "data_shared": ["personal_info", "contact_details", "address"],
                        "approved": True
                    }
                ],
                
                "audit_trail": [
                    {
                        "event": "account_created",
                        "timestamp": now,
                        "ip": ip_address or "",
                        "device": device_info.get("device_type", "") if device_info else "",
                        "notes": "User registration completed successfully"
                    }
                ],
                
                "security": {
                    "encryption_version": "AES-256-GCM",
                    "data_checksum": "",
                    "failed_login_attempts": 0,
                    "account_locked": False,
                    "last_activity": now
                },
                
                "created_at": now,
                "updated_at": now,
                
                # Hash indexes for searchability without decryption
                "email_hash": EncryptionService.generate_checksum(email),
                "phone_hash": EncryptionService.generate_checksum(phone)
            }
            
            # Step 6: Encrypt PII data (GDPR Article 32 compliance)
            encrypted_document = EncryptionService.encrypt_pii_data(user_document)
            
            # Step 7: Generate data integrity checksum
            checksum_data = f"{full_name}{email}{phone}{signup_data['dob']}"
            encrypted_document["security"]["data_checksum"] = EncryptionService.generate_checksum(checksum_data)
            
            # Step 8: Insert into database
            result = db["Users"].insert_one(encrypted_document)
            
            # Step 9: Create initial audit log entry
            db["AuditLogs"].insert_one({
                "user_id": str(result.inserted_id),
                "event": "user_registration",
                "timestamp": now,
                "ip": ip_address or "",
                "device": device_info.get("device_type", "") if device_info else "",
                "notes": "New user account created with encrypted PII data",
                "metadata": {
                    "encryption_version": "AES-256-GCM",
                    "gdpr_compliant": True,
                    "kyc_status": "not_started"
                }
            })
            
            # Step 10: Create consent ledger entry
            db["ConsentLedger"].insert_one({
                "user_id": str(result.inserted_id),
                "timestamp": now,
                "requested_by": "AegisKYC Platform",
                "purpose": "Account Registration and KYC Verification",
                "data_shared": ["personal_info", "contact_details", "address"],
                "approved": True,
                "action": "data_collection",
                "target_institution": "AegisKYC"
            })
            
            return {
                "success": True,
                "user_id": str(result.inserted_id),
                "message": "User registered successfully with encrypted data storage",
                "kyc_status": "not_started"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Registration failed: {str(e)}",
                "errors": {"server": str(e)}
            }
    
    @staticmethod
    def login_user(email: str, password: str, device_info: dict = None, ip_address: str = None) -> dict:
        """
        Authenticate user login
        """
        try:
            # Find user by email hash
            email_hash = EncryptionService.generate_checksum(email.lower())
            user = db["Users"].find_one({"email_hash": email_hash})
            
            if not user:
                # Log failed attempt
                db["AuditLogs"].insert_one({
                    "user_id": "unknown",
                    "event": "failed_login",
                    "timestamp": datetime.utcnow(),
                    "ip": ip_address or "",
                    "device": device_info.get("device_type", "") if device_info else "",
                    "notes": f"Login attempt with non-existent email: {email}"
                })
                return {
                    "success": False,
                    "message": "Invalid email or password"
                }
            
            # Check if account is locked
            if user["security"]["account_locked"]:
                return {
                    "success": False,
                    "message": "Account is locked due to multiple failed login attempts. Please contact support."
                }
            
            # Verify password
            password_valid = EncryptionService.verify_password(
                password,
                user["account_credentials"]["password_hash"],
                user["account_credentials"]["salt"]
            )
            
            if not password_valid:
                # Increment failed attempts
                failed_attempts = user["security"]["failed_login_attempts"] + 1
                db["Users"].update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "security.failed_login_attempts": failed_attempts,
                            "security.account_locked": failed_attempts >= 5
                        }
                    }
                )
                
                # Log failed attempt
                db["AuditLogs"].insert_one({
                    "user_id": str(user["_id"]),
                    "event": "failed_login",
                    "timestamp": datetime.utcnow(),
                    "ip": ip_address or "",
                    "device": device_info.get("device_type", "") if device_info else "",
                    "notes": f"Invalid password. Failed attempts: {failed_attempts}"
                })
                
                return {
                    "success": False,
                    "message": f"Invalid email or password. {5 - failed_attempts} attempts remaining."
                }
            
            # Successful login - reset failed attempts
            now = datetime.utcnow()
            db["Users"].update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "security.failed_login_attempts": 0,
                        "security.last_activity": now
                    }
                }
            )
            
            # Log successful login
            db["AuditLogs"].insert_one({
                "user_id": str(user["_id"]),
                "event": "login",
                "timestamp": now,
                "ip": ip_address or "",
                "device": device_info.get("device_type", "") if device_info else "",
                "notes": "Successful login"
            })
            
            return {
                "success": True,
                "user_id": str(user["_id"]),
                "message": "Login successful",
                "kyc_status": user["kyc_status"]["current_state"]
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Login failed: {str(e)}"
            }
    
    @staticmethod
    def get_user_by_id(user_id: str) -> dict:
        """
        Get user details by ID (with decrypted data)
        """
        try:
            user = db["Users"].find_one({"_id": ObjectId(user_id)})
            
            if not user:
                return {
                    "success": False,
                    "message": "User not found"
                }
            
            # Decrypt PII data
            decrypted_user = EncryptionService.decrypt_pii_data(user)
            personal_info = decrypted_user.get("personal_info", {})
            
            return {
                "success": True,
                "user": {
                    "user_id": str(user["_id"]),
                    "full_name": personal_info.get("full_name", "User"),
                    "email": personal_info.get("email", ""),
                    "phone": personal_info.get("phone", ""),
                    "kyc_status": user["kyc_status"]["current_state"],
                    "created_at": str(user.get("created_at", "")),
                    "last_activity": str(user.get("security", {}).get("last_activity", ""))
                }
            }
            
        except Exception as e:
            print(f"Error in get_user_by_id: {str(e)}")  # Debug logging
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": f"Error fetching user: {str(e)}"
            }
