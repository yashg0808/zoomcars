import { Shield, Clock, Wallet, Headphones, MapPin, Zap } from "lucide-react";

const benefits = [
  {
    icon: Shield,
    title: "Fully Insured",
    description:
      "All cars come with comprehensive insurance coverage for your peace of mind.",
  },
  {
    icon: Clock,
    title: "Flexible Timings",
    description:
      "Book by the hour, day, or week. Extend or modify your booking anytime.",
  },
  {
    icon: Wallet,
    title: "Best Prices",
    description:
      "Transparent pricing with no hidden charges. Get the best deals every time.",
  },
  {
    icon: Headphones,
    title: "24/7 Support",
    description:
      "Our support team is available round the clock for any assistance you need.",
  },
  {
    icon: MapPin,
    title: "Multiple Locations",
    description:
      "Pick up and drop off at convenient locations across 50+ cities in India.",
  },
  {
    icon: Zap,
    title: "Instant Booking",
    description:
      "Book your car in minutes with instant confirmation. No paperwork hassle.",
  },
];

export function WhyChooseUs() {
  return (
    <div>
      <h2 className="text-3xl font-bold text-center mb-4 text-gray-900">
        Why Choose Us
      </h2>
      <p className="text-gray-600 text-center mb-12 max-w-2xl mx-auto">
        We're committed to providing the best car rental experience in India.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {benefits.map((benefit, index) => (
          <div
            key={index}
            className="p-6 rounded-xl border border-gray-100 hover:border-zoomcar-green hover:shadow-lg transition-all duration-300"
          >
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-zoomcar-green/10 mb-4">
              <benefit.icon className="h-6 w-6 text-zoomcar-green" />
            </div>
            <h3 className="font-semibold text-lg mb-2">{benefit.title}</h3>
            <p className="text-gray-600 text-sm">{benefit.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
