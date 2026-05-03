from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from auth import (
    UserCreate, UserLogin, Token, TokenData, UserResponse, PasswordRecoveryRequest,
    create_token_pair, verify_token, validate_password_strength,
    refresh_access_token, get_security_headers, get_password_hash
)
import os
from logtail import LogtailHandler
from dotenv import load_dotenv
from models import UserModel, RecoveryKeyModel
import logging

load_dotenv()

handler = LogtailHandler(
    source_token=os.getenv("LOGTAIL_SOURCE_TOKEN"),
    host=os.getenv("LOGTAIL_HOST")
)


# Get logger for this module
logger = logging.getLogger(__name__)
logger.addHandler(handler)
router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserResponse:
    """Get current authenticated user"""
    logger.debug("Attempting to get current user from token")
    
    try:
        token_data = verify_token(credentials.credentials, token_type="access")
        
        if not token_data:
            logger.warning("Invalid or expired token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.debug(f"Token verified for user ID: {token_data.user_id}")
        
        user = UserModel.get_user_by_id(token_data.user_id)
        if not user:
            logger.error(f"User not found for ID: {token_data.user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.debug(f"Current user retrieved: [REDACTED]")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/register", response_model=dict)
async def register(user_data: UserCreate):
    """Register a new user"""
    logger.info(f"Registration attempt for username: [REDACTED]")
    logger.debug(f"Registration data - Username: [REDACTED], Email: [REDACTED]")
    
    try:
        # Validate password strength
        logger.debug("Validating password strength...")
        password_validation = validate_password_strength(user_data.password)
        if not password_validation["is_valid"]:
            logger.warning(f"Weak password provided for user: [REDACTED]")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Password does not meet requirements",
                    "password_feedback": password_validation["feedback"]
                }
            )
        
        logger.debug("Password validation passed")
        
        # Check if user already exists
        logger.debug("Checking if user already exists...")
        existing_user = UserModel.get_user_by_username(user_data.username)
        if existing_user:
            logger.warning(f"Registration failed - username already exists: [REDACTED]")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already registered"
            )
        
        logger.debug("Username available")
        
        # Hash password and create user
        logger.debug("Hashing password and creating user...")
        hashed_password = get_password_hash(user_data.password)
        new_user = UserModel.create_user(
            username=user_data.username,
            email=user_data.email,
            password=hashed_password
        )
        
        if not new_user:
            logger.error(f"Failed to create user in database: [REDACTED]")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        logger.info(f"User created successfully: [REDACTED] (ID: {new_user.id})")
        
        # Create tokens
        logger.debug("Creating authentication tokens...")
        tokens = create_token_pair(new_user.id, new_user.username)
        logger.debug("Tokens created successfully")
        
        # Generate recovery keys
        logger.debug("Generating recovery keys...")
        recovery_keys = RecoveryKeyModel.create_recovery_keys(new_user.id)
        logger.info(f"Recovery keys generated for user: [REDACTED]")

        logger.info(f"Registration completed successfully for user: [REDACTED]")
        
        return {
            "message": "Registration successful",
            "user": new_user,
            "tokens": tokens,
            "recovery_keys": recovery_keys
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error for user [REDACTED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=dict)
async def login(user_credentials: UserLogin):
    """Authenticate user and return tokens"""
    logger.info(f"Login attempt for user: [REDACTED]")
    
    try:
        # Authenticate user
        logger.debug("Authenticating user credentials...")
        user = UserModel.authenticate_user(
            user_credentials.username,
            user_credentials.password
        )
        
        if not user:
            logger.warning(f"Failed login attempt - invalid credentials for user: [REDACTED]")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.debug(f"User authenticated: [REDACTED]")
        
        # Check if account is active
        if not user.is_active:
            logger.warning(f"Login attempt for inactive account: [REDACTED]")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )
        
        logger.debug("Account is active")
        
        # Create tokens
        logger.debug("Creating authentication tokens...")
        tokens = create_token_pair(user.id, user.username)
        logger.debug("Tokens created successfully")
        
        logger.info(f"Successful login for user: [REDACTED]")
        
        return {
            "message": "Login successful",
            "user": user,
            "tokens": tokens
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for user [REDACTED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

from pydantic import BaseModel

class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/refresh", response_model=dict)
async def refresh_token(request: RefreshTokenRequest):
    """Refresh access token using refresh token"""
    logger.info("Token refresh attempt")
    logger.debug("Validating refresh token...")
    
    try:
        new_access_token = refresh_access_token(request.refresh_token)
        
        if not new_access_token:
            logger.warning("Token refresh failed - invalid or expired refresh token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info("Token refresh successful")
        logger.debug("New access token generated")
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    """Get current user information"""
    logger.info(f"User info request for: [REDACTED]")
    logger.debug("Returning current user information")
    return current_user

@router.post("/validate-password", response_model=dict)
async def validate_password(password: str):
    """Validate password strength"""
    logger.debug("Password validation request")
    
    try:
        validation_result = validate_password_strength(password)
        logger.debug(f"Password validation result: {validation_result['is_valid']}")
        
        if validation_result["is_valid"]:
            logger.debug("Password meets strength requirements")
        else:
            logger.debug(f"Password failed validation: {validation_result['feedback']}")
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Password validation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password validation failed"
        )

@router.post("/logout", response_model=dict)
async def logout(current_user: UserResponse = Depends(get_current_user)):
    """Logout user (client should remove tokens)"""
    logger.info(f"Logout request for user: [REDACTED]")
    logger.debug("User logout successful - tokens should be removed on client side")
    return {"message": "Logout successful"}

@router.post("/recover-password", response_model=dict)
async def recover_password(recovery_data: PasswordRecoveryRequest):
    """Reset password using recovery key"""
    logger.info(f"Password recovery attempt for email: [REDACTED]")
    
    try:
        # Validate password strength
        logger.debug("Validating new password strength...")
        password_validation = validate_password_strength(recovery_data.new_password)
        if not password_validation["is_valid"]:
            logger.warning(f"Weak password provided for password recovery: [REDACTED]")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Password does not meet requirements",
                    "password_feedback": password_validation["feedback"]
                }
            )
        
        logger.debug("New password validation passed")
        
        # Get user by email
        logger.debug("Looking up user by email...")
        user = UserModel.get_user_by_username(recovery_data.email)
        if not user:
            logger.warning(f"Password recovery failed - user not found: [REDACTED]")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.debug(f"User found: [REDACTED]")
        
        # Verify recovery key
        logger.debug("Verifying recovery key...")
        recovery_key_valid = RecoveryKeyModel.verify_recovery_key(
            user.id, 
            recovery_data.recovery_key
        )
        
        if not recovery_key_valid:
            logger.warning(f"Invalid recovery key used for user: [REDACTED]")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid recovery key"
            )
        
        logger.debug("Recovery key verified successfully")
        
        # Update password
        logger.debug("Updating user password...")
        hashed_password = get_password_hash(recovery_data.new_password)
        password_updated = UserModel.update_password(user.id, hashed_password)
        
        if not password_updated:
            logger.error(f"Failed to update password for user: [REDACTED]")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )
        
        logger.info(f"Password updated successfully for user: [REDACTED]")
        
        # Access the recovery key (this updates last_used timestamp)
        logger.debug("Updating recovery key access timestamp...")
        RecoveryKeyModel.access_recovery_key(user.id, recovery_data.recovery_key)
        
        # Get total recovery keys count
        total_keys = RecoveryKeyModel.count_recovery_keys(user.id)
        logger.debug(f"Total recovery keys for user: {total_keys}")
        
        logger.info(f"Password recovery completed successfully for user: [REDACTED]")
        
        return {
            "message": "Password reset successful",
            "total_recovery_keys": total_keys
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password recovery error for email [REDACTED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password recovery failed"
        )

# Optional authentication dependency for endpoints that work with or without auth
optional_security = HTTPBearer(auto_error=False)

async def get_optional_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security)) -> Optional[UserResponse]:
    """Get current user if authenticated, None otherwise"""
    if not credentials:
        logger.debug("No authentication credentials provided")
        return None
    
    try:
        logger.debug("Optional authentication - verifying token...")
        token_data = verify_token(credentials.credentials, token_type="access")
        
        if not token_data:
            logger.debug("Optional authentication - invalid token, returning None")
            return None
        
        user = UserModel.get_user_by_id(token_data.user_id)
        if not user:
            logger.debug("Optional authentication - user not found, returning None")
            return None
        
        logger.debug(f"Optional authentication successful for user: [REDACTED]")
        return user
        
    except Exception as e:
        logger.debug(f"Optional authentication failed: {e}")
        return None 