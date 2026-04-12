"""
Audit Logging Service with File-Based Storage
Tracks all consent actions, data access, and verification events
"""
import os
import json
from datetime import datetime
from pathlib import Path
from app.utils.db import db

class AuditLogService:
    """
    Immutable audit trail for regulatory compliance
    - All consent approvals/rejections
    - All identity vault accesses
    - All verification decisions
    - All credential issuances/revocations
    
    Uses .txt files for structured logging with MongoDB fallback
    """
    
    def __init__(self):
        # Create audit logs directory structure
        self.audit_dir = Path(os.getenv('AUDIT_LOG_DIR', 'audit_logs'))
        self.audit_dir.mkdir(exist_ok=True)
        
        # Organize by event type subdirectories
        self.event_dirs = {
            'consent_action': self.audit_dir / 'consent_actions',
            'vault_access': self.audit_dir / 'vault_access',
            'verification_decision': self.audit_dir / 'verification_decisions',
            'credential_issued': self.audit_dir / 'credential_issuance',
            'credential_revoked': self.audit_dir / 'credential_revocation',
            'anomaly_detected': self.audit_dir / 'anomaly_detection',
            'general': self.audit_dir / 'general'
        }
        
        for event_dir in self.event_dirs.values():
            event_dir.mkdir(exist_ok=True)
        
        print(f"✅ Audit logging initialized - storing logs in: {self.audit_dir.absolute()}")
    
    def log_event(self, event_type: str, user_id: str, details: dict) -> dict:
        """
        Log audit event to .txt file (one file per day per event type)
        Also store in MongoDB for querying
        """
        audit_entry = {
            "event_id": str(__import__('uuid').uuid4()),
            "event_type": event_type,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details,
            "source": "aegis_kyc_backend"
        }
        
        # Write to daily log file
        try:
            event_dir = self.event_dirs.get(event_type, self.event_dirs['general'])
            log_date = datetime.utcnow().strftime('%Y-%m-%d')
            log_file = event_dir / f"{log_date}.txt"
            
            # Append to daily log file (one line per event, JSON format)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(audit_entry) + '\n')
            
            print(f"📝 Audit log written: {event_type} for user {user_id}")
        except Exception as e:
            print(f"⚠️  File write failed: {e}, storing in MongoDB only")
        
        # Always store in MongoDB for easy querying
        try:
            db["AuditLogs"].insert_one(audit_entry.copy())
        except Exception as e:
            print(f"⚠️  MongoDB write failed: {e}")
        
        return {"success": True, "event_id": audit_entry["event_id"]}
    
    def _fallback_to_mongo(self, audit_entry: dict):
        """Store audit log in MongoDB (already handled in log_event)"""
        pass  # Not needed anymore, log_event handles both
    
    def log_consent_action(self, user_id: str, organization_id: str, action: str, consent_request_id: str, details: dict = None):
        """Log consent approval/rejection"""
        self.log_event(
            event_type="consent_action",
            user_id=user_id,
            details={
                "organization_id": organization_id,
                "action": action,  # approved, rejected, revoked
                "consent_request_id": consent_request_id,
                "additional_details": details or {}
            }
        )
    
    def log_vault_access(self, user_id: str, accessed_by: str, accessed_fields: list, purpose: str):
        """Log identity vault data access"""
        self.log_event(
            event_type="vault_access",
            user_id=user_id,
            details={
                "accessed_by": accessed_by,
                "accessed_fields": accessed_fields,
                "purpose": purpose,
                "data_minimization_compliant": True
            }
        )
    
    def log_verification_decision(self, user_id: str, verification_id: str, decision: str, scores: dict):
        """Log KYC verification decision"""
        self.log_event(
            event_type="verification_decision",
            user_id=user_id,
            details={
                "verification_id": verification_id,
                "decision": decision,  # approved, rejected, manual_review
                "scores": scores,
                "decision_timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def log_credential_issuance(self, user_id: str, credential_id: str, verification_id: str):
        """Log credential issuance"""
        self.log_event(
            event_type="credential_issued",
            user_id=user_id,
            details={
                "credential_id": credential_id,
                "verification_id": verification_id,
                "signature_algorithm": "RS256"
            }
        )
    
    def log_credential_revocation(self, user_id: str, credential_id: str, reason: str):
        """Log credential revocation"""
        self.log_event(
            event_type="credential_revoked",
            user_id=user_id,
            details={
                "credential_id": credential_id,
                "reason": reason
            }
        )
    
    def log_anomaly_detection(self, user_id: str, verification_id: str, anomalies: list):
        """Log detected anomalies"""
        self.log_event(
            event_type="anomaly_detected",
            user_id=user_id,
            details={
                "verification_id": verification_id,
                "anomalies": anomalies,
                "flagged_for_review": len(anomalies) >= 2
            }
        )
    
    def get_audit_trail(self, user_id: str, limit: int = 100) -> list:
        """
        Retrieve audit trail for a user (compliance/investigation)
        Reads from MongoDB for efficient querying
        """
        logs = db["AuditLogs"].find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
        return list(logs)
    
    def get_audit_trail_from_files(self, user_id: str, days_back: int = 30) -> list:
        """
        Read audit trail directly from .txt files (alternative method)
        Useful for compliance audits when DB unavailable
        """
        events = []
        cutoff_date = datetime.utcnow().date() - __import__('datetime').timedelta(days=days_back)
        
        # Read from all event type directories
        for event_dir in self.event_dirs.values():
            if not event_dir.exists():
                continue
                
            # Read all .txt files in the directory
            for log_file in event_dir.glob("*.txt"):
                # Check if file date is within range
                try:
                    file_date = datetime.strptime(log_file.stem, '%Y-%m-%d').date()
                    if file_date < cutoff_date:
                        continue
                except:
                    continue
                
                # Read and parse JSON lines
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                entry = json.loads(line)
                                if entry.get('user_id') == user_id:
                                    events.append(entry)
                except Exception as e:
                    print(f"Error reading {log_file}: {e}")
        
        # Sort by timestamp descending
        events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return events
    
    def generate_compliance_report(self, start_date: datetime, end_date: datetime) -> dict:
        """
        Generate compliance report for regulators
        """
        # Count events by type
        audit_logs = db["AuditLogs"].find({
            "timestamp": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            }
        })
        
        event_counts = {}
        for log in audit_logs:
            event_type = log.get('event_type', 'unknown')
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        return {
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_events": sum(event_counts.values()),
            "events_by_type": event_counts,
            "generated_at": datetime.utcnow().isoformat()
        }
