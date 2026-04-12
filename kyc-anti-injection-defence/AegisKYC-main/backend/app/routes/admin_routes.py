"""
Admin API Routes
Handles admin dashboard data and user management
"""
from flask import Blueprint, request, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Load .env
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
dotenv_path = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(dotenv_path)

MONGO_URI = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["aegis_kyc"]


@admin_bp.route('/dashboard-data', methods=['GET'])
def get_dashboard_data():
    """
    Get comprehensive admin dashboard data
    """
    from utils.encryption import EncryptionService
    try:
        # Fetch all users
        users = list(db.Users.find())
        
        # Decrypt user personal info
        decrypted_users = []
        for user in users:
            try:
                decrypted = EncryptionService.decrypt_pii_data(user)
                decrypted['_id'] = str(user['_id'])
                decrypted_users.append(decrypted)
            except Exception as e:
                print(f"Error decrypting user {user['_id']}: {e}")
                # Add user with minimal info
                decrypted_users.append({
                    '_id': str(user['_id']),
                    'personal_info': {'full_name': 'Encrypted', 'email': 'Encrypted'},
                    'kyc_status': user.get('kyc_status', {}),
                    'created_at': user.get('created_at'),
                    'credential_id': user.get('credential_id')
                })
        
        # Fetch verifications
        verifications = list(db.KYCVerificationRequests.find())
        for ver in verifications:
            ver['_id'] = str(ver['_id'])
        
        # Fetch credentials
        credentials = list(db.KYCCredentials.find())
        for cred in credentials:
            cred['_id'] = str(cred['_id'])
        
        # Fetch audit logs (last 100)
        logs = list(db.AuditLogs.find().sort('timestamp', -1).limit(100))
        for log in logs:
            log['_id'] = str(log['_id'])
        
        # Calculate statistics
        total_users = len(users)
        verified_users = len([u for u in users if u.get('kyc_status', {}).get('current_state') == 'approved'])
        pending_verifications = len([v for v in verifications if v.get('status') in ['initiated', 'in_progress']])
        credentials_issued = len([c for c in credentials if c.get('status') == 'active'])
        
        # Calculate analytics
        registration_trend = calculate_registration_trend(users)
        kyc_distribution = calculate_kyc_distribution(users)
        
        return jsonify({
            "success": True,
            "users": decrypted_users,
            "verifications": verifications,
            "credentials": credentials,
            "logs": logs,
            "stats": {
                "totalUsers": total_users,
                "verifiedUsers": verified_users,
                "pendingVerifications": pending_verifications,
                "credentialsIssued": credentials_issued
            },
            "analytics": {
                "registrationTrend": registration_trend,
                "kycDistribution": kyc_distribution
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error fetching dashboard data: {str(e)}"
        }), 500


def calculate_registration_trend(users):
    """Calculate monthly registration trend"""
    monthly_counts = {}
    
    for user in users:
        created_at = user.get('created_at')
        if created_at:
            month_key = created_at.strftime('%b %Y')
            monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
    
    # Get last 6 months
    labels = list(monthly_counts.keys())[-6:]
    data = [monthly_counts.get(label, 0) for label in labels]
    
    return {"labels": labels, "data": data}


def calculate_kyc_distribution(users):
    """Calculate KYC status distribution"""
    approved = len([u for u in users if u.get('kyc_status', {}).get('current_state') == 'approved'])
    pending = len([u for u in users if u.get('kyc_status', {}).get('current_state') == 'not_started'])
    rejected = len([u for u in users if u.get('kyc_status', {}).get('current_state') == 'rejected'])
    in_progress = len([u for u in users if u.get('kyc_status', {}).get('current_state') == 'in_progress'])
    
    return [approved, pending, rejected, in_progress]


@admin_bp.route('/suspend-user/<user_id>', methods=['POST'])
def suspend_user(user_id):
    """Suspend a user account"""
    try:
        result = db.Users.update_one(
            {'_id': ObjectId(user_id)},
            {
                '$set': {
                    'security.account_locked': True,
                    'security.suspension_reason': 'Admin action',
                    'security.suspended_at': datetime.utcnow()
                }
            }
        )
        
        # Log the action
        db.AuditLogs.insert_one({
            'user_id': user_id,
            'event': 'account_suspended',
            'timestamp': datetime.utcnow(),
            'ip': request.remote_addr,
            'notes': 'Account suspended by admin'
        })
        
        return jsonify({
            "success": True,
            "message": "User suspended successfully"
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error suspending user: {str(e)}"
        }), 500


@admin_bp.route('/ban-user/<user_id>', methods=['POST'])
def ban_user(user_id):
    """Permanently ban a user account"""
    try:
        result = db.Users.update_one(
            {'_id': ObjectId(user_id)},
            {
                '$set': {
                    'security.account_locked': True,
                    'security.banned': True,
                    'security.ban_reason': 'Admin action - security violation',
                    'security.banned_at': datetime.utcnow()
                }
            }
        )
        
        # Revoke any active credentials
        db.KYCCredentials.update_many(
            {'user_id': user_id},
            {
                '$set': {
                    'status': 'revoked',
                    'revoked_at': datetime.utcnow(),
                    'revoke_reason': 'User banned by admin'
                }
            }
        )
        
        # Log the action
        db.AuditLogs.insert_one({
            'user_id': user_id,
            'event': 'account_banned',
            'timestamp': datetime.utcnow(),
            'ip': request.remote_addr,
            'notes': 'Account permanently banned by admin'
        })
        
        return jsonify({
            "success": True,
            "message": "User banned successfully"
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error banning user: {str(e)}"
        }), 500


@admin_bp.route('/approve-kyc/<user_id>', methods=['POST'])
def approve_kyc(user_id):
    """Manually approve a user's KYC"""
    try:
        # Update user KYC status
        db.Users.update_one(
            {'_id': ObjectId(user_id)},
            {
                '$set': {
                    'kyc_status.current_state': 'approved',
                    'kyc_status.completion_percent': 100,
                    'kyc_status.last_updated': datetime.utcnow()
                }
            }
        )
        
        # Update verification request if exists
        db.KYCVerificationRequests.update_many(
            {'user_id': user_id},
            {
                '$set': {
                    'approval_decision': 'manual_approved',
                    'approval_timestamp': datetime.utcnow(),
                    'status': 'approved'
                }
            }
        )
        
        # Log the action
        db.AuditLogs.insert_one({
            'user_id': user_id,
            'event': 'kyc_manually_approved',
            'timestamp': datetime.utcnow(),
            'ip': request.remote_addr,
            'notes': 'KYC manually approved by admin'
        })
        
        return jsonify({
            "success": True,
            "message": "KYC approved successfully"
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error approving KYC: {str(e)}"
        }), 500


@admin_bp.route('/reject-kyc/<user_id>', methods=['POST'])
def reject_kyc(user_id):
    """Manually reject a user's KYC"""
    try:
        data = request.get_json()
        reason = data.get('reason', 'Admin rejection')
        
        # Update user KYC status
        db.Users.update_one(
            {'_id': ObjectId(user_id)},
            {
                '$set': {
                    'kyc_status.current_state': 'rejected',
                    'kyc_status.reason_if_rejected': reason,
                    'kyc_status.last_updated': datetime.utcnow()
                }
            }
        )
        
        # Update verification request
        db.KYCVerificationRequests.update_many(
            {'user_id': user_id},
            {
                '$set': {
                    'approval_decision': 'rejected',
                    'status': 'rejected',
                    'rejection_reason': reason
                }
            }
        )
        
        # Log the action
        db.AuditLogs.insert_one({
            'user_id': user_id,
            'event': 'kyc_rejected',
            'timestamp': datetime.utcnow(),
            'ip': request.remote_addr,
            'notes': f'KYC rejected by admin: {reason}'
        })
        
        return jsonify({
            "success": True,
            "message": "KYC rejected successfully"
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error rejecting KYC: {str(e)}"
        }), 500


@admin_bp.route('/revoke-credential/<credential_id>', methods=['POST'])
def revoke_credential(credential_id):
    """Revoke a KYC credential"""
    try:
        data = request.get_json()
        reason = data.get('reason', 'Admin revocation')
        
        result = db.KYCCredentials.update_one(
            {'credential_id': credential_id},
            {
                '$set': {
                    'status': 'revoked',
                    'revoked_at': datetime.utcnow(),
                    'revoke_reason': reason
                }
            }
        )
        
        # Log the action
        db.AuditLogs.insert_one({
            'event': 'credential_revoked',
            'credential_id': credential_id,
            'timestamp': datetime.utcnow(),
            'ip': request.remote_addr,
            'notes': f'Credential revoked by admin: {reason}'
        })
        
        return jsonify({
            "success": True,
            "message": "Credential revoked successfully"
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error revoking credential: {str(e)}"
        }), 500


@admin_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "admin",
        "database": "connected"
    }), 200


@admin_bp.route('/perf-test', methods=['GET'])
def perf_test():
    """Run quick performance and latency checks for core subsystems.
    Returns timings for DB ping, sample query, and optional model inferences.
    """
    import time
    results = {}

    # 1) MongoDB ping
    try:
        t0 = time.perf_counter()
        pong = client.admin.command('ping')
        t1 = time.perf_counter()
        results['mongodb_ping_ms'] = round((t1 - t0) * 1000, 2)
        results['mongodb_pong'] = pong
    except Exception as e:
        results['mongodb_ping_error'] = str(e)

    # 2) Sample DB query - find one user
    try:
        t0 = time.perf_counter()
        sample = db.Users.find_one()
        t1 = time.perf_counter()
        results['db_find_one_ms'] = round((t1 - t0) * 1000, 2)
        results['db_sample_user_exists'] = sample is not None
    except Exception as e:
        results['db_find_one_error'] = str(e)

    # Create a simple test image for model tests
    import numpy as np, cv2
    test_img = np.ones((10, 10, 3), dtype=np.uint8) * 255

    # 3) OCR model timing (if available)
    try:
        from models.ocr_model import OCRModel
        ocr = OCRModel()
        t0 = time.perf_counter()
        o = ocr.extract_text(test_img)
        t1 = time.perf_counter()
        results['ocr_ms'] = round((t1 - t0) * 1000, 2)
        results['ocr_sample'] = {'lines_count': len(o.get('lines', [])) if isinstance(o.get('lines'), (list,tuple)) else 0}
    except Exception as e:
        results['ocr_error'] = str(e)

    # 4) Deepfake model timing (if available)
    try:
        from models.deepfake_model import DeepfakeModel
        dm = DeepfakeModel()
        t0 = time.perf_counter()
        out = dm.predict(test_img)
        t1 = time.perf_counter()
        results['deepfake_ms'] = round((t1 - t0) * 1000, 2)
        results['deepfake_output'] = {'probability': out.get('probability') if isinstance(out, dict) else out}
    except Exception as e:
        results['deepfake_not_available'] = str(e)

    # 5) Face matcher timing
    try:
        from models.face_matcher import FaceMatcher
        fm = FaceMatcher()
        t0 = time.perf_counter()
        cmp = fm.compare(test_img, test_img)
        t1 = time.perf_counter()
        results['face_match_ms'] = round((t1 - t0) * 1000, 2)
        results['face_match_score'] = cmp.get('match_score')
    except Exception as e:
        results['face_match_error'] = str(e)

    # 6) Tamper detector timing
    try:
        from models.document_tamper_detector import DocumentTamperDetector
        td = DocumentTamperDetector()
        t0 = time.perf_counter()
        tam = td.analyze(test_img)
        t1 = time.perf_counter()
        results['tamper_ms'] = round((t1 - t0) * 1000, 2)
        results['tamper_score'] = tam.get('tamper_score')
    except Exception as e:
        results['tamper_error'] = str(e)

    results['timestamp'] = datetime.utcnow().isoformat()

    return jsonify({'success': True, 'results': results}), 200


@admin_bp.route('/feature-proof', methods=['GET'])
def feature_proof():
    """Run a set of deterministic proofs covering security, crypto, AI, and compliance features.
    Returns structured evidence that can be displayed on the frontend proof page.
    """
    import time
    import traceback
    proof = {}
    
    try:
        # Import services with fallback
        try:
            from utils.encryption import EncryptionService
        except Exception as e:
            EncryptionService = None
            print(f"Failed to import EncryptionService: {e}")
        
        try:
            from services.cryptographic_credential_service import CryptographicCredentialService
        except Exception as e:
            CryptographicCredentialService = None
            print(f"Failed to import CryptographicCredentialService: {e}")

        # 1) AES-256-GCM encrypt/decrypt test
        try:
            if not EncryptionService:
                raise ImportError("EncryptionService not available")
            sample = "Test PII: user@example.com"
            enc = EncryptionService.encrypt_field(sample)
            dec = EncryptionService.decrypt_field(enc)
            proof['aes_256_gcm'] = {
                'encrypted': enc.get('ciphertext')[:24] + '...',
                'nonce': enc.get('nonce'),
                'version': enc.get('version'),
                'decrypted_equals': dec == sample
            }
        except Exception as e:
            proof['aes_256_gcm'] = {'error': str(e)}

        # 2) RSA-2048 sign/verify flow using CryptographicCredentialService
        try:
            if not CryptographicCredentialService:
                raise ImportError("CryptographicCredentialService not available")
            cs = CryptographicCredentialService()
            kyc_data = {'credential_id': f'KYC-{int(time.time())}', 'identity_integrity_score': 95, 'kyc_status': 'approved'}
            signed = cs.issue_signed_credential('000000000000000000000000', 'verif-sample', kyc_data)
            verify = cs.verify_credential_signature(signed['signed_credential'])
            proof['rsa_2048_signature'] = {
                'credential_id': signed.get('credential_id'),
                'signed_jwt_preview': signed.get('signed_credential')[:48] + '...',
                'public_key_fingerprint': signed.get('public_key')[:48] if signed.get('public_key') else None,
                'verify_result': verify
            }
        except Exception as e:
            proof['rsa_2048_signature'] = {'error': str(e)}

        # 3) Audit log write/read proof
        try:
            now = datetime.utcnow()
            db.AuditLogs.insert_one({'event': 'proof_run', 'details': 'feature-proof invoked', 'timestamp': now})
            recent = list(db.AuditLogs.find().sort('timestamp', -1).limit(5))
            proof['audit_logs'] = [{'event': r.get('event'), 'timestamp': r.get('timestamp').isoformat()} for r in recent]
        except Exception as e:
            proof['audit_logs'] = {'error': str(e)}

        # 4) Deepfake detection (model or analyzer)
        # Create a simple 10x10 white image for testing
        try:
            import base64, cv2, numpy as np
            # Create a small test image (10x10 white square)
            test_img = np.ones((10, 10, 3), dtype=np.uint8) * 255
            
            try:
                from models.deepfake_model import DeepfakeModel
                dm = DeepfakeModel()
                df_out = dm.predict(test_img)
            except Exception as e:
                # fallback to RealFaceAnalyzer if available
                try:
                    # Encode test image to base64 for RealFaceAnalyzer
                    _, buffer = cv2.imencode('.png', test_img)
                    img_b64 = 'data:image/png;base64,' + base64.b64encode(buffer).decode()
                    from utils.real_face_analyzer import RealFaceAnalyzer
                    ra = RealFaceAnalyzer()
                    df_out = ra.analyze_selfie(img_b64)
                except Exception as e2:
                    df_out = {'error': str(e) + ' | ' + str(e2)}

            proof['deepfake_detection'] = df_out
        except Exception as e:
            proof['deepfake_detection'] = {'error': str(e)}

        # 5) OCR proof
        try:
            from models.ocr_model import OCRModel
            import base64, cv2, numpy as np
            ocr = OCRModel()
            # Create a small test image
            test_img = np.ones((10, 10, 3), dtype=np.uint8) * 255
            o = ocr.extract_text(test_img)
            proof['ocr'] = {'lines': o.get('lines', []) if isinstance(o.get('lines'), (list,tuple)) else [], 'raw_preview': (o.get('raw_text') or '')[:80]}
        except Exception as e:
            proof['ocr'] = {'error': str(e)}

        # 6) Behavioral trust / anomaly detector
        try:
            from models.anomaly_detector import AnomalyDetector
            ad = AnomalyDetector()
            sample_features = {'typing_speed': 30.0, 'error_rate': 0.02, 'mouse_smoothness': 0.9, 'session_duration': 120}
            ad_out = ad.detect(sample_features)
            proof['behavioral_analyzer'] = ad_out
        except Exception as e:
            proof['behavioral_analyzer'] = {'error': str(e)}

        # 7) Device fingerprint demo (hash of sample device info)
        try:
            import hashlib, json
            device_info = {'user_agent': 'perf-agent', 'screen': '1920x1080', 'timezone': 'UTC+0'}
            fp = hashlib.sha256(json.dumps(device_info, sort_keys=True).encode()).hexdigest()
            proof['device_fingerprint'] = {'fingerprint': fp, 'device_info': device_info}
        except Exception as e:
            proof['device_fingerprint'] = {'error': str(e)}

        proof['timestamp'] = datetime.utcnow().isoformat()
        
        # Convert numpy types to native Python types for JSON serialization
        def convert_to_native(obj):
            """Recursively convert numpy types to native Python types"""
            import numpy as np
            if isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(item) for item in obj]
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif hasattr(np, 'bool_') and isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, (bool, np.bool)):  # np.bool is the new name
                return bool(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            return obj
        
        proof = convert_to_native(proof)
        return jsonify({'success': True, 'proof': proof}), 200
    
    except Exception as e:
        # Catch-all for any unhandled errors
        import traceback
        error_details = traceback.format_exc()
        print(f"Feature proof error: {error_details}")
        return jsonify({'success': False, 'error': str(e), 'details': error_details}), 500
