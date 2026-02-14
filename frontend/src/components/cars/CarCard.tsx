"use client";

import Image from "next/image";
import Link from "next/link";
import { Star, Users, Fuel, Settings, MapPin } from "lucide-react";
import { CarSearchResult } from "@/lib/api";
import { getCarImageUrl, FALLBACK_BY_TYPE } from "@/lib/carImages";

interface CarCardProps {
  car: CarSearchResult;
  startTime: string;
  endTime: string;
}

export function CarCard({ car, startTime, endTime }: CarCardProps) {
  const bookingUrl = `/booking/${car.id}?start=${encodeURIComponent(startTime)}&end=${encodeURIComponent(endTime)}`;
  const imageUrl = getCarImageUrl(car, car.image_url);

  return (
    <div className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-lg transition-shadow duration-300">
      <div className="flex flex-col md:flex-row">
        {/* Image */}
        <div className="relative w-full md:w-48 h-48 md:h-auto bg-gray-200 flex-shrink-0">
          <Image
            src={imageUrl}
            alt={`${car.make} ${car.model}`}
            fill
            className="object-cover"
            onError={(e) => {
              (e.target as HTMLImageElement).src = FALLBACK_BY_TYPE.default;
            }}
          />
          {/* Rating Badge */}
          <div className="absolute top-2 right-2 bg-white/90 px-2 py-1 rounded-full flex items-center space-x-1">
            <Star className="h-3 w-3 text-yellow-500 fill-yellow-500" />
            <span className="text-xs font-semibold">{car.rating}</span>
          </div>
        </div>

        {/* Content */}
        <div className="flex-grow p-4">
          <div className="flex justify-between items-start mb-2">
            <div>
              <h3 className="font-bold text-lg">
                {car.make} {car.model}
              </h3>
              <p className="text-gray-500 text-sm">{car.year}</p>
            </div>
            <div className="text-right">
              {/* {car.dynamic_price !== car.base_hourly_rate && (
                <p className="text-gray-400 text-sm line-through">
                  ₹{car.base_hourly_rate}
                </p>
              )} */}
              <p className="text-zoomcar-green font-bold text-xl">
                ₹{car.dynamic_price}
              </p>
              <p className="text-gray-500 text-xs">per hour</p>
            </div>
          </div>

          {/* Features */}
          <div className="flex flex-wrap gap-3 text-sm text-gray-600 mb-3">
            <div className="flex items-center bg-gray-100 px-2 py-1 rounded">
              <Settings className="h-3 w-3 mr-1" />
              {car.transmission}
            </div>
            <div className="flex items-center bg-gray-100 px-2 py-1 rounded">
              <Fuel className="h-3 w-3 mr-1" />
              {car.fuel_type}
            </div>
            <div className="flex items-center bg-gray-100 px-2 py-1 rounded">
              <Users className="h-3 w-3 mr-1" />
              {car.seating_capacity} seats
            </div>
          </div>

          {/* Location */}
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center text-gray-500">
              <MapPin className="h-4 w-4 mr-1" />
              {car.location.name} • {car.distance_km} km away
            </div>
            <p className="text-gray-400 text-xs">{car.total_trips} trips</p>
          </div>

          {/* CTA */}
          <Link href={bookingUrl}>
            <button className="mt-4 w-full bg-zoomcar-green text-white py-2 rounded-lg font-semibold hover:bg-green-600 transition-colors">
              Book Now
            </button>
          </Link>
        </div>
      </div>
    </div>
  );
}
