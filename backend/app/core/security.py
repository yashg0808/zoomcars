"""
Security utilities for JWT authentication
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from pydantic import BaseModel

from app.core.config import settings

security = HTTPBearer()


class TokenData(BaseModel):
    """Token payload data"""
    user_id: str
    phone: str
    exp: datetime


class TokenPayload(BaseModel):
    """JWT token payload"""
    user_id: str
    phone: str


def create_access_token(user_id: str, phone: str) -> str:
    """Create JWT access token"""
    payload = {
        "user_id": user_id,
        "phone": phone,
        "exp": datetime.utcnow() + timedelta(days=settings.JWT_EXPIRY_DAYS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return TokenPayload(user_id=payload["user_id"], phone=payload["phone"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenPayload:
    """Dependency to get current user from token"""
    return decode_access_token(credentials.credentials)
