"""
SQLAlchemy Database Models
Production-ready car rental platform
"""

from datetime import datetime
from typing import Optional, List
import uuid
from sqlalchemy import (
    Column, String, Integer, Boolean, DECIMAL, Text, 
    ForeignKey, DateTime, Enum as SQLEnum, Index, CheckConstraint,
    event, text
)
from sqlalchemy.dialects.postgresql import UUID, TSTZRANGE
from sqlalchemy.orm import relationship, Mapped, mapped_column
from geoalchemy2 import Geography
import enum

from app.core.database import Base


class TransmissionType(str, enum.Enum):
    """Car transmission type enum"""
    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"


class FuelType(str, enum.Enum):
    """Car fuel type enum"""
    PETROL = "PETROL"
    DIESEL = "DIESEL"
    ELECTRIC = "ELECTRIC"
    CNG = "CNG"


class BookingStatus(str, enum.Enum):
    """Booking status enum"""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    phone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="user")
    
    __table_args__ = (
        Index("idx_users_created_at", created_at.desc()),
    )


class Location(Base):
    """Location/Hub model"""
    __tablename__ = "locations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coordinates = Column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    cars: Mapped[List["Car"]] = relationship("Car", back_populates="location")
    
    __table_args__ = (
        Index("idx_locations_geo", coordinates, postgresql_using="gist"),
        Index("idx_locations_city", city, postgresql_where=text("is_active = TRUE")),
    )


class Car(Base):
    """Car model"""
    __tablename__ = "cars"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("locations.id", ondelete="RESTRICT"), 
        nullable=False
    )
    make: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transmission: Mapped[TransmissionType] = mapped_column(
        SQLEnum(TransmissionType), 
        nullable=False
    )
    fuel_type: Mapped[FuelType] = mapped_column(
        SQLEnum(FuelType), 
        nullable=False
    )
    seating_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    base_hourly_rate: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    rating: Mapped[float] = mapped_column(DECIMAL(2, 1), default=4.5)
    total_trips: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="cars")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="car")
    
    __table_args__ = (
        CheckConstraint("year >= 2015", name="check_year_min"),
        CheckConstraint("seating_capacity BETWEEN 2 AND 8", name="check_seating_capacity"),
        CheckConstraint("base_hourly_rate > 0", name="check_base_rate_positive"),
        CheckConstraint("rating BETWEEN 0 AND 5", name="check_rating_range"),
        CheckConstraint("total_trips >= 0", name="check_trips_non_negative"),
        Index("idx_cars_location", location_id, postgresql_where=text("is_active = TRUE")),
        Index("idx_cars_type", transmission, fuel_type, postgresql_where=text("is_active = TRUE")),
        Index("idx_cars_rate", base_hourly_rate),
    )


class Booking(Base):
    """Booking model with double-booking prevention"""
    __tablename__ = "bookings"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="RESTRICT"), 
        nullable=False
    )
    car_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("cars.id", ondelete="RESTRICT"), 
        nullable=False
    )
    
    # Booking Period
    booking_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    booking_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Total period including buffer (for exclusion constraint)
    total_period = Column(TSTZRANGE, nullable=False)
    
    # Status & Payment
    status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus), 
        nullable=False, 
        default=BookingStatus.PENDING
    )
    payment_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    total_amount: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    
    # Expiration for PENDING bookings
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Idempotency key
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="bookings")
    car: Mapped["Car"] = relationship("Car", back_populates="bookings")
    history: Mapped[List["BookingHistory"]] = relationship("BookingHistory", back_populates="booking")
    
    __table_args__ = (
        CheckConstraint("booking_start < booking_end", name="check_booking_dates"),
        CheckConstraint("total_amount > 0", name="check_amount_positive"),
        CheckConstraint(
            "status != 'PENDING' OR expires_at IS NOT NULL", 
            name="check_pending_has_expiry"
        ),
        Index("idx_bookings_user", user_id, created_at.desc()),
        Index("idx_bookings_car", car_id, status),
        Index("idx_bookings_status", status, expires_at, postgresql_where=text("status = 'PENDING'")),
        Index("idx_bookings_payment_order", payment_order_id, postgresql_where=text("payment_order_id IS NOT NULL")),
        Index("idx_bookings_idempotency", idempotency_key, postgresql_where=text("idempotency_key IS NOT NULL")),
        # Note: Exclusion constraint is created via migration
    )


class BookingHistory(Base):
    """Booking status history for auditing"""
    __tablename__ = "booking_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("bookings.id"), 
        nullable=False
    )
    old_status: Mapped[Optional[BookingStatus]] = mapped_column(
        SQLEnum(BookingStatus), 
        nullable=True
    )
    new_status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus), 
        nullable=False
    )
    changed_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="history")
    
    __table_args__ = (
        Index("idx_booking_history_booking", booking_id, created_at.desc()),
    )
