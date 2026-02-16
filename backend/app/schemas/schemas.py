"""
Pydantic Schemas for API request/response validation
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
import re

from app.models import TransmissionType, FuelType, BookingStatus


# ============== Auth Schemas ==============

class SendOTPRequest(BaseModel):
    """Send OTP request"""
    phone: str = Field(..., description="Phone number with country code")
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        pattern = r"^\+91[6-9]\d{9}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid Indian phone number. Format: +91XXXXXXXXXX")
        return v


class SendOTPResponse(BaseModel):
    """Send OTP response"""
    message: str
    expires_in_seconds: int


class VerifyOTPRequest(BaseModel):
    """Verify OTP request"""
    phone: str = Field(..., description="Phone number with country code")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP")
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        pattern = r"^\+91[6-9]\d{9}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid Indian phone number. Format: +91XXXXXXXXXX")
        return v
    
    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("OTP must contain only digits")
        return v


class UserResponse(BaseModel):
    """User response"""
    id: UUID
    phone: str
    name: Optional[str] = None
    email: Optional[str] = None
    
    class Config:
        from_attributes = True


class VerifyOTPResponse(BaseModel):
    """Verify OTP response"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UpdateProfileRequest(BaseModel):
    """Update user profile request"""
    name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)


# ============== Location Schemas ==============

class LocationResponse(BaseModel):
    """Location response"""
    id: int
    name: str
    city: str
    address: Optional[str] = None
    latitude: float
    longitude: float
    
    class Config:
        from_attributes = True


class CitiesResponse(BaseModel):
    """Cities list response"""
    cities: List[str]


# ============== Car Schemas ==============

class CarLocationInfo(BaseModel):
    """Car location info"""
    name: str
    city: str
    address: Optional[str]


class CarSearchResult(BaseModel):
    """Car search result"""
    id: int
    make: str
    model: str
    year: int
    image_url: Optional[str]
    transmission: TransmissionType
    fuel_type: FuelType
    seating_capacity: int
    base_hourly_rate: float
    dynamic_price: float
    rating: float
    total_trips: int
    distance_km: float
    location: CarLocationInfo


class CarSearchResponse(BaseModel):
    """Car search response"""
    cars: List[CarSearchResult]
    total_count: int


class CarDetailResponse(BaseModel):
    """Car detail response"""
    id: int
    make: str
    model: str
    year: int
    image_url: Optional[str]
    transmission: TransmissionType
    fuel_type: FuelType
    seating_capacity: int
    base_hourly_rate: float
    rating: float
    total_trips: int
    location: CarLocationInfo
    
    class Config:
        from_attributes = True


# ============== Booking Schemas ==============

class InitiateBookingRequest(BaseModel):
    """
    Step 1: Initiate booking - creates a hold and sends OTP.
    No payment required, just reserves the slot temporarily.
    """
    car_id: int = Field(..., gt=0)
    phone: str = Field(..., description="Phone number with country code")
    start_time: datetime
    end_time: datetime
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        pattern = r"^\+91[6-9]\d{9}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid Indian phone number. Format: +91XXXXXXXXXX")
        return v
    
    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Start time must include timezone")
        return v
    
    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: datetime, info) -> datetime:
        if v.tzinfo is None:
            raise ValueError("End time must include timezone")
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("End time must be after start time")
        return v


class InitiateBookingResponse(BaseModel):
    """
    Response after initiating booking.
    Returns booking_id and lock_token needed for confirmation.
    """
    booking_id: UUID
    lock_token: str
    expires_at: datetime
    expires_in_seconds: int
    otp_sent: bool
    booking_preview: dict


class ConfirmBookingRequest(BaseModel):
    """
    Step 2: Confirm booking with OTP and lock_token.
    Validates hold is still active and creates the actual booking.
    """
    booking_id: UUID = Field(..., description="Booking ID from initiate response")
    lock_token: str = Field(..., description="Lock token from initiate response")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP")
    name: str = Field(..., min_length=2, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    
    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("OTP must contain only digits")
        return v


class ConfirmBookingResponse(BaseModel):
    """Response after booking is confirmed"""
    booking_id: UUID
    status: BookingStatus
    total_amount: float
    message: str
    car_details: dict
    booking_start: datetime
    booking_end: datetime


# Legacy schemas (kept for backward compatibility)
class BookingOTPRequest(BaseModel):
    """Request OTP for booking - collects user details"""
    car_id: int = Field(..., gt=0)
    start_time: datetime
    end_time: datetime
    name: str = Field(..., min_length=2, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    phone: str = Field(..., description="Phone number with country code")
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        pattern = r"^\+91[6-9]\d{9}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid Indian phone number. Format: +91XXXXXXXXXX")
        return v
    
    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Start time must include timezone")
        return v
    
    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: datetime, info) -> datetime:
        if v.tzinfo is None:
            raise ValueError("End time must include timezone")
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("End time must be after start time")
        return v


class BookingOTPResponse(BaseModel):
    """Response after sending booking OTP"""
    message: str
    expires_in_seconds: int
    booking_preview: dict


class BookingResponse(BaseModel):
    """Booking detail response"""
    id: UUID
    car_id: int
    car_make: str
    car_model: str
    car_image_url: Optional[str]
    location_name: str
    booking_start: datetime
    booking_end: datetime
    status: BookingStatus
    total_amount: float
    payment_id: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class BookingListResponse(BaseModel):
    """Booking list response"""
    bookings: List[BookingResponse]
    total_count: int


class ConfirmPaymentRequest(BaseModel):
    """Confirm payment request (when not using webhooks)"""
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class ConfirmPaymentResponse(BaseModel):
    """Confirm payment response"""
    booking_id: UUID
    status: BookingStatus
    message: str


class CancelBookingResponse(BaseModel):
    """Cancel booking response"""
    booking_id: UUID
    status: BookingStatus
    refund_status: Optional[str] = None
    message: str


class CancelHoldRequest(BaseModel):
    """Cancel a Redis-only hold (no DB interaction)"""
    booking_id: UUID = Field(..., description="Booking ID from initiate response")
    car_id: int = Field(..., gt=0, description="Car ID associated with the hold")


class CancelHoldResponse(BaseModel):
    """Response after cancelling a hold"""
    booking_id: UUID
    message: str


# ============== Webhook Schemas ==============

class RazorpayWebhookPayload(BaseModel):
    """Razorpay webhook payload"""
    event: str
    payload: dict


# ============== Health Check ==============

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    database: str
    redis: str
    timestamp: datetime
