"""
Cryptographically Signed KYC Credentials
Uses RSA-2048 digital signatures for tamper-proof credentials
"""
import os
import jwt
import json
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import base64
from utils.db import db

class CryptographicCredentialService:
    """
    Issue tamper-proof, cryptographically signed KYC credentials
    - RSA-2048 digital signatures
    - JWT format for portability
    - Verifiable by any organization without central authority
    """
    
    def __init__(self):
        # In production: Store private key in HSM/KMS
        self.private_key_pem = os.getenv('CREDENTIAL_PRIVATE_KEY', None)
        self.public_key_pem = os.getenv('CREDENTIAL_PUBLIC_KEY', None)
        
        if not self.private_key_pem or not self.public_key_pem:
            # Generate keys if not provided (development only)
            self._generate_keypair()
    
    def _generate_keypair(self):
        """Generate RSA-2048 keypair (development only)"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        self.private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        
        public_key = private_key.public_key()
        self.public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
        print("⚠️  WARNING: Using auto-generated keys. Set CREDENTIAL_PRIVATE_KEY in production!")
    
    def issue_signed_credential(self, user_id: str, verification_id: str, kyc_data: dict) -> dict:
        """
        Issue cryptographically signed KYC credential
        Returns: Signed JWT credential + credential_id
        """
        # Load private key
        private_key = serialization.load_pem_private_key(
            self.private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )
        
        # Prepare credential payload
        credential_payload = {
            "iss": "AegisKYC",  # Issuer
            "sub": user_id,  # Subject (user)
            "iat": datetime.utcnow(),  # Issued at
            "exp": datetime.utcnow() + timedelta(days=365),  # Expires in 1 year
            "credential_id": kyc_data.get('credential_id'),
            "verification_id": verification_id,
            "kyc_status": kyc_data.get('kyc_status', 'approved'),
            "identity_integrity_score": kyc_data.get('identity_integrity_score', 0),
            "risk_level": kyc_data.get('risk_level', 'unknown'),
            "verified_attributes": kyc_data.get('verified_attributes', []),
            "verification_date": datetime.utcnow().isoformat(),
            "credential_type": "KYC_VERIFIED_IDENTITY"
        }
        
        # Sign with RSA private key
        signed_credential = jwt.encode(
            credential_payload,
            self.private_key_pem,
            algorithm="RS256"
        )
        
        # Store credential metadata
        db["SignedCredentials"].update_one(
            {"credential_id": kyc_data.get('credential_id')},
            {
                "$set": {
                    "user_id": user_id,
                    "credential_id": kyc_data.get('credential_id'),
                    "signed_jwt": signed_credential,
                    "public_key_fingerprint": self._get_public_key_fingerprint(),
                    "issued_at": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(days=365),
                    "revoked": False,
                    "signature_algorithm": "RS256"
                }
            },
            upsert=True
        )
        
        return {
            "success": True,
            "credential_id": kyc_data.get('credential_id'),
            "signed_credential": signed_credential,
            "expires_at": (datetime.utcnow() + timedelta(days=365)).isoformat(),
            "public_key": self.public_key_pem,
            "verification_instructions": "Use the public key to verify this credential's signature"
        }
    
    def verify_credential_signature(self, signed_credential: str) -> dict:
        """
        Verify cryptographic signature of a credential
        Returns: decoded payload if valid, error if tampered
        """
        try:
            # Decode and verify signature
            payload = jwt.decode(
                signed_credential,
                self.public_key_pem,
                algorithms=["RS256"]
            )
            
            # Check if credential is revoked
            credential = db["SignedCredentials"].find_one({
                "credential_id": payload.get('credential_id')
            })
            
            if credential and credential.get('revoked'):
                return {
                    "valid": False,
                    "error": "Credential has been revoked",
                    "revoked_at": credential.get('revoked_at')
                }
            
            # Check expiration
            exp_timestamp = payload.get('exp')
            if exp_timestamp and datetime.utcfromtimestamp(exp_timestamp) < datetime.utcnow():
                return {
                    "valid": False,
                    "error": "Credential has expired",
                    "expired_at": datetime.utcfromtimestamp(exp_timestamp).isoformat()
                }
            
            return {
                "valid": True,
                "payload": payload,
                "verified_at": datetime.utcnow().isoformat(),
                "message": "Credential signature is valid and has not been tampered with"
            }
            
        except jwt.ExpiredSignatureError:
            return {"valid": False, "error": "Credential has expired"}
        except jwt.InvalidSignatureError:
            return {"valid": False, "error": "Invalid signature - credential has been tampered with"}
        except Exception as e:
            return {"valid": False, "error": f"Verification failed: {str(e)}"}
    
    def revoke_credential(self, credential_id: str, reason: str) -> dict:
        """
        Revoke a credential (user request, fraud detected, etc.)
        """
        result = db["SignedCredentials"].update_one(
            {"credential_id": credential_id},
            {
                "$set": {
                    "revoked": True,
                    "revoked_at": datetime.utcnow(),
                    "revocation_reason": reason
                }
            }
        )
        
        if result.modified_count > 0:
            # Log revocation
            db["CredentialRevocationLog"].insert_one({
                "credential_id": credential_id,
                "revoked_at": datetime.utcnow(),
                "reason": reason
            })
            
            return {"success": True, "message": "Credential revoked successfully"}
        else:
            return {"success": False, "error": "Credential not found"}
    
    def _get_public_key_fingerprint(self) -> str:
        """Generate fingerprint of public key for verification"""
        import hashlib
        fingerprint = hashlib.sha256(self.public_key_pem.encode()).hexdigest()
        return fingerprint[:16]  # First 16 chars
    
    def get_public_key_for_verification(self) -> dict:
        """
        Return public key for external organizations to verify credentials
        """
        return {
            "public_key_pem": self.public_key_pem,
            "algorithm": "RS256",
            "key_size": 2048,
            "fingerprint": self._get_public_key_fingerprint(),
            "usage": "Verify AegisKYC signed credentials"
        }
