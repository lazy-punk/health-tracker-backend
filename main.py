from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Any, Dict, Optional
import logging
import os
from dotenv import load_dotenv

# Import routers
from api.auth_routes import router as auth_router
from api.wellness_routes import router as wellness_router

# Import database initialization
from database import init_database, check_database_health, close_database_connection
from auth import get_security_headers

# Load environment variables
load_dotenv()

# Test models
class TestBody(BaseModel):
    """Flexible test body model"""
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "allow"  # Allow additional fields

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logging.info("Starting Wellness Tracker API...")
    
    # Test database connection
    if check_database_health():
        logging.info("MongoDB connection successful")
        
        # Initialize database with indexes and default data
        init_database()
        logging.info("MongoDB collections, indexes, and default data initialized")
    else:
        logging.error("MongoDB connection failed!")
        raise Exception("Cannot start application without database connection")
    
    yield
    
    # Shutdown
    logging.info("Shutting down Wellness Tracker API...")
    close_database_connection()

# Create FastAPI application
app = FastAPI(
    title=os.getenv("PROJECT_NAME", "Wellness Tracker API"),
    description="A comprehensive wellness tracking API with user authentication and progress monitoring",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS configuration
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    os.getenv("FRONTEND_URL")
]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
# Add trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.localhost", "*.netlify.app", "*.onrender.com"]
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Add security headers
    security_headers = get_security_headers()
    for header, value in security_headers.items():
        response.headers[header] = value
    
    return response

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(wellness_router, prefix="/api/v1")

# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Welcome to Wellness Tracker API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db_status = check_database_health()
        
        return {
            "status": "healthy" if db_status else "unhealthy",
            "database": "connected" if db_status else "disconnected",
            "database_type": "MongoDB",
            "version": "1.0.0"
        }
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "error",
                "database_type": "MongoDB",
                "error": str(e)
            }
        )
    
@app.post("/test")
async def test(request: Request):
    """Test endpoint - returns the entire request body"""
    try:
        # Get the request body as JSON
        body = await request.json()
        return {
            "received_body": body,
            "body_type": type(body).__name__,
            "message": "Successfully received POST request body"
        }
    except Exception as e:
        # If JSON parsing fails, try to get raw body
        try:
            raw_body = await request.body()
            return {
                "received_body": raw_body.decode('utf-8'),
                "body_type": "raw_string",
                "message": "Received raw body (not JSON)"
            }
        except Exception as parse_error:
                         return {
                 "error": str(e),
                 "parse_error": str(parse_error),
                 "message": "Failed to parse request body"
             }

@app.post("/test-structured")
async def test_structured(body: TestBody):
    """Test endpoint with structured body using Pydantic"""
    return {
        "received_body": body.dict(),
        "message": f"Received structured data: {body.message or 'No message provided'}",
        "extra_fields": {k: v for k, v in body.dict().items() if k not in ['message', 'data']},
        "data_provided": body.data is not None
    }

@app.post("/test-form")
async def test_form(request: Request):
    """Test endpoint that can handle all types of form data"""
    content_type = request.headers.get("content-type", "")
    
    try:
        if "application/json" in content_type:
            # Handle JSON data
            body = await request.json()
            return {
                "data_type": "JSON",
                "content_type": content_type,
                "received_data": body,
                "message": "Successfully parsed JSON data"
            }
        
        elif "multipart/form-data" in content_type:
            # Handle multipart form data
            form_data = await request.form()
            parsed_data = {}
            for key, value in form_data.items():
                parsed_data[key] = value
            
            return {
                "data_type": "Multipart Form Data",
                "content_type": content_type,
                "received_data": parsed_data,
                "field_count": len(parsed_data),
                "message": "Successfully parsed multipart form data"
            }
        
        elif "application/x-www-form-urlencoded" in content_type:
            # Handle URL encoded form data
            form_data = await request.form()
            parsed_data = {}
            for key, value in form_data.items():
                parsed_data[key] = value
            
            return {
                "data_type": "URL Encoded Form Data",
                "content_type": content_type,
                "received_data": parsed_data,
                "field_count": len(parsed_data),
                "message": "Successfully parsed URL encoded form data"
            }
        
        else:
            # Handle raw data
            raw_body = await request.body()
            return {
                "data_type": "Raw Data",
                "content_type": content_type,
                "received_data": raw_body.decode('utf-8') if raw_body else "",
                "message": "Received raw body data"
            }
            
    except Exception as e:
        return {
            "error": str(e),
            "content_type": content_type,
                         "message": "Failed to parse request data"
         }

@app.post("/test-form-simple")
async def test_form_simple(
    message: str = Form(...),
    password: str = Form(None),
    email: str = Form(None)
):
    """Simple form endpoint using FastAPI Form parameters"""
    return {
        "data_type": "FastAPI Form Parameters",
        "received_data": {
            "message": message,
            "password": password,
            "email": email
        },
        "message": f"Hello {message}! Form data received successfully."
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "server_error"
        }
    )
