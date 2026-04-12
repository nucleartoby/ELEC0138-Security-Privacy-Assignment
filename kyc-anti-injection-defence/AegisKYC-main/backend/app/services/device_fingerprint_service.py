"""
Device Fingerprinting Service
Creates unique device signatures to detect account sharing, bot farms, and fraud rings
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, Optional
from app.utils.db import db

class DeviceFingerprintService:
    """
    Generates and validates device fingerprints to:
    - Detect returning users on trusted devices
    - Identify suspicious device reuse across multiple accounts
    - Flag bot farms using similar device signatures
    - Build device trust scores over time
    """
    
    def generate_fingerprint(self, device_data: Dict) -> str:
        """
        Generate unique device fingerprint from browser/device characteristics
        
        Args:
            device_data: {
                "user_agent": str,
                "screen_resolution": str (e.g., "1920x1080"),
                "timezone": str,
                "language": str,
                "platform": str,
                "cpu_cores": int,
                "device_memory": int (GB),
                "canvas_hash": str (canvas fingerprinting),
                "webgl_vendor": str,
                "webgl_renderer": str,
                "fonts": list (installed fonts),
                "plugins": list (browser plugins),
                "do_not_track": bool,
                "touch_support": bool
            }
        
        Returns:
            32-character hex fingerprint
        """
        # Create stable signature from device characteristics
        signature_parts = [
            device_data.get('user_agent', ''),
            device_data.get('screen_resolution', ''),
            device_data.get('timezone', ''),
            device_data.get('language', ''),
            device_data.get('platform', ''),
            str(device_data.get('cpu_cores', 0)),
            str(device_data.get('device_memory', 0)),
            device_data.get('canvas_hash', ''),
            device_data.get('webgl_vendor', ''),
            device_data.get('webgl_renderer', ''),
            ','.join(sorted(device_data.get('fonts', []))),
            ','.join(sorted(device_data.get('plugins', [])))
        ]
        
        # Combine all parts
        combined = '|'.join(signature_parts)
        
        # Generate SHA-256 hash
        fingerprint = hashlib.sha256(combined.encode('utf-8')).hexdigest()[:32]
        
        return fingerprint
    
    def analyze_device_trust(
        self,
        fingerprint: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict:
        """
        Analyze device trustworthiness based on historical usage
        
        Returns:
            {
                "trust_score": float (0-100),
                "is_new_device": bool,
                "previous_users_count": int (how many users used this device),
                "suspicious_patterns": list,
                "first_seen": datetime,
                "last_seen": datetime,
                "total_sessions": int
            }
        """
        result = {
            "fingerprint": fingerprint,
            "trust_score": 50,  # Neutral starting score
            "is_new_device": True,
            "previous_users_count": 0,
            "suspicious_patterns": [],
            "first_seen": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat(),
            "total_sessions": 0
        }
        
        # Check if device has been seen before
        device_history = db["DeviceFingerprints"].find_one({"fingerprint": fingerprint})
        
        if device_history:
            result["is_new_device"] = False
            result["first_seen"] = device_history.get('first_seen', datetime.utcnow().isoformat())
            result["total_sessions"] = device_history.get('total_sessions', 0)
            result["previous_users_count"] = len(device_history.get('user_ids', []))
            
            # Calculate trust score based on history
            trust_score = 50
            
            # Bonus for returning devices
            if result["total_sessions"] > 0:
                trust_score += min(result["total_sessions"] * 2, 20)  # Up to +20 for session history
            
            # Check for device sharing across multiple accounts
            if result["previous_users_count"] > 1:
                result["suspicious_patterns"].append(f"Device used by {result['previous_users_count']} different users")
                trust_score -= result["previous_users_count"] * 10  # -10 per additional user
            
            # Check for rapid account creation from same device
            recent_users = device_history.get('recent_user_timestamps', [])
            if len(recent_users) > 3:
                # More than 3 accounts in short time = suspicious
                result["suspicious_patterns"].append("Rapid account creation pattern detected")
                trust_score -= 25
            
            # Check IP consistency
            if ip_address and device_history.get('ip_addresses'):
                unique_ips = len(set(device_history.get('ip_addresses', [])))
                if unique_ips > 10:
                    result["suspicious_patterns"].append(f"Device used from {unique_ips} different IP addresses")
                    trust_score -= 15
            
            # Cap trust score
            result["trust_score"] = max(0, min(100, trust_score))
            
            # Update device history
            db["DeviceFingerprints"].update_one(
                {"fingerprint": fingerprint},
                {
                    "$set": {
                        "last_seen": datetime.utcnow().isoformat(),
                        "trust_score": result["trust_score"]
                    },
                    "$inc": {"total_sessions": 1},
                    "$addToSet": {
                        "user_ids": user_id,
                        "ip_addresses": ip_address
                    } if user_id else {},
                    "$push": {
                        "recent_user_timestamps": {
                            "$each": [{"user_id": user_id, "timestamp": datetime.utcnow().isoformat()}],
                            "$slice": -10  # Keep last 10
                        }
                    } if user_id else {}
                }
            )
        else:
            # New device - create record
            db["DeviceFingerprints"].insert_one({
                "fingerprint": fingerprint,
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat(),
                "total_sessions": 1,
                "user_ids": [user_id] if user_id else [],
                "ip_addresses": [ip_address] if ip_address else [],
                "trust_score": 50,
                "recent_user_timestamps": [{"user_id": user_id, "timestamp": datetime.utcnow().isoformat()}] if user_id else []
            })
            
            # New devices get slight penalty
            result["trust_score"] = 45
        
        return result
    
    def detect_bot_farm(self, fingerprint: str) -> Dict:
        """
        Detect if device is part of a bot farm based on:
        - Identical fingerprints across many accounts
        - Sequential account creation patterns
        - Uniform device characteristics (scripted automation)
        """
        device = db["DeviceFingerprints"].find_one({"fingerprint": fingerprint})
        
        if not device:
            return {"is_bot_farm": False, "confidence": 0}
        
        bot_indicators = []
        confidence = 0
        
        # Check: Too many users on same device
        user_count = len(device.get('user_ids', []))
        if user_count > 5:
            bot_indicators.append(f"{user_count} accounts on single device")
            confidence += 30
        
        # Check: Rapid sequential creation
        timestamps = device.get('recent_user_timestamps', [])
        if len(timestamps) >= 3:
            # Check if accounts created within minutes of each other
            times = [datetime.fromisoformat(t['timestamp']) for t in timestamps if t.get('timestamp')]
            if len(times) >= 2:
                time_diffs = [(times[i+1] - times[i]).total_seconds() / 60 for i in range(len(times)-1)]
                avg_diff = sum(time_diffs) / len(time_diffs) if time_diffs else 0
                
                if avg_diff < 10:  # Average <10 minutes between accounts
                    bot_indicators.append(f"Accounts created {avg_diff:.1f} minutes apart (automated)")
                    confidence += 40
        
        # Check: Too many IPs (device moving around suspiciously)
        ip_count = len(device.get('ip_addresses', []))
        if ip_count > 20:
            bot_indicators.append(f"Used from {ip_count} different IPs")
            confidence += 20
        
        is_bot_farm = confidence >= 50
        
        return {
            "is_bot_farm": is_bot_farm,
            "confidence": min(100, confidence),
            "indicators": bot_indicators,
            "device_user_count": user_count,
            "recommendation": "manual_review" if is_bot_farm else "auto_proceed"
        }
