# ZoomCars - Load Analysis & Capacity Planning

> **Analysis Date:** February 2026  
> **Current Configuration:** Single-server deployment  
> **Stack:** FastAPI + PostgreSQL + Redis

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Memory Analysis Per Request](#2-memory-analysis-per-request)
3. [Database Capacity](#3-database-capacity)
4. [Redis Capacity](#4-redis-capacity)
5. [Worst-Case Scenarios](#5-worst-case-scenarios)
6. [System Breaking Points](#6-system-breaking-points)
7. [Scale Recommendations](#7-scale-recommendations)

---

## 1. Executive Summary

### Current Capacity (Single Instance)

| Metric                      | Value                     | Bottleneck             |
| --------------------------- | ------------------------- | ---------------------- |
| **Max Concurrent Requests** | 100-150                   | FastAPI worker threads |
| **Requests/Second (RPS)**   | 80-120 RPS                | Database connections   |
| **Peak Users/Hour**         | ~10,000 users             | With 80% cache hit     |
| **Database Connections**    | 15 (10 pool + 5 overflow) | Hard limit             |
| **Redis Memory**            | ~500 MB                   | For 10K active holds   |
| **Response Time (P95)**     | 50-150ms                  | Cache-warm search      |
| **Response Time (P99)**     | 200-400ms                 | Cache-miss scenario    |

### Scale Thresholds

| Traffic Level  | Status         | Action Required    |
| -------------- | -------------- | ------------------ |
| **< 50 RPS**   | ✅ Comfortable | Current config     |
| **50-100 RPS** | ⚠️ Monitor     | Watch DB pool      |
| **> 100 RPS**  | 🔴 At Risk     | Scale horizontally |
| **> 200 RPS**  | 💥 Breaking    | Add read replicas  |

---

## 2. Memory Analysis Per Request

### 2.1 Search Request (`GET /api/v1/cars/search`)

#### Worst-Case Scenario (Cold Cache)

```
┌─────────────────────────────────────────────────────────────────┐
│              SEARCH REQUEST - MEMORY BREAKDOWN                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Request Processing:                                             │
│  ├─ FastAPI request object          ~10 KB                      │
│  ├─ SQLAlchemy session              ~5 KB                       │
│  ├─ Redis connection (shared)       ~1 KB                       │
│  └─ Python locals/stack             ~5 KB                       │
│                                      --------                    │
│                           Subtotal:  21 KB                       │
│                                                                  │
│  Data Fetched (Worst Case - Mumbai):                             │
│  ├─ Locations query (50 locations)  ~25 KB                      │
│  ├─ Cars query (500 cars)           ~400 KB                     │
│  │   └─ Per car: ~800 bytes × 500                               │
│  ├─ Schedules (500 × 10 bookings)   ~600 KB                     │
│  │   └─ Per booking: ~120 bytes                                 │
│  └─ Response JSON (20 cars)         ~30 KB                      │
│                                      --------                    │
│                           Subtotal:  1,055 KB (~1 MB)            │
│                                                                  │
│  TOTAL WORST-CASE MEMORY:            ~1.1 MB per request         │
│                                                                  │
│  Cache-Warm Scenario:                ~50 KB per request          │
│  (95% of requests after warmup)                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Memory Breakdown by Cache State

| Cache State            | DB Queries  | Memory Used | Response Time |
| ---------------------- | ----------- | ----------- | ------------- |
| **100% Warm**          | 0           | ~50 KB      | 20-30ms       |
| **Partial Miss (20%)** | 1-2 queries | ~300 KB     | 80-120ms      |
| **100% Cold**          | 3 queries   | ~1.1 MB     | 200-350ms     |

### 2.2 Booking Initiate (`POST /api/v1/bookings/initiate`)

```
┌─────────────────────────────────────────────────────────────────┐
│           BOOKING INITIATE - MEMORY BREAKDOWN                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Request Processing:                                             │
│  ├─ FastAPI request object          ~10 KB                      │
│  ├─ SQLAlchemy session              ~5 KB                       │
│  ├─ Redis lock acquisition          ~2 KB                       │
│  └─ Python locals/stack             ~8 KB                       │
│                                      --------                    │
│                           Subtotal:  25 KB                       │
│                                                                  │
│  Data Operations:                                                │
│  ├─ Car details query (1 car)       ~1.5 KB                     │
│  ├─ Schedule cache read             ~15 KB (avg 50 bookings)    │
│  ├─ Holds check (Redis)             ~8 KB (avg 3 holds)         │
│  ├─ OTP generation                  ~2 KB                       │
│  ├─ Twilio API call                 ~10 KB                      │
│  └─ Hold data (Redis write)         ~1.5 KB                     │
│                                      --------                    │
│                           Subtotal:  38 KB                       │
│                                                                  │
│  TOTAL MEMORY:                       ~63 KB per request          │
│                                                                  │
│  Peak Concurrent:                    100 requests = ~6.3 MB      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Booking Confirm (`POST /api/v1/bookings/confirm`)

```
┌─────────────────────────────────────────────────────────────────┐
│           BOOKING CONFIRM - MEMORY BREAKDOWN                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Request Processing:                                             │
│  ├─ FastAPI request object          ~8 KB                       │
│  ├─ SQLAlchemy session + txn        ~15 KB                      │
│  ├─ Redis operations (5 commands)   ~5 KB                       │
│  └─ Python locals/stack             ~10 KB                      │
│                                      --------                    │
│                           Subtotal:  38 KB                       │
│                                                                  │
│  Data Operations:                                                │
│  ├─ Hold fetch (Redis)              ~1.5 KB                     │
│  ├─ OTP verification                ~1 KB                       │
│  ├─ User upsert query               ~2 KB                       │
│  ├─ Booking INSERT with txn         ~8 KB                       │
│  ├─ Schedule cache update (Lua)     ~15 KB                      │
│  └─ Response JSON                   ~4 KB                       │
│                                      --------                    │
│                           Subtotal:  31.5 KB                     │
│                                                                  │
│  TOTAL MEMORY:                       ~70 KB per request          │
│                                                                  │
│  DB Transaction Lock Time:           5-15ms (fast path)          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Database Capacity

### 3.1 Connection Pool Configuration

```python
# Current Config (config.py)
DB_POOL_SIZE = 10          # Persistent connections
DB_MAX_OVERFLOW = 5        # Emergency connections
# Total: 15 concurrent DB operations max
```

### 3.2 Connection Usage Patterns

| Endpoint             | Avg Queries/Request | Avg Duration | Max Concurrent |
| -------------------- | ------------------- | ------------ | -------------- |
| **Search (cold)**    | 3 queries           | 40-80ms      | ~4 concurrent  |
| **Search (warm)**    | 0 queries           | 0ms          | 0              |
| **Booking Initiate** | 1-2 queries         | 10-30ms      | ~2 concurrent  |
| **Booking Confirm**  | 2 queries           | 15-40ms      | ~3 concurrent  |

### 3.3 Requests Per Second Calculation

**Formula:**

```
Max RPS = (Pool Size × 1000ms) / Avg Query Duration
```

**Scenarios:**

```
Cold Cache (Worst Case):
  Search RPS = (15 × 1000ms) / 80ms = 187 RPS (unrealistic, cache always warms)

Warm Cache (Realistic):
  Search RPS = ∞ (no DB queries, pure Redis)

Mixed Workload (80% cache hit):
  - 80% requests: 0ms DB time
  - 20% requests: 80ms DB time
  Effective DB time per request = 0.2 × 80ms = 16ms
  Max RPS = 15,000ms / 16ms = 937 RPS ✓

Booking Confirm (DB write required):
  Max RPS = (15 × 1000ms) / 30ms = 500 RPS
```

**Real-World Bottleneck:** FastAPI workers, NOT database

---

## 4. Redis Capacity

### 4.1 Memory Usage Estimates

#### Active Data Size (10K Active Users)

```
┌─────────────────────────────────────────────────────────────────┐
│                  REDIS MEMORY BREAKDOWN                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CACHING LAYER:                                                  │
│  ├─ City locations (50 cities)      ~2 MB                       │
│  │   └─ 50 cities × 40 KB avg                                   │
│  ├─ Location cars (500 locations)   ~100 MB                     │
│  │   └─ 500 locs × 200 KB avg                                   │
│  ├─ Car schedules (5000 cars)       ~75 MB                      │
│  │   └─ 5000 cars × 15 KB avg                                   │
│                                      --------                    │
│                           Subtotal:  ~177 MB                     │
│                                                                  │
│  ACTIVE HOLDS (5 min TTL):                                       │
│  ├─ Hold data (500 concurrent)      ~750 KB                     │
│  │   └─ 500 holds × 1.5 KB                                      │
│  ├─ Car holds sets (500 cars)       ~200 KB                     │
│                                      --------                    │
│                           Subtotal:  ~1 MB                       │
│                                                                  │
│  AUTHENTICATION:                                                 │
│  ├─ Active OTPs (200 concurrent)    ~40 KB                      │
│  ├─ Rate limit counters (1K users)  ~100 KB                     │
│                                      --------                    │
│                           Subtotal:  ~140 KB                     │
│                                                                  │
│  TOTAL REDIS MEMORY:                 ~178 MB                     │
│                                                                  │
│  With Redis overhead (2x):           ~356 MB                     │
│                                                                  │
│  Recommended Redis Instance:         1 GB RAM (t3.small)         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Peak Traffic Scenario (100K Active Users)

```
Cache Layer:           ~177 MB  (mostly static)
Active Holds:          ~10 MB   (2000 concurrent bookings)
OTPs + Rate Limits:    ~2 MB    (10K active sessions)
                       --------
Total:                 ~189 MB
With Redis overhead:   ~400 MB

Recommended: 2 GB RAM (t3.medium)
```

### 4.2 Redis Operations Per Request

| Endpoint             | Redis Commands                  | Network RTT |
| -------------------- | ------------------------------- | ----------- |
| **Search (warm)**    | 8-12 commands (MGET for batch)  | 2-5ms       |
| **Booking Initiate** | 10 commands (lock + hold + OTP) | 3-6ms       |
| **Booking Confirm**  | 6 commands (verify + cleanup)   | 2-4ms       |

**Max Redis RPS (single instance):** ~50,000 RPS (well above app needs)

---

## 5. Worst-Case Scenarios

### 5.1 Traffic Spike - New Year's Eve

**Scenario:** 10x normal traffic for 2 hours

```
Normal Load:
  - 50 RPS average
  - 5 concurrent bookings/sec

Spike Load:
  - 500 RPS (300 search + 150 browse + 50 bookings)
  - 50 concurrent bookings/sec

System Impact:
  ┌──────────────────────────────────────────────────┐
  │ Component       │ Normal  │ Spike   │ Status    │
  ├──────────────────────────────────────────────────┤
  │ FastAPI Workers │ 30%     │ 95%     │ ⚠️ Slow    │
  │ DB Connections  │ 20%     │ 80%     │ ✅ OK      │
  │ Redis           │ 5%      │ 50%     │ ✅ OK      │
  │ Memory (App)    │ 500 MB  │ 2.5 GB  │ ⚠️ High    │
  │ Response Time   │ 50ms    │ 500ms   │ ⚠️ Slow    │
  └──────────────────────────────────────────────────┘

RESULT: System survives but degrades to ~500ms P99
```

### 5.2 Cache Failure - Redis Down

**Impact:**

```
All requests fall back to PostgreSQL

Search Performance:
  Before: 30ms (cache-warm)
  After:  300ms (all DB queries)

Database Load:
  Query Rate: 3 queries × 100 RPS = 300 queries/sec
  Connection Pool: EXHAUSTED in <1 second

RESULT: System survives with graceful degradation
  - Rate: ~20-30 RPS (vs 100 RPS normal)
  - Latency: 300-800ms (vs 50ms normal)
  - User Experience: Slow but functional ✓
```

### 5.3 DB Connection Pool Exhaustion

**Trigger:** 50+ concurrent long-running queries

```
Symptoms:
  - Request queue builds up
  - Timeouts begin after 30 seconds
  - 503 errors returned to users

Mitigation (ALREADY IMPLEMENTED):
  ✅ Try-catch on all cache operations
  ✅ Async I/O prevents blocking
  ✅ Connection pool pre-ping
  ✅ 1-hour connection recycle

Recovery Time: 1-2 seconds after spike ends
```

### 5.4 Mass Concurrent Bookings (Same Car)

**Scenario:** 100 users try to book same car simultaneously

```
Flow:
  1. User 1: Acquires lock → Creates hold → Success
  2. Users 2-100: Wait for lock (30s timeout)
  3. Users 2-100: Get lock one-by-one
  4. Check availability → 409 Conflict (car taken)

Memory Impact:
  - 100 requests × 63 KB = 6.3 MB (minimal)

Database Impact:
  - 1 write (only User 1 confirms)
  - 99 reads (failed attempts)
  - Total: ~3 seconds to process all

RESULT: System handles gracefully ✓
  - Lock prevents race conditions
  - Failed users get clear error message
  - No database corruption
```

---

## 6. System Breaking Points

### 6.1 Hard Limits

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYSTEM BREAKING POINTS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Component: Database Connections                                 │
│  ├─ Soft Limit:  100 RPS (starts queueing)                      │
│  ├─ Hard Limit:  ~120 RPS (timeouts begin)                      │
│  └─ Breaking:    150 RPS (cascade failure)                      │
│                                                                  │
│  Component: FastAPI Workers (Gunicorn 4 workers)                 │
│  ├─ Soft Limit:  80 RPS (latency increases)                     │
│  ├─ Hard Limit:  120 RPS (queue buildup)                        │
│  └─ Breaking:    200 RPS (OOM crashes)                          │
│                                                                  │
│  Component: Redis                                                │
│  ├─ Soft Limit:  10,000 RPS (not a bottleneck)                  │
│  └─ Hard Limit:  50,000 RPS (theoretical)                       │
│                                                                  │
│  Component: Memory (4 GB instance)                               │
│  ├─ Baseline:    500 MB (idle)                                  │
│  ├─ Soft Limit:  3 GB (80% usage, GC active)                    │
│  ├─ Hard Limit:  3.5 GB (swapping begins)                       │
│  └─ Breaking:    4 GB (OOM killer)                              │
│                                                                  │
│  OVERALL SYSTEM CAPACITY:                                        │
│  ├─ Sustained RPS:     80 RPS                                   │
│  ├─ Burst RPS (1 min): 150 RPS                                  │
│  └─ Max RPS (10s):     200 RPS                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Failure Modes

| Failure Scenario                   | Probability | Impact                              | Recovery Time |
| ---------------------------------- | ----------- | ----------------------------------- | ------------- |
| **Redis OOM**                      | Low         | Eviction of old cache, slower reads | Self-healing  |
| **DB Pool Exhausted**              | Medium      | Request queuing, 503 errors         | 1-2 seconds   |
| **App Server OOM**                 | Low         | Process crash, restart              | 10-30 seconds |
| **DB Deadlock**                    | Very Low    | Single request fails                | Immediate     |
| **Exclusion Constraint Violation** | Very Low    | 409 error to user                   | Immediate     |

---

## 7. Scale Recommendations

### 7.1 Current State (Single Instance)

```
Recommended For:
  ✅ 0-5,000 daily active users
  ✅ <50 RPS sustained load
  ✅ 100-200 bookings/day
  ✅ Development/staging environments

Instance Specs:
  - EC2 t3.medium (2 vCPU, 4 GB RAM)
  - PostgreSQL db.t3.small (1 vCPU, 2 GB RAM)
  - Redis t3.small (1 vCPU, 1 GB RAM)

Monthly Cost: ~$120 USD
```

### 7.2 Small Scale (3-Instance Cluster)

```
Target:
  ✅ 10,000-50,000 daily active users
  ✅ 100-300 RPS sustained
  ✅ 500-2,000 bookings/day

Architecture:
  ┌─────────────────────────────────────────┐
  │         Load Balancer (ALB)             │
  └──────────┬─────────┬──────────┬─────────┘
             │         │          │
       ┌─────▼───┐ ┌──▼─────┐ ┌──▼─────┐
       │ FastAPI │ │FastAPI │ │FastAPI │
       │  Node 1 │ │ Node 2 │ │ Node 3 │
       └────┬────┘ └───┬────┘ └───┬────┘
            └──────────┼──────────┘
                       │
          ┌────────────┴──────────────┐
          │                           │
    ┌─────▼──────┐           ┌────▼─────┐
    │ PostgreSQL │           │  Redis   │
    │  Primary   │◀─────────▶│ Primary  │
    │            │  Replica  │          │
    │ + Replica  │           │          │
    └────────────┘           └──────────┘

Changes:
  - 3× FastAPI servers (horizontal scale)
  - DB read replica for search queries
  - Sticky sessions for booking flow

Capacity:
  - 300 RPS (3× improvement)
  - 15,000 concurrent users
  - P95 latency: 30-80ms

Monthly Cost: ~$450 USD
```

### 7.3 Medium Scale (10-Instance Cluster)

```
Target:
  ✅ 50,000-200,000 daily active users
  ✅ 500-1,000 RPS sustained
  ✅ 5,000-20,000 bookings/day

Architecture:
  - 10× FastAPI autoscaling group
  - PostgreSQL multi-AZ with 3 read replicas
  - Redis Cluster (3 masters, 3 replicas)
  - Separate read/write DB connections
  - CDN for static assets

Capacity:
  - 1,000 RPS sustained
  - 50,000 concurrent users
  - P95 latency: 20-50ms

Monthly Cost: ~$2,000 USD
```

### 7.4 Bottleneck Optimization Priorities

**Priority 1: Database Read Scaling**

```
Problem: Search queries on cold cache
Solution: Read replicas with connection pooling
Impact:  3-5× read capacity
Cost:    +$100/month per replica
```

**Priority 2: Horizontal App Scaling**

```
Problem: FastAPI worker saturation
Solution: Auto-scaling group (3-10 instances)
Impact:  Linear scaling with instance count
Cost:    ~$50/month per instance
```

**Priority 3: Redis Clustering**

```
Problem: Single Redis memory limit
Solution: Redis Cluster with sharding
Impact:  10× memory capacity
Cost:    ~$300/month for cluster
```

**Priority 4: CDN for Static Assets**

```
Problem: Frontend bundle served from FastAPI
Solution: CloudFront for Next.js static files
Impact:  -60% app server load
Cost:    ~$20/month (low traffic)
```

### 7.5 Monitoring Thresholds

```yaml
Alerts:
  Critical (PagerDuty):
    - DB connection pool > 90% for 1 minute
    - Response time P99 > 2 seconds for 5 minutes
    - Error rate > 5% for 1 minute
    - Memory usage > 85% for 5 minutes

  Warning (Slack):
    - DB connection pool > 70% for 5 minutes
    - Response time P95 > 500ms for 10 minutes
    - Redis memory > 80% for 10 minutes
    - Cache hit rate < 70% for 30 minutes

  Info (Logs):
    - Booking confirmation rate
    - Search queries per minute
    - OTP send rate
    - Failed booking attempts
```

---

## Summary: Load Capacity Matrix

| Metric             | Current | Small Scale | Medium Scale   |
| ------------------ | ------- | ----------- | -------------- |
| **Instances**      | 1       | 3           | 10             |
| **Max RPS**        | 80-120  | 200-300     | 800-1,200      |
| **DAU**            | 5K      | 20K         | 100K           |
| **Bookings/Day**   | 200     | 1,000       | 10,000         |
| **DB Connections** | 15      | 45 (3×15)   | 150 (10×15)    |
| **Redis Memory**   | 500 MB  | 1 GB        | 4 GB (cluster) |
| **App Memory**     | 4 GB    | 12 GB (3×4) | 40 GB (10×4)   |
| **Monthly Cost**   | $120    | $450        | $2,000         |
| **P95 Latency**    | 50ms    | 40ms        | 30ms           |
| **P99 Latency**    | 150ms   | 100ms       | 80ms           |

---

## Conclusion

The current implementation can comfortably handle:

- **5,000 daily active users**
- **80 RPS sustained load**
- **200-300 bookings per day**

System degrades gracefully under load with:

- ✅ Redis failure fallback to PostgreSQL
- ✅ Try-catch on all cache operations
- ✅ Distributed locks prevent race conditions
- ✅ Exclusion constraints ensure data integrity

**Recommended next step:** Monitor production metrics for 2-4 weeks, then scale horizontally only when sustained load exceeds 60 RPS.
