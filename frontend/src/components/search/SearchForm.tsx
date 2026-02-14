"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Calendar,
  MapPin,
  Search,
  Clock,
  Building2,
  Loader2,
} from "lucide-react";
import { format, addHours, addDays, setHours, setMinutes } from "date-fns";
import { locationsApi, Location } from "@/lib/api";

export function SearchForm() {
  const router = useRouter();
  const [city, setCity] = useState("Bangalore");
  const [locations, setLocations] = useState<Location[]>([]);
  const [selectedLocation, setSelectedLocation] = useState<Location | null>(
    null,
  );
  const [isLoadingLocations, setIsLoadingLocations] = useState(false);
  const [startDate, setStartDate] = useState<Date>(getDefaultStartDate());
  const [endDate, setEndDate] = useState<Date>(getDefaultEndDate());
  const [isLoading, setIsLoading] = useState(false);

  function getDefaultStartDate() {
    // Tomorrow at 10 AM
    const tomorrow = addDays(new Date(), 1);
    return setMinutes(setHours(tomorrow, 10), 0);
  }

  function getDefaultEndDate() {
    // Tomorrow at 6 PM
    const tomorrow = addDays(new Date(), 1);
    return setMinutes(setHours(tomorrow, 18), 0);
  }

  // Fetch locations when city changes
  useEffect(() => {
    const fetchLocations = async () => {
      setIsLoadingLocations(true);
      setSelectedLocation(null);
      try {
        const response = await locationsApi.getLocations({ city });
        const locs = response.data;
        setLocations(locs);
        if (locs.length > 0) {
          setSelectedLocation(locs[0]);
        }
      } catch (error) {
        console.error("Failed to fetch locations:", error);
        setLocations([]);
      } finally {
        setIsLoadingLocations(false);
      }
    };

    fetchLocations();
  }, [city]);

  const handleLocationChange = (locationId: string) => {
    const loc = locations.find((l) => l.id === parseInt(locationId));
    setSelectedLocation(loc || null);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedLocation) {
      alert("Please select a pickup location");
      return;
    }

    setIsLoading(true);

    const params = new URLSearchParams({
      city,
      location_id: selectedLocation.id.toString(),
      location_name: selectedLocation.name,
      lat: selectedLocation.latitude.toString(),
      lng: selectedLocation.longitude.toString(),
      start_time: startDate.toISOString(),
      end_time: endDate.toISOString(),
    });

    router.push(`/search?${params.toString()}`);
  };

  const cities = [
    "Bangalore",
    "Mumbai",
    "Delhi",
    "Chennai",
    "Hyderabad",
    "Pune",
  ];

  return (
    <form onSubmit={handleSearch} className="bg-white rounded-xl p-6 shadow-xl">
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {/* City Select */}
        <div className="relative">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            <MapPin className="inline h-4 w-4 mr-1" />
            City
          </label>
          <select
            value={city}
            onChange={(e) => setCity(e.target.value)}
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent text-gray-900 bg-white"
          >
            {cities.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Location Select */}
        <div className="relative">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            <Building2 className="inline h-4 w-4 mr-1" />
            Pickup Location
          </label>
          <select
            value={selectedLocation?.id || ""}
            onChange={(e) => handleLocationChange(e.target.value)}
            disabled={isLoadingLocations || locations.length === 0}
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent text-gray-900 bg-white disabled:bg-gray-100 disabled:cursor-not-allowed"
          >
            {isLoadingLocations ? (
              <option value="">Loading...</option>
            ) : locations.length === 0 ? (
              <option value="">No locations available</option>
            ) : (
              locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))
            )}
          </select>
        </div>

        {/* Start Date/Time */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            <Calendar className="inline h-4 w-4 mr-1" />
            Pickup
          </label>
          <input
            type="datetime-local"
            value={format(startDate, "yyyy-MM-dd'T'HH:mm")}
            onChange={(e) => setStartDate(new Date(e.target.value))}
            min={format(new Date(), "yyyy-MM-dd'T'HH:mm")}
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent text-gray-900 bg-white"
          />
        </div>

        {/* End Date/Time */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            <Clock className="inline h-4 w-4 mr-1" />
            Drop-off
          </label>
          <input
            type="datetime-local"
            value={format(endDate, "yyyy-MM-dd'T'HH:mm")}
            onChange={(e) => setEndDate(new Date(e.target.value))}
            min={format(addHours(startDate, 1), "yyyy-MM-dd'T'HH:mm")}
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent text-gray-900 bg-white"
          />
        </div>

        {/* Search Button */}
        <div className="flex items-end">
          <button
            type="submit"
            disabled={isLoading || isLoadingLocations || !selectedLocation}
            className="w-full bg-zoomcar-green text-white p-3 rounded-lg font-semibold hover:bg-green-600 transition-colors flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 mr-2 animate-spin" />
            ) : (
              <Search className="h-5 w-5 mr-2" />
            )}
            Search Cars
          </button>
        </div>
      </div>

      {/* Duration Display */}
      <div className="mt-4 text-center text-sm text-gray-600">
        Duration: {calculateDuration(startDate, endDate)}
        {selectedLocation && (
          <span className="ml-2 text-gray-500">
            • Pickup: {selectedLocation.name}
          </span>
        )}
      </div>
    </form>
  );
}

function calculateDuration(start: Date, end: Date): string {
  const hours = Math.round(
    (end.getTime() - start.getTime()) / (1000 * 60 * 60),
  );
  if (hours < 24) {
    return `${hours} hour${hours !== 1 ? "s" : ""}`;
  }
  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  return `${days} day${days !== 1 ? "s" : ""}${remainingHours > 0 ? ` ${remainingHours}h` : ""}`;
}
