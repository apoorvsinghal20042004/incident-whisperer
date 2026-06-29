from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import get_settings

from app.db.database import engine, Base

# We import the incident model here even though we don't use it directly.
# Why? Because Base needs to "know about" all models before it can
# create their tables. Importing the module registers the model with Base.
# If we skip this import, Base.metadata.create_all creates zero tables.
from app.models import incident
from app.api import incidents
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    #everything before yield runs on startup
    print(f"Starting {settings.app_name}...")

    # engine.begin() opens a single connection for setup work.
    # We use it here just to run the CREATE TABLE statements.
    # async with ensures the connection is closed after setup.
    async with engine.begin() as conn:
        # Base.metadata.create_all looks at every model registered
        # with Base and creates its table in Postgres if it doesn't
        # exist yet. Safe to run every startup — won't overwrite
        # existing tables or data.         
        # run_sync() is needed because create_all is a synchronous
        # function inside an async context. It wraps the sync call
        # so it doesn't block the event loop.
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables ready")
    yield
    #dispose() closes all connections in pool cleanly
    await engine.dispose()
    print(f"Shutting down {settings.app_name}...")

# App instance
# actual FastAPI application created
app = FastAPI(
    title=settings.app_name,
    description="Autonomous incident diagnosis using multi-agent AI", 
    version="0.1.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["http://localhost:3000"], #only allow frontend
    allow_credentials=True,
    allow_methods=["*"], #allow all methods
    allow_headers=["*"],
)

# register routers
app.include_router(incidents.router)
# health check endpoint
# its there for every production API. It returns I am alive
# used by LBs and monitoring systems to verify the service is running
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "0.1.0"
    }

# Root endpoint- not actually required for our project
@app.get("/")
async def root():
    return {"message" : f"Welcome to {settings.app_name}"}