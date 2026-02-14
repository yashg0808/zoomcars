/**
 * Razorpay Payment Integration
 * Handles payment flow with proper error handling
 */

declare global {
  interface Window {
    Razorpay: any;
  }
}

export interface PaymentOptions {
  orderId: string;
  amount: number;
  bookingId: string;
  userPhone: string;
  userName?: string;
  userEmail?: string;
  onSuccess: (response: RazorpaySuccessResponse) => void;
  onFailure: (error: RazorpayError) => void;
}

export interface RazorpaySuccessResponse {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

export interface RazorpayError {
  code: string;
  description: string;
  source: string;
  step: string;
  reason: string;
}

// Load Razorpay script dynamically
export function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) {
      resolve(true);
      return;
    }

    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

export async function initiatePayment(options: PaymentOptions): Promise<void> {
  // Load Razorpay script if not loaded
  const isLoaded = await loadRazorpayScript();
  if (!isLoaded) {
    options.onFailure({
      code: "SCRIPT_LOAD_ERROR",
      description: "Failed to load payment gateway",
      source: "client",
      step: "payment_init",
      reason: "script_load_failed",
    });
    return;
  }

  const razorpayKeyId = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;
  if (!razorpayKeyId) {
    console.error("Razorpay key not configured");
    options.onFailure({
      code: "CONFIG_ERROR",
      description: "Payment gateway not configured",
      source: "client",
      step: "payment_init",
      reason: "missing_key",
    });
    return;
  }

  const razorpayOptions = {
    key: razorpayKeyId,
    amount: options.amount * 100, // Amount in paise
    currency: "INR",
    name: "Zoomcar Clone",
    description: `Booking: ${options.bookingId.substring(0, 8)}...`,
    order_id: options.orderId,
    prefill: {
      contact: options.userPhone,
      name: options.userName || "",
      email: options.userEmail || "",
    },
    theme: {
      color: "#00b386", // Zoomcar green
    },
    handler: (response: RazorpaySuccessResponse) => {
      options.onSuccess(response);
    },
    modal: {
      ondismiss: () => {
        options.onFailure({
          code: "PAYMENT_CANCELLED",
          description: "Payment was cancelled by user",
          source: "user",
          step: "payment_modal",
          reason: "user_dismissed",
        });
      },
      escape: true,
      animation: true,
    },
    retry: {
      enabled: true,
      max_count: 3,
    },
  };

  try {
    const razorpay = new window.Razorpay(razorpayOptions);

    razorpay.on("payment.failed", (response: { error: RazorpayError }) => {
      options.onFailure(response.error);
    });

    razorpay.open();
  } catch (error) {
    options.onFailure({
      code: "RAZORPAY_ERROR",
      description: "Failed to initialize payment",
      source: "client",
      step: "payment_init",
      reason: String(error),
    });
  }
}

// Generate idempotency key for booking requests
export function generateIdempotencyKey(): string {
  const timestamp = Date.now().toString(36);
  const randomPart = Math.random().toString(36).substring(2, 10);
  return `${timestamp}-${randomPart}`;
}
