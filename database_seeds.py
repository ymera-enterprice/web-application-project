"""
YMERA Enterprise - Database Seeds System
Production-Ready Database Seeding Infrastructure - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import json
import os
import random
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, Type
from dataclasses import dataclass, field

# Third-party imports (alphabetical)
import structlog
from sqlalchemy import text, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

# Local imports (alphabetical)
from .connection import (
    get_database_manager,
    agent_learning_data,
    knowledge_graph_nodes,
    knowledge_graph_edges,
    knowledge_transfer_logs,
    behavioral_patterns,
    external_knowledge_sources,
    memory_consolidation_sessions,
    learning_metrics
)
from config.settings import get_settings
from monitoring.performance_tracker import track_performance

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.database.seeds")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Seed settings
SEEDS_DIR = Path("database/seeds")
SEED_BATCH_SIZE = 1000
SEED_ENVIRONMENTS = ["development", "testing", "staging", "production"]

# Sample data configurations
SAMPLE_AGENT_IDS = [
    "learning_agent_001",
    "knowledge_processor_002", 
    "pattern_analyzer_003",
    "collaboration_manager_004",
    "memory_optimizer_005",
    "external_integrator_006",
    "performance_monitor_007",
    "validation_agent_008"
]

SAMPLE_KNOWLEDGE_TYPES = [
    "procedural_knowledge",
    "declarative_knowledge", 
    "conditional_knowledge",
    "metacognitive_knowledge",
    "behavioral_pattern",
    "optimization_rule",
    "error_pattern",
    "success_pattern"
]

SAMPLE_PATTERN_TYPES = [
    "communication_pattern",
    "learning_pattern",
    "error_recovery_pattern",
    "optimization_pattern",
    "collaboration_pattern",
    "resource_usage_pattern",
    "performance_pattern",
    "adaptation_pattern"
]

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class SeedConfiguration:
    """Configuration for database seeding"""
    environment: str
    batch_size: int = SEED_BATCH_SIZE
    enable_sample_data: bool = True
    sample_data_count: int = 100
    enable_performance_data: bool = True
    enable_learning_history: bool = True
    seed_all_tables: bool = True

@dataclass
class SeedExecutionResult:
    """Result of seed execution"""
    seeder_name: str
    table_name: str
    records_created: int
    execution_time_ms: int
    success: bool
    error_message: Optional[str] = None

@dataclass
class SeedSummary:
    """Summary of complete seeding operation"""
    environment: str
    total_seeders: int
    successful_seeders: int
    failed_seeders: int
    total_records_created: int
    total_execution_time_ms: int
    results: List[SeedExecutionResult] = field(default_factory=list)

# ===============================================================================
# BASE SEED CLASSES
# ===============================================================================

class BaseSeed(ABC):
    """Abstract base class for all database seeders"""
    
    def __init__(self, config: SeedConfiguration):
        self.config = config
        self.logger = logger.bind(seeder=self.__class__.__name__)
        self.table_name = ""
        self.batch_size = config.batch_size
    
    @abstractmethod
    async def should_seed(self, session: AsyncSession) -> bool:
        """Determine if seeding should occur"""
        pass
    
    @abstractmethod
    async def generate_data(self) -> List[Dict[str, Any]]:
        """Generate seed data"""
        pass
    
    @abstractmethod
    async def insert_data(self, session: AsyncSession, data: List[Dict[str, Any]]) -> int:
        """Insert data into database"""
        pass
    
    async def execute(self, session: AsyncSession) -> SeedExecutionResult:
        """Execute the seeding process"""
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(f"Starting seeding for {self.table_name}")
            
            # Check if seeding should occur
            if not await self.should_seed(session):
                self.logger.info(f"Skipping seeding for {self.table_name} - conditions not met")
                return SeedExecutionResult(
                    seeder_name=self.__class__.__name__,
                    table_name=self.table_name,
                    records_created=0,
                    execution_time_ms=0,
                    success=True
                )
            
            # Generate seed data
            data = await self.generate_data()
            
            if not data:
                self.logger.info(f"No data to seed for {self.table_name}")
                return SeedExecutionResult(
                    seeder_name=self.__class__.__name__,
                    table_name=self.table_name,
                    records_created=0,
                    execution_time_ms=0,
                    success=True
                )
            
            # Insert data in batches
            total_records = 0
            
            for i in range(0, len(data), self.batch_size):
                batch = data[i:i + self.batch_size]
                records_inserted = await self.insert_data(session, batch)
                total_records += records_inserted
                
                await session.flush()
                
                self.logger.debug(
                    f"Inserted batch for {self.table_name}",
                    batch_size=len(batch),
                    total_records=total_records
                )
            
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.logger.info(
                f"Completed seeding for {self.table_name}",
                records_created=total_records,
                execution_time_ms=execution_time
            )
            
            return SeedExecutionResult(
                seeder_name=self.__class__.__name__,
                table_name=self.table_name,
                records_created=total_records,
                execution_time_ms=execution_time,
                success=True
            )
            
        except Exception as e:
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.logger.error(
                f"Seeding failed for {self.table_name}",
                error=str(e),
                execution_time_ms=execution_time
            )
            
            return SeedExecutionResult(
                seeder_name=self.__class__.__name__,
                table_name=self.table_name,
                records_created=0,
                execution_time_ms=execution_time,
                success=False,
                error_message=str(e)
            )

# ===============================================================================
# LEARNING SYSTEM SEEDERS
# ===============================================================================

class AgentLearningDataSeeder(BaseSeed):
    """Seeder for agent learning data"""
    
    def __init__(self, config: SeedConfiguration):
        super().__init__(config)
        self.table_name = "agent_learning_data"
    
    async def should_seed(self, session: AsyncSession) -> bool:
        """Check if agent learning data should be seeded"""
        if not self.config.enable_sample_data:
            return False
        
        # Check if table has data
        result = await session.execute(select(agent_learning_data).limit(1))
        return result.first() is None
    
    async def generate_data(self) -> List[Dict[str, Any]]:
        """Generate sample agent learning data"""
        data = []
        base_time = datetime.utcnow() - timedelta(days=30)
        
        for i in range(self.config.sample_data_count):
            # Generate learning cycle data
            learning_cycle_id = str(uuid.uuid4())
            agent_id = random.choice(SAMPLE_AGENT_IDS)
            
            # Generate realistic experience data
            experience_data = {
                "interaction_type": random.choice(["user_query", "system_event", "agent_collaboration"]),
                "context": {
                    "session_id": str(uuid.uuid4()),
                    "task_type": random.choice(["data_processing", "knowledge_extraction", "pattern_analysis"]),
                    "complexity_level": random.randint(1, 10)
                },
                "inputs": {
                    "data_size": random.randint(100, 10000),
                    "processing_parameters": {
                        "algorithm": random.choice(["neural_network", "decision_tree", "clustering"]),
                        "threshold": round(random.uniform(0.1, 0.9), 2)
                    }
                },
                "outputs": {
                    "success_rate": round(random.uniform(0.7, 0.99), 2),
                    "processing_time": random.randint(50, 5000),
                    "quality_score": random.randint(70, 100)
                }
            }
            
            # Generate extracted knowledge
            knowledge_extracted = {
                "patterns_discovered": random.randint(0, 5),
                "rules_learned": [
                    {
                        "rule_type": random.choice(["optimization", "error_handling", "efficiency"]),
                        "condition": f"complexity_level > {random.randint(5, 8)}",
                        "action": "increase_processing_threads",
                        "confidence": round(random.uniform(0.7, 0.95), 2)
                    }
                ],
                "performance_insights": {
                    "bottlenecks_identified": random.randint(0, 3),
                    "optimization_opportunities": random.randint(1, 4),
                    "resource_efficiency": round(random.uniform(0.6, 0.95), 2)
                }
            }
            
            # Calculate timestamp with some variation
            timestamp_offset = timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            learning_timestamp = base_time + timestamp_offset
            
            data.append({
                "id": str(uuid.uuid4()),
                "agent_id": agent_id,
                "learning_cycle_id": learning_cycle_id,
                "experience_data": experience_data,
                "knowledge_extracted": knowledge_extracted,
                "confidence_score": random.randint(70, 95),
                "learning_timestamp": learning_timestamp,
                "source_type": random.choice(["direct_experience", "collaboration", "external_data"]),
                "processing_time_ms": random.randint(10, 500),
                "created_at": learning_timestamp,
                "updated_at": learning_timestamp
            })
        
        return data
    
    async def insert_data(self, session: AsyncSession, data: List[Dict[str, Any]]) -> int:
        """Insert agent learning data"""
        result = await session.execute(insert(agent_learning_data).values(data))
        return len(data)

class KnowledgeGraphSeeder(BaseSeed):
    """Seeder for knowledge graph nodes and edges"""
    
    def __init__(self, config: SeedConfiguration):
        super().__init__(config)
        self.table_name = "knowledge_graph"
    
    async def should_seed(self, session: AsyncSession) -> bool:
        """Check if knowledge graph should be seeded"""
        if not self.config.enable_sample_data:
            return False
        
        # Check if nodes table has data
        result = await session.execute(select(knowledge_graph_nodes).limit(1))
        return result.first() is None
    
    async def generate_data(self) -> List[Dict[str, Any]]:
        """Generate sample knowledge graph data"""
        nodes_data = []
        edges_data = []
        
        # Generate nodes
        node_ids = []
        
        for i in range(self.config.sample_data_count):
            node_id = str(uuid.uuid4())
            node_ids.append(node_id)
            
            node_type = random.choice(SAMPLE_KNOWLEDGE_TYPES)
            
            # Generate realistic node data based on type
            if node_type == "procedural_knowledge":
                node_data = {
                    "procedure_name": f"process_data_type_{i}",
                    "steps": [
                        {"step": 1, "action": "validate_input", "expected_time_ms": random.randint(10, 100)},
                        {"step": 2, "action": "transform_data", "expected_time_ms": random.randint(100, 1000)},
                        {"step": 3, "action": "validate_output", "expected_time_ms": random.randint(10, 100)}
                    ],
                    "success_rate": round(random.uniform(0.8, 0.99), 2),
                    "average_execution_time": random.randint(200, 2000)
                }
            elif node_type == "behavioral_pattern":
                node_data = {
                    "pattern_name": f"collaboration_pattern_{i}",
                    "trigger_conditions": {
                        "agent_load": f"> {random.randint(70, 90)}%",
                        "task_complexity": f"> {random.randint(6, 9)}"
                    },
                    "behavioral_response": {
                        "action": "request_assistance",
                        "target_agents": random.randint(1, 3),
                        "timeout_ms": random.randint(5000, 30000)
                    },
                    "effectiveness_score": round(random.uniform(0.7, 0.95), 2)
                }
            else:
                node_data = {
                    "knowledge_item": f"generic_knowledge_{i}",
                    "category": node_type,
                    "confidence": round(random.uniform(0.6, 0.95), 2),
                    "usage_frequency": random.randint(1, 100)
                }
            
            timestamp = datetime.utcnow() - timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23)
            )
            
            nodes_data.append({
                "id": node_id,
                "node_type": node_type,
                "node_data": node_data,
                "confidence_score": random.randint(60, 95),
                "source_agent_id": random.choice(SAMPLE_AGENT_IDS),
                "creation_timestamp": timestamp,
                "last_accessed": timestamp + timedelta(hours=random.randint(1, 72)),
                "access_count": random.randint(1, 50),
                "validation_status": random.choice(["validated", "pending", "in_review"]),
                "created_at": timestamp,
                "updated_at": timestamp
            })
        
        # Generate edges (relationships between nodes)
        edge_count = min(self.config.sample_data_count // 2, len(node_ids) // 2)
        
        for i in range(edge_count):
            source_node = random.choice(node_ids)
            target_node = random.choice([n for n in node_ids if n != source_node])
            
            relationship_types = [
                "depends_on", "enhances", "conflicts_with", "similar_to",
                "prerequisite_for", "alternative_to", "composed_of"
            ]
            
            relationship_data = {
                "strength": round(random.uniform(0.3, 0.9), 2),
                "discovered_at": datetime.utcnow() - timedelta(days=random.randint(0, 15)),
                "validation_count": random.randint(1, 10)
            }
            
            timestamp = datetime.utcnow() - timedelta(days=random.randint(0, 20))
            
            edges_data.append({
                "id": str(uuid.uuid4()),
                "source_node_id": source_node,
                "target_node_id": target_node,
                "relationship_type": random.choice(relationship_types),
                "relationship_data": relationship_data,
                "strength_score": random.randint(30, 90),
                "created_by_agent": random.choice(SAMPLE_AGENT_IDS),
                "created_at": timestamp,
                "updated_at": timestamp
            })
        
        return {"nodes": nodes_data, "edges": edges_data}
    
    async def insert_data(self, session: AsyncSession, data: Dict[str, Any]) -> int:
        """Insert knowledge graph data"""
        total_records = 0
        
        # Insert nodes
        if data["nodes"]:
            await session.execute(insert(knowledge_graph_nodes).values(data["nodes"]))
            total_records += len(data["nodes"])
        
        # Insert edges
        if data["edges"]:
            await session.execute(insert(knowledge_graph_edges).values(data["edges"]))
            total_records += len(data["edges"])
        
        return total_records

class KnowledgeTransferSeeder(BaseSeed):
    """Seeder for knowledge transfer logs"""
    
    def __init__(self, config: SeedConfiguration):
        super().__init__(config)
        self.table_name = "knowledge_transfer_logs"
    
    async def should_seed(self, session: AsyncSession) -> bool:
        """Check if knowledge transfer logs should be seeded"""
        if not self.config.enable_sample_data:
            return False
        
        result = await session.execute(select(knowledge_transfer_logs).limit(1))
        return result.first() is None
    
    async def generate_data(self) -> List[Dict[str, Any]]:
        """Generate sample knowledge transfer data"""
        data = []
        
        for i in range(self.config.sample_data_count):
            source_agent = random.choice(SAMPLE_AGENT_IDS)
            target_agent = random.choice([a for a in SAMPLE_AGENT_IDS if a != source_agent])
            
            transfer_types = [
                "pattern_sharing", "optimization_rule", "error_solution",
                "performance_insight", "behavioral_adaptation", "resource_allocation"
            ]
            
            transfer_data = {
                "knowledge_type": random.choice(SAMPLE_KNOWLEDGE_TYPES),
                "transfer_method": random.choice(["direct_sync", "queued_transfer", "broadcast"]),
                "knowledge_content": {
                    "summary": f"Knowledge transfer {i}",
                    "applicability_score": round(random.uniform(0.6, 0.9), 2),
                    "complexity_level": random.randint(1, 10)
                },
                "validation_result": {
                    "pre_transfer_validation": random.choice([True, False]),
                    "post_transfer_validation": random.choice([True, False]),
                    "integration_success": random.choice([True, False])
                }
            }
            
            success_status = transfer_data["validation_result"]["integration_success"]
            processing_time = random.randint(50, 2000) if success_status else random.randint(100, 5000)
            
            timestamp = datetime.utcnow() - timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            data.append({
                "id": str(uuid.uuid4()),
                "source_agent_id": source_agent,
                "target_agent_id": target_agent,
                "knowledge_item_id": str(uuid.uuid4()),
                "transfer_type": random.choice(transfer_types),
                "transfer_data": transfer_data,
                "success_status": success_status,
                "transfer_timestamp": timestamp,
                "processing_time_ms": processing_time,
                "collaboration_score": random.randint(60, 95) if success_status else random.randint(20, 60),
                "created_at": timestamp
            })
        
        return data
    
    async def insert_data(self, session: AsyncSession, data: List[Dict[str, Any]]) -> int:
        """Insert knowledge transfer data"""
        await session.execute(insert(knowledge_transfer_logs).values(data))
        return len(data)

class BehavioralPatternsSeeder(BaseSeed):
    """Seeder for behavioral patterns"""
    
    def __init__(self, config: SeedConfiguration):
        super().__init__(config)
        self.table_name = "behavioral_patterns"
    
    async def should_seed(self, session: AsyncSession) -> bool:
        """Check if behavioral patterns should be seeded"""
        if not self.config.enable_sample_data:
            return False
        
        result = await session.execute(select(behavioral_patterns).limit(1))
        return result.first() is None
    
    async def generate_data(self) -> List[Dict[str, Any]]:
        """Generate sample behavioral patterns"""
        data = []
        
        for i in range(self.config.sample_data_count // 2):  # Fewer patterns as they're more significant
            pattern_type = random.choice(SAMPLE_PATTERN_TYPES)
            
            # Generate pattern-specific data
            if pattern_type == "communication_pattern":
                pattern_data = {
                    "pattern_name": f"efficient_communication_{i}",
                    "trigger_conditions": {
                        "message_queue_size": f"> {random.randint(50, 100)}",
                        "response_time": f"> {random.randint(1000, 3000)}ms"
                    },
                    "behavioral_rules": {
                        "prioritize_urgent": True,
                        "batch_similar_requests": True,
                        "escalation_threshold": random.randint(3, 7)
                    },
                    "effectiveness_metrics": {
                        "response_time_improvement": f"{random.randint(20, 60)}%",
                        "throughput_increase": f"{random.randint(15, 40)}%"
                    }
                }
            elif pattern_type == "learning_pattern":
                pattern_data = {
                    "pattern_name": f"adaptive_learning_{i}",
                    "learning_triggers": {
                        "error_rate_threshold": f"> {random.randint(5, 15)}%",
                        "performance_decline": f"> {random.randint(10, 25)}%"
                    },
                    "adaptation_strategy": {
                        "algorithm_adjustment": random.choice(["gradual", "immediate", "scheduled"]),
                        "parameter_tuning": "automatic",
                        "knowledge_integration": "continuous"
                    },
                    "success_indicators": {
                        "error_reduction": f"{random.randint(30, 70)}%",
                        "learning_velocity": f"{random.randint(15, 50)}% faster"
                    }
                }
            else:
                pattern_data = {
                    "pattern_name": f"generic_pattern_{i}",
                    "pattern_description": f"Behavioral pattern for {pattern_type}",
                    "activation_frequency": random.randint(1, 100),
                    "success_rate": round(random.uniform(0.7, 0.95), 2)
                }
            
            timestamp = datetime.utcnow() - timedelta(
                days=random.randint(0, 45),
                hours=random.randint(0, 23)
            )
            
            last_applied = timestamp + timedelta(
                days=random.randint(1, 15),
                hours=random.randint(0, 23)
            ) if random.choice([True, False]) else None
            
            data.append({
                "id": str(uuid.uuid4()),
                "pattern_type": pattern_type,
                "pattern_data": pattern_data,
                "discovery_agent_id": random.choice(SAMPLE_AGENT_IDS),
                "significance_score": random.randint(70, 95),
                "usage_count": random.randint(1, 100),
                "last_applied": last_applied,
                "discovery_timestamp": timestamp,
                "validation_status": random.choice(["validated", "in_review", "experimental"]),
                "created_at": timestamp,
                "updated_at": timestamp
            })
        
        return data
    
    async def insert_data(self, session: AsyncSession, data: List[Dict[str, Any]]) -> int:
        """Insert behavioral patterns data"""
        await session.execute(insert(behavioral_patterns).values(data))
        return len(data)

class LearningMetricsSeeder(BaseSeed):
    """Seeder for learning metrics and analytics"""
    
    def __init__(self, config: SeedConfiguration):
        super().__init__(config)
        self.table_name = "learning_metrics"
    
    async def should_seed(self, session: AsyncSession) -> bool:
        """Check if learning metrics should be seeded"""
        if not self.config.enable_performance_data:
            return False
        
        result = await session.execute(select(learning_metrics).limit(1))
        return result.first() is None
    
    async def generate_data(self) -> List[Dict[str, Any]]:
        """Generate sample learning metrics"""
        data = []
        base_time = datetime.utcnow() - timedelta(days=30)
        
        metric_types = [
            "learning_velocity", "knowledge_retention_rate", "collaboration_effectiveness",
            "pattern_discovery_rate", "external_integration_success", "memory_optimization_efficiency",
            "agent_performance_score", "system_intelligence_level"
        ]
        
        # Generate metrics for each agent and time period
        for day in range(30):  # 30 days of historical data
            for agent_id in SAMPLE_AGENT_IDS:
                for metric_type in random.sample(metric_types, random.randint(3, 6)):
                    
                    # Generate realistic metric values based on type
                    if metric_type == "learning_velocity":
                        metric_value = random.randint(50, 200)  # Knowledge items per hour
                        metric_data = {
                            "knowledge_items_learned": metric_value,
                            "learning_efficiency": round(random.uniform(0.7, 0.95), 2),
                            "processing_speed": random.randint(100, 500)
                        }
                    elif metric_type == "collaboration_effectiveness":
                        metric_value = random.randint(60, 95)  # Percentage
                        metric_data = {
                            "successful_collaborations": random.randint(10, 50),
                            "knowledge_transfers": random.randint(5, 25),
                            "response_time_avg": random.randint(100, 1000)
                        }
                    elif metric_type == "pattern_discovery_rate":
                        metric_value = random.randint(1, 10)  # Patterns per day
                        metric_data = {
                            "patterns_discovered": metric_value,
                            "patterns_validated": random.randint(0, metric_value),
                            "discovery_accuracy": round(random.uniform(0.6, 0.9), 2)
                        }
                    else:
                        metric_value = random.randint(70, 95)
                        metric_data = {
                            "metric_specific_data": f"Data for {metric_type}",
                            "measurement_accuracy": round(random.uniform(0.8, 0.99), 2)
                        }
                    
                    metric_timestamp = base_time + timedelta(days=day, hours=random.randint(0, 23))
                    period_start = metric_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                    period_end = period_start + timedelta(days=1)
                    
                    data.append({
                        "id": str(uuid.uuid4()),
                        "metric_timestamp": metric_timestamp,
                        "metric_type": metric_type,
                        "agent_id": agent_id,
                        "metric_value": metric_value,
                        "metric_data": metric_data,
                        "measurement_period_start": period_start,
                        "measurement_period_end": period_end,
                        "created_at": metric_timestamp
                    })
        
        return data
    
    async def insert_data(self, session: AsyncSession, data: List[Dict[str, Any]]) -> int:
        """Insert learning metrics data"""
        await session.execute(insert(learning_metrics).values(data))
        return len(data)

# ===============================================================================
# SEED MANAGER
# ===============================================================================

class SeedManager:
    """Production-ready database seed manager"""
    
    def __init__(self, config: Optional[SeedConfiguration] = None):
        self.config = config or self._load_default_config()
        self.logger = logger.bind(manager="SeedManager")
        
        # Register all available seeders
        self._seeders: List[Type[BaseSeed]] = [
            AgentLearningDataSeeder,
            KnowledgeGraphSeeder,
            KnowledgeTransferSeeder,
            BehavioralPatternsSeeder,
            LearningMetricsSeeder
        ]
    
    def _load_default_config(self) -> SeedConfiguration:
        """Load default seed configuration"""
        environment = getattr(settings, 'ENVIRONMENT', 'development')
        
        return SeedConfiguration(
            environment=environment,
            batch_size=getattr(settings, 'SEED_BATCH_SIZE', SEED_BATCH_SIZE),
            enable_sample_data=getattr(settings, 'SEED_ENABLE_SAMPLE_DATA', True),
            sample_data_count=getattr(settings, 'SEED_SAMPLE_COUNT', 100),
            enable_performance_data=getattr(settings, 'SEED_ENABLE_PERFORMANCE_DATA', True),
            enable_learning_history=getattr(settings, 'SEED_ENABLE_LEARNING_HISTORY', True),
            seed_all_tables=getattr(settings, 'SEED_ALL_TABLES', True)
        )
    
    @track_performance
    async def seed_database(self, selected_seeders: Optional[List[str]] = None) -> SeedSummary:
        """
        Execute database seeding process.
        
        Args:
            selected_seeders: Optional list of seeder class names to run
            
        Returns:
            SeedSummary with execution results
        """
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(
                "Starting database seeding",
                environment=self.config.environment,
                selected_seeders=selected_seeders
            )
            
            # Filter seeders if specific ones requested
            seeders_to_run = self._seeders
            if selected_seeders:
                seeders_to_run = [
                    seeder for seeder in self._seeders 
                    if seeder.__name__ in selected_seeders
                ]
            
            # Execute seeders
            results = []
            total_records = 0
            
            db_manager = await get_database_manager()
            
            async with db_manager.get_session() as session:
                async with session.begin():
                    for seeder_class in seeders_to_run:
                        try:
                            seeder = seeder_class(self.config)
                            result = await seeder.execute(session)
                            results.append(result)
                            
                            if result.success:
                                total_records += result.records_created
                            
                        except Exception as e:
                            self.logger.error(
                                "Seeder execution failed",
                                seeder=seeder_class.__name__,
                                error=str(e)
                            )
                            
                            results.append(SeedExecutionResult(
                                seeder_name=seeder_class.__name__,
                                table_name="unknown",
                                records_created=0,
                                execution_time_ms=0,
                                success=False,
                                error_message=str(e)
                            ))
                    
                    # Commit all changes
                    await session.flush()
            
            # Generate summary
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            successful_seeders = len([r for r in results if r.success])
            failed_seeders = len(results) - successful_seeders
            
            summary = SeedSummary(
                environment=self.config.environment,
                total_seeders=len(results),
                successful_seeders=successful_seeders,
                failed_seeders=failed_seeders,
                total_records_created=total_records,
                total_execution_time_ms=execution_time,
                results=results
            )
            
            self.logger.info(
                "Database seeding completed",
                successful_seeders=successful_seeders,
                failed_seeders=failed_seeders,
                total_records=total_records,
                execution_time_ms=execution_time
            )
            
            return summary
            
        except Exception as e:
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.logger.error("Database seeding failed", error=str(e))
            
            return SeedSummary(
                environment=self.config.environment,
                total_seeders=0,
                successful_seeders=0,
                failed_seeders=1,
                total_records_created=0,
                total_execution_time_ms=execution_time,
                results=[SeedExecutionResult(
                    seeder_name="SeedManager",
                    table_name="all",
                    records_created=0,
                    execution_time_ms=execution_time,
                    success=False,
                    error_message=str(e)
                )]
            )
    
    async def get_seeding_status(self) -> Dict[str, Any]:
        """Get current database seeding status"""
        try:
            db_manager = await get_database_manager()
            status = {"tables": {}}
            
            # Check each table for data
            tables_to_check = [
                ("agent_learning_data", agent_learning_data),
                ("knowledge_graph_nodes", knowledge_graph_nodes),
                ("knowledge_graph_edges", knowledge_graph_edges),
                ("knowledge_transfer_logs", knowledge_transfer_logs),
                ("behavioral_patterns", behavioral_patterns),
                ("learning_metrics", learning_metrics)
            ]
            
            for table_name, table_obj in tables_to_check:
                try:
                    async with db_manager.get_session() as session:
                        # Count records
                        count_result = await session.execute(
                            text(f"SELECT COUNT(*) as count FROM {table_name}")
                        )
                        record_count = count_result.scalar()
                        
                        # Get latest record timestamp if exists
                        latest_timestamp = None
                        if record_count > 0:
                            timestamp_result = await session.execute(
                                text(f"SELECT MAX(created_at) as latest FROM {table_name}")
                            )
                            latest_timestamp = timestamp_result.scalar()
                        
                        status["tables"][table_name] = {
                            "record_count": record_count,
                            "has_data": record_count > 0,
                            "latest_record": latest_timestamp.isoformat() if latest_timestamp else None
                        }
                        
                except Exception as e:
                    status["tables"][table_name] = {
                        "error": str(e),
                        "has_data": False,
                        "record_count": 0
                    }
            
            # Calculate overall status
            total_records = sum(
                table_info.get("record_count", 0) 
                for table_info in status["tables"].values()
                if isinstance(table_info.get("record_count"), int)
            )
            
            tables_with_data = len([
                table for table in status["tables"].values()
                if table.get("has_data", False)
            ])
            
            status.update({
                "environment": self.config.environment,
                "total_records": total_records,
                "tables_with_data": tables_with_data,
                "total_tables_checked": len(tables_to_check),
                "seeding_recommended": tables_with_data < len(tables_to_check) // 2,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return status
            
        except Exception as e:
            self.logger.error("Failed to get seeding status", error=str(e))
            return {
                "environment": self.config.environment,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def clear_sample_data(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Clear sample data from database (use with caution).
        
        Args:
            confirm: Must be True to execute clearing
            
        Returns:
            Dict with clearing results
        """
        if not confirm:
            return {
                "status": "cancelled",
                "message": "Data clearing requires explicit confirmation",
                "cleared_records": 0
            }
        
        if self.config.environment == "production":
            raise RuntimeError("Sample data clearing is not allowed in production environment")
        
        try:
            self.logger.warning("Starting sample data clearing", environment=self.config.environment)
            
            db_manager = await get_database_manager()
            cleared_records = 0
            
            # Tables to clear (in order to respect foreign key constraints)
            tables_to_clear = [
                "learning_metrics",
                "memory_consolidation_sessions", 
                "external_knowledge_sources",
                "knowledge_transfer_logs",
                "behavioral_patterns",
                "knowledge_graph_edges",
                "knowledge_graph_nodes",
                "agent_learning_data"
            ]
            
            async with db_manager.get_session() as session:
                async with session.begin():
                    for table_name in tables_to_clear:
                        try:
                            # Count records before deletion
                            count_result = await session.execute(
                                text(f"SELECT COUNT(*) FROM {table_name}")
                            )
                            record_count = count_result.scalar()
                            
                            if record_count > 0:
                                # Clear table
                                await session.execute(text(f"DELETE FROM {table_name}"))
                                cleared_records += record_count
                                
                                self.logger.info(
                                    "Cleared table data",
                                    table=table_name,
                                    records_cleared=record_count
                                )
                        
                        except Exception as e:
                            self.logger.error(
                                "Failed to clear table",
                                table=table_name,
                                error=str(e)
                            )
                    
                    await session.flush()
            
            self.logger.warning(
                "Sample data clearing completed",
                total_cleared=cleared_records
            )
            
            return {
                "status": "completed",
                "environment": self.config.environment,
                "cleared_records": cleared_records,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error("Sample data clearing failed", error=str(e))
            return {
                "status": "failed",
                "error": str(e),
                "cleared_records": 0,
                "timestamp": datetime.utcnow().isoformat()
            }

# ===============================================================================
# ENVIRONMENT-SPECIFIC SEED CONFIGURATIONS
# ===============================================================================

class DevelopmentSeedConfig(SeedConfiguration):
    """Development environment seed configuration"""
    
    def __init__(self):
        super().__init__(
            environment="development",
            batch_size=500,
            enable_sample_data=True,
            sample_data_count=200,
            enable_performance_data=True,
            enable_learning_history=True,
            seed_all_tables=True
        )

class TestingSeedConfig(SeedConfiguration):
    """Testing environment seed configuration"""
    
    def __init__(self):
        super().__init__(
            environment="testing",
            batch_size=100,
            enable_sample_data=True,
            sample_data_count=50,
            enable_performance_data=False,
            enable_learning_history=False,
            seed_all_tables=False
        )

class StagingSeedConfig(SeedConfiguration):
    """Staging environment seed configuration"""
    
    def __init__(self):
        super().__init__(
            environment="staging",
            batch_size=1000,
            enable_sample_data=True,
            sample_data_count=500,
            enable_performance_data=True,
            enable_learning_history=True,
            seed_all_tables=True
        )

class ProductionSeedConfig(SeedConfiguration):
    """Production environment seed configuration"""
    
    def __init__(self):
        super().__init__(
            environment="production",
            batch_size=2000,
            enable_sample_data=False,  # No sample data in production
            sample_data_count=0,
            enable_performance_data=False,
            enable_learning_history=False,
            seed_all_tables=False
        )

# ===============================================================================
# SEED CONFIGURATION FACTORY
# ===============================================================================

def get_seed_config(environment: Optional[str] = None) -> SeedConfiguration:
    """Get seed configuration for specified environment"""
    if environment is None:
        environment = getattr(settings, 'ENVIRONMENT', 'development')
    
    config_map = {
        "development": DevelopmentSeedConfig,
        "testing": TestingSeedConfig,
        "staging": StagingSeedConfig,
        "production": ProductionSeedConfig
    }
    
    config_class = config_map.get(environment, DevelopmentSeedConfig)
    return config_class()

# ===============================================================================
# GLOBAL SEED MANAGER
# ===============================================================================

_seed_manager: Optional[SeedManager] = None

async def get_seed_manager(config: Optional[SeedConfiguration] = None) -> SeedManager:
    """Get or create global seed manager instance"""
    global _seed_manager
    
    if _seed_manager is None or (config and _seed_manager.config != config):
        _seed_manager = SeedManager(config)
    
    return _seed_manager

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def seed_database(
    environment: Optional[str] = None,
    selected_seeders: Optional[List[str]] = None
) -> SeedSummary:
    """
    Execute database seeding for specified environment.
    
    Args:
        environment: Target environment (development, testing, staging, production)
        selected_seeders: Optional list of specific seeders to run
        
    Returns:
        SeedSummary with execution results
    """
    config = get_seed_config(environment)
    manager = await get_seed_manager(config)
    return await manager.seed_database(selected_seeders)

async def get_seeding_status(environment: Optional[str] = None) -> Dict[str, Any]:
    """Get current seeding status for environment"""
    config = get_seed_config(environment)
    manager = await get_seed_manager(config)
    return await manager.get_seeding_status()

async def clear_sample_data(
    environment: Optional[str] = None, 
    confirm: bool = False
) -> Dict[str, Any]:
    """Clear sample data from database"""
    config = get_seed_config(environment)
    manager = await get_seed_manager(config)
    return await manager.clear_sample_data(confirm)

async def seed_for_testing() -> SeedSummary:
    """Quick seeding setup for testing environments"""
    return await seed_database("testing", [
        "AgentLearningDataSeeder",
        "KnowledgeGraphSeeder"
    ])

async def seed_for_development() -> SeedSummary:
    """Full seeding setup for development environments"""
    return await seed_database("development")

# ===============================================================================
# SEED DATA VALIDATION
# ===============================================================================

async def validate_seed_data() -> Dict[str, Any]:
    """Validate integrity of seeded data"""
    try:
        logger.info("Starting seed data validation")
        
        db_manager = await get_database_manager()
        validation_results = {
            "overall_status": "valid",
            "checks": {},
            "issues": [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        async with db_manager.get_session() as session:
            # Check referential integrity
            integrity_checks = [
                {
                    "name": "knowledge_graph_edges_references",
                    "query": """
                        SELECT COUNT(*) as invalid_count
                        FROM knowledge_graph_edges e
                        WHERE NOT EXISTS (
                            SELECT 1 FROM knowledge_graph_nodes n1 WHERE n1.id = e.source_node_id
                        ) OR NOT EXISTS (
                            SELECT 1 FROM knowledge_graph_nodes n2 WHERE n2.id = e.target_node_id
                        )
                    """
                },
                {
                    "name": "agent_ids_consistency",
                    "query": """
                        SELECT 
                            'agent_learning_data' as table_name,
                            COUNT(DISTINCT agent_id) as unique_agents
                        FROM agent_learning_data
                        UNION ALL
                        SELECT 
                            'knowledge_transfer_logs' as table_name,
                            COUNT(DISTINCT source_agent_id) as unique_agents
                        FROM knowledge_transfer_logs
                    """
                },
                {
                    "name": "timestamp_consistency",
                    "query": """
                        SELECT COUNT(*) as future_timestamps
                        FROM (
                            SELECT created_at FROM agent_learning_data WHERE created_at > NOW()
                            UNION ALL
                            SELECT created_at FROM knowledge_graph_nodes WHERE created_at > NOW()
                            UNION ALL
                            SELECT created_at FROM behavioral_patterns WHERE created_at > NOW()
                        ) future_data
                    """
                }
            ]
            
            for check in integrity_checks:
                try:
                    result = await session.execute(text(check["query"]))
                    
                    if check["name"] == "agent_ids_consistency":
                        rows = result.fetchall()
                        agent_counts = {row[0]: row[1] for row in rows}
                        validation_results["checks"][check["name"]] = {
                            "status": "valid",
                            "data": agent_counts
                        }
                    else:
                        count = result.scalar()
                        is_valid = count == 0
                        
                        validation_results["checks"][check["name"]] = {
                            "status": "valid" if is_valid else "invalid",
                            "invalid_count": count
                        }
                        
                        if not is_valid:
                            validation_results["overall_status"] = "invalid"
                            validation_results["issues"].append({
                                "check": check["name"],
                                "issue": f"Found {count} invalid records"
                            })
                
                except Exception as e:
                    validation_results["checks"][check["name"]] = {
                        "status": "error",
                        "error": str(e)
                    }
                    validation_results["issues"].append({
                        "check": check["name"],
                        "issue": f"Validation check failed: {str(e)}"
                    })
        
        logger.info(
            "Seed data validation completed",
            status=validation_results["overall_status"],
            issues_found=len(validation_results["issues"])
        )
        
        return validation_results
        
    except Exception as e:
        logger.error("Seed data validation failed", error=str(e))
        return {
            "overall_status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    # Core classes
    "BaseSeed",
    "SeedManager",
    
    # Seeder implementations
    "AgentLearningDataSeeder",
    "KnowledgeGraphSeeder", 
    "KnowledgeTransferSeeder",
    "BehavioralPatternsSeeder",
    "LearningMetricsSeeder",
    
    # Configuration classes
    "SeedConfiguration",
    "DevelopmentSeedConfig",
    "TestingSeedConfig", 
    "StagingSeedConfig",
    "ProductionSeedConfig",
    
    # Data models
    "SeedExecutionResult",
    "SeedSummary",
    
    # Utility functions
    "seed_database",
    "get_seeding_status",
    "clear_sample_data",
    "seed_for_testing",
    "seed_for_development",
    "validate_seed_data",
    "get_seed_config",
    "get_seed_manager"
]