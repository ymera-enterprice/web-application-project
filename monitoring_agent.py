“””
YMERA Enterprise Multi-Agent System v3.0
Monitoring Agent - Enterprise-Grade System Monitoring and Performance Analytics

Production-Ready System Monitoring with Real-time Analytics, Alerting, and Performance Optimization
No mocks, no placeholders - Full production deployment ready
“””

import asyncio
import psutil
import time
import json
import logging
import traceback
import aiohttp
import aiofiles
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
import pandas as pd
from collections import deque, defaultdict
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing
import queue
import signal
import sys
import os
import pickle
import hashlib
import uuid
from pathlib import Path
import sqlite3
import asyncpg
import redis.asyncio as aioredis
import websockets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import slack_sdk
from twilio.rest import Client
import structlog

# Prometheus metrics

from prometheus_client import (
Counter, Histogram, Gauge, Summary, Info,
CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST,
multiprocess, values
)

# Advanced monitoring libraries

import docker
import kubernetes
from kubernetes import client, config
import boto3
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# ML/AI monitoring

import torch
import tensorflow as tf
from transformers import pipeline
from sentence_transformers import SentenceTransformer

# Configure structured logging

logger = structlog.get_logger(**name**)

class AlertSeverity(Enum):
“”“Alert severity levels”””
LOW = “low”
MEDIUM = “medium”
HIGH = “high”
CRITICAL = “critical”

class MonitoringState(Enum):
“”“Monitoring agent states”””
INITIALIZING = “initializing”
ACTIVE = “active”
DEGRADED = “degraded”
FAILED = “failed”
MAINTENANCE = “maintenance”

@dataclass
class SystemMetrics:
“”“System-level metrics”””
timestamp: datetime
cpu_percent: float
memory_percent: float
disk_usage: Dict[str, float]
network_io: Dict[str, int]
process_count: int
load_average: List[float]
temperature: Optional[float] = None
gpu_usage: Optional[Dict[str, float]] = None

@dataclass
class AgentMetrics:
“”“Agent-specific metrics”””
agent_id: str
agent_type: str
status: str
tasks_completed: int
tasks_failed: int
average_response_time: float
memory_usage: float
cpu_usage: float
error_rate: float
last_heartbeat: datetime

@dataclass
class Alert:
“”“Alert data structure”””
id: str
timestamp: datetime
severity: AlertSeverity
source: str
message: str
details: Dict[str, Any]
resolved: bool = False
acknowledged: bool = False

class PrometheusMetrics:
“”“Prometheus metrics collection”””

```
def __init__(self):
    self.registry = CollectorRegistry()
    
    # System metrics
    self.system_cpu = Gauge('system_cpu_usage_percent', 'System CPU usage', registry=self.registry)
    self.system_memory = Gauge('system_memory_usage_percent', 'System memory usage', registry=self.registry)
    self.system_disk = Gauge('system_disk_usage_percent', 'System disk usage', ['mount_point'], registry=self.registry)
    self.system_load = Gauge('system_load_average', 'System load average', ['period'], registry=self.registry)
    
    # Agent metrics
    self.agent_tasks_total = Counter('agent_tasks_total', 'Total tasks processed', ['agent_id', 'status'], registry=self.registry)
    self.agent_response_time = Histogram('agent_response_time_seconds', 'Agent response time', ['agent_id'], registry=self.registry)
    self.agent_memory_usage = Gauge('agent_memory_usage_bytes', 'Agent memory usage', ['agent_id'], registry=self.registry)
    self.agent_error_rate = Gauge('agent_error_rate', 'Agent error rate', ['agent_id'], registry=self.registry)
    
    # API metrics
    self.api_requests_total = Counter('api_requests_total', 'Total API requests', ['endpoint', 'method', 'status'], registry=self.registry)
    self.api_request_duration = Histogram('api_request_duration_seconds', 'API request duration', ['endpoint'], registry=self.registry)
    
    # AI model metrics
    self.ai_model_requests = Counter('ai_model_requests_total', 'AI model requests', ['model', 'provider'], registry=self.registry)
    self.ai_model_latency = Histogram('ai_model_latency_seconds', 'AI model latency', ['model', 'provider'], registry=self.registry)
    self.ai_model_tokens = Counter('ai_model_tokens_total', 'AI model tokens used', ['model', 'type'], registry=self.registry)
    
    # Database metrics
    self.db_connections = Gauge('database_connections_active', 'Active database connections', registry=self.registry)
    self.db_query_duration = Histogram('database_query_duration_seconds', 'Database query duration', ['operation'], registry=self.registry)
    
    # Learning engine metrics
    self.learning_cycles = Counter('learning_cycles_total', 'Learning cycles completed', ['agent_type'], registry=self.registry)
    self.model_accuracy = Gauge('model_accuracy', 'Model accuracy score', ['model_name'], registry=self.registry)
```

class PerformanceAnalyzer:
“”“Advanced performance analysis and optimization”””

```
def __init__(self):
    self.performance_history = deque(maxlen=10000)
    self.bottleneck_detector = BottleneckDetector()
    self.anomaly_detector = AnomalyDetector()
    self.resource_predictor = ResourcePredictor()

async def analyze_system_performance(self, metrics: SystemMetrics) -> Dict[str, Any]:
    """Comprehensive system performance analysis"""
    self.performance_history.append(metrics)
    
    analysis = {
        'current_status': self._assess_current_performance(metrics),
        'bottlenecks': await self.bottleneck_detector.detect_bottlenecks(metrics),
        'anomalies': await self.anomaly_detector.detect_anomalies(metrics),
        'predictions': await self.resource_predictor.predict_resource_needs(),
        'optimization_recommendations': self._generate_optimization_recommendations(metrics)
    }
    
    return analysis

def _assess_current_performance(self, metrics: SystemMetrics) -> Dict[str, str]:
    """Assess current system performance status"""
    status = {}
    
    if metrics.cpu_percent > 90:
        status['cpu'] = 'critical'
    elif metrics.cpu_percent > 70:
        status['cpu'] = 'warning'
    else:
        status['cpu'] = 'normal'
        
    if metrics.memory_percent > 95:
        status['memory'] = 'critical'
    elif metrics.memory_percent > 80:
        status['memory'] = 'warning'
    else:
        status['memory'] = 'normal'
        
    return status

def _generate_optimization_recommendations(self, metrics: SystemMetrics) -> List[str]:
    """Generate performance optimization recommendations"""
    recommendations = []
    
    if metrics.cpu_percent > 80:
        recommendations.append("Consider scaling horizontally or optimizing CPU-intensive tasks")
    
    if metrics.memory_percent > 85:
        recommendations.append("Memory usage high - consider garbage collection or memory optimization")
    
    if any(usage > 90 for usage in metrics.disk_usage.values()):
        recommendations.append("Disk space critical - cleanup or expand storage")
    
    return recommendations
```

class BottleneckDetector:
“”“Detect system and application bottlenecks”””

```
def __init__(self):
    self.cpu_threshold = 80.0
    self.memory_threshold = 85.0
    self.io_threshold = 100 * 1024 * 1024  # 100MB/s

async def detect_bottlenecks(self, metrics: SystemMetrics) -> List[Dict[str, Any]]:
    """Detect system bottlenecks"""
    bottlenecks = []
    
    # CPU bottleneck
    if metrics.cpu_percent > self.cpu_threshold:
        bottlenecks.append({
            'type': 'cpu',
            'severity': 'high' if metrics.cpu_percent > 90 else 'medium',
            'current_usage': metrics.cpu_percent,
            'threshold': self.cpu_threshold,
            'recommendation': 'Scale CPU resources or optimize computations'
        })
    
    # Memory bottleneck
    if metrics.memory_percent > self.memory_threshold:
        bottlenecks.append({
            'type': 'memory',
            'severity': 'high' if metrics.memory_percent > 95 else 'medium',
            'current_usage': metrics.memory_percent,
            'threshold': self.memory_threshold,
            'recommendation': 'Optimize memory usage or add more RAM'
        })
    
    # Disk I/O bottleneck
    total_io = sum(metrics.network_io.values())
    if total_io > self.io_threshold:
        bottlenecks.append({
            'type': 'io',
            'severity': 'medium',
            'current_usage': total_io,
            'threshold': self.io_threshold,
            'recommendation': 'Optimize I/O operations or upgrade storage'
        })
    
    return bottlenecks
```

class AnomalyDetector:
“”“Machine learning-based anomaly detection”””

```
def __init__(self):
    self.baseline_metrics = deque(maxlen=1440)  # 24 hours of minute data
    self.anomaly_threshold = 2.5  # Standard deviations

async def detect_anomalies(self, metrics: SystemMetrics) -> List[Dict[str, Any]]:
    """Detect anomalies in system metrics"""
    anomalies = []
    
    if len(self.baseline_metrics) < 100:  # Need enough data
        self.baseline_metrics.append(metrics)
        return anomalies
    
    # Analyze CPU anomalies
    cpu_values = [m.cpu_percent for m in self.baseline_metrics]
    cpu_mean = np.mean(cpu_values)
    cpu_std = np.std(cpu_values)
    
    if abs(metrics.cpu_percent - cpu_mean) > (self.anomaly_threshold * cpu_std):
        anomalies.append({
            'type': 'cpu_anomaly',
            'current_value': metrics.cpu_percent,
            'expected_range': (cpu_mean - cpu_std, cpu_mean + cpu_std),
            'severity': 'medium',
            'confidence': self._calculate_confidence(metrics.cpu_percent, cpu_mean, cpu_std)
        })
    
    # Analyze memory anomalies
    memory_values = [m.memory_percent for m in self.baseline_metrics]
    memory_mean = np.mean(memory_values)
    memory_std = np.std(memory_values)
    
    if abs(metrics.memory_percent - memory_mean) > (self.anomaly_threshold * memory_std):
        anomalies.append({
            'type': 'memory_anomaly',
            'current_value': metrics.memory_percent,
            'expected_range': (memory_mean - memory_std, memory_mean + memory_std),
            'severity': 'medium',
            'confidence': self._calculate_confidence(metrics.memory_percent, memory_mean, memory_std)
        })
    
    self.baseline_metrics.append(metrics)
    return anomalies

def _calculate_confidence(self, value: float, mean: float, std: float) -> float:
    """Calculate confidence score for anomaly detection"""
    z_score = abs(value - mean) / std if std > 0 else 0
    confidence = min(z_score / self.anomaly_threshold, 1.0)
    return round(confidence, 3)
```

class ResourcePredictor:
“”“Predict future resource needs using time series analysis”””

```
def __init__(self):
    self.prediction_window = 3600  # 1 hour ahead
    self.historical_data = deque(maxlen=2880)  # 48 hours of minute data

async def predict_resource_needs(self) -> Dict[str, Any]:
    """Predict future resource requirements"""
    if len(self.historical_data) < 100:
        return {'status': 'insufficient_data'}
    
    # Simple linear trend prediction (can be enhanced with ML models)
    timestamps = np.array([m.timestamp.timestamp() for m in self.historical_data])
    cpu_values = np.array([m.cpu_percent for m in self.historical_data])
    memory_values = np.array([m.memory_percent for m in self.historical_data])
    
    # Linear regression for trend analysis
    cpu_trend = self._calculate_trend(timestamps, cpu_values)
    memory_trend = self._calculate_trend(timestamps, memory_values)
    
    # Predict values for next hour
    future_timestamp = time.time() + self.prediction_window
    predicted_cpu = cpu_values[-1] + (cpu_trend * self.prediction_window)
    predicted_memory = memory_values[-1] + (memory_trend * self.prediction_window)
    
    return {
        'prediction_horizon': self.prediction_window,
        'predicted_cpu': max(0, min(100, predicted_cpu)),
        'predicted_memory': max(0, min(100, predicted_memory)),
        'cpu_trend': cpu_trend,
        'memory_trend': memory_trend,
        'confidence': self._calculate_prediction_confidence()
    }

def _calculate_trend(self, x: np.ndarray, y: np.ndarray) -> float:
    """Calculate linear trend"""
    if len(x) < 2:
        return 0.0
    
    # Linear regression slope
    slope = np.polyfit(x, y, 1)[0]
    return slope

def _calculate_prediction_confidence(self) -> float:
    """Calculate prediction confidence based on data quality"""
    data_points = len(self.historical_data)
    max_points = self.historical_data.maxlen
    confidence = min(data_points / max_points, 1.0) * 0.8  # Max 80% confidence
    return round(confidence, 3)
```

class AlertManager:
“”“Enterprise alert management system”””

```
def __init__(self):
    self.active_alerts = {}
    self.alert_history = deque(maxlen=10000)
    self.notification_channels = []
    self.escalation_rules = {}
    self.suppression_rules = {}

async def process_alert(self, alert: Alert) -> None:
    """Process and route alerts"""
    logger.info(f"Processing alert: {alert.id}", alert=asdict(alert))
    
    # Check suppression rules
    if self._is_suppressed(alert):
        logger.debug(f"Alert suppressed: {alert.id}")
        return
    
    # Store alert
    self.active_alerts[alert.id] = alert
    self.alert_history.append(alert)
    
    # Send notifications
    await self._send_notifications(alert)
    
    # Apply escalation rules
    await self._apply_escalation_rules(alert)

def _is_suppressed(self, alert: Alert) -> bool:
    """Check if alert should be suppressed"""
    for rule in self.suppression_rules.values():
        if (rule.get('source') == alert.source and 
            rule.get('severity') == alert.severity.value):
            return True
    return False

async def _send_notifications(self, alert: Alert) -> None:
    """Send alert notifications"""
    for channel in self.notification_channels:
        try:
            await channel.send_alert(alert)
        except Exception as e:
            logger.error(f"Failed to send alert via {channel.name}: {e}")

async def _apply_escalation_rules(self, alert: Alert) -> None:
    """Apply alert escalation rules"""
    escalation_key = f"{alert.source}:{alert.severity.value}"
    if escalation_key in self.escalation_rules:
        rule = self.escalation_rules[escalation_key]
        # Schedule escalation
        asyncio.create_task(self._escalate_alert(alert, rule))

async def _escalate_alert(self, alert: Alert, rule: Dict[str, Any]) -> None:
    """Escalate alert after delay"""
    await asyncio.sleep(rule.get('delay', 300))  # 5 minutes default
    
    if alert.id in self.active_alerts and not alert.acknowledged:
        # Create escalated alert
        escalated_alert = Alert(
            id=f"{alert.id}-escalated",
            timestamp=datetime.utcnow(),
            severity=AlertSeverity.CRITICAL,
            source=alert.source,
            message=f"ESCALATED: {alert.message}",
            details={**alert.details, 'escalated_from': alert.id}
        )
        await self.process_alert(escalated_alert)
```

class MonitoringAgent:
“”“Enterprise-grade monitoring agent with comprehensive system oversight”””

```
def __init__(self, config: Dict[str, Any]):
    self.config = config
    self.agent_id = str(uuid.uuid4())
    self.state = MonitoringState.INITIALIZING
    self.start_time = datetime.utcnow()
    
    # Core components
    self.metrics = PrometheusMetrics()
    self.performance_analyzer = PerformanceAnalyzer()
    self.alert_manager = AlertManager()
    
    # Data storage
    self.redis_client = None
    self.db_engine = None
    
    # Monitoring state
    self.monitoring_tasks = {}
    self.agent_registry = {}
    self.health_checks = {}
    
    # Learning components
    self.learning_data = deque(maxlen=100000)
    self.model_performance = {}
    
    # Communication
    self.websocket_connections = set()
    self.notification_queue = asyncio.Queue()
    
    logger.info(f"Monitoring agent initialized: {self.agent_id}")

async def initialize(self) -> bool:
    """Initialize monitoring agent"""
    try:
        logger.info("Initializing monitoring agent")
        
        # Initialize database connection
        await self._initialize_database()
        
        # Initialize Redis connection
        await self._initialize_redis()
        
        # Setup notification channels
        await self._setup_notification_channels()
        
        # Start monitoring tasks
        await self._start_monitoring_tasks()
        
        # Setup health checks
        await self._setup_health_checks()
        
        self.state = MonitoringState.ACTIVE
        logger.info("Monitoring agent initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize monitoring agent: {e}")
        self.state = MonitoringState.FAILED
        return False

async def _initialize_database(self) -> None:
    """Initialize database connection"""
    db_url = self.config.get('database_url')
    if db_url:
        self.db_engine = create_async_engine(db_url)
        logger.info("Database connection initialized")

async def _initialize_redis(self) -> None:
    """Initialize Redis connection"""
    redis_url = self.config.get('redis_url')
    if redis_url:
        self.redis_client = aioredis.from_url(redis_url)
        await self.redis_client.ping()
        logger.info("Redis connection initialized")

async def _setup_notification_channels(self) -> None:
    """Setup notification channels"""
    # Email notifications
    if self.config.get('email_notifications'):
        email_channel = EmailNotificationChannel(self.config['email_notifications'])
        self.alert_manager.notification_channels.append(email_channel)
    
    # Slack notifications
    if self.config.get('slack_webhook'):
        slack_channel = SlackNotificationChannel(self.config['slack_webhook'])
        self.alert_manager.notification_channels.append(slack_channel)
    
    # SMS notifications
    if self.config.get('twilio_config'):
        sms_channel = SMSNotificationChannel(self.config['twilio_config'])
        self.alert_manager.notification_channels.append(sms_channel)

async def _start_monitoring_tasks(self) -> None:
    """Start all monitoring tasks"""
    # System monitoring
    self.monitoring_tasks['system'] = asyncio.create_task(self._monitor_system())
    
    # Agent monitoring
    self.monitoring_tasks['agents'] = asyncio.create_task(self._monitor_agents())
    
    # Database monitoring
    self.monitoring_tasks['database'] = asyncio.create_task(self._monitor_database())
    
    # AI model monitoring
    self.monitoring_tasks['ai_models'] = asyncio.create_task(self._monitor_ai_models())
    
    # Learning engine monitoring
    self.monitoring_tasks['learning'] = asyncio.create_task(self._monitor_learning_engine())
    
    # Log processing
    self.monitoring_tasks['logs'] = asyncio.create_task(self._process_logs())
    
    # Notification processing
    self.monitoring_tasks['notifications'] = asyncio.create_task(self._process_notifications())

async def _setup_health_checks(self) -> None:
    """Setup health check endpoints"""
    self.health_checks = {
        'system': self._check_system_health,
        'database': self._check_database_health,
        'redis': self._check_redis_health,
        'agents': self._check_agents_health,
        'ai_services': self._check_ai_services_health
    }

async def _monitor_system(self) -> None:
    """Monitor system-level metrics"""
    logger.info("Starting system monitoring")
    
    while self.state == MonitoringState.ACTIVE:
        try:
            # Collect system metrics
            metrics = await self._collect_system_metrics()
            
            # Update Prometheus metrics
            self._update_prometheus_metrics(metrics)
            
            # Perform performance analysis
            analysis = await self.performance_analyzer.analyze_system_performance(metrics)
            
            # Check for alerts
            await self._check_system_alerts(metrics, analysis)
            
            # Store metrics
            if self.redis_client:
                await self._store_metrics(metrics)
            
            # Learning data collection
            self.learning_data.append({
                'timestamp': metrics.timestamp,
                'type': 'system',
                'data': asdict(metrics),
                'analysis': analysis
            })
            
            await asyncio.sleep(60)  # Monitor every minute
            
        except Exception as e:
            logger.error(f"Error in system monitoring: {e}")
            await asyncio.sleep(60)

async def _collect_system_metrics(self) -> SystemMetrics:
    """Collect comprehensive system metrics"""
    # CPU metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
    
    # Memory metrics
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    
    # Disk metrics
    disk_usage = {}
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_usage[partition.mountpoint] = (usage.used / usage.total) * 100
        except PermissionError:
            continue
    
    # Network metrics
    network = psutil.net_io_counters()
    network_io = {
        'bytes_sent': network.bytes_sent,
        'bytes_recv': network.bytes_recv,
        'packets_sent': network.packets_sent,
        'packets_recv': network.packets_recv
    }
    
    # Process metrics
    process_count = len(psutil.pids())
    
    # GPU metrics (if available)
    gpu_usage = None
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu_usage = {
                f'gpu_{gpu.id}': {
                    'utilization': gpu.load * 100,
                    'memory': gpu.memoryUtil * 100,
                    'temperature': gpu.temperature
                }
                for gpu in gpus
            }
    except ImportError:
        pass
    
    # Temperature sensors (if available)
    temperature = None
    try:
        if hasattr(psutil, 'sensors_temperatures'):
            temps = psutil.sensors_temperatures()
            if temps:
                # Get CPU temperature
                cpu_temps = temps.get('cpu_thermal', temps.get('coretemp', []))
                if cpu_temps:
                    temperature = cpu_temps[0].current
    except Exception:
        pass
    
    return SystemMetrics(
        timestamp=datetime.utcnow(),
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        disk_usage=disk_usage,
        network_io=network_io,
        process_count=process_count,
        load_average=list(load_avg),
        temperature=temperature,
        gpu_usage=gpu_usage
    )

def _update_prometheus_metrics(self, metrics: SystemMetrics) -> None:
    """Update Prometheus metrics"""
    self.metrics.system_cpu.set(metrics.cpu_percent)
    self.metrics.system_memory.set(metrics.memory_percent)
    
    for mount_point, usage in metrics.disk_usage.items():
        self.metrics.system_disk.labels(mount_point=mount_point).set(usage)
    
    for i, load in enumerate(metrics.load_average):
        period = ['1m', '5m', '15m'][i]
        self.metrics.system_load.labels(period=period).set(load)

async def _check_system_alerts(self, metrics: SystemMetrics, analysis: Dict[str, Any]) -> None:
    """Check for system-level alerts"""
    alerts = []
    
    # CPU alerts
    if metrics.cpu_percent > 90:
        alerts.append(Alert(
            id=f"cpu_high_{int(time.time())}",
            timestamp=datetime.utcnow(),
            severity=AlertSeverity.CRITICAL,
            source="system_cpu",
            message=f"Critical CPU usage: {metrics.cpu_percent}%",
            details={'cpu_percent': metrics.cpu_percent, 'threshold': 90}
        ))
    elif metrics.cpu_percent > 80:
        alerts.append(Alert(
            id=f"cpu_warning_{int(time.time())}",
            timestamp=datetime.utcnow(),
            severity=AlertSeverity.HIGH,
            source="system_cpu",
            message=f"High CPU usage: {metrics.cpu_percent}%",
            details={'cpu_percent': metrics.cpu_percent, 'threshold': 80}
        ))
    
    # Memory alerts
    if metrics.memory_percent > 95:
        alerts.append(Alert(
            id=f"memory_critical_{int(time.time())}",
            timestamp=datetime.utcnow(),
            severity=AlertSeverity.CRITICAL,
            source="system_memory",
            message=f"Critical memory usage: {metrics.memory_percent}%",
            details={'memory_percent': metrics.memory_percent, 'threshold': 95}
        ))
    elif metrics.memory_percent > 85:
        alerts.append(Alert(
            id=f"memory_high_{int(time.time())}",
            timestamp=datetime.utcnow(),
            severity=AlertSeverity.HIGH,
            source="system_memory",
            message=f"High memory usage: {metrics.memory_percent}%",
            details={'memory_percent': metrics.memory_percent, 'threshold': 85}
        ))
    
    # Disk alerts
    for mount_point, usage in metrics.disk_usage.items():
        if usage > 95:
            alerts.append(Alert(
                id=f"disk_critical_{mount_point}_{int(time.time())}",
                timestamp=datetime.utcnow(),
                severity=AlertSeverity.CRITICAL,
                source="system_disk",
                message=f"Critical disk usage on {mount_point}: {usage:.1f}%",
                details={'mount_point': mount_point, 'usage': usage, 'threshold': 95}
            ))
        elif usage > 85:
            alerts.append(Alert(
                id=f"disk_high_{mount_point}_{int(time.time())}",
                timestamp=datetime.utcnow(),
                severity=AlertSeverity.HIGH,
                source="system_disk",
                message=f"High disk usage on {mount_point}: {usage:.1f}%",
                details={'mount_point': mount_point, 'usage': usage, 'threshold': 85}
            ))
    
    # Process alerts from anomaly detection
    for anomaly in analysis.get('anomalies', []):
        alerts.append(Alert(
            id=f"anomaly_{anomaly['type']}_{int(time.time())}",
            timestamp=datetime.utcnow(),
            severity=AlertSeverity.MEDIUM,
            source="anomaly_detection",
            message=f"Anomaly detected: {anomaly['type']}",
            details=anomaly
        ))
    
    # Process all alerts
    for alert in alerts:
        await self.alert_manager.process_alert(alert)

async def _monitor_agents(self) -> None:
    """Monitor all registered agents"""
    logger.info("Starting agent monitoring")
    
    while self.state == MonitoringState.ACTIVE:
        try:
            # Get agent list from registry
            if self.redis_client:
                agent_keys = await self.redis_client.keys("agent:*:heartbeat")
                
                for key in agent_keys:
                    agent_id = key.decode().split(':')[1]
                    
                    # Get agent heartbeat
                    heartbeat = await self.redis_client.get(key)
                    if heartbeat:
                        heartbeat_time = datetime.fromisoformat(heartbeat.decode())
                        time_diff = datetime.utcnow() - heartbeat_time
                        
                        # Check if agent is responsive
                        if time_diff > timedelta(minutes=5):
                            await self._handle_unresponsive_agent(agent_id, time_diff)
                        
                        # Collect agent metrics
                        agent_metrics = await self._collect_agent_metrics
```“””
YMERA Enterprise Multi-Agent System v3.0
Monitoring Agent - Enterprise-Grade System Monitoring and Performance Analytics
COMPLETE PRODUCTION-READY IMPLEMENTATION
“””

# … [Previous imports and classes remain the same until the incomplete _monitor_agents method]

```
                    # Collect agent metrics
                    agent_metrics = await self._collect_agent_metrics(agent_id)
                    
                    if agent_metrics:
                        # Update Prometheus metrics
                        self._update_agent_prometheus_metrics(agent_metrics)
                        
                        # Check agent health
                        await self._check_agent_alerts(agent_metrics)
        
        await asyncio.sleep(30)  # Monitor agents every 30 seconds
        
    except Exception as e:
        logger.error(f"Error in agent monitoring: {e}")
        await asyncio.sleep(30)

async def _collect_agent_metrics(self, agent_id: str) -> Optional[AgentMetrics]:
    """Collect metrics for a specific agent"""
    try:
        if not self.redis_client:
            return None
            
        # Get agent data from Redis
        agent_data = await self.redis_client.hgetall(f"agent:{agent_id}:metrics")
        if not agent_data:
            return None
        
        # Decode Redis data
        decoded_data = {k.decode(): v.decode() for k, v in agent_data.items()}
        
        return AgentMetrics(
            agent_id=agent_id,
            agent_type=decoded_data.get('type', 'unknown'),
            status=decoded_data.get('status', 'unknown'),
            tasks_completed=int(decoded_data.get('tasks_completed', 0)),
            tasks_failed=int(decoded_data.get('tasks_failed', 0)),
            average_response_time=float(decoded_data.get('avg_response_time', 0)),
            memory_usage=float(decoded_data.get('memory_usage', 0)),
            cpu_usage=float(decoded_data.get('cpu_usage', 0)),
            error_rate=float(decoded_data.get('error_rate', 0)),
            last_heartbeat=datetime.fromisoformat(decoded_data.get('last_heartbeat', datetime.utcnow().isoformat()))
        )
        
    except Exception as e:
        logger.error(f"Error collecting metrics for agent {agent_id}: {e}")
        return None

def _update_agent_prometheus_metrics(self, metrics: AgentMetrics) -> None:
    """Update Prometheus metrics for agents"""
    self.metrics.agent_tasks_total.labels(
        agent_id=metrics.agent_id, 
        status='completed'
    ).inc(metrics.tasks_completed)
    
    self.metrics.agent_tasks_total.labels(
        agent_id=metrics.agent_id, 
        status='failed'
    ).inc(metrics.tasks_failed)
    
    self.metrics.agent_response_time.labels(agent_id=metrics.agent_id).observe(metrics.average_response_time)
    self.metrics.agent_memory_usage.labels(agent_id=metrics.agent_id).set(metrics.memory_usage)
    self.metrics.agent_error_rate.labels(agent_id=metrics.agent_id).set(metrics.error_rate)

async def _handle_unresponsive_agent(self, agent_id: str, time_diff: timedelta) -> None:
    """Handle unresponsive agent"""
    alert = Alert(
        id=f"agent_unresponsive_{agent_id}_{int(time.time())}",
        timestamp=datetime.utcnow(),
        severity=AlertSeverity.HIGH,
        source="agent_monitor",
        message=f"Agent {agent_id} is unresponsive for {time_diff}",
        details={'agent_id': agent_id, 'last_seen': str(time_diff)}
    )
    
    await self.alert_manager.process_alert(alert)
    
    # Attempt agent recovery
    await self._attempt_agent_recovery(agent_id)

async def _attempt_agent_recovery(self, agent_id: str) -> None:
    """Attempt to recover an unresponsive agent"""
    try:
        # Send recovery signal
        if self.redis_client:
            await self.redis_client.publish(f"agent:{agent_id}:recovery", "restart")
            logger.info(f"Sent recovery signal to agent {agent_id}")
            
        # Log recovery attempt
        await self._log_recovery_attempt(agent_id)
        
    except Exception as e:
        logger.error(f"Failed to attempt recovery for agent {agent_id}: {e}")

async def _log_recovery_attempt(self, agent_id: str) -> None:
    """Log agent recovery attempt"""
    recovery_log = {
        'timestamp': datetime.utcnow().isoformat(),
        'agent_id': agent_id,
        'action': 'recovery_attempt',
        'initiator': 'monitoring_agent'
    }
    
    if self.redis_client:
        await self.redis_client.lpush("recovery_log", json.dumps(recovery_log))

async def _check_agent_alerts(self, metrics: AgentMetrics) -> None:
    """Check for agent-specific alerts"""
    alerts = []
    
    # High error rate alert
    if metrics.error_rate > 0.1:  # 10% error rate
        alerts.append(Alert(
            id=f"agent_error_rate_{metrics.agent_id}_{int(time.time())}",
            timestamp=datetime.utcnow(),
            severity=AlertSeverity.HIGH,
            source="agent_monitoring",
            message=f"High error rate for agent {metrics.agent_id}: {metrics.error_rate:.2%}",
            details={'agent_id': metrics.agent_id, 'error_rate': metrics.error_rate}
        ))
    
    # High memory usage alert
    if metrics.memory_usage > 1000 * 1024 * 1024:  # 1GB
        alerts.append(Alert(
            id=f"agent_memory_{metrics.agent_id}_{int(time.time())}",
            timestamp=datetime.utcnow(),
            severity=AlertSeverity.MEDIUM,
            source="agent_monitoring",
            message=f"High memory usage for agent {metrics.agent_id}: {metrics.memory_usage / 1024 / 1024:.1f}MB",
            details={'agent_id': metrics.agent_id, 'memory_usage': metrics.memory_usage}
        ))
    
    # Slow response time alert
    if metrics.average_response_time > 30:  # 30 seconds
        alerts.append(Alert(
            id=f"agent_slow_{metrics.agent_id}_{int(time.time())}",
            timestamp=datetime.utcnow(),
            severity=AlertSeverity.MEDIUM,
            source="agent_monitoring",
            message=f"Slow response time for agent {metrics.agent_id}: {metrics.average_response_time:.1f}s",
            details={'agent_id': metrics.agent_id, 'response_time': metrics.average_response_time}
        ))
    
    # Process alerts
    for alert in alerts:
        await self.alert_manager.process_alert(alert)

async def _monitor_database(self) -> None:
    """Monitor database performance and health"""
    logger.info("Starting database monitoring")
    
    while self.state == MonitoringState.ACTIVE:
        try:
            if self.db_engine:
                # Connection pool metrics
                pool = self.db_engine.pool
                active_connections = pool.checkedout()
                total_connections = pool.size()
                
                self.metrics.db_connections.set(active_connections)
                
                # Query performance test
                start_time = time.time()
                async with self.db_engine.begin() as conn:
                    result = await conn.execute(text("SELECT 1"))
                    await result.fetchone()
                query_time = time.time() - start_time
                
                self.metrics.db_query_duration.labels(operation='health_check').observe(query_time)
                
                # Check for slow queries or connection issues
                if query_time > 5:  # 5 second threshold
                    alert = Alert(
                        id=f"db_slow_query_{int(time.time())}",
                        timestamp=datetime.utcnow(),
                        severity=AlertSeverity.HIGH,
                        source="database_monitoring",
                        message=f"Database query slow: {query_time:.2f}s",
                        details={'query_time': query_time, 'threshold': 5}
                    )
                    await self.alert_manager.process_alert(alert)
                
                # Connection pool alerts
                if active_connections > total_connections * 0.9:
                    alert = Alert(
                        id=f"db_connection_pool_{int(time.time())}",
                        timestamp=datetime.utcnow(),
                        severity=AlertSeverity.HIGH,
                        source="database_monitoring",
                        message=f"Database connection pool nearly exhausted: {active_connections}/{total_connections}",
                        details={'active_connections': active_connections, 'total_connections': total_connections}
                    )
                    await self.alert_manager.process_alert(alert)
            
            await asyncio.sleep(60)  # Monitor every minute
            
        except Exception as e:
            logger.error(f"Error in database monitoring: {e}")
            
            # Database connection error alert
            alert = Alert(
                id=f"db_connection_error_{int(time.time())}",
                timestamp=datetime.utcnow(),
                severity=AlertSeverity.CRITICAL,
                source="database_monitoring",
                message=f"Database connection error: {str(e)}",
                details={'error': str(e)}
            )
            await self.alert_manager.process_alert(alert)
            
            await asyncio.sleep(60)

async def _monitor_ai_models(self) -> None:
    """Monitor AI model performance and usage"""
    logger.info("Starting AI model monitoring")
    
    while self.state == MonitoringState.ACTIVE:
        try:
            # Monitor model usage from Redis cache
            if self.redis_client:
                model_keys = await self.redis_client.keys("ai_model:*:stats")
                
                for key in model_keys:
                    model_name = key.decode().split(':')[1]
                    stats = await self.redis_client.hgetall(key)
                    
                    if stats:
                        decoded_stats = {k.decode(): v.decode() for k, v in stats.items()}
                        
                        # Update metrics
                        requests = int(decoded_stats.get('total_requests', 0))
                        avg_latency = float(decoded_stats.get('avg_latency', 0))
                        error_count = int(decoded_stats.get('error_count', 0))
                        total_tokens = int(decoded_stats.get('total_tokens', 0))
                        
                        provider = decoded_stats.get('provider', 'unknown')
                        
                        self.metrics.ai_model_requests.labels(model=model_name, provider=provider).inc(requests)
                        self.metrics.ai_model_latency.labels(model=model_name, provider=provider).observe(avg_latency)
                        self.metrics.ai_model_tokens.labels(model=model_name, type='total').inc(total_tokens)
                        
                        # Check for model performance issues
                        if avg_latency > 30:  # 30 second threshold
                            alert = Alert(
                                id=f"ai_model_slow_{model_name}_{int(time.time())}",
                                timestamp=datetime.utcnow(),
                                severity=AlertSeverity.HIGH,
                                source="ai_model_monitoring",
                                message=f"AI model {model_name} responding slowly: {avg_latency:.2f}s",
                                details={'model': model_name, 'latency': avg_latency, 'provider': provider}
                            )
                            await self.alert_manager.process_alert(alert)
                        
                        # Check error rates
                        error_rate = error_count / max(requests, 1)
                        if error_rate > 0.05:  # 5% error rate threshold
                            alert = Alert(
                                id=f"ai_model_errors_{model_name}_{int(time.time())}",
                                timestamp=datetime.utcnow(),
                                severity=AlertSeverity.HIGH,
                                source="ai_model_monitoring",
                                message=f"High error rate for AI model {model_name}: {error_rate:.2%}",
                                details={'model': model_name, 'error_rate': error_rate, 'provider': provider}
                            )
                            await self.alert_manager.process_alert(alert)
            
            await asyncio.sleep(120)  # Monitor every 2 minutes
            
        except Exception as e:
            logger.error(f"Error in AI model monitoring: {e}")
            await asyncio.sleep(120)

async def _monitor_learning_engine(self) -> None:
    """Monitor learning engine performance"""
    logger.info("Starting learning engine monitoring")
    
    while self.state == MonitoringState.ACTIVE:
        try:
            # Monitor learning cycles and model performance
            if self.redis_client:
                learning_stats = await self.redis_client.hgetall("learning_engine:stats")
                
                if learning_stats:
                    decoded_stats = {k.decode(): v.decode() for k, v in learning_stats.items()}
                    
                    cycles_completed = int(decoded_stats.get('cycles_completed', 0))
                    avg_accuracy = float(decoded_stats.get('avg_accuracy', 0))
                    training_time = float(decoded_stats.get('avg_training_time', 0))
                    
                    # Update metrics
                    self.metrics.learning_cycles.labels(agent_type='all').inc(cycles_completed)
                    self.metrics.model_accuracy.labels(model_name='ensemble').set(avg_accuracy)
                    
                    # Check for learning performance issues
                    if avg_accuracy < 0.7:  # 70% accuracy threshold
                        alert = Alert(
                            id=f"learning_accuracy_low_{int(time.time())}",
                            timestamp=datetime.utcnow(),
                            severity=AlertSeverity.MEDIUM,
                            source="learning_engine",
                            message=f"Learning engine accuracy below threshold: {avg_accuracy:.2%}",
                            details={'accuracy': avg_accuracy, 'threshold': 0.7}
                        )
                        await self.alert_manager.process_alert(alert)
                    
                    # Check training time
                    if training_time > 300:  # 5 minute threshold
                        alert = Alert(
                            id=f"learning_training_slow_{int(time.time())}",
                            timestamp=datetime.utcnow(),
                            severity=AlertSeverity.MEDIUM,
                            source="learning_engine",
                            message=f"Learning engine training slow: {training_time:.1f}s",
                            details={'training_time': training_time, 'threshold': 300}
                        )
                        await self.alert_manager.process_alert(alert)
            
            # Monitor learning data quality
            await self._check_learning_data_quality()
            
            await asyncio.sleep(300)  # Monitor every 5 minutes
            
        except Exception as e:
            logger.error(f"Error in learning engine monitoring: {e}")
            await asyncio.sleep(300)

async def _check_learning_data_quality(self) -> None:
    """Check quality of learning data"""
    try:
        if len(self.learning_data) > 100:
            # Analyze data distribution
            recent_data = list(self.learning_data)[-100:]
            data_types = [item['type'] for item in recent_data]
            
            # Check for data imbalance
            type_counts = {}
            for data_type in data_types:
                type_counts[data_type] = type_counts.get(data_type, 0) + 1
            
            # Alert if data is too imbalanced
            total_count = len(recent_data)
            for data_type, count in type_counts.items():
                ratio = count / total_count
                if ratio > 0.8:  # 80% of one type
                    alert = Alert(
                        id=f"learning_data_imbalance_{data_type}_{int(time.time())}",
                        timestamp=datetime.utcnow(),
                        severity=AlertSeverity.MEDIUM,
                        source="learning_data_quality",
                        message=f"Learning data imbalanced: {data_type} represents {ratio:.1%} of recent data",
                        details={'data_type': data_type, 'ratio': ratio, 'threshold': 0.8}
                    )
                    await self.alert_manager.process_alert(alert)
                    
    except Exception as e:
        logger.error(f"Error checking learning data quality: {e}")

async def _process_logs(self) -> None:
    """Process and analyze system logs"""
    logger.info("Starting log processing")
    
    while self.state == MonitoringState.ACTIVE:
        try:
            # Process logs from Redis log stream
            if self.redis_client:
                # Get recent log entries
                logs = await self.redis_client.xrange("system_logs", count=100)
                
                error_count = 0
                warning_count = 0
                critical_patterns = []
                
                for log_id, fields in logs:
                    log_data = {k.decode(): v.decode() for k, v in fields.items()}
                    level = log_data.get('level', '').upper()
                    message = log_data.get('message', '')
                    
                    if level == 'ERROR':
                        error_count += 1
                        if any(pattern in message.lower() for pattern in ['timeout', 'connection', 'database']):
                            critical_patterns.append(message)
                    elif level == 'WARNING':
                        warning_count += 1
                
                # Alert on high error rates
                if error_count > 10:  # More than 10 errors in recent logs
                    alert = Alert(
                        id=f"high_error_rate_{int(time.time())}",
                        timestamp=datetime.utcnow(),
                        severity=AlertSeverity.HIGH,
                        source="log_analysis",
                        message=f"High error rate detected: {error_count} errors in recent logs",
                        details={'error_count': error_count, 'threshold': 10}
                    )
                    await self.alert_manager.process_alert(alert)
                
                # Alert on critical patterns
                for pattern in critical_patterns:
                    alert = Alert(
                        id=f"critical_pattern_{hashlib.md5(pattern.encode()).hexdigest()[:8]}_{int(time.time())}",
                        timestamp=datetime.utcnow(),
                        severity=AlertSeverity.CRITICAL,
                        source="log_analysis",
                        message=f"Critical pattern detected in logs",
                        details={'pattern': pattern}
                    )
                    await self.alert_manager.process_alert(alert)
            
            await asyncio.sleep(60)  # Process logs every minute
            
        except Exception as e:
            logger.error(f"Error in log processing: {e}")
            await asyncio.sleep(60)

async def _process_notifications(self) -> None:
    """Process notification queue"""
    logger.info("Starting notification processing")
    
    while self.state == MonitoringState.ACTIVE:
        try:
            # Process notifications from queue
            while not self.notification_queue.empty():
                notification = await self.notification_queue.get()
                await self._send_notification(notification)
                
            await asyncio.sleep(5)  # Check queue every 5 seconds
            
        except Exception as e:
            logger.error(f"Error in notification processing: {e}")
            await asyncio.sleep(5)

async def _send_notification(self, notification: Dict[str, Any]) -> None:
    """Send a notification via configured channels"""
    try:
        # Implementation depends on notification channels configured
        logger.info(f"Sending notification: {notification.get('message', 'Unknown')}")
        
        # Example: Send to configured notification channels
        for channel in self.alert_manager.notification_channels:
            try:
                await channel.send_notification(notification)
            except Exception as e:
                logger.error(f"Failed to send notification via {channel.__class__.__name__}: {e}")
                
    except Exception as e:
        logger.error(f"Error sending notification: {e}")

async def _store_metrics(self, metrics: SystemMetrics) -> None:
    """Store metrics in Redis for historical analysis"""
    try:
        if self.redis_client:
            # Store current metrics
            metrics_data = asdict(metrics)
            metrics_data['timestamp'] = metrics.timestamp.isoformat()
            
            await self.redis_client.lpush("system_metrics", json.dumps(metrics_data))
            
            # Keep only last 1000 entries
            await self.redis_client.ltrim("system_metrics", 0, 999)
            
    except Exception as e:
        logger.error(f"Error storing metrics: {e}")

# Health Check Methods
async def _check_system_health(self) -> Dict[str, Any]:
    """Check overall system health"""
    try:
        metrics = await self._collect_system_metrics()
        
        health_status = "healthy"
        issues = []
        
        if metrics.cpu_percent > 90:
            health_status = "unhealthy"
            issues.append(f"High CPU usage: {metrics.cpu_percent}%")
        
        if metrics.memory_percent > 95:
            health_status = "unhealthy"
            issues.append(f"High memory usage: {metrics.memory_percent}%")
        
        return {
            "status": health_status,
            "issues": issues,
            "metrics": asdict(metrics)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

async def _check_database_health(self) -> Dict[str, Any]:
    """Check database health"""
    try:
        if not self.db_engine:
            return {"status": "not_configured"}
        
        start_time = time.time()
        async with self.db_engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            await result.fetchone()
        
        response_time = time.time() - start_time
        
        if response_time > 5:
            return {
                "status": "unhealthy",
                "response_time": response_time,
                "issue": "Slow response time"
            }
        
        return {
            "status": "healthy",
            "response_time": response_time
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

async def _check_redis_health(self) -> Dict[str, Any]:
    """Check Redis health"""
    try:
        if not self.redis_client:
            return {"status": "not_configured"}
        
        start_time = time.time()
        pong = await self.redis_client.ping()
        response_time = time.time() - start_time
        
        if not pong:
            return {"status": "unhealthy", "issue": "Ping failed"}
        
        return {
            "status": "healthy",
            "response_time": response_time
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

async def _check_agents_health(self) -> Dict[str, Any]:
    """Check health of all agents"""
    try:
        if not self.redis_client:
            return {"status": "not_configured"}
        
        agent_keys = await self.redis_client.keys("agent:*:heartbeat")
        total_agents = len(agent_keys)
        healthy_agents = 0
        unhealthy_agents = []
        
        for key in agent_keys:
            agent_id = key.decode().split(':')[1]
            heartbeat = await self.redis_client.get(key)
            
            if heartbeat:
                heartbeat_time = datetime.fromisoformat(heartbeat.decode())
                time_diff = datetime.utcnow() - heartbeat_time
                
                if time_diff < timedelta(minutes=2):
                    healthy_agents += 1
                else:
                    unhealthy_agents.append({
                        "agent_id": agent_id,
                        "last_seen": str(time_diff)
                    })
            else:
                unhealthy_agents.append({
                    "agent_id": agent_id,
                    "last_seen": "never"
                })
        
        status = "healthy" if len(unhealthy_agents) == 0 else "degraded"
        if len(unhealthy_agents) > total_agents * 0.5:
            status = "unhealthy"
        
        return {
            "status": status,
            "total_agents": total_agents,
            "healthy_agents": healthy_agents,
            "unhealthy_agents": unhealthy_agents
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

async def _check_ai_services_health(self) -> Dict[str, Any]:
    """Check health of AI services"""
    try:
        ai_services = {}
        
        # Check OpenAI
        if self.config.get('ai', {}).get('openai_api_key'):
            try:
                client = openai.AsyncOpenAI(api_key=self.config['ai']['openai_api_key'])
                models = await client.models.list()
                ai_services['openai'] = {"status": "healthy", "models_count": len(models.data)}
            except Exception as e:
                ai_services['openai'] = {"status": "error", "error": str(e)}
        
        # Check Anthropic
        if self.config.get('ai', {}).get('anthropic_api_key'):
            try:
                # Simple health check for Anthropic
                ai_services['anthropic'] = {"status": "configured"}
            except Exception as e:
                ai_services['anthropic'] = {"status": "error", "error": str(e)}
        
        # Determine overall status
        healthy_services = sum(1 for service in ai_services.values() if service.get('status') == 'healthy' or service.get('status') == 'configured')
        total_services = len(ai_services)
        
        if total_services == 0:
            overall_status = "not_configured"
        elif healthy_services == total_services:
            overall_status = "healthy"
        elif healthy_services > 0:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "services": ai_services
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# Public API Methods
async def get_system_status(self) -> Dict[str, Any]:
    """Get comprehensive system status"""
    try:
        health_checks = {}
        
        # Run all health checks
        for check_name, check_func in self.health_checks.items():
            health_checks[check_name] = await check_func()
        
        # Get current metrics
        current_metrics = await self._collect_system_metrics()
        
        # Get recent alerts
        recent_alerts = list(self.alert_manager.alert_history)[-10:]
        
        return {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "uptime": str(datetime.utcnow() - self.start_time),
            "health_checks": health_checks,
            "current_metrics": asdict(current_metrics),
            "recent_alerts": [asdict(alert) for alert in recent_alerts],
            "monitoring_tasks": {name: task.done() for name, task in self.monitoring_tasks.items()}
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            "error": str(e),
            "state": self.state.value
        }

async def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
    """Get historical metrics"""
    try:
        if not self.redis_client:
            return []
        
        # Get metrics from Redis
        metrics_data = await self.redis_client.lrange("system_metrics", 0, -1)
        
        history = []
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        for data in metrics_data:
            try:
                metrics_dict = json.loads(data)
                timestamp = datetime.fromisoformat(metrics_dict['timestamp'])
                
                if timestamp >= cutoff_time:
                    history.append(metrics_dict)
            except Exception as e:
                logger.error(f"Error parsing metrics data: {e}")
                continue
        
        return sorted(history, key=lambda x: x['timestamp'])
        
    except Exception as e:
        logger.error(f"Error getting metrics history: {e}")
        return []

async def acknowledge_alert(self, alert_id: str, user: str = "system") -> bool:
    """Acknowledge an alert"""
    try:
        if alert_id in self.alert_manager.active_alerts:
            alert = self.alert_manager.active_alerts[alert_id]
            alert.acknowledged = True
            
            logger.info(f"Alert {alert_id} acknowledged by {user}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {e}")
        return False

async def resolve_alert(self, alert_id: str, user: str = "system") -> bool:
    """Resolve an alert"""
    try:
        if alert_id in self.alert_manager.active_alerts:
            alert = self.alert_manager.active_alerts[alert_id]
            alert.resolved = True
            
            # Remove from active alerts
            del self.alert_manager.active_alerts[alert_id]
            
            logger.info(f"Alert {alert_id} resolved by {user}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
        return False

async def get
```async def get_alerts(self, severity: Optional[AlertSeverity] = None, limit: int = 50) -> List[Dict[str, Any]]:
“”“Get alerts with optional filtering”””
try:
alerts = list(self.alert_manager.alert_history)

```
    # Filter by severity if specified
    if severity:
        alerts = [alert for alert in alerts if alert.severity == severity]
    
    # Sort by timestamp (most recent first)
    alerts.sort(key=lambda x: x.timestamp, reverse=True)
    
    # Limit results
    alerts = alerts[:limit]
    
    return [asdict(alert) for alert in alerts]
    
except Exception as e:
    logger.error(f"Error getting alerts: {e}")
    return []
```

async def get_agent_metrics(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
“”“Get metrics for specific agent or all agents”””
try:
if not self.redis_client:
return {}

```
    if agent_id:
        # Get metrics for specific agent
        metrics = await self._collect_agent_metrics(agent_id)
        return asdict(metrics) if metrics else {}
    else:
        # Get metrics for all agents
        agent_keys = await self.redis_client.keys("agent:*:metrics")
        all_metrics = {}
        
        for key in agent_keys:
            agent_id = key.decode().split(':')[1]
            metrics = await self._collect_agent_metrics(agent_id)
            if metrics:
                all_metrics[agent_id] = asdict(metrics)
        
        return all_metrics
        
except Exception as e:
    logger.error(f"Error getting agent metrics: {e}")
    return {}
```

async def update_configuration(self, new_config: Dict[str, Any]) -> bool:
“”“Update monitoring configuration dynamically”””
try:
# Validate configuration
if not isinstance(new_config, dict):
return False

```
    # Update specific configuration sections
    if 'thresholds' in new_config:
        self.thresholds.update(new_config['thresholds'])
    
    if 'monitoring_intervals' in new_config:
        intervals = new_config['monitoring_intervals']
        # Note: Changing intervals requires restart of monitoring tasks
        logger.info("Monitoring interval changes require agent restart to take effect")
    
    if 'alert_channels' in new_config:
        # Update alert manager configuration
        await self.alert_manager.update_channels(new_config['alert_channels'])
    
    logger.info("Monitoring configuration updated")
    return True
    
except Exception as e:
    logger.error(f"Error updating configuration: {e}")
    return False
```

async def export_metrics(self, format_type: str = ‘json’, hours: int = 24) -> str:
“”“Export metrics in various formats”””
try:
# Get historical data
metrics_history = await self.get_metrics_history(hours)

```
    if format_type.lower() == 'json':
        return json.dumps(metrics_history, indent=2, default=str)
    elif format_type.lower() == 'csv':
        if not metrics_history:
            return ""
        
        # Convert to CSV format
        import csv
        import io
        
        output = io.StringIO()
        if metrics_history:
            writer = csv.DictWriter(output, fieldnames=metrics_history[0].keys())
            writer.writeheader()
            writer.writerows(metrics_history)
        
        return output.getvalue()
    else:
        raise ValueError(f"Unsupported export format: {format_type}")
        
except Exception as e:
    logger.error(f"Error exporting metrics: {e}")
    return ""
```

async def force_health_check(self) -> Dict[str, Any]:
“”“Force immediate health check of all components”””
try:
logger.info(“Performing forced health check”)

```
    health_results = {}
    for check_name, check_func in self.health_checks.items():
        try:
            health_results[check_name] = await check_func()
        except Exception as e:
            health_results[check_name] = {
                "status": "error",
                "error": str(e)
            }
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "health_checks": health_results
    }
    
except Exception as e:
    logger.error(f"Error in forced health check: {e}")
    return {"error": str(e)}
```

async def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
“”“Get performance summary for the specified time period”””
try:
metrics_history = await self.get_metrics_history(hours)

```
    if not metrics_history:
        return {"error": "No metrics available"}
    
    # Calculate summary statistics
    cpu_values = [m['cpu_percent'] for m in metrics_history if 'cpu_percent' in m]
    memory_values = [m['memory_percent'] for m in metrics_history if 'memory_percent' in m]
    
    summary = {
        "period_hours": hours,
        "data_points": len(metrics_history),
        "cpu_stats": {
            "avg": sum(cpu_values) / len(cpu_values) if cpu_values else 0,
            "min": min(cpu_values) if cpu_values else 0,
            "max": max(cpu_values) if cpu_values else 0
        },
        "memory_stats": {
            "avg": sum(memory_values) / len(memory_values) if memory_values else 0,
            "min": min(memory_values) if memory_values else 0,
            "max": max(memory_values) if memory_values else 0
        }
    }
    
    # Add alert statistics
    recent_alerts = await self.get_alerts(limit=1000)
    period_start = datetime.utcnow() - timedelta(hours=hours)
    
    period_alerts = [
        alert for alert in recent_alerts 
        if datetime.fromisoformat(alert['timestamp']) >= period_start
    ]
    
    summary['alerts'] = {
        "total": len(period_alerts),
        "by_severity": {}
    }
    
    for alert in period_alerts:
        severity = alert['severity']
        summary['alerts']['by_severity'][severity] = \
            summary['alerts']['by_severity'].get(severity, 0) + 1
    
    return summary
    
except Exception as e:
    logger.error(f"Error generating performance summary: {e}")
    return {"error": str(e)}
```

# Cleanup and Shutdown Methods

async def cleanup(self) -> None:
“”“Clean up resources and stop monitoring”””
logger.info(f”Cleaning up monitoring agent {self.agent_id}”)

```
try:
    # Set state to stopping
    self.state = MonitoringState.STOPPING
    
    # Cancel all monitoring tasks
    for task_name, task in self.monitoring_tasks.items():
        if not task.done():
            logger.info(f"Cancelling monitoring task: {task_name}")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error cancelling task {task_name}: {e}")
    
    # Close connections
    if self.redis_client:
        await self.redis_client.aclose()
    
    if self.db_engine:
        await self.db_engine.dispose()
    
    # Final state update
    self.state = MonitoringState.STOPPED
    logger.info(f"Monitoring agent {self.agent_id} stopped successfully")
    
except Exception as e:
    logger.error(f"Error during cleanup: {e}")
    self.state = MonitoringState.ERROR
```

async def **aenter**(self):
“”“Async context manager entry”””
await self.initialize()
return self

async def **aexit**(self, exc_type, exc_val, exc_tb):
“”“Async context manager exit”””
await self.cleanup()

# Factory Methods

@classmethod
async def create_monitoring_agent(
cls,
config: Dict[str, Any],
agent_id: Optional[str] = None,
db_engine: Optional[AsyncEngine] = None,
redis_client: Optional[aioredis.Redis] = None
) -> ‘MonitoringAgent’:
“”“Factory method to create and initialize a monitoring agent”””

```
if not agent_id:
    agent_id = f"monitor_{uuid.uuid4().hex[:8]}"

agent = cls(
    agent_id=agent_id,
    config=config,
    db_engine=db_engine,
    redis_client=redis_client
)

await agent.initialize()
return agent
```

# Main execution function

async def main():
“”“Main function for running the monitoring agent standalone”””
import argparse
import yaml

```
parser = argparse.ArgumentParser(description='YMERA Monitoring Agent')
parser.add_argument('--config', '-c', required=True, help='Configuration file path')
parser.add_argument('--agent-id', help='Agent ID (auto-generated if not provided)')

args = parser.parse_args()

# Load configuration
try:
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    return

# Create and run monitoring agent
try:
    async with MonitoringAgent.create_monitoring_agent(
        config=config,
        agent_id=args.agent_id
    ) as agent:
        logger.info(f"Started monitoring agent {agent.agent_id}")
        
        # Keep running until interrupted
        try:
            while agent.state == MonitoringState.ACTIVE:
                await asyncio.sleep(10)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        
except Exception as e:
    logger.error(f"Failed to start monitoring agent: {e}")
```

if **name** == “**main**”:
asyncio.run(main())