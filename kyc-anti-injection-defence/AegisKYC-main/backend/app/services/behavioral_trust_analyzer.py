"""
Behavioral Trust Model
Detects bot behavior, coached attempts, and natural human patterns
Tracks: typing rhythm, mouse movement, form filling speed, device handling
"""
import numpy as np
from datetime import datetime
from statistics import mean, stdev
from app.utils.db import db

class BehavioralTrustAnalyzer:
    """
    Analyze user behavior during KYC to detect:
    - Bot-assisted form filling
    - Coached attempts (someone guiding the user)
    - Unnatural typing patterns
    - Copy-paste vs manual typing
    - Device handling anomalies
    """
    
    # Normal human typing speed: 40-80 WPM (200-400 ms per character)
    HUMAN_TYPING_SPEED_MS = {"min": 100, "max": 600, "mean": 250}
    
    # Bot detection thresholds
    BOT_INDICATORS = {
        "uniform_typing_speed": 0.9,  # Typing speed variance < 10% → bot
        "instant_paste": 30,           # >30% fields pasted → suspicious
        "superhuman_speed": 80,        # < 80ms avg per char → bot
        "no_corrections": 0.95,        # >95% no backspace/corrections → bot
        "linear_mouse_movement": 0.85  # >85% straight lines → bot
    }
    
    @staticmethod
    def analyze_typing_pattern(keystroke_data: list) -> dict:
        """
        Analyze keystroke dynamics
        keystroke_data: [{"key": "a", "timestamp": 1234567890, "event": "keydown"}, ...]
        """
        if not keystroke_data or len(keystroke_data) < 10:
            return {"insufficient_data": True, "trust_score": 50}
        
        # Calculate inter-keystroke intervals
        intervals = []
        for i in range(1, len(keystroke_data)):
            if keystroke_data[i]['event'] == 'keydown':
                interval = keystroke_data[i]['timestamp'] - keystroke_data[i-1]['timestamp']
                intervals.append(interval)
        
        if not intervals:
            return {"insufficient_data": True, "trust_score": 50}
        
        avg_interval = mean(intervals)
        std_deviation = stdev(intervals) if len(intervals) > 1 else 0
        
        # Calculate coefficient of variation (CV)
        cv = (std_deviation / avg_interval) if avg_interval > 0 else 0
        
        # Bot detection flags
        is_uniform = cv < 0.1  # Very consistent = bot
        is_superhuman = avg_interval < BehavioralTrustAnalyzer.BOT_INDICATORS["superhuman_speed"]
        is_natural = 100 < avg_interval < 600 and cv > 0.15
        
        # Count corrections (backspace, delete)
        corrections = sum(1 for k in keystroke_data if k.get('key') in ['Backspace', 'Delete'])
        correction_rate = corrections / len(keystroke_data)
        no_corrections = correction_rate < 0.05  # <5% corrections is suspicious
        
        # Calculate trust score
        trust_score = 100
        if is_uniform:
            trust_score -= 30
        if is_superhuman:
            trust_score -= 40
        if no_corrections:
            trust_score -= 20
        if is_natural:
            trust_score += 10
        
        return {
            "avg_typing_interval_ms": round(avg_interval, 2),
            "typing_variance": round(cv, 3),
            "is_uniform_typing": is_uniform,
            "is_superhuman_speed": is_superhuman,
            "correction_rate": round(correction_rate, 3),
            "trust_score": max(0, min(100, trust_score)),
            "flags": {
                "bot_like_uniformity": is_uniform,
                "superhuman_speed": is_superhuman,
                "minimal_corrections": no_corrections
            }
        }
    
    @staticmethod
    def analyze_paste_behavior(field_events: dict) -> dict:
        """
        Detect copy-paste vs manual typing
        field_events: {"field_name": {"typed": True/False, "pasted": True/False, "time_spent_ms": 1000}}
        """
        total_fields = len(field_events)
        if total_fields == 0:
            return {"insufficient_data": True, "trust_score": 50}
        
        pasted_count = sum(1 for f in field_events.values() if f.get('pasted'))
        paste_percentage = (pasted_count / total_fields) * 100
        
        # Pasting is normal for some fields (email, address), but not for name/DOB
        critical_fields = ['full_name', 'father_name', 'mother_name', 'date_of_birth']
        critical_pasted = sum(1 for field, data in field_events.items() 
                             if field in critical_fields and data.get('pasted'))
        
        trust_score = 100
        if paste_percentage > 50:
            trust_score -= 20
        if paste_percentage > 70:
            trust_score -= 30
        if critical_pasted > 0:
            trust_score -= 25  # Pasting name/DOB is very suspicious
        
        return {
            "total_fields": total_fields,
            "pasted_fields": pasted_count,
            "paste_percentage": round(paste_percentage, 1),
            "critical_fields_pasted": critical_pasted,
            "trust_score": max(0, min(100, trust_score)),
            "flags": {
                "excessive_pasting": paste_percentage > 50,
                "critical_field_paste": critical_pasted > 0
            }
        }
    
    @staticmethod
    def analyze_mouse_movement(mouse_events: list) -> dict:
        """
        Detect bot-like linear mouse movements vs natural human curves
        mouse_events: [{"x": 100, "y": 200, "timestamp": 123456}, ...]
        """
        if not mouse_events or len(mouse_events) < 20:
            return {"insufficient_data": True, "trust_score": 50}
        
        # Calculate path linearity (ratio of direct distance to actual path)
        linear_segments = 0
        total_segments = len(mouse_events) - 1
        
        for i in range(1, len(mouse_events)):
            dx = mouse_events[i]['x'] - mouse_events[i-1]['x']
            dy = mouse_events[i]['y'] - mouse_events[i-1]['y']
            
            # Check if movement is too straight (bot-like)
            if abs(dx) < 5 or abs(dy) < 5:  # Perfect horizontal/vertical
                linear_segments += 1
        
        linearity_ratio = linear_segments / total_segments if total_segments > 0 else 0
        
        trust_score = 100
        if linearity_ratio > 0.7:
            trust_score -= 30  # Very linear = bot
        if linearity_ratio > 0.85:
            trust_score -= 40
        
        return {
            "total_movements": len(mouse_events),
            "linear_movements": linear_segments,
            "linearity_ratio": round(linearity_ratio, 3),
            "trust_score": max(0, min(100, trust_score)),
            "flags": {
                "bot_like_movement": linearity_ratio > 0.7
            }
        }
    
    @staticmethod
    def analyze_form_filling_speed(form_start_time: int, form_submit_time: int, field_count: int) -> dict:
        """
        Detect unnaturally fast or slow form completion
        """
        time_spent_ms = form_submit_time - form_start_time
        time_spent_seconds = time_spent_ms / 1000
        time_per_field_seconds = time_spent_seconds / field_count if field_count > 0 else 0
        
        # Normal human: 5-15 seconds per field (reading + typing)
        is_too_fast = time_per_field_seconds < 3  # Bot or coached
        is_too_slow = time_per_field_seconds > 60  # Suspicious delay
        is_natural = 5 <= time_per_field_seconds <= 20
        
        trust_score = 100
        if is_too_fast:
            trust_score -= 35
        if is_too_slow:
            trust_score -= 15
        if is_natural:
            trust_score += 5
        
        return {
            "total_time_seconds": round(time_spent_seconds, 1),
            "time_per_field_seconds": round(time_per_field_seconds, 1),
            "field_count": field_count,
            "is_too_fast": is_too_fast,
            "is_too_slow": is_too_slow,
            "trust_score": max(0, min(100, trust_score)),
            "flags": {
                "unnaturally_fast": is_too_fast,
                "unusually_slow": is_too_slow
            }
        }
    
    @staticmethod
    def calculate_overall_behavioral_trust(verification_id: str, behavior_data: dict) -> dict:
        """
        Combine all behavioral signals into final trust score
        """
        # Extract individual scores
        typing_score = behavior_data.get('typing_analysis', {}).get('trust_score', 70)
        paste_score = behavior_data.get('paste_analysis', {}).get('trust_score', 70)
        mouse_score = behavior_data.get('mouse_analysis', {}).get('trust_score', 70)
        speed_score = behavior_data.get('speed_analysis', {}).get('trust_score', 70)
        
        # Weighted average
        overall_score = (
            typing_score * 0.35 +
            paste_score * 0.25 +
            mouse_score * 0.20 +
            speed_score * 0.20
        )
        
        # Aggregate all flags
        all_flags = []
        for analysis in behavior_data.values():
            if isinstance(analysis, dict) and 'flags' in analysis:
                for flag, value in analysis['flags'].items():
                    if value:
                        all_flags.append(flag)
        
        # Determine bot likelihood
        bot_likelihood = max(0, 100 - overall_score)
        
        # Store in verification record
        db["KYCVerificationRequests"].update_one(
            {"_id": __import__('bson').ObjectId(verification_id)},
            {
                "$set": {
                    "behavioral_trust": {
                        "overall_trust_score": round(overall_score, 1),
                        "bot_likelihood": round(bot_likelihood, 1),
                        "flags": all_flags,
                        "typing_score": typing_score,
                        "paste_score": paste_score,
                        "mouse_score": mouse_score,
                        "speed_score": speed_score,
                        "analyzed_at": datetime.utcnow()
                    }
                }
            }
        )
        
        return {
            "verification_id": verification_id,
            "overall_trust_score": round(overall_score, 1),
            "bot_likelihood": round(bot_likelihood, 1),
            "risk_level": "high" if bot_likelihood > 50 else "medium" if bot_likelihood > 25 else "low",
            "flags_detected": all_flags,
            "recommendation": "manual_review" if bot_likelihood > 40 else "auto_approve" if overall_score > 80 else "standard_flow"
        }
