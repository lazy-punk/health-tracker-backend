from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from passlib.hash import bcrypt
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import logging

# Load environment variables
load_dotenv()

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic models
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str  # Can be username or email
    password: str

class PasswordRecoveryRequest(BaseModel):
    email: str
    recovery_key: str
    new_password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    is_active: bool
    total_points: int
    current_streak: int
    best_streak: int
    created_at: datetime

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logging.error(f"Password verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Hash a password"""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logging.error(f"Password hashing error: {e}")
        raise

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    
    try:
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logging.error(f"Token creation error: {e}")
        raise

def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    try:
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logging.error(f"Refresh token creation error: {e}")
        raise

def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """Verify JWT token and return token data"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # Check token type
        if payload.get("type") != token_type:
            return None
        
        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        
        if user_id is None:
            return None
            
        return TokenData(user_id=user_id, username=username)
    except jwt.ExpiredSignatureError:
        logging.warning("Token has expired")
        return None
    except JWTError as e:
        logging.error(f"JWT verification error: {e}")
        return None

def create_token_pair(user_id: str, username: str) -> Token:
    """Create both access and refresh tokens"""
    token_data = {"sub": user_id, "username": username}
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )

def refresh_access_token(refresh_token: str) -> Optional[str]:
    """Create new access token using refresh token"""
    token_data = verify_token(refresh_token, token_type="refresh")
    
    if not token_data:
        return None
    
    new_token_data = {"sub": token_data.user_id, "username": token_data.username}
    return create_access_token(new_token_data)

def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength and return feedback"""
    feedback = []
    score = 0
    
    if len(password) >= 8:
        score += 1
    else:
        feedback.append("At least 8 characters")
    
    if any(c.islower() for c in password):
        score += 1
    else:
        feedback.append("Include lowercase letters")
    
    if any(c.isupper() for c in password):
        score += 1
    else:
        feedback.append("Include uppercase letters")
    
    if any(c.isdigit() for c in password):
        score += 1
    else:
        feedback.append("Include numbers")
    
    if any(c in "!@#$%^&*(),.?\":{}|<>" for c in password):
        score += 1
    else:
        feedback.append("Include special characters")
    
    strength_levels = {
        0: "Very Weak",
        1: "Very Weak", 
        2: "Weak",
        3: "Fair",
        4: "Strong",
        5: "Very Strong"
    }
    
    return {
        "score": score,
        "strength": strength_levels[score],
        "feedback": feedback,
        "is_valid": score >= 3  # Require at least "Fair" strength
    }

# Security headers middleware
def get_security_headers() -> Dict[str, str]:
    """Get security headers for API responses"""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'"
    } 