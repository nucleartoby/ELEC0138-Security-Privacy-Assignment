"""
Test script to demonstrate file-based audit logging
Run this to see how audit logs are created
"""

from app.services.audit_log_service import AuditLogService
from datetime import datetime

def test_audit_logging():
    print("=" * 60)
    print("Testing File-Based Audit Logging System")
    print("=" * 60)
    
    # Initialize audit service
    audit_service = AuditLogService()
    
    # Test 1: Log consent action
    print("\n1. Logging consent action...")
    audit_service.log_consent_action(
        user_id="691c6b3fd63c7a092591b82c",
        organization_id="org_hdfc_bank",
        action="approved",
        consent_request_id="consent_12345",
        details={
            "requested_fields": ["full_name", "aadhaar_number", "pan_number"],
            "purpose": "Account opening verification",
            "approved_at": datetime.utcnow().isoformat()
        }
    )
    
    # Test 2: Log vault access
    print("\n2. Logging vault access...")
    audit_service.log_vault_access(
        user_id="691c6b3fd63c7a092591b82c",
        accessed_by="org_hdfc_bank",
        accessed_fields=["full_name", "aadhaar_number"],
        purpose="KYC verification for savings account"
    )
    
    # Test 3: Log verification decision
    print("\n3. Logging verification decision...")
    audit_service.log_verification_decision(
        user_id="691c6b3fd63c7a092591b82c",
        verification_id="verify_789",
        decision="approved",
        scores={
            "document_authenticity": 85.5,
            "face_match": 92.3,
            "liveness": 88.7,
            "overall": 88.8
        }
    )
    
    # Test 4: Log credential issuance
    print("\n4. Logging credential issuance...")
    audit_service.log_credential_issuance(
        user_id="691c6b3fd63c7a092591b82c",
        credential_id="KYC-476648C794836399",
        verification_id="verify_789"
    )
    
    # Test 5: Log anomaly detection
    print("\n5. Logging anomaly detection...")
    audit_service.log_anomaly_detection(
        user_id="691c6b3fd63c7a092591b82c",
        verification_id="verify_789",
        anomalies=[
            "Document upload from different device",
            "Unusual time of day (3:00 AM)"
        ]
    )
    
    print("\n" + "=" * 60)
    print("✅ All audit logs created successfully!")
    print("=" * 60)
    
    # Show where logs are stored
    import os
    from pathlib import Path
    
    audit_dir = Path(os.getenv('AUDIT_LOG_DIR', 'audit_logs'))
    print(f"\n📂 Audit logs directory: {audit_dir.absolute()}")
    print("\n📁 Log file structure:")
    
    if audit_dir.exists():
        for subdir in sorted(audit_dir.iterdir()):
            if subdir.is_dir():
                print(f"  └── {subdir.name}/")
                for log_file in sorted(subdir.glob("*.txt")):
                    # Get file size
                    size = log_file.stat().st_size
                    print(f"      └── {log_file.name} ({size} bytes)")
    
    # Test retrieval
    print("\n" + "=" * 60)
    print("Testing Audit Trail Retrieval")
    print("=" * 60)
    
    # From MongoDB (fast)
    print("\n🔍 Retrieving from MongoDB:")
    trail = audit_service.get_audit_trail("691c6b3fd63c7a092591b82c", limit=10)
    print(f"  Found {len(trail)} events")
    for event in trail[:3]:  # Show first 3
        print(f"  - {event.get('event_type')}: {event.get('timestamp')}")
    
    # From files (compliance/forensics)
    print("\n🔍 Retrieving from .txt files:")
    trail_from_files = audit_service.get_audit_trail_from_files(
        "691c6b3fd63c7a092591b82c", 
        days_back=7
    )
    print(f"  Found {len(trail_from_files)} events from files")
    for event in trail_from_files[:3]:  # Show first 3
        print(f"  - {event.get('event_type')}: {event.get('timestamp')}")
    
    print("\n" + "=" * 60)
    print("✅ Audit logging test complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_audit_logging()
