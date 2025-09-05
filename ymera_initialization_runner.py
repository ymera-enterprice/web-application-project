#!/usr/bin/env python3
"""
YMERA System Initialization Runner
Main entry point for initializing and running the YMERA system
"""

import asyncio
import sys
import os
import logging
import argparse
from pathlib import Path
from typing import Optional
import signal
import uvloop
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Configure basic logging before importing other modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(project_root / 'logs' / 'initialization.log')
    ]
)

logger = logging.getLogger(__name__)

def setup_environment():
    """Setup environment variables and configurations"""
    logger.info("Setting up environment...")
    
    # Create necessary directories
    directories = [
        'logs',
        'data',
        'cache',
        'temp',
        'backups',
        'migrations'
    ]
    
    for dir_name in directories:
        dir_path = project_root / dir_name
        dir_path.mkdir(exist_ok=True, parents=True)
        logger.debug(f"Created directory: {dir_path}")
    
    # Set default environment variables if not present
    default_env_vars = {
        'DATABASE_URL': 'postgresql://user:password@localhost:5432/ymera_db',
        'REDIS_URL': 'redis://localhost:6379/0',
        'SECRET_KEY': 'your-secret-key-here-change-in-production',
        'LOG_LEVEL': 'INFO',
        'ENVIRONMENT': 'development',
        'API_HOST': '0.0.0.0',
        'API_PORT': '8000',
        'OPENAI_API_KEY': 'your-openai-api-key',
        'ANTHROPIC_API_KEY': 'your-anthropic-api-key',
        'PINECONE_API_KEY': 'your-pinecone-api-key',
        'PINECONE_ENVIRONMENT': 'us-west1-gcp'
    }
    
    for key, default_value in default_env_vars.items():
        if not os.getenv(key):
            os.environ[key] = default_value
            logger.debug(f"Set default environment variable: {key}")
    
    logger.info("Environment setup completed")

def validate_dependencies():
    """Validate that all required dependencies are available"""
    logger.info("Validating dependencies...")
    
    required_packages = [
        'asyncio',
        'uvloop',
        'structlog',
        'psutil',
        'aiohttp',
        'sqlalchemy',
        'redis',
        'openai',
        'anthropic',
        'pinecone-client',
        'numpy',
        'pandas'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            logger.debug(f"✓ {package}")
        except ImportError:
            missing_packages.append(package)
            logger.error(f"✗ {package}")
    
    if missing_packages:
        logger.error(f"Missing required packages: {missing_packages}")
        logger.error("Please install them with: pip install " + " ".join(missing_packages))
        return False
    
    logger.info("All dependencies validated successfully")
    return True

async def create_system_initializer():
    """Create and configure the SystemInitializer"""
    try:
        # Import the SystemInitializer after environment setup
        from ymera_system_init import SystemInitializer, initialize_ymera
        
        logger.info("Creating system initializer...")
        
        # Initialize the system
        initializer = await initialize_ymera()
        
        logger.info("System initializer created successfully")
        return initializer
        
    except ImportError as e:
        logger.error(f"Failed to import SystemInitializer: {e}")
        logger.error("Make sure the ymera_system_init.py file is in the same directory")
        raise
    except Exception as e:
        logger.error(f"Failed to create system initializer: {e}")
        raise

class YMERARunner:
    """Main YMERA system runner"""
    
    def __init__(self):
        self.initializer: Optional[object] = None
        self.running = False
        self.shutdown_event = asyncio.Event()
    
    async def start(self):
        """Start the YMERA system"""
        try:
            logger.info("Starting YMERA system...")
            
            # Set up the event loop
            if sys.platform != 'win32':
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            
            # Create and initialize the system
            self.initializer = await create_system_initializer()
            
            # Set up signal handlers
            self._setup_signal_handlers()
            
            self.running = True
            logger.info("YMERA system started successfully")
            
            # Print system status
            await self._print_system_status()
            
            # Keep the system running
            await self._run_main_loop()
            
        except Exception as e:
            logger.error(f"Failed to start YMERA system: {e}")
            await self._emergency_shutdown()
            raise
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        if sys.platform != 'win32':
            def signal_handler(signum, frame):
                logger.info(f"Received signal {signum}, initiating shutdown...")
                asyncio.create_task(self.shutdown())
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        else:
            # Windows doesn't support SIGTERM, only handle SIGINT (Ctrl+C)
            def signal_handler(signum, frame):
                logger.info("Received interrupt signal, initiating shutdown...")
                asyncio.create_task(self.shutdown())
            
            signal.signal(signal.SIGINT, signal_handler)
    
    async def _print_system_status(self):
        """Print current system status"""
        if self.initializer:
            try:
                health_status = self.initializer.get_health_status()
                
                print("\n" + "="*60)
                print("🚀 YMERA SYSTEM STATUS")
                print("="*60)
                print(f"Overall Status: {health_status.get('overall_status', 'Unknown').upper()}")
                print(f"Startup Time: {health_status.get('startup_time', 0):.2f} seconds")
                print(f"Last Health Check: {health_status.get('last_check', 'Never')}")
                
                print("\n📊 COMPONENT STATUS:")
                components = health_status.get('components', {})
                for component, status in components.items():
                    status_emoji = "✅" if status.get('status') == 'healthy' else "❌"
                    print(f"  {status_emoji} {component.upper()}: {status.get('status', 'unknown')}")
                
                print("\n🖥️  SYSTEM METRICS:")
                metrics = health_status.get('system_metrics', {})
                if metrics:
                    print(f"  CPU Cores: {metrics.get('cpu_count', 'Unknown')}")
                    print(f"  Memory: {metrics.get('memory_total', 0) / (1024**3):.1f} GB")
                    print(f"  Python Version: {metrics.get('python_version', 'Unknown')}")
                
                print("\n🌐 API ENDPOINTS:")
                print(f"  Health Check: http://{os.getenv('API_HOST', 'localhost')}:{os.getenv('API_PORT', '8000')}/health")
                print(f"  API Documentation: http://{os.getenv('API_HOST', 'localhost')}:{os.getenv('API_PORT', '8000')}/docs")
                
                print("\n📝 LOGS:")
                print(f"  Log Directory: {project_root / 'logs'}")
                print(f"  Current Log Level: {os.getenv('LOG_LEVEL', 'INFO')}")
                
                print("="*60)
                print("System is running. Press Ctrl+C to shutdown gracefully.")
                print("="*60 + "\n")
                
            except Exception as e:
                logger.error(f"Failed to print system status: {e}")
    
    async def _run_main_loop(self):
        """Main system loop"""
        try:
            logger.info("Entering main system loop...")
            
            # Create background monitoring task
            monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            # Cancel monitoring task
            monitoring_task.cancel()
            
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            raise
    
    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Monitor every minute
                
                if self.initializer:
                    # Get current health status
                    health_status = self.initializer.get_health_status()
                    overall_status = health_status.get('overall_status')
                    
                    if overall_status == 'unhealthy':
                        logger.warning("System health is unhealthy!")
                        # Could implement automatic recovery here
                    
                    # Log periodic status
                    if datetime.now().minute % 15 == 0:  # Every 15 minutes
                        logger.info(f"System status check: {overall_status}")
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
    
    async def shutdown(self):
        """Gracefully shutdown the system"""
        if not self.running:
            return
        
        logger.info("Initiating system shutdown...")
        self.running = False
        
        try:
            if self.initializer:
                await self.initializer.graceful_shutdown()
            
            logger.info("System shutdown completed successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            self.shutdown_event.set()
    
    async def _emergency_shutdown(self):
        """Emergency shutdown in case of startup failure"""
        logger.error("Performing emergency shutdown...")
        
        try:
            if self.initializer:
                await self.initializer._cleanup_on_failure()
        except Exception as e:
            logger.error(f"Error during emergency shutdown: {e}")
        
        self.shutdown_event.set()

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='YMERA System Initialization Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_ymera.py                    # Start with default settings
  python run_ymera.py --validate-only    # Only validate dependencies
  python run_ymera.py --log-level DEBUG  # Start with debug logging
        """
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate dependencies and exit'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--config-file',
        type=Path,
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Perform initialization without starting services'
    )
    
    return parser.parse_args()

async def main():
    """Main function"""
    print("""
    ╔═══════════════════════════════════════╗
    ║           YMERA SYSTEM                ║
    ║        Initialization Runner          ║
    ║                                       ║
    ║    🤖 AI-Powered System Platform      ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    try:
        # Setup environment
        setup_environment()
        
        # Validate dependencies
        if not validate_dependencies():
            logger.error("Dependency validation failed")
            sys.exit(1)
        
        # If validate-only flag is set, exit after validation
        if args.validate_only:
            logger.info("Validation completed successfully. Exiting.")
            return
        
        # Load configuration file if provided
        if args.config_file and args.config_file.exists():
            logger.info(f"Loading configuration from: {args.config_file}")
            # Configuration loading logic would go here
        
        # Create and start the system runner
        runner = YMERARunner()
        
        if args.dry_run:
            logger.info("Dry run mode - system will not start services")
            # Perform initialization without starting services
            initializer = await create_system_initializer()
            health_status = initializer.get_health_status()
            logger.info(f"Dry run completed. System status: {health_status.get('overall_status')}")
            return
        
        # Start the system
        await runner.start()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("YMERA system runner exiting...")

if __name__ == "__main__":
    try:
        # Run the main function
        if sys.platform == 'win32':
            # Windows compatibility
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)