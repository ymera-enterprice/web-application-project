'confidence': min(len(collab_experiences) / 20, 1.0)
                })
        
        return meta_patterns

    async def _apply_meta_pattern(self, pattern: Dict[str, Any]):
        """Apply discovered meta-pattern to improve system"""
        try:
            if pattern['type'] == 'complexity_success_pattern':
                await self._adjust_complexity_handling(pattern)
            elif pattern['type'] == 'collaboration_benefit':
                await self._enhance_collaboration_mechanisms(pattern)
            
            logger.info("Meta-pattern applied",
                       pattern_type=pattern['type'])
                       
        except Exception as e:
            logger.error("Failed to apply meta-pattern",
                        pattern_type=pattern.get('type', 'unknown'),
                        error=str(e))

    async def _adjust_complexity_handling(self, pattern: Dict[str, Any]):
        """Adjust system complexity handling based on meta-pattern"""
        complexity_level = pattern['complexity_level']
        success_rate = pattern['success_rate']
        
        # Adjust agent assignment strategies based on complexity patterns
        if complexity_level == 'high' and success_rate < 0.5:
            # High complexity tasks have low success - need better assignment
            for agent in self.agents.values():
                if hasattr(agent, 'complexity_threshold'):
                    agent.complexity_threshold = max(agent.complexity_threshold - 0.1, 0.3)
        
        elif complexity_level == 'low' and success_rate > 0.9:
            # Low complexity tasks very successful - can handle more complexity
            for agent in self.agents.values():
                if hasattr(agent, 'complexity_threshold'):
                    agent.complexity_threshold = min(agent.complexity_threshold + 0.05, 0.9)

    async def _enhance_collaboration_mechanisms(self, pattern: Dict[str, Any]):
        """Enhance collaboration based on discovered benefits"""
        collaboration_advantage = pattern['collaboration_advantage']
        
        if collaboration_advantage > 0.2:  # Significant benefit
            # Increase collaboration probability
            for agent in self.agents.values():
                if hasattr(agent, 'collaboration_preference'):
                    agent.collaboration_preference = min(
                        agent.collaboration_preference + 0.1, 0.9
                    )
            
            # Update inter-agent learning config
            self.inter_agent_system.learning_config['consensus_threshold'] *= 0.95  # Make consensus easier

    async def _consolidate_knowledge(self):
        """Consolidate and compress knowledge across the system"""
        try:
            consolidation_tasks = []
            
            for agent in self.agents.values():
                if agent.state == AgentState.ACTIVE:
                    consolidation_tasks.append(self._consolidate_agent_knowledge(agent))
            
            if consolidation_tasks:
                await asyncio.gather(*consolidation_tasks, return_exceptions=True)
                
            self.global_learning_state['knowledge_graph_updates'] += len(consolidation_tasks)
            
        except Exception as e:
            logger.error("Knowledge consolidation failed", error=str(e))

    async def _consolidate_agent_knowledge(self, agent: 'EnhancedAgent'):
        """Consolidate knowledge for individual agent"""
        try:
            # Get agent's knowledge graph
            knowledge_items = await agent.knowledge_graph.get_all_knowledge()
            
            if len(knowledge_items) > 1000:  # Need consolidation
                # Identify redundant or outdated knowledge
                outdated_items = []
                current_time = datetime.now()
                
                for item_id, item_data in knowledge_items.items():
                    if 'timestamp' in item_data:
                        item_time = datetime.fromisoformat(item_data['timestamp'])
                        age_days = (current_time - item_time).days
                        
                        # Remove very old items with low relevance
                        if age_days > 30 and item_data.get('relevance_score', 0) < 0.3:
                            outdated_items.append(item_id)
                
                # Remove outdated items
                for item_id in outdated_items[:100]:  # Limit removals
                    await agent.knowledge_graph.remove_knowledge(item_id)
                
                logger.info("Agent knowledge consolidated",
                           agent_id=agent.agent_id,
                           items_removed=len(outdated_items[:100]))
                           
        except Exception as e:
            logger.error("Agent knowledge consolidation failed",
                        agent_id=agent.agent_id,
                        error=str(e))

    async def _facilitate_knowledge_sharing(self):
        """Facilitate cross-agent knowledge sharing"""
        try:
            sharing_opportunities = []
            
            # Find agents with complementary knowledge
            for agent1 in self.agents.values():
                for agent2 in self.agents.values():
                    if (agent1.agent_id != agent2.agent_id and 
                        self._should_facilitate_sharing(agent1, agent2)):
                        sharing_opportunities.append((agent1, agent2))
            
            # Execute knowledge sharing
            for source_agent, target_agent in sharing_opportunities[:5]:  # Limit concurrent sharing
                await self._execute_knowledge_transfer(source_agent, target_agent)
            
            if sharing_opportunities:
                logger.info("Knowledge sharing facilitated",
                           transfers=len(sharing_opportunities[:5]))
                           
        except Exception as e:
            logger.error("Knowledge sharing facilitation failed", error=str(e))

    def _should_facilitate_sharing(self, agent1: 'EnhancedAgent', 
                                 agent2: 'EnhancedAgent') -> bool:
        """Determine if knowledge sharing should be facilitated"""
        # Share if performance gap exists
        performance_gap = agent1.metrics.success_rate - agent2.metrics.success_rate
        
        if performance_gap > 0.15:  # Significant performance difference
            return True
        
        # Share if complementary specializations
        skill_complement = len(agent1.specialized_skills - agent2.specialized_skills)
        if skill_complement > 2:
            return True
        
        return False

    async def _execute_knowledge_transfer(self, source_agent: 'EnhancedAgent', 
                                        target_agent: 'EnhancedAgent'):
        """Execute knowledge transfer between agents"""
        try:
            # Get high-value knowledge from source
            source_knowledge = await source_agent.knowledge_graph.get_top_knowledge(
                limit=5, 
                sort_by='relevance_score'
            )
            
            # Create transfer experiences
            for knowledge_item in source_knowledge:
                transfer_experience = Experience(
                    experience_id=str(uuid.uuid4()),
                    agent_id=source_agent.agent_id,
                    task_type="knowledge_transfer",
                    input_data={'knowledge_item': knowledge_item},
                    output_data={'transfer_target': target_agent.agent_id},
                    feedback_score=0.8,
                    execution_time=0.5,
                    timestamp=datetime.now(),
                    context={'transfer_type': 'direct_knowledge'},
                    success=True,
                    learned_patterns=[f"knowledge_sharing_{source_agent.agent_type.value}"],
                    confidence_score=0.75,
                    memory_type=MemoryType.SEMANTIC
                )
                
                await self.inter_agent_system.share_experience(
                    source_agent.agent_id,
                    transfer_experience,
                    [target_agent.agent_id]
                )
                
        except Exception as e:
            logger.error("Knowledge transfer failed",
                        source_agent=source_agent.agent_id,
                        target_agent=target_agent.agent_id,
                        error=str(e))

    async def stop_continual_learning(self):
        """Stop the continual learning loop"""
        if self.learning_scheduler:
            self.learning_scheduler.cancel()
            self.learning_scheduler = None
            logger.info("Continual learning loop stopped")

    def get_learning_metrics(self) -> Dict[str, Any]:
        """Get comprehensive learning metrics"""
        return {
            'global_state': self.global_learning_state,
            'learning_metrics': self.learning_metrics,
            'inter_agent_metrics': self.inter_agent_system.collaboration_metrics,
            'active_agents': len([a for a in self.agents.values() if a.state == AgentState.ACTIVE]),
            'learning_efficiency': self._calculate_learning_efficiency()
        }

    def _calculate_learning_efficiency(self) -> float:
        """Calculate overall learning efficiency"""
        total_experiences = self.global_learning_state['total_experiences_processed']
        if total_experiences == 0:
            return 0.0
        
        improvements = self.learning_metrics['agents_improved']
        transfers = self.learning_metrics['knowledge_transfers']
        patterns = self.learning_metrics['meta_patterns_discovered']
        
        efficiency = (improvements + transfers * 0.5 + patterns * 2) / total_experiences
        return min(efficiency, 1.0)


class EnhancedAgentOrchestrator:
    """Advanced orchestrator managing the complete enhanced agent ecosystem"""
    
    def __init__(self, redis_client=None, config: Dict[str, Any] = None):
        self.redis_client = redis_client
        self.config = config or self._default_config()
        
        # Core systems
        self.agents: Dict[str, 'EnhancedAgent'] = {}
        self.task_queue = asyncio.Queue()
        self.adaptive_scheduler = AdaptiveScheduler()
        self.inter_agent_system = InterAgentLearningSystem(redis_client)
        self.continual_learning = None
        
        # Orchestrator state
        self.orchestrator_state = OrchestrationState.INITIALIZING
        self.system_health = SystemHealth()
        self.global_metrics = GlobalMetrics()
        
        # Monitoring and control
        self.monitoring_tasks = []
        self.shutdown_event = asyncio.Event()
        self.emergency_stop = False
        
        # Advanced features
        self.auto_scaling_enabled = True
        self.load_balancing_enabled = True
        self.fault_tolerance_enabled = True
        
        logger.info("Enhanced Agent Orchestrator initialized")

    def _default_config(self) -> Dict[str, Any]:
        """Default orchestrator configuration"""
        return {
            'max_agents': 50,
            'min_agents': 2,
            'auto_scaling': {
                'enabled': True,
                'scale_up_threshold': 0.8,
                'scale_down_threshold': 0.3,
                'cooldown_period': 300
            },
            'health_monitoring': {
                'enabled': True,
                'check_interval': 30,
                'unhealthy_threshold': 3,
                'recovery_timeout': 120
            },
            'load_balancing': {
                'algorithm': 'adaptive_weighted',
                'rebalance_interval': 60,
                'imbalance_threshold': 0.3
            },
            'fault_tolerance': {
                'max_retries': 3,
                'retry_delay': 5,
                'circuit_breaker_enabled': True,
                'recovery_strategy': 'gradual'
            }
        }

    async def initialize_system(self, initial_agents: List[Dict[str, Any]] = None):
        """Initialize the complete agent system"""
        try:
            self.orchestrator_state = OrchestrationState.INITIALIZING
            
            # Initialize core systems
            await self.adaptive_scheduler.initialize()
            
            # Create initial agents
            if initial_agents:
                for agent_config in initial_agents:
                    await self.create_agent(agent_config)
            else:
                # Create default agents
                await self._create_default_agents()
            
            # Initialize continual learning
            self.continual_learning = ContinualLearningLoop(
                list(self.agents.values()),
                self.inter_agent_system
            )
            
            # Start monitoring systems
            await self._start_monitoring_systems()
            
            # Start continual learning
            await self.continual_learning.start_continual_learning()
            
            self.orchestrator_state = OrchestrationState.ACTIVE
            logger.info("Agent system fully initialized",
                       agent_count=len(self.agents))
                       
        except Exception as e:
            self.orchestrator_state = OrchestrationState.ERROR
            logger.error("System initialization failed", error=str(e))
            raise

    async def _create_default_agents(self):
        """Create default set of agents"""
        default_configs = [
            {
                'agent_type': 'task_executor',
                'specialization': ['general_processing', 'data_analysis'],
                'resource_limits': {'max_memory': 512, 'max_cpu': 2}
            },
            {
                'agent_type': 'coordinator',
                'specialization': ['task_coordination', 'workflow_management'],
                'resource_limits': {'max_memory': 256, 'max_cpu': 1}
            }
        ]
        
        for config in default_configs:
            await self.create_agent(config)

    async def create_agent(self, config: Dict[str, Any]) -> str:
        """Create and register a new enhanced agent"""
        try:
            # Generate agent ID
            agent_id = f"agent_{len(self.agents)}_{int(time.time())}"
            
            # Create enhanced agent (this would be imported from the enhanced agent module)
            # For now, we'll create a placeholder
            from enhanced_agent import EnhancedAgent  # This would be the actual import
            
            agent = EnhancedAgent(
                agent_id=agent_id,
                redis_client=self.redis_client,
                config=config
            )
            
            # Initialize agent
            await agent.initialize()
            
            # Register with systems
            self.agents[agent_id] = agent
            await self.adaptive_scheduler.register_agent(agent)
            
            # Update metrics
            self.global_metrics.total_agents_created += 1
            self.global_metrics.active_agents += 1
            
            logger.info("Agent created and registered",
                       agent_id=agent_id,
                       agent_type=config.get('agent_type', 'unknown'))
            
            return agent_id
            
        except Exception as e:
            logger.error("Agent creation failed",
                        config=config,
                        error=str(e))
            raise

    async def submit_task(self, task_data: Dict[str, Any]) -> str:
        """Submit task to the system"""
        try:
            # Create task object
            task = Task(
                task_id=str(uuid.uuid4()),
                task_type=task_data.get('type', 'general'),
                priority=TaskPriority(task_data.get('priority', 'medium')),
                requirements=task_data.get('requirements', {}),
                input_data=task_data.get('input_data', {}),
                constraints=task_data.get('constraints', {}),
                deadline=task_data.get('deadline'),
                created_at=datetime.now()
            )
            
            # Add to queue
            await self.task_queue.put(task)
            
            # Update metrics
            self.global_metrics.total_tasks_submitted += 1
            
            logger.info("Task submitted",
                       task_id=task.task_id,
                       task_type=task.task_type)
            
            return task.task_id
            
        except Exception as e:
            logger.error("Task submission failed",
                        task_data=task_data,
                        error=str(e))
            raise

    async def _start_monitoring_systems(self):
        """Start all monitoring systems"""
        if self.config['health_monitoring']['enabled']:
            self.monitoring_tasks.append(
                asyncio.create_task(self._health_monitoring_loop())
            )
        
        if self.config['auto_scaling']['enabled']:
            self.monitoring_tasks.append(
                asyncio.create_task(self._auto_scaling_loop())
            )
        
        if self.config['load_balancing']['enabled']:
            self.monitoring_tasks.append(
                asyncio.create_task(self._load_balancing_loop())
            )
        
        # Task processing loop
        self.monitoring_tasks.append(
            asyncio.create_task(self._task_processing_loop())
        )
        
        logger.info("Monitoring systems started",
                   active_monitors=len(self.monitoring_tasks))

    async def _health_monitoring_loop(self):
        """Monitor system and agent health"""
        while not self.shutdown_event.is_set():
            try:
                # Check agent health
                unhealthy_agents = []
                
                for agent_id, agent in self.agents.items():
                    health_status = await agent.get_health_status()
                    
                    if not health_status.get('healthy', True):
                        unhealthy_agents.append(agent_id)
                        self.system_health.unhealthy_agents.add(agent_id)
                    else:
                        self.system_health.unhealthy_agents.discard(agent_id)
                
                # Handle unhealthy agents
                for agent_id in unhealthy_agents:
                    await self._handle_unhealthy_agent(agent_id)
                
                # Update system health
                self.system_health.last_health_check = datetime.now()
                self.system_health.overall_health = len(unhealthy_agents) == 0
                
                await asyncio.sleep(self.config['health_monitoring']['check_interval'])
                
            except Exception as e:
                logger.error("Health monitoring error", error=str(e))
                await asyncio.sleep(30)

    async def _handle_unhealthy_agent(self, agent_id: str):
        """Handle unhealthy agent"""
        try:
            agent = self.agents.get(agent_id)
            if not agent:
                return
            
            # Attempt recovery
            logger.warning("Attempting agent recovery", agent_id=agent_id)
            
            recovery_success = await agent.attempt_recovery()
            
            if recovery_success:
                logger.info("Agent recovery successful", agent_id=agent_id)
                self.system_health.unhealthy_agents.discard(agent_id)
            else:
                # Consider agent replacement
                logger.error("Agent recovery failed, considering replacement", 
                           agent_id=agent_id)
                
                if self.fault_tolerance_enabled:
                    await self._replace_agent(agent_id)
                    
        except Exception as e:
            logger.error("Agent recovery handling failed",
                        agent_id=agent_id,
                        error=str(e))

    async def _replace_agent(self, failed_agent_id: str):
        """Replace a failed agent"""
        try:
            failed_agent = self.agents.get(failed_agent_id)
            if not failed_agent:
                return
            
            # Create replacement with same configuration
            replacement_config = {
                'agent_type': failed_agent.agent_type.value,
                'specialization': list(failed_agent.specialized_skills),
                'resource_limits': failed_agent.resource_limits
            }
            
            # Create new agent
            new_agent_id = await self.create_agent(replacement_config)
            
            # Remove failed agent
            await self.remove_agent(failed_agent_id)
            
            logger.info("Agent replaced",
                       failed_agent=failed_agent_id,
                       replacement_agent=new_agent_id)
                       
        except Exception as e:
            logger.error("Agent replacement failed",
                        failed_agent_id=failed_agent_id,
                        error=str(e))

    async def _auto_scaling_loop(self):
        """Handle automatic scaling based on load"""
        while not self.shutdown_event.is_set():
            try:
                # Calculate current load
                current_load = await self._calculate_system_load()
                
                # Check scaling conditions
                if (current_load > self.config['auto_scaling']['scale_up_threshold'] and
                    len(self.agents) < self.config['max_agents']):
                    await self._scale_up()
                    
                elif (current_load < self.config['auto_scaling']['scale_down_threshold'] and
                      len(self.agents) > self.config['min_agents']):
                    await self._scale_down()
                
                await asyncio.sleep(self.config['auto_scaling']['cooldown_period'])
                
            except Exception as e:
                logger.error("Auto-scaling error", error=str(e))
                await asyncio.sleep(60)

    async def _calculate_system_load(self) -> float:
        """Calculate current system load"""
        if not self.agents:
            return 0.0
        
        total_workload = sum(
            self.adaptive_scheduler.agent_workloads.get(agent_id, 0)
            for agent_id in self.agents.keys()
        )
        
        max_capacity = len(self.agents) * 10  # Assume each agent can handle 10 tasks
        return min(total_workload / max_capacity, 1.0) if max_capacity > 0 else 0.0

    async def _scale_up(self):
        """Scale up the system by adding agents"""
        try:
            # Determine what type of agent to create based on current needs
            new_agent_config = {
                'agent_type': 'task_executor',
                'specialization': ['general_processing'],
                'resource_limits': {'max_memory': 512, 'max_cpu': 2}
            }
            
            new_agent_id = await self.create_agent(new_agent_config)
            logger.info("System scaled up", new_agent_id=new_agent_id)
            
        except Exception as e:
            logger.error("Scale up failed", error=str(e))

    async def _scale_down(self):
        """Scale down the system by removing agents"""
        try:
            # Find least utilized agent
            min_workload = float('inf')
            target_agent_id = None
            
            for agent_id in self.agents.keys():
                workload = self.adaptive_scheduler.agent_workloads.get(agent_id, 0)
                if workload < min_workload:
                    min_workload = workload
                    target_agent_id = agent_id
            
            if target_agent_id and min_workload == 0:  # Only remove idle agents
                await self.remove_agent(target_agent_id)
                logger.info("System scaled down", removed_agent=target_agent_id)
                
        except Exception as e:
            logger.error("Scale down failed", error=str(e))

    async def _load_balancing_loop(self):
        """Handle load balancing across agents"""
        while not self.shutdown_event.is_set():
            try:
                await self._rebalance_workload()
                await asyncio.sleep(self.config['load_balancing']['rebalance_interval'])
                
            except Exception as e:
                logger.error("Load balancing error", error=str(e))
                await asyncio.sleep(60)

    async def _rebalance_workload(self):
        """Rebalance workload across agents"""
        if len(self.agents) < 2:
            return
        
        workloads = {
            agent_id: self.adaptive_scheduler.agent_workloads.get(agent_id, 0)
            for agent_id in self.agents.keys()
        }
        
        if not workloads:
            return
        
        avg_workload = sum(workloads.values()) / len(workloads)
        max_workload = max(workloads.values())
        min_workload = min(workloads.values())
        
        # Check if rebalancing is needed
        imbalance = (max_workload - min_workload) / (avg_workload + 1)
        
        if imbalance > self.config['load_balancing']['imbalance_threshold']:
            logger.info("Workload imbalance detected, rebalancing",
                       imbalance=imbalance)
            
            # This would implement actual task migration
            # For now, we just update the scheduler's algorithm
            await self.adaptive_scheduler.optimize_algorithm()

    async def _task_processing_loop(self):
        """Main task processing loop"""
        while not self.shutdown_event.is_set():
            try:
                # Get task from queue
                task = await asyncio.wait_for(
                    self.task_queue.get(), 
                    timeout=1.0
                )
                
                # Assign task
                await self.adaptive_scheduler.assign_task(task, list(self.agents.values()))
                
                # Update metrics
                self.global_metrics.total_tasks_processed += 1
                
            except asyncio.TimeoutError:
                continue  # No tasks available
            except Exception as e:
                logger.error("Task processing error", error=str(e))

    async def remove_agent(self, agent_id: str):
        """Remove agent from the system"""
        try:
            agent = self.agents.get(agent_id)
            if not agent:
                logger.warning("Agent not found for removal", agent_id=agent_id)
                return
            
            # Shutdown agent
            await agent.shutdown()
            
            # Remove from systems
            await self.adaptive_scheduler.unregister_agent(agent_id)
            del self.agents[agent_id]
            
            # Update metrics
            self.global_metrics.active_agents -= 1
            
            logger.info("Agent removed", agent_id=agent_id)
            
        except Exception as e:
            logger.error("Agent removal failed",
                        agent_id=agent_id,
                        error=str(e))

    async def emergency_shutdown(self):
        """Emergency shutdown of entire system"""
        logger.warning("Emergency shutdown initiated")
        self.emergency_stop = True
        self.orchestrator_state = OrchestrationState.EMERGENCY_STOP
        
        # Stop all monitoring
        for task in self.monitoring_tasks:
            task.cancel()
        
        # Stop continual learning
        if self.continual_learning:
            await self.continual_learning.stop_continual_learning()
        
        # Shutdown all agents
        shutdown_tasks = [
            agent.shutdown() for agent in self.agents.values()
        ]
        
        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        self.shutdown_event.set()
        logger.info("Emergency shutdown completed")

    async def graceful_shutdown(self):
        """Graceful shutdown of the system"""
        logger.info("Graceful shutdown initiated")
        self.orchestrator_state = OrchestrationState.SHUTTING_DOWN
        
        # Stop accepting new tasks
        # Process remaining tasks
        remaining_tasks = self.task_queue.qsize()
        if remaining_tasks > 0:
            logger.info(f"Processing {remaining_tasks} remaining tasks")
            
            # Wait for tasks to complete (with timeout)
            await asyncio.sleep(min(remaining_tasks * 2, 30))
        
        # Stop monitoring systems
        for task in self.monitoring_tasks:
            task.cancel()
        
        # Stop continual learning
        if self.continual_learning:
            await self.continual_learning.stop_continual_learning()
        
        # Gracefully shutdown agents
        for agent in self.agents.values():
            await agent.graceful_shutdown()
        
        self.shutdown_event.set()
        self.orchestrator_state = OrchestrationState.SHUTDOWN
        logger.info("Graceful shutdown completed")

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            'orchestrator_state': self.orchestrator_state.value,
            'total_agents': len(self.agents),
            'active_agents': len([a for a in self.agents.values() 
                                if a.state == AgentState.ACTIVE]),
            'system_health': {
                'overall_healthy': self.system_health.overall_health,
                'unhealthy_agents': len(self.system_health.unhealthy_agents),
                'last_health_check': self.system_health.last_health_check.isoformat() 
                                   if self.system_health.last_health_check else None
            },
            'global_metrics': asdict(self.global_metrics),
            'scheduling_stats': self.adaptive_scheduler.get_scheduling_stats(),
            'learning_metrics': self.continual_learning.get_learning_metrics() 
                              if self.continual_learning else {},
            'queue_size': self.task_queue.qsize(),
            'emergency_stop': self.emergency_stop
        }


# Data classes for system state management
@dataclass
class SystemHealth:
    overall_health: bool = True
    unhealthy_agents: set = field(default_factory=set)
    last_health_check: Optional[datetime] = None
    critical_issues: List[str] = field(default_factory=list)


@dataclass  
class GlobalMetrics:
    total_agents_created: int = 0
    active_agents: int = 0
    total_tasks_submitted: int = 0
    total_tasks_processed: int = 0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    system_uptime_start: datetime = field(default_factory=datetime.now)
    
    def get_success_rate(self) -> float:
        if self.total_tasks_processed == 0:
            return 0.0
        return self.total_tasks_completed / self.total_tasks_processed
    
    def get_uptime_seconds(self) -> float:
        return (datetime.now() - self.system_uptime_start).total_seconds()


class OrchestrationState(Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    SCALING = "scaling"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"
    ERROR = "error" 
    EMERGENCY_STOP = "emergency_stop"