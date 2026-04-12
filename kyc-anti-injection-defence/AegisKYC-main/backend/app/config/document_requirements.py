"""
Document Requirements Configuration
Defines all document categories, types, and validation rules
"""

# Document Categories and Requirements
DOCUMENT_CATEGORIES = {
    "identity_proof": {
        "name": "Identity Proof Documents",
        "mandatory": True,
        "min_documents": 3,
        "accepted_documents": [
            "aadhaar",
            "passport",
            "pan_card",
            "driving_license",
            "voter_id",
            "nrega_job_card",
            "govt_id_card"
        ],
        "validations": [
            "blur_detection",
            "edge_detection",
            "reflectance_scan",
            "ocr_extraction",
            "qr_code_validation",
            "mrz_reading",
            "signature_extraction",
            "dob_extraction",
            "face_matching"
        ]
    },
    "address_proof": {
        "name": "Address Proof Documents",
        "mandatory": True,
        "min_documents": 3,
        "accepted_documents": [
            "aadhaar",
            "passport",
            "driving_license",
            "voter_id",
            "utility_bill_electricity",
            "utility_bill_water",
            "utility_bill_gas",
            "telephone_bill",
            "bank_statement",
            "ration_card",
            "rent_agreement",
            "property_tax_receipt",
            "employer_housing_certificate",
            "govt_allotment_letter"
        ],
        "validations": [
            "address_extraction",
            "address_matching",
            "date_validity",
            "geo_consistency",
            "qr_code_validation",
            "forgery_detection",
            "blur_detection"
        ]
    },
    "age_proof": {
        "name": "Age / Date of Birth Proof",
        "mandatory": True,
        "min_documents": 2,
        "accepted_documents": [
            "birth_certificate",
            "ssc_certificate",
            "passport",
            "aadhaar",
            "pan_card"
        ],
        "validations": [
            "dob_extraction",
            "age_verification",
            "authenticity_check",
            "minor_guardian_check"
        ]
    },
    "photo_biometric": {
        "name": "Photo / Biometric Capture",
        "mandatory": True,
        "min_captures": 2,
        "types": [
            "live_selfie",
            "video_liveness"
        ],
        "validations": [
            "face_matching",
            "3d_liveness",
            "anti_spoofing",
            "micro_gesture_detection",
            "expression_variance"
        ]
    },
    "income_employment": {
        "name": "Income / Employment Documents",
        "mandatory": False,
        "min_documents": 3,
        "accepted_documents": [
            "salary_slip",
            "form_16",
            "bank_statement",
            "it_returns",
            "employment_offer_letter",
            "salary_certificate",
            "gst_returns",
            "business_registration"
        ],
        "validations": [
            "ocr_numeric_extraction",
            "employer_validation",
            "income_calculation",
            "pdf_tampering_detection",
            "consistency_check"
        ]
    },
    "educational": {
        "name": "Educational Documents",
        "mandatory": False,
        "min_documents": 2,
        "accepted_documents": [
            "ssc_marksheet",
            "hsc_marksheet",
            "graduation_degree",
            "postgraduation_degree",
            "professional_certification"
        ],
        "validations": [
            "name_matching",
            "institution_recognition",
            "year_consistency",
            "tampering_detection",
            "seal_stamp_detection"
        ]
    },
    "financial_risk": {
        "name": "Financial Risk Assessment",
        "mandatory": False,
        "min_documents": 2,
        "accepted_documents": [
            "source_of_funds",
            "income_proof",
            "investment_proof",
            "business_ownership",
            "bank_ownership"
        ],
        "validations": [
            "cross_matching",
            "value_consistency",
            "suspicious_pattern_detection",
            "aml_risk_flagging"
        ]
    },
    "supporting": {
        "name": "Other Supporting Documents",
        "mandatory": False,
        "min_documents": 0,
        "accepted_documents": [
            "marriage_certificate",
            "name_change_gazette",
            "affidavit",
            "employer_id",
            "disability_certificate",
            "caste_certificate"
        ],
        "validations": [
            "authenticity_check",
            "tampering_detection"
        ]
    }
}

# QR Code Validation Rules
QR_CODE_RULES = {
    "aadhaar": {
        "required": True,
        "validation_type": "encoded_data_extraction",
        "fields": ["name", "dob", "gender", "address", "photo"]
    },
    "driving_license": {
        "required": True,
        "validation_type": "issuance_data",
        "fields": ["license_number", "validity", "vehicle_class"]
    },
    "passport": {
        "required": False,
        "validation_type": "mrz",
        "fields": ["passport_number", "name", "dob", "expiry"]
    },
    "pan_card": {
        "required": False,
        "validation_type": "ocr_signature",
        "fields": ["pan_number", "name", "dob", "signature"]
    },
    "voter_id": {
        "required": False,
        "validation_type": "optional_qr",
        "fields": ["epic_number", "name", "dob"]
    }
}

# Core Authenticity Checks (Applied to ALL documents)
CORE_AUTHENTICITY_CHECKS = [
    "blur_sharpness_score",
    "glare_shadow_detection",
    "edge_integrity",
    "color_consistency",
    "text_distortion",
    "metadata_extraction",
    "reflectance_pattern",
    "compression_artifacts"
]

# Age-Based Document Requirements
AGE_BASED_REQUIREMENTS = {
    "minor": {  # < 18 years
        "special_flow": "guardian_kyc_required",
        "documents": ["birth_certificate", "guardian_aadhaar", "guardian_pan"]
    },
    "young_adult": {  # 18-25 years
        "additional_docs": ["educational_certificates"],
        "verification_level": "enhanced"
    },
    "adult": {  # 26-60 years
        "additional_docs": ["employment_proof"],
        "verification_level": "standard"
    },
    "senior": {  # 60+ years
        "additional_docs": ["pension_certificate"],
        "verification_level": "enhanced"
    }
}

# Micro-Gesture Prompts for Video Liveness
MICRO_GESTURE_PROMPTS = [
    {"action": "look_left", "duration": 2, "description": "Look to your left"},
    {"action": "look_right", "duration": 2, "description": "Look to your right"},
    {"action": "blink", "duration": 1, "description": "Blink twice"},
    {"action": "smile", "duration": 2, "description": "Smile naturally"},
    {"action": "nod", "duration": 2, "description": "Nod your head up and down"}
]

# Document Upload Limits
UPLOAD_LIMITS = {
    "max_file_size_mb": 10,
    "max_files_per_category": 5,
    "supported_formats": ["jpg", "jpeg", "png", "pdf"],
    "min_resolution": {"width": 800, "height": 600},
    "max_resolution": {"width": 4096, "height": 4096}
}

# OCR Confidence Thresholds
OCR_THRESHOLDS = {
    "min_field_confidence": 0.80,
    "critical_fields": ["name", "dob", "document_number"],
    "critical_field_confidence": 0.90
}

# Blur Detection Thresholds
BLUR_THRESHOLDS = {
    "min_laplacian_variance": 100,  # Below this = blurry
    "reject_threshold": 50,
    "warning_threshold": 80
}

# Face Matching Thresholds
FACE_MATCH_THRESHOLDS = {
    "min_match_score": 0.75,
    "high_confidence_score": 0.85,
    "reject_below": 0.60
}
