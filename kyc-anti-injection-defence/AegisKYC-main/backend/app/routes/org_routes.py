from flask import Blueprint, request, jsonify, render_template
from bson import ObjectId
from datetime import datetime, timedelta
import secrets
import os
from pymongo import MongoClient
import bcrypt
import jwt

org_bp = Blueprint('organization', __name__)

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
client = MongoClient(MONGO_URI)
db = client["aegis_kyc"]

# Collections
organizations_collection = db["Organizations"]
org_kyc_requests_collection = db["OrganizationKYCRequests"]
consent_requests_collection = db["ConsentRequests"]
users_collection = db["Users"]
credentials_collection = db["KYCCredentials"]
verifications_collection = db["KYCVerificationRequests"]

# JWT Secret
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")

@org_bp.route('/organization/signup', methods=['GET'])
def org_signup_page():
    """Render organization signup page"""
    return render_template('org_signup.html')

@org_bp.route('/organization/login', methods=['GET'])
def org_login_page():
    """Render organization login page"""
    return render_template('org_login.html')

@org_bp.route('/organization/dashboard', methods=['GET'])
def org_dashboard_page():
    """Render organization dashboard page"""
    return render_template('org_dashboard.html')

@org_bp.route('/api/organization/signup', methods=['POST'])
def org_signup():
    """Handle organization signup"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = [
            'organization_name', 'organization_type', 'registration_number',
            'country', 'admin_email', 'admin_first_name', 'admin_last_name',
            'phone', 'password'
        ]
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check if organization already exists
        existing_org = organizations_collection.find_one({
            '$or': [
                {'admin_email': data['admin_email']},
                {'registration_number': data['registration_number']}
            ]
        })
        
        if existing_org:
            return jsonify({'error': 'Organization already registered with this email or registration number'}), 400
        
        # Hash password
        hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
        
        # Generate API keys
        prod_api_key = 'pk_live_' + secrets.token_hex(16)
        test_api_key = 'pk_test_' + secrets.token_hex(16)
        
        # Create organization document
        org_doc = {
            'organization_name': data['organization_name'],
            'organization_type': data['organization_type'],
            'registration_number': data['registration_number'],
            'country': data['country'],
            'admin_email': data['admin_email'],
            'admin_first_name': data['admin_first_name'],
            'admin_last_name': data['admin_last_name'],
            'phone': data['phone'],
            'password': hashed_password,
            'api_keys': {
                'production': prod_api_key,
                'test': test_api_key
            },
            'status': 'active',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'settings': {
                'webhook_url': '',
                'notification_email': data['admin_email'],
                'email_notifications': True,
                'webhook_notifications': False
            },
            'stats': {
                'total_requests': 0,
                'approved_count': 0,
                'pending_count': 0,
                'rejected_count': 0,
                'api_calls_today': 0
            }
        }
        
        result = organizations_collection.insert_one(org_doc)
        
        return jsonify({
            'message': 'Organization registered successfully',
            'organization_id': str(result.inserted_id)
        }), 201
        
    except Exception as e:
        print(f"Error in org_signup: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@org_bp.route('/api/organization/login', methods=['POST'])
def org_login():
    """Handle organization login"""
    try:
        data = request.json
        
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password required'}), 400
        
        # Find organization
        org = organizations_collection.find_one({'admin_email': data['email']})
        
        if not org:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Verify password
        if not bcrypt.checkpw(data['password'].encode('utf-8'), org['password']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check if organization is active
        if org.get('status') != 'active':
            return jsonify({'error': 'Organization account is suspended'}), 403
        
        # Generate JWT token
        token = jwt.encode({
            'org_id': str(org['_id']),
            'email': org['admin_email'],
            'exp': datetime.utcnow() + timedelta(days=7)
        }, JWT_SECRET, algorithm='HS256')
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'organization_id': str(org['_id']),
            'organization_name': org['organization_name'],
            'admin_name': f"{org['admin_first_name']} {org['admin_last_name']}"
        }), 200
        
    except Exception as e:
        print(f"Error in org_login: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@org_bp.route('/api/organization/dashboard-data', methods=['GET'])
def get_org_dashboard_data():
    """Get organization dashboard data"""
    try:
        # Extract token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        token = auth_header.split(' ')[1]
        
        # Verify token
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            org_id = decoded['org_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        # Get organization
        org = organizations_collection.find_one({'_id': ObjectId(org_id)})
        
        if not org:
            return jsonify({'error': 'Organization not found'}), 404
        
        # Get KYC requests for this organization
        requests = list(org_kyc_requests_collection.find({'organization_id': org_id}))
        
        # Calculate stats
        stats = org.get('stats', {})
        
        return jsonify({
            'organization_name': org['organization_name'],
            'admin_name': f"{org['admin_first_name']} {org['admin_last_name']}",
            'admin_email': org['admin_email'],
            'total_requests': stats.get('total_requests', 0),
            'approved_count': stats.get('approved_count', 0),
            'pending_count': stats.get('pending_count', 0),
            'rejected_count': stats.get('rejected_count', 0),
            'api_calls_today': stats.get('api_calls_today', 0),
            'api_keys': {
                'production': org['api_keys']['production'],
                'test': org['api_keys']['test']
            },
            'settings': org.get('settings', {})
        }), 200
        
    except Exception as e:
        print(f"Error in get_org_dashboard_data: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@org_bp.route('/api/organization/request-kyc', methods=['POST'])
def request_kyc():
    """Submit a KYC verification request"""
    try:
        # Extract and verify token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            org_id = decoded['org_id']
        except:
            return jsonify({'error': 'Invalid token'}), 401
        
        data = request.json
        
        # Validate required fields
        required_fields = ['user_email', 'user_first_name', 'user_last_name', 'verification_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create KYC request document
        request_doc = {
            'organization_id': org_id,
            'user_email': data['user_email'],
            'user_phone': data.get('user_phone', ''),
            'user_first_name': data['user_first_name'],
            'user_last_name': data['user_last_name'],
            'verification_type': data['verification_type'],
            'purpose': data.get('purpose', ''),
            'callback_url': data.get('callback_url', ''),
            'status': 'pending',
            'request_id': 'REQ-' + secrets.token_hex(8).upper(),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        result = org_kyc_requests_collection.insert_one(request_doc)
        
        # Update organization stats
        organizations_collection.update_one(
            {'_id': ObjectId(org_id)},
            {
                '$inc': {
                    'stats.total_requests': 1,
                    'stats.pending_count': 1
                }
            }
        )
        
        return jsonify({
            'message': 'KYC request submitted successfully',
            'request_id': request_doc['request_id'],
            'id': str(result.inserted_id)
        }), 201
        
    except Exception as e:
        print(f"Error in request_kyc: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@org_bp.route('/api/organization/verifications', methods=['GET'])
def get_verifications():
    """Get all KYC verification requests for organization"""
    try:
        # Extract and verify token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            org_id = decoded['org_id']
        except:
            return jsonify({'error': 'Invalid token'}), 401
        
        # Get all requests for this organization
        requests = list(org_kyc_requests_collection.find({'organization_id': org_id}))
        
        # Convert ObjectId to string
        for req in requests:
            req['_id'] = str(req['_id'])
            req['created_at'] = req['created_at'].isoformat() if req.get('created_at') else ''
        
        return jsonify({
            'verifications': requests,
            'total': len(requests)
        }), 200
        
    except Exception as e:
        print(f"Error in get_verifications: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@org_bp.route('/api/organization/settings', methods=['PUT'])
def update_settings():
    """Update organization settings"""
    try:
        # Extract and verify token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            org_id = decoded['org_id']
        except:
            return jsonify({'error': 'Invalid token'}), 401
        
        data = request.json
        
        # Update settings
        update_doc = {}
        if 'webhook_url' in data:
            update_doc['settings.webhook_url'] = data['webhook_url']
        if 'notification_email' in data:
            update_doc['settings.notification_email'] = data['notification_email']
        if 'email_notifications' in data:
            update_doc['settings.email_notifications'] = data['email_notifications']
        if 'webhook_notifications' in data:
            update_doc['settings.webhook_notifications'] = data['webhook_notifications']
        
        if update_doc:
            organizations_collection.update_one(
                {'_id': ObjectId(org_id)},
                {'$set': update_doc}
            )
        
        return jsonify({'message': 'Settings updated successfully'}), 200
        
    except Exception as e:
        print(f"Error in update_settings: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@org_bp.route('/api/organization/search-user', methods=['GET'])
def search_user():
    """Search for a user by Credential ID or Email"""
    try:
        # Extract and verify token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            org_id = decoded['org_id']
        except Exception as e:
            print(f"Token decode error: {str(e)}")
            return jsonify({'error': 'Invalid token'}), 401
        
        search_query = request.args.get('query', '').strip()
        
        if not search_query:
            return jsonify({'error': 'Search query required'}), 400
        
        print(f"Searching for: {search_query}")
        
        # Search by credential ID first
        credential = credentials_collection.find_one({'credential_id': search_query})
        
        print(f"Credential found: {credential}")
        
        if credential:
            user_id = credential.get('user_id')
            print(f"User ID: {user_id}")
            
            # Try to find user with ObjectId or string ID
            try:
                user = users_collection.find_one({'_id': ObjectId(user_id)})
            except:
                # If ObjectId conversion fails, try as string
                user = users_collection.find_one({'_id': user_id})
            
            print(f"User found: {user.get('email') if user else 'None'}")
            
            if user:
                # Get decrypted names
                first_name = user.get('first_name', '')
                last_name = user.get('last_name', '')
                
                # Try to decrypt if encrypted fields exist
                if user.get('encrypted_first_name'):
                    try:
                        import sys
                        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        from services.encryption_service import EncryptionService
                        encryption_service = EncryptionService()
                        
                        first_name = encryption_service.decrypt(user['encrypted_first_name'])
                        last_name = encryption_service.decrypt(user['encrypted_last_name'])
                    except Exception as e:
                        print(f"Decryption error: {str(e)}")
                        pass
                
                # Extract KYC status - handle both object and string formats
                kyc_status = user.get('kyc_status', 'pending')
                if isinstance(kyc_status, dict):
                    kyc_status = kyc_status.get('current_state', 'pending')
                
                result = {
                    'user_id': str(user['_id']),
                    'credential_id': credential['credential_id'],
                    'user': {
                        'first_name': first_name,
                        'last_name': last_name,
                        'email': user.get('email', ''),
                        'kyc_status': kyc_status
                    }
                }
                
                print(f"Returning result: {result}")
                return jsonify(result), 200
        
        # If not found by credential, search by email
        user = users_collection.find_one({'email': search_query})
        
        if user:
            # Get decrypted names
            first_name = user.get('first_name', '')
            last_name = user.get('last_name', '')
            
            # Try to decrypt if encrypted fields exist
            if user.get('encrypted_first_name'):
                try:
                    import sys
                    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    from services.encryption_service import EncryptionService
                    encryption_service = EncryptionService()
                    
                    first_name = encryption_service.decrypt(user['encrypted_first_name'])
                    last_name = encryption_service.decrypt(user['encrypted_last_name'])
                except Exception as e:
                    print(f"Decryption error: {str(e)}")
                    pass
            
            # Find credential for this user
            credential = credentials_collection.find_one({'user_id': str(user['_id'])})
            
            # Extract KYC status - handle both object and string formats
            kyc_status = user.get('kyc_status', 'pending')
            if isinstance(kyc_status, dict):
                kyc_status = kyc_status.get('current_state', 'pending')
            
            result = {
                'user_id': str(user['_id']),
                'credential_id': credential['credential_id'] if credential else None,
                'user': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': user.get('email', ''),
                    'kyc_status': kyc_status
                }
            }
            
            print(f"Returning result: {result}")
            return jsonify(result), 200
        
        return jsonify({'error': 'User not found'}), 404
        
    except Exception as e:
        print(f"Error in search_user: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

@org_bp.route('/api/organization/request-consent', methods=['POST'])
def request_consent():
    """Send consent request to user"""
    try:
        # Extract and verify token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            org_id = decoded['org_id']
        except:
            return jsonify({'error': 'Invalid token'}), 401
        
        data = request.json
        
        # Validate required fields
        if not data.get('user_id') or not data.get('purpose'):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Get organization details
        org = organizations_collection.find_one({'_id': ObjectId(org_id)})
        
        # Get user details
        try:
            user_obj_id = ObjectId(data['user_id'])
        except:
            user_obj_id = data['user_id']
        
        user = users_collection.find_one({'_id': user_obj_id})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user's name - handle both plain and encrypted formats
        first_name = user.get('first_name', '')
        last_name = user.get('last_name', '')
        user_email = user.get('email', '')
        
        # Try to decrypt if encrypted fields exist
        if user.get('encrypted_first_name') or user.get('encrypted_last_name'):
            try:
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from services.encryption_service import EncryptionService
                encryption_service = EncryptionService()
                
                if user.get('encrypted_first_name'):
                    first_name = encryption_service.decrypt(user['encrypted_first_name'])
                if user.get('encrypted_last_name'):
                    last_name = encryption_service.decrypt(user['encrypted_last_name'])
            except Exception as e:
                print(f"Decryption warning: {str(e)}")
                # Use whatever is available if decryption fails
                first_name = first_name or 'User'
                last_name = last_name or ''
        
        user_full_name = f"{first_name} {last_name}".strip() or "Unknown User"
        
        print(f"User details - Name: {user_full_name}, Email: {user_email}")
        
        # Create consent request document - store user_id as ObjectId
        consent_doc = {
            'organization_id': org_id,
            'organization_name': org['organization_name'],
            'user_id': user_obj_id,  # Store as ObjectId
            'user_name': user_full_name,
            'user_email': user_email,
            'credential_id': data.get('credential_id'),
            'purpose': data['purpose'],
            'consent_status': 'pending',
            'request_id': 'CONSENT-' + secrets.token_hex(8).upper(),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        print(f"Creating consent request for user_id: {user_obj_id}, type: {type(user_obj_id)}")
        print(f"Organization ID: {org_id}, type: {type(org_id)}")
        print(f"Organization name: {org.get('organization_name')}")
        
        result = consent_requests_collection.insert_one(consent_doc)
        print(f"Consent request created with ID: {result.inserted_id}")
        
        # Verify it was inserted
        verify = consent_requests_collection.find_one({'_id': result.inserted_id})
        if verify:
            print(f"✓ Verified consent request in database:")
            print(f"  - organization_id: {verify.get('organization_id')}")
            print(f"  - user_id: {verify.get('user_id')}")
            print(f"  - consent_status: {verify.get('consent_status')}")
        else:
            print("✗ WARNING: Could not verify consent request in database!")
        
        # Update organization stats
        organizations_collection.update_one(
            {'_id': ObjectId(org_id)},
            {
                '$inc': {
                    'stats.total_requests': 1,
                    'stats.pending_count': 1
                }
            }
        )
        
        return jsonify({
            'message': 'Consent request sent successfully',
            'request_id': consent_doc['request_id'],
            'id': str(result.inserted_id)
        }), 201
        
    except Exception as e:
        print(f"Error in request_consent: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@org_bp.route('/api/organization/consent-requests', methods=['GET'])
def get_consent_requests():
    """Get all consent requests for organization"""
    try:
        # Extract and verify token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            print("ERROR: No authorization header")
            return jsonify({'error': 'Unauthorized'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            org_id = decoded['org_id']
        except Exception as e:
            print(f"ERROR: Token decode failed: {str(e)}")
            return jsonify({'error': 'Invalid token'}), 401
        
        print(f"\n=== GET CONSENT REQUESTS ===")
        print(f"Organization ID from token: {org_id} (type: {type(org_id)})")
        
        # Count all documents in collection first
        total_in_collection = consent_requests_collection.count_documents({})
        print(f"Total documents in ConsentRequests collection: {total_in_collection}")
        
        # Try to find with the org_id
        requests = list(consent_requests_collection.find({'organization_id': org_id}).sort('created_at', -1))
        print(f"Found {len(requests)} consent requests for organization_id: {org_id}")
        
        # If none found, list all to see what org_ids exist
        if len(requests) == 0 and total_in_collection > 0:
            print("WARNING: No requests found for this org_id. Listing all org_ids in collection:")
            all_requests = list(consent_requests_collection.find({}, {'organization_id': 1, 'organization_name': 1}))
            for req in all_requests:
                print(f"  - org_id: {req.get('organization_id')} (type: {type(req.get('organization_id'))}), name: {req.get('organization_name')}")
        
        # Convert ObjectId to string and handle all fields properly
        for req in requests:
            req['_id'] = str(req['_id'])
            
            # Handle user_id ObjectId
            if isinstance(req.get('user_id'), ObjectId):
                req['user_id'] = str(req['user_id'])
            
            # Handle datetime objects
            if req.get('created_at'):
                req['created_at'] = req['created_at'].isoformat() if hasattr(req['created_at'], 'isoformat') else str(req['created_at'])
            if req.get('updated_at'):
                req['updated_at'] = req['updated_at'].isoformat() if hasattr(req['updated_at'], 'isoformat') else str(req['updated_at'])
            
            print(f"  Request: {req.get('request_id')} | User: {req.get('user_name')} | Status: {req.get('consent_status')}")
        
        print(f"Returning {len(requests)} requests to frontend")
        
        return jsonify({
            'requests': requests,
            'total': len(requests)
        }), 200
        
    except Exception as e:
        print(f"Error in get_consent_requests: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@org_bp.route('/api/organization/fix-consent-names', methods=['POST'])
def fix_consent_names():
    """Fix missing user names in existing consent requests"""
    try:
        # Extract and verify token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            org_id = decoded['org_id']
        except:
            return jsonify({'error': 'Invalid token'}), 401
        
        print(f"\n=== FIXING CONSENT REQUEST NAMES ===")
        print(f"Organization ID: {org_id}")
        
        # Get all consent requests for this organization
        requests = list(consent_requests_collection.find({'organization_id': org_id}))
        print(f"Total requests for this org: {len(requests)}")
        
        # Also check total users in database
        total_users = users_collection.count_documents({})
        print(f"Total users in database: {total_users}")
        
        fixed_count = 0
        for req in requests:
            user_id = req.get('user_id')
            current_name = req.get('user_name', '')
            
            # Fix if name is missing, empty, or "Unknown User"
            if not current_name or current_name.strip() == '' or current_name.strip() == 'Unknown User':
                print(f"Fixing request {req.get('request_id')} (current: '{current_name}')...")
                print(f"  User ID: {user_id} (type: {type(user_id)})")
                
                # Get user - try both ObjectId and string formats
                user = None
                if isinstance(user_id, ObjectId):
                    user = users_collection.find_one({'_id': user_id})
                else:
                    # Try as ObjectId first
                    try:
                        user = users_collection.find_one({'_id': ObjectId(user_id)})
                    except:
                        # If that fails, try as string
                        user = users_collection.find_one({'_id': user_id})
                
                if user:
                    print(f"  User found in database")
                    print(f"  All user fields: {list(user.keys())}")
                    
                    # Get user details
                    first_name = user.get('first_name', '')
                    last_name = user.get('last_name', '')
                    email = user.get('email', '')
                    
                    print(f"  Raw fields - first: '{first_name}', last: '{last_name}', email: '{email}'")
                    print(f"  Encrypted fields - first: {bool(user.get('encrypted_first_name'))}, last: {bool(user.get('encrypted_last_name'))}")
                    
                    # Show all encrypted field values (hashed, not full value)
                    if user.get('encrypted_first_name'):
                        print(f"  encrypted_first_name exists (length: {len(user.get('encrypted_first_name'))})")
                    if user.get('encrypted_last_name'):
                        print(f"  encrypted_last_name exists (length: {len(user.get('encrypted_last_name'))})")
                    
                    # Try to decrypt if encrypted
                    if user.get('encrypted_first_name') or user.get('encrypted_last_name'):
                        try:
                            import sys
                            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                            from services.encryption_service import EncryptionService
                            encryption_service = EncryptionService()
                            
                            if user.get('encrypted_first_name'):
                                first_name = encryption_service.decrypt(user['encrypted_first_name'])
                                print(f"  Decrypted first name: '{first_name}'")
                            if user.get('encrypted_last_name'):
                                last_name = encryption_service.decrypt(user['encrypted_last_name'])
                                print(f"  Decrypted last name: '{last_name}'")
                        except Exception as e:
                            print(f"  Decryption error: {str(e)}")
                            first_name = first_name or 'User'
                            last_name = last_name or ''
                    
                    user_full_name = f"{first_name} {last_name}".strip() or "Unknown User"
                    print(f"  Final name: '{user_full_name}', email: '{email}'")
                    
                    # Update the consent request
                    result = consent_requests_collection.update_one(
                        {'_id': req['_id']},
                        {
                            '$set': {
                                'user_name': user_full_name,
                                'user_email': email
                            }
                        }
                    )
                    
                    if result.modified_count > 0:
                        print(f"  ✓ Updated successfully")
                        fixed_count += 1
                    else:
                        print(f"  ✗ No changes made (values might be the same)")
                else:
                    print(f"  ✗ User not found in database!")
        
        print(f"Fixed {fixed_count} consent requests")
        
        return jsonify({
            'message': f'Fixed {fixed_count} consent requests',
            'fixed_count': fixed_count
        }), 200
        
    except Exception as e:
        print(f"Error in fix_consent_names: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@org_bp.route('/api/organization/test-populate-verification-data/<user_id>', methods=['POST'])
def test_populate_verification_data(user_id):
    """TEST ENDPOINT: Populate face and video verification data for testing"""
    try:
        from datetime import datetime
        
        # Create mock face verification data
        face_verification_collection = db['FaceVerification']
        face_data = {
            'user_id': user_id,
            'verification_id': 'test_verification',
            'timestamp': datetime.utcnow(),
            'selfie_image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',  # 1x1 red pixel
            'liveness_check': {
                'score': 95.5,
                'micro_blinks_detected': True,
                'facial_twitches_detected': True,
                'head_sway_natural': True,
                'deepfake_score': 2.1
            },
            'face_matching': {
                'score': 91.0,
                'face_to_document_match': True,
                'confidence_level': 'high'
            },
            'overall_score': 93.2,
            'verification_passed': True
        }
        face_verification_collection.insert_one(face_data)
        
        # Create mock video verification data
        video_verification_collection = db['VideoVerification']
        video_data = {
            'user_id': user_id,
            'verification_id': 'test_verification',
            'timestamp': datetime.utcnow(),
            'video_data': 'data:video/mp4;base64,AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAAu1tZGF0',  # minimal video
            'lipsync_score': 92.5,
            'deepfake_score': 96.8,
            'quality_score': 88.3,
            'overall_score': 92.5,
            'verification_passed': True
        }
        video_verification_collection.insert_one(video_data)
        
        return jsonify({
            'success': True,
            'message': 'Test verification data populated',
            'user_id': user_id
        }), 200
        
    except Exception as e:
        print(f"Error populating test data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@org_bp.route('/api/organization/kyc-details/<request_id>', methods=['GET'])
def get_kyc_details(request_id):
    """Get KYC details for a consent request (only if approved)"""
    try:
        # Extract and verify token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            org_id = decoded['org_id']
        except:
            return jsonify({'error': 'Invalid token'}), 401
        
        # Find consent request
        consent_req = consent_requests_collection.find_one({
            '_id': ObjectId(request_id),
            'organization_id': org_id
        })
        
        if not consent_req:
            return jsonify({'error': 'Request not found'}), 404
        
        # Check if consent is approved
        if consent_req.get('consent_status') != 'approved':
            return jsonify({'error': 'Consent not approved yet'}), 403
        
        # Get user details
        user = users_collection.find_one({'_id': ObjectId(consent_req['user_id'])})
        
        user_id_str = str(consent_req['user_id'])
        user_id_obj = consent_req['user_id']
        
        # Get the most recent verification request for this user - try both ObjectId and string
        verification = verifications_collection.find_one(
            {'user_id': user_id_obj},
            sort=[('created_at', -1)]
        )
        
        if not verification:
            # Try with string user_id
            verification = verifications_collection.find_one(
                {'user_id': user_id_str},
                sort=[('created_at', -1)]
            )
        
        print(f"Found verification: {verification.get('_id') if verification else 'None'}")
        print(f"Searched with user_id ObjectId: {user_id_obj} and string: {user_id_str}")
        
        # Get credential
        credential = credentials_collection.find_one({'credential_id': consent_req.get('credential_id')})
        
        # Get all documents - try multiple approaches
        documents_collection = db['DocumentAnalysis']
        documents = []
        
        if verification:
            # Try verification_id as string
            documents = list(documents_collection.find({
                'verification_id': str(verification['_id'])
            }).sort('uploaded_at', -1))
            
            if not documents:
                # Try user_id with ObjectId
                documents = list(documents_collection.find({
                    'user_id': user_id_obj
                }).sort('uploaded_at', -1))
            
            if not documents:
                # Try user_id as string
                documents = list(documents_collection.find({
                    'user_id': user_id_str
                }).sort('uploaded_at', -1))
                
            print(f"Found {len(documents)} documents for verification/user")
        else:
            # No verification found, try user_id directly (both formats)
            documents = list(documents_collection.find({
                'user_id': user_id_obj
            }).sort('uploaded_at', -1))
            
            if not documents:
                documents = list(documents_collection.find({
                    'user_id': user_id_str
                }).sort('uploaded_at', -1))
            
            print(f"Found {len(documents)} documents for user (no verification found)")
        
        # Get face verification data for the most recent verification
        face_verification_collection = db['FaceVerification']
        face_verification = None
        
        # Debug: Check what's in the collection
        total_face_records = face_verification_collection.count_documents({})
        print(f"Total FaceVerification records in DB: {total_face_records}")
        if total_face_records > 0:
            sample_face = face_verification_collection.find_one()
            print(f"Sample FaceVerification record user_id type: {type(sample_face.get('user_id'))}")
            print(f"Sample FaceVerification record user_id value: {sample_face.get('user_id')}")
        
        if verification:
            # Try with verification_id as string
            face_verification = face_verification_collection.find_one(
                {'verification_id': str(verification['_id'])},
                sort=[('timestamp', -1)]
            )
            print(f"Tried verification_id: {str(verification['_id'])}, found: {face_verification is not None}")
        
        if not face_verification:
            # Try with user_id as ObjectId
            face_verification = face_verification_collection.find_one(
                {'user_id': user_id_obj},
                sort=[('timestamp', -1)]
            )
            print(f"Tried user_id (ObjectId): {user_id_obj}, found: {face_verification is not None}")
        
        if not face_verification:
            # Try with user_id as string
            face_verification = face_verification_collection.find_one(
                {'user_id': user_id_str},
                sort=[('timestamp', -1)]
            )
            print(f"Tried user_id (string): {user_id_str}, found: {face_verification is not None}")
        
        # Get video verification data for the most recent verification
        video_verification_collection = db['VideoVerification']
        video_verification = None
        
        # Debug: Check what's in the collection
        total_video_records = video_verification_collection.count_documents({})
        print(f"Total VideoVerification records in DB: {total_video_records}")
        if total_video_records > 0:
            sample_video = video_verification_collection.find_one()
            print(f"Sample VideoVerification record user_id type: {type(sample_video.get('user_id'))}")
            print(f"Sample VideoVerification record user_id value: {sample_video.get('user_id')}")
        
        if verification:
            # Try with verification_id as string
            video_verification = video_verification_collection.find_one(
                {'verification_id': str(verification['_id'])},
                sort=[('timestamp', -1)]
            )
            print(f"Tried verification_id: {str(verification['_id'])}, found: {video_verification is not None}")
        
        if not video_verification:
            # Try with user_id as ObjectId
            video_verification = video_verification_collection.find_one(
                {'user_id': user_id_obj},
                sort=[('timestamp', -1)]
            )
            print(f"Tried user_id (ObjectId): {user_id_obj}, found: {video_verification is not None}")
        
        if not video_verification:
            # Try with user_id as string
            video_verification = video_verification_collection.find_one(
                {'user_id': user_id_str},
                sort=[('timestamp', -1)]
            )
            print(f"Tried user_id (string): {user_id_str}, found: {video_verification is not None}")
        
        print(f"FINAL - Face verification: {face_verification is not None}")
        print(f"FINAL - Video verification: {video_verification is not None}")
        
        # Prepare response - decrypt sensitive data if needed
        try:
            # Try to import and use encryption service
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from services.encryption_service import EncryptionService
            encryption_service = EncryptionService()
            
            first_name = encryption_service.decrypt(user['encrypted_first_name']) if user.get('encrypted_first_name') else user.get('first_name', '')
            last_name = encryption_service.decrypt(user['encrypted_last_name']) if user.get('encrypted_last_name') else user.get('last_name', '')
        except:
            # Fallback to plain text if encryption service not available
            first_name = user.get('first_name', '')
            last_name = user.get('last_name', '')
        
        # Extract KYC status - handle both object and string formats
        kyc_status_raw = user.get('kyc_status', 'pending')
        if isinstance(kyc_status_raw, dict):
            kyc_status = kyc_status_raw.get('current_state', 'pending')
        else:
            kyc_status = kyc_status_raw
        
        # Prepare documents array from DocumentAnalysis collection
        documents_data = []
        for doc in documents:
            documents_data.append({
                'document_type': doc.get('document_type', 'Unknown'),
                'category': doc.get('category', 'supporting'),
                'front_image': doc.get('front_image_data', doc.get('front_image', '')),
                'back_image': doc.get('back_image_data', doc.get('back_image', '')),
                'uploaded_at': doc.get('uploaded_at').isoformat() if doc.get('uploaded_at') else '',
                'authenticity_score': doc.get('authenticity_score', 0),
                'verification_status': doc.get('verification_status', 'pending'),
                'analysis_results': doc.get('analysis_results', {})
            })
        
        # Prepare verification details with all scores
        verification_data = {}
        if verification:
            print(f"Building verification data from verification record:")
            print(f"  - Status: {verification.get('status')}")
            print(f"  - Steps completed: {len(verification.get('steps_completed', []))}/10")
            print(f"  - Identity integrity score: {verification.get('identity_integrity_score', 0)}")
            
            verification_data = {
                'verification_id': str(verification.get('_id', '')),
                'status': verification.get('status', 'in_progress'),
                'identity_integrity_score': verification.get('identity_integrity_score', 0),
                'document_authenticity_score': verification.get('document_authenticity_score', 0),
                'face_match_score': verification.get('face_match_score', 0),
                'aml_risk_score': verification.get('aml_risk_score', 0),
                'risk_level': verification.get('risk_level', 'unknown'),
                'completion_percentage': (len(verification.get('steps_completed', [])) / 10) * 100,
                'current_step': verification.get('current_step', 0),
                'steps_completed': verification.get('steps_completed', [])
            }
        elif credential:
            print(f"No active verification found, using credential data")
            # Fallback to credential data
            verification_summary = credential.get('verification_summary', {})
            verification_data = {
                'verification_id': credential.get('credential_id'),
                'status': credential.get('status', 'active'),
                'identity_integrity_score': verification_summary.get('identity_integrity_score', 0),
                'completion_percentage': 100
            }
        else:
            print(f"WARNING: No verification or credential data found!")
            verification_data = {
                'verification_id': 'N/A',
                'status': 'not_started',
                'identity_integrity_score': 0,
                'completion_percentage': 0
            }
        
        # Add face verification details (selfie and liveness scores)
        face_data = {}
        if face_verification:
            face_data = {
                'selfie_image': face_verification.get('selfie_image', ''),
                'liveness_score': face_verification.get('liveness_check', {}).get('score', 0),
                'face_match_score': face_verification.get('face_matching', {}).get('score', 0),
                'overall_score': face_verification.get('overall_score', 0),
                'deepfake_score': face_verification.get('liveness_check', {}).get('deepfake_score', 0),
                'verification_passed': face_verification.get('verification_passed', False)
            }
        
        # Add video verification details
        video_data = {}
        if video_verification:
            video_data = {
                'video_data': video_verification.get('video_data', ''),
                'lipsync_score': video_verification.get('lipsync_score', 0),
                'deepfake_score': video_verification.get('deepfake_score', 0),
                'quality_score': video_verification.get('quality_score', 0),
                'overall_score': video_verification.get('overall_score', 0)
            }
        
        response_data = {
            'user': {
                'first_name': first_name,
                'last_name': last_name,
                'email': user.get('email', ''),
                'kyc_status': kyc_status
            },
            'credential_id': consent_req.get('credential_id'),
            'verification': verification_data,
            'face_verification': face_data,
            'video_verification': video_data,
            'documents': documents_data
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"Error in get_kyc_details: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500
