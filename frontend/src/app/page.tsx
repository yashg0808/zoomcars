import { Suspense } from "react";
import { SearchForm } from "@/components/search/SearchForm";
import { FeaturedCars } from "@/components/cars/FeaturedCars";
import { HowItWorks } from "@/components/home/HowItWorks";
import { WhyChooseUs } from "@/components/home/WhyChooseUs";

export default function HomePage() {
  return (
    <div>
      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-zoomcar-dark to-gray-900 text-white">
        <div className="container mx-auto px-4 py-16 md:py-24">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 animate-fadeIn">
              Self-Drive Car Rentals
            </h1>
            <p className="text-lg md:text-xl text-gray-300 mb-8 animate-fadeIn">
              Drive anywhere, anytime. Choose from 1000+ cars across 50+ cities
              in India.
            </p>
          </div>

          {/* Search Form */}
          <div className="max-w-4xl mx-auto mt-8">
            <Suspense fallback={<SearchFormSkeleton />}>
              <SearchForm />
            </Suspense>
          </div>
        </div>

        {/* Wave divider */}
        <div className="absolute bottom-0 left-0 right-0">
          <svg viewBox="0 0 1440 100" className="w-full h-auto fill-white">
            <path d="M0,64L48,58.7C96,53,192,43,288,48C384,53,480,75,576,80C672,85,768,75,864,64C960,53,1056,43,1152,42.7C1248,43,1344,53,1392,58.7L1440,64L1440,100L1392,100C1344,100,1248,100,1152,100C1056,100,960,100,864,100C768,100,672,100,576,100C480,100,384,100,288,100C192,100,96,100,48,100L0,100Z" />
          </svg>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <HowItWorks />
        </div>
      </section>

      {/* Featured Cars */}
      {/* <section className="py-16 bg-gray-50">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold text-center mb-12 text-gray-900">
            Popular Cars
          </h2>
          <Suspense fallback={<FeaturedCarsSkeleton />}>
            <FeaturedCars />
          </Suspense>
        </div>
      </section> */}

      {/* Why Choose Us */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <WhyChooseUs />
        </div>
      </section>
    </div>
  );
}

function SearchFormSkeleton() {
  return (
    <div className="bg-white rounded-xl p-6 shadow-xl animate-pulse">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="h-12 bg-gray-200 rounded-lg" />
        <div className="h-12 bg-gray-200 rounded-lg" />
        <div className="h-12 bg-gray-200 rounded-lg" />
        <div className="h-12 bg-gray-200 rounded-lg" />
      </div>
    </div>
  );
}

function FeaturedCarsSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {[1, 2, 3].map((i) => (
        <div key={i} className="bg-white rounded-xl p-4 shadow animate-pulse">
          <div className="h-48 bg-gray-200 rounded-lg mb-4" />
          <div className="h-6 bg-gray-200 rounded w-3/4 mb-2" />
          <div className="h-4 bg-gray-200 rounded w-1/2" />
        </div>
      ))}
    </div>
  );
}
