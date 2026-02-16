"""
Location Endpoints
Manage car pickup locations/hubs
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, distinct
import redis.asyncio as redis

from app.core.database import get_db
from app.core.redis import get_redis, CacheManager
from app.models import Location
from app.schemas import LocationResponse, CitiesResponse

router = APIRouter()


@router.get("/cities", response_model=CitiesResponse)
async def get_cities(
    redis_client: redis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db)
) -> CitiesResponse:
    """
    Get list of operational cities.
    Cached for 24 hours.
    """
    cache = CacheManager(redis_client)
    
    # Check cache first
    try:
        cached_cities = await cache.get_cities()
    except Exception:
        logger.warning("Cache read failed for cities list", exc_info=True)
        cached_cities = None
    
    if cached_cities:
        return CitiesResponse(cities=cached_cities)
    
    # Query database
    result = await db.execute(
        select(distinct(Location.city))
        .where(Location.is_active == True)
        .order_by(Location.city)
    )
    cities = [row[0] for row in result.fetchall()]
    
    # Cache result
    try:
        await cache.set_cities(cities)
    except Exception:
        logger.warning("Failed to cache cities list", exc_info=True)
    
    return CitiesResponse(cities=cities)


@router.get("/", response_model=List[LocationResponse])
async def get_locations(
    city: str = Query(None, description="Filter by city"),
    lat: float = Query(None, ge=-90, le=90, description="User latitude"),
    lng: float = Query(None, ge=-180, le=180, description="User longitude"),
    radius_km: float = Query(5.0, ge=1, le=50, description="Search radius in km"),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> List[LocationResponse]:
    """
    Get locations with optional filtering by city or proximity.
    City-based queries are cached for 24 hours.
    """
    cache = CacheManager(redis_client)
    
    if lat is not None and lng is not None:
        # Geospatial search (not cached - dynamic)
        query = text("""
            SELECT 
                id, name, city, address,
                ST_Y(coordinates::geometry) as latitude,
                ST_X(coordinates::geometry) as longitude,
                ST_Distance(
                    coordinates::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                ) as distance_meters
            FROM locations
            WHERE is_active = TRUE
            AND ST_DWithin(
                coordinates::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :radius_meters
            )
            ORDER BY distance_meters ASC
        """)
        
        result = await db.execute(
            query,
            {"lat": lat, "lng": lng, "radius_meters": radius_km * 1000}
        )
        rows = result.fetchall()
        
    elif city:
        # Cache-first for city-based queries
        city_normalized = city.strip().title()
        try:
            cached_locations = await cache.get_city_locations(city_normalized)
        except Exception:
            logger.warning(f"Cache read failed for city locations: {city_normalized}", exc_info=True)
            cached_locations = None
        
        if cached_locations:
            return [
                LocationResponse(
                    id=loc["id"],
                    name=loc["name"],
                    city=city_normalized,
                    address=loc.get("address"),
                    latitude=loc["lat"],
                    longitude=loc["lng"]
                )
                for loc in cached_locations
            ]
        
        # Cache miss - fetch from DB
        query = text("""
            SELECT 
                id, name, city, address,
                ST_Y(coordinates::geometry) as latitude,
                ST_X(coordinates::geometry) as longitude
            FROM locations
            WHERE is_active = TRUE AND city = :city
            ORDER BY name
        """)
        
        result = await db.execute(query, {"city": city_normalized})
        rows = result.fetchall()
        
        # Populate cache
        if rows:
            cache_data = [
                {
                    "id": row.id,
                    "name": row.name,
                    "lat": float(row.latitude),
                    "lng": float(row.longitude),
                    "address": row.address
                }
                for row in rows
            ]
            try:
                await cache.set_city_locations(city_normalized, cache_data)
            except Exception:
                logger.warning(f"Failed to cache locations for city: {city_normalized}", exc_info=True)
        
        return [
            LocationResponse(
                id=row.id,
                name=row.name,
                city=row.city,
                address=row.address,
                latitude=row.latitude,
                longitude=row.longitude
            )
            for row in rows
        ]
    else:
        # Return all active locations (not cached)
        query = text("""
            SELECT 
                id, name, city, address,
                ST_Y(coordinates::geometry) as latitude,
                ST_X(coordinates::geometry) as longitude
            FROM locations
            WHERE is_active = TRUE
            ORDER BY city, name
        """)
        
        result = await db.execute(query)
        rows = result.fetchall()
    
    return [
        LocationResponse(
            id=row.id,
            name=row.name,
            city=row.city,
            address=row.address,
            latitude=row.latitude,
            longitude=row.longitude
        )
        for row in rows
    ]


@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: int,
    db: AsyncSession = Depends(get_db)
) -> LocationResponse:
    """Get location by ID."""
    query = text("""
        SELECT 
            id, name, city, address,
            ST_Y(coordinates::geometry) as latitude,
            ST_X(coordinates::geometry) as longitude
        FROM locations
        WHERE id = :location_id AND is_active = TRUE
    """)
    
    result = await db.execute(query, {"location_id": location_id})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Location not found"
        )
    
    return LocationResponse(
        id=row.id,
        name=row.name,
        city=row.city,
        address=row.address,
        latitude=row.latitude,
        longitude=row.longitude
    )
