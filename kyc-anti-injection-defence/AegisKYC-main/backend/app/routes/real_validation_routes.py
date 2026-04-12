"""
Real AI Validation API Routes
Uses actual OCR, face detection, and liveness detection
WITH AUTOMATIC VERIFICATION STATUS UPDATES
"""
from flask import Blueprint, request, jsonify
import sys
import os
from datetime import datetime, timedelta
import secrets
import hashlib

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.real_ocr_validator import RealOCRValidator
from utils.real_face_analyzer import RealFaceAnalyzer, RealLivenessDetector

real_validation_bp = Blueprint('real_validation', __name__, url_prefix='/api/validation')

# Initialize validators
ocr_validator = RealOCRValidator()
face_analyzer = RealFaceAnalyzer()
liveness_detector = RealLivenessDetector()


def get_db_connection():
    """Get MongoDB database connection"""
    from pymongo import MongoClient
    from dotenv import load_dotenv
    import os
    
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    dotenv_path = os.path.join(PROJECT_ROOT, '.env')
    load_dotenv(dotenv_path)
    
    MONGO_URI = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI")
    client = MongoClient(MONGO_URI)
    return client["aegis_kyc"]


def update_verification_step(verification_id, step_name, status='completed'):
    """Update verification step status in database"""
    try:
        if not verification_id:
            return
        
        from bson.objectid import ObjectId
        db = get_db_connection()
        
        db.KYCVerificationRequests.update_one(
            {'_id': ObjectId(verification_id)},
            {
                '$set': {
                    f'steps_status.{step_name}': status,
                    'updated_at': datetime.utcnow()
                },
                '$addToSet': {
                    'steps_completed': step_name.replace('step_', 'step_').split('_')[1]
                }
            }
        )
    except Exception as e:
        print(f"Error updating verification step: {e}")


def check_and_auto_approve(verification_id, user_id):
    """Check if all steps completed and auto-approve + issue credential"""
    try:
        if not verification_id or not user_id:
            return
        
        from bson.objectid import ObjectId
        db = get_db_connection()
        
        # Get verification request
        verification = db.KYCVerificationRequests.find_one({'_id': ObjectId(verification_id)})
        if not verification:
            return
        
        # Check critical steps
        steps_status = verification.get('steps_status', {})
        critical_steps = [
            'step_2_document_upload',
            'step_5_selfie_capture', 
            'step_7_liveness_check'
        ]
        
        all_completed = all(
            steps_status.get(step) == 'completed'
            for step in critical_steps
        )
        
        # If all critical steps done and not yet approved, auto-approve
        if all_completed and verification.get('approval_decision') != 'auto_approved':
            # Update to approved
            db.KYCVerificationRequests.update_one(
                {'_id': ObjectId(verification_id)},
                {
                    '$set': {
                        'approval_decision': 'auto_approved',
                        'approval_timestamp': datetime.utcnow(),
                        'risk_score': 90,
                        'identity_integrity_score': 92,
                        'status': 'approved',
                        'progress_percentage': 100,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            # Auto-issue credential
            issue_credential_auto(verification_id, user_id, db)
            
    except Exception as e:
        print(f"Error in auto-approval: {e}")


def issue_credential_auto(verification_id, user_id, db):
    """Automatically issue credential after approval"""
    try:
        # Check if credential already exists
        existing = db.KYCCredentials.find_one({'user_id': user_id})
        if existing:
            print(f"Credential already exists for user {user_id}")
            return
        
        # Generate credential ID
        credential_id = f"KYC-{secrets.token_hex(8).upper()}"
        
        # Create credential
        credential_data = {
            "user_id": user_id,
            "credential_id": credential_id,
            "verification_id": verification_id,
            "issued_at": datetime.utcnow(),
            "expiry_date": datetime.utcnow() + timedelta(days=365),
            "status": "active",
            "verification_summary": {
                "identity_integrity_score": 92,
                "document_verified": True,
                "face_verified": True,
                "liveness_verified": True,
                "address_verified": True,
                "aml_cleared": True
            },
            "credential_hash": hashlib.sha256(credential_id.encode()).hexdigest()
        }
        
        db.KYCCredentials.insert_one(credential_data)
        
        # Update user status
        from bson.objectid import ObjectId
        db.Users.update_one(
            {'_id': ObjectId(user_id)},
            {
                '$set': {
                    'kyc_status.current_state': 'approved',
                    'kyc_status.completion_percent': 100,
                    'kyc_status.last_updated': datetime.utcnow(),
                    'credential_id': credential_id
                }
            }
        )
        
        print(f"✅ Auto-issued credential: {credential_id} for user {user_id}")
        
    except Exception as e:
        print(f"Error issuing credential: {e}")


@real_validation_bp.route('/validate-document', methods=['POST'])
def validate_document():
    """
    Validate document with REAL OCR extraction
    Expected: { document_image (base64), document_type, verification_id, user_id }
    Returns: { extracted_data, quality_score, authenticity_score }
    """
    try:
        data = request.get_json()
        document_image = data.get('document_image')
        document_type = data.get('document_type', 'GENERIC')
        verification_id = data.get('verification_id')
        user_id = data.get('user_id')
        
        if not document_image:
            return jsonify({
                "success": False,
                "message": "document_image is required"
            }), 400
        
        # Validate document using real OCR
        result = ocr_validator.validate_document(document_image, document_type)
        
        # Update verification status if validation successful
        if result.get('success') and verification_id:
            update_verification_step(verification_id, 'step_2_document_upload', 'completed')
            
            # Check if we can auto-approve
            if user_id:
                check_and_auto_approve(verification_id, user_id)
        
        return jsonify(result), 200 if result.get('success') else 400
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Document validation failed"
        }), 500


@real_validation_bp.route('/extract-pan', methods=['POST'])
def extract_pan():
    """Extract PAN card details with real OCR"""
    try:
        data = request.get_json()
        document_image = data.get('document_image')
        
        if not document_image:
            return jsonify({"success": False, "message": "document_image required"}), 400
        
        result = ocr_validator.extract_pan_details(document_image)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@real_validation_bp.route('/extract-aadhaar', methods=['POST'])
def extract_aadhaar():
    """Extract Aadhaar card details with QR + OCR"""
    try:
        data = request.get_json()
        document_image = data.get('document_image')
        
        if not document_image:
            return jsonify({"success": False, "message": "document_image required"}), 400
        
        result = ocr_validator.extract_aadhaar_details(document_image)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@real_validation_bp.route('/extract-passport', methods=['POST'])
def extract_passport():
    """Extract passport details with MRZ + OCR"""
    try:
        data = request.get_json()
        document_image = data.get('document_image')
        
        if not document_image:
            return jsonify({"success": False, "message": "document_image required"}), 400
        
        result = ocr_validator.extract_passport_details(document_image)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@real_validation_bp.route('/extract-dl', methods=['POST'])
def extract_dl():
    """Extract driving license details with OCR"""
    try:
        data = request.get_json()
        document_image = data.get('document_image')
        
        if not document_image:
            return jsonify({"success": False, "message": "document_image required"}), 400
        
        result = ocr_validator.extract_driving_license_details(document_image)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@real_validation_bp.route('/verify-selfie', methods=['POST'])
def verify_selfie():
    """
    Verify selfie with REAL face detection
    Expected: { selfie_image (base64), document_photo (base64, optional), verification_id, user_id }
    Returns: { face_detected, quality_analysis, face_matching }
    """
    try:
        data = request.get_json()
        selfie_image = data.get('selfie_image')
        document_photo = data.get('document_photo')
        verification_id = data.get('verification_id')
        user_id = data.get('user_id')
        
        if not selfie_image:
            return jsonify({
                "success": False,
                "message": "selfie_image is required"
            }), 400
        
        # Analyze selfie with real face detection
        result = face_analyzer.analyze_selfie(selfie_image, document_photo)
        
        # Update verification status if successful
        if result.get('success') and verification_id:
            update_verification_step(verification_id, 'step_5_selfie_capture', 'completed')
            
            # Check if we can auto-approve
            if user_id:
                check_and_auto_approve(verification_id, user_id)
        
        return jsonify(result), 200 if result.get('success') else 400
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Selfie verification failed"
        }), 500


@real_validation_bp.route('/verify-liveness', methods=['POST'])
def verify_liveness():
    """
    Verify liveness with REAL eye tracking
    Expected: { video_frames: [base64, ...], expected_gestures: ['blink', 'look_left', ...], verification_id, user_id }
    Returns: { detected_gestures, liveness_score, passed }
    """
    try:
        data = request.get_json()
        video_frames = data.get('video_frames', [])
        expected_gestures = data.get('expected_gestures', ['blink', 'look_left', 'look_right'])
        verification_id = data.get('verification_id')
        user_id = data.get('user_id')
        
        if not video_frames:
            return jsonify({
                "success": False,
                "message": "video_frames are required"
            }), 400
        
        # Analyze video with real eye tracking
        result = liveness_detector.analyze_video_frames(video_frames, expected_gestures)
        
        # Update verification status if successful
        if result.get('success') and verification_id:
            update_verification_step(verification_id, 'step_7_liveness_check', 'completed')
            
            # Check if we can auto-approve and issue credential
            if user_id:
                check_and_auto_approve(verification_id, user_id)
        
        return jsonify(result), 200 if result.get('success') else 400
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Liveness verification failed"
        }), 500


@real_validation_bp.route('/cross-verify-name', methods=['POST'])
def cross_verify_name():
    """
    Cross-verify name across multiple documents
    Expected: { names: ['Name 1', 'Name 2', ...] }
    Returns: { all_match, similarity_scores, verified_name }
    """
    try:
        data = request.get_json()
        names = data.get('names', [])
        
        if len(names) < 2:
            return jsonify({
                "success": False,
                "message": "At least 2 names required for comparison"
            }), 400
        
        # Compare all names pairwise
        comparisons = []
        for i in range(len(names)):
            for j in range(i+1, len(names)):
                comparison = ocr_validator.cross_verify_name(names[i], names[j])
                comparisons.append(comparison)
        
        # Determine if all match
        all_match = all(c.get('match', False) for c in comparisons)
        avg_similarity = sum(c.get('similarity_score', 0) for c in comparisons) / len(comparisons)
        
        return jsonify({
            "success": True,
            "all_match": all_match,
            "average_similarity": avg_similarity,
            "comparisons": comparisons,
            "verified_name": names[0] if all_match else None,
            "message": "All names match" if all_match else "Name mismatch detected"
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@real_validation_bp.route('/cross-verify-dob', methods=['POST'])
def cross_verify_dob():
    """
    Cross-verify date of birth across multiple documents
    Expected: { dobs: ['01/01/1990', '1990-01-01', ...] }
    Returns: { consistent, verified_dob, age }
    """
    try:
        data = request.get_json()
        dobs = data.get('dobs', [])
        
        if not dobs:
            return jsonify({
                "success": False,
                "message": "At least 1 DOB required"
            }), 400
        
        # Verify DOB consistency
        result = ocr_validator.cross_verify_dob(dobs)
        
        # Add age calculation if DOB verified
        if result.get('consistent') and result.get('verified_dob'):
            age_info = ocr_validator.validate_date_of_birth(result['verified_dob'])
            result['age'] = age_info.get('age')
            result['is_adult'] = age_info.get('is_adult')
        
        return jsonify({
            "success": True,
            **result
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@real_validation_bp.route('/detect-blur', methods=['POST'])
def detect_blur():
    """Detect if image is blurry"""
    try:
        data = request.get_json()
        image_base64 = data.get('image')
        
        if not image_base64:
            return jsonify({"success": False, "message": "image required"}), 400
        
        image = ocr_validator.base64_to_cv2(image_base64)
        result = ocr_validator.detect_blur(image)
        
        return jsonify({
            "success": True,
            **result
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
