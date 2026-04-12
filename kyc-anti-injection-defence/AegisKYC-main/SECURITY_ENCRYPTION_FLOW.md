# Security Encryption Implementation - Quick Reference

## How User Data Flows Through AegisKYC Encryption

### 1. User Signs Up (Frontend → Backend)

**Frontend:** `frontend/signup.html`
```javascript
// User enters data
const userData = {
    full_name: "John Doe",
    phone: "+1-555-123-4567",
    dob: "1990-01-15",
    ssn: "123-45-6789"
};

// Send to backend
fetch('/api/auth/signup', {
    method: 'POST',
    body: JSON.stringify(userData)
});
```

### 2. Backend Encrypts Sensitive Fields

**Backend:** `backend/app/services/auth_service.py`
```python
from utils.encryption import EncryptionService

encryption = EncryptionService()

# Encrypt sensitive fields
phone_encrypted = encryption.encrypt_field(user_data['phone'])
dob_encrypted = encryption.encrypt_field(user_data['dob'])
ssn_encrypted = encryption.encrypt_field(user_data['ssn'])

# Returns: {ciphertext: "...", nonce: "...", version: "AES-256-GCM"}
```

**Encryption Code:** `backend/app/utils/encryption.py`
```python
def encrypt_field(plaintext: str) -> dict:
    # Generate unique nonce (12 bytes for GCM)
    nonce = os.urandom(12)
    
    # Initialize AES-GCM cipher with 256-bit key
    aesgcm = AESGCM(MASTER_KEY)
    
    # Encrypt with authenticated encryption
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    
    return {
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "version": "AES-256-GCM"
    }
```

### 3. Store in MongoDB (Encrypted)

**Storage:** `backend/app/services/auth_service.py`
```python
# Store in MongoDB
db.users.insert_one({
    "_id": ObjectId(),
    "full_name": user_data['full_name'],  # Not encrypted (for search)
    "email": user_data['email'],          # Not encrypted (for login)
    
    # Encrypted fields (ciphertext + nonce stored separately)
    "phone_encrypted": phone_encrypted['ciphertext'],
    "phone_nonce": phone_encrypted['nonce'],
    
    "dob_encrypted": dob_encrypted['ciphertext'],
    "dob_nonce": dob_encrypted['nonce'],
    
    "ssn_encrypted": ssn_encrypted['ciphertext'],
    "ssn_nonce": ssn_encrypted['nonce'],
    
    "created_at": datetime.utcnow()
})
```

**MongoDB Document Example:**
```json
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "full_name": "John Doe",
  "email": "john@example.com",
  "phone_encrypted": "8MwsbQRYcHGywaElie3FdhPSQ0jMxgNvK33Mhg37xw==",
  "phone_nonce": "VXFELOmineGBh6SX",
  "ssn_encrypted": "ZOjO7DOcVjG2bWbKGTZNxz1hjPVNYst52ZkU",
  "ssn_nonce": "hZNkB1cGe6sHWs2C"
}
```

### 4. Retrieve and Decrypt

**Retrieval:** `backend/app/services/auth_service.py`
```python
# Get user from database
user = db.users.find_one({"email": "john@example.com"})

# Decrypt phone number
decrypted_phone = encryption.decrypt_field({
    "ciphertext": user['phone_encrypted'],
    "nonce": user['phone_nonce']
})
# Returns: "+1-555-123-4567"

# Decrypt SSN
decrypted_ssn = encryption.decrypt_field({
    "ciphertext": user['ssn_encrypted'],
    "nonce": user['ssn_nonce']
})
# Returns: "123-45-6789"
```

**Decryption Code:** `backend/app/utils/encryption.py`
```python
def decrypt_field(encrypted_data: dict) -> str:
    # Decode from base64
    ciphertext = base64.b64decode(encrypted_data["ciphertext"])
    nonce = base64.b64decode(encrypted_data["nonce"])
    
    # Initialize cipher
    aesgcm = AESGCM(MASTER_KEY)
    
    # Decrypt (will raise error if tampered)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    
    return plaintext.decode()
```

### 5. Send to Frontend (Decrypted for Authorized User)

**Backend Response:**
```python
return jsonify({
    "success": True,
    "user": {
        "full_name": user['full_name'],
        "email": user['email'],
        "phone": decrypted_phone,  # Decrypted only for authorized user
        "dob": decrypted_dob,
        "kyc_status": user['kyc_status']
    }
})
```

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. USER INPUT (Plaintext)                                  │
│    Phone: +1-555-123-4567                                   │
│    SSN: 123-45-6789                                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. AES-256-GCM ENCRYPTION                                   │
│    - Generate unique 96-bit nonce                           │
│    - Encrypt with 256-bit key                               │
│    - Result: {ciphertext, nonce}                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. MONGODB STORAGE                                          │
│    {                                                        │
│      phone_encrypted: "8MwsbQRYcHGy...",                    │
│      phone_nonce: "VXFELOmi...",                            │
│      ssn_encrypted: "ZOjO7DOcVjG2...",                      │
│      ssn_nonce: "hZNkB1cGe6s..."                            │
│    }                                                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. RETRIEVAL (Authorized User/Admin Only)                  │
│    - Fetch ciphertext + nonce from DB                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. DECRYPTION                                               │
│    - Use nonce + master key                                 │
│    - AES-GCM decrypts and verifies                          │
│    - Returns: +1-555-123-4567                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. VERIFICATION                                             │
│    ✅ Decrypted: +1-555-123-4567                            │
│    ✅ Original:  +1-555-123-4567                            │
│    ✅ MATCH! (100% accuracy)                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Security Features Demonstrated

### ✅ Authenticated Encryption (GCM Mode)
- **What:** AES-GCM provides both encryption and authentication
- **Why:** Detects tampering automatically
- **Test:** Modify ciphertext → Decryption fails ✅

### ✅ Unique Nonce Per Encryption
- **What:** Each encryption uses a new random 96-bit nonce
- **Why:** Same plaintext produces different ciphertexts
- **Test:** 100 encryptions = 100 unique nonces ✅

### ✅ Tamper Detection
- **What:** Any modification to ciphertext detected
- **Why:** Prevents data manipulation attacks
- **Test:** Changed 10 chars → Error: "Incorrect padding" ✅

### ✅ Nonce Validation
- **What:** Decryption fails if wrong nonce used
- **Why:** Ensures data integrity
- **Test:** Used nonce from different encryption → Failed ✅

---

## Files Involved

| File | Purpose |
|------|---------|
| `backend/app/utils/encryption.py` | Core encryption/decryption logic |
| `backend/app/services/auth_service.py` | User signup with encryption |
| `backend/app/services/identity_vault.py` | Secure PII storage |
| `tests/test_security_encryption.py` | Complete encryption flow test |
| `TEST_RESULTS.md` | Test results documentation |

---

## Run the Test

```bash
# From project root
python tests/test_security_encryption.py
```

**Expected Output:**
- ✅ 7 PII fields encrypted/decrypted
- ✅ 100% verification (decrypted = original)
- ✅ Nonce uniqueness: 100/100
- ✅ Tamper detection: Working
- ✅ Wrong nonce: Rejected

---

