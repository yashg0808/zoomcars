"""
Authentication Endpoints
OTP-based authentication for Indian phone numbers
"""

import random
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis, CacheManager
from app.core.security import create_access_token, get_current_user_token, TokenPayload
from app.models import User
from app.schemas import (
    SendOTPRequest, SendOTPResponse,
    VerifyOTPRequest, VerifyOTPResponse,
    UserResponse, UpdateProfileRequest
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp(
    request: SendOTPRequest,
    redis_client: redis.Redis = Depends(get_redis)
) -> SendOTPResponse:
    """
    Generate and send OTP via SMS.
    Rate limit: 3 OTPs per phone per hour.
    """
    cache = CacheManager(redis_client)
    
    # Check rate limit
    try:
        is_allowed, current_count = await cache.check_otp_rate_limit(request.phone)
    except Exception:
        logger.error("Cache read failed for OTP rate limit check, failing open", exc_info=True)
        is_allowed, current_count = True, 0  # Fail-open on Redis failure
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please try again after 1 hour."
        )
    
    # Generate 4-digit OTP
    otp = str(random.randint(1000, 9999))
    
    # Store OTP in Redis
    await cache.store_otp(request.phone, otp)
    
    # Increment rate limit counter
    await cache.increment_otp_rate_limit(request.phone)
    
    # Send OTP via Twilio WhatsApp
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        try:
            twilio_client = TwilioClient(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
            
            # Format phone for WhatsApp (ensure it has whatsapp: prefix)
            whatsapp_to = f"whatsapp:{request.phone}" if not request.phone.startswith("whatsapp:") else request.phone
            
            message = twilio_client.messages.create(
                from_=settings.TWILIO_WHATSAPP_FROM,
                content_sid=settings.TWILIO_CONTENT_SID,
                content_variables=json.dumps({"1": otp}),
                to=whatsapp_to
            )
            logger.info(f"Twilio message sent: {message.sid}")
        except TwilioRestException as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP. Please try again."
            )
    else:
        # In development without Twilio, log the OTP
        logger.info(f"[DEV] OTP for {request.phone}: {otp}")
    
    return SendOTPResponse(
        message="OTP sent successfully",
        expires_in_seconds=settings.OTP_EXPIRY_SECONDS
    )


@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp(
    request: VerifyOTPRequest,
    redis_client: redis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db)
) -> VerifyOTPResponse:
    """
    Verify OTP and issue JWT token.
    Creates user if not exists.
    """
    cache = CacheManager(redis_client)
    
    # Get stored OTP
    try:
        stored_otp = await cache.get_otp(request.phone)
    except Exception:
        logger.warning("Cache read failed for OTP retrieval", exc_info=True)
        stored_otp = None
    
    if not stored_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired or not found. Please request a new OTP."
        )
    
    if stored_otp != request.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP. Please check and try again."
        )
    
    # Delete OTP after successful verification
    await cache.delete_otp(request.phone)
    
    # Get or create user
    result = await db.execute(
        select(User).where(User.phone == request.phone)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Create new user
        user = User(phone=request.phone, is_verified=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"New user created: {user.id}")
    else:
        # Update verification status
        if not user.is_verified:
            user.is_verified = True
            await db.commit()
    
    # Generate JWT token
    access_token = create_access_token(str(user.id), user.phone)
    
    return VerifyOTPResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            phone=user.phone,
            name=user.name,
            email=user.email
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    token: TokenPayload = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Get current authenticated user's profile."""
    result = await db.execute(
        select(User).where(User.id == token.user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user.id,
        phone=user.phone,
        name=user.name,
        email=user.email
    )


@router.put("/me", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    token: TokenPayload = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Update current user's profile."""
    result = await db.execute(
        select(User).where(User.id == token.user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    if request.name is not None:
        user.name = request.name
    if request.email is not None:
        user.email = request.email
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse(
        id=user.id,
        phone=user.phone,
        name=user.name,
        email=user.email
    )
