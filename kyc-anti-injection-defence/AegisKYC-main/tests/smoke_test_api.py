"""Simple smoke tests for key API endpoints.

Run after starting the backend (dev). This script does not create or activate virtual environments.

Start backend (example):

    pip install -r backend\requirements.txt
    python backend\app\main.py

Then run this script:

    python tests\smoke_test_api.py

This script will create a verification session (with a placeholder user id) and call
`/api/kyc/detect-deepfake` and `/api/kyc/verify-video` using the returned verification id.
"""
import requests
import json

API_BASE = 'http://127.0.0.1:5000'


def test_detect_deepfake():
    url = f"{API_BASE}/api/kyc/detect-deepfake"
    # Use a tiny transparent image as placeholder
    sample_b64 = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII='
    res = requests.post(url, json={'image_base64': sample_b64}, timeout=10)
    print('detect-deepfake status', res.status_code, res.text)


def test_verify_video():
    url = f"{API_BASE}/api/kyc/verify-video"
    # Provide sample frames array (same tiny image)
    sample_b64 = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII='

    # Create a verification session first (use a placeholder valid ObjectId string)
    init_url = f"{API_BASE}/api/kyc/initiate"
    try:
        init_res = requests.post(init_url, json={'user_id': '000000000000000000000000'}, timeout=10)
        print('initiate status', init_res.status_code, init_res.text)
        if init_res.status_code == 201:
            verification_id = init_res.json().get('verification_id')
        else:
            print('Failed to create verification session; using fallback id')
            verification_id = '000000000000000000000000'
    except Exception as e:
        print('initiate failed:', e)
        verification_id = '000000000000000000000000'

    payload = {
        'verification_id': verification_id,
        'video_frames': [sample_b64]
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        print('verify-video status', res.status_code, res.text)
    except Exception as e:
        print('verify-video failed:', e)


if __name__ == '__main__':
    print('Running smoke tests against', API_BASE)
    test_detect_deepfake()
    test_verify_video()
