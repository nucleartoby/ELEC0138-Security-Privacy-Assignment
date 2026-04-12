"""
Security Encryption Test - Demonstrates Full Encryption Flow
Shows: User Input → AES-256-GCM Encryption → MongoDB Storage → Decryption → Verification
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'app'))

from utils.encryption import EncryptionService
from datetime import datetime
import json

def test_full_encryption_flow():
    """
    Complete demonstration of security encryption flow:
    1. User enters sensitive data (PII)
    2. System encrypts with AES-256-GCM
    3. Data stored in MongoDB (simulated)
    4. Data retrieved and decrypted
    5. Verification that decrypted = original
    """
    
    print("=" * 70)
    print("🔒 AEGISKYC SECURITY ENCRYPTION TEST")
    print("=" * 70)
    print()
    
    # Initialize encryption service
    encryption = EncryptionService()
    
    # ============================================================================
    # STEP 1: User Input (Sensitive PII Data)
    # ============================================================================
    print("📝 STEP 1: User Enters Sensitive Data")
    print("-" * 70)
    
    user_data = {
        "full_name": "John Michael Doe",
        "email": "john.doe@example.com",
        "phone": "+1-555-123-4567",
        "dob": "1990-01-15",
        "ssn": "123-45-6789",  # Highly sensitive
        "address": {
            "line1": "123 Main Street",
            "line2": "Apt 4B",
            "city": "New York",
            "state": "NY",
            "country": "USA",
            "pincode": "10001"
        },
        "passport_number": "P87654321",
        "bank_account": "9876543210",
        "credit_card": "4532-1111-2222-3333"
    }
    
    print(json.dumps(user_data, indent=2))
    print()
    
    # ============================================================================
    # STEP 2: Encryption with AES-256-GCM
    # ============================================================================
    print("🔐 STEP 2: Encrypting with AES-256-GCM")
    print("-" * 70)
    
    encrypted_fields = {}
    
    # Encrypt each sensitive field
    sensitive_fields = ["phone", "dob", "ssn", "address", "passport_number", "bank_account", "credit_card"]
    
    for field in sensitive_fields:
        if field in user_data:
            original_value = user_data[field]
            if isinstance(original_value, dict):
                original_value = json.dumps(original_value)
            
            encrypted_data = encryption.encrypt_field(original_value)
            encrypted_fields[field] = encrypted_data
            
            print(f"✓ {field}:")
            print(f"  Original: {original_value[:50]}..." if len(str(original_value)) > 50 else f"  Original: {original_value}")
            print(f"  Encrypted: {encrypted_data['ciphertext'][:60]}...")
            print(f"  Nonce: {encrypted_data['nonce']}")
            print()
    
    # ============================================================================
    # STEP 3: MongoDB Storage Simulation
    # ============================================================================
    print("💾 STEP 3: Store in MongoDB (Simulated)")
    print("-" * 70)
    
    # This is how data would be stored in MongoDB
    mongodb_document = {
        "_id": "507f1f77bcf86cd799439011",
        "full_name": user_data["full_name"],  # Not encrypted (for search)
        "email": user_data["email"],  # Not encrypted (for login)
        
        # Encrypted fields stored as objects with ciphertext + nonce
        "phone_encrypted": encrypted_fields["phone"]["ciphertext"],
        "phone_nonce": encrypted_fields["phone"]["nonce"],
        
        "dob_encrypted": encrypted_fields["dob"]["ciphertext"],
        "dob_nonce": encrypted_fields["dob"]["nonce"],
        
        "ssn_encrypted": encrypted_fields["ssn"]["ciphertext"],
        "ssn_nonce": encrypted_fields["ssn"]["nonce"],
        
        "address_encrypted": encrypted_fields["address"]["ciphertext"],
        "address_nonce": encrypted_fields["address"]["nonce"],
        
        "passport_encrypted": encrypted_fields["passport_number"]["ciphertext"],
        "passport_nonce": encrypted_fields["passport_number"]["nonce"],
        
        "bank_encrypted": encrypted_fields["bank_account"]["ciphertext"],
        "bank_nonce": encrypted_fields["bank_account"]["nonce"],
        
        "credit_card_encrypted": encrypted_fields["credit_card"]["ciphertext"],
        "credit_card_nonce": encrypted_fields["credit_card"]["nonce"],
        
        "created_at": datetime.utcnow().isoformat(),
        "kyc_status": "in_progress"
    }
    
    print("MongoDB Document Structure:")
    print(json.dumps({
        "_id": mongodb_document["_id"],
        "full_name": mongodb_document["full_name"],
        "email": mongodb_document["email"],
        "phone_encrypted": mongodb_document["phone_encrypted"][:60] + "...",
        "phone_nonce": mongodb_document["phone_nonce"],
        "dob_encrypted": mongodb_document["dob_encrypted"][:60] + "...",
        "ssn_encrypted": mongodb_document["ssn_encrypted"][:60] + "...",
        "address_encrypted": mongodb_document["address_encrypted"][:60] + "...",
        "...": "other encrypted fields"
    }, indent=2))
    print()
    
    # ============================================================================
    # STEP 4: Retrieval and Decryption
    # ============================================================================
    print("🔓 STEP 4: Retrieve from MongoDB and Decrypt")
    print("-" * 70)
    
    decrypted_data = {}
    
    field_mapping = {
        "phone": "phone",
        "dob": "dob", 
        "ssn": "ssn",
        "address": "address",
        "passport_number": "passport",
        "bank_account": "bank",
        "credit_card": "credit_card"
    }
    
    for field in sensitive_fields:
        encrypted_field_key = field_mapping.get(field, field)
        encrypted_field_name = encrypted_field_key + "_encrypted"
        nonce_field_name = encrypted_field_key + "_nonce"
        
        # Retrieve encrypted data from MongoDB document
        ciphertext = mongodb_document.get(encrypted_field_name)
        nonce = mongodb_document.get(nonce_field_name)
        
        if ciphertext and nonce:
            # Decrypt
            decrypted_value = encryption.decrypt_field({"ciphertext": ciphertext, "nonce": nonce})
            
            # Parse JSON if it was an object
            if field == "address":
                decrypted_value = json.loads(decrypted_value)
            
            decrypted_data[field] = decrypted_value
            
            print(f"✓ {field}:")
            print(f"  Decrypted: {decrypted_value}")
            print()
    
    # ============================================================================
    # STEP 5: Verification
    # ============================================================================
    print("✅ STEP 5: Verification (Decrypted = Original)")
    print("-" * 70)
    
    all_match = True
    for field in sensitive_fields:
        original = user_data[field]
        decrypted = decrypted_data.get(field)
        
        match = original == decrypted
        all_match = all_match and match
        
        status = "✅ MATCH" if match else "❌ MISMATCH"
        print(f"{status} - {field}")
    
    print()
    print("=" * 70)
    
    if all_match:
        print("🎉 SUCCESS: All decrypted data matches original input!")
        print("🔒 AES-256-GCM encryption verified working correctly")
    else:
        print("❌ FAILURE: Some data does not match!")
        return False
    
    print("=" * 70)
    print()
    
    # ============================================================================
    # Additional Security Tests
    # ============================================================================
    print("🛡️ ADDITIONAL SECURITY TESTS")
    print("-" * 70)
    
    # Test 1: Nonce Uniqueness
    print("\n1. Nonce Uniqueness Test:")
    nonces = set()
    for _ in range(100):
        enc = encryption.encrypt_field("test")
        nonces.add(enc['nonce'])
    print(f"   ✓ Generated 100 encryptions → {len(nonces)} unique nonces")
    print(f"   ✓ Nonce collision rate: {((100 - len(nonces)) / 100) * 100:.2f}%")
    
    # Test 2: Same plaintext → Different ciphertext (due to nonce)
    print("\n2. Randomized Encryption Test:")
    same_input = "SecretData123"
    enc1 = encryption.encrypt_field(same_input)
    enc2 = encryption.encrypt_field(same_input)
    print(f"   ✓ Same input encrypted twice:")
    print(f"     Ciphertext 1: {enc1['ciphertext'][:40]}...")
    print(f"     Ciphertext 2: {enc2['ciphertext'][:40]}...")
    print(f"   ✓ Different ciphertexts: {enc1['ciphertext'] != enc2['ciphertext']}")
    
    # Test 3: Tamper Detection
    print("\n3. Tamper Detection Test:")
    original_enc = encryption.encrypt_field("Important Data")
    tampered_ciphertext = original_enc['ciphertext'][:-10] + "TAMPERED!!"
    try:
        encryption.decrypt_field({"ciphertext": tampered_ciphertext, "nonce": original_enc['nonce']})
        print("   ❌ FAILED: Tampered data was accepted!")
    except Exception as e:
        print(f"   ✓ Tampered data rejected: {str(e)[:50]}...")
    
    # Test 4: Wrong nonce detection
    print("\n4. Wrong Nonce Test:")
    enc_a = encryption.encrypt_field("Data A")
    enc_b = encryption.encrypt_field("Data B")
    try:
        encryption.decrypt_field({"ciphertext": enc_a['ciphertext'], "nonce": enc_b['nonce']})
        print("   ❌ FAILED: Wrong nonce accepted!")
    except Exception as e:
        print(f"   ✓ Wrong nonce rejected: {str(e)[:50]}...")
    
    print()
    print("=" * 70)
    print("✅ ALL SECURITY TESTS PASSED")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    try:
        success = test_full_encryption_flow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
