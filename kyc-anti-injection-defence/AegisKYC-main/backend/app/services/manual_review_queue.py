"""
Manual Review Queue Service
For borderline/high-risk cases requiring human judgment
Prevents algorithmic bias from affecting user access
"""
from datetime import datetime
from bson.objectid import ObjectId
from app.utils.db import db

class ManualReviewQueue:
    """
    Queue management for verifications requiring human review
    - Borderline scores (60-70% identity integrity)
    - Anomaly detections (behavioral, device, document)
    - High-risk users
    - Bias prevention (ensure fair treatment)
    """
    
    PRIORITY_LEVELS = {
        "urgent": 1,    # Fraud suspected, high-value customer
        "high": 2,      # Multiple anomalies, borderline score
        "medium": 3,    # Single anomaly or edge case
        "low": 4        # Standard review for quality assurance
    }
    
    @staticmethod
    def add_to_review_queue(verification_id: str, reason: str, priority: str = "medium", details: dict = None) -> dict:
        """
        Add verification to manual review queue
        """
        verification = db["KYCVerificationRequests"].find_one({"_id": ObjectId(verification_id)})
        if not verification:
            return {"error": "Verification not found"}
        
        # Create review task
        review_task = {
            "verification_id": verification_id,
            "user_id": verification.get('user_id'),
            "reason": reason,
            "priority": priority,
            "priority_score": ManualReviewQueue.PRIORITY_LEVELS.get(priority, 3),
            "status": "pending",
            "created_at": datetime.utcnow(),
            "assigned_to": None,
            "reviewed_at": None,
            "review_decision": None,
            "reviewer_notes": None,
            "details": details or {},
            "identity_score": verification.get('identity_integrity_score', 0),
            "risk_score": verification.get('risk_score', 0),
            "anomalies": verification.get('anomalies_detected', [])
        }
        
        result = db["ManualReviewQueue"].insert_one(review_task)
        
        # Update verification status
        db["KYCVerificationRequests"].update_one(
            {"_id": ObjectId(verification_id)},
            {
                "$set": {
                    "status": "pending_manual_review",
                    "review_queue_id": str(result.inserted_id),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {
            "success": True,
            "review_queue_id": str(result.inserted_id),
            "message": f"Added to manual review queue with {priority} priority"
        }
    
    @staticmethod
    def get_pending_reviews(reviewer_id: str = None, priority: str = None, limit: int = 50) -> list:
        """
        Get pending reviews for a reviewer or all pending
        """
        query = {"status": "pending"}
        
        if reviewer_id:
            query["assigned_to"] = reviewer_id
        
        if priority:
            query["priority"] = priority
        
        reviews = db["ManualReviewQueue"].find(query).sort([
            ("priority_score", 1),  # Lower priority_score = higher priority
            ("created_at", 1)       # Older first
        ]).limit(limit)
        
        review_list = []
        for review in reviews:
            # Get verification details
            verification = db["KYCVerificationRequests"].find_one({"_id": ObjectId(review['verification_id'])})
            
            review_list.append({
                "review_id": str(review['_id']),
                "verification_id": review['verification_id'],
                "user_id": review['user_id'],
                "reason": review['reason'],
                "priority": review['priority'],
                "created_at": review['created_at'].isoformat(),
                "identity_score": review.get('identity_score', 0),
                "risk_score": review.get('risk_score', 0),
                "anomalies": review.get('anomalies', []),
                "waiting_time_minutes": int((datetime.utcnow() - review['created_at']).total_seconds() / 60)
            })
        
        return review_list
    
    @staticmethod
    def assign_review(review_id: str, reviewer_id: str, reviewer_name: str) -> dict:
        """
        Assign review to a specific reviewer
        """
        result = db["ManualReviewQueue"].update_one(
            {"_id": ObjectId(review_id), "status": "pending"},
            {
                "$set": {
                    "assigned_to": reviewer_id,
                    "assigned_to_name": reviewer_name,
                    "assigned_at": datetime.utcnow(),
                    "status": "in_review"
                }
            }
        )
        
        if result.modified_count > 0:
            return {"success": True, "message": f"Review assigned to {reviewer_name}"}
        else:
            return {"success": False, "error": "Review not found or already assigned"}
    
    @staticmethod
    def complete_review(review_id: str, decision: str, reviewer_notes: str, reviewer_id: str) -> dict:
        """
        Complete manual review with decision
        decision: "approved", "rejected", "request_more_info"
        """
        if decision not in ["approved", "rejected", "request_more_info"]:
            return {"error": "Invalid decision. Must be: approved, rejected, or request_more_info"}
        
        review = db["ManualReviewQueue"].find_one({"_id": ObjectId(review_id)})
        if not review:
            return {"error": "Review not found"}
        
        # Update review task
        db["ManualReviewQueue"].update_one(
            {"_id": ObjectId(review_id)},
            {
                "$set": {
                    "status": "completed",
                    "review_decision": decision,
                    "reviewer_notes": reviewer_notes,
                    "reviewed_at": datetime.utcnow(),
                    "reviewed_by": reviewer_id,
                    "review_duration_minutes": int((datetime.utcnow() - review.get('assigned_at', datetime.utcnow())).total_seconds() / 60)
                }
            }
        )
        
        # Update verification status
        verification_status = {
            "approved": "approved",
            "rejected": "rejected",
            "request_more_info": "additional_info_required"
        }[decision]
        
        db["KYCVerificationRequests"].update_one(
            {"_id": ObjectId(review['verification_id'])},
            {
                "$set": {
                    "status": verification_status,
                    "manual_review_decision": decision,
                    "manual_review_notes": reviewer_notes,
                    "manual_reviewed_at": datetime.utcnow(),
                    "manual_reviewed_by": reviewer_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # If approved, proceed to credential issuance
        if decision == "approved":
            # Trigger credential issuance
            pass  # Will be handled by credential service
        
        return {
            "success": True,
            "verification_id": review['verification_id'],
            "decision": decision,
            "message": f"Review completed: {decision}"
        }
    
    @staticmethod
    def get_review_statistics() -> dict:
        """
        Get statistics for monitoring review queue health
        """
        total_pending = db["ManualReviewQueue"].count_documents({"status": "pending"})
        total_in_review = db["ManualReviewQueue"].count_documents({"status": "in_review"})
        total_completed_today = db["ManualReviewQueue"].count_documents({
            "status": "completed",
            "reviewed_at": {"$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
        })
        
        # Average review time
        completed_reviews = db["ManualReviewQueue"].find({
            "status": "completed",
            "review_duration_minutes": {"$exists": True}
        })
        
        avg_review_time = 0
        review_count = 0
        for review in completed_reviews:
            avg_review_time += review.get('review_duration_minutes', 0)
            review_count += 1
        
        avg_review_time = avg_review_time / review_count if review_count > 0 else 0
        
        # Approval rate
        approved_count = db["ManualReviewQueue"].count_documents({"review_decision": "approved"})
        rejected_count = db["ManualReviewQueue"].count_documents({"review_decision": "rejected"})
        total_reviewed = approved_count + rejected_count
        approval_rate = (approved_count / total_reviewed * 100) if total_reviewed > 0 else 0
        
        return {
            "queue_health": {
                "pending_reviews": total_pending,
                "in_progress": total_in_review,
                "completed_today": total_completed_today,
                "avg_review_time_minutes": round(avg_review_time, 1)
            },
            "decisions": {
                "total_reviewed": total_reviewed,
                "approved": approved_count,
                "rejected": rejected_count,
                "approval_rate": round(approval_rate, 1)
            },
            "alerts": {
                "queue_backlog": total_pending > 100,
                "slow_reviews": avg_review_time > 30
            }
        }
    
    @staticmethod
    def escalate_review(review_id: str, escalation_reason: str) -> dict:
        """
        Escalate review to senior reviewer or fraud team
        """
        db["ManualReviewQueue"].update_one(
            {"_id": ObjectId(review_id)},
            {
                "$set": {
                    "priority": "urgent",
                    "priority_score": 1,
                    "escalated": True,
                    "escalation_reason": escalation_reason,
                    "escalated_at": datetime.utcnow()
                }
            }
        )
        
        return {"success": True, "message": "Review escalated to urgent priority"}
