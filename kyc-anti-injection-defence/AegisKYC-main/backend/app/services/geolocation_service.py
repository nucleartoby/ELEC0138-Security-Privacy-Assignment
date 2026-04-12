"""
Geolocation Verification Service
Validates user location consistency across IP, GPS, and declared address
"""

import requests
from datetime import datetime
from typing import Dict, Optional
import os

class GeolocationService:
    """
    Verifies location consistency to detect:
    - VPN usage
    - GPS spoofing
    - Cross-border fraud attempts
    - Location mismatch with declared address
    """
    
    def __init__(self):
        # Free IP geolocation APIs (no key required for basic features)
        self.ip_api_url = "http://ip-api.com/json/"
        self.backup_api_url = "https://ipapi.co/{ip}/json/"
    
    def get_ip_location(self, ip_address: str) -> Dict:
        """
        Get location from IP address
        Returns: country, region, city, lat, lon, timezone, isp
        """
        try:
            # Try primary API (ip-api.com - free, no key needed)
            response = requests.get(f"{self.ip_api_url}{ip_address}", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    return {
                        "success": True,
                        "ip": ip_address,
                        "country": data.get('country'),
                        "country_code": data.get('countryCode'),
                        "region": data.get('regionName'),
                        "city": data.get('city'),
                        "zip": data.get('zip'),
                        "lat": data.get('lat'),
                        "lon": data.get('lon'),
                        "timezone": data.get('timezone'),
                        "isp": data.get('isp'),
                        "org": data.get('org'),
                        "as": data.get('as'),  # Autonomous System
                        "mobile": data.get('mobile', False),
                        "proxy": data.get('proxy', False),
                        "hosting": data.get('hosting', False)
                    }
        except Exception as e:
            print(f"IP geolocation failed: {e}")
        
        return {
            "success": False,
            "ip": ip_address,
            "error": "Unable to determine location from IP"
        }
    
    def verify_location_consistency(
        self, 
        ip_address: str,
        gps_coords: Optional[Dict] = None,
        declared_address: Optional[Dict] = None
    ) -> Dict:
        """
        Verify location consistency across multiple sources
        
        Args:
            ip_address: User's IP address
            gps_coords: {"latitude": float, "longitude": float} from device
            declared_address: {"city": str, "state": str, "country": str, "pincode": str}
        
        Returns:
            {
                "is_consistent": bool,
                "risk_level": "low" | "medium" | "high",
                "risk_score": float (0-100),
                "flags": list of detected anomalies,
                "details": location info
            }
        """
        result = {
            "is_consistent": True,
            "risk_level": "low",
            "risk_score": 0,
            "flags": [],
            "ip_location": {},
            "gps_location": gps_coords or {},
            "declared_location": declared_address or {},
            "verification_timestamp": datetime.utcnow().isoformat()
        }
        
        # Get IP-based location
        ip_location = self.get_ip_location(ip_address)
        result["ip_location"] = ip_location
        
        if not ip_location.get('success'):
            result["flags"].append("Unable to verify IP location")
            result["risk_score"] += 10
        else:
            # Check for VPN/Proxy
            if ip_location.get('proxy'):
                result["flags"].append("VPN or proxy detected")
                result["risk_score"] += 30
                result["is_consistent"] = False
            
            # Check for hosting provider (datacenter IP)
            if ip_location.get('hosting'):
                result["flags"].append("Datacenter IP detected (possible bot)")
                result["risk_score"] += 25
                result["is_consistent"] = False
            
            # Check country mismatch with declared address
            if declared_address and declared_address.get('country'):
                declared_country = declared_address.get('country', '').upper()
                ip_country = ip_location.get('country_code', '').upper()
                
                # India variations
                if declared_country in ['INDIA', 'IN', 'IND'] and ip_country != 'IN':
                    result["flags"].append(f"IP country ({ip_location.get('country')}) doesn't match declared country (India)")
                    result["risk_score"] += 40
                    result["is_consistent"] = False
                elif declared_country not in ['INDIA', 'IN', 'IND'] and ip_country != declared_country:
                    result["flags"].append(f"Country mismatch: IP={ip_location.get('country')}, Declared={declared_address.get('country')}")
                    result["risk_score"] += 40
                    result["is_consistent"] = False
            
            # Check state/city mismatch
            if declared_address and declared_address.get('state'):
                ip_state = ip_location.get('region', '').lower()
                declared_state = declared_address.get('state', '').lower()
                
                # Fuzzy match (handle abbreviations like "MH" vs "Maharashtra")
                if declared_state not in ip_state and ip_state not in declared_state:
                    # Only flag if countries match (same country but different state = suspicious)
                    if ip_location.get('country_code') == 'IN' or declared_address.get('country', '').upper() in ['INDIA', 'IN']:
                        result["flags"].append(f"State mismatch: IP={ip_location.get('region')}, Declared={declared_address.get('state')}")
                        result["risk_score"] += 15
        
        # GPS verification (if available)
        if gps_coords and gps_coords.get('latitude') and gps_coords.get('longitude'):
            gps_lat = gps_coords.get('latitude')
            gps_lon = gps_coords.get('longitude')
            
            # Check if GPS is significantly different from IP location
            if ip_location.get('success'):
                ip_lat = ip_location.get('lat')
                ip_lon = ip_location.get('lon')
                
                if ip_lat and ip_lon:
                    # Calculate distance (rough approximation)
                    distance_km = self._calculate_distance(ip_lat, ip_lon, gps_lat, gps_lon)
                    result["distance_km"] = distance_km
                    
                    # Flag if GPS is >100km away from IP location
                    if distance_km > 100:
                        result["flags"].append(f"GPS location is {distance_km:.0f}km away from IP location")
                        result["risk_score"] += 20
                    
                    # Extreme distance (>500km) = likely spoofing
                    if distance_km > 500:
                        result["flags"].append("Extreme GPS/IP mismatch - possible GPS spoofing")
                        result["risk_score"] += 30
                        result["is_consistent"] = False
        
        # Determine risk level
        if result["risk_score"] >= 50:
            result["risk_level"] = "high"
        elif result["risk_score"] >= 25:
            result["risk_level"] = "medium"
        else:
            result["risk_level"] = "low"
        
        return result
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula
        Returns distance in kilometers
        """
        from math import radians, sin, cos, sqrt, atan2
        
        # Earth radius in km
        R = 6371
        
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)
        
        a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c
    
    def get_timezone_mismatch(self, declared_timezone: str, ip_timezone: str) -> bool:
        """
        Check if declared timezone matches IP timezone
        Helps detect VPN usage
        """
        # Normalize timezone strings
        declared = declared_timezone.lower().replace('_', ' ')
        ip_tz = ip_timezone.lower().replace('_', ' ')
        
        # Allow for slight variations (e.g., "Asia/Kolkata" vs "Asia/Calcutta")
        if 'kolkata' in declared or 'calcutta' in declared:
            return 'kolkata' not in ip_tz and 'calcutta' not in ip_tz
        
        return declared != ip_tz
