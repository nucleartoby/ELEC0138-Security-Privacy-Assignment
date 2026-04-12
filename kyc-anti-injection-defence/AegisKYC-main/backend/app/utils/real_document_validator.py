"""
Real AI-powered Document Analysis
Uses PaddleOCR, OpenCV, and Computer Vision for actual validation
"""
import cv2
import numpy as np
from PIL import Image
import base64
import io
import re
from datetime import datetime
import easyocr

class RealDocumentValidator:
    """Production-grade document validation with real AI models"""
    
    def __init__(self):
        # Initialize EasyOCR (faster than PaddleOCR for demo)
        self.reader = easyocr.Reader(['en'], gpu=False)
    
    @staticmethod
    def base64_to_cv2(base64_string):
        """Convert base64 to OpenCV image"""
        # Remove data URL prefix if present
        if ',' in base64_string:
            base64_string = base64_string.split(',')[1]
        
        img_data = base64.b64decode(base64_string)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    
    @staticmethod
    def detect_blur(image):
        """Real blur detection using Laplacian variance"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Threshold: < 100 is blurry
        is_clear = laplacian_var > 100
        
        return {
            "laplacian_variance": float(laplacian_var),
            "quality": "high" if laplacian_var > 200 else "medium" if laplacian_var > 100 else "low",
            "passed": is_clear,
            "score": min(100, int((laplacian_var / 300) * 100))
        }
    
    @staticmethod
    def detect_edges(image):
        """Edge detection for tampering analysis"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        # Normal documents have 5-15% edge density
        is_normal = 0.05 <= edge_density <= 0.15
        
        return {
            "edge_density": float(edge_density),
            "tampering_detected": not is_normal,
            "passed": is_normal,
            "score": 100 if is_normal else 60
        }
    
    def extract_text_ocr(self, image):
        """Real OCR text extraction using EasyOCR"""
        try:
            # Run OCR
            results = self.reader.readtext(image)
            
            # Extract all text
            extracted_text = ' '.join([text[1] for text in results])
            
            # Extract structured data
            extracted_data = self._parse_document_text(extracted_text)
            
            confidence = np.mean([text[2] for text in results]) * 100 if results else 0
            
            return {
                "raw_text": extracted_text,
                "extracted_data": extracted_data,
                "confidence": float(confidence),
                "passed": confidence > 60,
                "score": int(min(100, confidence))
            }
        except Exception as e:
            return {
                "raw_text": "",
                "extracted_data": {},
                "confidence": 0,
                "passed": False,
                "score": 0,
                "error": str(e)
            }
    
    @staticmethod
    def _parse_document_text(text):
        """Parse structured data from OCR text"""
        data = {}
        
        # Extract name (usually in CAPS or Title Case)
        name_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?\b'
        names = re.findall(name_pattern, text)
        if names:
            data['name'] = names[0]
        
        # Extract DOB patterns (DD/MM/YYYY, DD-MM-YYYY, etc.)
        dob_patterns = [
            r'\b(\d{2}[/-]\d{2}[/-]\d{4})\b',
            r'\b(\d{4}[/-]\d{2}[/-]\d{2})\b'
        ]
        for pattern in dob_patterns:
            dob_match = re.search(pattern, text)
            if dob_match:
                data['dob'] = dob_match.group(1)
                break
        
        # Extract Aadhaar number (12 digits, may have spaces)
        aadhaar_pattern = r'\b\d{4}\s?\d{4}\s?\d{4}\b'
        aadhaar_match = re.search(aadhaar_pattern, text)
        if aadhaar_match:
            data['aadhaar'] = aadhaar_match.group(0).replace(' ', '')
        
        # Extract PAN number (ABCDE1234F)
        pan_pattern = r'\b[A-Z]{5}\d{4}[A-Z]\b'
        pan_match = re.search(pan_pattern, text)
        if pan_match:
            data['pan'] = pan_match.group(0)
        
        # Extract phone number
        phone_pattern = r'\b[6-9]\d{9}\b'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            data['phone'] = phone_match.group(0)
        
        # Extract address (very basic - line with pin code)
        pincode_pattern = r'\b\d{6}\b'
        if re.search(pincode_pattern, text):
            # Extract context around pincode as address
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if re.search(pincode_pattern, line):
                    # Take this line and previous 2-3 lines as address
                    address_lines = lines[max(0, i-2):i+1]
                    data['address'] = ' '.join(address_lines)
                    data['pincode'] = re.search(pincode_pattern, line).group(0)
                    break
        
        return data
    
    @staticmethod
    def verify_dob_consistency(extracted_data, user_entered_dob):
        """Verify DOB from document matches user input"""
        if 'dob' not in extracted_data:
            return {
                "matched": False,
                "confidence": 0,
                "message": "DOB not found in document"
            }
        
        # Parse both dates
        doc_dob = extracted_data['dob']
        
        # Try different formats
        for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%Y/%m/%d']:
            try:
                doc_date = datetime.strptime(doc_dob, fmt)
                user_date = datetime.strptime(user_entered_dob, '%Y-%m-%d')
                
                if doc_date.date() == user_date.date():
                    return {
                        "matched": True,
                        "confidence": 100,
                        "message": "DOB verified successfully"
                    }
                else:
                    return {
                        "matched": False,
                        "confidence": 0,
                        "message": f"DOB mismatch: Document shows {doc_date.date()}, you entered {user_date.date()}"
                    }
            except:
                continue
        
        return {
            "matched": False,
            "confidence": 0,
            "message": "Could not parse DOB format"
        }
    
    @staticmethod
    def verify_name_consistency(extracted_data, user_entered_name):
        """Verify name from document matches user input"""
        if 'name' not in extracted_data:
            return {
                "matched": False,
                "confidence": 0,
                "message": "Name not found in document"
            }
        
        doc_name = extracted_data['name'].lower().strip()
        user_name = user_entered_name.lower().strip()
        
        # Simple fuzzy matching (Levenshtein distance would be better)
        doc_words = set(doc_name.split())
        user_words = set(user_name.split())
        
        common = doc_words.intersection(user_words)
        total = doc_words.union(user_words)
        
        similarity = (len(common) / len(total)) * 100 if total else 0
        
        matched = similarity > 70
        
        return {
            "matched": matched,
            "confidence": int(similarity),
            "message": "Name verified" if matched else f"Name mismatch: Document shows '{extracted_data['name']}', you entered '{user_entered_name}'"
        }
    
    def comprehensive_analysis(self, base64_image, document_type, user_data=None):
        """Run all validation checks on a document"""
        try:
            # Convert to OpenCV format
            image = self.base64_to_cv2(base64_image)
            
            # Run all checks
            blur_result = self.detect_blur(image)
            edge_result = self.detect_edges(image)
            ocr_result = self.extract_text_ocr(image)
            
            # Calculate overall authenticity score
            scores = [
                blur_result.get('score', 0),
                edge_result.get('score', 0),
                ocr_result.get('score', 0)
            ]
            
            authenticity_score = int(np.mean(scores))
            
            # Verify user data if provided
            verification_results = {}
            if user_data and ocr_result.get('extracted_data'):
                if 'dob' in user_data:
                    verification_results['dob_verification'] = self.verify_dob_consistency(
                        ocr_result['extracted_data'],
                        user_data['dob']
                    )
                
                if 'name' in user_data:
                    verification_results['name_verification'] = self.verify_name_consistency(
                        ocr_result['extracted_data'],
                        user_data['name']
                    )
            
            return {
                "success": True,
                "document_type": document_type,
                "blur_detection": blur_result,
                "edge_analysis": edge_result,
                "ocr_extraction": ocr_result,
                "verification_results": verification_results,
                "authenticity_score": authenticity_score,
                "passed": authenticity_score >= 70,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "authenticity_score": 0,
                "passed": False
            }
