"""
Authentication Routes
Handles signup and login endpoints
"""
from flask import Blueprint, request, jsonify
import sys
import os
from bson import ObjectId
from pymongo import MongoClient

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# MongoDB connection for consent requests
MONGO_URI = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["aegis_kyc"]


@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    User Registration Endpoint
    
    Expected JSON:
    {
        "full_name": "string",
        "email": "string",
        "phone": "string",
        "dob": "YYYY-MM-DD",
        "gender": "string",
        "address": {
            "line1": "string",
            "line2": "string",
            "city": "string",
            "state": "string",
            "country": "string",
            "pincode": "string"
        },
        "password": "string"
    }
    """
    try:
        # Get JSON data
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "message": "No data provided"
            }), 400
        
        # Get device info from headers
        device_info = {
            "device_type": "web",
            "device_id": request.headers.get('X-Device-ID', ''),
            "os_version": request.headers.get('User-Agent', ''),
            "browser": request.headers.get('User-Agent', ''),
            "screen_resolution": request.headers.get('X-Screen-Resolution', '')
        }
        
        # Get IP address
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        # Register user
        result = AuthService.register_user(
            signup_data=data,
            device_info=device_info,
            ip_address=ip_address
        )
        
        if result["success"]:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}"
        }), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    User Login Endpoint
    
    Expected JSON:
    {
        "email": "string",
        "password": "string"
    }
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({
                "success": False,
                "message": "Email and password are required"
            }), 400
        
        # Get device info from headers
        device_info = {
            "device_type": "web",
            "device_id": request.headers.get('X-Device-ID', ''),
            "os_version": request.headers.get('User-Agent', ''),
            "browser": request.headers.get('User-Agent', '')
        }
        
        # Get IP address
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        # Authenticate user
        result = AuthService.login_user(
            email=data['email'],
            password=data['password'],
            device_info=device_info,
            ip_address=ip_address
        )
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 401
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}"
        }), 500


@auth_bp.route('/user/<user_id>', methods=['GET'])
def get_user(user_id):
    """
    Get User Details Endpoint
    Returns decrypted user information
    """
    try:
        from bson import ObjectId
        from services.auth_service import AuthService
        
        # Fetch user from database
        result = AuthService.get_user_by_id(user_id)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 404
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}"
        }), 500


@auth_bp.route('/user/consent-requests/<user_id>', methods=['GET'])
def get_consent_requests(user_id):
    """Get all consent requests for a user"""
    try:
        print(f"\n=== USER CONSENT REQUESTS REQUEST ===")
        print(f"User ID from URL: {user_id}")
        
        consent_requests_collection = mongo_db['ConsentRequests']
        
        # Try to convert to ObjectId, fallback to string
        try:
            query_user_id = ObjectId(user_id)
            print(f"Converted to ObjectId: {query_user_id}")
        except:
            query_user_id = user_id
            print(f"Using as string: {query_user_id}")
        
        print(f"Searching consent requests for user_id: {query_user_id}, type: {type(query_user_id)}")
        
        # Check total documents in collection
        total_docs = consent_requests_collection.count_documents({})
        print(f"Total documents in ConsentRequests collection: {total_docs}")
        
        # Find all consent requests for this user
        requests = list(consent_requests_collection.find({'user_id': query_user_id}))
        print(f"Found {len(requests)} consent requests for this user")
        
        # If none found, show all user_ids in collection for debugging
        if len(requests) == 0 and total_docs > 0:
            print("WARNING: No requests found. All user_ids in collection:")
            all_user_ids = consent_requests_collection.distinct('user_id')
            for uid in all_user_ids:
                print(f"  - {uid} (type: {type(uid)})")
        
        # Convert ObjectId to string for JSON serialization
        for req in requests:
            req['_id'] = str(req['_id'])
            if isinstance(req.get('user_id'), ObjectId):
                req['user_id'] = str(req['user_id'])
            if isinstance(req.get('organization_id'), ObjectId):
                req['organization_id'] = str(req['organization_id'])
            # Convert datetime to string
            if 'created_at' in req:
                req['created_at'] = req['created_at'].isoformat()
            if 'updated_at' in req:
                req['updated_at'] = req['updated_at'].isoformat()
        
        return jsonify({
            "success": True,
            "requests": requests
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error fetching consent requests: {str(e)}"
        }), 500


@auth_bp.route('/user/consent-response', methods=['POST'])
def consent_response():
    """Handle user's consent approval or rejection"""
    try:
        from datetime import datetime
        
        data = request.json
        request_id = data.get('request_id')
        status = data.get('status')  # 'approved' or 'rejected'
        
        if not request_id or not status:
            return jsonify({
                "success": False,
                "message": "Request ID and status are required"
            }), 400
            
        if status not in ['approved', 'rejected']:
            return jsonify({
                "success": False,
                "message": "Status must be 'approved' or 'rejected'"
            }), 400
        
        consent_requests_collection = mongo_db['ConsentRequests']
        
        # Try to find by ObjectId first, then by string
        consent_request = None
        try:
            consent_request = consent_requests_collection.find_one({'_id': ObjectId(request_id)})
        except:
            consent_request = consent_requests_collection.find_one({'_id': request_id})
        
        if not consent_request:
            # Try finding by request_id field
            consent_request = consent_requests_collection.find_one({'request_id': request_id})
            
        if not consent_request:
            return jsonify({
                "success": False,
                "message": "Consent request not found"
            }), 404
        
        # Update consent status
        update_result = consent_requests_collection.update_one(
            {'_id': consent_request['_id']},
            {
                '$set': {
                    'consent_status': status,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        if update_result.modified_count > 0:
            return jsonify({
                "success": True,
                "message": f"Consent request {status}",
                "status": status
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Failed to update consent request"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error processing consent: {str(e)}"
        }), 500


@auth_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "auth",
        "encryption": "AES-256-GCM",
        "compliance": ["GDPR", "CCPA", "SOC2"]
    }), 200

