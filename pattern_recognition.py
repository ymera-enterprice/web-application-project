"""
YMERA Enterprise - Pattern Recognition Engine
Production-Ready Behavioral Pattern Discovery System - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import json
import logging
import math
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from collections import defaultdict, Counter
from itertools import combinations

# Third-party imports (alphabetical)
import aioredis
import numpy as np
import structlog
from fastapi import HTTPException, status
from pydantic import BaseModel, Field, validator
from sklearn.cluster import DBSCAN, KMeans
from sklearn.preprocessing import StandardScaler
from scipy import stats

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.learning_engine.pattern_recognition")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Pattern recognition constants
MIN_PATTERN_INSTANCES = 3
MIN_PATTERN_CONFIDENCE = 0.6
MAX_PATTERN_COMPLEXITY = 10
PATTERN_DISCOVERY_INTERVAL = 15 * 60  # 15 minutes
TEMPORAL_WINDOW_SIZE = 3600  # 1 hour
SIMILARITY_THRESHOLD = 0.8
MAX_PATTERNS_PER_TYPE = 100

# Pattern types
PATTERN_TYPES = {
    "temporal": "Time-based behavioral patterns",
    "sequential": "Action sequence patterns", 
    "collaborative": "Agent collaboration patterns",
    "performance": "Performance trend patterns",
    "error": "Error occurrence patterns",
    "communication": "Communication patterns",
    "resource": "Resource usage patterns",
    "learning": "Learning efficiency patterns"
}

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class PatternRecognitionConfig:
    """Configuration for pattern recognition engine"""
    enabled: bool = True
    min_pattern_instances: int = MIN_PATTERN_INSTANCES
    min_pattern_confidence: float = MIN_PATTERN_CONFIDENCE
    max_pattern_complexity: int = MAX_PATTERN_COMPLEXITY
    discovery_interval: int = PATTERN_DISCOVERY_INTERVAL
    temporal_window_size: int = TEMPORAL_WINDOW_SIZE
    similarity_threshold: float = SIMILARITY_THRESHOLD
    max_patterns_per_type: int = MAX_PATTERNS_PER_TYPE
    enable_real_time_discovery: bool = True
    enable_advanced_analytics: bool = True
    pattern_retention_days: int = 90

@dataclass
class PatternInstance:
    """Single instance of a pattern occurrence"""
    instance_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    agent_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

@dataclass
class DiscoveredPattern:
    """Represents a discovered behavioral pattern"""
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_type: str = ""
    name: str = ""
    description: str = ""
    instances: List[PatternInstance] = field(default_factory=list)
    confidence: float = 0.0
    significance: float = 0.0
    frequency: int = 0
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    agents_involved: Set[str] = field(default_factory=set)
    context_requirements: Dict[str, Any] = field(default_factory=dict)
    predictive_value: float = 0.0
    optimization_potential: float = 0.0

class PatternAnalysisRequest(BaseModel):
    """Request for pattern analysis"""
    events: List[Dict[str, Any]]
    analysis_type: str = "all"  # 'temporal', 'sequential', 'collaborative', 'all'
    time_window: Optional[int] = None
    agent_filter: Optional[List[str]] = None
    min_confidence: float = 0.6
    include_predictions: bool = False

class PatternSearchResult(BaseModel):
    """Pattern search result"""
    pattern_id: str
    pattern_type: str
    name: str
    description: str
    confidence: float
    significance: float
    frequency: int
    last_seen: datetime
    instances_count: int
    predictive_value: float
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class BasePatternAnalyzer(ABC):
    """Abstract base class for pattern analyzers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger.bind(analyzer=self.__class__.__name__)
    
    @abstractmethod
    async def analyze_events(self, events: List[Dict[str, Any]]) -> List[DiscoveredPattern]:
        """Analyze events for patterns"""
        pass
    
    @abstractmethod
    async def validate_pattern(self, pattern: DiscoveredPattern) -> bool:
        """Validate discovered pattern"""
        pass

class TemporalPatternAnalyzer(BasePatternAnalyzer):
    """Analyzes temporal patterns in agent behavior"""
    
    async def analyze_events(self, events: List[Dict[str, Any]]) -> List[DiscoveredPattern]:
        """Analyze temporal patterns in events"""
        patterns = []
        
        try:
            # Group events by time windows
            time_windows = self._group_events_by_time(events)
            
            # Analyze periodic patterns
            periodic_patterns = await self._find_periodic_patterns(time_windows)
            patterns.extend(periodic_patterns)
            
            # Analyze burst patterns
            burst_patterns = await self._find_burst_patterns(events)
            patterns.extend(burst_patterns)
            
            # Analyze trend patterns
            trend_patterns = await self._find_trend_patterns(events)
            patterns.extend(trend_patterns)
            
            return patterns
            
        except Exception as e:
            self.logger.error("Temporal pattern analysis failed", error=str(e))
            return []
    
    def _group_events_by_time(self, events: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
        """Group events by time windows"""
        time_windows = defaultdict(list)
        window_size = self.config.get("temporal_window_size", TEMPORAL_WINDOW_SIZE)
        
        for event in events:
            timestamp = event.get("timestamp", datetime.utcnow())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            window_id = int(timestamp.timestamp()) // window_size
            time_windows[window_id].append(event)
        
        return time_windows
    
    async def _find_periodic_patterns(self, time_windows: Dict[int, List[Dict[str, Any]]]) -> List[DiscoveredPattern]:
        """Find periodic patterns in time windows"""
        patterns = []
        
        try:
            # Analyze event frequency over time
            window_counts = {window_id: len(events) for window_id, events in time_windows.items()}
            
            if len(window_counts) < 3:
                return patterns
            
            # Convert to time series
            sorted_windows = sorted(window_counts.keys())
            counts = [window_counts[w] for w in sorted_windows]
            
            # Find periodic peaks using FFT
            if len(counts) >= 8:  # Minimum for meaningful FFT
                fft_result = np.fft.fft(counts)
                frequencies = np.fft.fftfreq(len(counts))
                
                # Find dominant frequencies
                power_spectrum = np.abs(fft_result)
                dominant_freq_idx = np.argmax(power_spectrum[1:len(power_spectrum)//2]) + 1
                period = 1.0 / abs(frequencies[dominant_freq_idx]) if frequencies[dominant_freq_idx] != 0 else 0
                
                if period >= 2:  # At least 2 time windows
                    confidence = power_spectrum[dominant_freq_idx] / np.sum(power_spectrum)
                    
                    if confidence > self.config.get("min_pattern_confidence", MIN_PATTERN_CONFIDENCE):
                        pattern = DiscoveredPattern(
                            pattern_type="temporal",
                            name=f"Periodic Activity Pattern (Period: {period:.1f} windows)",
                            description=f"Recurring activity pattern with period of {period:.1f} time windows",
                            confidence=float(confidence),
                            significance=float(confidence * len(counts) / max(counts)),
                            frequency=len([c for c in counts if c > np.mean(counts)]),
                            context_requirements={"period": period, "min_activity": np.mean(counts)}
                        )
                        
                        # Create pattern instances
                        for window_id, events in time_windows.items():
                            if len(events) > np.mean(counts):
                                pattern.instances.append(PatternInstance(
                                    timestamp=datetime.fromtimestamp(window_id * self.config.get("temporal_window_size", TEMPORAL_WINDOW_SIZE)),
                                    data={"event_count": len(events), "window_id": window_id},
                                    confidence=confidence
                                ))
                        
                        patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            self.logger.error("Failed to find periodic patterns", error=str(e))
            return []
    
    async def _find_burst_patterns(self, events: List[Dict[str, Any]]) -> List[DiscoveredPattern]:
        """Find burst patterns in events"""
        patterns = []
        
        try:
            # Group events by agent and time
            agent_timelines = defaultdict(list)
            
            for event in events:
                agent_id = event.get("agent_id", "unknown")
                timestamp = event.get("timestamp", datetime.utcnow())
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                agent_timelines[agent_id].append(timestamp)
            
            # Analyze each agent's timeline for bursts
            for agent_id, timestamps in agent_timelines.items():
                if len(timestamps) < 5:  # Need minimum events for burst detection
                    continue
                
                timestamps.sort()
                intervals = [(timestamps[i+1] - timestamps[i]).total_seconds() 
                           for i in range(len(timestamps)-1)]
                
                if not intervals:
                    continue
                
                # Find unusually short intervals (bursts)
                mean_interval = np.mean(intervals)
                std_interval = np.std(intervals)
                
                if std_interval > 0:
                    burst_threshold = mean_interval - 2 * std_interval
                    burst_intervals = [i for i in intervals if i < burst_threshold and i > 0]
                    
                    if len(burst_intervals) >= 3:  # At least 3 burst intervals
                        confidence = len(burst_intervals) / len(intervals)
                        
                        if confidence > self.config.get("min_pattern_confidence", MIN_PATTERN_CONFIDENCE):
                            pattern = DiscoveredPattern(
                                pattern_type="temporal",
                                name=f"Activity Burst Pattern - Agent {agent_id}",
                                description=f"Agent shows burst activity patterns with {len(burst_intervals)} burst intervals",
                                confidence=confidence,
                                significance=confidence * (mean_interval / (burst_threshold + 1)),
                                frequency=len(burst_intervals),
                                agents_involved={agent_id}
                            )
                            
                            # Add instances for each burst
                            for i, interval in enumerate(intervals):
                                if interval < burst_threshold:
                                    pattern.instances.append(PatternInstance(
                                        timestamp=timestamps[i],
                                        agent_id=agent_id,
                                        data={"interval": interval, "burst_intensity": mean_interval / interval},
                                        confidence=confidence
                                    ))
                            
                            patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            self.logger.error("Failed to find burst patterns", error=str(e))
            return []
    
    async def _find_trend_patterns(self, events: List[Dict[str, Any]]) -> List[DiscoveredPattern]:
        """Find trend patterns in events"""
        patterns = []
        
        try:
            # Group events by type and time
            event_types = defaultdict(list)
            
            for event in events:
                event_type = event.get("event_type", "unknown")
                timestamp = event.get("timestamp", datetime.utcnow())
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                event_types[event_type].append(timestamp)
            
            # Analyze trends for each event type
            for event_type, timestamps in event_types.items():
                if len(timestamps) < 5:
                    continue
                
                timestamps.sort()
                
                # Create time series (hourly buckets)
                start_time = timestamps[0]
                end_time = timestamps[-1]
                hours = int((end_time - start_time).total_seconds() / 3600) + 1
                
                if hours < 3:
                    continue
                
                hourly_counts = [0] * hours
                for ts in timestamps:
                    hour_idx = int((ts - start_time).total_seconds() / 3600)
                    if 0 <= hour_idx < hours:
                        hourly_counts[hour_idx] += 1
                
                # Calculate trend using linear regression
                x = np.arange(hours)
                y = np.array(hourly_counts)
                
                if np.sum(y) > 0:  # Only if there are events
                    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
                    
                    # Significant trend detection
                    if abs(r_value) > 0.5 and p_value < 0.05:
                        trend_type = "increasing" if slope > 0 else "decreasing"
                        confidence = abs(r_value)
                        
                        pattern = DiscoveredPattern(
                            pattern_type="temporal",
                            name=f"{trend_type.title()} Trend - {event_type}",
                            description=f"Event type '{event_type}' shows {trend_type} trend over time",
                            confidence=confidence,
                            significance=confidence * abs(slope),
                            frequency=len(timestamps),
                            context_requirements={
                                "event_type": event_type,
                                "trend_direction": trend_type,
                                "slope": slope
                            }
                        )
                        
                        # Add trend instances
                        for i, count in enumerate(hourly_counts):
                            if count > 0:
                                pattern.instances.append(PatternInstance(
                                    timestamp=start_time + timedelta(hours=i),
                                    data={
                                        "event_count": count,
                                        "expected_count": slope * i + intercept,
                                        "trend_position": i
                                    },
                                    confidence=confidence
                                ))
                        
                        patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            self.logger.error("Failed to find trend patterns", error=str(e))
            return []
    
    async def validate_pattern(self, pattern: DiscoveredPattern) -> bool:
        """Validate temporal pattern"""
        try:
            # Check minimum instances
            if len(pattern.instances) < self.config.get("min_pattern_instances", MIN_PATTERN_INSTANCES):
                return False
            
            # Check confidence threshold
            if pattern.confidence < self.config.get("min_pattern_confidence", MIN_PATTERN_CONFIDENCE):
                return False
            
            # Check temporal distribution
            if len(pattern.instances) > 1:
                timestamps = [inst.timestamp for inst in pattern.instances]
                timestamps.sort()
                
                # Check for reasonable time distribution
                time_span = (timestamps[-1] - timestamps[0]).total_seconds()
                if time_span < 60:  # Less than 1 minute total span
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error("Pattern validation failed", error=str(e))
            return False

class SequentialPatternAnalyzer(BasePatternAnalyzer):
    """Analyzes sequential patterns in agent actions"""
    
    async def analyze_events(self, events: List[Dict[str, Any]]) -> List[DiscoveredPattern]:
        """Analyze sequential patterns in events"""
        patterns = []
        
        try:
            # Group events by agent
            agent_sequences = defaultdict(list)
            
            for event in events:
                agent_id = event.get("agent_id", "unknown")
                agent_sequences[agent_id].append(event)
            
            # Analyze sequences for each agent
            for agent_id, agent_events in agent_sequences.items():
                if len(agent_events) < 3:
                    continue
                
                # Sort events by timestamp
                agent_events.sort(key=lambda x: x.get("timestamp", datetime.utcnow()))
                
                # Find common subsequences
                subsequence_patterns = await self._find_common_subsequences(agent_events, agent_id)
                patterns.extend(subsequence_patterns)
                
                # Find action chains
                chain_patterns = await self._find_action_chains(agent_events, agent_id)
                patterns.extend(chain_patterns)
            
            return patterns
            
        except Exception as e:
            self.logger.error("Sequential pattern analysis failed", error=str(e))
            return []
    
    async def _find_common_subsequences(self, events: List[Dict[str, Any]], agent_id: str) -> List[DiscoveredPattern]:
        """Find common subsequences in event sequences"""
        patterns = []
        
        try:
            # Extract action sequences
            actions = [event.get("action", event.get("event_type", "unknown")) for event in events]
            
            if len(actions) < 5:
                return patterns
            
            # Find subsequences of different lengths
            for seq_length in range(2, min(6, len(actions))):  # Subsequences of length 2-5
                subsequences = []
                
                for i in range(len(actions) - seq_length + 1):
                    subseq = tuple(actions[i:i + seq_length])
                    subsequences.append(subseq)
                
                # Count subsequence occurrences
                subseq_counts = Counter(subsequences)
                
                # Find frequent subsequences
                min_frequency = max(2, len(subsequences) // 10)  # At least 2 or 10% of subsequences
                
                for subseq, count in subseq_counts.items():
                    if count >= min_frequency:
                        confidence = count / len(subsequences)
                        
                        if confidence > self.config.get("min_pattern_confidence", MIN_PATTERN_CONFIDENCE):
                            pattern = DiscoveredPattern(
                                pattern_type="sequential",
                                name=f"Action Sequence Pattern - {' → '.join(subseq)}",
                                description=f"Agent {agent_id} frequently performs sequence: {' → '.join(subseq)}",
                                confidence=confidence,
                                significance=confidence * count,
                                frequency=count,
                                agents_involved={agent_id},
                                context_requirements={"sequence": list(subseq), "min_frequency": min_frequency}
                            )
                            
                            # Find instances of this subsequence
                            for i in range(len(actions) - seq_length + 1):
                                if tuple(actions[i:i + seq_length]) == subseq:
                                    pattern.instances.append(PatternInstance(
                                        timestamp=events[i].get("timestamp", datetime.utcnow()),
                                        agent_id=agent_id,
                                        data={
                                            "sequence": list(subseq),
                                            "position": i,
                                            "context": events[i].get("context", {})
                                        },
                                        confidence=confidence
                                    ))
                            
                            patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            self.logger.error("Failed to find common subsequences", error=str(e))
            return []
    
    async def _find_action_chains(self, events: List[Dict[str, Any]], agent_id: str) -> List[DiscoveredPattern]:
        """Find action chains and dependencies"""
        patterns = []
        
        try:
            # Build action transition matrix
            actions = [event.get("action", event.get("event_type", "unknown")) for event in events]
            unique_actions = list(set(actions))
            
            if len(unique_actions) < 2:
                return patterns
            
            # Create transition matrix
            transition_matrix = defaultdict(lambda: defaultdict(int))
            
            for i in range(len(actions) - 1):
                current_action = actions[i]
                next_action = actions[i + 1]
                transition_matrix[current_action][next_action] += 1
            
            # Find strong transitions
            for from_action, transitions in transition_matrix.items():
                total_from_action = sum(transitions.values())
                
                if total_from_action < 2:
                    continue
                
                for to_action, count in transitions.items():
                    transition_probability = count / total_from_action
                    
                    if transition_probability > 0.7 and count >= 2:  # Strong dependency
                        pattern = DiscoveredPattern(
                            pattern_type="sequential",
                            name=f"Action Chain: {from_action} → {to_action}",
                            description=f"Agent {agent_id} frequently follows '{from_action}' with '{to_action}' ({transition_probability:.1%} probability)",
                            confidence=transition_probability,
                            significance=transition_probability * count,
                            frequency=count,
                            agents_involved={agent_id},
                            context_requirements={
                                "from_action": from_action,
                                "to_action": to_action,
                                "min_probability": 0.7
                            },
                            predictive_value=transition_probability
                        )
                        
                        # Find instances of this transition
                        for i in range(len(actions) - 1):
                            if actions[i] == from_action and actions[i + 1] == to_action:
                                pattern.instances.append(PatternInstance(
                                    timestamp=events[i].get("timestamp", datetime.utcnow()),
                                    agent_id=agent_id,
                                    data={
                                        "from_action": from_action,
                                        "to_action": to_action,
                                        "transition_probability": transition_probability
                                    },
                                    confidence=transition_probability
                                ))
                        
                        patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            self.logger.error("Failed to find action chains", error=str(e))
            return []
    
    async def validate_pattern(self, pattern: DiscoveredPattern) -> bool:
        """Validate sequential pattern"""
        try:
            # Check minimum instances
            if len(pattern.instances) < self.config.get("min_pattern_instances", MIN_PATTERN_INSTANCES):
                return False
            
            # Check confidence threshold
            if pattern.confidence < self.config.get("min_pattern_confidence", MIN_PATTERN_CONFIDENCE):
                return False
            
            # Check sequence validity
            if "sequence" in pattern.context_requirements:
                sequence = pattern.context_requirements["sequence"]
                if len(sequence) < 2 or len(sequence) > self.config.get("max_pattern_complexity", MAX_PATTERN_COMPLEXITY):
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error("Sequential pattern validation failed", error=str(e))
            return False

class CollaborativePatternAnalyzer(BasePatternAnalyzer):
    """Analyzes collaborative patterns between agents"""
    
    async def analyze_events(self, events: List[Dict[str, Any]]) -> List[DiscoveredPattern]:
        """Analyze collaborative patterns in events"""
        patterns = []
        
        try:
            # Find interaction events
            interaction_events = [e for e in events if self._is_interaction_event(e)]
            
            if len(interaction_events) < 3:
                return patterns
            
            # Analyze collaboration networks
            network_patterns = await self._find_collaboration_networks(interaction_events)
            patterns.extend(network_patterns)
            
            # Analyze synchronization patterns
            sync_patterns = await self._find_synchronization_patterns(interaction_events)
            patterns.extend(sync_patterns)
            
            # Analyze role patterns
            role_patterns = await self._find_role_patterns(interaction_events)
            patterns.extend(role_patterns)
            
            return patterns
            
        except Exception as e:
            self.logger.error("Collaborative pattern analysis failed", error=str(e))
            return []
    
    def _is_interaction_event(self, event: Dict[str, Any]) -> bool:
        """Check if event represents an interaction"""
        interaction_indicators = [
            "collaboration", "communication", "handoff", "sync",
            "share", "assist", "coordinate", "team"
        ]
        
        eventdef _is_interaction_event(self, event: Dict[str, Any]) -> bool:
        """Check if event represents an interaction"""
        interaction_indicators = [
            "collaboration", "communication", "handoff", "sync",
            "share", "assist", "coordinate", "team"
        ]
        
        event_type = event.get("event_type", "").lower()
        action = event.get("action", "").lower()
        
        # Check if event involves multiple agents
        if "participants" in event.get("data", {}):
            return True
        
        if "target_agent" in event.get("data", {}):
            return True
        
        # Check for interaction keywords
        return any(indicator in event_type or indicator in action 
                  for indicator in interaction_indicators)
    
    async def _find_collaboration_networks(self, events: List[Dict[str, Any]]) -> List[DiscoveredPattern]:
        """Find collaboration network patterns"""
        patterns = []
        
        try:
            # Build collaboration graph
            collaboration_pairs = defaultdict(int)
            agent_interactions = defaultdict(set)
            
            for event in events:
                agent_id = event.get("agent_id")
                data = event.get("data", {})
                
                # Extract collaboration partners
                partners = []
                if "participants" in data:
                    partners = [p for p in data["participants"] if p != agent_id]
                elif "target_agent" in data:
                    partners = [data["target_agent"]]
                
                for partner in partners:
                    if agent_id and partner:
                        pair = tuple(sorted([agent_id, partner]))
                        collaboration_pairs[pair] += 1
                        agent_interactions[agent_id].add(partner)
                        agent_interactions[partner].add(agent_id)
            
            # Find frequent collaboration pairs
            total_interactions = sum(collaboration_pairs.values())
            
            for (agent1, agent2), count in collaboration_pairs.items():
                if count >= 3:  # Minimum collaboration instances
                    frequency = count / total_interactions if total_interactions > 0 else 0
                    
                    if frequency > 0.1:  # At least 10% of interactions
                        pattern = DiscoveredPattern(
                            pattern_type="collaborative",
                            name=f"Frequent Collaboration: {agent1} ↔ {agent2}",
                            description=f"Agents {agent1} and {agent2} collaborate frequently ({count} interactions)",
                            confidence=min(1.0, frequency * 5),
                            significance=frequency * count,
                            frequency=count,
                            agents_involved={agent1, agent2},
                            context_requirements={
                                "collaboration_pair": [agent1, agent2],
                                "min_interactions": 3
                            }
                        )
                        
                        # Find collaboration instances
                        for event in events:
                            event_agent = event.get("agent_id")
                            data = event.get("data", {})
                            
                            partners = []
                            if "participants" in data:
                                partners = data["participants"]
                            elif "target_agent" in data:
                                partners = [data["target_agent"]]
                            
                            if (event_agent == agent1 and agent2 in partners) or \
                               (event_agent == agent2 and agent1 in partners):
                                pattern.instances.append(PatternInstance(
                                    timestamp=event.get("timestamp", datetime.utcnow()),
                                    agent_id=event_agent,
                                    data={
                                        "collaboration_type": event.get("event_type"),
                                        "partners": partners,
                                        "context": data
                                    },
                                    confidence=frequency
                                ))
                        
                        patterns.append(pattern)
            
            # Find collaboration hubs (agents with many connections)
            for agent_id, partners in agent_interactions.items():
                if len(partners) >= 3:  # Connected to at least 3 other agents
                    hub_strength = len(partners) / len(agent_interactions) if len(agent_interactions) > 0 else 0
                    
                    pattern = DiscoveredPattern(
                        pattern_type="collaborative",
                        name=f"Collaboration Hub: {agent_id}",
                        description=f"Agent {agent_id} acts as collaboration hub with {len(partners)} connections",
                        confidence=min(1.0, hub_strength * 3),
                        significance=hub_strength * len(partners),
                        frequency=len(partners),
                        agents_involved={agent_id},
                        context_requirements={
                            "hub_agent": agent_id,
                            "min_connections": 3
                        }
                    )
                    
                    patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            self.logger.error("Failed to find collaboration networks", error=str(e))
            return []
    
    async def _find_synchronization_patterns(self, events: List[Dict[str, Any]]) -> List[DiscoveredPattern]:
        """Find synchronization patterns between agents"""
        patterns = []
        
        try:
            # Group events by time windows (5-minute windows)
            window_size = 300  # 5 minutes
            time_windows = defaultdict(lambda: defaultdict(list))
            
            for event in events:
                timestamp = event.get("timestamp", datetime.utcnow())
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                window_id = int(timestamp.timestamp()) // window_size
                agent_id = event.get("agent_id", "unknown")
                time_windows[window_id][agent_id].append(event)
            
            # Find synchronization patterns
            sync_groups = []
            
            for window_id, agent_events in time_windows.items():
                if len(agent_events) >= 2:  # At least 2 agents active
                    # Check if agents are performing similar actions
                    agent_actions = {}
                    for agent_id, events_list in agent_events.items():
                        actions = [e.get("action", e.get("event_type", "")) for e in events_list]
                        agent_actions[agent_id] = actions
                    
                    # Find agents with similar action patterns
                    agents = list(agent_actions.keys())
                    for i in range(len(agents)):
                        for j in range(i + 1, len(agents)):
                            agent1, agent2 = agents[i], agents[j]
                            actions1 = set(agent_actions[agent1])
                            actions2 = set(agent_actions[agent2])
                            
                            # Calculate action similarity
                            if actions1 and actions2:
                                similarity = len(actions1 & actions2) / len(actions1 | actions2)
                                
                                if similarity > 0.5:  # 50% similarity threshold
                                    sync_groups.append({
                                        "window_id": window_id,
                                        "agents": [agent1, agent2],
                                        "similarity": similarity,
                                        "common_actions": list(actions1 & actions2)
                                    })
            
            # Group synchronization instances by agent pairs
            agent_pair_syncs = defaultdict(list)
            
            for sync in sync_groups:
                pair = tuple(sorted(sync["agents"]))
                agent_pair_syncs[pair].append(sync)
            
            # Create patterns for frequent synchronization
            for (agent1, agent2), syncs in agent_pair_syncs.items():
                if len(syncs) >= 3:  # At least 3 synchronization instances
                    avg_similarity = sum(s["similarity"] for s in syncs) / len(syncs)
                    
                    pattern = DiscoveredPattern(
                        pattern_type="collaborative",
                        name=f"Synchronization Pattern: {agent1} ⟷ {agent2}",
                        description=f"Agents {agent1} and {agent2} show synchronized behavior ({len(syncs)} instances)",
                        confidence=avg_similarity,
                        significance=avg_similarity * len(syncs),
                        frequency=len(syncs),
                        agents_involved={agent1, agent2},
                        context_requirements={
                            "sync_agents": [agent1, agent2],
                            "min_similarity": 0.5
                        }
                    )
                    
                    # Add synchronization instances
                    for sync in syncs:
                        pattern.instances.append(PatternInstance(
                            timestamp=datetime.fromtimestamp(sync["window_id"] * window_size),
                            data={
                                "agents": sync["agents"],
                                "similarity": sync["similarity"],
                                "common_actions": sync["common_actions"]
                            },
                            confidence=sync["similarity"]
                        ))
                    
                    patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            self.logger.error("Failed to find synchronization patterns", error=str(e))
            return []
    
    async def _find_role_patterns(self, events: List[Dict[str, Any]]) -> List[DiscoveredPattern]:
        """Find role-based interaction patterns"""
        patterns = []
        
        try:
            # Analyze interaction directions and types
            agent_roles = defaultdict(lambda: {"initiator": 0, "responder": 0, "coordinator": 0})
            
            for event in events:
                agent_id = event.get("agent_id")
                event_type = event.get("event_type", "").lower()
                data = event.get("data", {})
                
                if not agent_id:
                    continue
                
                # Determine role based on event characteristics
                if any(keyword in event_type for keyword in ["initiate", "start", "create", "lead"]):
                    agent_roles[agent_id]["initiator"] += 1
                elif any(keyword in event_type for keyword in ["respond", "reply", "acknowledge", "follow"]):
                    agent_roles[agent_id]["responder"] += 1
                elif any(keyword in event_type for keyword in ["coordinate", "organize", "manage", "assign"]):
                    agent_roles[agent_id]["coordinator"] += 1
                
                # Check for coordination indicators in data
                if "task_assignment" in data or "resource_allocation" in data:
                    agent_roles[agent_id]["coordinator"] += 1
            
            # Identify dominant roles
            for agent_id, roles in agent_roles.items():
                total_actions = sum(roles.values())
                
                if total_actions >= 5:  # Minimum actions for role analysis
                    dominant_role = max(roles.keys(), key=lambda k: roles[k])
                    role_strength = roles[dominant_role] / total_actions
                    
                    if role_strength > 0.6:  # 60% of actions in one role
                        pattern = DiscoveredPattern(
                            pattern_type="collaborative",
                            name=f"Role Pattern: {agent_id} as {dominant_role.title()}",
                            description=f"Agent {agent_id} primarily acts as {dominant_role} ({role_strength:.1%} of interactions)",
                            confidence=role_strength,
                            significance=role_strength * total_actions,
                            frequency=roles[dominant_role],
                            agents_involved={agent_id},
                            context_requirements={
                                "agent_role": dominant_role,
                                "min_role_strength": 0.6
                            }
                        )
                        
                        # Find role instances
                        for event in events:
                            if event.get("agent_id") == agent_id:
                                event_type = event.get("event_type", "").lower()
                                
                                # Check if event matches the dominant role
                                role_match = False
                                if dominant_role == "initiator" and any(kw in event_type for kw in ["initiate", "start", "create", "lead"]):
                                    role_match = True
                                elif dominant_role == "responder" and any(kw in event_type for kw in ["respond", "reply", "acknowledge", "follow"]):
                                    role_match = True
                                elif dominant_role == "coordinator" and any(kw in event_type for kw in ["coordinate", "organize", "manage", "assign"]):
                                    role_match = True
                                
                                if role_match:
                                    pattern.instances.append(PatternInstance(
                                        timestamp=event.get("timestamp", datetime.utcnow()),
                                        agent_id=agent_id,
                                        data={
                                            "role": dominant_role,
                                            "event_type": event_type,
                                            "role_strength": role_strength
                                        },
                                        confidence=role_strength
                                    ))
                        
                        patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            self.logger.error("Failed to find role patterns", error=str(e))
            return []
    
    async def validate_pattern(self, pattern: DiscoveredPattern) -> bool:
        """Validate collaborative pattern"""
        try:
            # Check minimum instances
            if len(pattern.instances) < self.config.get("min_pattern_instances", MIN_PATTERN_INSTANCES):
                return False
            
            # Check confidence threshold
            if pattern.confidence < self.config.get("min_pattern_confidence", MIN_PATTERN_CONFIDENCE):
                return False
            
            # Check agent involvement
            if len(pattern.agents_involved) < 1:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error("Collaborative pattern validation failed", error=str(e))
            return False

class PatternRecognitionEngine:
    """
    Production-ready pattern recognition engine for behavioral analysis.
    
    Discovers patterns in agent behavior, interactions, and system performance
    using multiple analysis strategies and machine learning techniques.
    """
    
    def __init__(
        self,
        config: PatternRecognitionConfig,
        knowledge_graph,
        metrics_collector
    ):
        self.config = config
        self.knowledge_graph = knowledge_graph
        self.metrics_collector = metrics_collector
        self.logger = logger.bind(component="pattern_recognition_engine")
        
        # Initialize analyzers
        self._analyzers = {
            "temporal": TemporalPatternAnalyzer(config.__dict__),
            "sequential": SequentialPatternAnalyzer(config.__dict__),
            "collaborative": CollaborativePatternAnalyzer(config.__dict__)
        }
        
        # Pattern storage
        self._discovered_patterns = {}
        self._pattern_cache = {}
        
        # Performance tracking
        self._analysis_performance = []
        self._discovery_stats = defaultdict(int)
        
        # Health status
        self._health_status = "unknown"
        self._is_initialized = False
    
    async def _initialize_resources(self) -> None:
        """Initialize pattern recognition engine resources"""
        try:
            self.logger.info("Initializing pattern recognition engine")
            
            # Initialize Redis for pattern caching
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                max_connections=20,
                retry_on_timeout=True
            )
            
            # Load existing patterns from knowledge graph
            await self._load_existing_patterns()
            
            # Start real-time discovery if enabled
            if self.config.enable_real_time_discovery:
                asyncio.create_task(self._real_time_discovery_loop())
            
            self._is_initialized = True
            self._health_status = "healthy"
            
            self.logger.info(
                "Pattern recognition engine initialized successfully",
                analyzers_count=len(self._analyzers),
                patterns_loaded=len(self._discovered_patterns)
            )
            
        except Exception as e:
            self._health_status = "unhealthy"
            self.logger.error("Failed to initialize pattern recognition engine", error=str(e))
            raise
    
    async def _load_existing_patterns(self) -> None:
        """Load existing patterns from knowledge graph"""
        try:
            from .knowledge_graph import KnowledgeQuery
            
            query = KnowledgeQuery(
                query_type="exact",
                query_data={"content": {"type": "pattern"}},
                max_results=1000,
                include_connections=False
            )
            
            results = await self.knowledge_graph.query_knowledge(query)
            
            for result in results:
                pattern_data = result.content
                if "pattern_id" in pattern_data:
                    self._discovered_patterns[pattern_data["pattern_id"]] = pattern_data
            
            self.logger.info(f"Loaded {len(results)} existing patterns")
            
        except Exception as e:
            self.logger.warning("Failed to load existing patterns", error=str(e))
    
    @track_performance
    async def analyze_event_patterns(self, events: List[Dict[str, Any]]) -> List[DiscoveredPattern]:
        """
        Analyze events for behavioral patterns.
        
        Args:
            events: List of events to analyze
            
        Returns:
            List of discovered patterns
        """
        try:
            analysis_start = datetime.utcnow()
            
            self.logger.debug(
                "Starting pattern analysis",
                events_count=len(events)
            )
            
            all_patterns = []
            
            # Run all analyzers
            for analyzer_name, analyzer in self._analyzers.items():
                try:
                    patterns = await analyzer.analyze_events(events)
                    
                    # Validate patterns
                    valid_patterns = []
                    for pattern in patterns:
                        if await analyzer.validate_pattern(pattern):
                            valid_patterns.append(pattern)
                            self._discovery_stats[analyzer_name] += 1
                    
                    all_patterns.extend(valid_patterns)
                    
                    self.logger.debug(
                        "Analyzer completed",
                        analyzer=analyzer_name,
                        patterns_found=len(valid_patterns)
                    )
                    
                except Exception as e:
                    self.logger.error(
                        "Analyzer failed",
                        analyzer=analyzer_name,
                        error=str(e)
                    )
            
            # Deduplicate and merge similar patterns
            unique_patterns = await self._deduplicate_patterns(all_patterns)
            
            # Store patterns in knowledge graph
            for pattern in unique_patterns:
                await self._store_pattern(pattern)
            
            # Update metrics
            analysis_duration = (datetime.utcnow() - analysis_start).total_seconds()
            self._analysis_performance.append({
                "duration": analysis_duration,
                "events_analyzed": len(events),
                "patterns_found": len(unique_patterns),
                "timestamp": analysis_start
            })
            
            # Keep only last 100 analysis records
            if len(self._analysis_performance) > 100:
                self._analysis_performance.pop(0)
            
            await self.metrics_collector.update_metrics({
                "patterns_discovered": len(unique_patterns),
                "pattern_analysis_duration": analysis_duration,
                "events_analyzed": len(events)
            })
            
            self.logger.info(
                "Pattern analysis completed",
                events_analyzed=len(events),
                patterns_discovered=len(unique_patterns),
                duration=analysis_duration
            )
            
            return unique_patterns
            
        except Exception as e:
            self.logger.error("Pattern analysis failed", error=str(e))
            raise PatternRecognitionError(f"Pattern analysis failed: {str(e)}")
    
    async def discover_new_patterns(self) -> List[DiscoveredPattern]:
        """
        Discover new patterns from recent knowledge graph data.
        
        Returns:
            List of newly discovered patterns
        """
        try:
            self.logger.info("Starting new pattern discovery")
            
            # Get recent events from knowledge graph
            from .knowledge_graph import KnowledgeQuery
            
            recent_time = datetime.utcnow() - timedelta(hours=1)
            
            query = KnowledgeQuery(
                query_type="temporal",
                query_data={"start_time": recent_time},
                max_results=1000,
                include_connections=True
            )
            
            results = await self.knowledge_graph.query_knowledge(query)
            
            # Convert knowledge results to events
            events = []
            for result in results:
                event = {
                    "event_id": result.node_id,
                    "timestamp": result.created_at,
                    "event_type": result.node_type,
                    "agent_id": result.content.get("agent_id"),
                    "data": result.content,
                    "confidence": result.confidence
                }
                events.append(event)
            
            # Analyze for patterns
            new_patterns = await self.analyze_event_patterns(events)
            
            # Filter out patterns we already know
            truly_new_patterns = []
            for pattern in new_patterns:
                if not await self._is_known_pattern(pattern):
                    truly_new_patterns.append(pattern)
                    self._discovered_patterns[pattern.pattern_id] = pattern
            
            self.logger.info(
                "New pattern discovery completed",
                events_analyzed=len(events),
                new_patterns=len(truly_new_patterns)
            )
            
            return truly_new_patterns
            
        except Exception as e:
            self.logger.error("New pattern discovery failed", error=str(e))
            return []
    
    async def _deduplicate_patterns(self, patterns: List[DiscoveredPattern]) -> List[DiscoveredPattern]:
        """Remove duplicate and similar patterns"""
        unique_patterns = []
        
        try:
            for pattern in patterns:
                is_duplicate = False
                
                for existing in unique_patterns:
                    similarity = await self._calculate_pattern_similarity(pattern, existing)
                    
                    if similarity > self.config.similarity_threshold:
                        # Merge patterns by keeping the one with higher confidence
                        if pattern.confidence > existing.confidence:
                            unique_patterns.remove(existing)
                            unique_patterns.append(pattern)
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    unique_patterns.append(pattern)
            
            return unique_patterns
            
        except Exception as e:
            self.logger.error("Pattern deduplication failed", error=str(e))
            return patterns  # Return original patterns if deduplication fails
    
    async def _calculate_pattern_similarity(self, pattern1: DiscoveredPattern, pattern2: DiscoveredPattern) -> float:
        """Calculate similarity between two patterns"""
        try:
            # Different pattern types are not similar
            if pattern1.pattern_type != pattern2.pattern_type:
                return 0.0
            
            # Compare agents involved
            agents1 = pattern1.agents_involved
            agents2 = pattern2.agents_involved
            
            if agents1 and agents2:
                agent_similarity = len(agents1 & agents2) / len(agents1 | agents2)
            else:
                agent_similarity = 0.5  # Neutral if no agent info
            
            # Compare context requirements
            context1 = pattern1.context_requirements
            context2 = pattern2.context_requirements
            
            context_similarity = 0.0
            if context1 and context2:
                common_keys = set(context1.keys()) & set(context2.keys())
                if common_keys:
                    matches = sum(1 for key in common_keys if context1[key] == context2[key])
                    context_similarity = matches / len(common_keys)
            
            # Compare name similarity (simple word overlap)
            name1_words = set(pattern1.name.lower().split())
            name2_words = set(pattern2.name.lower().split())
            
            if name1_words and name2_words:
                name_similarity = len(name1_words & name2_words) / len(name1_words | name2_words)
            else:
                name_similarity = 0.0
            
            # Weighted average
            total_similarity = (
                agent_similarity * 0.4 +
                context_similarity * 0.4 +
                name_similarity * 0.2
            )
            
            return total_similarity
            
        except Exception as e:
            self.logger.error("Pattern similarity calculation failed", error=str(e))
            return 0.0
    
    async def _store_pattern(self, pattern: DiscoveredPattern) -> None:
        """Store pattern in knowledge graph"""
        try:
            from .knowledge_graph import KnowledgeItem
            
            pattern_data = {
                "pattern_id": pattern.pattern_id,
                "pattern_type": pattern.pattern_type,
                "name": pattern.name,
                "description": pattern.description,
                "confidence": pattern.confidence,
                "significance": pattern.significance,
                "frequency": pattern.frequency,
                "discovered_at": pattern.discovered_at.isoformat(),
                "last_seen": pattern.last_seen.isoformat(),
                "agents_involved": list(pattern.agents_involved),
                "context_requirements": pattern.context_requirements,
                "predictive_value": pattern.predictive_value,
                "optimization_potential": pattern.optimization_potential,
                "instances_count": len(pattern.instances)
            }
            
            knowledge_item = KnowledgeItem(
                content=pattern_data,
                node_type="pattern",
                confidence=pattern.confidence,
                source="pattern_recognition",
                tags=["pattern", pattern.pattern_type]
            )
            
            await self.knowledge_graph.add_knowledge_item(knowledge_item)
            
        except Exception as e:
            self.logger.error("Failed to store pattern", pattern_id=pattern.pattern_id, error=str(e))
    
    async def _is_known_pattern(self, pattern: DiscoveredPattern) -> bool:
        """Check if pattern is already known"""
        try:
            for known_pattern in self._discovered_patterns.values():
                if isinstance(known_pattern, dict):
                    # Convert dict to DiscoveredPattern for comparison
                    known_pattern_obj = DiscoveredPattern(
                        pattern_id=known_pattern.get("pattern_id", ""),
                        pattern_type=known_pattern.get("pattern_type", ""),
                        name=known_pattern.get("name", ""),
                        description=known_pattern.get("description", ""),
                        confidence=known_pattern.get("confidence", 0.0),
                        agents_involved=set(known_pattern.get("agents_involved", [])),
                        context_requirements=known_pattern.get("context_requirements", {})
                    )
                else:
                    known_pattern_obj = known_pattern
                
                similarity = await self._calculate_pattern_similarity(pattern, known_pattern_obj)
                if similarity > self.config.similarity_threshold:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error("Known pattern check failed", error=str(e))
            return False
    
    async def _real_time_discovery_loop(self) -> None:
        """Real-time pattern discovery loop"""
        self.logger.info("Starting real-time pattern discovery loop")
        
        while True:
            try:
                await asyncio.sleep(self.config.discovery_interval)
                
                # Discover new patterns
                new_patterns = await self.discover_new_patterns()
                
                if new_patterns:
                    self.logger.info(f"Discovered {len(new_patterns)} new patterns in real-time")
                
            except Exception as e:
                self.logger.error("Error in real-time discovery loop", error=str(e))
                await asyncio.sleep(60)  # Wait before retrying
    
    async def get_pattern_analytics(self) -> Dict[str, Any]:
        """Get pattern recognition analytics"""
        try:
            analytics = {
                "total_patterns": len(self._discovered_patterns),
                "patterns_by_type": defaultdict(int),
                "discovery_stats": dict(self._discovery_stats),
                "performance": {
                    "avg_analysis_time": 0.0,
                    "total_analyses": len(self._analysis_performance),
                    "total_events_analyzed": sum(a["events_analyzed"] for a in self._analysis_performance)
                },
                "pattern_quality": {
                    "avg_confidence": 0.0,
                    "avg_significance": 0.0,
                    "high_confidence_patterns": 0
                }
            }
            
            # Calculate performance metrics
            if self._analysis_performance:
                analytics["performance"]["avg_analysis_time"] = sum(
                    a["duration"] for a in self._analysis_performance
                ) / len(self._analysis_performance)
            
            # Analyze pattern quality
            if self._discovered_patterns:
                confidences = []
                significances = []
                
                for pattern in self._discovered_patterns.values():
                    if isinstance(pattern, dict):
                        pattern_type = pattern.get("pattern_type", "unknown")
                        confidence = pattern.get("confidence", 0.0)
                        significance = pattern.get("significance", 0.0)
                    else:
                        pattern_type = pattern.pattern_type
                        confidence = pattern.confidence
                        significance = pattern.significance
                    
                    analytics["patterns_by_type"][pattern_type] += 1
                    confidences.append(confidence)
                    significances.append(significance)
                    
                    if confidence > 0.8:
                        analytics["pattern_quality"]["high_confidence_patterns"] += 1
                
                if confidences:
                    analytics["pattern_quality"]["avg_confidence"] = sum(confidences) / len(confidences)
                if significances:
                    analytics["pattern_quality"]["avg_significance"] = sum(significances) / len(significances)
            
            return analytics
            
        except Exception as e:
            self.logger.error("Failed to get pattern analytics", error=str(e))
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Pattern recognition engine health check"""
        try:
            # Test Redis connection
            redis_healthy = False
            try:
                await self._redis_client.ping()
                redis_healthy = True
            except Exception:
                pass
            
            return {
                "status": self._health_status,
                "initialized": self._is_initialized,
                "analyzers_count": len(self._analyzers),
                "patterns_discovered": len(self._discovered_patterns),
                "redis_healthy": redis_healthy,
                "analysis_performance_samples": len(self._analysis_performance),
                "real_time_discovery": self.config.enable_real_time_discovery,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def cleanup(self) -> None:
        """Cleanup pattern recognition resources"""
        try:
            self.logger.info("Cleaning up pattern recognition engine resources")
            
            # Close Redis connection
            if hasattr(self, '_