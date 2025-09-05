"""
YMERA Enterprise - Security Analysis System
Production-Ready Security Analytics & Threat Detection - v4.0
Enterprise-grade implementation with zero placeholders
"""

# Standard library imports
import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from ipaddress import ip_address, ip_network, AddressValueError

# Third-party imports
import structlog
import aioredis
import geoip2.database
import geoip2.errors
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib

# Local imports
from config.settings import get_settings
from monitoring.performance_tracker import track_performance
from database.connection import get_db_session
from utils.encryption import encrypt_data, decrypt_data

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.security.analysis")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Threat detection thresholds
MAX_LOGIN_ATTEMPTS_PER_MINUTE = 5
MAX_API_CALLS_PER_MINUTE = 100
SUSPICIOUS_LOGIN_THRESHOLD = 3
ANOMALY_DETECTION_WINDOW = 3600  # 1 hour
GEO_ANOMALY_DISTANCE_KM = 1000

# Risk scoring
RISK_SCORE_CRITICAL = 90
RISK_SCORE_HIGH = 70
RISK_SCORE_MEDIUM = 50
RISK_SCORE_LOW = 30

# Analysis windows
ANALYSIS_WINDOW_SHORT = 300    # 5 minutes
ANALYSIS_WINDOW_MEDIUM = 1800  # 30 minutes
ANALYSIS_WINDOW_LONG = 3600    # 1 hour
ANALYSIS_RETENTION_DAYS = 30

# Behavioral patterns
MIN_PATTERN_SAMPLES = 10
BEHAVIORAL_DEVIATION_THRESHOLD = 2.5

settings = get_settings()

# ===============================================================================
# ENUMS & DATA MODELS
# ===============================================================================

class ThreatType(str, Enum):
    """Types of security threats"""
    BRUTE_FORCE = "brute_force"
    CREDENTIAL_STUFFING = "credential_stuffing"
    DDoS = "ddos"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    RATE_LIMITING = "rate_limiting"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    GEO_ANOMALY = "geo_anomaly"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"

class RiskLevel(str, Enum):
    """Risk severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class AnalysisStatus(str, Enum):
    """Analysis processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ResponseAction(str, Enum):
    """Automated response actions"""
    BLOCK_IP = "block_ip"
    RATE_LIMIT = "rate_limit"
    REQUIRE_MFA = "require_mfa"
    LOG_ONLY = "log_only"
    ALERT_ADMIN = "alert_admin"
    QUARANTINE_USER = "quarantine_user"

@dataclass
class SecurityAnalysisConfig:
    """Configuration for security analysis system"""
    enable_real_time_analysis: bool = True
    enable_behavioral_analysis: bool = True
    enable_geo_analysis: bool = True
    enable_ml_detection: bool = True
    analysis_batch_size: int = 1000
    analysis_interval_seconds: int = 60
    threat_retention_days: int = ANALYSIS_RETENTION_DAYS
    risk_score_threshold: int = RISK_SCORE_MEDIUM
    auto_response_enabled: bool = True
    geoip_database_path: str = "data/geoip/GeoLite2-City.mmdb"

class SecurityEvent(BaseModel):
    """Security event data model"""
    event_id: str = Field(default_factory=lambda: secrets.token_hex(16))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str
    source_ip: str
    user_id: Optional[str] = None
    user_agent: str = ""
    endpoint: str = ""
    method: str = "GET"
    status_code: int = 200
    response_time_ms: float = 0.0
    payload_size: int = 0
    session_id: Optional[str] = None
    geolocation: Optional[Dict[str, Any]] = None
    risk_factors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ThreatIndicator(BaseModel):
    """Threat detection indicator"""
    indicator_id: str = Field(default_factory=lambda: secrets.token_hex(16))
    threat_type: ThreatType
    confidence: float = Field(ge=0.0, le=1.0)
    risk_score: int = Field(ge=0, le=100)
    description: str
    affected_entities: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    count: int = 1

class SecurityAnalysis(BaseModel):
    """Security analysis results"""
    analysis_id: str = Field(default_factory=lambda: secrets.token_hex(16))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    time_window: timedelta
    events_analyzed: int
    threats_detected: List[ThreatIndicator] = Field(default_factory=list)
    risk_level: RiskLevel
    overall_risk_score: int = Field(ge=0, le=100)
    anomalies_detected: int = 0
    recommendations: List[str] = Field(default_factory=list)
    auto_responses: List[ResponseAction] = Field(default_factory=list)
    analysis_duration_ms: float = 0.0
    status: AnalysisStatus = AnalysisStatus.COMPLETED

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            timedelta: lambda v: v.total_seconds()
        }

class BehavioralProfile(BaseModel):
    """User behavioral profile"""
    user_id: str
    profile_created: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    total_sessions: int = 0
    avg_session_duration: float = 0.0
    common_locations: List[Dict[str, Any]] = Field(default_factory=list)
    common_user_agents: List[str] = Field(default_factory=list)
    typical_access_times: List[int] = Field(default_factory=list)  # Hours of day
    endpoint_patterns: Dict[str, int] = Field(default_factory=dict)
    risk_baseline: float = 0.0
    anomaly_threshold: float = 2.5

class GeolocationData(BaseModel):
    """Geolocation analysis data"""
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_radius: Optional[int] = None
    is_vpn: bool = False
    is_tor: bool = False
    is_proxy: bool = False
    asn: Optional[str] = None
    organization: Optional[str] = None

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class SecurityAnalysisEngine:
    """Production-ready security analysis and threat detection system"""
    
    def __init__(self, config: SecurityAnalysisConfig):
        self.config = config
        self.logger = logger.bind(component="security_analysis")
        self._redis_client = None
        self._geoip_reader = None
        self._ml_models = {}
        self._threat_rules = {}
        self._behavioral_profiles = {}
        self._analysis_queue = deque()
        self._initialize_components()
    
    def _initialize_components(self) -> None:
        """Initialize analysis components"""
        try:
            self._load_geoip_database()
            self._load_ml_models()
            self._load_threat_rules()
            self.logger.info("Security analysis engine initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize security analysis engine", error=str(e))
            raise RuntimeError(f"Security analysis initialization failed: {str(e)}")
    
    def _load_geoip_database(self) -> None:
        """Load GeoIP database for location analysis"""
        try:
            if os.path.exists(self.config.geoip_database_path):
                self._geoip_reader = geoip2.database.Reader(self.config.geoip_database_path)
                self.logger.info("GeoIP database loaded successfully")
            else:
                self.logger.warning("GeoIP database not found - geo analysis disabled")
        except Exception as e:
            self.logger.error("Failed to load GeoIP database", error=str(e))
    
    def _load_ml_models(self) -> None:
        """Load machine learning models for anomaly detection"""
        try:
            if self.config.enable_ml_detection:
                # Initialize isolation forest for anomaly detection
                self._ml_models['anomaly_detector'] = IsolationForest(
                    contamination=0.1,
                    random_state=42,
                    n_estimators=100
                )
                
                # Initialize scaler for feature normalization
                self._ml_models['scaler'] = StandardScaler()
                
                # Load pre-trained models if available
                model_path = "data/models/security_analysis_models.joblib"
                if os.path.exists(model_path):
                    self._ml_models.update(joblib.load(model_path))
                    self.logger.info("Pre-trained ML models loaded")
                else:
                    self.logger.info("No pre-trained models found - using default models")
            
        except Exception as e:
            self.logger.error("Failed to load ML models", error=str(e))
    
    def _load_threat_rules(self) -> None:
        """Load threat detection rules"""
        self._threat_rules = {
            ThreatType.BRUTE_FORCE: {
                'max_failed_attempts': 5,
                'time_window': 300,  # 5 minutes
                'confidence_threshold': 0.8
            },
            ThreatType.DDoS: {
                'requests_per_minute': 1000,
                'unique_endpoints_threshold': 50,
                'confidence_threshold': 0.9
            },
            ThreatType.SQL_INJECTION: {
                'patterns': [
                    r"(\bunion\b.*\bselect\b)",
                    r"(\bselect\b.*\bfrom\b.*\bwhere\b.*['\"].*['\"])",
                    r"(\bdrop\b.*\btable\b)",
                    r"(\binsert\b.*\binto\b.*\bvalues\b)",
                    r"(\bor\b.*['\"].*['\"].*=.*['\"].*['\"])"
                ],
                'confidence_threshold': 0.7
            },
            ThreatType.XSS: {
                'patterns': [
                    r"<script[^>]*>.*?</script>",
                    r"javascript:",
                    r"on\w+\s*=",
                    r"<iframe[^>]*>.*?</iframe>",
                    r"eval\s*\("
                ],
                'confidence_threshold': 0.8
            }
        }
    
    async def _get_redis_client(self) -> aioredis.Redis:
        """Get Redis client for caching and storage"""
        if not self._redis_client:
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis_client
    
    @track_performance
    async def analyze_security_event(self, event: SecurityEvent) -> SecurityAnalysis:
        """Analyze individual security event for threats"""
        start_time = time.time()
        
        try:
            # Enrich event with geolocation data
            if self.config.enable_geo_analysis:
                event.geolocation = await self._get_geolocation(event.source_ip)
            
            # Detect threats
            threats = []
            
            # Real-time threat detection
            if self.config.enable_real_time_analysis:
                threats.extend(await self._detect_real_time_threats(event))
            
            # Behavioral analysis
            if self.config.enable_behavioral_analysis:
                behavioral_threats = await self._analyze_behavioral_patterns(event)
                threats.extend(behavioral_threats)
            
            # ML-based anomaly detection
            if self.config.enable_ml_detection:
                ml_threats = await self._detect_ml_anomalies([event])
                threats.extend(ml_threats)
            
            # Calculate overall risk
            risk_score = self._calculate_risk_score(threats)
            risk_level = self._determine_risk_level(risk_score)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(threats, event)
            
            # Determine auto responses
            auto_responses = []
            if self.config.auto_response_enabled:
                auto_responses = await self._determine_auto_responses(threats, risk_level)
            
            analysis_duration = (time.time() - start_time) * 1000
            
            analysis = SecurityAnalysis(
                time_window=timedelta(seconds=0),  # Single event
                events_analyzed=1,
                threats_detected=threats,
                risk_level=risk_level,
                overall_risk_score=risk_score,
                anomalies_detected=len([t for t in threats if t.threat_type == ThreatType.ANOMALOUS_BEHAVIOR]),
                recommendations=recommendations,
                auto_responses=auto_responses,
                analysis_duration_ms=analysis_duration
            )
            
            # Store analysis results
            await self._store_analysis_results(analysis)
            
            # Execute auto responses
            if auto_responses:
                await self._execute_auto_responses(auto_responses, event)
            
            self.logger.info(
                "Security event analyzed",
                event_id=event.event_id,
                threats_count=len(threats),
                risk_score=risk_score,
                analysis_time_ms=analysis_duration
            )
            
            return analysis
            
        except Exception as e:
            self.logger.error("Security event analysis failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Security analysis failed"
            )
    
    async def _get_geolocation(self, ip_address_str: str) -> Optional[GeolocationData]:
        """Get geolocation data for IP address"""
        try:
            if not self._geoip_reader:
                return None
            
            # Skip private IPs
            try:
                ip = ip_address(ip_address_str)
                if ip.is_private:
                    return None
            except AddressValueError:
                return None
            
            response = self._geoip_reader.city(ip_address_str)
            
            return GeolocationData(
                country=response.country.name,
                city=response.city.name,
                region=response.subdivisions.most_specific.name,
                latitude=float(response.location.latitude) if response.location.latitude else None,
                longitude=float(response.location.longitude) if response.location.longitude else None,
                accuracy_radius=response.location.accuracy_radius,
                asn=str(response.traits.autonomous_system_number) if response.traits.autonomous_system_number else None,
                organization=response.traits.autonomous_system_organization
            )
            
        except (geoip2.errors.AddressNotFoundError, Exception) as e:
            self.logger.debug("Geolocation lookup failed", ip=ip_address_str, error=str(e))
            return None
    
    async def _detect_real_time_threats(self, event: SecurityEvent) -> List[ThreatIndicator]:
        """Detect threats in real-time based on rules"""
        threats = []
        
        try:
            # Brute force detection
            if await self._detect_brute_force(event):
                threats.append(ThreatIndicator(
                    threat_type=ThreatType.BRUTE_FORCE,
                    confidence=0.9,
                    risk_score=80,
                    description=f"Brute force attack detected from {event.source_ip}",
                    affected_entities=[event.source_ip, event.user_id] if event.user_id else [event.source_ip],
                    evidence=[{"failed_attempts": await self._get_failed_attempts(event.source_ip)}]
                ))
            
            # DDoS detection
            if await self._detect_ddos(event):
                threats.append(ThreatIndicator(
                    threat_type=ThreatType.DDoS,
                    confidence=0.95,
                    risk_score=90,
                    description=f"DDoS attack pattern detected from {event.source_ip}",
                    affected_entities=[event.source_ip],
                    evidence=[{"request_rate": await self._get_request_rate(event.source_ip)}]
                ))
            
            # SQL injection detection
            sql_injection_threat = await self._detect_sql_injection(event)
            if sql_injection_threat:
                threats.append(sql_injection_threat)
            
            # XSS detection
            xss_threat = await self._detect_xss(event)
            if xss_threat:
                threats.append(xss_threat)
            
            # Geographic anomaly detection
            if event.geolocation:
                geo_threat = await self._detect_geo_anomaly(event)
                if geo_threat:
                    threats.append(geo_threat)
            
        except Exception as e:
            self.logger.error("Real-time threat detection failed", error=str(e))
        
        return threats
    
    async def _detect_brute_force(self, event: SecurityEvent) -> bool:
        """Detect brute force attacks"""
        try:
            if event.status_code not in [401, 403]:
                return False
            
            redis_client = await self._get_redis_client()
            key = f"failed_attempts:{event.source_ip}"
            
            # Get failed attempts in time window
            current_time = int(time.time())
            window_start = current_time - self._threat_rules[ThreatType.BRUTE_FORCE]['time_window']
            
            # Add current attempt
            await redis_client.zadd(key, {str(current_time): current_time})
            await redis_client.expire(key, self._threat_rules[ThreatType.BRUTE_FORCE]['time_window'])
            
            # Count attempts in window
            attempt_count = await redis_client.zcount(key, window_start, current_time)
            
            return attempt_count >= self._threat_rules[ThreatType.BRUTE_FORCE]['max_failed_attempts']
            
        except Exception as e:
            self.logger.error("Brute force detection failed", error=str(e))
            return False
    
    async def _detect_ddos(self, event: SecurityEvent) -> bool:
        """Detect DDoS attacks based on request patterns"""
        try:
            redis_client = await self._get_redis_client()
            current_minute = int(time.time()) // 60
            
            # Track requests per minute
            requests_key = f"requests_per_minute:{event.source_ip}:{current_minute}"
            request_count = await redis_client.incr(requests_key)
            await redis_client.expire(requests_key, 120)  # Keep for 2 minutes
            
            # Track unique endpoints
            endpoints_key = f"endpoints:{event.source_ip}:{current_minute}"
            await redis_client.sadd(endpoints_key, event.endpoint)
            await redis_client.expire(endpoints_key, 120)
            endpoint_count = await redis_client.scard(endpoints_key)
            
            ddos_rules = self._threat_rules[ThreatType.DDoS]
            
            return (request_count >= ddos_rules['requests_per_minute'] and 
                   endpoint_count >= ddos_rules['unique_endpoints_threshold'])
            
        except Exception as e:
            self.logger.error("DDoS detection failed", error=str(e))
            return False
    
    async def _detect_sql_injection(self, event: SecurityEvent) -> Optional[ThreatIndicator]:
        """Detect SQL injection attempts"""
        try:
            patterns = self._threat_rules[ThreatType.SQL_INJECTION]['patterns']
            payload = f"{event.endpoint} {json.dumps(event.metadata)}"
            
            detected_patterns = []
            for pattern in patterns:
                if re.search(pattern, payload, re.IGNORECASE):
                    detected_patterns.append(pattern)
            
            if detected_patterns:
                return ThreatIndicator(
                    threat_type=ThreatType.SQL_INJECTION,
                    confidence=min(1.0, len(detected_patterns) * 0.3),
                    risk_score=75,
                    description=f"SQL injection attempt detected from {event.source_ip}",
                    affected_entities=[event.source_ip, event.endpoint],
                    evidence=[{"patterns_matched": detected_patterns, "payload": payload[:500]}]
                )
            
            return None
            
        except Exception as e:
            self.logger.error("SQL injection detection failed", error=str(e))
            return None
    
    async def _detect_xss(self, event: SecurityEvent) -> Optional[ThreatIndicator]:
        """Detect XSS attempts"""
        try:
            patterns = self._threat_rules[ThreatType.XSS]['patterns']
            payload = f"{event.endpoint} {json.dumps(event.metadata)}"
            
            detected_patterns = []
            for pattern in patterns:
                if re.search(pattern, payload, re.IGNORECASE):
                    detected_patterns.append(pattern)
            
            if detected_patterns:
                return ThreatIndicator(
                    threat_type=ThreatType.XSS,
                    confidence=min(1.0, len(detected_patterns) * 0.35),
                    risk_score=70,
                    description=f"XSS attempt detected from {event.source_ip}",
                    affected_entities=[event.source_ip, event.endpoint],
                    evidence=[{"patterns_matched": detected_patterns, "payload": payload[:500]}]
                )
            
            return None
            
        except Exception as e:
            self.logger.error("XSS detection failed", error=str(e))
            return None
    
    async def _detect_geo_anomaly(self, event: SecurityEvent) -> Optional[ThreatIndicator]:
        """Detect geographical anomalies"""
        try:
            if not event.user_id or not event.geolocation:
                return None
            
            # Get user's behavioral profile
            profile = await self._get_behavioral_profile(event.user_id)
            if not profile or not profile.common_locations:
                return None
            
            current_location = (event.geolocation.get('latitude'), event.geolocation.get('longitude'))
            if not all(current_location):
                return None
            
            # Calculate distance from common locations
            min_distance = float('inf')
            for location in profile.common_locations:
                if 'latitude' in location and 'longitude' in location:
                    distance = self._calculate_distance(
                        current_location,
                        (location['latitude'], location['longitude'])
                    )
                    min_distance = min(min_distance, distance)
            
            # Check if location is anomalous
            if min_distance > GEO_ANOMALY_DISTANCE_KM:
                return ThreatIndicator(
                    threat_type=ThreatType.GEO_ANOMALY,
                    confidence=0.7,
                    risk_score=60,
                    description=f"Unusual login location detected for user {event.user_id}",
                    affected_entities=[event.user_id, event.source_ip],
                    evidence=[{
                        "current_location": event.geolocation,
                        "distance_km": min_distance,
                        "common_locations": profile.common_locations[:3]  # Top 3 locations
                    }]
                )
            
            return None
            
        except Exception as e:
            self.logger.error("Geo anomaly detection failed", error=str(e))
            return None
    
    def _calculate_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """Calculate distance between two geographic points using Haversine formula"""
        import math
        
        lat1, lon1 = point1
        lat2, lon2 = point2
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth radius in kilometers
        r = 6371
        
        return c * r
    
    async def _analyze_behavioral_patterns(self, event: SecurityEvent) -> List[ThreatIndicator]:
        """Analyze behavioral patterns for anomalies"""
        threats = []
        
        try:
            if not event.user_id:
                return threats
            
            # Get or create behavioral profile
            profile = await self._get_behavioral_profile(event.user_id)
            if not profile:
                profile = await self._create_behavioral_profile(event.user_id)
            
            # Update profile with current event
            await self._update_behavioral_profile(profile, event)
            
            # Check for behavioral anomalies
            anomalies = self._detect_behavioral_anomalies(profile, event)
            
            for anomaly in anomalies:
                threats.append(ThreatIndicator(
                    threat_type=ThreatType.ANOMALOUS_BEHAVIOR,
                    confidence=anomaly['confidence'],
                    risk_score=anomaly['risk_score'],
                    description=f"Behavioral anomaly detected: {anomaly['description']}",
                    affected_entities=[event.user_id],
                    evidence=[anomaly['evidence']]
                ))
            
        except Exception as e:
            self.logger.error("Behavioral pattern analysis failed", error=str(e))
        
        return threats
    
    async def _get_behavioral_profile(self, user_id: str) -> Optional[BehavioralProfile]:
        """Get user's behavioral profile"""
        try:
            redis_client = await self._get_redis_client()
            profile_data = await redis_client.get(f"behavioral_profile:{user_id}")
            
            if profile_data:
                return BehavioralProfile.parse_raw(profile_data)
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to get behavioral profile", error=str(e))
            return None
    
    async def _create_behavioral_profile(self, user_id: str) -> BehavioralProfile:
        """Create new behavioral profile for user"""
        profile = BehavioralProfile(user_id=user_id)
        
        try:
            redis_client = await self._get_redis_client()
            await redis_client.setex(
                f"behavioral_profile:{user_id}",
                self.config.threat_retention_days * 24 * 3600,
                profile.json()
            )
            
            return profile
            
        except Exception as e:
            self.logger.error("Failed to create behavioral profile", error=str(e))
            return profile
    
    async def _update_behavioral_profile(self, profile: BehavioralProfile, event: SecurityEvent) -> None:
        """Update behavioral profile with new event data"""
        try:
            # Update session count
            profile.total_sessions += 1
            profile.last_updated = datetime.utcnow()
            
            # Update geolocation patterns
            if event.geolocation and event.geolocation.get('latitude') and event.geolocation.get('longitude'):
                location = {
                    'country': event.geolocation.get('country'),
                    'city': event.geolocation.get('city'),
                    'latitude': event.geolocation.get('latitude'),
                    'longitude': event.geolocation.get('longitude'),
                    'count': 1
                }
                
                # Update or add location
                found = False
                for loc in profile.common_locations:
                    if (loc.get('country') == location['country'] and 
                        loc.get('city') == location['city']):
                        loc['count'] += 1
                        found = True
                        break
                
                if not found:
                    profile.common_locations.append(location)
                
                # Keep top 10 locations
                profile.common_locations.sort(key=lambda x: x.get('count', 0), reverse=True)
                profile.common_locations = profile.common_locations[:10]
            
            # Update user agent patterns
            if event.user_agent and event.user_agent not in profile.common_user_agents:
                profile.common_user_agents.append(event.user_agent)
                profile.common_user_agents = profile.common_user_agents[-5:]  # Keep last 5
            
            # Update access time patterns
            current_hour = event.timestamp.hour
            if current_hour not in profile.typical_access_times:
                profile.typical_access_times.append(current_hour)
            
            # Update endpoint patterns
            if event.endpoint:
                profile.endpoint_patterns[event.endpoint] = profile.endpoint_patterns.get(event.endpoint, 0) + 1
            
            # Store updated profile
            redis_client = await self._get_redis_client()
            await redis_client.setex(
                f"behavioral_profile:{profile.user_id}",
                self.config.threat_retention_days * 24 * 3600,
                profile.json()
            )
            
        except Exception as e:
            self.logger.error("Failed to update behavioral profile", error=str(e))
    
    def _detect_behavioral_anomalies(self, profile: BehavioralProfile, event: SecurityEvent) -> List[Dict[str, Any]]:
        """Detect anomalies in user behavior"""
        anomalies = []
        
        try:
            # Skip if profile doesn't have enough data
            if profile.total_sessions < MIN_PATTERN_SAMPLES:
                return anomalies
            
            # Check access time anomaly
            current_hour = event.timestamp.hour
            if profile.typical_access_times and current_hour not in profile.typical_access_times:
                # Calculate how unusual this time is
                hour_distances = [min(abs(current_hour - h), 24 - abs(current_hour - h)) for h in profile.typical_access_times]
                min_distance = min(hour_distances)
                
                if min_distance >= 6:  # More than 6 hours difference
                    anomalies.append({
                        'type': 'unusual_access_time',
                        'confidence': min(0.9, min_distance / 12),
                        'risk_score': int(min_distance * 5),
                        'description': f"Access at unusual time: {current_hour}:00",
                        'evidence': {
                            'current_hour': current_hour,
                            'typical_hours': profile.typical_access_times,
                            'hour_distance': min_distance
                        }
                    })
            
            # Check user agent anomaly
            if event.user_agent and profile.common_user_agents:
                if event.user_agent not in profile.common_user_agents:
                    anomalies.append({
                        'type': 'new_user_agent',
                        'confidence': 0.6,
                        'risk_score': 40,
                        'description': "New user agent detected",
                        'evidence': {
                            'current_user_agent': event.user_agent[:100],
                            'common_user_agents': profile.common_user_agents
                        }
                    })
            
            # Check endpoint access patterns
            if event.endpoint and profile.endpoint_patterns:
                endpoint_frequency = profile.endpoint_patterns.get(event.endpoint, 0)
                total_accesses = sum(profile.endpoint_patterns.values())
                endpoint_probability = endpoint_frequency / total_accesses if total_accesses > 0 else 0
                
                # Flag rare endpoint access
                if endpoint_probability < 0.05 and endpoint_frequency < 3:  # Less than 5% and fewer than 3 times
                    anomalies.append({
                        'type': 'rare_endpoint_access',
                        'confidence': 0.7,
                        'risk_score': 50,
                        'description': f"Access to rarely used endpoint: {event.endpoint}",
                        'evidence': {
                            'endpoint': event.endpoint,
                            'frequency': endpoint_frequency,
                            'probability': endpoint_probability,
                            'total_accesses': total_accesses
                        }
                    })
            
        except Exception as e:
            self.logger.error("Behavioral anomaly detection failed", error=str(e))
        
        return anomalies
    
    async def _detect_ml_anomalies(self, events: List[SecurityEvent]) -> List[ThreatIndicator]:
        """Use machine learning models to detect anomalies"""
        threats = []
        
        try:
            if not self.config.enable_ml_detection or not events:
                return threats
            
            # Extract features from events
            features = self._extract_ml_features(events)
            if not features:
                return threats
            
            # Prepare feature matrix
            feature_matrix = np.array(features)
            
            # Scale features
            if 'scaler' in self._ml_models and hasattr(self._ml_models['scaler'], 'transform'):
                feature_matrix = self._ml_models['scaler'].transform(feature_matrix)
            
            # Detect anomalies
            if 'anomaly_detector' in self._ml_models:
                anomaly_scores = self._ml_models['anomaly_detector'].decision_function(feature_matrix)
                is_anomaly = self._ml_models['anomaly_detector'].predict(feature_matrix)
                
                for i, (event, score, anomaly) in enumerate(zip(events, anomaly_scores, is_anomaly)):
                    if anomaly == -1:  # Anomaly detected
                        confidence = min(1.0, abs(score))
                        risk_score = int(confidence * 80)
                        
                        threats.append(ThreatIndicator(
                            threat_type=ThreatType.ANOMALOUS_BEHAVIOR,
                            confidence=confidence,
                            risk_score=risk_score,
                            description=f"ML-detected anomaly in event from {event.source_ip}",
                            affected_entities=[event.source_ip, event.user_id] if event.user_id else [event.source_ip],
                            evidence=[{
                                'anomaly_score': float(score),
                                'features': dict(zip(self._get_feature_names(), features[i]))
                            }]
                        ))
            
        except Exception as e:
            self.logger.error("ML anomaly detection failed", error=str(e))
        
        return threats
    
    def _extract_ml_features(self, events: List[SecurityEvent]) -> List[List[float]]:
        """Extract numerical features for ML analysis"""
        features = []
        
        for event in events:
            try:
                feature_vector = [
                    event.response_time_ms,
                    event.payload_size,
                    event.status_code,
                    len(event.endpoint) if event.endpoint else 0,
                    len(event.user_agent) if event.user_agent else 0,
                    event.timestamp.hour,
                    event.timestamp.weekday(),
                    1.0 if event.geolocation else 0.0,
                    len(event.risk_factors),
                    1.0 if event.status_code >= 400 else 0.0
                ]
                features.append(feature_vector)
                
            except Exception as e:
                self.logger.debug("Feature extraction failed for event", error=str(e))
                continue
        
        return features
    
    def _get_feature_names(self) -> List[str]:
        """Get names of ML features"""
        return [
            'response_time_ms',
            'payload_size',
            'status_code',
            'endpoint_length',
            'user_agent_length',
            'hour_of_day',
            'day_of_week',
            'has_geolocation',
            'risk_factors_count',
            'is_error_status'
        ]
    
    def _calculate_risk_score(self, threats: List[ThreatIndicator]) -> int:
        """Calculate overall risk score from detected threats"""
        if not threats:
            return 0
        
        # Weight threats by confidence and type
        total_score = 0
        threat_weights = {
            ThreatType.DDoS: 1.2,
            ThreatType.BRUTE_FORCE: 1.1,
            ThreatType.SQL_INJECTION: 1.3,
            ThreatType.XSS: 1.2,
            ThreatType.PRIVILEGE_ESCALATION: 1.4,
            ThreatType.DATA_EXFILTRATION: 1.5,
            ThreatType.CREDENTIAL_STUFFING: 1.1,
            ThreatType.ANOMALOUS_BEHAVIOR: 0.8,
            ThreatType.GEO_ANOMALY: 0.7,
            ThreatType.RATE_LIMITING: 0.6
        }
        
        for threat in threats:
            weight = threat_weights.get(threat.threat_type, 1.0)
            weighted_score = threat.risk_score * threat.confidence * weight
            total_score += weighted_score
        
        # Normalize and cap at 100
        return min(100, int(total_score / len(threats)))
    
    def _determine_risk_level(self, risk_score: int) -> RiskLevel:
        """Determine risk level based on score"""
        if risk_score >= RISK_SCORE_CRITICAL:
            return RiskLevel.CRITICAL
        elif risk_score >= RISK_SCORE_HIGH:
            return RiskLevel.HIGH
        elif risk_score >= RISK_SCORE_MEDIUM:
            return RiskLevel.MEDIUM
        elif risk_score >= RISK_SCORE_LOW:
            return RiskLevel.LOW
        else:
            return RiskLevel.INFO
    
    def _generate_recommendations(self, threats: List[ThreatIndicator], event: SecurityEvent) -> List[str]:
        """Generate security recommendations based on detected threats"""
        recommendations = []
        
        threat_types = {threat.threat_type for threat in threats}
        
        if ThreatType.BRUTE_FORCE in threat_types:
            recommendations.append("Enable account lockout after failed attempts")
            recommendations.append("Implement CAPTCHA for suspicious login patterns")
            recommendations.append("Consider IP-based rate limiting")
        
        if ThreatType.DDoS in threat_types:
            recommendations.append("Implement DDoS protection at network level")
            recommendations.append("Enable rate limiting per IP address")
            recommendations.append("Consider using CDN with DDoS protection")
        
        if ThreatType.SQL_INJECTION in threat_types or ThreatType.XSS in threat_types:
            recommendations.append("Review input validation and sanitization")
            recommendations.append("Implement Web Application Firewall (WAF)")
            recommendations.append("Use prepared statements for database queries")
            recommendations.append("Enable Content Security Policy (CSP)")
        
        if ThreatType.GEO_ANOMALY in threat_types:
            recommendations.append("Enable multi-factor authentication")
            recommendations.append("Send login notifications to users")
            recommendations.append("Consider geo-blocking for high-risk regions")
        
        if ThreatType.ANOMALOUS_BEHAVIOR in threat_types:
            recommendations.append("Review user access patterns and permissions")
            recommendations.append("Implement behavioral analytics")
            recommendations.append("Enable session monitoring")
        
        # Remove duplicates
        return list(set(recommendations))
    
    async def _determine_auto_responses(self, threats: List[ThreatIndicator], risk_level: RiskLevel) -> List[ResponseAction]:
        """Determine automated response actions"""
        actions = []
        
        threat_types = {threat.threat_type for threat in threats}
        
        if risk_level == RiskLevel.CRITICAL:
            actions.append(ResponseAction.ALERT_ADMIN)
            
            if ThreatType.DDoS in threat_types or ThreatType.BRUTE_FORCE in threat_types:
                actions.append(ResponseAction.BLOCK_IP)
            else:
                actions.append(ResponseAction.RATE_LIMIT)
        
        elif risk_level == RiskLevel.HIGH:
            actions.append(ResponseAction.ALERT_ADMIN)
            actions.append(ResponseAction.RATE_LIMIT)
            
            if ThreatType.GEO_ANOMALY in threat_types or ThreatType.ANOMALOUS_BEHAVIOR in threat_types:
                actions.append(ResponseAction.REQUIRE_MFA)
        
        elif risk_level == RiskLevel.MEDIUM:
            actions.append(ResponseAction.RATE_LIMIT)
            actions.append(ResponseAction.LOG_ONLY)
        
        else:
            actions.append(ResponseAction.LOG_ONLY)
        
        return list(set(actions))
    
    async def _execute_auto_responses(self, actions: List[ResponseAction], event: SecurityEvent) -> None:
        """Execute automated response actions"""
        try:
            redis_client = await self._get_redis_client()
            
            for action in actions:
                if action == ResponseAction.BLOCK_IP:
                    await self._block_ip_address(event.source_ip, redis_client)
                
                elif action == ResponseAction.RATE_LIMIT:
                    await self._apply_rate_limit(event.source_ip, redis_client)
                
                elif action == ResponseAction.REQUIRE_MFA:
                    if event.user_id:
                        await self._require_mfa(event.user_id, redis_client)
                
                elif action == ResponseAction.ALERT_ADMIN:
                    await self._send_admin_alert(event, actions)
                
                elif action == ResponseAction.QUARANTINE_USER:
                    if event.user_id:
                        await self._quarantine_user(event.user_id, redis_client)
                
                self.logger.info(
                    "Auto response executed",
                    action=action.value,
                    source_ip=event.source_ip,
                    user_id=event.user_id
                )
                
        except Exception as e:
            self.logger.error("Failed to execute auto responses", error=str(e))
    
    async def _block_ip_address(self, ip_address: str, redis_client: aioredis.Redis) -> None:
        """Block IP address for security reasons"""
        block_key = f"blocked_ip:{ip_address}"
        await redis_client.setex(block_key, 3600, "security_block")  # Block for 1 hour
        self.logger.warning("IP address blocked", ip_address=ip_address)
    
    async def _apply_rate_limit(self, ip_address: str, redis_client: aioredis.Redis) -> None:
        """Apply rate limiting to IP address"""
        limit_key = f"rate_limit:{ip_address}"
        await redis_client.setex(limit_key, 300, "limited")  # Limit for 5 minutes
        self.logger.info("Rate limit applied", ip_address=ip_address)
    
    async def _require_mfa(self, user_id: str, redis_client: aioredis.Redis) -> None:
        """Require MFA for user's next login"""
        mfa_key = f"require_mfa:{user_id}"
        await redis_client.setex(mfa_key, 3600, "required")  # Require for 1 hour
        self.logger.info("MFA required", user_id=user_id)
    
    async def _quarantine_user(self, user_id: str, redis_client: aioredis.Redis) -> None:
        """Quarantine user account"""
        quarantine_key = f"quarantined_user:{user_id}"
        await redis_client.setex(quarantine_key, 24 * 3600, "quarantined")  # Quarantine for 24 hours
        self.logger.warning("User quarantined", user_id=user_id)
    
    async def _send_admin_alert(self, event: SecurityEvent, actions: List[ResponseAction]) -> None:
        """Send alert to administrators"""
        # This would integrate with your notification system
        alert_data = {
            "timestamp": event.timestamp.isoformat(),
            "event_id": event.event_id,
            "source_ip": event.source_ip,
            "user_id": event.user_id,
            "threat_level": "HIGH",
            "actions_taken": [action.value for action in actions],
            "event_details": {
                "endpoint": event.endpoint,
                "user_agent": event.user_agent[:100],
                "geolocation": event.geolocation
            }
        }
        
        # Store alert for admin dashboard
        redis_client = await self._get_redis_client()
        alert_key = f"security_alert:{int(time.time())}:{event.event_id}"
        await redis_client.setex(alert_key, 7 * 24 * 3600, json.dumps(alert_data))
        
        self.logger.critical("Security alert generated", alert=alert_data)
    
    async def _store_analysis_results(self, analysis: SecurityAnalysis) -> None:
        """Store analysis results for historical tracking"""
        try:
            redis_client = await self._get_redis_client()
            
            # Store analysis
            analysis_key = f"security_analysis:{analysis.analysis_id}"
            await redis_client.setex(
                analysis_key,
                self.config.threat_retention_days * 24 * 3600,
                analysis.json()
            )
            
            # Index by timestamp for time-series queries
            timestamp_key = f"analysis_timeline:{int(analysis.timestamp.timestamp())}"
            await redis_client.setex(timestamp_key, self.config.threat_retention_days * 24 * 3600, analysis.analysis_id)
            
            # Store threat indicators separately for quick lookup
            for threat in analysis.threats_detected:
                threat_key = f"threat:{threat.threat_type}:{threat.indicator_id}"
                await redis_client.setex(
                    threat_key,
                    self.config.threat_retention_days * 24 * 3600,
                    threat.json()
                )
            
        except Exception as e:
            self.logger.error("Failed to store analysis results", error=str(e))
    
    async def _get_failed_attempts(self, ip_address: str) -> int:
        """Get failed attempt count for IP address"""
        try:
            redis_client = await self._get_redis_client()
            key = f"failed_attempts:{ip_address}"
            current_time = int(time.time())
            window_start = current_time - 300  # 5 minutes
            
            return await redis_client.zcount(key, window_start, current_time)
            
        except Exception:
            return 0
    
    async def _get_request_rate(self, ip_address: str) -> int:
        """Get request rate for IP address"""
        try:
            redis_client = await self._get_redis_client()
            current_minute = int(time.time()) // 60
            key = f"requests_per_minute:{ip_address}:{current_minute}"
            
            rate = await redis_client.get(key)
            return int(rate) if rate else 0
            
        except Exception:
            return 0
    
    @track_performance
    async def batch_analyze_events(self, events: List[SecurityEvent]) -> SecurityAnalysis:
        """Analyze multiple security events in batch"""
        start_time = time.time()
        
        try:
            if not events:
                return SecurityAnalysis(
                    time_window=timedelta(seconds=0),
                    events_analyzed=0,
                    risk_level=RiskLevel.INFO,
                    overall_risk_score=0
                )
            
            all_threats = []
            anomaly_count = 0
            
            # Analyze events individually first
            for event in events:
                event_analysis = await self.analyze_security_event(event)
                all_threats.extend(event_analysis.threats_detected)
                anomaly_count += event_analysis.anomalies_detected
            
            # Perform batch-specific analysis
            batch_threats = await self._analyze_event_correlations(events)
            all_threats.extend(batch_threats)
            
            # ML analysis on batch
            if self.config.enable_ml_detection:
                ml_threats = await self._detect_ml_anomalies(events)
                all_threats.extend(ml_threats)
                anomaly_count += len([t for t in ml_threats if t.threat_type == ThreatType.ANOMALOUS_BEHAVIOR])
            
            # Calculate overall metrics
            risk_score = self._calculate_risk_score(all_threats)
            risk_level = self._determine_risk_level(risk_score)
            
            # Generate recommendations
            recommendations = []
            if all_threats:
                sample_event = events[0]  # Use first event as representative
                recommendations = self._generate_recommendations(all_threats, sample_event)
            
            # Determine auto responses
            auto_responses = []
            if self.config.auto_response_enabled and all_threats:
                sample_event = events[0]
                auto_responses = await self._determine_auto_responses(all_threats, risk_level)
            
            analysis_duration = (time.time() - start_time) * 1000
            time_window = timedelta(seconds=(events[-1].timestamp - events[0].timestamp).total_seconds()) if len(events) > 1 else timedelta(seconds=0)
            
            analysis = SecurityAnalysis(
                time_window=time_window,
                events_analyzed=len(events),
                threats_detected=all_threats,
                risk_level=risk_level,
                overall_risk_score=risk_score,
                anomalies_detected=anomaly_count,
                recommendations=recommendations,
                auto_responses=auto_responses,
                analysis_duration_ms=analysis_duration
            )
            
            # Store results
            await self._store_analysis_results(analysis)
            
            # Execute auto responses if needed
            if auto_responses and all_threats:
                await self._execute_auto_responses(auto_responses, events[0])
            
            self.logger.info(
                "Batch security analysis completed",
                events_count=len(events),
                threats_count=len(all_threats),
                risk_score=risk_score,
                analysis_time_ms=analysis_duration
            )
            
            return analysis
            
        except Exception as e:
            self.logger.error("Batch security analysis failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Batch security analysis failed"
            )
    
    async def _analyze_event_correlations(self, events: List[SecurityEvent]) -> List[ThreatIndicator]:
        """Analyze correlations between events to detect complex attacks"""
        threats = []
        
        try:
            # Group events by IP address
            ip_events = defaultdict(list)
            for event in events:
                ip_events[event.source_ip].append(event)
            
            # Look for distributed attacks
            for ip, ip_event_list in ip_events.items():
                if len(ip_event_list) > 20:  # High activity from single IP
                    # Check for endpoint scanning
                    unique_endpoints = set(event.endpoint for event in ip_event_list)
                    if len(unique_endpoints) > 10:  # Accessing many different endpoints
                        threats.append(ThreatIndicator(
                            threat_type=ThreatType.DATA_EXFILTRATION,
                            confidence=0.7,
                            risk_score=65,
                            description=f"Potential scanning/enumeration from {ip}",
                            affected_entities=[ip],
                            evidence=[{
                                "event_count": len(ip_event_list),
                                "unique_endpoints": len(unique_endpoints),
                                "time_span_minutes": (ip_event_list[-1].timestamp - ip_event_list[0].timestamp).total_seconds() / 60
                            }]
                        ))
            
            # Look for coordinated attacks from multiple IPs
            time_grouped_events = defaultdict(list)
            for event in events:
                minute_timestamp = int(event.timestamp.timestamp()) // 60
                time_grouped_events[minute_timestamp].append(event)
            
            for minute, minute_events in time_grouped_events.items():
                unique_ips = set(event.source_ip for event in minute_events)
                if len(unique_ips) > 50 and len(minute_events) > 200:  # High activity from many IPs
                    threats.append(ThreatIndicator(
                        threat_type=ThreatType.DDoS,
                        confidence=0.9,
                        risk_score=85,
                        description="Coordinated DDoS attack detected",
                        affected_entities=list(unique_ips)[:10],  # Show first 10 IPs
                        evidence=[{
                            "unique_ips": len(unique_ips),
                            "total_requests": len(minute_events),
                            "time_window": "1 minute"
                        }]
                    ))
            
        except Exception as e:
            self.logger.error("Event correlation analysis failed", error=str(e))
        
        return threats
    
    async def get_threat_summary(self, time_window: timedelta) -> Dict[str, Any]:
        """Get threat summary for specified time window"""
        try:
            redis_client = await self._get_redis_client()
            end_time = datetime.utcnow()
            start_time = end_time - time_window
            
            # Get analyses in time window
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())
            
            threat_counts = defaultdict(int)
            risk_levels = defaultdict(int)
            total_events = 0
            total_analyses = 0
            
            # Scan through timeline
            for timestamp in range(start_timestamp, end_timestamp + 1, 60):  # Every minute
                timeline_key = f"analysis_timeline:{timestamp}"
                analysis_id = await redis_client.get(timeline_key)
                
                if analysis_id:
                    analysis_data = await redis_client.get(f"security_analysis:{analysis_id}")
                    if analysis_data:
                        analysis = SecurityAnalysis.parse_raw(analysis_data)
                        total_analyses += 1
                        total_events += analysis.events_analyzed
                        risk_levels[analysis.risk_level] += 1
                        
                        for threat in analysis.threats_detected:
                            threat_counts[threat.threat_type] += 1
            
            return {
                "time_window_hours": time_window.total_seconds() / 3600,
                "total_analyses": total_analyses,
                "total_events_analyzed": total_events,
                "threat_counts": dict(threat_counts),
                "risk_level_distribution": dict(risk_levels),
                "top_threats": sorted(threat_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            }
            
        except Exception as e:
            self.logger.error("Failed to get threat summary", error=str(e))
            return {}
    
    async def train_ml_models(self, training_events: List[SecurityEvent]) -> bool:
        """Train machine learning models with historical data"""
        try:
            if not self.config.enable_ml_detection or len(training_events) < 100:
                return False
            
            # Extract features
            features = self._extract_ml_features(training_events)
            if not features:
                return False
            
            feature_matrix = np.array(features)
            
            # Train scaler
            scaler = StandardScaler()
            scaled_features = scaler.fit_transform(feature_matrix)
            
            # Train anomaly detector
            anomaly_detector = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=100
            )
            anomaly_detector.fit(scaled_features)
            
            # Update models
            self._ml_models['scaler'] = scaler
            self._ml_models['anomaly_detector'] = anomaly_detector
            
            # Save models
            model_path = "data/models/security_analysis_models.joblib"
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            joblib.dump(self._ml_models, model_path)
            
            self.logger.info(
                "ML models trained successfully",
                training_samples=len(training_events),
                features_count=len(features[0]) if features else 0
            )
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to train ML models", error=str(e))
            return False
    
    async def cleanup(self) -> None:
        """Cleanup resources and connections"""
        try:
            if self._redis_client:
                await self._redis_client.close()
            
            if self._geoip_reader:
                self._geoip_reader.close()
            
            self.logger.info("Security analysis engine cleanup completed")
            
        except Exception as e:
            self.logger.error("Cleanup failed", error=str(e))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

# Global security analysis engine instance
_analysis_engine = None

async def get_security_analysis_engine() -> SecurityAnalysisEngine:
    """Get security analysis engine instance"""
    global _analysis_engine
    if not _analysis_engine:
        config = SecurityAnalysisConfig(
            enable_real_time_analysis=settings.SECURITY_REAL_TIME_ANALYSIS,
            enable_behavioral_analysis=settings.SECURITY_BEHAVIORAL_ANALYSIS,
            enable_geo_analysis=settings.SECURITY_GEO_ANALYSIS,
            enable_ml_detection=settings.SECURITY_ML_DETECTION,
            auto_response_enabled=settings.SECURITY_AUTO_RESPONSE
        )
        _analysis_engine = SecurityAnalysisEngine(config)
    return _analysis_engine

async def analyze_security_event(event: SecurityEvent) -> SecurityAnalysis:
    """Analyze single security event - helper function"""
    engine = await get_security_analysis_engine()
    return await engine.analyze_security_event(event)

async def batch_analyze_security_events(events: List[SecurityEvent]) -> SecurityAnalysis:
    """Batch analyze security events - helper function"""
    engine = await get_security_analysis_engine()
    return await engine.batch_analyze_events(events)

def create_security_event(
    event_type: str,
    source_ip: str,
    endpoint: str = "/",
    method: str = "GET",
    status_code: int = 200,
    user_id: Optional[str] = None,
    **kwargs
) -> SecurityEvent:
    """Create security event helper function"""
    return SecurityEvent(
        event_type=event_type,
        source_ip=source_ip,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        user_id=user_id,
        **kwargs
    )

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "SecurityAnalysisEngine",
    "SecurityAnalysisConfig",
    "SecurityEvent",
    "SecurityAnalysis", 
    "ThreatIndicator",
    "BehavioralProfile",
    "GeolocationData",
    "ThreatType",
    "RiskLevel",
    "ResponseAction",
    "AnalysisStatus",
    "get_security_analysis_engine",
    "analyze_security_event",
    "batch_analyze_security_events",
    "create_security_event"
]