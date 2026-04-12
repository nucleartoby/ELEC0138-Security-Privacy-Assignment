"""
Input validation utilities for KYC data
Ensures data integrity and prevents injection attacks
"""
import re
from datetime import datetime


class Validators:
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number (international format)"""
        # Remove spaces and dashes
        phone = re.sub(r'[\s-]', '', phone)
        # Accept + followed by 10-15 digits
        pattern = r'^\+?[1-9]\d{9,14}$'
        return bool(re.match(pattern, phone))
    
    @staticmethod
    def validate_dob(dob_str: str) -> bool:
        """
        Validate date of birth
        Format: YYYY-MM-DD
        Must be 18+ years old
        """
        try:
            dob = datetime.strptime(dob_str, '%Y-%m-%d')
            age = (datetime.now() - dob).days / 365.25
            return age >= 18 and age <= 120
        except:
            return False
    
    @staticmethod
    def validate_gender(gender: str) -> bool:
        """Validate gender selection"""
        valid_genders = ['male', 'female', 'other', 'prefer-not-to-say']
        return gender.lower() in valid_genders
    
    @staticmethod
    def validate_password(password: str) -> dict:
        """
        Validate password strength
        Requirements:
        - Minimum 8 characters
        - At least 1 uppercase
        - At least 1 lowercase
        - At least 1 digit
        - At least 1 special character
        """
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    @staticmethod
    def validate_pincode(pincode: str) -> bool:
        """Validate pincode/ZIP code (4-10 alphanumeric)"""
        pattern = r'^[A-Za-z0-9\s-]{4,10}$'
        return bool(re.match(pattern, pincode))
    
    @staticmethod
    def sanitize_string(text: str, max_length: int = 255) -> str:
        """Sanitize string input to prevent injection attacks"""
        if not text:
            return ""
        # Remove potential SQL/NoSQL injection patterns
        text = re.sub(r'[<>{}\\$]', '', text)
        return text[:max_length].strip()
    
    @staticmethod
    def validate_signup_data(data: dict) -> dict:
        """
        Validate complete signup data
        Returns: {valid: bool, errors: dict}
        """
        errors = {}
        
        # Validate email
        if not data.get("email") or not Validators.validate_email(data["email"]):
            errors["email"] = "Invalid email address"
        
        # Validate phone
        if not data.get("phone") or not Validators.validate_phone(data["phone"]):
            errors["phone"] = "Invalid phone number format"
        
        # Validate full name
        if not data.get("full_name") or len(data["full_name"].strip()) < 2:
            errors["full_name"] = "Full name is required (minimum 2 characters)"
        
        # Validate DOB
        if not data.get("dob") or not Validators.validate_dob(data["dob"]):
            errors["dob"] = "Invalid date of birth or user must be 18+ years old"
        
        # Validate gender
        if not data.get("gender") or not Validators.validate_gender(data["gender"]):
            errors["gender"] = "Invalid gender selection"
        
        # Validate password
        if not data.get("password"):
            errors["password"] = "Password is required"
        else:
            pwd_validation = Validators.validate_password(data["password"])
            if not pwd_validation["valid"]:
                errors["password"] = pwd_validation["errors"]
        
        # Validate address
        address = data.get("address", {})
        if not address.get("line1"):
            errors["address_line1"] = "Address line 1 is required"
        if not address.get("city"):
            errors["city"] = "City is required"
        if not address.get("state"):
            errors["state"] = "State is required"
        if not address.get("country"):
            errors["country"] = "Country is required"
        if not address.get("pincode") or not Validators.validate_pincode(address["pincode"]):
            errors["pincode"] = "Invalid pincode/ZIP code"
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
