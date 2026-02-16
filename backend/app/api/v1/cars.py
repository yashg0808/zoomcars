"""
Cars Search Endpoints
City-based search with Redis caching and real-time availability

Architecture:
1. Cache locations by city (24h TTL) - locations rarely change
2. Cache cars by location (1h TTL) - car assignments rarely change
3. In-memory distance filtering using Haversine formula
4. Schedule cache + holds check for availability
5. DB fallback only on cache miss (with write-through)

Result: 0 DB hits when cache is warm
"""

from datetime import datetime, timedelta
from typing import Optional
from math import radians, sin, cos, sqrt, atan2
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis
import logging

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis, CacheManager
from app.models import TransmissionType, FuelType
from app.schemas import CarSearchResponse, CarSearchResult, CarLocationInfo, CarDetailResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Earth's radius in meters
EARTH_RADIUS_M = 6_371_000


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great-circle distance between two points in meters.
    Uses the Haversine formula.
    """
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return EARTH_RADIUS_M * c


def calculate_dynamic_price(
    base_rate: float, 
    start_time: datetime, 
    duration_hours: float
) -> float:
    """
    Apply surge pricing based on demand factors.
    - Weekend surge: +20%
    - Long-term discount: -15% for >7 days
    """
    price = base_rate
    
    # Weekend surge (Friday 6pm onwards to Sunday midnight)
    if start_time.weekday() >= 4:  # Friday = 4
        price *= 1.2
    
    # Long-term discount (>7 days / 168 hours)
    if duration_hours >= 168:
        price *= 0.85
    
    return round(price, 2)


@router.get("/search", response_model=CarSearchResponse)
async def search_cars(
    # City (required for caching)
    city: str = Query(..., min_length=2, max_length=50, description="City name"),
    
    # Location (required for distance filtering)
    lat: float = Query(..., ge=-90, le=90, description="User latitude"),
    lng: float = Query(..., ge=-180, le=180, description="User longitude"),
    
    # Time (required)
    start_time: datetime = Query(..., description="Pickup time (ISO format with timezone)"),
    end_time: datetime = Query(..., description="Drop-off time (ISO format with timezone)"),
    
    # Filters (optional)
    transmission: Optional[TransmissionType] = Query(None, description="Filter by transmission type"),
    fuel_type: Optional[FuelType] = Query(None, description="Filter by fuel type"),
    max_price: Optional[float] = Query(None, ge=0, description="Max hourly rate"),
    min_seats: Optional[int] = Query(None, ge=2, le=8, description="Minimum seating capacity"),
    
    # Pagination
    limit: int = Query(20, ge=1, le=50, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> CarSearchResponse:
    """
    Search for available cars in a city near user's location.
    
    City-Based Caching Architecture (0 DB hits when warm):
    1. Redis: Get locations for city (24h TTL)
    2. Python: Filter locations within radius using Haversine
    3. Redis: Batch get cars for nearby locations (1h TTL)
    4. Python: Apply filters (transmission, fuel_type, etc.)
    5. Redis: Check schedule cache + holds for availability
    6. DB fallback only on cache miss (with write-through)
    """
    cache = CacheManager(redis_client)
    city_normalized = city.strip().title()  # "mumbai" -> "Mumbai"
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 1: Validation
    # ═══════════════════════════════════════════════════════════════════════
    now = datetime.utcnow()
    if start_time.tzinfo:
        now = datetime.now(start_time.tzinfo)
    
    if start_time < now:
        raise HTTPException(
            status_code=400,
            detail="Start time cannot be in the past"
        )
    
    if end_time <= start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )
    
    rental_duration_hours = (end_time - start_time).total_seconds() / 3600
    if rental_duration_hours < settings.MIN_RENTAL_HOURS:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum rental duration is {settings.MIN_RENTAL_HOURS} hour(s)"
        )
    
    end_time_with_buffer = end_time + timedelta(hours=settings.BUFFER_HOURS)
    start_time_str = start_time.isoformat()
    end_time_with_buffer_str = end_time_with_buffer.isoformat()
    radius_meters = settings.SEARCH_RADIUS_METERS
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 2: Get locations for city (cache-first)
    # ═══════════════════════════════════════════════════════════════════════
    locations = await cache.get_city_locations(city_normalized)
    
    if locations is None:
        # Cache miss (~1%) - 24h TTL, locations rarely change
        location_query = text("""
            SELECT 
                id, name, 
                ST_Y(coordinates::geometry) as lat,
                ST_X(coordinates::geometry) as lng,
                address
            FROM locations
            WHERE city = :city AND is_active = TRUE
        """)
        result = await db.execute(location_query, {"city": city_normalized})
        rows = result.fetchall()
        
        if not rows:
            return CarSearchResponse(cars=[], total_count=0)
        
        locations = [
            {
                "id": row.id,
                "name": row.name,
                "lat": float(row.lat),
                "lng": float(row.lng),
                "address": row.address
            }
            for row in rows
        ]
        
        # Write-through: cache locations
        try:
            await cache.set_city_locations(city_normalized, locations)
            logger.debug(f"Cache miss: Populated {len(locations)} locations for {city_normalized}")
        except Exception:
            logger.warning(f"Failed to cache locations for city: {city_normalized}", exc_info=True)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 3: Filter locations within radius (Haversine in Python)
    # ═══════════════════════════════════════════════════════════════════════
    nearby_locations = []
    for loc in locations:
        distance = haversine_distance(lat, lng, loc["lat"], loc["lng"])
        if distance <= radius_meters:
            nearby_locations.append({
                **loc,
                "distance_meters": distance
            })
    
    if not nearby_locations:
        return CarSearchResponse(cars=[], total_count=0)
    
    # Sort by distance
    nearby_locations.sort(key=lambda x: x["distance_meters"])
    nearby_location_ids = [loc["id"] for loc in nearby_locations]
    location_map = {loc["id"]: loc for loc in nearby_locations}
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 4: Get cars for nearby locations (cache-first, batch)
    # ═══════════════════════════════════════════════════════════════════════

    # Batch get cars for all nearby locations (1h TTL)
    location_cars_cache = await cache.get_location_cars_batch(nearby_location_ids)
    
    all_cars = []
    cache_miss_location_ids = []
    
    for loc_id in nearby_location_ids:
        cars_data = location_cars_cache.get(loc_id)
        if cars_data is None:
            cache_miss_location_ids.append(loc_id)
        else:
            for car in cars_data:
                car["_location_id"] = loc_id  # Track location for distance
            all_cars.extend(cars_data)
    
    # DB fallback for location cache misses (~5-10%) - 1h TTL per location
    if cache_miss_location_ids:
        cars_query = text("""
            SELECT 
                id, location_id, make, model, year, image_url,
                transmission::text, fuel_type::text, seating_capacity,
                base_hourly_rate, rating, total_trips
            FROM cars
            WHERE location_id = ANY(:location_ids) AND is_active = TRUE
        """)
        result = await db.execute(cars_query, {"location_ids": cache_miss_location_ids})
        rows = result.fetchall()
        
        # Group by location for caching
        cars_by_location = {loc_id: [] for loc_id in cache_miss_location_ids}
        for row in rows:
            car_data = {
                "id": row.id,
                "location_id": row.location_id,
                "make": row.make,
                "model": row.model,
                "year": row.year,
                "image_url": row.image_url,
                "transmission": row.transmission,
                "fuel_type": row.fuel_type,
                "seating_capacity": row.seating_capacity,
                "base_hourly_rate": float(row.base_hourly_rate),
                "rating": float(row.rating),
                "total_trips": row.total_trips,
                "_location_id": row.location_id
            }
            cars_by_location[row.location_id].append(car_data)
            all_cars.append(car_data)
        
        # Write-through: cache cars per location
        try:
            await cache.set_location_cars_batch(cars_by_location)
            logger.debug(f"Cache miss: Populated cars for {len(cache_miss_location_ids)} locations")
        except Exception:
            logger.warning("Failed to cache location cars batch", exc_info=True)
    
    if not all_cars:
        return CarSearchResponse(cars=[], total_count=0)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 5: Apply filters (in Python)
    # ═══════════════════════════════════════════════════════════════════════
    filtered_cars = []
    for car in all_cars:
        if transmission and car["transmission"] != transmission.value:
            continue
        if fuel_type and car["fuel_type"] != fuel_type.value:
            continue
        if max_price is not None and car["base_hourly_rate"] > max_price:
            continue
        if min_seats is not None and car["seating_capacity"] < min_seats:
            continue
        filtered_cars.append(car)
    
    if not filtered_cars:
        return CarSearchResponse(cars=[], total_count=0)
    
    car_ids = [car["id"] for car in filtered_cars]
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 6: Check schedule cache for availability
    # ═══════════════════════════════════════════════════════════════════════
    schedules = await cache.get_car_schedules_batch(car_ids)
    
    available_car_ids = []
    schedule_cache_miss_ids = []
    
    for car_id in car_ids:
        schedule = schedules.get(car_id)
        
        if schedule is None:
            schedule_cache_miss_ids.append(car_id)
        else:
            is_available = True
            for booking in schedule:
                if booking.get("status") != "CONFIRMED":
                    continue
                existing_start = datetime.fromisoformat(booking["start"])
                existing_end = datetime.fromisoformat(booking["end"])
                if start_time < existing_end and end_time_with_buffer > existing_start:
                    is_available = False
                    break
            if is_available:
                available_car_ids.append(car_id)
    
    # DB fallback for schedule cache misses (~10-20%) - 1h TTL, depends on location popularity
    if schedule_cache_miss_ids:
        schedule_query = text("""
            SELECT 
                car_id,
                lower(total_period) as period_start,
                upper(total_period) as period_end,
                status
            FROM bookings
            WHERE car_id = ANY(:car_ids)
            AND status = 'CONFIRMED'
            AND upper(total_period) > NOW()
            ORDER BY car_id, lower(total_period)
        """)
        
        result = await db.execute(schedule_query, {"car_ids": schedule_cache_miss_ids})
        rows = result.fetchall()
        
        db_schedules = {cid: [] for cid in schedule_cache_miss_ids}
        blocked_by_db = set()
        
        for row in rows:
            db_schedules[row.car_id].append({
                "start": row.period_start.isoformat(),
                "end": row.period_end.isoformat(),
                "status": row.status
            })
            if start_time < row.period_end and end_time_with_buffer > row.period_start:
                blocked_by_db.add(row.car_id)
        
        # Write-through: cache schedules for missed cars
        try:
            await cache.set_car_schedules_batch(db_schedules)
        except Exception:
            logger.warning("Failed to cache car schedules batch", exc_info=True)
        
        for car_id in schedule_cache_miss_ids:
            if car_id not in blocked_by_db:
                available_car_ids.append(car_id)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 7: Filter by Redis holds
    # ═══════════════════════════════════════════════════════════════════════
    if available_car_ids:
        blocked_by_holds = await cache.check_holds_for_cars_batch(
            available_car_ids,
            start_time_str,
            end_time_with_buffer_str
        )
        available_car_ids = [cid for cid in available_car_ids if cid not in blocked_by_holds]
    
    # ═══════════════════════════════════════════════════════════════════════
    # Step 8: Build response with sorting and pagination
    # ═══════════════════════════════════════════════════════════════════════
    available_car_ids_set = set(available_car_ids)
    available_cars = [car for car in filtered_cars if car["id"] in available_car_ids_set]
    
    # Sort by distance (using location's distance), then by price
    def sort_key(car):
        loc = location_map.get(car["_location_id"], {})
        return (loc.get("distance_meters", float("inf")), car["base_hourly_rate"])
    
    available_cars.sort(key=sort_key)
    
    total_available = len(available_cars)
    paginated_cars = available_cars[offset:offset + limit]
    
    results = []
    for car in paginated_cars:
        loc = location_map.get(car["_location_id"], {})
        
        dynamic_price = calculate_dynamic_price(
            car["base_hourly_rate"],
            start_time,
            rental_duration_hours
        )
        
        results.append(CarSearchResult(
            id=car["id"],
            make=car["make"],
            model=car["model"],
            year=car["year"],
            image_url=car["image_url"],
            transmission=TransmissionType(car["transmission"]),
            fuel_type=FuelType(car["fuel_type"]),
            seating_capacity=car["seating_capacity"],
            base_hourly_rate=car["base_hourly_rate"],
            dynamic_price=dynamic_price,
            rating=car["rating"],
            total_trips=car["total_trips"],
            distance_km=round(loc.get("distance_meters", 0) / 1000, 2),
            location=CarLocationInfo(
                name=loc.get("name", ""),
                city=city_normalized,
                address=loc.get("address", "")
            )
        ))
    
    logger.debug(
        f"Search[{city_normalized}]: {len(locations)} locs → {len(nearby_locations)} nearby → "
        f"{len(all_cars)} cars → {len(filtered_cars)} filtered → {total_available} available"
    )
    
    return CarSearchResponse(
        cars=results,
        total_count=total_available
    )


@router.get("/{car_id}", response_model=CarDetailResponse)
async def get_car_details(
    car_id: int,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> CarDetailResponse:
    """Get detailed information about a specific car."""
    query = text("""
        SELECT 
            c.id, c.make, c.model, c.year, c.image_url,
            c.transmission::text, c.fuel_type::text, c.seating_capacity,
            c.base_hourly_rate, c.rating, c.total_trips,
            l.name as location_name, l.city, l.address
        FROM cars c
        INNER JOIN locations l ON c.location_id = l.id
        WHERE c.id = :car_id AND c.is_active = TRUE
    """)
    
    result = await db.execute(query, {"car_id": car_id})
    car = result.fetchone()
    
    if not car:
        raise HTTPException(
            status_code=404,
            detail="Car not found"
        )
    
    return CarDetailResponse(
        id=car.id,
        make=car.make,
        model=car.model,
        year=car.year,
        image_url=car.image_url,
        transmission=TransmissionType(car.transmission),
        fuel_type=FuelType(car.fuel_type),
        seating_capacity=car.seating_capacity,
        base_hourly_rate=float(car.base_hourly_rate),
        rating=float(car.rating),
        total_trips=car.total_trips,
        location=CarLocationInfo(
            name=car.location_name,
            city=car.city,
            address=car.address
        )
    )
