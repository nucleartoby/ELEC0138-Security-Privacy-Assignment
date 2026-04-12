"""
Document Validation Utilities
Simulated implementations for OCR, QR, blur detection, etc.
Ready to be replaced with real AI/CV services
"""
import base64
import random
import re
from datetime import datetime, timedelta
import hashlib


class DocumentValidator:
    """
    Document validation utilities with simulated AI/CV capabilities
    """
    
    @staticmethod
    def detect_blur(image_base64: str) -> dict:
        """
        Detect if document image is blurry
        SIMULATION: Returns dummy scores
        PRODUCTION: Use OpenCV Laplacian variance or Google Cloud Vision
        """
        # Simulated blur detection based on image size (larger = sharper)
        image_size = len(image_base64)
        laplacian_variance = min(200, image_size / 10000)  # Dummy calculation
        
        is_blurry = laplacian_variance < 100
        quality = "sharp" if laplacian_variance > 150 else "acceptable" if laplacian_variance > 100 else "blurry"
        
        return {
            "is_blurry": is_blurry,
            "laplacian_variance": laplacian_variance,
            "quality": quality,
            "passed": not is_blurry,
            "confidence": 0.85
        }
    
    @staticmethod
    def detect_glare_shadow(image_base64: str) -> dict:
        """
        Detect glare and shadows on document
        SIMULATION: Returns dummy detection
        PRODUCTION: Use histogram analysis or ML model
        """
        # Simulated detection
        has_glare = random.random() < 0.1
        has_shadow = random.random() < 0.15
        
        return {
            "has_glare": has_glare,
            "has_shadow": has_shadow,
            "glare_intensity": random.uniform(0, 0.3) if has_glare else 0,
            "shadow_intensity": random.uniform(0, 0.4) if has_shadow else 0,
            "passed": not (has_glare or has_shadow),
            "confidence": 0.82
        }
    
    @staticmethod
    def detect_edge_tampering(image_base64: str) -> dict:
        """
        Detect if document edges are tampered/cropped
        SIMULATION: Returns dummy detection
        PRODUCTION: Use edge detection algorithms (Canny, Sobel)
        """
        edge_integrity = random.uniform(0.75, 0.98)
        
        return {
            "edge_integrity_score": edge_integrity,
            "is_tampered": edge_integrity < 0.80,
            "corners_detected": 4,
            "aspect_ratio_valid": True,
            "passed": edge_integrity >= 0.80,
            "confidence": 0.88
        }
    
    @staticmethod
    def extract_text_ocr(image_base64: str, document_type: str) -> dict:
        """
        Extract text from document using OCR
        SIMULATION: Returns dummy extracted data
        PRODUCTION: Use Tesseract.js, Google Cloud Vision, or AWS Textract
        """
        # Simulated OCR extraction based on document type
        dummy_data = {
            "aadhaar": {
                "name": "AMIT KUMAR SHARMA",
                "dob": "15/08/1990",
                "gender": "Male",
                "aadhaar_number": "1234 5678 9012",
                "address": "123 MG Road, Bangalore, Karnataka 560001",
                "confidence": 0.92
            },
            "pan_card": {
                "name": "AMIT KUMAR SHARMA",
                "father_name": "RAJESH SHARMA",
                "dob": "15/08/1990",
                "pan_number": "ABCDE1234F",
                "confidence": 0.89
            },
            "passport": {
                "name": "AMIT KUMAR SHARMA",
                "passport_number": "K1234567",
                "dob": "15/08/1990",
                "issue_date": "10/01/2020",
                "expiry_date": "09/01/2030",
                "nationality": "INDIAN",
                "confidence": 0.94
            },
            "driving_license": {
                "name": "AMIT KUMAR SHARMA",
                "dl_number": "KA0120200012345",
                "dob": "15/08/1990",
                "issue_date": "05/03/2018",
                "validity": "04/03/2038",
                "vehicle_class": "LMV",
                "confidence": 0.87
            },
            "voter_id": {
                "name": "AMIT KUMAR SHARMA",
                "epic_number": "ABC1234567",
                "dob": "15/08/1990",
                "gender": "Male",
                "confidence": 0.85
            }
        }
        
        extracted = dummy_data.get(document_type, {
            "text": "Simulated OCR text extraction",
            "confidence": 0.80
        })
        
        return {
            "success": True,
            "extracted_fields": extracted,
            "overall_confidence": extracted.get("confidence", 0.80),
            "critical_fields_found": True,
            "passed": extracted.get("confidence", 0.80) >= 0.80
        }
    
    @staticmethod
    def extract_qr_code(image_base64: str, document_type: str) -> dict:
        """
        Extract and validate QR code from document
        SIMULATION: Returns dummy QR data
        PRODUCTION: Use qr-scanner, jsQR, or zxing library
        """
        qr_required_docs = ["aadhaar", "driving_license"]
        
        if document_type not in qr_required_docs:
            return {
                "qr_required": False,
                "qr_found": False,
                "passed": True
            }
        
        # Simulated QR extraction
        qr_data = {
            "aadhaar": {
                "encoded_data": hashlib.sha256(b"aadhaar_qr_data").hexdigest()[:32],
                "name": "AMIT KUMAR SHARMA",
                "dob": "15/08/1990",
                "gender": "M",
                "address": "123 MG Road, Bangalore",
                "photo_hash": hashlib.md5(b"photo_data").hexdigest()
            },
            "driving_license": {
                "license_number": "KA0120200012345",
                "name": "AMIT KUMAR SHARMA",
                "dob": "15/08/1990",
                "validity": "04/03/2038",
                "vehicle_class": "LMV"
            }
        }
        
        return {
            "qr_required": True,
            "qr_found": True,
            "qr_data": qr_data.get(document_type, {}),
            "validation_passed": True,
            "passed": True,
            "confidence": 0.93
        }
    
    @staticmethod
    def read_mrz(image_base64: str) -> dict:
        """
        Read Machine Readable Zone from passport
        SIMULATION: Returns dummy MRZ data
        PRODUCTION: Use mrz library or specialized passport scanner
        """
        # Simulated MRZ reading
        return {
            "mrz_found": True,
            "mrz_type": "TD3",  # Passport
            "document_number": "K1234567",
            "nationality": "IND",
            "name": "SHARMA<<AMIT<KUMAR",
            "dob": "900815",  # YYMMDD
            "sex": "M",
            "expiry": "300109",
            "personal_number": "",
            "check_digit_valid": True,
            "passed": True,
            "confidence": 0.96
        }
    
    @staticmethod
    def detect_reflectance_pattern(image_base64: str) -> dict:
        """
        Detect reflectance patterns to catch reprinted documents
        SIMULATION: Returns dummy analysis
        PRODUCTION: Use spectral analysis or specialized hardware
        """
        reflectance_score = random.uniform(0.70, 0.98)
        is_original = reflectance_score > 0.85
        
        return {
            "reflectance_score": reflectance_score,
            "is_original_print": is_original,
            "is_photocopy": not is_original and reflectance_score < 0.80,
            "is_scan": not is_original and reflectance_score >= 0.80,
            "passed": is_original,
            "confidence": 0.79
        }
    
    @staticmethod
    def extract_metadata(image_base64: str) -> dict:
        """
        Extract EXIF metadata from image
        SIMULATION: Returns dummy metadata
        PRODUCTION: Use PIL/Pillow EXIF extraction
        """
        return {
            "camera_make": "Apple",
            "camera_model": "iPhone 14 Pro",
            "timestamp": datetime.now().isoformat(),
            "gps_coordinates": None,
            "software": None,
            "has_been_edited": False,
            "passed": True
        }
    
    @staticmethod
    def validate_signature(image_base64: str) -> dict:
        """
        Detect and validate signature on document (PAN card)
        SIMULATION: Returns dummy detection
        PRODUCTION: Use signature detection ML model
        """
        return {
            "signature_found": True,
            "signature_location": {"x": 450, "y": 320, "width": 120, "height": 40},
            "signature_quality": "good",
            "passed": True,
            "confidence": 0.84
        }
    
    @staticmethod
    def extract_dob(ocr_data: dict) -> dict:
        """
        Extract and parse date of birth from OCR data
        """
        dob_str = ocr_data.get("extracted_fields", {}).get("dob", "")
        
        if not dob_str:
            return {
                "dob_found": False,
                "dob_parsed": None,
                "age": None,
                "age_category": None
            }
        
        # Try parsing DD/MM/YYYY format
        try:
            dob = datetime.strptime(dob_str, "%d/%m/%Y")
            age = (datetime.now() - dob).days // 365
            
            # Determine age category
            if age < 18:
                age_category = "minor"
            elif age <= 25:
                age_category = "young_adult"
            elif age <= 60:
                age_category = "adult"
            else:
                age_category = "senior"
            
            return {
                "dob_found": True,
                "dob_parsed": dob.isoformat(),
                "dob_string": dob_str,
                "age": age,
                "age_category": age_category,
                "is_adult": age >= 18
            }
        except:
            return {
                "dob_found": True,
                "dob_parsed": None,
                "dob_string": dob_str,
                "age": None,
                "age_category": None,
                "parse_error": True
            }
    
    @staticmethod
    def cross_verify_dob(documents_data: list) -> dict:
        """
        Cross-verify DOB across multiple documents
        """
        dobs = []
        for doc in documents_data:
            dob = doc.get("extracted_fields", {}).get("dob")
            if dob:
                dobs.append(dob)
        
        if not dobs:
            return {
                "verification_status": "no_dob_found",
                "consistent": False
            }
        
        # Check if all DOBs match
        unique_dobs = set(dobs)
        is_consistent = len(unique_dobs) == 1
        
        return {
            "verification_status": "consistent" if is_consistent else "mismatch",
            "consistent": is_consistent,
            "dob_count": len(dobs),
            "unique_dobs": list(unique_dobs),
            "primary_dob": dobs[0] if is_consistent else None,
            "passed": is_consistent
        }
    
    @staticmethod
    def comprehensive_document_check(image_base64: str, document_type: str) -> dict:
        """
        Run all validation checks on a document
        """
        results = {
            "document_type": document_type,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        # Run all checks
        results["checks"]["blur_detection"] = DocumentValidator.detect_blur(image_base64)
        results["checks"]["glare_shadow"] = DocumentValidator.detect_glare_shadow(image_base64)
        results["checks"]["edge_tampering"] = DocumentValidator.detect_edge_tampering(image_base64)
        results["checks"]["ocr_extraction"] = DocumentValidator.extract_text_ocr(image_base64, document_type)
        results["checks"]["qr_code"] = DocumentValidator.extract_qr_code(image_base64, document_type)
        results["checks"]["reflectance"] = DocumentValidator.detect_reflectance_pattern(image_base64)
        results["checks"]["metadata"] = DocumentValidator.extract_metadata(image_base64)
        
        # Document-specific checks
        if document_type == "passport":
            results["checks"]["mrz_reading"] = DocumentValidator.read_mrz(image_base64)
        
        if document_type == "pan_card":
            results["checks"]["signature"] = DocumentValidator.validate_signature(image_base64)
        
        # Extract DOB
        dob_info = DocumentValidator.extract_dob(results["checks"]["ocr_extraction"])
        results["dob_info"] = dob_info
        
        # Calculate overall authenticity score
        check_scores = []
        for check_name, check_result in results["checks"].items():
            if isinstance(check_result, dict) and "confidence" in check_result:
                if check_result.get("passed", True):
                    check_scores.append(check_result["confidence"])
                else:
                    check_scores.append(0)
        
        authenticity_score = (sum(check_scores) / len(check_scores) * 100) if check_scores else 0
        
        results["authenticity_score"] = round(authenticity_score, 2)
        results["all_checks_passed"] = all(
            check.get("passed", True) for check in results["checks"].values() if isinstance(check, dict)
        )
        results["verification_status"] = "verified" if results["all_checks_passed"] and authenticity_score >= 75 else "needs_review"
        
        return results
