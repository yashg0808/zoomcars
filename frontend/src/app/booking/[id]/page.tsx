"use client";

import { useState, Suspense, useEffect } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import Image from "next/image";
import { format } from "date-fns";
import {
  Car,
  MapPin,
  Calendar,
  Clock,
  User,
  Mail,
  Phone,
  Shield,
  Loader2,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";

import { carsApi, bookingsApi } from "@/lib/api";
import { getCarImageByMakeModel } from "@/lib/carImages";

type BookingStep = "details" | "otp" | "confirming" | "success" | "failed";

function BookingContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();

  const carId = parseInt(params.id as string);
  const startTime = searchParams.get("start") || "";
  const endTime = searchParams.get("end") || "";

  const [step, setStep] = useState<BookingStep>("details");
  const [error, setError] = useState("");
  const [countdown, setCountdown] = useState(0);

  // User details form
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("+91");
  const [otp, setOtp] = useState("");

  // Hold data from initiate (NEW)
  const [holdData, setHoldData] = useState<{
    booking_id: string;
    lock_token: string;
    expires_at: string;
  } | null>(null);

  // Booking preview from initiate request
  const [bookingPreview, setBookingPreview] = useState<{
    car: string;
    duration_hours: number;
    total_amount: number;
  } | null>(null);

  // Confirmed booking data
  const [confirmedBooking, setConfirmedBooking] = useState<{
    booking_id: string;
    total_amount: number;
    car_details: { make: string; model: string; year: number };
  } | null>(null);

  // Countdown timer for hold expiration - uses absolute expiresAt to prevent drift
  useEffect(() => {
    if (!holdData?.expires_at || step !== "otp") {
      return;
    }

    const expiresAt = new Date(holdData.expires_at).getTime();

    const tick = () => {
      const now = Date.now();
      const remaining = Math.max(0, Math.floor((expiresAt - now) / 1000));
      setCountdown(remaining);

      if (remaining <= 0) {
        // Hold expired, go back to details
        setError("Your hold has expired. Please start over.");
        setStep("details");
        setHoldData(null);
        setBookingPreview(null);
      }
    };

    // Initial tick
    tick();

    // Update every second using absolute time calculation
    const interval = setInterval(tick, 1000);

    // Also update when tab becomes visible (handles backgrounded tabs)
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        tick();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [holdData?.expires_at, step]);

  // Fetch car details
  const { data: car, isLoading: isLoadingCar } = useQuery({
    queryKey: ["car", carId],
    queryFn: async () => {
      const response = await carsApi.getDetails(carId);
      return response.data;
    },
    enabled: !!carId,
  });

  // Calculate rental details
  const startDate = new Date(startTime);
  const endDate = new Date(endTime);
  const durationHours =
    (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60);
  const estimatedAmount = car ? car.base_hourly_rate * durationHours : 0;

  // Initiate booking mutation (creates hold + sends OTP)
  const initiateMutation = useMutation({
    mutationFn: async () => {
      const response = await bookingsApi.initiate({
        car_id: carId,
        phone,
        start_time: startTime,
        end_time: endTime,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setHoldData({
        booking_id: data.booking_id,
        lock_token: data.lock_token,
        expires_at: data.expires_at,
      });
      setBookingPreview(data.booking_preview);
      // countdown is calculated from expires_at in useEffect
      setStep("otp");
      setError("");
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Failed to send OTP");
    },
  });

  // Confirm booking mutation
  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!holdData) {
        throw new Error("No active booking hold");
      }
      const response = await bookingsApi.confirmBooking({
        booking_id: holdData.booking_id,
        lock_token: holdData.lock_token,
        otp,
        name,
        email: email || undefined,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setConfirmedBooking({
        booking_id: data.booking_id,
        total_amount: data.total_amount,
        car_details: data.car_details,
      });
      setStep("success");
      setError("");
    },
    onError: (err: any) => {
      const errorMsg =
        err.response?.data?.detail || "Failed to confirm booking";
      if (
        errorMsg.includes("OTP expired") ||
        errorMsg.includes("Invalid OTP")
      ) {
        setError(errorMsg);
      } else {
        setError(errorMsg);
        setStep("failed");
      }
    },
  });

  const handleRequestOtp = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Please enter your name");
      return;
    }
    if (!phone.match(/^\+91[6-9]\d{9}$/)) {
      setError("Please enter a valid Indian phone number");
      return;
    }
    setError("");
    initiateMutation.mutate();
  };

  const handleConfirmBooking = (e: React.FormEvent) => {
    e.preventDefault();
    if (otp.length !== 6) {
      setError("Please enter a 6-digit OTP");
      return;
    }
    setError("");
    confirmMutation.mutate();
  };

  const handleResendOtp = () => {
    setOtp("");
    setHoldData(null);
    initiateMutation.mutate();
  };

  if (isLoadingCar) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-12 w-12 text-zoomcar-green animate-spin" />
      </div>
    );
  }

  if (!car) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center">
        <AlertCircle className="h-16 w-16 text-red-500 mb-4" />
        <h1 className="text-2xl font-bold mb-2">Car Not Found</h1>
        <p className="text-gray-600">
          The car you&apos;re looking for doesn&apos;t exist.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="container mx-auto px-4 max-w-4xl">
        {/* Progress indicator */}
        <div className="flex items-center justify-center mb-8 space-x-4">
          {["Your Details", "Verify OTP", "Confirmed"].map((label, index) => {
            const stepIndex = {
              details: 0,
              otp: 1,
              confirming: 2,
              success: 2,
              failed: 2,
            }[step];
            const isActive = index <= stepIndex;
            const isCurrent = index === stepIndex;

            return (
              <div key={label} className="flex items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${
                    isActive
                      ? "bg-zoomcar-green text-white"
                      : "bg-gray-200 text-gray-500"
                  } ${isCurrent ? "ring-4 ring-zoomcar-green/30" : ""}`}
                >
                  {index + 1}
                </div>
                <span
                  className={`ml-2 text-sm ${isActive ? "text-gray-800" : "text-gray-400"}`}
                >
                  {label}
                </span>
                {index < 2 && (
                  <div
                    className={`w-12 h-0.5 mx-2 ${isActive ? "bg-zoomcar-green" : "bg-gray-200"}`}
                  />
                )}
              </div>
            );
          })}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl shadow-md p-6">
              {/* Car Info */}
              <div className="flex flex-col md:flex-row gap-6 mb-6">
                <div className="relative w-full md:w-48 h-32 bg-gray-200 rounded-lg overflow-hidden flex-shrink-0">
                  <Image
                    src={getCarImageByMakeModel(car.make, car.model)}
                    alt={`${car.make} ${car.model}`}
                    fill
                    className="object-cover"
                  />
                </div>
                <div>
                  <h1 className="text-2xl font-bold mb-1 text-gray-900">
                    {car.make} {car.model}
                  </h1>
                  <p className="text-gray-500">{car.year}</p>
                  <div className="flex items-center mt-2 text-gray-600">
                    <MapPin className="h-4 w-4 mr-1" />
                    {car.location.name}, {car.location.city}
                  </div>
                </div>
              </div>

              {/* Trip Details */}
              <div className="border-t pt-6 mb-6">
                <h2 className="font-semibold text-lg mb-4 text-gray-900">
                  Trip Details
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex items-start space-x-3">
                    <Calendar className="h-5 w-5 text-zoomcar-green flex-shrink-0 mt-1" />
                    <div>
                      <p className="text-sm text-gray-500">Pickup</p>
                      <p className="font-medium text-gray-900">
                        {format(startDate, "PPP")}
                      </p>
                      <p className="text-gray-600">{format(startDate, "p")}</p>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <Clock className="h-5 w-5 text-zoomcar-green flex-shrink-0 mt-1" />
                    <div>
                      <p className="text-sm text-gray-500">Drop-off</p>
                      <p className="font-medium text-gray-900">
                        {format(endDate, "PPP")}
                      </p>
                      <p className="text-gray-600">{format(endDate, "p")}</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Error Display */}
              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  {error}
                </div>
              )}

              {/* Step: User Details Form */}
              {step === "details" && (
                <form onSubmit={handleRequestOtp} className="border-t pt-6">
                  <h2 className="font-semibold text-lg mb-4 text-gray-900">
                    Your Details
                  </h2>
                  <p className="text-gray-600 text-sm mb-4">
                    Enter your details to proceed. We&apos;ll send an OTP to
                    verify your phone number.
                  </p>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Full Name *
                      </label>
                      <div className="relative">
                        <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                        <input
                          type="text"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          placeholder="Enter your full name"
                          className="w-full pl-10 pr-4 py-3 border rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent text-gray-900"
                          required
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Email (Optional)
                      </label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                        <input
                          type="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          placeholder="Enter your email"
                          className="w-full pl-10 pr-4 py-3 border rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent text-gray-900"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Phone Number *
                      </label>
                      <div className="relative">
                        <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                        <input
                          type="tel"
                          value={phone}
                          onChange={(e) => setPhone(e.target.value)}
                          placeholder="+919876543210"
                          className="w-full pl-10 pr-4 py-3 border rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent text-gray-900"
                          required
                        />
                      </div>
                      <p className="text-xs text-gray-500 mt-1">
                        Format: +91XXXXXXXXXX (Indian mobile number)
                      </p>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={initiateMutation.isPending}
                    className="w-full mt-6 bg-zoomcar-green text-white py-3 rounded-lg font-semibold hover:bg-green-600 transition-colors flex items-center justify-center disabled:opacity-50"
                  >
                    {initiateMutation.isPending ? (
                      <>
                        <Loader2 className="h-5 w-5 animate-spin mr-2" />
                        Sending OTP...
                      </>
                    ) : (
                      "Continue & Verify"
                    )}
                  </button>
                </form>
              )}

              {/* Step: OTP Verification */}
              {step === "otp" && (
                <form onSubmit={handleConfirmBooking} className="border-t pt-6">
                  <h2 className="font-semibold text-lg mb-4 text-gray-900">
                    Verify OTP
                  </h2>
                  <p className="text-gray-600 text-sm mb-4">
                    Enter the 6-digit OTP sent to your WhatsApp on {phone}
                  </p>

                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      OTP Code
                    </label>
                    <input
                      type="text"
                      value={otp}
                      onChange={(e) =>
                        setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))
                      }
                      placeholder="Enter 6-digit OTP"
                      className="w-full px-4 py-3 text-center text-2xl tracking-widest border rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent text-gray-900"
                      maxLength={6}
                      required
                    />
                  </div>

                  <div className="text-center mb-4">
                    {countdown > 0 ? (
                      <p className="text-sm text-gray-500">
                        Resend OTP in{" "}
                        <span className="font-semibold text-zoomcar-green">
                          {countdown}s
                        </span>
                      </p>
                    ) : (
                      <button
                        type="button"
                        onClick={handleResendOtp}
                        disabled={initiateMutation.isPending}
                        className="text-sm text-zoomcar-green hover:underline"
                      >
                        Resend OTP
                      </button>
                    )}
                  </div>

                  <div className="flex space-x-3">
                    <button
                      type="button"
                      onClick={() => setStep("details")}
                      className="flex-1 py-3 border border-gray-300 rounded-lg font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                      Back
                    </button>
                    <button
                      type="submit"
                      disabled={confirmMutation.isPending || otp.length !== 6}
                      className="flex-1 bg-zoomcar-green text-white py-3 rounded-lg font-semibold hover:bg-green-600 transition-colors flex items-center justify-center disabled:opacity-50"
                    >
                      {confirmMutation.isPending ? (
                        <>
                          <Loader2 className="h-5 w-5 animate-spin mr-2" />
                          Confirming...
                        </>
                      ) : (
                        "Confirm Booking"
                      )}
                    </button>
                  </div>
                </form>
              )}

              {/* Step: Success */}
              {step === "success" && confirmedBooking && (
                <div className="border-t pt-6 text-center py-8">
                  <CheckCircle2 className="h-16 w-16 text-green-500 mx-auto mb-4" />
                  <h2 className="text-2xl font-bold text-green-600 mb-2">
                    Booking Confirmed!
                  </h2>
                  <p className="text-gray-600 mb-2">
                    Your booking ID:{" "}
                    <span className="font-mono font-semibold">
                      {confirmedBooking.booking_id.slice(0, 8)}...
                    </span>
                  </p>
                  <p className="text-gray-600 mb-6">
                    {confirmedBooking.car_details.make}{" "}
                    {confirmedBooking.car_details.model} (
                    {confirmedBooking.car_details.year})
                  </p>
                  <p className="text-lg font-semibold text-gray-900 mb-6">
                    Total: ₹{confirmedBooking.total_amount.toFixed(2)}
                  </p>
                  <button
                    onClick={() => router.push("/")}
                    className="bg-zoomcar-green text-white px-8 py-3 rounded-lg font-semibold hover:bg-green-600 transition-colors"
                  >
                    Back to Home
                  </button>
                </div>
              )}

              {/* Step: Failed */}
              {step === "failed" && (
                <div className="border-t pt-6 text-center py-8">
                  <AlertCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
                  <h2 className="text-xl font-bold text-red-600 mb-2">
                    Booking Failed
                  </h2>
                  <p className="text-gray-600 mb-6">
                    {error || "Something went wrong"}
                  </p>
                  <button
                    onClick={() => {
                      setStep("details");
                      setError("");
                      setOtp("");
                    }}
                    className="bg-zoomcar-green text-white px-8 py-3 rounded-lg font-semibold hover:bg-green-600 transition-colors"
                  >
                    Try Again
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Price Summary Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl shadow-md p-6 sticky top-20">
              <h2 className="font-semibold text-lg mb-4 text-gray-900">
                Price Summary
              </h2>

              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Base fare</span>
                  <span className="text-gray-900">
                    ₹{car.base_hourly_rate}/hr × {durationHours.toFixed(1)}hrs
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Subtotal</span>
                  <span className="text-gray-900">
                    ₹{estimatedAmount.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-green-600">
                  <span>Insurance</span>
                  <span>Included</span>
                </div>
                <div className="border-t pt-3 flex justify-between font-semibold text-lg">
                  <span className="text-gray-900">Total</span>
                  <span className="text-zoomcar-green">
                    ₹
                    {bookingPreview?.total_amount?.toFixed(2) ||
                      estimatedAmount.toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Trust badges */}
              <div className="mt-6 pt-4 border-t space-y-2">
                <div className="flex items-center text-sm text-gray-600">
                  <Shield className="h-4 w-4 text-green-500 mr-2" />
                  Fully insured
                </div>
                <div className="flex items-center text-sm text-gray-600">
                  <CheckCircle2 className="h-4 w-4 text-green-500 mr-2" />
                  Free cancellation
                </div>
                <div className="flex items-center text-sm text-gray-600">
                  <Car className="h-4 w-4 text-green-500 mr-2" />
                  24/7 roadside assistance
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function BookingPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="h-12 w-12 text-zoomcar-green animate-spin" />
        </div>
      }
    >
      <BookingContent />
    </Suspense>
  );
}
