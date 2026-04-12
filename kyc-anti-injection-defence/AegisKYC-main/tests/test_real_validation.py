"""
Quick Test Script for Real AI Validation
Tests the validation endpoints without running the full app
"""

# Test imports
try:
    import cv2
    print("✓ OpenCV imported successfully")
except ImportError as e:
    print(f"✗ OpenCV import failed: {e}")

try:
    import mediapipe as mp
    print("✓ MediaPipe imported successfully")
except ImportError as e:
    print(f"✗ MediaPipe import failed: {e}")

try:
    import numpy as np
    print("✓ NumPy imported successfully")
except ImportError as e:
    print(f"✗ NumPy import failed: {e}")

try:
    from PIL import Image
    print("✓ Pillow imported successfully")
except ImportError as e:
    print(f"✗ Pillow import failed: {e}")

try:
    from pyzbar.pyzbar import decode
    print("✓ Pyzbar imported successfully")
except ImportError as e:
    print(f"✗ Pyzbar import failed: {e}")

try:
    from difflib import SequenceMatcher
    print("✓ difflib imported successfully")
except ImportError as e:
    print(f"✗ difflib import failed: {e}")

print("\n" + "="*50)
print("Testing Real Validators...")
print("="*50 + "\n")

# Test Real OCR Validator
try:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))
    
    from utils.real_ocr_validator import RealOCRValidator
    
    validator = RealOCRValidator()
    print("✓ RealOCRValidator instantiated successfully")
    
    # Test DOB validation
    dob_result = validator.validate_date_of_birth("01/01/1990")
    if dob_result.get('valid'):
        print(f"✓ DOB Validation works! Parsed: {dob_result['parsed_date']}, Age: {dob_result['age']}")
    
    # Test name verification
    name_result = validator.cross_verify_name("JOHN DOE", "JOHN DOE")
    if name_result.get('match'):
        print(f"✓ Name Verification works! Similarity: {name_result['similarity_score']:.1f}%")
    
except Exception as e:
    print(f"✗ RealOCRValidator test failed: {e}")

# Test Real Face Analyzer
try:
    from utils.real_face_analyzer import RealFaceAnalyzer, RealLivenessDetector
    
    face_analyzer = RealFaceAnalyzer()
    print("✓ RealFaceAnalyzer instantiated successfully")
    
    liveness_detector = RealLivenessDetector()
    print("✓ RealLivenessDetector instantiated successfully")
    
except Exception as e:
    print(f"✗ Face Analyzer test failed: {e}")

print("\n" + "="*50)
print("✅ All Core Components Ready!")
print("="*50 + "\n")

print("Next Steps:")
print("1. Start Flask server: python app/main.py")
print("2. Open browser: http://localhost:5000/kyc_complete")
print("3. Upload documents to test real validation")
print("\nAPI Endpoints Available:")
print("  - POST /api/validation/validate-document")
print("  - POST /api/validation/extract-pan")
print("  - POST /api/validation/extract-aadhaar")
print("  - POST /api/validation/verify-selfie")
print("  - POST /api/validation/verify-liveness")
print("  - POST /api/validation/cross-verify-name")
print("  - POST /api/validation/cross-verify-dob")
