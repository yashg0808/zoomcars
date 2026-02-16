"""
Booking Endpoints
Critical booking flow with double-booking prevention

NEW FLOW (Redis-only holds):
1. /initiate - Creates hold in Redis, sends OTP (NO DB write)
2. /confirm - Verifies OTP + lock_token, writes to DB

Benefits:
- Zero DB writes on abandoned bookings
- Fail-fast availability checks via Redis
- TTL auto-cleanup of abandoned holds
"""

import uuid
import logging
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
import redis.asyncio as redis
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis, CacheManager
from app.core.security import get_current_user_token, TokenPayload
from app.models import User, Car, Booking, BookingStatus
from app.schemas import (
    InitiateBookingRequest, InitiateBookingResponse,
    BookingResponse, BookingListResponse,
    ConfirmPaymentRequest, ConfirmPaymentResponse,
    CancelBookingResponse,
    BookingOTPRequest, BookingOTPResponse,
    ConfirmBookingRequest, ConfirmBookingResponse,
    CancelHoldRequest, CancelHoldResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)


def calculate_dynamic_price(base_rate: float, start_time: datetime, duration_hours: float) -> float:
    """Apply surge pricing."""
    price = base_rate
    if start_time.weekday() >= 4:
        price *= 1.2
    if duration_hours >= 168:
        price *= 0.85
    return round(price, 2)


# ============== NEW BOOKING FLOW (Redis-only holds) ==============

@router.post("/initiate", response_model=InitiateBookingResponse)
async def initiate_booking(
    request: InitiateBookingRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> InitiateBookingResponse:
    """
    Step 1: Initiate booking - creates a HOLD in Redis and sends OTP.
    
    CRITICAL: This does NOT write to the database.
    The hold exists only in Redis with a TTL. If user abandons,
    the hold auto-expires and the slot becomes available again.
    
    Flow:
    1. Rate limit check
    2. Validate times
    3. Verify car exists
    4. Fail-fast availability check (cache + holds)
    5. Acquire distributed lock for car
    6. Create hold in Redis (with TTL)
    7. Send OTP
    8. Return booking_id + lock_token
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
    
    # Validation
    now = datetime.utcnow()
    if request.start_time.tzinfo:
        now = datetime.now(request.start_time.tzinfo)
    
    if request.start_time < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time cannot be in the past"
        )
    
    if request.end_time <= request.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time must be after start time"
        )
    
    rental_duration_hours = (request.end_time - request.start_time).total_seconds() / 3600
    if rental_duration_hours < settings.MIN_RENTAL_HOURS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum rental duration is {settings.MIN_RENTAL_HOURS} hour(s)"
        )
    
    # Verify car exists
    car = await db.get(Car, request.car_id)
    if not car or not car.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Car not found or not available"
        )
    
    # Calculate buffer and times
    end_time_with_buffer = request.end_time + timedelta(hours=settings.BUFFER_HOURS)
    start_time_str = request.start_time.isoformat()
    end_time_with_buffer_str = end_time_with_buffer.isoformat()
    
    # ═══════════════════════════════════════════════════════════════════════
    # FAIL-FAST: Check availability against cache + active holds
    # This avoids waiting for lock if slot is obviously unavailable
    # ═══════════════════════════════════════════════════════════════════════
    try:
        is_available, cache_hit, _ = await cache.check_availability_with_holds(
            car_id=request.car_id,
            start_time=start_time_str,
            end_time_with_buffer=end_time_with_buffer_str
        )
    except Exception:
        logger.warning("Cache read failed for availability check, will check DB under lock", exc_info=True)
        is_available, cache_hit = True, False  # Proceed to lock and check DB
    
    if not is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Car is not available for the selected time period"
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # CRITICAL SECTION: Distributed lock to prevent race conditions
    # Lock is per car_id (not per time slot) to prevent overlapping holds
    # ═══════════════════════════════════════════════════════════════════════
    lock = cache.get_booking_lock(request.car_id)
    lock_acquired = False
    
    try:
        lock_acquired = await lock.acquire()
        if not lock_acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Car is being booked by another user. Please try again."
            )
        
        # Re-check availability after acquiring lock
        try:
            is_available, cache_hit, _ = await cache.check_availability_with_holds(
                car_id=request.car_id,
                start_time=start_time_str,
                end_time_with_buffer=end_time_with_buffer_str
            )
        except Exception:
            logger.warning("Cache read failed for availability recheck, will verify from DB", exc_info=True)
            is_available, cache_hit = True, False  # Will verify against DB below
        
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Car was just taken. Please try another slot."
            )
        
        # If cache miss, verify against DB and populate cache (write-through)
        if not cache_hit:
            # Fetch ALL confirmed bookings for this car to populate cache
            schedule_query = text("""
                SELECT 
                    lower(total_period) as period_start,
                    upper(total_period) as period_end,
                    status
                FROM bookings
                WHERE car_id = :car_id
                AND status = 'CONFIRMED'
                AND upper(total_period) > NOW()
                ORDER BY lower(total_period)
            """)
            
            result = await db.execute(schedule_query, {"car_id": request.car_id})
            rows = result.fetchall()
            
            # Check for overlap with requested slot
            is_unavailable = False
            schedule = []
            for row in rows:
                period_start = row.period_start
                period_end = row.period_end
                
                schedule.append({
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                    "status": row.status
                })
                
                # Check overlap: [req_start, req_end) && [existing_start, existing_end)
                if request.start_time < period_end and end_time_with_buffer > period_start:
                    is_unavailable = True
            
            # Write-through: populate cache with fetched schedule
            await cache.set_car_schedule(request.car_id, schedule)
            
            if is_unavailable:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Car is not available for the selected time period"
                )
        
        # Calculate pricing
        dynamic_price = calculate_dynamic_price(
            float(car.base_hourly_rate),
            request.start_time,
            rental_duration_hours
        )
        total_amount = round(dynamic_price * rental_duration_hours, 2)
        
        # Generate booking ID and lock token
        booking_id = str(uuid.uuid4())
        lock_token = str(uuid.uuid4())
        
        # Create hold in Redis (NO DATABASE WRITE!)
        hold_data = await cache.create_hold(
            booking_id=booking_id,
            car_id=request.car_id,
            phone=request.phone,
            start_time=start_time_str,
            end_time_with_buffer=end_time_with_buffer_str,
            lock_token=lock_token,
            total_amount=total_amount,
            car_details={
                "make": car.make,
                "model": car.model,
                "year": car.year,
                "image_url": car.image_url,
                "booking_start": request.start_time.isoformat(),
                "booking_end": request.end_time.isoformat()
            }
        )
        
    finally:
        if lock_acquired:
            await lock.release()
    
    # Generate and store OTP (with demo bypass)
    if request.phone == "+919999999999":
        # Demo OTP bypass — skip Twilio entirely
        otp = "123456"
        logger.info("Demo OTP bypass used for 9999999999")
        otp_sent = True
        await cache.store_otp(request.phone, otp)
        await cache.increment_otp_rate_limit(request.phone)
    else:
        otp = str(random.randint(100000, 999999))
        await cache.store_otp(request.phone, otp)
        await cache.increment_otp_rate_limit(request.phone)
        
        # Send OTP via Twilio WhatsApp
        otp_sent = False
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                twilio_client = TwilioClient(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN
                )
                
                whatsapp_to = f"whatsapp:{request.phone}" if not request.phone.startswith("whatsapp:") else request.phone
                
                message = twilio_client.messages.create(
                    from_=settings.TWILIO_WHATSAPP_FROM,
                    content_sid=settings.TWILIO_CONTENT_SID,
                    content_variables=json.dumps({"1": otp}),
                    to=whatsapp_to
                )
                logger.info(f"Twilio message sent: {message.sid}")
                otp_sent = True
            except TwilioRestException as e:
                logger.error(f"Failed to send WhatsApp message: {e}")
                # Don't fail the booking - user can still see OTP in dev mode
                otp_sent = False
        else:
            logger.info(f"[DEV] Booking OTP for {request.phone}: {otp}")
            otp_sent = True  # In dev mode, consider it sent
    
    expires_at = datetime.fromisoformat(hold_data["expires_at"])
    
    return InitiateBookingResponse(
        booking_id=uuid.UUID(booking_id),
        lock_token=lock_token,
        expires_at=expires_at,
        expires_in_seconds=cache.TTL_HOLD,
        otp_sent=otp_sent,
        booking_preview={
            "car": f"{car.make} {car.model} ({car.year})",
            "duration_hours": round(rental_duration_hours, 1),
            "total_amount": total_amount,
            "start_time": request.start_time.isoformat(),
            "end_time": request.end_time.isoformat()
        }
    )


@router.post("/confirm", response_model=ConfirmBookingResponse)
async def confirm_booking(
    request: ConfirmBookingRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> ConfirmBookingResponse:
    """
    Step 2: Confirm booking with OTP and lock_token.
    
    Validates:
    - Hold exists in Redis (not expired)
    - Lock token matches
    - OTP is correct
    
    Then:
    - Creates user if not exists
    - Writes CONFIRMED booking to database
    - Cleans up Redis hold
    - Updates schedule cache
    
    The DB exclusion constraint is the FINAL safety net against double-booking.
    """
    cache = CacheManager(redis_client)
    booking_id = str(request.booking_id)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 1: Fetch hold from Redis and validate lock_token
    # ═══════════════════════════════════════════════════════════════════════
    try:
        hold_data = await cache.get_hold(booking_id)
    except Exception:
        logger.warning(f"Cache read failed for hold: {booking_id}", exc_info=True)
        hold_data = None
    
    if hold_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking hold expired. Please start a new booking."
        )
    
    if hold_data["lock_token"] != request.lock_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid lock token. Please start a new booking."
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 2: Verify OTP
    # ═══════════════════════════════════════════════════════════════════════
    phone = hold_data["phone"]
    try:
        stored_otp = await cache.get_otp(phone)
    except Exception:
        logger.warning(f"Cache read failed for OTP: {phone}", exc_info=True)
        stored_otp = None
    
    if not stored_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired. Please request a new booking."
        )
    
    if stored_otp != request.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP. Please check and try again."
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 3: Extract booking details from hold
    # ═══════════════════════════════════════════════════════════════════════
    car_id = hold_data["car_id"]
    car_details = hold_data["car_details"]
    total_amount = hold_data["total_amount"]
    start_time = datetime.fromisoformat(car_details["booking_start"])
    end_time = datetime.fromisoformat(car_details["booking_end"])
    end_time_with_buffer = datetime.fromisoformat(hold_data["end"])
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 3b: Lazy Booking — check if inventory lock has expired
    # If the 5-minute lock window has passed but the 10-minute session is
    # still alive, re-check availability and re-acquire the hold.
    # ═══════════════════════════════════════════════════════════════════════
    lock_expires_at = datetime.fromisoformat(hold_data["lock_expires_at"])
    now = datetime.now(timezone.utc)
    # Make lock_expires_at timezone-aware if needed
    if lock_expires_at.tzinfo is None:
        lock_expires_at = lock_expires_at.replace(tzinfo=timezone.utc)
    
    if now > lock_expires_at:
        # Inventory lock expired — perform lazy re-check
        logger.info(f"Lazy booking: lock expired for {booking_id}, re-checking availability")
        
        start_time_str = hold_data["start"]
        end_time_with_buffer_str = hold_data["end"]
        
        try:
            is_available, _, _ = await cache.check_availability_with_holds(
                car_id=car_id,
                start_time=start_time_str,
                end_time_with_buffer=end_time_with_buffer_str
            )
        except Exception:
            logger.warning(f"Cache read failed during lazy re-check for {booking_id}", exc_info=True)
            # On cache failure, be conservative and fail
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unable to verify availability. Please start a new booking."
            )
        
        if not is_available:
            # Car was taken during the grace period
            await cache.delete_hold(booking_id, car_id)
            await cache.delete_otp(phone)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Car was booked by someone else during your session. Please try another slot."
            )
        
        # Re-acquire the hold by refreshing the car:holds set membership
        car_holds_key = f"car:holds:{car_id}"
        await redis_client.sadd(car_holds_key, booking_id)
        logger.info(f"Lazy booking: re-acquired hold for {booking_id}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 4: Get or create user
    # ═══════════════════════════════════════════════════════════════════════
    result = await db.execute(
        select(User).where(User.phone == phone)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            id=uuid.uuid4(),
            phone=phone,
            name=request.name,
            email=request.email
        )
        db.add(user)
        await db.flush()
    else:
        # Update user details if provided
        if request.name:
            user.name = request.name
        if request.email:
            user.email = request.email
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 5: Insert CONFIRMED booking into database
    # DB exclusion constraint is the FINAL safety net
    # Idempotency key = booking_id for safe retries
    # ═══════════════════════════════════════════════════════════════════════
    idempotency_key = booking_id  # Use booking_id for idempotent confirms
    
    insert_query = text("""
        INSERT INTO bookings (
            id, user_id, car_id, booking_start, booking_end,
            total_period, status, total_amount, idempotency_key
        ) VALUES (
            :id, :user_id, :car_id, :booking_start, :booking_end,
            tstzrange(:period_start, :period_end, '[)'), 'CONFIRMED', :total_amount, :idempotency_key
        )
    """)
    
    try:
        await db.execute(insert_query, {
            "id": booking_id,
            "user_id": str(user.id),
            "car_id": car_id,
            "booking_start": start_time,
            "booking_end": end_time,
            "period_start": start_time,
            "period_end": end_time_with_buffer,
            "total_amount": total_amount,
            "idempotency_key": idempotency_key
        })
        await db.commit()
        
    except IntegrityError as e:
        await db.rollback()
        error_str = str(e)
        
        if "no_double_booking" in error_str:
            # This is rare - means another booking snuck in (edge case)
            # Clean up the now-useless hold
            await cache.delete_hold(booking_id, car_id)
            await cache.delete_otp(phone)
            logger.warning(f"Double-booking constraint caught for booking {booking_id}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This slot was just booked by someone else. Please try another time."
            )
        else:
            logger.error(f"Database error during booking confirm: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred. Please try again."
            )
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 6: Clean up Redis
    # ═══════════════════════════════════════════════════════════════════════
    await cache.delete_hold(booking_id, car_id)
    await cache.delete_otp(phone)
    
    # Update schedule cache (write-through)
    try:
        await cache.add_booking_to_schedule(
            car_id=car_id,
            booking_start=start_time.isoformat(),
            booking_end=end_time_with_buffer.isoformat(),
            status="CONFIRMED"
        )
    except Exception:
        logger.warning(f"Failed to update schedule cache for car: {car_id}", exc_info=True)
    
    logger.info(f"Booking confirmed: {booking_id} for car {car_id}")
    
    return ConfirmBookingResponse(
        booking_id=request.booking_id,
        status=BookingStatus.CONFIRMED,
        total_amount=total_amount,
        message="Booking confirmed successfully!",
        car_details={
            "make": car_details["make"],
            "model": car_details["model"],
            "year": car_details["year"],
            "image_url": car_details.get("image_url")
        },
        booking_start=start_time,
        booking_end=end_time
    )


@router.post("/cancel", response_model=CancelHoldResponse)
async def cancel_hold(
    request: CancelHoldRequest,
    redis_client: redis.Redis = Depends(get_redis)
) -> CancelHoldResponse:
    """
    Cancel/Release a pending hold (Redis only, no DB interaction).
    
    Use this to explicitly release a car if the user decides not to proceed
    or if the demo bugs out. Removes both the hold data key and the
    car holds set entry immediately.
    """
    cache = CacheManager(redis_client)
    booking_id = str(request.booking_id)
    
    await cache.delete_hold(booking_id, request.car_id)
    logger.info(f"Hold cancelled: {booking_id} for car {request.car_id}")
    
    return CancelHoldResponse(
        booking_id=request.booking_id,
        message="Hold released successfully."
    )
