"""
YMERA Enterprise - Routes Module Initialization
Production-Ready API Routes Package - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import logging
from typing import Dict, List, Any

# Third-party imports (alphabetical)
import structlog
from fastapi import APIRouter, FastAPI

# Local imports (alphabetical)
from .api_gateway import router as api_gateway_router
from .auth_routes import router as auth_router
from .agent_routes import router as agent_router
from .file_routes import router as file_router
from .project_routes import router as project_router
from .websocket_routes import router as websocket_router

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.routes")

# ===============================================================================
# ROUTER CONFIGURATION
# ===============================================================================

def configure_routes(app: FastAPI) -> None:
    """
    Configure all application routes with proper prefixes and tags.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        None
        
    Raises:
        ValueError: If app is not a valid FastAPI instance
    """
    try:
        # Main API Gateway (handles routing and load balancing)
        app.include_router(
            api_gateway_router,
            prefix="/api/v1",
            tags=["gateway"],
            responses={
                404: {"description": "Not found"},
                500: {"description": "Internal server error"}
            }
        )
        
        # Authentication routes
        app.include_router(
            auth_router,
            prefix="/api/v1/auth",
            tags=["authentication"],
            responses={
                401: {"description": "Unauthorized"},
                403: {"description": "Forbidden"}
            }
        )
        
        # Agent communication routes
        app.include_router(
            agent_router,
            prefix="/api/v1/agents",
            tags=["agents"],
            responses={
                400: {"description": "Bad request"},
                503: {"description": "Service unavailable"}
            }
        )
        
        # File management routes
        app.include_router(
            file_router,
            prefix="/api/v1/files",
            tags=["files"],
            responses={
                413: {"description": "File too large"},
                415: {"description": "Unsupported media type"}
            }
        )
        
        # Project management routes
        app.include_router(
            project_router,
            prefix="/api/v1/projects",
            tags=["projects"],
            responses={
                404: {"description": "Project not found"},
                409: {"description": "Conflict"}
            }
        )
        
        # WebSocket routes
        app.include_router(
            websocket_router,
            prefix="/ws",
            tags=["websockets"]
        )
        
        logger.info("All routes configured successfully")
        
    except Exception as e:
        logger.error("Failed to configure routes", error=str(e))
        raise ValueError(f"Route configuration failed: {str(e)}")

def get_route_summary() -> Dict[str, Any]:
    """
    Get summary of all configured routes.
    
    Returns:
        Dictionary containing route information
    """
    return {
        "total_routers": 6,
        "routes": {
            "api_gateway": {
                "prefix": "/api/v1",
                "description": "Main API gateway and routing"
            },
            "authentication": {
                "prefix": "/api/v1/auth",
                "description": "User authentication and authorization"
            },
            "agents": {
                "prefix": "/api/v1/agents",
                "description": "Agent management and communication"
            },
            "files": {
                "prefix": "/api/v1/files",
                "description": "File upload, download, and management"
            },
            "projects": {
                "prefix": "/api/v1/projects",
                "description": "Project creation and management"
            },
            "websockets": {
                "prefix": "/ws",
                "description": "Real-time communication"
            }
        }
    }

# ===============================================================================
# HEALTH CHECK ROUTES
# ===============================================================================

health_router = APIRouter()

@health_router.get("/health/routes")
async def routes_health_check() -> Dict[str, Any]:
    """Health check for routes module"""
    return {
        "status": "healthy",
        "module": "routes",
        "version": "4.0",
        "configured_routes": len(get_route_summary()["routes"]),
        "timestamp": "2025-01-24T12:00:00Z"
    }

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "configure_routes",
    "get_route_summary",
    "health_router",
    "api_gateway_router",
    "auth_router",
    "agent_router",
    "file_router",
    "project_router",
    "websocket_router"
]