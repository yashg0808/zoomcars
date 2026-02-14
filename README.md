# Zoomcar Clone - Production-Ready Car Rental Platform

A full-stack car rental platform built with FastAPI, Next.js, PostgreSQL, and Redis. Designed for high availability with zero double bookings through database-level constraints.

## Features

- **OTP-based authentication** - Secure phone verification
- **Geospatial car search** - Find cars within radius using PostGIS
- **Zero double bookings** - PostgreSQL exclusion constraints prevent conflicts
- **Real-time booking with timer** - 8-minute payment window with countdown
- **Razorpay integration** - Seamless payment processing with webhook support
- **Distributed locking** - Redis-based locks for concurrent booking protection
- **Background jobs** - Automated cleanup and reconciliation

## Tech Stack

### Backend

- **FastAPI** - Modern Python web framework
- **PostgreSQL 15+** with PostGIS extension
- **Redis 7.0+** - Caching and distributed locks
- **SQLAlchemy** - Async ORM
- **Razorpay** - Payment gateway

### Frontend

- **Next.js 14** - React framework with App Router
- **TanStack Query** - Data fetching and caching
- **Zustand** - State management
- **Tailwind CSS** - Styling

### Infrastructure

- **AWS Lambda** - Serverless deployment via Mangum
- **Docker** - Containerization
- **Serverless Framework** - Lambda deployment

## Project Structure

```
zoomcars/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── core/            # Config, database, security
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   └── jobs/            # Background jobs
│   ├── tests/               # Pytest tests
│   ├── lambda_handler.py    # AWS Lambda entry point
│   ├── requirements.txt
│   ├── serverless.yml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js pages
│   │   ├── components/      # React components
│   │   ├── lib/             # API client, utilities
│   │   └── store/           # Zustand stores
│   ├── package.json
│   └── Dockerfile
├── database/
│   └── schema.sql           # PostgreSQL schema
├── docker-compose.yml
└── README.md
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+
- Python 3.11+
- Razorpay account (for payments)

### Using Docker Compose (Recommended)

1. **Clone and setup environment**

   ```bash
   cd zoomcars
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env.local
   ```

2. **Configure Razorpay credentials** in both `.env` files

3. **Start all services**

   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Adminer (DB): http://localhost:8080
   - Redis Commander: http://localhost:8081

### Manual Setup

#### Backend

1. **Create virtual environment**

   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Setup PostgreSQL with PostGIS**

   ```bash
   # Run the schema file
   psql -U postgres -d zoomcar -f ../database/schema.sql
   ```

3. **Start Redis**

   ```bash
   redis-server
   ```

4. **Run backend**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   uvicorn app.main:app --reload
   ```

#### Frontend

1. **Install dependencies**

   ```bash
   cd frontend
   npm install
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env.local
   # Edit .env.local with your configuration
   ```

3. **Run frontend**
   ```bash
   npm run dev
   ```

## API Documentation

Once the backend is running, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Key Endpoints

| Method | Endpoint                    | Description                              |
| ------ | --------------------------- | ---------------------------------------- |
| POST   | `/api/v1/auth/otp/send`     | Send OTP to phone                        |
| POST   | `/api/v1/auth/otp/verify`   | Verify OTP and get token                 |
| GET    | `/api/v1/cars/search`       | Search available cars                    |
| GET    | `/api/v1/cars/{id}`         | Get car details                          |
| POST   | `/api/v1/bookings/initiate` | Start booking (requires idempotency key) |
| POST   | `/api/v1/bookings/confirm`  | Confirm payment                          |
| GET    | `/api/v1/bookings/my`       | Get user's bookings                      |

## Booking Flow

```
1. User searches for cars → GET /cars/search
2. User selects a car and time slot
3. Frontend generates idempotency key
4. User initiates booking → POST /bookings/initiate
   - Backend acquires Redis lock
   - Creates PENDING booking with exclusion constraint
   - Creates Razorpay order
   - Returns booking_id, order_id, expires_at
5. Frontend shows 8-minute countdown timer
6. User completes payment via Razorpay
7. Frontend confirms → POST /bookings/confirm
   - OR Razorpay webhook confirms automatically
8. Booking status becomes CONFIRMED
```

## Double Booking Prevention

The system uses a multi-layer approach:

1. **PostgreSQL Exclusion Constraint**

   ```sql
   CONSTRAINT no_double_booking EXCLUDE USING gist (
       car_id WITH =,
       total_period WITH &&
   ) WHERE (status IN ('CONFIRMED', 'PENDING'))
   ```

2. **Distributed Redis Locks**

   ```python
   async with redis.lock(f"booking:{car_id}:{start}:{end}"):
       # Create booking
   ```

3. **Idempotency Keys**
   - Prevents duplicate bookings from retry requests
   - Cached for 10 minutes

## Testing

```bash
cd backend
pytest
```

## Deployment

### AWS Lambda (Serverless)

1. **Configure AWS credentials**

   ```bash
   aws configure
   ```

2. **Deploy**
   ```bash
   cd backend
   serverless deploy --stage prod
   ```

### Environment Variables

Store sensitive data in AWS Parameter Store:

```bash
aws ssm put-parameter --name "/zoomcar/prod/database_url" --value "your-db-url" --type SecureString
aws ssm put-parameter --name "/zoomcar/prod/jwt_secret" --value "your-secret" --type SecureString
```

## Architecture Decisions

### Why PostgreSQL Exclusion Constraints?

- Database-level guarantee against double bookings
- Atomic operations - no race conditions
- Works even if application crashes mid-transaction

### Why Redis for Locks?

- Sub-millisecond latency
- Distributed locks work across multiple instances
- Prevents thundering herd problem

### Why 8-Minute Booking Expiry?

- Balances user experience with inventory availability
- Similar to airline/movie ticket booking patterns
- Long enough for payment, short enough to not block inventory

## License

MIT License - See LICENSE file for details.
