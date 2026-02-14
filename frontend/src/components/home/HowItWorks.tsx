import { Search, CreditCard, Car, MapPin } from "lucide-react";

const steps = [
  {
    icon: Search,
    title: "Search & Select",
    description:
      "Enter your location and travel dates. Browse available cars and pick your favorite.",
  },
  {
    icon: CreditCard,
    title: "Book & Pay",
    description:
      "Complete your booking with secure online payment. Get instant confirmation.",
  },
  {
    icon: MapPin,
    title: "Pick Up",
    description:
      "Visit the pickup location at your scheduled time. Complete quick verification.",
  },
  {
    icon: Car,
    title: "Drive Away",
    description:
      "Hit the road! Enjoy your self-drive experience with 24/7 roadside assistance.",
  },
];

export function HowItWorks() {
  return (
    <div>
      <h2 className="text-3xl font-bold text-center mb-4">How It Works</h2>
      <p className="text-gray-600 text-center mb-12 max-w-2xl mx-auto">
        Renting a car has never been easier. Follow these simple steps to get
        started.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
        {steps.map((step, index) => (
          <div key={index} className="relative">
            {/* Connector line (hidden on mobile and last item) */}
            {index < steps.length - 1 && (
              <div className="hidden md:block absolute top-12 left-1/2 w-full h-0.5 bg-gray-200 z-0" />
            )}

            <div className="relative z-10 text-center">
              {/* Icon */}
              <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-zoomcar-green/10 mb-4">
                <step.icon className="h-10 w-10 text-zoomcar-green" />
              </div>

              {/* Step number */}
              <div className="absolute -top-2 left-1/2 transform -translate-x-1/2 w-8 h-8 bg-zoomcar-green rounded-full flex items-center justify-center text-white font-bold text-sm">
                {index + 1}
              </div>

              {/* Content */}
              <h3 className="font-semibold text-lg mb-2">{step.title}</h3>
              <p className="text-gray-600 text-sm">{step.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
