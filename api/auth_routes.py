from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from auth import (
    UserCreate, UserLogin, Token, TokenData, UserResponse, PasswordRecoveryRequest,
    create_token_pair, verify_token, validate_password_strength,
    refresh_access_token, get_security_headers, get_password_hash
)
from models import UserModel, RecoveryKeyModel
import logging

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserResponse:
    """Get current authenticated user"""
    token_data = verify_token(credentials.credentials, token_type="access")
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = UserModel.get_user_by_id(token_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

@router.post("/register", response_model=dict)
async def register(user_data: UserCreate):
    """Register a new user"""
    try:
        # Validate password strength
        password_validation = validate_password_strength(user_data.password)
        if not password_validation["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Password does not meet requirements",
                    "password_feedback": password_validation["feedback"]
                }
            )
        
        # Check if user already exists
        existing_user = UserModel.get_user_by_username(user_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already registered"
            )
        
        # Hash password and create user
        hashed_password = get_password_hash(user_data.password)
        new_user = UserModel.create_user(
            username=user_data.username,
            email=user_data.email,
            password=hashed_password
        )
        
        if not new_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        # Create tokens
        tokens = create_token_pair(new_user.id, new_user.username)
        
        # Generate recovery keys
        recovery_keys = RecoveryKeyModel.create_recovery_keys(new_user.id)
        
        return {
            "message": "Registration successful",
            "user": new_user,
            "tokens": tokens,
            "recovery_keys": recovery_keys
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=dict)
async def login(user_credentials: UserLogin):
    """Authenticate user and return tokens"""
    try:
        # Authenticate user
        user = UserModel.authenticate_user(
            user_credentials.username,
            user_credentials.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )
        
        # Create tokens
        tokens = create_token_pair(user.id, user.username)
        
        return {
            "message": "Login successful",
            "user": user,
            "tokens": tokens
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Login error: {e}")
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
    try:
        new_access_token = refresh_access_token(request.refresh_token)
        
        if not new_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@router.post("/validate-password", response_model=dict)
async def validate_password(password: str):
    """Validate password strength"""
    validation_result = validate_password_strength(password)
    return validation_result

@router.post("/logout", response_model=dict)
async def logout(current_user: UserResponse = Depends(get_current_user)):
    """Logout user (client should remove tokens)"""
    return {"message": "Logout successful"}

@router.post("/recover-password", response_model=dict)
async def recover_password(recovery_data: PasswordRecoveryRequest):
    """Reset password using recovery key"""
    try:
        # Validate password strength
        password_validation = validate_password_strength(recovery_data.new_password)
        if not password_validation["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Password does not meet requirements",
                    "password_feedback": password_validation["feedback"]
                }
            )
        
        # Get user by email
        user = UserModel.get_user_by_username(recovery_data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify recovery key
        if not RecoveryKeyModel.verify_recovery_key(user["id"], recovery_data.recovery_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid recovery key"
            )
        
        # Update password
        new_password_hash = get_password_hash(recovery_data.new_password)
        UserModel.update_password(user["id"], new_password_hash)
        
        # Log recovery key usage (but don't mark as used since keys are reusable)
        RecoveryKeyModel.use_recovery_key(user["id"], recovery_data.recovery_key)
        
        # Get total keys count (all keys are reusable)
        total_keys = RecoveryKeyModel.count_unused_keys(user["id"])
        
        return {
            "message": "Password reset successful",
            "total_recovery_keys": total_keys
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Password recovery error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password recovery failed"
        )

# Optional security dependency
optional_security = HTTPBearer(auto_error=False)

# Dependency to get current user (can be used in other routes)
async def get_optional_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security)) -> Optional[UserResponse]:
    """Get current user if authenticated, otherwise None"""
    if not credentials:
        return None
    
    try:
        token_data = verify_token(credentials.credentials, token_type="access")
        if not token_data:
            return None
        
        user = UserModel.get_user_by_id(token_data.user_id)
        return user
    except:
        return None 