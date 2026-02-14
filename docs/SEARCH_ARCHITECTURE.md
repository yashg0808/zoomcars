# Car Search Architecture

## Overview

The ZoomCars search system uses a **city-based caching architecture** to minimize database hits while providing accurate real-time availability. The system combines Redis caching with in-memory distance calculations to deliver fast, scalable search results.

---

## Table of Contents

1. [Architecture Diagram](#architecture-diagram)
2. [Cache Hierarchy](#cache-hierarchy)
3. [Search Flow](#search-flow)
4. [API Reference](#api-reference)
5. [Frontend Components](#frontend-components)
6. [Cache Keys & TTLs](#cache-keys--ttls)
7. [Availability Checking](#availability-checking)
8. [Performance Considerations](#performance-considerations)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                        │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌──────────────────┐ │
│  │   SearchForm.tsx    │───▶│   search/page.tsx   │───▶│   CarCard.tsx    │ │
│  │  - City dropdown    │    │  - Fetch results    │    │  - Display car   │ │
│  │  - Location dropdown│    │  - Apply filters    │    │  - Book button   │ │
│  │  - Date picker      │    │  - Show results     │    │                  │ │
│  └─────────────────────┘    └─────────────────────┘    └──────────────────┘ │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ HTTP
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND API                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    GET /api/v1/cars/search                              ││
│  │  Params: city, lat, lng, start_time, end_time, filters, limit, offset  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                     │                                        │
│                    ┌────────────────┼────────────────┐                      │
│                    ▼                ▼                ▼                      │
│            ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│            │  Location   │  │    Car      │  │  Schedule   │               │
│            │   Cache     │  │   Cache     │  │   Cache     │               │
│            └─────────────┘  └─────────────┘  └─────────────┘               │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
            ┌─────────────┐                   ┌─────────────┐
            │    REDIS    │                   │  POSTGRES   │
            │   (Cache)   │                   │   (Source)  │
            └─────────────┘                   └─────────────┘
```

---

## Cache Hierarchy

The system uses a **three-tier cache hierarchy** optimized for the city → location → car relationship:

```
                    ┌──────────────────┐
                    │      Cities      │
                    │   (Finite set)   │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
     │  Bangalore  │ │   Mumbai    │ │   Delhi     │
     │  Locations  │ │  Locations  │ │  Locations  │
     └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
            │               │               │
     ┌──────┼──────┐        │        ┌──────┼──────┐
     ▼      ▼      ▼        ▼        ▼      ▼      ▼
   ┌───┐  ┌───┐  ┌───┐    ┌───┐    ┌───┐  ┌───┐  ┌───┐
   │L1 │  │L2 │  │L3 │    │L1 │    │L1 │  │L2 │  │L3 │
   │   │  │   │  │   │    │   │    │   │  │   │  │   │
   └─┬─┘  └─┬─┘  └─┬─┘    └─┬─┘    └─┬─┘  └─┬─┘  └─┬─┘
     │      │      │        │        │      │      │
   Cars   Cars   Cars     Cars     Cars   Cars   Cars
```

### Why City-Based Caching?

| Approach            | Cache Keys | Problem                              |
| ------------------- | ---------- | ------------------------------------ |
| Lat/Lng based       | Infinite   | Every unique coordinate = cache miss |
| City-center only    | ~6         | Inaccurate for suburb searches       |
| **City + Location** | **~100**   | **Finite, accurate, cacheable**      |

---

## Search Flow

### Step-by-Step Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SEARCH FLOW (8 STEPS)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. VALIDATE INPUT                                                          │
│     └── Check: city required, date validation                               │
│                                                                             │
│  2. GET CITY LOCATIONS (Cache Layer 1)                                      │
│     ├── Try: Redis GET locations:city:{city}                                │
│     └── Miss: Query DB → Cache for 24h                                      │
│                                                                             │
│  3. HAVERSINE DISTANCE FILTER                                               │
│     └── Filter locations within radius_km using in-memory calculation       │
│                                                                             │
│  4. GET CARS PER LOCATION (Cache Layer 2)                                   │
│     ├── Try: Redis MGET cars:location:{id} for each location                │
│     └── Miss: Query DB → Cache for 1h                                       │
│                                                                             │
│  5. APPLY USER FILTERS                                                      │
│     └── Filter by: transmission, fuel_type, price, seats                    │
│                                                                             │
│  6. CHECK SCHEDULE CACHE (Cache Layer 3)                                    │
│     ├── Try: Redis MGET car:schedule:{id} for each car                      │
│     └── Miss: Query DB → Cache for 1h                                       │
│                                                                             │
│  7. CHECK ACTIVE HOLDS                                                      │
│     └── Check car:holds:{car_id} sets + hold:{id} data for overlaps       │
│                                                                             │
│  8. PAGINATE & RETURN                                                       │
│     └── Apply offset/limit, return with total_count                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Haversine Distance Calculation

The system uses the **Haversine formula** to calculate great-circle distance between two points:

```python
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.
    Returns distance in kilometers.
    """
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c
```

**Why not PostGIS ST_DWithin?**

- PostGIS requires DB hit for every search
- Haversine in Python allows filtering against cached location data
- Result: **0 DB hits** when caches are warm

---

## API Reference

### GET /api/v1/cars/search

Search for available cars near a location.

#### Request Parameters

| Parameter      | Type     | Required | Default | Description                              |
| -------------- | -------- | -------- | ------- | ---------------------------------------- |
| `city`         | string   | ✅ Yes   | -       | City name (e.g., "Bangalore")            |
| `lat`          | float    | ✅ Yes   | -       | Latitude of search center                |
| `lng`          | float    | ✅ Yes   | -       | Longitude of search center               |
| `start_time`   | datetime | ✅ Yes   | -       | Booking start (ISO 8601)                 |
| `end_time`     | datetime | ✅ Yes   | -       | Booking end (ISO 8601)                   |
| `radius_km`    | float    | No       | 15.0    | Search radius in kilometers              |
| `transmission` | enum     | No       | -       | "AUTOMATIC" or "MANUAL"                  |
| `fuel_type`    | enum     | No       | -       | "PETROL", "DIESEL", "ELECTRIC", "HYBRID" |
| `min_seats`    | int      | No       | -       | Minimum seat count                       |
| `max_price`    | float    | No       | -       | Maximum hourly price                     |
| `limit`        | int      | No       | 20      | Results per page (max 100)               |
| `offset`       | int      | No       | 0       | Pagination offset                        |

#### Response

```json
{
  "cars": [
    {
      "id": 1,
      "make": "Hyundai",
      "model": "i20",
      "year": 2023,
      "transmission": "AUTOMATIC",
      "fuel_type": "PETROL",
      "seats": 5,
      "price_per_hour": 150.0,
      "location_name": "Koramangala Hub",
      "distance_km": 2.3,
      "image_url": "/images/cars/i20.jpg",
      "features": ["Bluetooth", "AC", "Power Steering"]
    }
  ],
  "total_count": 42,
  "limit": 20,
  "offset": 0
}
```

#### Error Responses

| Status | Description                                      |
| ------ | ------------------------------------------------ |
| 400    | Invalid parameters (missing city, invalid dates) |
| 422    | Validation error (end_time before start_time)    |

---

### GET /api/v1/locations

Get locations, optionally filtered by city.

#### Request Parameters

| Parameter | Type   | Required | Description              |
| --------- | ------ | -------- | ------------------------ |
| `city`    | string | No       | Filter locations by city |

#### Response

```json
[
  {
    "id": 1,
    "name": "Koramangala Hub",
    "address": "100 Feet Road, Koramangala",
    "city": "Bangalore",
    "latitude": 12.9352,
    "longitude": 77.6245
  }
]
```

**Caching**: When `city` parameter is provided, results are cached for 24 hours.

---

## Frontend Components

### SearchForm.tsx

The main search form on the home page.

```
┌─────────────────────────────────────────────────────────────────┐
│                        SEARCH FORM                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │  City Dropdown  │  │Location Dropdown│                      │
│  │  [Bangalore ▼]  │  │  [Koramangala▼] │                      │
│  └─────────────────┘  └─────────────────┘                      │
│         │                      │                                │
│         │ onChange             │ onChange                       │
│         ▼                      ▼                                │
│  Fetch locations        Set lat/lng/location_id                │
│  for selected city                                              │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │  Start Date     │  │   End Date      │  │  Search Btn    │  │
│  │  [Feb 14, 2026] │  │  [Feb 15, 2026] │  │  [🔍 Search]   │  │
│  └─────────────────┘  └─────────────────┘  └────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### State Management

```typescript
// Location state
const [locations, setLocations] = useState<Location[]>([]);
const [selectedLocation, setSelectedLocation] = useState<Location | null>(null);
const [isLoadingLocations, setIsLoadingLocations] = useState(false);

// Fetch locations when city changes
useEffect(() => {
  if (city) {
    setIsLoadingLocations(true);
    locationsApi
      .getLocations({ city })
      .then((res) => setLocations(res.data))
      .finally(() => setIsLoadingLocations(false));
  }
}, [city]);
```

#### URL Parameters Generated

When user clicks "Search Cars":

```
/search?city=Bangalore
       &location_id=1
       &location_name=Koramangala%20Hub
       &lat=12.9352
       &lng=77.6245
       &start_time=2026-02-14T10:00:00.000Z
       &end_time=2026-02-15T10:00:00.000Z
```

### search/page.tsx

The search results page.

#### Parameter Extraction

```typescript
// Get lat/lng from URL (from selected location)
const fallbackCoords = cityCoordinates[city] || cityCoordinates.Bangalore;
const lat = parseFloat(searchParams.get("lat") || String(fallbackCoords.lat));
const lng = parseFloat(searchParams.get("lng") || String(fallbackCoords.lng));
const locationName = searchParams.get("location_name") || null;
```

#### Query Key Strategy

```typescript
// Include lat/lng in query key for accurate cache separation
queryKey: ["cars", city, lat, lng, startTime, endTime, filters];
```

---

## Cache Keys & TTLs

### Redis Key Format

| Key Pattern              | Example                    | TTL | Description                 |
| ------------------------ | -------------------------- | --- | --------------------------- |
| `locations:city:{city}`  | `locations:city:bangalore` | 24h | All locations in a city     |
| `cars:location:{id}`     | `cars:location:1`          | 1h  | All cars at a location      |
| `car:schedule:{car_id}`  | `car:schedule:42`          | 1h  | Car's booking schedule      |
| `hold:{booking_id}`      | `hold:abc-123-uuid`        | 5m  | Hold data by booking ID     |
| `car:holds:{car_id}`     | `car:holds:42`             | 1h  | Set of active hold IDs/car  |

### TTL Constants (redis.py)

```python
TTL_CITY_LOCATIONS = 86400   # 24 hours
TTL_LOCATION_CARS = 3600     # 1 hour
TTL_CAR_SCHEDULE = 3600      # 1 hour
TTL_OTP = 300                # 5 minutes
TTL_HOLD = 300               # 5 minutes (aligned with OTP TTL)
TTL_CAR_HOLDS_SET = 3600     # 1 hour for car holds set
```

### Cache Warming Strategy

```
Cold Start (first user in city):
├── locations:city:bangalore  → DB query, cache 24h
├── cars:location:1           → DB query, cache 1h
├── cars:location:2           → DB query, cache 1h
└── car:schedule:*            → DB query per car, cache 1h

Warm Cache (subsequent users):
├── locations:city:bangalore  → Redis HIT ✓
├── cars:location:*           → Redis HIT ✓
└── car:schedule:*            → Redis HIT ✓
Result: 0 DB queries
```

---

## Availability Checking

### Multi-Layer Availability

A car is considered **unavailable** if ANY of these conditions are true:

```
┌─────────────────────────────────────────────────────────┐
│                  AVAILABILITY CHECK                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. SCHEDULE CONFLICT                                   │
│     └── Existing CONFIRMED/ACTIVE booking overlaps      │
│         with requested time range                       │
│                                                         │
│  2. ACTIVE HOLD                                         │
│     └── Another user has hold:{booking_id} with          │
│         overlapping time range (expires in 5 minutes)   │
│                                                         │
│  3. CAR STATUS                                          │
│     └── Car is not AVAILABLE (maintenance, etc.)        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Hold Checking Implementation

Holds use a two-key architecture:
- `car:holds:{car_id}` - Set of booking IDs that have holds on this car
- `hold:{booking_id}` - Actual hold data with time range and TTL

```python
async def check_holds_for_cars_batch(
    car_ids: list[int],
    start_time: str,
    end_time_with_buffer: str
) -> set[int]:
    """
    Check which cars have overlapping holds.
    Returns: Set of car_ids that are BLOCKED by holds
    """
    blocked_cars = set()
    
    # 1. Get hold ID sets for all cars (pipeline)
    for car_id in car_ids:
        hold_ids = await redis.smembers(f"car:holds:{car_id}")
        
        # 2. Fetch hold data for each hold_id
        for hold_id in hold_ids:
            hold_data = await redis.get(f"hold:{hold_id}")
            if hold_data is None:
                # Stale reference, clean up
                continue
            
            # 3. Check time overlap
            if overlaps(hold_data, start_time, end_time_with_buffer):
                blocked_cars.add(car_id)
    
    return blocked_cars
```

### Schedule Conflict Detection

```python
def has_schedule_conflict(schedules: List[Dict], start: datetime, end: datetime) -> bool:
    """Check if any existing booking overlaps with requested time."""
    for booking in schedules:
        booking_start = datetime.fromisoformat(booking["start_time"])
        booking_end = datetime.fromisoformat(booking["end_time"])

        # Overlap exists if: start < other_end AND end > other_start
        if start < booking_end and end > booking_start:
            return True

    return False
```

---

## Performance Considerations

### Cache Hit Rates

| Scenario              | DB Queries          | Redis Ops           | Response Time |
| --------------------- | ------------------- | ------------------- | ------------- |
| Cold cache (new city) | O(locations + cars) | O(1) write per item | ~500ms        |
| Warm cache (typical)  | 0                   | O(locations) reads  | ~50ms         |
| Cache partial miss    | O(missing items)    | O(n) mixed          | ~150ms        |

### Scaling Considerations

1. **City Expansion**
   - Adding new cities: Only affects first user (cache warming)
   - No code changes required

2. **Location Density**
   - More locations per city = more cache keys
   - But: O(1) lookup per key, O(n) for batch MGET
   - Redis handles 100k+ keys easily

3. **Car Inventory Growth**
   - Cars cached per-location: Load distributed
   - Schedule cache per-car: Linear growth
   - Consider: Redis Cluster for >1M cars

### Memory Estimation

```
Per City:
├── locations:city:{city}    ~5KB (50 locations × 100 bytes)
├── cars:location:{id} × 50  ~500KB (10 cars × 1KB × 50 locations)
└── car:schedule:{id} × 500  ~250KB (500 cars × 500 bytes avg)

Total per city: ~750KB
6 cities: ~4.5MB Redis memory
```

---

## Troubleshooting

### Common Issues

| Issue                | Cause                  | Solution                             |
| -------------------- | ---------------------- | ------------------------------------ |
| Stale car data       | Location cars cache    | Wait 1h or clear `cars:location:*`   |
| Wrong availability   | Schedule cache stale   | Clear `car:schedule:{id}` on booking |
| Location not showing | City cache outdated    | Clear `locations:city:{city}`        |
| Holds not respected  | Redis connection issue | Check Redis connectivity             |

### Debug Endpoints

```bash
# Check cache health
redis-cli KEYS "locations:city:*"
redis-cli KEYS "cars:location:*"
redis-cli KEYS "hold:*"
redis-cli KEYS "car:holds:*"

# Clear city cache (force refresh)
redis-cli DEL "locations:city:bangalore"

# Check active holds for a car
redis-cli SMEMBERS "car:holds:42"

# Check specific hold data
redis-cli GET "hold:abc-123-uuid"
```

---

## Future Improvements

1. **Cache Invalidation Webhooks**
   - Invalidate `cars:location:{id}` when car moves locations
   - Invalidate `car:schedule:{id}` on booking create/cancel

2. **Predictive Cache Warming**
   - Pre-warm popular city caches during off-peak hours
   - Use analytics to identify high-demand locations

3. **Geo-Sharding**
   - Distribute Redis by region for global scale
   - Example: `redis-bangalore.cluster`, `redis-mumbai.cluster`

4. **Real-Time Availability**
   - WebSocket updates when car becomes available
   - Push notification for waitlisted users
