from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv('MONGO_URL'))
db = client['aegis_kyc']

# Check FaceVerification
face = db['FaceVerification'].find_one()
print('=== FACE VERIFICATION ===')
if face:
    print(f'Record found: {face.get("_id")}')
    print(f'User ID: {face.get("user_id")}')
    print(f'Verification ID: {face.get("verification_id")}')
    selfie = face.get('selfie_image', '')
    print(f'Selfie image length: {len(selfie)} bytes')
    if len(selfie) > 0:
        print(f'Starts with: {selfie[:50]}...')
        print(f'Is base64?: {selfie.startswith("data:image")}')
    print(f'Liveness score: {face.get("liveness_check", {}).get("score")}')
    print(f'Face match score: {face.get("face_matching", {}).get("score")}')
    print(f'Overall score: {face.get("overall_score")}')
else:
    print('NO RECORDS FOUND')

print('\n=== VIDEO VERIFICATION ===')
video = db['VideoVerification'].find_one()
if video:
    print(f'Record found: {video.get("_id")}')
    print(f'User ID: {video.get("user_id")}')
    print(f'Verification ID: {video.get("verification_id")}')
    video_data = video.get('video_data', '')
    print(f'Video data length: {len(video_data)} bytes')
    if len(video_data) > 0:
        print(f'Starts with: {video_data[:50]}...')
        print(f'Is base64?: {video_data.startswith("data:video")}')
    print(f'Lipsync score: {video.get("lipsync_score")}')
    print(f'Deepfake score: {video.get("deepfake_score")}')
    print(f'Overall score: {video.get("overall_score")}')
else:
    print('NO RECORDS FOUND')
