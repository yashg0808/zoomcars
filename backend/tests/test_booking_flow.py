import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
import uuid

from app.main import app
from app.core.database import get_db
from app.core.redis import get_redis, CacheManager
from app.models import Base, User, Location, Car, Booking

# Test database URL - use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Create test database session."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def mock_redis():
    """Create mock Redis client."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    
    # Mock lock context manager
    mock_lock = AsyncMock()
    mock_lock.__aenter__ = AsyncMock(return_value=True)
    mock_lock.__aexit__ = AsyncMock(return_value=None)
    mock.lock = MagicMock(return_value=mock_lock)
    
    return mock


@pytest_asyncio.fixture
async def client(test_session, mock_redis):
    """Create test client with dependency overrides."""
    async def override_get_db():
        yield test_session
    
    async def override_get_redis():
        return mock_redis
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(test_session):
    """Create test user."""
    user = User(
        id=uuid.uuid4(),
        phone="+919876543210",
        name="Test User",
        email="test@example.com",
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_location(test_session):
    """Create test location."""
    location = Location(
        id=1,
        name="Test Location",
        city="Mumbai",
        address="123 Test Street",
        latitude=19.0760,
        longitude=72.8777,
    )
    test_session.add(location)
    await test_session.commit()
    await test_session.refresh(location)
    return location


@pytest_asyncio.fixture
async def test_car(test_session, test_location):
    """Create test car."""
    car = Car(
        id=1,
        location_id=test_location.id,
        make="Toyota",
        model="Camry",
        year=2023,
        license_plate="MH01AB1234",
        transmission="automatic",
        fuel_type="petrol",
        seats=5,
        base_hourly_rate=500.0,
    )
    test_session.add(car)
    await test_session.commit()
    await test_session.refresh(car)
    return car


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    async def test_health_check(self, client):
        """Test health check returns ok status."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    async def test_send_otp_success(self, client):
        """Test OTP sending succeeds."""
        response = await client.post(
            "/api/v1/auth/otp/send",
            json={"phone": "+919876543210"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "OTP sent successfully"

    async def test_send_otp_invalid_phone(self, client):
        """Test OTP sending fails with invalid phone."""
        response = await client.post(
            "/api/v1/auth/otp/send",
            json={"phone": "invalid"}
        )
        assert response.status_code == 422


class TestCarsEndpoints:
    """Tests for car search endpoints."""

    async def test_search_cars_no_results(self, client):
        """Test car search with no matching cars."""
        response = await client.get(
            "/api/v1/cars/search",
            params={
                "lat": 19.0760,
                "lng": 72.8777,
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "end_time": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["cars"] == []

    async def test_search_cars_invalid_time(self, client):
        """Test car search with invalid time range."""
        response = await client.get(
            "/api/v1/cars/search",
            params={
                "lat": 19.0760,
                "lng": 72.8777,
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
                "end_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            }
        )
        assert response.status_code == 400


class TestBookingEndpoints:
    """Tests for booking endpoints."""

    async def test_initiate_booking_unauthorized(self, client, test_car):
        """Test booking initiation without authentication."""
        response = await client.post(
            "/api/v1/bookings/initiate",
            json={
                "car_id": test_car.id,
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "end_time": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
            }
        )
        assert response.status_code == 401

    @patch("app.api.v1.bookings.razorpay_client")
    async def test_initiate_booking_success(
        self,
        mock_razorpay,
        client,
        test_session,
        test_user,
        test_car,
        mock_redis
    ):
        """Test successful booking initiation."""
        # Mock Razorpay order creation
        mock_razorpay.order.create.return_value = {
            "id": "order_test123",
            "amount": 200000,
            "currency": "INR",
        }
        
        # Create JWT token for test user
        from app.core.security import create_access_token
        token = create_access_token(data={"sub": str(test_user.id)})
        
        idempotency_key = str(uuid.uuid4())
        
        response = await client.post(
            "/api/v1/bookings/initiate",
            json={
                "car_id": test_car.id,
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "end_time": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Idempotency-Key": idempotency_key,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "booking_id" in data
        assert "razorpay_order_id" in data
        assert "expires_at" in data


class TestLocationsEndpoints:
    """Tests for location endpoints."""

    async def test_list_cities(self, client, test_location):
        """Test cities listing."""
        response = await client.get("/api/v1/locations/cities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestIdempotency:
    """Tests for idempotency handling."""

    async def test_idempotency_key_required(self, client, test_user, test_car):
        """Test that idempotency key is required for booking."""
        from app.core.security import create_access_token
        token = create_access_token(data={"sub": str(test_user.id)})
        
        response = await client.post(
            "/api/v1/bookings/initiate",
            json={
                "car_id": test_car.id,
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "end_time": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
            },
            headers={
                "Authorization": f"Bearer {token}",
            }
        )
        
        assert response.status_code == 422
