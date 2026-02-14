"use client";

import { useState, useEffect, useCallback } from "react";
import { AlertTriangle } from "lucide-react";

interface BookingTimerProps {
  expiresAt: string;
  serverTime: string;
  onExpire: () => void;
}

export function BookingTimer({
  expiresAt,
  serverTime,
  onExpire,
}: BookingTimerProps) {
  const [timeLeft, setTimeLeft] = useState<number>(0);
  const [isInitialized, setIsInitialized] = useState(false);

  const calculateTimeLeft = useCallback(() => {
    // Calculate initial time accounting for server-client clock skew
    const expiryTime = new Date(expiresAt).getTime();
    const serverTimestamp = new Date(serverTime).getTime();
    const clientTimestamp = Date.now();
    const clockSkew = clientTimestamp - serverTimestamp;

    const adjustedTimeLeft = Math.max(
      0,
      expiryTime - clientTimestamp + clockSkew,
    );
    return Math.floor(adjustedTimeLeft / 1000);
  }, [expiresAt, serverTime]);

  useEffect(() => {
    // Initialize
    const initialTimeLeft = calculateTimeLeft();
    setTimeLeft(initialTimeLeft);
    setIsInitialized(true);

    // Set up countdown interval
    const interval = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          onExpire();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [calculateTimeLeft, onExpire]);

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;
  const isUrgent = timeLeft < 60;
  const isCritical = timeLeft < 30;

  if (!isInitialized) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4 animate-pulse">
        <div className="h-8 bg-yellow-200 rounded w-24 mx-auto" />
      </div>
    );
  }

  return (
    <div
      className={`rounded-lg p-4 mb-4 transition-colors ${
        isCritical
          ? "bg-red-100 border border-red-300"
          : isUrgent
            ? "bg-orange-100 border border-orange-300"
            : "bg-yellow-50 border border-yellow-200"
      }`}
    >
      <div className="flex items-center justify-center space-x-2 mb-2">
        {isUrgent && (
          <AlertTriangle
            className={`h-5 w-5 ${
              isCritical ? "text-red-600 animate-pulse" : "text-orange-600"
            }`}
          />
        )}
        <p className="text-sm font-medium text-gray-700">
          Complete payment within
        </p>
      </div>

      <div
        className={`text-center text-4xl font-bold font-mono ${
          isCritical
            ? "text-red-600 animate-pulse"
            : isUrgent
              ? "text-orange-600"
              : "text-gray-800"
        }`}
      >
        {String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}
      </div>

      {isUrgent && (
        <p
          className={`text-center text-sm mt-2 font-medium ${
            isCritical ? "text-red-600" : "text-orange-600"
          }`}
        >
          {isCritical
            ? "⚠️ Hurry! Booking about to expire!"
            : "⏰ Time running out!"}
        </p>
      )}
    </div>
  );
}
