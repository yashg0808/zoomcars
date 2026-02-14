"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Phone, ArrowRight, Loader2 } from "lucide-react";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

type Step = "phone" | "otp";

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();

  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("+91");
  const [otp, setOtp] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [countdown, setCountdown] = useState(0);

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      await authApi.sendOtp(phone);
      setStep("otp");
      startCountdown(60);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Failed to send OTP. Please try again.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const response = await authApi.verifyOtp(phone, otp);
      setAuth(response.data.user, response.data.access_token);
      router.push("/");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Invalid OTP. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const startCountdown = (seconds: number) => {
    setCountdown(seconds);
    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const handleResendOtp = async () => {
    if (countdown > 0) return;

    setIsLoading(true);
    try {
      await authApi.sendOtp(phone);
      startCountdown(60);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to resend OTP.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center bg-gray-50 py-12 px-4">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-zoomcar-dark">Welcome Back</h1>
          <p className="text-gray-600 mt-2">
            {step === "phone"
              ? "Enter your phone number to continue"
              : "Enter the OTP sent to your phone"}
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-xl shadow-lg p-8">
          {step === "phone" ? (
            <form onSubmit={handleSendOtp}>
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Phone Number
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+91 9876543210"
                    className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent"
                    pattern="^\+91[6-9]\d{9}$"
                    required
                  />
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Enter your 10-digit Indian mobile number
                </p>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading || phone.length !== 13}
                className="w-full bg-zoomcar-green text-white py-3 rounded-lg font-semibold hover:bg-green-600 transition-colors flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <>
                    Continue
                    <ArrowRight className="ml-2 h-5 w-5" />
                  </>
                )}
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerifyOtp}>
              <div className="mb-2">
                <p className="text-sm text-gray-600">
                  OTP sent to <span className="font-medium">{phone}</span>
                </p>
                <button
                  type="button"
                  onClick={() => setStep("phone")}
                  className="text-sm text-zoomcar-green hover:underline"
                >
                  Change
                </button>
              </div>

              <div className="mb-6 mt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Enter OTP
                </label>
                <input
                  type="text"
                  value={otp}
                  onChange={(e) =>
                    setOtp(e.target.value.replace(/\D/g, "").slice(0, 4))
                  }
                  placeholder="Enter 4-digit OTP"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent text-center text-2xl tracking-widest"
                  maxLength={4}
                  required
                />
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading || otp.length !== 4}
                className="w-full bg-zoomcar-green text-white py-3 rounded-lg font-semibold hover:bg-green-600 transition-colors flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  "Verify OTP"
                )}
              </button>

              <div className="mt-4 text-center">
                {countdown > 0 ? (
                  <p className="text-sm text-gray-500">
                    Resend OTP in {countdown}s
                  </p>
                ) : (
                  <button
                    type="button"
                    onClick={handleResendOtp}
                    className="text-sm text-zoomcar-green hover:underline"
                  >
                    Resend OTP
                  </button>
                )}
              </div>
            </form>
          )}
        </div>

        {/* Terms */}
        <p className="text-center text-xs text-gray-500 mt-6">
          By continuing, you agree to our{" "}
          <a href="/terms" className="text-zoomcar-green hover:underline">
            Terms of Service
          </a>{" "}
          and{" "}
          <a href="/privacy" className="text-zoomcar-green hover:underline">
            Privacy Policy
          </a>
        </p>
      </div>
    </div>
  );
}
