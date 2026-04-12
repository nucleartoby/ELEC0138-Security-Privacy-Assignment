"""
AES-256-GCM Encryption Utilities for PII Data
Compliant with GDPR, CCPA, and Banking Security Standards
"""
import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv
import secrets

# Load .env from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
dotenv_path = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(dotenv_path)

# Master encryption key from environment (must be 32 bytes for AES-256)
MASTER_KEY = bytes.fromhex(os.getenv("ENCRYPTION_MASTER_KEY", ""))
if len(MASTER_KEY) != 32:
    raise ValueError("ENCRYPTION_MASTER_KEY must be exactly 32 bytes (256 bits)")


class EncryptionService:
    """
    Enterprise-grade encryption service using AES-256-GCM
    - AES-256-GCM for authenticated encryption
    - PBKDF2 for key derivation
    - Unique salt and nonce per encryption
    """
    
    @staticmethod
    def generate_salt(length=16):
        """Generate cryptographically secure random salt"""
        return secrets.token_bytes(length)
    
    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """
        Derive encryption key from password using PBKDF2
        100,000 iterations for enhanced security
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(password.encode())
    
    @staticmethod
    def encrypt_field(plaintext: str) -> dict:
        """
        Encrypt a single field using AES-256-GCM
        Returns: {ciphertext, nonce, tag} all base64 encoded
        """
        if not plaintext:
            return {"ciphertext": "", "nonce": "", "tag": ""}
        
        # Generate unique nonce (12 bytes for GCM)
        nonce = os.urandom(12)
        
        # Initialize AES-GCM cipher
        aesgcm = AESGCM(MASTER_KEY)
        
        # Encrypt with authenticated encryption
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        
        return {
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "version": "AES-256-GCM"
        }
    
    @staticmethod
    def decrypt_field(encrypted_data: dict) -> str:
        """
        Decrypt a field encrypted with encrypt_field
        """
        if not encrypted_data or not encrypted_data.get("ciphertext"):
            return ""
        
        try:
            ciphertext = base64.b64decode(encrypted_data["ciphertext"])
            nonce = base64.b64decode(encrypted_data["nonce"])
            
            aesgcm = AESGCM(MASTER_KEY)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            return plaintext.decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
    
    @staticmethod
    def hash_password(password: str, salt: bytes = None) -> dict:
        """
        Hash password using PBKDF2-SHA256
        Returns: {hash, salt}
        """
        if salt is None:
            salt = EncryptionService.generate_salt()
        
        password_hash = EncryptionService.derive_key(password, salt)
        
        return {
            "password_hash": base64.b64encode(password_hash).decode(),
            "salt": base64.b64encode(salt).decode()
        }
    
    @staticmethod
    def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
        """
        Verify password against stored hash
        """
        salt = base64.b64decode(stored_salt)
        password_hash = EncryptionService.derive_key(password, salt)
        stored_hash_bytes = base64.b64decode(stored_hash)
        
        return secrets.compare_digest(password_hash, stored_hash_bytes)
    
    @staticmethod
    def generate_checksum(data: str) -> str:
        """
        Generate SHA-256 checksum for data integrity verification
        """
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def encrypt_pii_data(user_data: dict) -> dict:
        """
        Encrypt all PII fields in user data
        Complies with GDPR Article 32 (Security of Processing)
        """
        encrypted_data = user_data.copy()
        
        # Encrypt personal_info fields
        if "personal_info" in encrypted_data:
            personal = encrypted_data["personal_info"]
            
            # Encrypt name, email, phone
            if personal.get("full_name"):
                personal["full_name"] = EncryptionService.encrypt_field(personal["full_name"])
            if personal.get("email"):
                personal["email"] = EncryptionService.encrypt_field(personal["email"])
            if personal.get("phone"):
                personal["phone"] = EncryptionService.encrypt_field(personal["phone"])
            if personal.get("dob"):
                personal["dob"] = EncryptionService.encrypt_field(personal["dob"])
            
            # Encrypt address
            if "address" in personal:
                addr = personal["address"]
                if addr.get("line1"):
                    addr["line1"] = EncryptionService.encrypt_field(addr["line1"])
                if addr.get("line2"):
                    addr["line2"] = EncryptionService.encrypt_field(addr["line2"])
                if addr.get("city"):
                    addr["city"] = EncryptionService.encrypt_field(addr["city"])
                if addr.get("state"):
                    addr["state"] = EncryptionService.encrypt_field(addr["state"])
                if addr.get("pincode"):
                    addr["pincode"] = EncryptionService.encrypt_field(addr["pincode"])
        
        return encrypted_data
    
    @staticmethod
    def decrypt_pii_data(encrypted_data: dict) -> dict:
        """
        Decrypt all PII fields in user data
        """
        decrypted_data = encrypted_data.copy()
        
        # Decrypt personal_info fields
        if "personal_info" in decrypted_data:
            personal = decrypted_data["personal_info"]
            
            # Decrypt name, email, phone
            if isinstance(personal.get("full_name"), dict):
                personal["full_name"] = EncryptionService.decrypt_field(personal["full_name"])
            if isinstance(personal.get("email"), dict):
                personal["email"] = EncryptionService.decrypt_field(personal["email"])
            if isinstance(personal.get("phone"), dict):
                personal["phone"] = EncryptionService.decrypt_field(personal["phone"])
            if isinstance(personal.get("dob"), dict):
                personal["dob"] = EncryptionService.decrypt_field(personal["dob"])
            
            # Decrypt address
            if "address" in personal:
                addr = personal["address"]
                if isinstance(addr.get("line1"), dict):
                    addr["line1"] = EncryptionService.decrypt_field(addr["line1"])
                if isinstance(addr.get("line2"), dict):
                    addr["line2"] = EncryptionService.decrypt_field(addr["line2"])
                if isinstance(addr.get("city"), dict):
                    addr["city"] = EncryptionService.decrypt_field(addr["city"])
                if isinstance(addr.get("state"), dict):
                    addr["state"] = EncryptionService.decrypt_field(addr["state"])
                if isinstance(addr.get("pincode"), dict):
                    addr["pincode"] = EncryptionService.decrypt_field(addr["pincode"])
        
        return decrypted_data
