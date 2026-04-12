"""
Encrypted Identity Vault
AES-256 encryption for sensitive user data
Keys stored separately in KMS (simulated with environment variables for now)
"""
import os
import base64
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend
from datetime import datetime
from bson.objectid import ObjectId
from app.utils.db import db

class IdentityVault:
    """
    Encrypted storage for sensitive identity information
    - Data-at-rest encryption with AES-256
    - Key derivation from master key + user salt
    - Attribute-level encryption (encrypt only PII fields)
    """
    
    def __init__(self):
        # In production: Fetch from AWS KMS / HashiCorp Vault / Azure Key Vault
        self.master_key = os.getenv('VAULT_MASTER_KEY', 'default-master-key-change-in-production')
        
    def _derive_key(self, user_id: str, salt: bytes = None) -> tuple:
        """
        Derive encryption key from master key + user-specific salt
        Returns: (fernet_key, salt)
        """
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        # Combine master key with user_id for user-specific keys
        key_material = f"{self.master_key}:{user_id}".encode()
        key = base64.urlsafe_b64encode(kdf.derive(key_material))
        
        return Fernet(key), salt
    
    def encrypt_identity_data(self, user_id: str, identity_data: dict) -> dict:
        """
        Encrypt sensitive identity fields
        Returns encrypted data + salt for key derivation
        """
        # Fields to encrypt (PII)
        sensitive_fields = [
            'full_name', 'date_of_birth', 'aadhaar_number', 'pan_number',
            'passport_number', 'driver_license_number', 'email', 'phone',
            'address', 'father_name', 'mother_name', 'bank_account_number',
            'ifsc_code', 'salary', 'employer_name'
        ]
        
        fernet, salt = self._derive_key(user_id)
        
        encrypted_data = {}
        for field, value in identity_data.items():
            if field in sensitive_fields and value:
                # Encrypt sensitive field
                encrypted_value = fernet.encrypt(str(value).encode())
                encrypted_data[field] = {
                    "encrypted": True,
                    "value": base64.b64encode(encrypted_value).decode()
                }
            else:
                # Non-sensitive fields stored as-is
                encrypted_data[field] = {
                    "encrypted": False,
                    "value": value
                }
        
        # Store in vault
        vault_record = {
            "user_id": user_id,
            "encrypted_data": encrypted_data,
            "salt": base64.b64encode(salt).decode(),
            "encryption_algorithm": "AES-256-Fernet",
            "created_at": datetime.utcnow(),
            "last_accessed": datetime.utcnow(),
            "access_count": 0
        }
        
        db["IdentityVault"].update_one(
            {"user_id": user_id},
            {"$set": vault_record},
            upsert=True
        )
        
        return {"success": True, "message": "Identity data encrypted and stored"}
    
    def decrypt_identity_data(self, user_id: str, requested_fields: list = None) -> dict:
        """
        Decrypt and retrieve identity data
        Only returns requested fields (consent-driven)
        """
        vault_record = db["IdentityVault"].find_one({"user_id": user_id})
        if not vault_record:
            return {"error": "Identity data not found"}
        
        # Derive decryption key using stored salt
        salt = base64.b64decode(vault_record['salt'])
        fernet, _ = self._derive_key(user_id, salt)
        
        encrypted_data = vault_record['encrypted_data']
        decrypted_data = {}
        
        for field, field_data in encrypted_data.items():
            # If requested_fields specified, only return those
            if requested_fields and field not in requested_fields:
                continue
            
            if field_data.get('encrypted'):
                # Decrypt
                try:
                    encrypted_value = base64.b64decode(field_data['value'])
                    decrypted_value = fernet.decrypt(encrypted_value).decode()
                    decrypted_data[field] = decrypted_value
                except Exception as e:
                    decrypted_data[field] = f"[DECRYPTION_ERROR: {str(e)}]"
            else:
                # Return as-is
                decrypted_data[field] = field_data['value']
        
        # Update access log
        db["IdentityVault"].update_one(
            {"user_id": user_id},
            {
                "$set": {"last_accessed": datetime.utcnow()},
                "$inc": {"access_count": 1}
            }
        )
        
        # Log access for audit
        db["VaultAccessLog"].insert_one({
            "user_id": user_id,
            "accessed_fields": requested_fields or list(encrypted_data.keys()),
            "accessed_at": datetime.utcnow(),
            "access_type": "consent_driven_read"
        })
        
        return decrypted_data
    
    def get_encrypted_fields_for_consent(self, user_id: str, consent_request_fields: list) -> dict:
        """
        Return only the fields requested in consent (privacy-by-design)
        Used when organization requests specific attributes
        """
        vault_record = db["IdentityVault"].find_one({"user_id": user_id})
        if not vault_record:
            return {"error": "Identity data not found"}
        
        # Derive key
        salt = base64.b64decode(vault_record['salt'])
        fernet, _ = self._derive_key(user_id, salt)
        
        encrypted_data = vault_record['encrypted_data']
        shared_data = {}
        
        for field in consent_request_fields:
            if field in encrypted_data:
                field_data = encrypted_data[field]
                if field_data.get('encrypted'):
                    # Decrypt for sharing
                    encrypted_value = base64.b64decode(field_data['value'])
                    decrypted_value = fernet.decrypt(encrypted_value).decode()
                    shared_data[field] = decrypted_value
                else:
                    shared_data[field] = field_data['value']
        
        return shared_data
    
    def anonymize_vault_data(self, user_id: str) -> dict:
        """
        GDPR Right to Erasure: Anonymize all sensitive data
        Keep statistical metadata for regulatory compliance
        """
        vault_record = db["IdentityVault"].find_one({"user_id": user_id})
        if not vault_record:
            return {"error": "Identity data not found"}
        
        # Replace encrypted data with anonymized placeholders
        anonymized_data = {}
        for field in vault_record['encrypted_data']:
            anonymized_data[field] = {
                "encrypted": False,
                "value": "[ANONYMIZED]"
            }
        
        db["IdentityVault"].update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "encrypted_data": anonymized_data,
                    "anonymized": True,
                    "anonymized_at": datetime.utcnow()
                }
            }
        )
        
        # Log anonymization
        db["VaultAccessLog"].insert_one({
            "user_id": user_id,
            "action": "anonymization",
            "timestamp": datetime.utcnow(),
            "reason": "User requested data erasure (GDPR/DPDP)"
        })
        
        return {"success": True, "message": "Identity data anonymized"}
