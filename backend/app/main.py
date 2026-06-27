from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import get_settings
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    #everything before yield runs on startup
    print(f"Starting {settings.app_name}...")
    print(f"Connecting to database at {settings.postgres_host}:{settings.postgres_port}")
    yield
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