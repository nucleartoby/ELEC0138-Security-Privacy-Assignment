"""
Bias Detection & Monitoring Service
Ensures AI models are fair and unbiased across demographics
Monitors for skew, drift, and discriminatory patterns
"""
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from app.utils.db import db

class BiasDetectionService:
    """
    Monitor verification decisions for demographic bias
    - Gender bias detection
    - Age bias detection  
    - Geographic bias detection
    - Document type bias
    - Approval rate disparities
    """
    
    # Acceptable variance in approval rates (±10%)
    BIAS_THRESHOLD = 0.10
    
    # Minimum sample size for statistical significance
    MIN_SAMPLE_SIZE = 30
    
    @staticmethod
    def analyze_gender_bias(start_date: datetime, end_date: datetime) -> dict:
        """
        Check if approval rates differ significantly by gender
        """
        verifications = db["KYCVerificationRequests"].find({
            "created_at": {"$gte": start_date, "$lte": end_date},
            "status": {"$in": ["approved", "rejected"]}
        })
        
        stats = defaultdict(lambda: {"total": 0, "approved": 0, "rejected": 0})
        
        for verification in verifications:
            user_id = verification.get('user_id')
            user = db["Users"].find_one({"_id": user_id})
            
            if not user:
                continue
            
            gender = user.get('gender', 'unknown')
            status = verification.get('status')
            
            stats[gender]["total"] += 1
            if status == "approved":
                stats[gender]["approved"] += 1
            else:
                stats[gender]["rejected"] += 1
        
        # Calculate approval rates
        results = {}
        for gender, data in stats.items():
            if data["total"] >= BiasDetectionService.MIN_SAMPLE_SIZE:
                approval_rate = data["approved"] / data["total"] if data["total"] > 0 else 0
                results[gender] = {
                    "total_verifications": data["total"],
                    "approved": data["approved"],
                    "rejected": data["rejected"],
                    "approval_rate": round(approval_rate * 100, 2)
                }
        
        # Check for bias
        approval_rates = [r["approval_rate"] for r in results.values()]
        if len(approval_rates) >= 2:
            max_rate = max(approval_rates)
            min_rate = min(approval_rates)
            disparity = (max_rate - min_rate) / 100
            
            bias_detected = disparity > BiasDetectionService.BIAS_THRESHOLD
        else:
            bias_detected = False
            disparity = 0
        
        return {
            "dimension": "gender",
            "period": f"{start_date.date()} to {end_date.date()}",
            "statistics": results,
            "bias_detected": bias_detected,
            "disparity": round(disparity * 100, 2),
            "threshold": BiasDetectionService.BIAS_THRESHOLD * 100,
            "recommendation": "Review gender-related features in scoring model" if bias_detected else "No significant gender bias detected"
        }
    
    @staticmethod
    def analyze_age_bias(start_date: datetime, end_date: datetime) -> dict:
        """
        Check if approval rates differ by age group
        """
        verifications = db["KYCVerificationRequests"].find({
            "created_at": {"$gte": start_date, "$lte": end_date},
            "status": {"$in": ["approved", "rejected"]}
        })
        
        # Age buckets: 18-25, 26-35, 36-50, 51+
        age_groups = {
            "18-25": {"total": 0, "approved": 0},
            "26-35": {"total": 0, "approved": 0},
            "36-50": {"total": 0, "approved": 0},
            "51+": {"total": 0, "approved": 0}
        }
        
        for verification in verifications:
            user_id = verification.get('user_id')
            user = db["Users"].find_one({"_id": user_id})
            
            if not user:
                continue
            
            dob = user.get('date_of_birth')
            if not dob:
                continue
            
            # Calculate age
            age = (datetime.utcnow() - datetime.fromisoformat(dob)).days // 365
            
            # Assign to age group
            if 18 <= age <= 25:
                group = "18-25"
            elif 26 <= age <= 35:
                group = "26-35"
            elif 36 <= age <= 50:
                group = "36-50"
            else:
                group = "51+"
            
            age_groups[group]["total"] += 1
            if verification.get('status') == "approved":
                age_groups[group]["approved"] += 1
        
        # Calculate rates
        results = {}
        for group, data in age_groups.items():
            if data["total"] >= BiasDetectionService.MIN_SAMPLE_SIZE:
                rate = data["approved"] / data["total"] if data["total"] > 0 else 0
                results[group] = {
                    "total": data["total"],
                    "approved": data["approved"],
                    "approval_rate": round(rate * 100, 2)
                }
        
        # Detect bias
        if len(results) >= 2:
            rates = [r["approval_rate"] for r in results.values()]
            disparity = (max(rates) - min(rates)) / 100
            bias_detected = disparity > BiasDetectionService.BIAS_THRESHOLD
        else:
            bias_detected = False
            disparity = 0
        
        return {
            "dimension": "age",
            "statistics": results,
            "bias_detected": bias_detected,
            "disparity": round(disparity * 100, 2),
            "recommendation": "Age should not affect approval - investigate scoring model" if bias_detected else "No age bias detected"
        }
    
    @staticmethod
    def analyze_geographic_bias(start_date: datetime, end_date: datetime) -> dict:
        """
        Check for geographic/location-based bias
        """
        verifications = db["KYCVerificationRequests"].find({
            "created_at": {"$gte": start_date, "$lte": end_date},
            "status": {"$in": ["approved", "rejected"]}
        })
        
        location_stats = defaultdict(lambda: {"total": 0, "approved": 0})
        
        for verification in verifications:
            user_id = verification.get('user_id')
            user = db["Users"].find_one({"_id": user_id})
            
            if not user:
                continue
            
            state = user.get('state', 'unknown')
            location_stats[state]["total"] += 1
            
            if verification.get('status') == "approved":
                location_stats[state]["approved"] += 1
        
        # Calculate approval rates
        results = {}
        for location, data in location_stats.items():
            if data["total"] >= BiasDetectionService.MIN_SAMPLE_SIZE:
                rate = data["approved"] / data["total"] if data["total"] > 0 else 0
                results[location] = {
                    "total": data["total"],
                    "approved": data["approved"],
                    "approval_rate": round(rate * 100, 2)
                }
        
        # Detect bias
        if len(results) >= 2:
            rates = [r["approval_rate"] for r in results.values()]
            disparity = (max(rates) - min(rates)) / 100
            bias_detected = disparity > BiasDetectionService.BIAS_THRESHOLD
        else:
            bias_detected = False
            disparity = 0
        
        return {
            "dimension": "geography",
            "statistics": results,
            "bias_detected": bias_detected,
            "disparity": round(disparity * 100, 2),
            "recommendation": "Geographic location should not affect verification" if bias_detected else "No geographic bias detected"
        }
    
    @staticmethod
    def generate_bias_report() -> dict:
        """
        Comprehensive bias monitoring report
        """
        # Last 30 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        gender_analysis = BiasDetectionService.analyze_gender_bias(start_date, end_date)
        age_analysis = BiasDetectionService.analyze_age_bias(start_date, end_date)
        geo_analysis = BiasDetectionService.analyze_geographic_bias(start_date, end_date)
        
        # Overall bias score
        bias_dimensions = [gender_analysis, age_analysis, geo_analysis]
        total_bias_detected = sum(1 for d in bias_dimensions if d.get('bias_detected'))
        
        overall_health = "HEALTHY" if total_bias_detected == 0 else "NEEDS_ATTENTION" if total_bias_detected == 1 else "CRITICAL"
        
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "reporting_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": 30
            },
            "overall_fairness_score": round((3 - total_bias_detected) / 3 * 100, 1),
            "overall_health": overall_health,
            "bias_analysis": {
                "gender": gender_analysis,
                "age": age_analysis,
                "geography": geo_analysis
            },
            "recommendations": [],
            "compliance_status": "COMPLIANT" if overall_health == "HEALTHY" else "NON_COMPLIANT"
        }
        
        # Add recommendations
        if gender_analysis.get('bias_detected'):
            report["recommendations"].append("⚠️ Gender bias detected - retrain model with balanced dataset")
        if age_analysis.get('bias_detected'):
            report["recommendations"].append("⚠️ Age bias detected - remove age-correlated features")
        if geo_analysis.get('bias_detected'):
            report["recommendations"].append("⚠️ Geographic bias detected - ensure uniform document standards")
        
        if not report["recommendations"]:
            report["recommendations"].append("✅ No significant bias detected - continue monitoring")
        
        # Store report in database
        db["BiasMonitoringReports"].insert_one(report)
        
        return report
    
    @staticmethod
    def monitor_model_drift() -> dict:
        """
        Detect if AI model performance is drifting over time
        """
        # Compare last 7 days vs previous 7 days
        now = datetime.utcnow()
        
        period1_start = now - timedelta(days=14)
        period1_end = now - timedelta(days=7)
        
        period2_start = now - timedelta(days=7)
        period2_end = now
        
        # Get approval rates for both periods
        def get_approval_rate(start, end):
            verifications = db["KYCVerificationRequests"].find({
                "created_at": {"$gte": start, "$lte": end},
                "status": {"$in": ["approved", "rejected"]}
            })
            
            total = 0
            approved = 0
            for v in verifications:
                total += 1
                if v.get('status') == "approved":
                    approved += 1
            
            return (approved / total * 100) if total > 0 else 0
        
        rate_period1 = get_approval_rate(period1_start, period1_end)
        rate_period2 = get_approval_rate(period2_start, period2_end)
        
        drift_percentage = abs(rate_period2 - rate_period1)
        drift_detected = drift_percentage > 5  # >5% change is significant
        
        return {
            "drift_detected": drift_detected,
            "period1_approval_rate": round(rate_period1, 2),
            "period2_approval_rate": round(rate_period2, 2),
            "drift_percentage": round(drift_percentage, 2),
            "recommendation": "Model may need retraining" if drift_detected else "Model performance stable",
            "monitored_at": datetime.utcnow().isoformat()
        }
