from fastapi import FastAPI, Request
# restart trigger: updated timestamp
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware
from sqlmodel import select
import os

from app.core.config import get_settings
from app.core.database import lifespan
from app.api.routes import auth as auth_routes
from app.api.routes import users as users_routes
from app.api.routes import projects as projects_routes
from app.api.routes import tasks as tasks_routes
from app.models.user import User

settings = get_settings()

# Disable default API docs - we'll add custom protected ones
app = FastAPI(
    title=settings.app_name, 
    debug=settings.debug, 
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# GZip compression for faster page loads (compresses responses > 500 bytes)
app.add_middleware(GZipMiddleware, minimum_size=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Workspace injection middleware - adds workspace to all requests
# MUST be added BEFORE SessionMiddleware so it runs AFTER (middleware order is reversed)
from starlette.middleware.base import BaseHTTPMiddleware

class WorkspaceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip workspace lookup for static files, health checks, and API calls
        path = request.url.path
        if path.startswith('/static') or path.startswith('/uploads') or path == '/health' or path.startswith('/api/'):
            return await call_next(request)
        
        user_id = None
        
        # Safely check for session
        try:
            if "session" in request.scope:
                user_id = request.scope["session"].get('user_id')
        except Exception:
            pass
        
        if user_id:
            try:
                from app.core.database import get_session
                from app.models.workspace import Workspace
                async for db in get_session():
                    user = (await db.execute(
                        select(User).where(User.id == user_id)
                    )).scalar_one_or_none()
                    
                    if user and user.workspace_id:
                        workspace = (await db.execute(
                            select(Workspace).where(Workspace.id == user.workspace_id)
                        )).scalar_one_or_none()
                        
                        if workspace:
                            request.state.workspace = workspace
                    break
            except Exception:
                pass
        
        response = await call_next(request)
        return response

app.add_middleware(WorkspaceMiddleware)

# Cache control middleware for static assets
class CacheControlMiddleware(BaseHTTPMiddleware):
    """Add cache headers to static files for better performance"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        # Cache uploaded files (images, attachments) for 1 day
        if path.startswith('/uploads'):
            response.headers['Cache-Control'] = 'public, max-age=86400'
        # Cache static assets (JS, CSS, icons, manifest) for 7 days
        elif path.startswith('/static'):
            response.headers['Cache-Control'] = 'public, max-age=604800'
        return response

app.add_middleware(CacheControlMiddleware)

# Security headers middleware for HTTPS optimization
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # Enable XSS filter
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Permissions policy
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        # HSTS - only in production (when not debug mode)
        if not settings.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Session middleware for server-rendered web UI
# In production: secure=True ensures cookies only sent over HTTPS
# httponly=True prevents JavaScript access to session cookie
# same_site='lax' provides CSRF protection while allowing normal navigation
app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.secret_key,
    https_only=not settings.debug,  # Secure cookies in production
    same_site='lax'
)

# Import templates from web routes to get the enhanced version with workspace injection
from app.web.routes import templates

# Mount uploads directory for serving uploaded files (logos, attachments, etc.)
BASE_DIR = Path(__file__).resolve().parent
uploads_path = os.path.join(BASE_DIR, "uploads")
os.makedirs(uploads_path, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")

# Mount static directory for PWA assets (icons, manifest, service worker)
static_path = os.path.join(BASE_DIR, "static")
os.makedirs(static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}


# API routers
app.include_router(auth_routes.router, prefix="/api")
app.include_router(users_routes.router, prefix="/api")
app.include_router(projects_routes.router, prefix="/api")
app.include_router(tasks_routes.router, prefix="/api")
from app.api.routes import system as system_routes
app.include_router(system_routes.router, prefix="/api")
from app.api.routes import external as external_routes
app.include_router(external_routes.router, prefix="/api")
from app.web import routes as web_routes  # noqa: E402
app.include_router(web_routes.router, prefix="/web")


# Minimal server-rendered pages
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # Get workspace from request state (added by middleware)
    workspace = getattr(request.state, 'workspace', None)
    # Render the landing page template
    return templates.TemplateResponse("index.html", {
        "request": request,
        "workspace": workspace
    })
