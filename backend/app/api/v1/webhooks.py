"""
Webhook Handlers
Razorpay payment webhooks with signature verification
"""

import hashlib
import hmac
import logging
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis, CacheManager
from fastapi import Depends
import redis.asyncio as redis

router = APIRouter()
logger = logging.getLogger(__name__)


def verify_razorpay_signature(body: bytes, signature: str) -> bool:
    """
    Verify Razorpay webhook signature.
    CRITICAL for security - prevents forged webhooks.
    """
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        logger.warning("Webhook secret not configured - skipping verification")
        return True
    
    try:
        expected_signature = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


@router.post("/payment")
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> dict:
    """
    Razorpay webhook handler for payment events.
    
    Handles:
    - payment.captured: Payment successful
    - payment.failed: Payment failed
    - refund.created: Refund initiated
    """
    cache = CacheManager(redis_client)
    
    # === STEP 1: Verify Signature ===
    webhook_body = await request.body()
    webhook_signature = request.headers.get("X-Razorpay-Signature", "")
    
    if not verify_razorpay_signature(webhook_body, webhook_signature):
        logger.warning("Invalid webhook signature received")
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook signature"
        )
    
    # === STEP 2: Parse Payload ===
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    
    event_type = payload.get("event")
    
    if not event_type:
        return {"status": "ignored", "reason": "No event type"}
    
    logger.info(f"Processing webhook event: {event_type}")
    
    # === STEP 3: Handle Payment Events ===
    
    if event_type == "payment.captured":
        return await handle_payment_captured(payload, db, cache)
    
    elif event_type == "payment.failed":
        return await handle_payment_failed(payload, db, cache)
    
    elif event_type == "refund.created":
        return await handle_refund_created(payload, db)
    
    else:
        logger.info(f"Unhandled event type: {event_type}")
        return {"status": "ignored", "reason": f"Unhandled event: {event_type}"}


async def handle_payment_captured(
    payload: dict,
    db: AsyncSession,
    cache: CacheManager
) -> dict:
    """Handle successful payment capture."""
    try:
        payment_entity = payload["payload"]["payment"]["entity"]
        payment_id = payment_entity["id"]
        order_id = payment_entity["order_id"]
        status = payment_entity["status"]
        
        if status != "captured":
            return {"status": "ignored", "reason": "Not captured status"}
        
        # Find booking
        result = await db.execute(
            text("SELECT id, car_id, status FROM bookings WHERE payment_order_id = :order_id"),
            {"order_id": order_id}
        )
        booking = result.fetchone()
        
        if not booking:
            logger.error(f"Booking not found for order_id: {order_id}")
            return {"status": "error", "reason": "Booking not found"}
        
        # Already confirmed?
        if booking.status == "CONFIRMED":
            logger.info(f"Booking {booking.id} already confirmed")
            return {"status": "success", "reason": "Already confirmed"}
        
        # Update booking status
        await db.execute(
            text("""
                UPDATE bookings 
                SET status = 'CONFIRMED', payment_id = :payment_id, expires_at = NULL, updated_at = NOW()
                WHERE id = :booking_id AND status = 'PENDING'
            """),
            {"payment_id": payment_id, "booking_id": str(booking.id)}
        )
        await db.commit()
        
        # Invalidate cache
        await cache.invalidate_car_schedule(booking.car_id)
        
        logger.info(f"Booking {booking.id} confirmed via webhook")
        
        return {"status": "success", "booking_id": str(booking.id)}
        
    except Exception as e:
        logger.error(f"Error handling payment.captured: {e}")
        return {"status": "error", "reason": str(e)}


async def handle_payment_failed(
    payload: dict,
    db: AsyncSession,
    cache: CacheManager
) -> dict:
    """Handle failed payment."""
    try:
        payment_entity = payload["payload"]["payment"]["entity"]
        order_id = payment_entity["order_id"]
        error_reason = payment_entity.get("error_description", "Payment failed")
        
        # Find booking
        result = await db.execute(
            text("SELECT id, car_id FROM bookings WHERE payment_order_id = :order_id"),
            {"order_id": order_id}
        )
        booking = result.fetchone()
        
        if not booking:
            return {"status": "ignored", "reason": "Booking not found"}
        
        # We don't automatically cancel - user might retry
        # Just log the failure
        logger.warning(f"Payment failed for booking {booking.id}: {error_reason}")
        
        return {"status": "logged", "booking_id": str(booking.id)}
        
    except Exception as e:
        logger.error(f"Error handling payment.failed: {e}")
        return {"status": "error", "reason": str(e)}


async def handle_refund_created(
    payload: dict,
    db: AsyncSession
) -> dict:
    """Handle refund creation."""
    try:
        refund_entity = payload["payload"]["refund"]["entity"]
        payment_id = refund_entity["payment_id"]
        refund_id = refund_entity["id"]
        refund_amount = refund_entity["amount"] / 100  # Convert from paise
        
        logger.info(f"Refund {refund_id} created for payment {payment_id}: Rs.{refund_amount}")
        
        return {"status": "success", "refund_id": refund_id}
        
    except Exception as e:
        logger.error(f"Error handling refund.created: {e}")
        return {"status": "error", "reason": str(e)}
