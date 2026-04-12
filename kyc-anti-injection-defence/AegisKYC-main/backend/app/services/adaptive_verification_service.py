"""
Adaptive Verification Service
Determines verification path based on user risk profile
"""
from datetime import datetime
from bson.objectid import ObjectId
from app.utils.db import db

class AdaptiveVerificationService:
    """
    Risk-based adaptive verification logic
    Low-risk users: Fast-track (skip redundant steps)
    High-risk users: Deep verification (all steps + manual review)
    """
    
    RISK_THRESHOLDS = {
        "low": 85,      # Score >= 85: Fast-track
        "medium": 60,   # Score 60-84: Standard flow
        "high": 60      # Score < 60: Deep verification + manual review
    }
    
    @staticmethod
    def calculate_initial_risk_score(user_data: dict, device_data: dict) -> dict:
        """
        Calculate initial risk score before KYC starts
        Factors: Email reputation, phone verification, device trust, location
        """
        score = 100  # Start optimistic
        risk_factors = []
        
        # Email verification status
        if not user_data.get('email_verified'):
            score -= 15
            risk_factors.append("Email not verified")
        
        # Phone verification
        if not user_data.get('phone_verified'):
            score -= 10
            risk_factors.append("Phone not verified")
        
        # Device trust
        device_trust = device_data.get('trust_score', 50)
        if device_trust < 40:
            score -= 20
            risk_factors.append("Low device trust")
        elif device_trust < 70:
            score -= 10
            risk_factors.append("Medium device trust")
        
        # Location risk (example: VPN detection, high-fraud regions)
        if device_data.get('vpn_detected'):
            score -= 15
            risk_factors.append("VPN detected")
        
        if device_data.get('location_mismatch'):
            score -= 10
            risk_factors.append("Location mismatch")
        
        # New vs returning user
        if user_data.get('is_returning_customer'):
            score += 10
            risk_factors.append("Returning customer (+10)")
        
        # Determine risk level
        if score >= AdaptiveVerificationService.RISK_THRESHOLDS["low"]:
            risk_level = "low"
        elif score >= AdaptiveVerificationService.RISK_THRESHOLDS["medium"]:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        return {
            "initial_risk_score": max(0, min(100, score)),
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "recommended_flow": AdaptiveVerificationService._get_verification_flow(risk_level)
        }
    
    @staticmethod
    def _get_verification_flow(risk_level: str) -> dict:
        """
        Define which steps to execute based on risk level
        """
        if risk_level == "low":
            # Fast-track: Skip redundant steps
            return {
                "flow_type": "fast_track",
                "required_steps": [0, 1, 2, 3, 7, 9],  # Pre-check, document, analysis, face, risk, credential
                "optional_steps": [5, 6],  # Video and AML are optional
                "estimated_time_minutes": 8,
                "manual_review_required": False
            }
        elif risk_level == "medium":
            # Standard flow: Most steps required
            return {
                "flow_type": "standard",
                "required_steps": [0, 1, 2, 3, 5, 7, 9],  # Include video verification
                "optional_steps": [4, 6],  # Address and AML optional
                "estimated_time_minutes": 15,
                "manual_review_required": False
            }
        else:  # high
            # Deep verification: All steps + manual review
            return {
                "flow_type": "deep_verification",
                "required_steps": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],  # All steps
                "optional_steps": [],
                "estimated_time_minutes": 25,
                "manual_review_required": True,
                "review_reason": "High initial risk score or anomaly detected"
            }
    
    @staticmethod
    def update_risk_score_during_verification(verification_id: str) -> dict:
        """
        Recalculate risk score as verification progresses
        Adjust flow dynamically if anomalies detected
        """
        verification = db["KYCVerificationRequests"].find_one({"_id": ObjectId(verification_id)})
        if not verification:
            return {"error": "Verification not found"}
        
        current_score = verification.get('risk_score', 70)
        anomalies = []
        
        # Check document authenticity
        docs = list(db["DocumentAnalysis"].find({"verification_id": verification_id}))
        if docs:
            avg_authenticity = sum(d.get('authenticity_score', 0) for d in docs) / len(docs)
            if avg_authenticity < 50:
                current_score -= 20
                anomalies.append("Low document authenticity")
            elif avg_authenticity < 70:
                current_score -= 10
                anomalies.append("Medium document authenticity")
        
        # Check face verification
        face = db["FaceVerification"].find_one({"verification_id": verification_id})
        if face:
            liveness = face.get('liveness_check', {}).get('score', 0)
            if liveness < 70:
                current_score -= 15
                anomalies.append("Low liveness score")
            
            face_match = face.get('face_matching', {}).get('score', 0)
            if face_match < 75:
                current_score -= 15
                anomalies.append("Low face match score")
        
        # Check behavioral patterns
        behavior = verification.get('behavioral_trust', {})
        if behavior.get('bot_likelihood', 0) > 30:
            current_score -= 25
            anomalies.append("Potential bot behavior detected")
        
        # Update risk level
        if current_score >= AdaptiveVerificationService.RISK_THRESHOLDS["low"]:
            risk_level = "low"
        elif current_score >= AdaptiveVerificationService.RISK_THRESHOLDS["medium"]:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        # Update verification record
        db["KYCVerificationRequests"].update_one(
            {"_id": ObjectId(verification_id)},
            {
                "$set": {
                    "risk_score": current_score,
                    "risk_level": risk_level,
                    "anomalies_detected": anomalies,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {
            "verification_id": verification_id,
            "current_risk_score": current_score,
            "risk_level": risk_level,
            "anomalies": anomalies,
            "requires_manual_review": risk_level == "high" or len(anomalies) >= 2
        }
    
    @staticmethod
    def should_skip_step(verification_id: str, step_number: int) -> bool:
        """
        Determine if a step can be skipped based on current risk profile
        """
        verification = db["KYCVerificationRequests"].find_one({"_id": ObjectId(verification_id)})
        if not verification:
            return False
        
        risk_level = verification.get('risk_level', 'medium')
        flow = AdaptiveVerificationService._get_verification_flow(risk_level)
        
        # Skip if step is not in required_steps for this risk level
        return step_number not in flow['required_steps']
