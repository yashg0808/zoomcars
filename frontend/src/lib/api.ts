import axios, {
  AxiosError,
  AxiosInstance,
  InternalAxiosRequestConfig,
} from "axios";
import { useAuthStore } from "@/store/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Create axios instance
export const api: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000, // 30 seconds
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      useAuthStore.getState().logout();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

// API functions

// Auth
export const authApi = {
  sendOtp: (phone: string) =>
    api.post<{ message: string; expires_in_seconds: number }>(
      "/auth/send-otp",
      { phone },
    ),

  verifyOtp: (phone: string, otp: string) =>
    api.post<{
      access_token: string;
      token_type: string;
      user: { id: string; phone: string; name?: string; email?: string };
    }>("/auth/verify-otp", { phone, otp }),

  getProfile: () =>
    api.get<{ id: string; phone: string; name?: string; email?: string }>(
      "/auth/me",
    ),

  updateProfile: (data: { name?: string; email?: string }) =>
    api.put<{ id: string; phone: string; name?: string; email?: string }>(
      "/auth/me",
      data,
    ),
};

// Locations
export const locationsApi = {
  getCities: () => api.get<{ cities: string[] }>("/locations/cities"),

  getLocations: (params?: {
    city?: string;
    lat?: number;
    lng?: number;
    radius_km?: number;
  }) => api.get<Location[]>("/locations", { params }),

  getLocation: (id: number) => api.get<Location>(`/locations/${id}`),
};

// Cars
export const carsApi = {
  search: (params: CarSearchParams) =>
    api.get<CarSearchResponse>("/cars/search", { params }),

  getDetails: (id: number) => api.get<CarDetails>(`/cars/${id}`),

  checkAvailability: (carId: number, startTime: string, endTime: string) =>
    api.get<{ car_id: number; is_available: boolean }>(
      `/cars/${carId}/availability`,
      {
        params: { start_time: startTime, end_time: endTime },
      },
    ),
};

// Bookings
export const bookingsApi = {
  // New hold-based flow
  initiate: (data: InitiateBookingRequest) =>
    api.post<InitiateBookingResponse>("/bookings/initiate", data),

  confirmBooking: (data: ConfirmBookingRequest) =>
    api.post<ConfirmBookingResponse>("/bookings/confirm", data),

  cancelHold: (booking_id: string, car_id: number) =>
    api.post<{ booking_id: string; message: string }>("/bookings/cancel", {
      booking_id,
      car_id,
    }),
};

// Types
export interface Location {
  id: number;
  name: string;
  city: string;
  address?: string;
  latitude: number;
  longitude: number;
}

export interface CarSearchParams {
  city: string;
  lat: number;
  lng: number;
  start_time: string;
  end_time: string;
  transmission?: "MANUAL" | "AUTOMATIC";
  fuel_type?: "PETROL" | "DIESEL" | "ELECTRIC" | "CNG";
  max_price?: number;
  min_seats?: number;
  limit?: number;
  offset?: number;
}

export interface CarSearchResult {
  id: number;
  make: string;
  model: string;
  year: number;
  image_url?: string;
  transmission: "Manual" | "Automatic";
  fuel_type: "Petrol" | "Diesel" | "Electric" | "CNG";
  seating_capacity: number;
  base_hourly_rate: number;
  dynamic_price: number;
  rating: number;
  total_trips: number;
  distance_km: number;
  location: {
    name: string;
    city: string;
    address?: string;
  };
}

export interface CarSearchResponse {
  cars: CarSearchResult[];
  total_count: number;
}

export interface CarDetails {
  id: number;
  make: string;
  model: string;
  year: number;
  image_url?: string;
  transmission: "Manual" | "Automatic";
  fuel_type: "Petrol" | "Diesel" | "Electric" | "CNG";
  seating_capacity: number;
  base_hourly_rate: number;
  rating: number;
  total_trips: number;
  location: {
    name: string;
    city: string;
    address?: string;
  };
}

export interface InitiateBookingRequest {
  car_id: number;
  phone: string;
  start_time: string;
  end_time: string;
}

export interface InitiateBookingResponse {
  booking_id: string;
  lock_token: string;
  expires_at: string;
  expires_in_seconds: number;
  otp_sent: boolean;
  booking_preview: {
    car: string;
    duration_hours: number;
    total_amount: number;
    start_time: string;
    end_time: string;
  };
}

export interface ConfirmPaymentRequest {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface ConfirmPaymentResponse {
  booking_id: string;
  status: string;
  message: string;
}

export interface BookingResponse {
  id: string;
  car_id: number;
  car_make: string;
  car_model: string;
  car_image_url?: string;
  location_name: string;
  booking_start: string;
  booking_end: string;
  status: "PENDING" | "CONFIRMED" | "CANCELLED" | "EXPIRED" | "COMPLETED";
  total_amount: number;
  payment_id?: string;
  created_at: string;
}

export interface BookingListResponse {
  bookings: BookingResponse[];
  total_count: number;
}

export interface CancelBookingResponse {
  booking_id: string;
  status: string;
  refund_status?: string;
  message: string;
}

// New hold-based booking types
export interface ConfirmBookingRequest {
  booking_id: string;
  lock_token: string;
  otp: string;
  name: string;
  email?: string;
}

export interface ConfirmBookingResponse {
  booking_id: string;
  status: string;
  total_amount: number;
  message: string;
  car_details: {
    make: string;
    model: string;
    year: number;
    image_url?: string;
  };
  booking_start: string;
  booking_end: string;
}
