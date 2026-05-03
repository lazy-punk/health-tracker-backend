from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Any, Dict, Optional
import logging
from logtail import LogtailHandler
import sys
import time
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
# print(os.getenv("LOGTAIL_SOURCE_TOKEN"))
# print(os.getenv("LOGTAIL_HOST"))

handler = LogtailHandler(
    source_token=os.getenv("LOGTAIL_SOURCE_TOKEN"),
    host=os.getenv("LOGTAIL_HOST")
)

# Configure logging with comprehensive setup
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get logger for this module
logger = logging.getLogger(__name__)

logger.addHandler(handler)

# Test models
class TestBody(BaseModel):
    """Flexible test body model"""
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "allow"  # Allow additional fields

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Wellness Tracker API...")
    
    try:
        # Test database connection
        logger.debug("Testing database connection...")
        if check_database_health():
            logger.info("MongoDB connection successful")
            
            # Initialize database with indexes and default data
            logger.debug("Initializing database...")
            init_database()
            logger.info("MongoDB collections, indexes, and default data initialized")
        else:
            logger.error("MongoDB connection failed!")
            raise Exception("Cannot start application without database connection")
            
        logger.info("Application startup completed successfully")
        
    except Exception as e:
        logger.error(f"Application startup failed: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Wellness Tracker API...")
    try:
        close_database_connection()
        logger.info("Database connection closed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)

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

logger.info(f"CORS origins configured: {CORS_ORIGINS}")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
logger.debug("CORS middleware added")

# Add trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.localhost", "*.netlify.app", "*.onrender.com"]
)
logger.debug("Trusted host middleware added")

# Request logging and security headers middleware
@app.middleware("http")
async def log_requests_and_security(request: Request, call_next):
    """Log requests and add security headers to all responses"""
    start_time = time.time()
    
    # Log incoming request
    logger.info(f"REQUEST: {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}")
    logger.debug(f"Request headers: {dict(request.headers)}")
    
    try:
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        logger.info(f"RESPONSE: {response.status_code} for {request.method} {request.url.path} - Time: {process_time:.4f}s")
        
        # Add security headers
        try:
            security_headers = get_security_headers()
            for header, value in security_headers.items():
                response.headers[header] = value
            logger.debug("Security headers added to response")
        except Exception as e:
            logger.warning(f"Failed to add security headers: {e}")
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"REQUEST ERROR: {request.method} {request.url.path} - {str(e)} - Time: {process_time:.4f}s", exc_info=True)
        raise

# Include routers
logger.debug("Including API routers...")
app.include_router(auth_router, prefix="/api/v1")
logger.debug("Auth router included")
app.include_router(wellness_router, prefix="/api/v1")
logger.debug("Wellness router included")

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail} - Path: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "http_error"}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    logger.error(f"Validation Error: {exc.errors()} - Path: {request.url.path}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "type": "validation_error",
            "errors": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"UNHANDLED EXCEPTION: {type(exc).__name__}: {str(exc)}", exc_info=True)
    logger.error(f"Request details: {request.method} {request.url.path}")
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "server_error"
        }
    )

# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    logger.info("Root endpoint accessed")
    logger.debug("Returning API information")
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
    logger.debug("Health check endpoint accessed")
    
    try:
        # Test database connection
        logger.debug("Testing database health...")
        db_status = check_database_health()
        
        if db_status:
            logger.info("Health check passed - all systems operational")
            status_response = {
                "status": "healthy",
                "database": "connected",
                "database_type": "MongoDB",
                "version": "1.0.0"
            }
        else:
            logger.warning("Health check failed - database not connected")
            status_response = {
                "status": "unhealthy",
                "database": "disconnected",
                "database_type": "MongoDB",
                "version": "1.0.0"
            }
        
        return status_response
        
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "error",
                "database_type": "MongoDB",
                "error": str(e),
                "version": "1.0.0"
            }
        )

@app.post("/test")
async def test(request: Request):
    """Test endpoint - returns the entire request body"""
    logger.info("Test endpoint accessed")
    
    try:
        logger.debug("Attempting to parse JSON body...")
        # Get the request body as JSON
        body = await request.json()
        logger.info("Test endpoint - JSON body parsed successfully")
        logger.debug(f"Received body type: {type(body).__name__}")
        
        return {
            "received_body": body,
            "body_type": type(body).__name__,
            "message": "Successfully received POST request body"
        }
        
    except Exception as e:
        logger.warning(f"JSON parsing failed: {e}")
        logger.debug("Attempting to parse raw body...")
        
        # If JSON parsing fails, try to get raw body
        try:
            raw_body = await request.body()
            logger.info("Test endpoint - raw body parsed successfully")
            
            return {
                "received_body": raw_body.decode('utf-8'),
                "body_type": "raw_string",
                "message": "Received raw body (not JSON)"
            }
            
        except Exception as parse_error:
            logger.error(f"Failed to parse both JSON and raw body: JSON error: {e}, Raw error: {parse_error}")
            
            return {
                "error": str(e),
                "parse_error": str(parse_error),
                "message": "Failed to parse request body"
            }

@app.post("/test-structured")
async def test_structured(body: TestBody):
    """Test endpoint with structured body using Pydantic"""
    logger.info("Structured test endpoint accessed")
    logger.debug(f"Received structured data with message: {body.message}")
    
    extra_fields = {k: v for k, v in body.dict().items() if k not in ['message', 'data']}
    if extra_fields:
        logger.debug(f"Extra fields detected: {extra_fields}")
    
    return {
        "received_body": body.dict(),
        "message": f"Received structured data: {body.message or 'No message provided'}",
        "extra_fields": extra_fields,
        "data_provided": body.data is not None
    }

@app.post("/test-form")
async def test_form(request: Request):
    """Test endpoint that can handle all types of form data"""
    logger.info("Form test endpoint accessed")
    content_type = request.headers.get("content-type", "")
    logger.debug(f"Content type: {content_type}")
    
    try:
        if "application/json" in content_type:
            logger.debug("Processing JSON data...")
            # Handle JSON data
            body = await request.json()
            logger.info("JSON form data processed successfully")
            
            return {
                "data_type": "JSON",
                "content_type": content_type,
                "received_data": body,
                "message": "Successfully parsed JSON data"
            }
        
        elif "multipart/form-data" in content_type:
            logger.debug("Processing multipart form data...")
            # Handle multipart form data
            form_data = await request.form()
            parsed_data = {}
            for key, value in form_data.items():
                parsed_data[key] = value
            
            logger.info(f"Multipart form data processed successfully - {len(parsed_data)} fields")
            
            return {
                "data_type": "Multipart Form Data",
                "content_type": content_type,
                "received_data": parsed_data,
                "field_count": len(parsed_data),
                "message": "Successfully parsed multipart form data"
            }
        
        elif "application/x-www-form-urlencoded" in content_type:
            logger.debug("Processing URL encoded form data...")
            # Handle URL encoded form data
            form_data = await request.form()
            parsed_data = {}
            for key, value in form_data.items():
                parsed_data[key] = value
            
            logger.info(f"URL encoded form data processed successfully - {len(parsed_data)} fields")
            
            return {
                "data_type": "URL Encoded Form Data",
                "content_type": content_type,
                "received_data": parsed_data,
                "field_count": len(parsed_data),
                "message": "Successfully parsed URL encoded form data"
            }
        
        else:
            logger.debug("Processing raw data...")
            # Handle raw data
            raw_body = await request.body()
            logger.info("Raw data processed successfully")
            
            return {
                "data_type": "Raw Data",
                "content_type": content_type,
                "received_data": raw_body.decode('utf-8') if raw_body else "",
                "message": "Received raw body data"
            }
            
    except Exception as e:
        logger.error(f"Form processing error: {e}", exc_info=True)
        
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
    logger.info("Simple form test endpoint accessed")
    logger.debug(f"Form data received - message: {message}, email: [REDACTED]")
    
    return {
        "data_type": "FastAPI Form Parameters",
        "received_data": {
            "message": message,
            "password": password,
            "email": email
        },
        "message": f"Hello {message}! Form data received successfully."
    }
