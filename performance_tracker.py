"""
YMERA Enterprise - Performance Tracking System
Production-Ready Performance Metrics Tracker - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

import asyncio
import logging
import json
import os
import uuid
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from enum import Enum
from collections import defaultdict, deque
from functools import wraps
import statistics

# Third-party imports
import structlog
from fastapi import HTTPException, status
import aioredis
from pydantic import BaseModel, Field, validator

# Local imports
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.performance_tracker")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
CACHE_TTL = 3600
DEFAULT_SAMPLE_SIZE = 1000
PERCENTILES = [50, 90, 95, 99]

settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

class MetricType(str, Enum):
    """Performance metric types"""
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"
    DATABASE_QUERY = "database_query"
    CACHE_HIT_RATE = "cache_hit_rate"
    QUEUE_SIZE = "queue_size"
    CUSTOM = "custom"

class MetricUnit(str, Enum):
    """Metric measurement units"""
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"
    PERCENT = "percent"
    BYTES = "bytes"
    BYTES_PER_SECOND = "bytes_per_second"
    REQUESTS_PER_SECOND = "requests_per_second"
    COUNT = "count"

@dataclass
class PerformanceConfig:
    """Configuration for performance tracking"""
    enabled: bool = True
    sample_size: int = 1000
    retention_hours: int = 24
    aggregation_interval: int = 60  # seconds
    percentiles: List[int] = field(default_factory=lambda: [50, 90, 95, 99])
    enable_real_time: bool = True
    enable_persistence: bool = True
    redis_prefix: str = "ymera:perf"

@dataclass
class MetricSample:
    """Individual metric sample"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MetricStats:
    """Statistical analysis of metric samples"""
    count: int
    min_value: float
    max_value: float
    mean: float
    median: float
    std_dev: float
    percentiles: Dict[int, float]
    rate_per_second: float = 0.0
    trend: str = "stable"  # increasing, decreasing, stable

class PerformanceMetrics(BaseModel):
    """Performance metrics container"""
    metric_name: str
    metric_type: MetricType
    unit: MetricUnit
    timestamp: datetime
    stats: MetricStats
    samples: List[MetricSample] = []
    labels: Dict[str, str] = {}
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            MetricSample: lambda v: {
                "timestamp": v.timestamp.isoformat(),
                "value": v.value,
                "labels": v.labels,
                "metadata": v.metadata
            },
            MetricStats: lambda v: v.__dict__
        }

class PerformanceReport(BaseModel):
    """Comprehensive performance report"""
    report_id: str
    generated_at: datetime
    time_range: Dict[str, datetime]
    metrics: Dict[str, PerformanceMetrics]
    summary: Dict[str, Any]
    alerts: List[Dict[str, Any]] = []
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MetricThreshold(BaseModel):
    """Performance threshold configuration"""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison_operator: str = "greater_than"  # greater_than, less_than, equals
    duration_seconds: int = 300  # How long threshold must be exceeded

# ===============================================================================
# PERFORMANCE TRACKING IMPLEMENTATION
# ===============================================================================

class MetricCollector:
    """Thread-safe metric collector"""
    
    def __init__(self, metric_name: str, metric_type: MetricType, unit: MetricUnit, sample_size: int = 1000):
        self.metric_name = metric_name
        self.metric_type = metric_type
        self.unit = unit
        self.sample_size = sample_size
        self._samples = deque(maxlen=sample_size)
        self._lock = threading.RLock()
        self._labels = {}
        
    def add_sample(self, value: float, labels: Optional[Dict[str, str]] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a metric sample thread-safely"""
        with self._lock:
            sample = MetricSample(
                timestamp=datetime.utcnow(),
                value=value,
                labels=labels or {},
                metadata=metadata or {}
            )
            self._samples.append(sample)
    
    def get_stats(self, time_range: Optional[timedelta] = None) -> MetricStats:
        """Calculate statistics for collected samples"""
        with self._lock:
            samples = list(self._samples)
            
            if time_range:
                cutoff_time = datetime.utcnow() - time_range
                samples = [s for s in samples if s.timestamp >= cutoff_time]
            
            if not samples:
                return MetricStats(
                    count=0,
                    min_value=0.0,
                    max_value=0.0,
                    mean=0.0,
                    median=0.0,
                    std_dev=0.0,
                    percentiles={p: 0.0 for p in PERCENTILES}
                )
            
            values = [s.value for s in samples]
            
            # Calculate percentiles
            percentiles = {}
            for p in PERCENTILES:
                percentiles[p] = statistics.quantiles(values, n=100)[p-1] if len(values) > 1 else values[0]
            
            # Calculate rate per second if applicable
            rate_per_second = 0.0
            if len(samples) > 1:
                time_span = (samples[-1].timestamp - samples[0].timestamp).total_seconds()
                if time_span > 0:
                    rate_per_second = len(samples) / time_span
            
            # Determine trend
            trend = "stable"
            if len(values) >= 10:
                first_half = values[:len(values)//2]
                second_half = values[len(values)//2:]
                first_avg = statistics.mean(first_half)
                second_avg = statistics.mean(second_half)
                
                change_ratio = (second_avg - first_avg) / first_avg if first_avg != 0 else 0
                if change_ratio > 0.1:
                    trend = "increasing"
                elif change_ratio < -0.1:
                    trend = "decreasing"
            
            return MetricStats(
                count=len(values),
                min_value=min(values),
                max_value=max(values),
                mean=statistics.mean(values),
                median=statistics.median(values),
                std_dev=statistics.stdev(values) if len(values) > 1 else 0.0,
                percentiles=percentiles,
                rate_per_second=rate_per_second,
                trend=trend
            )
    
    def get_samples(self, count: Optional[int] = None) -> List[MetricSample]:
        """Get recent samples"""
        with self._lock:
            samples = list(self._samples)
            if count:
                return samples[-count:]
            return samples
    
    def clear_samples(self) -> None:
        """Clear all samples"""
        with self._lock:
            self._samples.clear()

class PerformanceTracker:
    """Production-ready performance tracking system"""
    
    def __init__(self, config: PerformanceConfig):
        self.config = config
        self.logger = logger.bind(component="performance_tracker")
        self._collectors: Dict[str, MetricCollector] = {}
        self._thresholds: Dict[str, MetricThreshold] = {}
        self._redis_client: Optional[aioredis.Redis] = None
        self._aggregation_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._alert_history: List[Dict[str, Any]] = []
    
    async def initialize(self) -> None:
        """Initialize performance tracking system"""
        try:
            if self.config.enable_persistence:
                await self._setup_redis()
            
            if self.config.enable_real_time:
                await self._start_aggregation_tasks()
            
            self._running = True
            self.logger.info("Performance tracker initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize performance tracker", error=str(e))
            raise
    
    async def _setup_redis(self) -> None:
        """Setup Redis connection for persistence"""
        try:
            self._redis_client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis_client.ping()
            self.logger.info("Redis connection established for performance tracking")
        except Exception as e:
            self.logger.error("Failed to setup Redis for performance tracking", error=str(e))
            raise
    
    async def _start_aggregation_tasks(self) -> None:
        """Start background aggregation tasks"""
        if self.config.aggregation_interval > 0:
            task = asyncio.create_task(self._aggregation_loop())
            self._aggregation_tasks["main"] = task
            self.logger.info("Performance aggregation task started", interval=self.config.aggregation_interval)
    
    async def _aggregation_loop(self) -> None:
        """Background aggregation loop"""
        while self._running:
            try:
                await self._aggregate_metrics()
                await self._check_thresholds()
                await asyncio.sleep(self.config.aggregation_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in aggregation loop", error=str(e))
                await asyncio.sleep(5)
    
    async def _aggregate_metrics(self) -> None:
        """Aggregate metrics and store to Redis if enabled"""
        if not self.config.enable_persistence or not self._redis_client:
            return
        
        try:
            for metric_name, collector in self._collectors.items():
                stats = collector.get_stats(timedelta(minutes=5))  # Last 5 minutes
                
                # Store aggregated stats
                key = f"{self.config.redis_prefix}:stats:{metric_name}:{int(time.time())}"
                data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "count": stats.count,
                    "min": stats.min_value,
                    "max": stats.max_value,
                    "mean": stats.mean,
                    "median": stats.median,
                    "std_dev": stats.std_dev,
                    "percentiles": json.dumps(stats.percentiles),
                    "rate_per_second": stats.rate_per_second,
                    "trend": stats.trend
                }
                
                await self._redis_client.hset(key, mapping=data)
                await self._redis_client.expire(key, self.config.retention_hours * 3600)
                
        except Exception as e:
            self.logger.error("Failed to aggregate metrics", error=str(e))
    
    async def _check_thresholds(self) -> None:
        """Check performance thresholds and generate alerts"""
        try:
            for metric_name, threshold in self._thresholds.items():
                if metric_name not in self._collectors:
                    continue
                
                collector = self._collectors[metric_name]
                stats = collector.get_stats(timedelta(seconds=threshold.duration_seconds))
                
                if stats.count == 0:
                    continue
                
                # Check threshold violation
                value_to_check = stats.mean
                threshold_exceeded = False
                
                if threshold.comparison_operator == "greater_than":
                    threshold_exceeded = value_to_check > threshold.critical_threshold
                    severity = "critical"
                    if value_to_check > threshold.warning_threshold:
                        threshold_exceeded = True
                        severity = "warning"
                elif threshold.comparison_operator == "less_than":
                    threshold_exceeded = value_to_check < threshold.critical_threshold
                    severity = "critical"
                    if value_to_check < threshold.warning_threshold:
                        threshold_exceeded = True
                        severity = "warning"
                
                if threshold_exceeded:
                    alert = {
                        "id": str(uuid.uuid4()),
                        "timestamp": datetime.utcnow().isoformat(),
                        "metric_name": metric_name,
                        "severity": severity,
                        "current_value": value_to_check,
                        "threshold_value": threshold.critical_threshold if severity == "critical" else threshold.warning_threshold,
                        "comparison": threshold.comparison_operator,
                        "duration_seconds": threshold.duration_seconds,
                        "sample_count": stats.count
                    }
                    
                    self._alert_history.append(alert)
                    
                    # Keep only recent alerts
                    if len(self._alert_history) > 100:
                        self._alert_history = self._alert_history[-100:]
                    
                    self.logger.warning("Performance threshold exceeded", **alert)
                    
        except Exception as e:
            self.logger.error("Failed to check thresholds", error=str(e))
    
    def get_or_create_collector(self, metric_name: str, metric_type: MetricType, unit: MetricUnit) -> MetricCollector:
        """Get existing collector or create new one"""
        if metric_name not in self._collectors:
            self._collectors[metric_name] = MetricCollector(
                metric_name=metric_name,
                metric_type=metric_type,
                unit=unit,
                sample_size=self.config.sample_size
            )
            self.logger.debug("Created new metric collector", metric=metric_name, type=metric_type.value)
        
        return self._collectors[metric_name]
    
    def record_metric(
        self,
        metric_name: str,
        value: float,
        metric_type: MetricType = MetricType.CUSTOM,
        unit: MetricUnit = MetricUnit.COUNT,
        labels: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a performance metric"""
        try:
            collector = self.get_or_create_collector(metric_name, metric_type, unit)
            collector.add_sample(value, labels, metadata)
        except Exception as e:
            self.logger.error("Failed to record metric", metric=metric_name, error=str(e))
    
    def record_response_time(
        self,
        operation: str,
        response_time: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record response time metric"""
        self.record_metric(
            metric_name=f"response_time.{operation}",
            value=response_time,
            metric_type=MetricType.RESPONSE_TIME,
            unit=MetricUnit.SECONDS,
            labels=labels
        )
    
    def record_throughput(
        self,
        operation: str,
        count: int,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record throughput metric"""
        self.record_metric(
            metric_name=f"throughput.{operation}",
            value=count,
            metric_type=MetricType.THROUGHPUT,
            unit=MetricUnit.REQUESTS_PER_SECOND,
            labels=labels
        )
    
    def record_error_rate(
        self,
        operation: str,
        error_rate: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record error rate metric"""
        self.record_metric(
            metric_name=f"error_rate.{operation}",
            value=error_rate,
            metric_type=MetricType.ERROR_RATE,
            unit=MetricUnit.PERCENT,
            labels=labels
        )
    
    async def get_metrics(
        self,
        metric_names: Optional[List[str]] = None,
        time_range: Optional[timedelta] = None,
        include_samples: bool = False
    ) -> Dict[str, PerformanceMetrics]:
        """Get performance metrics"""
        try:
            metrics = {}
            collectors_to_process = self._collectors
            
            if metric_names:
                collectors_to_process = {k: v for k, v in self._collectors.items() if k in metric_names}
            
            for metric_name, collector in collectors_to_process.items():
                stats = collector.get_stats(time_range)
                samples = collector.get_samples(100) if include_samples else []
                
                metrics[metric_name] = PerformanceMetrics(
                    metric_name=metric_name,
                    metric_type=collector.metric_type,
                    unit=collector.unit,
                    timestamp=datetime.utcnow(),
                    stats=stats,
                    samples=samples,
                    labels=collector._labels
                )
            
            return metrics
            
        except Exception as e:
            self.logger.error("Failed to get metrics", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve performance metrics"
            )
    
    async def generate_report(
        self,
        time_range: Optional[timedelta] = None,
        metric_names: Optional[List[str]] = None
    ) -> PerformanceReport:
        """Generate comprehensive performance report"""
        try:
            if time_range is None:
                time_range = timedelta(hours=1)
            
            start_time = datetime.utcnow() - time_range
            end_time = datetime.utcnow()
            
            metrics = await self.get_metrics(metric_names, time_range, include_samples=False)
            
            # Generate summary statistics
            summary = {
                "total_metrics": len(metrics),
                "time_range_hours": time_range.total_seconds() / 3600,
                "report_generated_at": datetime.utcnow().isoformat(),
                "top_response_times": {},
                "error_rates": {},
                "throughput_stats": {}
            }
            
            # Analyze response times
            response_time_metrics = {k: v for k, v in metrics.items() if v.metric_type == MetricType.RESPONSE_TIME}
            if response_time_metrics:
                summary["top_response_times"] = {
                    k: v.stats.mean for k, v in 
                    sorted(response_time_metrics.items(), key=lambda x: x[1].stats.mean, reverse=True)[:5]
                }
            
            # Analyze error rates
            error_rate_metrics = {k: v for k, v in metrics.items() if v.metric_type == MetricType.ERROR_RATE}
            if error_rate_metrics:
                summary["error_rates"] = {
                    k: v.stats.mean for k, v in error_rate_metrics.items()
                }
            
            # Analyze throughput
            throughput_metrics = {k: v for k, v in metrics.items() if v.metric_type == MetricType.THROUGHPUT}
            if throughput_metrics:
                summary["throughput_stats"] = {
                    "total_requests": sum(v.stats.count for v in throughput_metrics.values()),
                    "average_rps": sum(v.stats.rate_per_second for v in throughput_metrics.values())
                }
            
            # Get recent alerts
            recent_alerts = [
                alert for alert in self._alert_history 
                if datetime.fromisoformat(alert["timestamp"]) >= start_time
            ]
            
            return PerformanceReport(
                report_id=str(uuid.uuid4()),
                generated_at=datetime.utcnow(),
                time_range={"start": start_time, "end": end_time},
                metrics=metrics,
                summary=summary,
                alerts=recent_alerts
            )
            
        except Exception as e:
            self.logger.error("Failed to generate performance report", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate performance report"
            )
    
    def add_threshold(self, threshold: MetricThreshold) -> None:
        """Add performance threshold"""
        self._thresholds[threshold.metric_name] = threshold
        self.logger.info("Performance threshold added", metric=threshold.metric_name)
    
    def remove_threshold(self, metric_name: str) -> None:
        """Remove performance threshold"""
        if metric_name in self._thresholds:
            del self._thresholds[metric_name]
            self.logger.info("Performance threshold removed", metric=metric_name)
    
    async def cleanup(self) -> None:
        """Cleanup performance tracker resources"""
        try:
            self._running = False
            
            # Cancel aggregation tasks
            for task in self._aggregation_tasks.values():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Close Redis connection
            if self._redis_client:
                await self._redis_client.close()
            
            self.logger.info("Performance tracker cleanup completed")
        except Exception as e:
            self.logger.error("Error during performance tracker cleanup", error=str(e))

# ===============================================================================
# PERFORMANCE DECORATORS
# ===============================================================================

def track_performance(
    metric_name: Optional[str] = None,
    labels: Optional[Dict[str, str]] = None,
    track_errors: bool = True
):
    """Decorator for tracking function performance"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            operation_name = metric_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                
                # Record successful execution
                response_time = time.time() - start_time
                if hasattr(func, '_performance_tracker'):
                    func._performance_tracker.record_response_time(
                        operation_name, response_time, labels
                    )
                
                return result
                
            except Exception as e:
                # Record error
                response_time = time.time() - start_time
                
                if hasattr(func, '_performance_tracker') and track_errors:
                    error_labels = (labels or {}).copy()
                    error_labels.update({"error_type": type(e).__name__})
                    
                    func._performance_tracker.record_response_time(
                        f"{operation_name}.error", response_time, error_labels
                    )
                    func._performance_tracker.record_error_rate(
                        operation_name, 100.0, error_labels
                    )
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            operation_name = metric_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Record successful execution
                response_time = time.time() - start_time
                if hasattr(func, '_performance_tracker'):
                    func._performance_tracker.record_response_time(
                        operation_name, response_time, labels
                    )
                
                return result
                
            except Exception as e:
                # Record error
                response_time = time.time() - start_time
                
                if hasattr(func, '_performance_tracker') and track_errors:
                    error_labels = (labels or {}).copy()
                    error_labels.update({"error_type": type(e).__name__})
                    
                    func._performance_tracker.record_response_time(
                        f"{operation_name}.error", response_time, error_labels
                    )
                    func._performance_tracker.record_error_rate(
                        operation_name, 100.0, error_labels
                    )
                
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# ===============================================================================
# CONTEXT MANAGERS
# ===============================================================================

@asynccontextmanager
async def track_operation(
    tracker: PerformanceTracker,
    operation_name: str,
    labels: Optional[Dict[str, str]] = None
):
    """Context manager for tracking operation performance"""
    start_time = time.time()
    
    try:
        yield
        
        # Record successful operation
        response_time = time.time() - start_time
        tracker.record_response_time(operation_name, response_time, labels)
        
    except Exception as e:
        # Record failed operation
        response_time = time.time() - start_time
        
        error_labels = (labels or {}).copy()
        error_labels.update({"error_type": type(e).__name__})
        
        tracker.record_response_time(f"{operation_name}.error", response_time, error_labels)
        tracker.record_error_rate(operation_name, 100.0, error_labels)
        
        raise

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def create_default_config() -> PerformanceConfig:
    """Create default performance tracking configuration"""
    return PerformanceConfig(
        enabled=True,
        sample_size=1000,
        retention_hours=24,
        aggregation_interval=60,
        percentiles=[50, 90, 95, 99],
        enable_real_time=True,
        enable_persistence=True,
        redis_prefix="ymera:perf"
    )

async def get_system_performance() -> Dict[str, Any]:
    """Get basic system performance metrics"""
    import psutil
    
    return {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0],
        "timestamp": datetime.utcnow().isoformat()
    }

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

# Global performance tracker instance
_global_tracker: Optional[PerformanceTracker] = None

async def initialize_performance_tracker(config: Optional[PerformanceConfig] = None) -> PerformanceTracker:
    """Initialize performance tracker for production use"""
    global _global_tracker
    
    if config is None:
        config = create_default_config()
    
    _global_tracker = PerformanceTracker(config)
    await _global_tracker.initialize()
    
    return _global_tracker

def get_global_tracker() -> Optional[PerformanceTracker]:
    """Get global performance tracker instance"""
    return _global_tracker

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "PerformanceTracker",
    "PerformanceMetrics",
    "PerformanceConfig",
    "PerformanceReport",
    "MetricType",
    "MetricUnit",
    "MetricCollector",
    "MetricSample",
    "MetricStats",
    "MetricThreshold",
    "track_performance",
    "track_operation",
    "initialize_performance_tracker",
    "get_global_tracker",
    "create_default_config",
    "get_system_performance"
]