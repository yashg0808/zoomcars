"use client";

import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState, Suspense } from "react";
import { carsApi, CarSearchResult } from "@/lib/api";
import { CarCard } from "@/components/cars/CarCard";
import { SearchFilters } from "@/components/search/SearchFilters";
import { Loader2, AlertCircle, Car, MapPin } from "lucide-react";

// Fallback city coordinates (only used if lat/lng not in URL)
const cityCoordinates: Record<string, { lat: number; lng: number }> = {
  Bangalore: { lat: 12.9716, lng: 77.5946 },
  Mumbai: { lat: 19.076, lng: 72.8777 },
  Delhi: { lat: 28.6139, lng: 77.209 },
  Chennai: { lat: 13.0827, lng: 80.2707 },
  Hyderabad: { lat: 17.385, lng: 78.4867 },
  Pune: { lat: 18.5204, lng: 73.8567 },
};

function SearchContent() {
  const searchParams = useSearchParams();

  // Get search parameters
  const city = searchParams.get("city") || "Bangalore";
  const locationName = searchParams.get("location_name") || null;
  const startTime = searchParams.get("start_time") || new Date().toISOString();
  const endTime =
    searchParams.get("end_time") ||
    new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString();

  // Get lat/lng from URL params (from selected location)
  // Fall back to city center if not provided
  const fallbackCoords = cityCoordinates[city] || cityCoordinates.Bangalore;
  const lat = parseFloat(searchParams.get("lat") || String(fallbackCoords.lat));
  const lng = parseFloat(searchParams.get("lng") || String(fallbackCoords.lng));

  // Filter state
  const [filters, setFilters] = useState({
    transmission: "",
    fuel_type: "",
    max_price: "",
    min_seats: "",
  });

  // Fetch cars - query key includes lat/lng for accurate caching
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["cars", city, lat, lng, startTime, endTime, filters],
    queryFn: async () => {
      const params: any = {
        city: city,
        lat: lat,
        lng: lng,
        start_time: startTime,
        end_time: endTime,
        limit: 50,
      };

      if (filters.transmission) params.transmission = filters.transmission;
      if (filters.fuel_type) params.fuel_type = filters.fuel_type;
      if (filters.max_price) params.max_price = parseFloat(filters.max_price);
      if (filters.min_seats) params.min_seats = parseInt(filters.min_seats);

      const response = await carsApi.search(params);
      return response.data;
    },
    staleTime: 60000, // 1 minute
  });

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm">
        <div className="container mx-auto px-4 py-6">
          <h1 className="text-2xl font-bold">Cars in {city}</h1>
          <div className="flex items-center gap-4 text-gray-600">
            {locationName && (
              <span className="flex items-center">
                <MapPin className="h-4 w-4 mr-1" />
                {locationName}
              </span>
            )}
            <span>
              {new Date(startTime).toLocaleDateString()} -{" "}
              {new Date(endTime).toLocaleDateString()}
            </span>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Filters Sidebar */}
          <div className="lg:col-span-1">
            <SearchFilters filters={filters} onFilterChange={setFilters} />
          </div>

          {/* Results */}
          <div className="lg:col-span-3">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-16">
                <Loader2 className="h-12 w-12 text-zoomcar-green animate-spin mb-4" />
                <p className="text-gray-600">Searching for available cars...</p>
              </div>
            ) : isError ? (
              <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
                <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
                <h3 className="font-semibold text-red-800 mb-2">
                  Error loading cars
                </h3>
                <p className="text-red-600 text-sm">
                  {(error as Error)?.message || "Please try again later"}
                </p>
              </div>
            ) : data?.cars?.length === 0 ? (
              <div className="bg-white rounded-lg p-12 text-center shadow">
                <Car className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                <h3 className="font-semibold text-xl mb-2">
                  No cars available
                </h3>
                <p className="text-gray-600">
                  Try adjusting your filters or selecting different dates
                </p>
              </div>
            ) : (
              <>
                <p className="text-gray-600 mb-4">
                  Found {data?.total_count || 0} cars near{" "}
                  {locationName || city}
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {data?.cars?.map((car: CarSearchResult) => (
                    <CarCard
                      key={car.id}
                      car={car}
                      startTime={startTime}
                      endTime={endTime}
                    />
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <Loader2 className="h-12 w-12 text-zoomcar-green animate-spin" />
        </div>
      }
    >
      <SearchContent />
    </Suspense>
  );
}
