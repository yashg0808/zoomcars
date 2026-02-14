"use client";

import Image from "next/image";
import Link from "next/link";
import { Star, Users, Fuel, Settings } from "lucide-react";
import { getCarImageByMakeModel, FALLBACK_BY_TYPE } from "@/lib/carImages";

// Static featured cars data (in production, this would come from an API)
const featuredCars = [
  {
    id: 1,
    make: "Hyundai",
    model: "Creta",
    year: 2023,
    image_url: "/images/cars/creta.jpg",
    transmission: "Automatic",
    fuel_type: "Diesel",
    seating_capacity: 5,
    base_hourly_rate: 199,
    rating: 4.8,
    total_trips: 67,
    location: { name: "Koramangala Hub", city: "Bangalore" },
  },
  {
    id: 2,
    make: "Maruti",
    model: "Swift",
    year: 2023,
    image_url: "/images/cars/swift.jpg",
    transmission: "Manual",
    fuel_type: "Petrol",
    seating_capacity: 5,
    base_hourly_rate: 99,
    rating: 4.5,
    total_trips: 150,
    location: { name: "Indira Nagar Metro", city: "Bangalore" },
  },
  {
    id: 3,
    make: "Tata",
    model: "Nexon EV",
    year: 2024,
    image_url: "/images/cars/nexon-ev.jpg",
    transmission: "Automatic",
    fuel_type: "Electric",
    seating_capacity: 5,
    base_hourly_rate: 249,
    rating: 4.9,
    total_trips: 45,
    location: { name: "HSR Layout", city: "Bangalore" },
  },
];

export function FeaturedCars() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {featuredCars.map((car) => (
        <CarCard key={car.id} car={car} />
      ))}
    </div>
  );
}

interface CarCardProps {
  car: (typeof featuredCars)[0];
}

function CarCard({ car }: CarCardProps) {
  return (
    <Link href={`/cars/${car.id}`}>
      <div className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-xl transition-shadow duration-300 group">
        {/* Image */}
        <div className="relative h-48 bg-gray-200">
          <div className="absolute inset-0 bg-gradient-to-t from-black/30 to-transparent z-10" />
          <Image
            src={getCarImageByMakeModel(car.make, car.model)}
            alt={`${car.make} ${car.model}`}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-300"
            onError={(e) => {
              (e.target as HTMLImageElement).src = FALLBACK_BY_TYPE.default;
            }}
          />
          {/* Rating Badge */}
          <div className="absolute top-3 right-3 z-20 bg-white px-2 py-1 rounded-full flex items-center space-x-1">
            <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
            <span className="text-sm font-semibold">{car.rating}</span>
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          <div className="flex justify-between items-start mb-2">
            <div>
              <h3 className="font-bold text-lg">
                {car.make} {car.model}
              </h3>
              <p className="text-gray-500 text-sm">{car.year}</p>
            </div>
            <div className="text-right">
              <p className="text-zoomcar-green font-bold text-lg">
                ₹{car.base_hourly_rate}
              </p>
              <p className="text-gray-500 text-xs">per hour</p>
            </div>
          </div>

          {/* Features */}
          <div className="flex items-center space-x-4 text-sm text-gray-600 mb-3">
            <div className="flex items-center">
              <Settings className="h-4 w-4 mr-1" />
              {car.transmission}
            </div>
            <div className="flex items-center">
              <Fuel className="h-4 w-4 mr-1" />
              {car.fuel_type}
            </div>
            <div className="flex items-center">
              <Users className="h-4 w-4 mr-1" />
              {car.seating_capacity}
            </div>
          </div>

          {/* Location */}
          <p className="text-sm text-gray-500">📍 {car.location.name}</p>

          {/* CTA */}
          <button className="mt-4 w-full bg-zoomcar-green text-white py-2 rounded-lg font-semibold hover:bg-green-600 transition-colors">
            View Details
          </button>
        </div>
      </div>
    </Link>
  );
}
