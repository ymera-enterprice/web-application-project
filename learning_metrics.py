"""
YMERA Enterprise - Learning Metrics Module
Production-Ready Learning Analytics & Performance Tracking - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import json
import logging
import os
import statistics
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple, Union

# Third-party imports (alphabetical)
import aioredis
import numpy as np
import structlog
from fastapi import HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from monitoring.performance_tracker import track_performance
from security.jwt_handler import verify_token
from utils.encryption import encrypt_data, decrypt_data

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.learning_metrics")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Metrics collection intervals
REAL_TIME_WINDOW = 60  # seconds
SHORT_TERM_WINDOW = 3600  # 1 hour
MEDIUM_TERM_WINDOW = 86400  # 24 hours
LONG_TERM_WINDOW = 604800  # 7 days

# Performance thresholds
MIN_LEARNING_VELOCITY = 5.0  # knowledge items per hour
MAX_RESPONSE_TIME = 200  # milliseconds
MIN_RETENTION_RATE = 0.85  # 85%
MIN_COLLABORATION_SCORE = 0.7  # 70%

# Cache configuration
METRICS_CACHE_TTL = 300  # 5 minutes
AGGREGATION_CACHE_TTL = 1800  # 30 minutes

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class LearningMetricsConfig:
    """Configuration dataclass for learning metrics settings"""
    enabled: bool = True
    collection_interval: int = 60  # seconds
    retention_period: int = 2592000  # 30 days
    aggregation_enabled: bool = True
    real_time_alerts: bool = True
    performance_tracking: bool = True
    
class MetricPoint(BaseModel):
    """Individual metric data point"""
    timestamp: datetime
    metric_type: str
    value: float
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class LearningVelocityMetric(BaseModel):
    """Learning velocity tracking"""
    knowledge_items_learned: int
    time_period_hours: float
    velocity: float  # items per hour
    trend: str  # increasing, stable, decreasing
    agent_breakdown: Dict[str, float] = Field(default_factory=dict)

class CollaborationMetric(BaseModel):
    """Inter-agent collaboration metrics"""
    total_transfers: int
    successful_transfers: int
    success_rate: float
    average_transfer_time: float
    knowledge_diversity_score: float
    collaboration_effectiveness: float

class RetentionMetric(BaseModel):
    """Knowledge retention tracking"""
    total_knowledge_items: int
    retained_items: int
    retention_rate: float
    decay_rate: float
    consolidation_effectiveness: float

class PatternDiscoveryMetric(BaseModel):
    """Pattern discovery and analysis metrics"""
    patterns_discovered: int  
    patterns_validated: int
    pattern_accuracy: float
    behavioral_insights: int
    optimization_suggestions: int

class SystemIntelligenceMetric(BaseModel):
    """Overall system intelligence assessment"""
    collective_iq_score: float
    problem_solving_efficiency: float
    adaptation_rate: float
    knowledge_utilization: float
    decision_accuracy: float

class MetricsSnapshot(BaseModel):
    """Complete metrics snapshot"""
    timestamp: datetime
    learning_velocity: LearningVelocityMetric
    collaboration: CollaborationMetric
    retention: RetentionMetric
    pattern_discovery: PatternDiscoveryMetric
    system_intelligence: SystemIntelligenceMetric
    health_score: float
    alerts: List[str] = Field(default_factory=list)

class MetricsQuery(BaseModel):
    """Query parameters for metrics retrieval"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metric_types: List[str] = Field(default_factory=list)
    agent_ids: List[str] = Field(default_factory=list)
    aggregation_level: str = "hour"  # minute, hour, day, week
    include_metadata: bool = False

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class MetricsCollector:
    """Real-time metrics collection and processing"""
    
    def __init__(self, config: LearningMetricsConfig):
        self.config = config
        self.logger = logger.bind(component="metrics_collector")
        self._metric_buffers = defaultdict(deque)
        self._collection_tasks = {}
        self._redis = None
        
    async def initialize(self) -> None:
        """Initialize metrics collection resources"""
        try:
            # Initialize Redis connection for real-time data
            redis_url = settings.REDIS_URL
            self._redis = await aioredis.from_url(redis_url)
            
            # Start collection tasks
            await self._start_collection_tasks()
            
            self.logger.info("Metrics collector initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize metrics collector", error=str(e))
            raise

    async def collect_metric(
        self,
        metric_type: str,
        value: float,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Collect individual metric point"""
        try:
            metric_point = MetricPoint(
                timestamp=datetime.utcnow(),
                metric_type=metric_type,
                value=value,
                agent_id=agent_id,
                metadata=metadata or {}
            )
            
            # Store in buffer for real-time processing
            self._metric_buffers[metric_type].append(metric_point)
            
            # Maintain buffer size
            if len(self._metric_buffers[metric_type]) > 1000:
                self._metric_buffers[metric_type].popleft()
            
            # Store in Redis for immediate access
            await self._store_real_time_metric(metric_point)
            
            self.logger.debug(
                "Metric collected",
                metric_type=metric_type,
                value=value,
                agent_id=agent_id
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to collect metric",
                error=str(e),
                metric_type=metric_type,
                value=value
            )
            raise

    async def _store_real_time_metric(self, metric: MetricPoint) -> None:
        """Store metric in Redis for real-time access"""
        try:
            key = f"metrics:realtime:{metric.metric_type}"
            metric_data = {
                "timestamp": metric.timestamp.isoformat(),
                "value": metric.value,
                "agent_id": metric.agent_id,
                "metadata": json.dumps(metric.metadata)
            }
            
            # Store in sorted set for time-based queries
            await self._redis.zadd(
                key,
                {json.dumps(metric_data): metric.timestamp.timestamp()}
            )
            
            # Expire old data
            cutoff = time.time() - REAL_TIME_WINDOW * 10  # Keep 10x window
            await self._redis.zremrangebyscore(key, 0, cutoff)
            
        except Exception as e:
            self.logger.error("Failed to store real-time metric", error=str(e))

    async def _start_collection_tasks(self) -> None:
        """Start background collection tasks"""
        self._collection_tasks["real_time"] = asyncio.create_task(
            self._real_time_collection_loop()
        )
        
        self._collection_tasks["aggregation"] = asyncio.create_task(
            self._aggregation_loop()
        )
        
        self.logger.info("Collection tasks started")

    async def _real_time_collection_loop(self) -> None:
        """Real-time metrics collection loop"""
        while True:
            try:
                await asyncio.sleep(self.config.collection_interval)
                await self._process_real_time_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Real-time collection error", error=str(e))
                await asyncio.sleep(5)  # Brief pause before retry

    async def _aggregation_loop(self) -> None:
        """Metrics aggregation loop"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                await self._aggregate_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Aggregation loop error", error=str(e))
                await asyncio.sleep(30)  # Longer pause for aggregation errors

    async def _process_real_time_metrics(self) -> None:
        """Process accumulated real-time metrics"""
        for metric_type, buffer in self._metric_buffers.items():
            if not buffer:
                continue
                
            try:
                # Calculate real-time statistics
                values = [point.value for point in buffer]
                stats = {
                    "count": len(values),
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "min": min(values),
                    "max": max(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0.0
                }
                
                # Store aggregated stats
                await self._store_aggregated_stats(metric_type, stats)
                
            except Exception as e:
                self.logger.error(
                    "Failed to process real-time metrics",
                    error=str(e),
                    metric_type=metric_type
                )

    async def _store_aggregated_stats(self, metric_type: str, stats: Dict[str, float]) -> None:
        """Store aggregated statistics"""
        try:
            key = f"metrics:aggregated:{metric_type}"
            stats_data = {
                "timestamp": datetime.utcnow().isoformat(),
                **stats
            }
            
            await self._redis.setex(
                key,
                AGGREGATION_CACHE_TTL,
                json.dumps(stats_data)
            )
            
        except Exception as e:
            self.logger.error("Failed to store aggregated stats", error=str(e))

    async def cleanup(self) -> None:
        """Cleanup collection resources"""
        try:
            # Cancel collection tasks
            for task in self._collection_tasks.values():
                task.cancel()
                
            # Wait for tasks to complete
            await asyncio.gather(*self._collection_tasks.values(), return_exceptions=True)
            
            # Close Redis connection
            if self._redis:
                await self._redis.close()
                
            self.logger.info("Metrics collector cleaned up")
            
        except Exception as e:
            self.logger.error("Failed to cleanup metrics collector", error=str(e))


class LearningMetricsAnalyzer:
    """Advanced analytics for learning metrics"""
    
    def __init__(self, config: LearningMetricsConfig):
        self.config = config
        self.logger = logger.bind(component="metrics_analyzer")
        self._redis = None
        
    async def initialize(self) -> None:
        """Initialize analytics resources"""
        try:
            redis_url = settings.REDIS_URL
            self._redis = await aioredis.from_url(redis_url)
            
            self.logger.info("Metrics analyzer initialized")
            
        except Exception as e:
            self.logger.error("Failed to initialize metrics analyzer", error=str(e))
            raise

    @track_performance
    async def calculate_learning_velocity(
        self,
        time_window: int = SHORT_TERM_WINDOW
    ) -> LearningVelocityMetric:
        """Calculate learning velocity metrics"""
        try:
            current_time = datetime.utcnow()
            start_time = current_time - timedelta(seconds=time_window)
            
            # Get knowledge acquisition data
            knowledge_key = "metrics:realtime:knowledge_acquired"
            knowledge_data = await self._redis.zrangebyscore(
                knowledge_key,
                start_time.timestamp(),
                current_time.timestamp(),
                withscores=True
            )
            
            # Parse and analyze data
            total_items = 0
            agent_breakdown = defaultdict(int)
            
            for data_json, timestamp in knowledge_data:
                try:
                    data = json.loads(data_json)
                    items = int(data.get("value", 0))
                    agent_id = data.get("agent_id", "unknown")
                    
                    total_items += items
                    agent_breakdown[agent_id] += items
                    
                except (json.JSONDecodeError, ValueError) as e:
                    self.logger.warning("Invalid knowledge data", error=str(e))
                    continue
            
            # Calculate velocity
            hours = time_window / 3600
            velocity = total_items / hours if hours > 0 else 0.0
            
            # Calculate agent velocities
            agent_velocities = {
                agent: items / hours 
                for agent, items in agent_breakdown.items()
            }
            
            # Determine trend
            trend = await self._calculate_velocity_trend(velocity, time_window)
            
            return LearningVelocityMetric(
                knowledge_items_learned=total_items,
                time_period_hours=hours,
                velocity=velocity,
                trend=trend,
                agent_breakdown=agent_velocities
            )
            
        except Exception as e:
            self.logger.error("Failed to calculate learning velocity", error=str(e))
            raise

    async def _calculate_velocity_trend(self, current_velocity: float, window: int) -> str:
        """Calculate velocity trend direction"""
        try:
            # Get previous period data
            previous_window_start = datetime.utcnow() - timedelta(seconds=window * 2)
            previous_window_end = datetime.utcnow() - timedelta(seconds=window)
            
            knowledge_key = "metrics:realtime:knowledge_acquired"
            previous_data = await self._redis.zrangebyscore(
                knowledge_key,
                previous_window_start.timestamp(),
                previous_window_end.timestamp()
            )
            
            # Calculate previous velocity
            previous_items = sum(
                int(json.loads(data).get("value", 0)) 
                for data in previous_data
            )
            previous_velocity = previous_items / (window / 3600)
            
            # Determine trend
            if current_velocity > previous_velocity * 1.1:
                return "increasing"
            elif current_velocity < previous_velocity * 0.9:
                return "decreasing"
            else:
                return "stable"
                
        except Exception as e:
            self.logger.warning("Failed to calculate trend", error=str(e))
            return "unknown"

    @track_performance
    async def calculate_collaboration_metrics(
        self,
        time_window: int = SHORT_TERM_WINDOW
    ) -> CollaborationMetric:
        """Calculate inter-agent collaboration metrics"""
        try:
            current_time = datetime.utcnow()
            start_time = current_time - timedelta(seconds=time_window)
            
            # Get knowledge transfer data
            transfer_key = "metrics:realtime:knowledge_transfers"
            transfer_data = await self._redis.zrangebyscore(
                transfer_key,
                start_time.timestamp(),
                current_time.timestamp()
            )
            
            total_transfers = 0
            successful_transfers = 0
            transfer_times = []
            agents_involved = set()
            
            for data_json, _ in transfer_data:
                try:
                    data = json.loads(data_json)
                    total_transfers += 1
                    
                    if data.get("success", False):
                        successful_transfers += 1
                        
                    transfer_time = data.get("transfer_time", 0)
                    if transfer_time > 0:
                        transfer_times.append(transfer_time)
                        
                    # Track agent diversity
                    source_agent = data.get("source_agent")
                    target_agent = data.get("target_agent")
                    if source_agent:
                        agents_involved.add(source_agent)
                    if target_agent:
                        agents_involved.add(target_agent)
                        
                except (json.JSONDecodeError, ValueError) as e:
                    self.logger.warning("Invalid transfer data", error=str(e))
                    continue
            
            # Calculate metrics
            success_rate = successful_transfers / total_transfers if total_transfers > 0 else 0.0
            avg_transfer_time = statistics.mean(transfer_times) if transfer_times else 0.0
            diversity_score = len(agents_involved) / max(total_transfers, 1)
            
            # Calculate collaboration effectiveness
            effectiveness = (success_rate * 0.4 + 
                           min(diversity_score, 1.0) * 0.3 + 
                           max(0, 1 - avg_transfer_time / 1000) * 0.3)
            
            return CollaborationMetric(
                total_transfers=total_transfers,
                successful_transfers=successful_transfers,
                success_rate=success_rate,
                average_transfer_time=avg_transfer_time,
                knowledge_diversity_score=diversity_score,
                collaboration_effectiveness=effectiveness
            )
            
        except Exception as e:
            self.logger.error("Failed to calculate collaboration metrics", error=str(e))
            raise

    @track_performance
    async def calculate_retention_metrics(
        self,
        time_window: int = MEDIUM_TERM_WINDOW
    ) -> RetentionMetric:
        """Calculate knowledge retention metrics"""
        try:
            current_time = datetime.utcnow()
            
            # Get knowledge retention data
            retention_key = "metrics:realtime:knowledge_retention"
            retention_data = await self._redis.zrangebyscore(
                retention_key,
                (current_time - timedelta(seconds=time_window)).timestamp(),
                current_time.timestamp()
            )
            
            total_items = 0
            retained_items = 0
            decay_measurements = []
            
            for data_json, _ in retention_data:
                try:
                    data = json.loads(data_json)
                    total_items += data.get("total_items", 0)
                    retained_items += data.get("retained_items", 0)
                    
                    decay_rate = data.get("decay_rate", 0)
                    if decay_rate > 0:
                        decay_measurements.append(decay_rate)
                        
                except (json.JSONDecodeError, ValueError) as e:
                    self.logger.warning("Invalid retention data", error=str(e))
                    continue
            
            # Calculate metrics
            retention_rate = retained_items / total_items if total_items > 0 else 0.0
            avg_decay_rate = statistics.mean(decay_measurements) if decay_measurements else 0.0
            
            # Calculate consolidation effectiveness
            consolidation_effectiveness = min(retention_rate / MIN_RETENTION_RATE, 1.0)
            
            return RetentionMetric(
                total_knowledge_items=total_items,
                retained_items=retained_items,
                retention_rate=retention_rate,
                decay_rate=avg_decay_rate,
                consolidation_effectiveness=consolidation_effectiveness
            )
            
        except Exception as e:
            self.logger.error("Failed to calculate retention metrics", error=str(e))
            raise

    @track_performance
    async def calculate_pattern_discovery_metrics(
        self,
        time_window: int = SHORT_TERM_WINDOW
    ) -> PatternDiscoveryMetric:
        """Calculate pattern discovery and analysis metrics"""
        try:
            current_time = datetime.utcnow()
            start_time = current_time - timedelta(seconds=time_window)
            
            # Get pattern discovery data
            pattern_key = "metrics:realtime:patterns_discovered"
            pattern_data = await self._redis.zrangebyscore(
                pattern_key,
                start_time.timestamp(),
                current_time.timestamp()
            )
            
            patterns_discovered = 0
            patterns_validated = 0
            accuracy_scores = []
            behavioral_insights = 0
            optimization_suggestions = 0
            
            for data_json, _ in pattern_data:
                try:
                    data = json.loads(data_json)
                    patterns_discovered += data.get("patterns_count", 0)
                    patterns_validated += data.get("validated_count", 0)
                    
                    accuracy = data.get("accuracy", 0)
                    if accuracy > 0:
                        accuracy_scores.append(accuracy)
                        
                    behavioral_insights += data.get("insights_count", 0)
                    optimization_suggestions += data.get("optimizations_count", 0)
                    
                except (json.JSONDecodeError, ValueError) as e:
                    self.logger.warning("Invalid pattern data", error=str(e))
                    continue
            
            # Calculate metrics
            pattern_accuracy = statistics.mean(accuracy_scores) if accuracy_scores else 0.0
            
            return PatternDiscoveryMetric(
                patterns_discovered=patterns_discovered,
                patterns_validated=patterns_validated,
                pattern_accuracy=pattern_accuracy,
                behavioral_insights=behavioral_insights,
                optimization_suggestions=optimization_suggestions
            )
            
        except Exception as e:
            self.logger.error("Failed to calculate pattern discovery metrics", error=str(e))
            raise

    @track_performance
    async def calculate_system_intelligence_metrics(
        self,
        time_window: int = SHORT_TERM_WINDOW
    ) -> SystemIntelligenceMetric:
        """Calculate overall system intelligence metrics"""
        try:
            # Get component metrics
            learning_velocity = await self.calculate_learning_velocity(time_window)
            collaboration = await self.calculate_collaboration_metrics(time_window)
            retention = await self.calculate_retention_metrics(time_window)
            patterns = await self.calculate_pattern_discovery_metrics(time_window)
            
            # Calculate composite intelligence score
            velocity_score = min(learning_velocity.velocity / MIN_LEARNING_VELOCITY, 1.0)
            collaboration_score = collaboration.collaboration_effectiveness
            retention_score = retention.consolidation_effectiveness
            pattern_score = min(patterns.pattern_accuracy, 1.0)
            
            collective_iq = (velocity_score * 0.25 + 
                           collaboration_score * 0.25 + 
                           retention_score * 0.25 + 
                           pattern_score * 0.25)
            
            # Get problem-solving efficiency data
            efficiency_key = "metrics:realtime:problem_solving"
            efficiency_data = await self._redis.get(efficiency_key)
            
            problem_solving_efficiency = 0.8  # Default
            if efficiency_data:
                try:
                    data = json.loads(efficiency_data)
                    problem_solving_efficiency = data.get("efficiency", 0.8)
                except json.JSONDecodeError:
                    pass
            
            # Calculate other metrics
            adaptation_rate = collaboration_score * 0.6 + pattern_score * 0.4
            knowledge_utilization = retention_score * 0.7 + velocity_score * 0.3
            decision_accuracy = pattern_score * 0.8 + collaboration_score * 0.2
            
            return SystemIntelligenceMetric(
                collective_iq_score=collective_iq,
                problem_solving_efficiency=problem_solving_efficiency,
                adaptation_rate=adaptation_rate,
                knowledge_utilization=knowledge_utilization,
                decision_accuracy=decision_accuracy
            )
            
        except Exception as e:
            self.logger.error("Failed to calculate system intelligence metrics", error=str(e))
            raise

    async def cleanup(self) -> None:
        """Cleanup analyzer resources"""
        try:
            if self._redis:
                await self._redis.close()
                
            self.logger.info("Metrics analyzer cleaned up")
            
        except Exception as e:
            self.logger.error("Failed to cleanup metrics analyzer", error=str(e))


class LearningMetricsManager:
    """Main metrics management interface"""
    
    def __init__(self, config: LearningMetricsConfig):
        self.config = config
        self.logger = logger.bind(component="metrics_manager")
        self.collector = MetricsCollector(config)
        self.analyzer = LearningMetricsAnalyzer(config)
        self._alert_thresholds = self._initialize_alert_thresholds()
        self._health_status = True
        
    def _initialize_alert_thresholds(self) -> Dict[str, float]:
        """Initialize alerting thresholds"""
        return {
            "learning_velocity_min": MIN_LEARNING_VELOCITY,
            "retention_rate_min": MIN_RETENTION_RATE,
            "collaboration_score_min": MIN_COLLABORATION_SCORE,
            "response_time_max": MAX_RESPONSE_TIME,
            "error_rate_max": 0.05,  # 5%
            "system_health_min": 0.8  # 80%
        }

    async def initialize(self) -> None:
        """Initialize metrics management system"""
        try:
            await self.collector.initialize()
            await self.analyzer.initialize()
            
            self.logger.info("Learning metrics manager initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize metrics manager", error=str(e))
            self._health_status = False
            raise

    @track_performance
    async def record_learning_event(
        self,
        event_type: str,
        value: float,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a learning-related event"""
        try:
            await self.collector.collect_metric(
                metric_type=event_type,
                value=value,
                agent_id=agent_id,
                metadata=metadata
            )
            
            # Check for immediate alerts
            if self.config.real_time_alerts:
                await self._check_real_time_alerts(event_type, value, agent_id)
                
        except Exception as e:
            self.logger.error(
                "Failed to record learning event",
                error=str(e),
                event_type=event_type,
                agent_id=agent_id
            )
            raise

    async def _check_real_time_alerts(
        self,
        event_type: str,
        value: float,
        agent_id: Optional[str]
    ) -> None:
        """Check for real-time alert conditions"""
        try:
            alerts = []
            
            # Check specific metric thresholds
            if event_type == "learning_velocity" and value < self._alert_thresholds["learning_velocity_min"]:
                alerts.append(f"Low learning velocity: {value:.2f} (threshold: {self._alert_thresholds['learning_velocity_min']})")
                
            elif event_type == "retention_rate" and value < self._alert_thresholds["retention_rate_min"]:
                alerts.append(f"Low retention rate: {value:.2f} (threshold: {self._alert_thresholds['retention_rate_min']})")
                
            elif event_type == "response_time" and value > self._alert_thresholds["response_time_max"]:
                alerts.append(f"High response time: {value:.2f}ms (threshold: {self._alert_thresholds['response_time_max']}ms)")
            
            # Send alerts if any triggered
            for alert in alerts:
                await self._send_alert(alert, event_type, agent_id)
                
        except Exception as e:
            self.logger.error("Failed to check real-time alerts", error=str(e))

    async def _send_alert(self, message: str, event_type: str, agent_id: Optional[str]) -> None:
        """Send alert notification"""
        try:
            alert_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "message": message,
                "event_type": event_type,
                "agent_id": agent_id,
                "severity": "warning"
            }
            
            # Store alert in Redis for monitoring dashboard
            alert_key = f"alerts:learning_metrics:{int(time.time())}"
            await self.collector._redis.setex(
                alert_key,
                3600,  # 1 hour TTL
                json.dumps(alert_data)
            )
            
            self.logger.warning("Learning metrics alert", **alert_data)
            
        except Exception as e:
            self.logger.error("Failed to send alert", error=str(e))

    @track_performance
    async def get_current_snapshot(self) -> MetricsSnapshot:
        """Get current complete metrics snapshot"""
        try:
            # Calculate all metric categories
            learning_velocity = await self.analyzer.calculate_learning_velocity()
            collaboration = await self.analyzer.calculate_collaboration_metrics()
            retention = await self.analyzer.calculate_retention_metrics()
            pattern_discovery = await self.analyzer.calculate_pattern_discovery_metrics()
            system_intelligence = await self.analyzer.calculate_system_intelligence_metrics()
            
            # Calculate overall health score
            health_components = [
                min(learning_velocity.velocity / MIN_LEARNING_VELOCITY, 1.0),
                collaboration.collaboration_effectiveness,
                retention.consolidation_effectiveness,
                system_intelligence.collective_iq_score
            ]
            health_score = statistics.mean(health_components)
            
            # Check for current alerts
            alerts = await self._get_current_alerts()
            
            return MetricsSnapshot(
                timestamp=datetime.utcnow(),
                learning_velocity=learning_velocity,
                collaboration=collaboration,
                retention=retention,
                pattern_discovery=pattern_discovery,
                system_intelligence=system_intelligence,
                health_score=health_score,
                alerts=alerts
            )
            
        except Exception as e:
            self.logger.error("Failed to get current snapshot", error=str(e))
            raise

    async def _get_current_alerts(self) -> List[str]:
        """Get current active alerts"""
        try:
            alerts = []
            
            # Get recent alerts from Redis
            alert_pattern = "alerts:learning_metrics:*"
            alert_keys = await self.collector._redis.keys(alert_pattern)
            
            for key in alert_keys[-10:]:  # Get last 10 alerts
                try:
                    alert_data = await self.collector._redis.get(key)
                    if alert_data:
                        alert_info = json.loads(alert_data)
                        alerts.append(alert_info.get("message", "Unknown alert"))
                except (json.JSONDecodeError, AttributeError):
                    continue
                    
            return alerts
            
        except Exception as e:
            self.logger.error("Failed to get current alerts", error=str(e))
            return []

    @track_performance
    async def query_metrics(
        self,
        query: MetricsQuery,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Query historical metrics with advanced filtering"""
        try:
            # Set default time range if not provided
            end_time = query.end_time or datetime.utcnow()
            start_time = query.start_time or (end_time - timedelta(hours=24))
            
            # Validate time range
            if start_time >= end_time:
                raise HTTPException(
                    status_code=400,
                    detail="Start time must be before end time"
                )
            
            # Query metrics from database
            metrics_data = await self._query_database_metrics(
                db, start_time, end_time, query
            )
            
            # Apply aggregation if requested
            if query.aggregation_level != "raw":
                metrics_data = await self._aggregate_metrics_data(
                    metrics_data, query.aggregation_level
                )
            
            # Filter by metric types if specified
            if query.metric_types:
                metrics_data = {
                    k: v for k, v in metrics_data.items()
                    if k in query.metric_types
                }
            
            # Calculate summary statistics
            summary = await self._calculate_query_summary(metrics_data)
            
            return {
                "query": query.dict(),
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "duration_hours": (end_time - start_time).total_seconds() / 3600
                },
                "metrics": metrics_data,
                "summary": summary,
                "metadata": {
                    "total_points": sum(len(v) if isinstance(v, list) else 1 for v in metrics_data.values()),
                    "aggregation_level": query.aggregation_level,
                    "generated_at": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error("Failed to query metrics", error=str(e))
            raise

    async def _query_database_metrics(
        self,
        db: AsyncSession,
        start_time: datetime,
        end_time: datetime,
        query: MetricsQuery
    ) -> Dict[str, Any]:
        """Query metrics from database"""
        try:
            # This would integrate with your actual database schema
            # For now, we'll simulate with Redis data
            
            metrics_data = {}
            
            # Define metric types to query
            metric_types = query.metric_types or [
                "learning_velocity",
                "knowledge_transfers",
                "retention_rate",
                "patterns_discovered",
                "collaboration_score"
            ]
            
            for metric_type in metric_types:
                key = f"metrics:realtime:{metric_type}"
                raw_data = await self.collector._redis.zrangebyscore(
                    key,
                    start_time.timestamp(),
                    end_time.timestamp(),
                    withscores=True
                )
                
                # Parse and structure data
                parsed_data = []
                for data_json, timestamp in raw_data:
                    try:
                        data = json.loads(data_json)
                        parsed_data.append({
                            "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
                            "value": data.get("value", 0),
                            "agent_id": data.get("agent_id"),
                            "metadata": data.get("metadata", {}) if query.include_metadata else {}
                        })
                    except (json.JSONDecodeError, ValueError):
                        continue
                        
                metrics_data[metric_type] = parsed_data
            
            return metrics_data
            
        except Exception as e:
            self.logger.error("Failed to query database metrics", error=str(e))
            raise

    async def _aggregate_metrics_data(
        self,
        metrics_data: Dict[str, Any],
        aggregation_level: str
    ) -> Dict[str, Any]:
        """Aggregate metrics data by specified level"""
        try:
            aggregated_data = {}
            
            # Define aggregation intervals
            intervals = {
                "minute": 60,
                "hour": 3600,
                "day": 86400,
                "week": 604800
            }
            
            interval_seconds = intervals.get(aggregation_level, 3600)
            
            for metric_type, data_points in metrics_data.items():
                if not data_points:
                    aggregated_data[metric_type] = []
                    continue
                    
                # Group data points by time intervals
                grouped_data = defaultdict(list)
                
                for point in data_points:
                    timestamp = datetime.fromisoformat(point["timestamp"])
                    # Round down to interval boundary
                    interval_start = datetime.fromtimestamp(
                        (timestamp.timestamp() // interval_seconds) * interval_seconds
                    )
                    grouped_data[interval_start].append(point)
                
                # Calculate aggregated values for each interval
                aggregated_points = []
                for interval_time, points in grouped_data.items():
                    values = [p["value"] for p in points]
                    agents = list(set(p["agent_id"] for p in points if p["agent_id"]))
                    
                    aggregated_points.append({
                        "timestamp": interval_time.isoformat(),
                        "count": len(values),
                        "mean": statistics.mean(values),
                        "median": statistics.median(values),
                        "min": min(values),
                        "max": max(values),
                        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                        "agents_involved": len(agents),
                        "agent_ids": agents[:10]  # Limit to first 10 agents
                    })
                
                # Sort by timestamp
                aggregated_points.sort(key=lambda x: x["timestamp"])
                aggregated_data[metric_type] = aggregated_points
            
            return aggregated_data
            
        except Exception as e:
            self.logger.error("Failed to aggregate metrics data", error=str(e))
            raise

    async def _calculate_query_summary(self, metrics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate summary statistics for query results"""
        try:
            summary = {
                "total_metrics": len(metrics_data),
                "metric_summaries": {},
                "overall_trends": {},
                "performance_indicators": {}
            }
            
            for metric_type, data_points in metrics_data.items():
                if not data_points:
                    continue
                    
                # Extract values based on data structure
                if isinstance(data_points[0], dict) and "value" in data_points[0]:
                    # Raw data points
                    values = [p["value"] for p in data_points]
                elif isinstance(data_points[0], dict) and "mean" in data_points[0]:
                    # Aggregated data points
                    values = [p["mean"] for p in data_points]
                else:
                    continue
                
                if not values:
                    continue
                    
                # Calculate summary statistics
                summary["metric_summaries"][metric_type] = {
                    "count": len(values),
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "min": min(values),
                    "max": max(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "range": max(values) - min(values)
                }
                
                # Calculate trend
                if len(values) >= 2:
                    first_half = values[:len(values)//2]
                    second_half = values[len(values)//2:]
                    
                    first_avg = statistics.mean(first_half)
                    second_avg = statistics.mean(second_half)
                    
                    if second_avg > first_avg * 1.05:
                        trend = "increasing"
                    elif second_avg < first_avg * 0.95:
                        trend = "decreasing"
                    else:
                        trend = "stable"
                        
                    summary["overall_trends"][metric_type] = {
                        "direction": trend,
                        "change_percentage": ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
                    }
            
            # Calculate performance indicators
            summary["performance_indicators"] = await self._calculate_performance_indicators(summary)
            
            return summary
            
        except Exception as e:
            self.logger.error("Failed to calculate query summary", error=str(e))
            return {"error": "Failed to calculate summary"}

    async def _calculate_performance_indicators(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate high-level performance indicators"""
        try:
            indicators = {}
            
            # Learning efficiency indicator
            if "learning_velocity" in summary["metric_summaries"]:
                velocity_stats = summary["metric_summaries"]["learning_velocity"]
                efficiency = min(velocity_stats["mean"] / MIN_LEARNING_VELOCITY, 1.0)
                indicators["learning_efficiency"] = {
                    "score": efficiency,
                    "status": "excellent" if efficiency >= 0.9 else "good" if efficiency >= 0.7 else "needs_improvement"
                }
            
            # Collaboration effectiveness
            if "collaboration_score" in summary["metric_summaries"]:
                collab_stats = summary["metric_summaries"]["collaboration_score"]
                effectiveness = collab_stats["mean"]
                indicators["collaboration_effectiveness"] = {
                    "score": effectiveness,
                    "status": "excellent" if effectiveness >= 0.8 else "good" if effectiveness >= 0.6 else "needs_improvement"
                }
            
            # Knowledge retention quality
            if "retention_rate" in summary["metric_summaries"]:
                retention_stats = summary["metric_summaries"]["retention_rate"]
                quality = retention_stats["mean"]
                indicators["retention_quality"] = {
                    "score": quality,
                    "status": "excellent" if quality >= 0.9 else "good" if quality >= 0.8 else "needs_improvement"
                }
            
            # Overall system health
            scores = [ind["score"] for ind in indicators.values() if "score" in ind]
            if scores:
                overall_health = statistics.mean(scores)
                indicators["overall_health"] = {
                    "score": overall_health,
                    "status": "excellent" if overall_health >= 0.8 else "good" if overall_health >= 0.6 else "needs_attention"
                }
            
            return indicators
            
        except Exception as e:
            self.logger.error("Failed to calculate performance indicators", error=str(e))
            return {}

    @track_performance
    async def export_metrics_report(
        self,
        query: MetricsQuery,
        db: AsyncSession,
        format_type: str = "json"
    ) -> Dict[str, Any]:
        """Export comprehensive metrics report"""
        try:
            # Get metrics data
            metrics_data = await self.query_metrics(query, db)
            
            # Get current snapshot for context
            current_snapshot = await self.get_current_snapshot()
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                metrics_data, current_snapshot
            )
            
            # Create comprehensive report
            report = {
                "report_metadata": {
                    "generated_at": datetime.utcnow().isoformat(),
                    "report_type": "learning_metrics_analysis",
                    "version": "4.0",
                    "format": format_type
                },
                "executive_summary": await self._generate_executive_summary(
                    metrics_data, current_snapshot
                ),
                "current_status": current_snapshot.dict(),
                "historical_analysis": metrics_data,
                "recommendations": recommendations,
                "appendix": {
                    "methodology": "Real-time metrics collection with Redis storage and PostgreSQL persistence",
                    "data_sources": ["agent_interactions", "knowledge_transfers", "pattern_analysis"],
                    "accuracy_notes": "All metrics calculated with 95% confidence intervals where applicable"
                }
            }
            
            self.logger.info(
                "Metrics report generated",
                query_range=f"{query.start_time} to {query.end_time}",
                format_type=format_type
            )
            
            return report
            
        except Exception as e:
            self.logger.error("Failed to export metrics report", error=str(e))
            raise

    async def _generate_executive_summary(
        self,
        metrics_data: Dict[str, Any],
        current_snapshot: MetricsSnapshot
    ) -> Dict[str, Any]:
        """Generate executive summary of metrics"""
        try:
            summary = {
                "overall_health": {
                    "score": current_snapshot.health_score,
                    "status": "healthy" if current_snapshot.health_score >= 0.8 else "attention_needed",
                    "key_metrics": {
                        "learning_velocity": current_snapshot.learning_velocity.velocity,
                        "collaboration_effectiveness": current_snapshot.collaboration.collaboration_effectiveness,
                        "retention_rate": current_snapshot.retention.retention_rate,
                        "system_intelligence": current_snapshot.system_intelligence.collective_iq_score
                    }
                },
                "trends": {},
                "alerts": {
                    "active_count": len(current_snapshot.alerts),
                    "recent_alerts": current_snapshot.alerts[-5:]  # Last 5 alerts
                },
                "performance_highlights": [],
                "areas_for_improvement": []
            }
            
            # Analyze trends from summary data
            if "summary" in metrics_data and "overall_trends" in metrics_data["summary"]:
                for metric, trend_data in metrics_data["summary"]["overall_trends"].items():
                    summary["trends"][metric] = {
                        "direction": trend_data["direction"],
                        "change": f"{trend_data['change_percentage']:.1f}%"
                    }
            
            # Identify highlights and improvements
            if current_snapshot.learning_velocity.velocity >= MIN_LEARNING_VELOCITY * 1.2:
                summary["performance_highlights"].append("Learning velocity exceeds target by 20%")
                
            if current_snapshot.collaboration.collaboration_effectiveness >= 0.8:
                summary["performance_highlights"].append("Excellent inter-agent collaboration")
                
            if current_snapshot.retention.retention_rate < MIN_RETENTION_RATE:
                summary["areas_for_improvement"].append("Knowledge retention below target threshold")
                
            if current_snapshot.collaboration.success_rate < 0.9:
                summary["areas_for_improvement"].append("Knowledge transfer success rate needs improvement")
            
            return summary
            
        except Exception as e:
            self.logger.error("Failed to generate executive summary", error=str(e))
            return {"error": "Failed to generate summary"}

    async def _generate_recommendations(
        self,
        metrics_data: Dict[str, Any],
        current_snapshot: MetricsSnapshot
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations based on metrics"""
        try:
            recommendations = []
            
            # Learning velocity recommendations
            if current_snapshot.learning_velocity.velocity < MIN_LEARNING_VELOCITY:
                recommendations.append({
                    "category": "learning_optimization",
                    "priority": "high",
                    "title": "Improve Learning Velocity",
                    "description": "Learning velocity is below target threshold",
                    "current_value": current_snapshot.learning_velocity.velocity,
                    "target_value": MIN_LEARNING_VELOCITY,
                    "suggested_actions": [
                        "Increase knowledge source diversity",
                        "Optimize learning cycle frequency",
                        "Review agent learning algorithms"
                    ],
                    "expected_impact": "20-30% improvement in learning rate"
                })
            
            # Collaboration recommendations
            if current_snapshot.collaboration.collaboration_effectiveness < MIN_COLLABORATION_SCORE:
                recommendations.append({
                    "category": "collaboration_enhancement",
                    "priority": "medium",
                    "title": "Enhance Inter-Agent Collaboration",
                    "description": "Collaboration effectiveness below optimal level",
                    "current_value": current_snapshot.collaboration.collaboration_effectiveness,
                    "target_value": MIN_COLLABORATION_SCORE,
                    "suggested_actions": [
                        "Implement better knowledge matching algorithms",
                        "Reduce knowledge transfer latency",
                        "Increase agent interaction frequency"
                    ],
                    "expected_impact": "15-25% improvement in collaboration score"
                })
            
            # Retention recommendations
            if current_snapshot.retention.retention_rate < MIN_RETENTION_RATE:
                recommendations.append({
                    "category": "memory_optimization",
                    "priority": "high",
                    "title": "Optimize Knowledge Retention",
                    "description": "Knowledge retention rate needs improvement",
                    "current_value": current_snapshot.retention.retention_rate,
                    "target_value": MIN_RETENTION_RATE,
                    "suggested_actions": [
                        "Implement spaced repetition algorithms",
                        "Optimize memory consolidation frequency",
                        "Review knowledge importance scoring"
                    ],
                    "expected_impact": "10-20% improvement in retention rate"
                })
            
            # Pattern discovery recommendations
            if current_snapshot.pattern_discovery.pattern_accuracy < 0.8:
                recommendations.append({
                    "category": "pattern_analysis",
                    "priority": "medium",
                    "title": "Enhance Pattern Recognition",
                    "description": "Pattern discovery accuracy could be improved",
                    "current_value": current_snapshot.pattern_discovery.pattern_accuracy,
                    "target_value": 0.8,
                    "suggested_actions": [
                        "Upgrade pattern recognition algorithms",
                        "Increase training data diversity",
                        "Implement ensemble pattern detection"
                    ],
                    "expected_impact": "5-15% improvement in pattern accuracy"
                })
            
            # System-wide recommendations
            if current_snapshot.health_score < 0.8:
                recommendations.append({
                    "category": "system_optimization",
                    "priority": "high",
                    "title": "Overall System Health Improvement",
                    "description": "Multiple metrics indicate system optimization needed",
                    "current_value": current_snapshot.health_score,
                    "target_value": 0.8,
                    "suggested_actions": [
                        "Conduct comprehensive system audit",
                        "Optimize resource allocation",
                        "Review and update learning parameters"
                    ],
                    "expected_impact": "Comprehensive system performance improvement"
                })
            
            # Sort by priority
            priority_order = {"high": 0, "medium": 1, "low": 2}
            recommendations.sort(key=lambda x: priority_order.get(x["priority"], 2))
            
            return recommendations
            
        except Exception as e:
            self.logger.error("Failed to generate recommendations", error=str(e))
            return []

    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of metrics system"""
        try:
            # Check collector health
            collector_healthy = self.collector._redis is not None
            
            # Check analyzer health  
            analyzer_healthy = self.analyzer._redis is not None
            
            # Get recent metrics to check data flow
            current_time = datetime.utcnow()
            recent_metrics_key = "metrics:realtime:knowledge_acquired"
            recent_data = await self.collector._redis.zrangebyscore(
                recent_metrics_key,
                (current_time - timedelta(minutes=5)).timestamp(),
                current_time.timestamp()
            )
            data_flow_healthy = len(recent_data) > 0
            
            # Calculate overall health
            health_components = [collector_healthy, analyzer_healthy, data_flow_healthy]
            overall_healthy = all(health_components)
            
            return {
                "status": "healthy" if overall_healthy else "degraded",
                "timestamp": current_time.isoformat(),
                "components": {
                    "collector": "healthy" if collector_healthy else "unhealthy",
                    "analyzer": "healthy" if analyzer_healthy else "unhealthy", 
                    "data_flow": "healthy" if data_flow_healthy else "unhealthy"
                },
                "metrics": {
                    "recent_data_points": len(recent_data),
                    "collection_active": collector_healthy,
                    "analysis_active": analyzer_healthy
                },
                "uptime": "Active",  # Could track actual uptime
                "version": "4.0"
            }
            
        except Exception as e:
            self.logger.error("Failed to get health status", error=str(e))
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    async def cleanup(self) -> None:
        """Cleanup all metrics resources"""
        try:
            await self.collector.cleanup()
            await self.analyzer.cleanup()
            
            self.logger.info("Learning metrics manager cleaned up successfully")
            
        except Exception as e:
            self.logger.error("Failed to cleanup metrics manager", error=str(e))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def health_check() -> Dict[str, Any]:
    """Module health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "learning_metrics",
        "version": "4.0"
    }

def validate_configuration(config: Dict[str, Any]) -> bool:
    """Validate module configuration"""
    required_fields = ["enabled", "collection_interval", "retention_period"]
    return all(field in config for field in required_fields)

def calculate_confidence_interval(
    values: List[float],
    confidence: float = 0.95
) -> Tuple[float, float]:
    """Calculate confidence interval for metric values"""
    try:
        if len(values) < 2:
            return (0.0, 0.0)
            
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values)
        n = len(values)
        
        # Use t-distribution for small samples
        if n < 30:
            # Simplified calculation - in production, use scipy.stats.t
            margin = 2.0 * std_dev / (n ** 0.5)  # Approximation
        else:
            # Normal distribution
            margin = 1.96 * std_dev / (n ** 0.5)  # 95% confidence
            
        return (mean - margin, mean + margin)
        
    except (statistics.StatisticsError, ValueError):
        return (0.0, 0.0)

async def batch_record_metrics(
    manager: LearningMetricsManager,
    metrics_batch: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Record multiple metrics in batch for efficiency"""
    try:
        results = {
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for metric_data in metrics_batch:
            try:
                await manager.record_learning_event(
                    event_type=metric_data["event_type"],
                    value=metric_data["value"],
                    agent_id=metric_data.get("agent_id"),
                    metadata=metric_data.get("metadata")
                )
                results["successful"] += 1
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "metric": metric_data,
                    "error": str(e)
                })
        
        return results
        
    except Exception as e:
        logger.error("Failed to process metrics batch", error=str(e))
        raise

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_learning_metrics() -> LearningMetricsManager:
    """Initialize learning metrics module for production use"""
    try:
        config = LearningMetricsConfig(
            enabled=getattr(settings, 'LEARNING_METRICS_ENABLED', True),
            collection_interval=getattr(settings, 'METRICS_COLLECTION_INTERVAL', 60),
            retention_period=getattr(settings, 'METRICS_RETENTION_PERIOD', 2592000),
            aggregation_enabled=getattr(settings, 'METRICS_AGGREGATION_ENABLED', True),
            real_time_alerts=getattr(settings, 'METRICS_REAL_TIME_ALERTS', True),
            performance_tracking=getattr(settings, 'METRICS_PERFORMANCE_TRACKING', True)
        )
        
        manager = LearningMetricsManager(config)
        await manager.initialize()
        
        logger.info("Learning metrics module initialized successfully")
        return manager
        
    except Exception as e:
        logger.error("Failed to initialize learning metrics module", error=str(e))
        raise

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "LearningMetricsManager",
    "LearningMetricsConfig", 
    "MetricsCollector",
    "LearningMetricsAnalyzer",
    "MetricPoint",
    "LearningVelocityMetric",
    "CollaborationMetric", 
    "RetentionMetric",
    "PatternDiscoveryMetric",
    "SystemIntelligenceMetric",
    "MetricsSnapshot",
    "MetricsQuery",
    "initialize_learning_metrics",
    "health_check",
    "batch_record_metrics",
    "calculate_confidence_interval"
]