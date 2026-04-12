from pymongo import MongoClient
import os
from dotenv import load_dotenv
from bson.objectid import ObjectId

load_dotenv()
client = MongoClient(os.getenv('MONGO_URL'))
db = client['aegis_kyc']

# Get the consent request
consent = db['ConsentRequests'].find_one({'consent_request_id': 'CONSENT-364F5467BCAC22F0'})
if consent:
    print(f"Consent user_id: {consent.get('user_id')}")
    
    # Get latest verification
    verification = db['KYCVerificationRequests'].find_one(
        {'user_id': consent.get('user_id')},
        sort=[('created_at', -1)]
    )
    if verification:
        print(f"Latest verification _id: {verification.get('_id')}")
        
        # Get face verification
        face = db['FaceVerification'].find_one()
        if face:
            print(f"Face record verification_id: {face.get('verification_id')}")
            print(f"MATCH? {str(verification.get('_id')) == face.get('verification_id')}")
        else:
            print("No face verification found")
    else:
        print("No verification found")
else:
    print("Consent not found")
