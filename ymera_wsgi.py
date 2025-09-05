"""
YMERA Enterprise - WSGI Configuration
Production-Ready WSGI Server Configuration - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

import logging
import multiprocessing
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Third-party imports
import gunicorn.app.base
import structlog
from gunicorn.config import Config
from gunicorn.workers.gthread import ThreadWorker

# Local imports
from main import app
from config.settings import get_settings

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.wsgi")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

settings = get_settings()

# ===============================================================================
# CUSTOM GUNICORN WORKER CLASS
# ===============================================================================

class YMERAWorker(ThreadWorker):
    """Custom Gunicorn worker optimized for YMERA platform"""
    
    def init_process(self):
        """Initialize worker process with proper logging and monitoring"""
        super().init_process()
        
        # Setup structured logging for worker
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        worker_logger = structlog.get_logger("ymera.worker")
        worker_logger.info(
            "YMERA worker process initialized",
            worker_pid=os.getpid(),
            worker_id=self.worker_id if hasattr(self, 'worker_id') else 'unknown'
        )
    
    def handle_request(self, listener, req, client, addr):
        """Handle request with enhanced monitoring and error handling"""
        try:
            return super().handle_request(listener, req, client, addr)
        except Exception as e:
            logger.error(
                "Worker request handling failed",
                error=str(e),
                client_addr=addr,
                worker_pid=os.getpid()
            )
            raise

# ===============================================================================
# GUNICORN APPLICATION CLASS
# ===============================================================================

class YMERAGunicornApp(gunicorn.app.base.BaseApplication):
    """Custom Gunicorn application for YMERA platform"""
    
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()
    
    def load_config(self):
        """Load Gunicorn configuration"""
        config = {
            # Server socket
            'bind': f"{settings.HOST}:{settings.PORT}",
            'backlog': 2048,
            
            # Worker processes
            'workers': self._calculate_workers(),
            'worker_class': 'wsgi:YMERAWorker',
            'worker_connections': 1000,
            'max_requests': 10000,
            'max_requests_jitter': 1000,
            'timeout': 120,
            'keepalive': 5,
            'preload_app': True,
            
            # Threading
            'threads': min(multiprocessing.cpu_count() * 2, 8),
            
            # Logging
            'accesslog': '-',
            'errorlog': '-',
            'loglevel': 'info',
            'access_log_format': (
                '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
                '"%(f)s" "%(a)s" %(D)s'
            ),
            
            # Process naming
            'proc_name': 'ymera-enterprise',
            
            # Security
            'limit_request_line': 8192,
            'limit_request_fields': 100,
            'limit_request_field_size': 8190,
            
            # Performance
            'sendfile': True,
            'reuse_port': True,
            
            # Monitoring and debugging
            'statsd_host': settings.STATSD_HOST if hasattr(settings, 'STATSD_HOST') else None,
            'statsd_prefix': 'ymera.gunicorn',
        }
        
        # SSL Configuration
        if settings.SSL_CERT_FILE and settings.SSL_KEY_FILE:
            config.update({
                'certfile': settings.SSL_CERT_FILE,
                'keyfile': settings.SSL_KEY_FILE,
                'ssl_version': 3,  # TLSv1.2+
                'ciphers': 'ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS',
                'do_handshake_on_connect': False,
            })
        
        # Development vs Production configuration
        if settings.ENVIRONMENT == "development":
            config.update({
                'reload': True,
                'reload_engine': 'poll',
                'loglevel': 'debug',
            })
        elif settings.ENVIRONMENT == "production":
            config.update({
                'preload_app': True,
                'worker_tmp_dir': '/dev/shm',  # Use memory for worker temp files
                'forwarded_allow_ips': '*',
                'proxy_allow_ips': '*',
            })
        
        # Apply custom options
        config.update(self.options)
        
        for key, value in config.items():
            if value is not None:
                self.cfg.set(key.lower(), value)
    
    def load(self):
        """Load the WSGI application"""
        return self.application
    
    def _calculate_workers(self) -> int:
        """Calculate optimal number of worker processes"""
        cpu_count = multiprocessing.cpu_count()
        
        if settings.ENVIRONMENT == "development":
            return 1
        elif settings.ENVIRONMENT == "testing":
            return 2
        else:
            # Production: 2-4 workers per CPU core, but cap at reasonable number
            workers = min(cpu_count * 2 + 1, 16)
            
            # Adjust based on available memory (assume 512MB per worker minimum)
            try:
                import psutil
                available_memory_gb = psutil.virtual_memory().available / (1024**3)
                memory_workers = int(available_memory_gb / 0.5)  # 512MB per worker
                workers = min(workers, memory_workers)
            except ImportError:
                logger.warning("psutil not available, using CPU-based worker calculation")
            
            return max(workers, 2)  # Minimum 2 workers in production

# ===============================================================================
# GUNICORN HOOKS
# ===============================================================================

def on_starting(server):
    """Called just before the master process is initialized"""
    logger.info(
        "YMERA Gunicorn server starting",
        environment=settings.ENVIRONMENT,
        bind_address=f"{settings.HOST}:{settings.PORT}",
        workers=server.cfg.workers,
        threads=server.cfg.threads
    )

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP"""
    logger.info("YMERA Gunicorn server reloading")

def when_ready(server):
    """Called just after the server is started"""
    logger.info(
        "YMERA Gunicorn server ready to accept connections",
        master_pid=os.getpid(),
        worker_count=server.cfg.workers
    )

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT"""
    logger.info(
        "YMERA worker received INT or QUIT signal",
        worker_pid=worker.pid,
        worker_age=worker.age
    )

def pre_fork(server, worker):
    """Called just before a worker is forked"""
    logger.debug(
        "YMERA worker about to be forked",
        worker_id=worker.id,
        master_pid=os.getpid()
    )

def post_fork(server, worker):
    """Called just after a worker has been forked"""
    logger.info(
        "YMERA worker forked successfully",
        worker_pid=os.getpid(),
        worker_id=worker.id,
        master_pid=server.pid
    )

def post_worker_init(worker):
    """Called just after a worker has initialized the application"""
    logger.info(
        "YMERA worker initialized application",
        worker_pid=os.getpid(),
        worker_id=worker.id
    )

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal"""
    logger.error(
        "YMERA worker aborted",
        worker_pid=worker.pid,
        worker_id=worker.id
    )

def pre_exec(server):
    """Called just before a new master process is forked"""
    logger.info("YMERA server pre-exec hook called")

def pre_request(worker, req):
    """Called just before a worker processes the request"""
    worker.log.debug(
        f"Processing request: {req.method} {req.path}",
        extra={
            "worker_id": worker.id,
            "request_method": req.method,
            "request_path": req.path
        }
    )

def post_request(worker, req, environ, resp):
    """Called after a request has been processed"""
    worker.log.info(
        f"Request completed: {req.method} {req.path} - {resp.status}",
        extra={
            "worker_id": worker.id,
            "request_method": req.method,
            "request_path": req.path,
            "response_status": resp.status,
            "response_length": getattr(resp, 'response_length', 0)
        }
    )

def child_exit(server, worker):
    """Called just after a worker has been reaped"""
    logger.info(
        "YMERA worker process exited",
        worker_pid=worker.pid,
        worker_id=worker.id,
        exit_code=worker.exitcode
    )

def worker_exit(server, worker):
    """Called just after a worker has been reaped"""
    logger.info(
        "YMERA worker exiting",
        worker_pid=worker.pid,
        worker_id=worker.id
    )

def nworkers_changed(server, new_value, old_value):
    """Called just after num_workers has been changed"""
    logger.info(
        "YMERA worker count changed",
        old_workers=old_value,
        new_workers=new_value
    )

def on_exit(server):
    """Called just before exiting"""
    logger.info("YMERA Gunicorn server shutting down")

# ===============================================================================
# WSGI APPLICATION FACTORY
# ===============================================================================

def create_wsgi_app():
    """Create WSGI application with proper configuration"""
    
    # Environment-specific options
    options = {}
    
    if settings.ENVIRONMENT == "production":
        options.update({
            'preload_app': True,
            'worker_tmp_dir': '/dev/shm',
            'max_requests': 10000,
            'max_requests_jitter': 1000,
        })
    
    return YMERAGunicornApp(app, options)

# ===============================================================================
# MAIN ENTRY POINT
# ===============================================================================

def main():
    """Main entry point for WSGI server"""
    try:
        logger.info(
            "Starting YMERA Enterprise Platform via WSGI",
            environment=settings.ENVIRONMENT,
            python_version=sys.version,
            gunicorn_version=gunicorn.__version__
        )
        
        wsgi_app = create_wsgi_app()
        wsgi_app.run()
        
    except Exception as e:
        logger.critical(
            "Failed to start YMERA WSGI server",
            error=str(e),
            traceback=traceback.format_exc()
        )
        sys.exit(1)

# ===============================================================================
# MODULE EXPORTS
# ===============================================================================

# For direct WSGI server imports
application = app

# Gunicorn hooks - these are automatically discovered by Gunicorn
__all__ = [
    'application',
    'on_starting',
    'on_reload', 
    'when_ready',
    'worker_int',
    'pre_fork',
    'post_fork',
    'post_worker_init',
    'worker_abort',
    'pre_exec',
    'pre_request',
    'post_request',
    'child_exit',
    'worker_exit',
    'nworkers_changed',
    'on_exit',
    'YMERAGunicornApp',
    'create_wsgi_app'
]

if __name__ == "__main__":
    main()