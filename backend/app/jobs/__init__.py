"""
Background Jobs
Scheduled tasks for cleanup and maintenance
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.pool import NullPool
import redis.asyncio as redis

from app.core.config import settings
from app.core.redis import CacheManager

logger = logging.getLogger(__name__)

# Create engine without pooling for Lambda
lambda_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
)

LambdaSessionLocal = async_sessionmaker(
    bind=lambda_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def cleanup_stale_holds():
    """
    Clean up stale hold references from car:holds:* sets.
    
    With the new Redis-only hold system:
    - hold:{booking_id} keys auto-expire via TTL
    - car:holds:{car_id} sets may have stale references
    
    This job scans and cleans those stale references.
    Note: This is a belt-and-suspenders cleanup - the main system
    does lazy cleanup during availability checks.
    
    Run frequency: Every 2 minutes
    """
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    cache = CacheManager(redis_client)
    
    try:
        cleaned_count = 0
        
        # Scan for all car:holds:* keys
        cursor = 0
        while True:
            cursor, keys = await redis_client.scan(
                cursor, 
                match="car:holds:*", 
                count=100
            )
            
            for key in keys:
                # Extract car_id from key
                car_id_str = key.split(":")[-1]
                try:
                    car_id = int(car_id_str)
                    removed = await cache.cleanup_stale_car_holds(car_id)
                    cleaned_count += removed
                except ValueError:
                    logger.warning(f"Invalid car:holds key: {key}")
            
            if cursor == 0:
                break
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} stale hold references")
        
        return {"cleaned_count": cleaned_count}
        
    except Exception as e:
        logger.error(f"Stale holds cleanup error: {e}")
        raise
    finally:
        await redis_client.close()


async def cleanup_expired_bookings():
    """
    Mark PENDING bookings in DB as EXPIRED if payment window has passed.
    
    NOTE: With the new Redis-only hold system, PENDING bookings in DB
    should be rare (edge case: confirm started but crashed mid-write).
    This job handles those edge cases.
    
    Run frequency: Every 1 minute
    """
    async with LambdaSessionLocal() as db:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        cache = CacheManager(redis_client)
        
        try:
            # Find expired PENDING bookings (these are edge cases now)
            result = await db.execute(text("""
                SELECT id, car_id 
                FROM bookings 
                WHERE status = 'PENDING' 
                AND expires_at <= NOW()
            """))
            
            expired_bookings = result.fetchall()
            expired_car_ids = set()
            
            if not expired_bookings:
                logger.debug("No expired DB bookings found")
                return {"cleaned_count": 0}
            
            # Update status to EXPIRED
            booking_ids = [str(b.id) for b in expired_bookings]
            for booking in expired_bookings:
                expired_car_ids.add(booking.car_id)
            
            await db.execute(text("""
                UPDATE bookings 
                SET status = 'EXPIRED', updated_at = NOW()
                WHERE status = 'PENDING' AND expires_at <= NOW()
            """))
            await db.commit()
            
            # Invalidate cache for affected cars
            for car_id in expired_car_ids:
                await cache.invalidate_car_schedule(car_id)
            
            logger.info(f"Cleaned up {len(expired_bookings)} expired DB bookings")
            
            return {
                "cleaned_count": len(expired_bookings),
                "booking_ids": booking_ids,
                "car_ids": list(expired_car_ids)
            }
            
        except Exception as e:
            logger.error(f"Cleanup job error: {e}")
            await db.rollback()
            raise
        finally:
            await redis_client.close()


async def reconcile_pending_payments():
    """
    Check Razorpay for payments that succeeded but webhook may have failed.
    Manually confirms bookings if payment is found to be successful.
    
    Run frequency: Every 10 minutes
    """
    import razorpay
    
    if not settings.RAZORPAY_KEY_ID:
        logger.warning("Razorpay not configured - skipping reconciliation")
        return {"reconciled_count": 0}
    
    razorpay_client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    
    async with LambdaSessionLocal() as db:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        cache = CacheManager(redis_client)
        
        try:
            # Find PENDING bookings older than 2 minutes but not expired
            cutoff_time = datetime.utcnow() - timedelta(minutes=2)
            
            result = await db.execute(text("""
                SELECT id, car_id, payment_order_id, total_amount
                FROM bookings
                WHERE status = 'PENDING'
                AND payment_order_id IS NOT NULL
                AND created_at < :cutoff_time
                AND expires_at > NOW()
            """), {"cutoff_time": cutoff_time})
            
            pending_bookings = result.fetchall()
            reconciled_count = 0
            
            for booking in pending_bookings:
                try:
                    # Check Razorpay order status
                    order = razorpay_client.order.fetch(booking.payment_order_id)
                    
                    if order["status"] == "paid":
                        # Payment was successful - webhook may have failed
                        payment_items = razorpay_client.order.payments(booking.payment_order_id)
                        
                        payment_id = None
                        for payment in payment_items.get("items", []):
                            if payment["status"] == "captured":
                                payment_id = payment["id"]
                                break
                        
                        if payment_id:
                            await db.execute(text("""
                                UPDATE bookings 
                                SET status = 'CONFIRMED', 
                                    payment_id = :payment_id, 
                                    expires_at = NULL,
                                    updated_at = NOW()
                                WHERE id = :booking_id AND status = 'PENDING'
                            """), {"payment_id": payment_id, "booking_id": str(booking.id)})
                            await db.commit()
                            
                            await cache.invalidate_car_schedule(booking.car_id)
                            
                            reconciled_count += 1
                            logger.info(f"Reconciled booking {booking.id} with payment {payment_id}")
                
                except Exception as e:
                    logger.error(f"Error reconciling booking {booking.id}: {e}")
                    continue
            
            if reconciled_count > 0:
                logger.info(f"Reconciled {reconciled_count} bookings")
            
            return {"reconciled_count": reconciled_count}
            
        except Exception as e:
            logger.error(f"Reconciliation job error: {e}")
            raise
        finally:
            await redis_client.close()


async def refresh_car_schedules():
    """
    Proactively refresh car schedule caches for popular cars.
    Prevents cache misses during high traffic.
    
    Run frequency: Every 5 minutes
    """
    async with LambdaSessionLocal() as db:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        cache = CacheManager(redis_client)
        
        try:
            # Get cars with recent bookings (popular cars)
            result = await db.execute(text("""
                SELECT DISTINCT car_id
                FROM bookings
                WHERE created_at > NOW() - INTERVAL '24 hours'
                AND status IN ('CONFIRMED', 'PENDING')
                LIMIT 100
            """))
            
            car_ids = [row.car_id for row in result.fetchall()]
            refreshed_count = 0
            
            for car_id in car_ids:
                # Get schedule from database
                schedule_result = await db.execute(text("""
                    SELECT 
                        lower(total_period) as period_start,
                        upper(total_period) as period_end,
                        status
                    FROM bookings
                    WHERE car_id = :car_id
                    AND status IN ('CONFIRMED', 'PENDING')
                    AND upper(total_period) > NOW()
                    ORDER BY lower(total_period) ASC
                """), {"car_id": car_id})
                
                schedule = []
                for row in schedule_result.fetchall():
                    schedule.append({
                        "start": row.period_start.isoformat(),
                        "end": row.period_end.isoformat(),
                        "status": row.status
                    })
                
                # Update cache
                await cache.set_car_schedule(car_id, schedule)
                refreshed_count += 1
            
            logger.info(f"Refreshed schedules for {refreshed_count} cars")
            return {"refreshed_count": refreshed_count}
            
        except Exception as e:
            logger.error(f"Schedule refresh job error: {e}")
            raise
        finally:
            await redis_client.close()
