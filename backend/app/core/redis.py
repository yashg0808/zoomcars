"""
Redis Connection Management
For caching and distributed locking
"""

import redis.asyncio as redis
from redis.asyncio.lock import Lock
from datetime import timedelta
from typing import Optional
import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis client instance
redis_client: Optional[redis.Redis] = None


async def init_redis_connection():
    """Initialize Redis connection"""
    global redis_client
    logger.info("Initializing Redis connection...")
    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )
    # Test connection
    await redis_client.ping()
    logger.info("Redis connection initialized")


async def close_redis_connection():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        logger.info("Closing Redis connection...")
        await redis_client.close()
        logger.info("Redis connection closed")


async def get_redis() -> redis.Redis:
    """Dependency to get Redis client"""
    if redis_client is None:
        raise RuntimeError("Redis not initialized")
    return redis_client


class CacheManager:
    """Redis cache management utilities"""
    
    # Cache key patterns
    CITIES_KEY = "config:cities"
    CAR_DETAILS_KEY = "car:details:{car_id}"
    CAR_SCHEDULE_KEY = "car:schedule:{car_id}"
    USER_OTP_KEY = "user:otp:{phone}"
    BOOKING_LOCK_KEY = "booking:lock:{car_id}"  # Per-car lock to prevent overlapping holds
    IDEMPOTENCY_KEY = "idempotency:{key}"
    RATE_LIMIT_USER_KEY = "rate_limit:user:{user_id}"
    RATE_LIMIT_IP_KEY = "rate_limit:ip:{ip}"
    OTP_RATE_LIMIT_KEY = "otp_rate_limit:{phone}"
    
    # Hold management keys
    HOLD_KEY = "hold:{booking_id}"  # Individual hold data
    CAR_HOLDS_KEY = "car:holds:{car_id}"  # Set of active hold IDs per car
    
    # City-based caching keys
    CITY_LOCATIONS_KEY = "locations:city:{city}"  # All locations in a city
    LOCATION_CARS_KEY = "cars:location:{location_id}"  # All cars at a location
    
    # TTLs (in seconds)
    TTL_CITIES = 86400  # 24 hours
    TTL_CAR_DETAILS = 86400  # 24 hours
    TTL_CAR_SCHEDULE = 3600  # 1 hour (write-through keeps it accurate)
    TTL_OTP = 300  # 5 minutes
    TTL_BOOKING_LOCK = 30  # 30 seconds
    TTL_IDEMPOTENCY = 600  # 10 minutes
    TTL_RATE_LIMIT = 60  # 1 minute
    TTL_OTP_RATE_LIMIT = 3600  # 1 hour
    TTL_HOLD = 300  # 5 minutes for booking hold (aligned with OTP TTL)
    TTL_CAR_HOLDS_SET = 3600  # 1 hour for car holds set (auto-cleanup if no activity)
    TTL_CITY_LOCATIONS = 86400  # 24 hours (locations rarely change)
    TTL_LOCATION_CARS = 3600  # 1 hour (car assignments rarely change)
    
    def __init__(self, client: redis.Redis):
        self.client = client
    
    # === OTP Management ===
    
    async def store_otp(self, phone: str, otp: str) -> None:
        """Store OTP with expiry"""
        key = self.USER_OTP_KEY.format(phone=phone)
        await self.client.setex(key, self.TTL_OTP, otp)
    
    async def get_otp(self, phone: str) -> Optional[str]:
        """Get stored OTP"""
        key = self.USER_OTP_KEY.format(phone=phone)
        return await self.client.get(key)
    
    async def delete_otp(self, phone: str) -> None:
        """Delete OTP after verification"""
        key = self.USER_OTP_KEY.format(phone=phone)
        await self.client.delete(key)
    
    async def check_otp_rate_limit(self, phone: str) -> tuple[bool, int]:
        """Check OTP rate limit. Returns (is_allowed, current_count)"""
        key = self.OTP_RATE_LIMIT_KEY.format(phone=phone)
        current = await self.client.get(key)
        
        if current and int(current) >= settings.OTP_RATE_LIMIT_HOUR:
            return False, int(current)
        
        return True, int(current) if current else 0
    
    async def increment_otp_rate_limit(self, phone: str) -> None:
        """Increment OTP rate limit counter"""
        key = self.OTP_RATE_LIMIT_KEY.format(phone=phone)
        exists = await self.client.exists(key)
        
        if exists:
            await self.client.incr(key)
        else:
            await self.client.setex(key, self.TTL_OTP_RATE_LIMIT, 1)
    
    # === Car Schedule Management ===
    
    async def get_car_schedule(self, car_id: int) -> Optional[list]:
        """Get cached car schedule"""
        key = self.CAR_SCHEDULE_KEY.format(car_id=car_id)
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def set_car_schedule(self, car_id: int, schedule: list) -> None:
        """Cache car schedule"""
        key = self.CAR_SCHEDULE_KEY.format(car_id=car_id)
        await self.client.setex(key, self.TTL_CAR_SCHEDULE, json.dumps(schedule))
    
    async def check_availability_from_cache(
        self, car_id: int, start_time: str, end_time_with_buffer: str
    ) -> tuple[bool, bool]:
        """
        Check car availability from cache (fail-fast).
        
        Returns: (is_available, cache_hit)
        - (True, True): Available according to cache
        - (False, True): Unavailable according to cache (fail-fast rejection)
        - (True, False): Cache miss, must check database
        """
        from datetime import datetime
        
        schedule = await self.get_car_schedule(car_id)
        
        if schedule is None:
            # Cache miss - need to check DB
            return True, False
        
        # Parse requested times
        req_start = datetime.fromisoformat(start_time)
        req_end = datetime.fromisoformat(end_time_with_buffer)
        
        # Check for overlaps with existing bookings
        for booking in schedule:
            if booking.get("status") not in ("CONFIRMED", "PENDING"):
                continue
            
            existing_start = datetime.fromisoformat(booking["start"])
            existing_end = datetime.fromisoformat(booking["end"])
            
            # Check overlap: [req_start, req_end) && [existing_start, existing_end)
            if req_start < existing_end and req_end > existing_start:
                return False, True  # Unavailable, cache hit
        
        return True, True  # Available, cache hit
    
    async def invalidate_car_schedule(self, car_id: int) -> None:
        """Invalidate car schedule cache"""
        key = self.CAR_SCHEDULE_KEY.format(car_id=car_id)
        await self.client.delete(key)
    
    async def add_booking_to_schedule(self, car_id: int, booking_start: str, booking_end: str, status: str = "CONFIRMED") -> None:
        """
        Add a new booking to the cached schedule instead of invalidating.
        This prevents cache misses during high traffic.
        """
        key = self.CAR_SCHEDULE_KEY.format(car_id=car_id)
        
        # Get existing schedule or start fresh
        data = await self.client.get(key)
        schedule = json.loads(data) if data else []
        
        # Add new booking
        schedule.append({
            "start": booking_start,
            "end": booking_end,
            "status": status
        })
        
        # Sort by start time
        schedule.sort(key=lambda x: x["start"])
        
        # Update cache
        await self.client.setex(key, self.TTL_CAR_SCHEDULE, json.dumps(schedule))
    
    # === Idempotency ===
    
    async def get_idempotency_response(self, idempotency_key: str) -> Optional[dict]:
        """Get cached idempotency response"""
        key = self.IDEMPOTENCY_KEY.format(key=idempotency_key)
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def set_idempotency_response(self, idempotency_key: str, response: dict) -> None:
        """Cache idempotency response"""
        key = self.IDEMPOTENCY_KEY.format(key=idempotency_key)
        await self.client.setex(key, self.TTL_IDEMPOTENCY, json.dumps(response))
    
    # === Distributed Locking ===
    
    def get_booking_lock(self, car_id: int) -> Lock:
        """Get a distributed lock for booking a car"""
        key = self.BOOKING_LOCK_KEY.format(car_id=car_id)
        return self.client.lock(key, timeout=self.TTL_BOOKING_LOCK, blocking_timeout=5)
    
    # === Cities Cache ===
    
    async def get_cities(self) -> Optional[list]:
        """Get cached cities"""
        data = await self.client.get(self.CITIES_KEY)
        return json.loads(data) if data else None
    
    async def set_cities(self, cities: list) -> None:
        """Cache cities"""
        await self.client.setex(self.CITIES_KEY, self.TTL_CITIES, json.dumps(cities))
    
    # === City-Based Location/Car Caching ===
    
    async def get_city_locations(self, city: str) -> Optional[list[dict]]:
        """
        Get all locations in a city from cache.
        Returns list of {id, name, lat, lng, address} or None if cache miss.
        """
        key = self.CITY_LOCATIONS_KEY.format(city=city.lower())
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def set_city_locations(self, city: str, locations: list[dict]) -> None:
        """
        Cache all locations for a city.
        locations: [{id, name, lat, lng, address}, ...]
        """
        key = self.CITY_LOCATIONS_KEY.format(city=city.lower())
        await self.client.setex(key, self.TTL_CITY_LOCATIONS, json.dumps(locations))
    
    async def get_location_cars(self, location_id: int) -> Optional[list[dict]]:
        """
        Get all cars at a location from cache.
        Returns list of car dicts or None if cache miss.
        """
        key = self.LOCATION_CARS_KEY.format(location_id=location_id)
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def set_location_cars(self, location_id: int, cars: list[dict]) -> None:
        """Cache all cars for a location."""
        key = self.LOCATION_CARS_KEY.format(location_id=location_id)
        await self.client.setex(key, self.TTL_LOCATION_CARS, json.dumps(cars))
    
    async def get_location_cars_batch(self, location_ids: list[int]) -> dict[int, list[dict] | None]:
        """
        Batch get cars for multiple locations.
        Returns: {location_id: cars_list or None if cache miss}
        """
        if not location_ids:
            return {}
        
        keys = [self.LOCATION_CARS_KEY.format(location_id=lid) for lid in location_ids]
        cached_data = await self.client.mget(keys)
        
        result = {}
        for location_id, data in zip(location_ids, cached_data):
            result[location_id] = json.loads(data) if data else None
        
        return result
    
    async def set_location_cars_batch(self, location_cars: dict[int, list[dict]]) -> None:
        """Batch set cars for multiple locations."""
        if not location_cars:
            return
        
        async with self.client.pipeline(transaction=False) as pipe:
            for location_id, cars in location_cars.items():
                key = self.LOCATION_CARS_KEY.format(location_id=location_id)
                pipe.setex(key, self.TTL_LOCATION_CARS, json.dumps(cars))
            await pipe.execute()
    
    # === Hold Management (Redis-only reservation system) ===
    
    async def create_hold(
        self,
        booking_id: str,
        car_id: int,
        phone: str,
        start_time: str,
        end_time_with_buffer: str,
        lock_token: str,
        total_amount: float,
        car_details: dict
    ) -> dict:
        """
        Create a hold for a car booking in Redis.
        Hold auto-expires via TTL - no DB write until confirm.
        
        Returns the hold data dict.
        """
        from datetime import datetime, timezone
        
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.TTL_HOLD)
        
        hold_data = {
            "booking_id": booking_id,
            "car_id": car_id,
            "phone": phone,
            "start": start_time,
            "end": end_time_with_buffer,
            "lock_token": lock_token,
            "total_amount": total_amount,
            "car_details": car_details,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat()
        }
        
        hold_key = self.HOLD_KEY.format(booking_id=booking_id)
        car_holds_key = self.CAR_HOLDS_KEY.format(car_id=car_id)
        
        # Use pipeline for atomic operation
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.setex(hold_key, self.TTL_HOLD, json.dumps(hold_data))
            pipe.sadd(car_holds_key, booking_id)
            # Refresh TTL on car holds set (auto-cleanup if no booking activity)
            pipe.expire(car_holds_key, self.TTL_CAR_HOLDS_SET)
            await pipe.execute()
        
        return hold_data
    
    async def get_hold(self, booking_id: str) -> Optional[dict]:
        """Get hold data by booking ID. Returns None if expired."""
        key = self.HOLD_KEY.format(booking_id=booking_id)
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def delete_hold(self, booking_id: str, car_id: int) -> None:
        """Delete a hold after confirmation or manual cancellation."""
        hold_key = self.HOLD_KEY.format(booking_id=booking_id)
        car_holds_key = self.CAR_HOLDS_KEY.format(car_id=car_id)
        
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.delete(hold_key)
            pipe.srem(car_holds_key, booking_id)
            await pipe.execute()
    
    async def get_car_holds(self, car_id: int) -> list[dict]:
        """
        Get all active holds for a car.
        Automatically cleans up stale references (where hold TTL expired).
        
        Returns list of valid hold data dicts.
        """
        car_holds_key = self.CAR_HOLDS_KEY.format(car_id=car_id)
        hold_ids = await self.client.smembers(car_holds_key)
        
        if not hold_ids:
            return []
        
        valid_holds = []
        stale_ids = []
        
        for hold_id in hold_ids:
            hold_data = await self.get_hold(hold_id)
            if hold_data is None:
                # Hold expired (TTL), mark for cleanup
                stale_ids.append(hold_id)
            else:
                valid_holds.append(hold_data)
        
        # Lazy cleanup of stale references
        if stale_ids:
            await self.client.srem(car_holds_key, *stale_ids)
        
        return valid_holds
    
    async def check_availability_with_holds(
        self,
        car_id: int,
        start_time: str,
        end_time_with_buffer: str
    ) -> tuple[bool, bool, list[str]]:
        """
        Check car availability against both confirmed bookings (cache) AND active holds.
        
        Returns: (is_available, cache_hit, stale_hold_ids)
        - is_available: True if no overlap found
        - cache_hit: True if schedule cache was available
        - stale_hold_ids: List of stale hold IDs that were cleaned up
        """
        from datetime import datetime
        
        req_start = datetime.fromisoformat(start_time)
        req_end = datetime.fromisoformat(end_time_with_buffer)
        stale_ids = []
        
        # 1. Check against confirmed bookings (from schedule cache)
        schedule = await self.get_car_schedule(car_id)
        cache_hit = schedule is not None
        
        if schedule:
            for booking in schedule:
                if booking.get("status") not in ("CONFIRMED",):
                    continue
                
                existing_start = datetime.fromisoformat(booking["start"])
                existing_end = datetime.fromisoformat(booking["end"])
                
                # Check overlap: [req_start, req_end) && [existing_start, existing_end)
                if req_start < existing_end and req_end > existing_start:
                    return False, cache_hit, stale_ids  # Blocked by confirmed booking
        
        # 2. Check against active holds
        car_holds_key = self.CAR_HOLDS_KEY.format(car_id=car_id)
        hold_ids = await self.client.smembers(car_holds_key)
        
        for hold_id in hold_ids:
            hold_data = await self.get_hold(hold_id)
            
            if hold_data is None:
                # Hold expired, mark for cleanup
                stale_ids.append(hold_id)
                continue
            
            hold_start = datetime.fromisoformat(hold_data["start"])
            hold_end = datetime.fromisoformat(hold_data["end"])
            
            # Check overlap
            if req_start < hold_end and req_end > hold_start:
                # Clean up stale holds before returning
                if stale_ids:
                    await self.client.srem(car_holds_key, *stale_ids)
                return False, cache_hit, stale_ids  # Blocked by active hold
        
        # Clean up stale holds
        if stale_ids:
            await self.client.srem(car_holds_key, *stale_ids)
        
        return True, cache_hit, stale_ids  # Available
    
    async def cleanup_stale_car_holds(self, car_id: int) -> int:
        """
        Clean up stale hold references for a car.
        Called by background job or on-demand.
        
        Returns number of stale holds removed.
        """
        car_holds_key = self.CAR_HOLDS_KEY.format(car_id=car_id)
        hold_ids = await self.client.smembers(car_holds_key)
        
        if not hold_ids:
            return 0
        
        stale_ids = []
        for hold_id in hold_ids:
            exists = await self.client.exists(self.HOLD_KEY.format(booking_id=hold_id))
            if not exists:
                stale_ids.append(hold_id)
        
        if stale_ids:
            await self.client.srem(car_holds_key, *stale_ids)
        
        return len(stale_ids)

    # === Batch Operations for Search ===
    
    async def get_car_schedules_batch(self, car_ids: list[int]) -> dict[int, list | None]:
        """
        Batch get schedules for multiple cars.
        Uses MGET for efficiency.
        
        Returns: {car_id: schedule_list or None if cache miss}
        """
        if not car_ids:
            return {}
        
        keys = [self.CAR_SCHEDULE_KEY.format(car_id=cid) for cid in car_ids]
        cached_data = await self.client.mget(keys)
        
        result = {}
        for car_id, data in zip(car_ids, cached_data):
            result[car_id] = json.loads(data) if data else None
        
        return result
    
    async def set_car_schedules_batch(self, schedules: dict[int, list]) -> None:
        """
        Batch set schedules for multiple cars.
        Uses pipeline for efficiency.
        """
        if not schedules:
            return
        
        async with self.client.pipeline(transaction=False) as pipe:
            for car_id, schedule in schedules.items():
                key = self.CAR_SCHEDULE_KEY.format(car_id=car_id)
                pipe.setex(key, self.TTL_CAR_SCHEDULE, json.dumps(schedule))
            await pipe.execute()
    
    async def check_holds_for_cars_batch(
        self,
        car_ids: list[int],
        start_time: str,
        end_time_with_buffer: str
    ) -> set[int]:
        """
        Check which cars have overlapping holds.
        
        Returns: Set of car_ids that are BLOCKED by holds
        """
        from datetime import datetime
        
        if not car_ids:
            return set()
        
        req_start = datetime.fromisoformat(start_time)
        req_end = datetime.fromisoformat(end_time_with_buffer)
        blocked_cars = set()
        
        # Get all hold sets in one pipeline
        car_holds_keys = [self.CAR_HOLDS_KEY.format(car_id=cid) for cid in car_ids]
        
        async with self.client.pipeline(transaction=False) as pipe:
            for key in car_holds_keys:
                pipe.smembers(key)
            hold_sets = await pipe.execute()
        
        # Collect all unique hold IDs to fetch
        all_hold_ids = set()
        car_to_holds = {}
        for car_id, hold_ids in zip(car_ids, hold_sets):
            car_to_holds[car_id] = hold_ids
            all_hold_ids.update(hold_ids)
        
        if not all_hold_ids:
            return set()
        
        # Fetch all hold data in one MGET
        hold_keys = [self.HOLD_KEY.format(booking_id=hid) for hid in all_hold_ids]
        hold_data_list = await self.client.mget(hold_keys)
        
        # Build hold_id -> data map
        hold_data_map = {}
        stale_holds_by_car = {}  # For cleanup
        
        for hold_id, data in zip(all_hold_ids, hold_data_list):
            if data:
                hold_data_map[hold_id] = json.loads(data)
            else:
                # Stale hold, track for cleanup
                hold_data_map[hold_id] = None
        
        # Check each car's holds for overlap
        for car_id in car_ids:
            hold_ids = car_to_holds.get(car_id, set())
            stale_ids = []
            
            for hold_id in hold_ids:
                hold_data = hold_data_map.get(hold_id)
                
                if hold_data is None:
                    stale_ids.append(hold_id)
                    continue
                
                hold_start = datetime.fromisoformat(hold_data["start"])
                hold_end = datetime.fromisoformat(hold_data["end"])
                
                # Check overlap
                if req_start < hold_end and req_end > hold_start:
                    blocked_cars.add(car_id)
                    break  # No need to check more holds for this car
            
            if stale_ids:
                stale_holds_by_car[car_id] = stale_ids
        
        # Lazy cleanup of stale holds
        if stale_holds_by_car:
            async with self.client.pipeline(transaction=False) as pipe:
                for car_id, stale_ids in stale_holds_by_car.items():
                    key = self.CAR_HOLDS_KEY.format(car_id=car_id)
                    pipe.srem(key, *stale_ids)
                await pipe.execute()
        
        return blocked_cars
