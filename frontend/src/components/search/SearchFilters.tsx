"use client";

import { Filter, X } from "lucide-react";

interface SearchFiltersProps {
  filters: {
    transmission: string;
    fuel_type: string;
    max_price: string;
    min_seats: string;
  };
  onFilterChange: (filters: any) => void;
}

export function SearchFilters({ filters, onFilterChange }: SearchFiltersProps) {
  const handleChange = (key: string, value: string) => {
    onFilterChange({ ...filters, [key]: value });
  };

  const clearFilters = () => {
    onFilterChange({
      transmission: "",
      fuel_type: "",
      max_price: "",
      min_seats: "",
    });
  };

  const hasActiveFilters = Object.values(filters).some((v) => v !== "");

  return (
    <div className="bg-white rounded-xl shadow-md p-6 sticky top-20">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-lg flex items-center">
          <Filter className="h-5 w-5 mr-2" />
          Filters
        </h2>
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-sm text-red-500 hover:text-red-600 flex items-center"
          >
            <X className="h-4 w-4 mr-1" />
            Clear
          </button>
        )}
      </div>

      <div className="space-y-5">
        {/* Transmission */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Transmission
          </label>
          <select
            value={filters.transmission}
            onChange={(e) => handleChange("transmission", e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent"
          >
            <option value="">All</option>
            <option value="MANUAL">Manual</option>
            <option value="AUTOMATIC">Automatic</option>
          </select>
        </div>

        {/* Fuel Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Fuel Type
          </label>
          <select
            value={filters.fuel_type}
            onChange={(e) => handleChange("fuel_type", e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent"
          >
            <option value="">All</option>
            <option value="PETROL">Petrol</option>
            <option value="DIESEL">Diesel</option>
            <option value="ELECTRIC">Electric</option>
            <option value="CNG">CNG</option>
          </select>
        </div>

        {/* Max Price */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Max Price (per hour)
          </label>
          <select
            value={filters.max_price}
            onChange={(e) => handleChange("max_price", e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent"
          >
            <option value="">Any</option>
            <option value="100">Under ₹100</option>
            <option value="150">Under ₹150</option>
            <option value="200">Under ₹200</option>
            <option value="300">Under ₹300</option>
            <option value="500">Under ₹500</option>
          </select>
        </div>

        {/* Minimum Seats */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Minimum Seats
          </label>
          <select
            value={filters.min_seats}
            onChange={(e) => handleChange("min_seats", e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-zoomcar-green focus:border-transparent"
          >
            <option value="">Any</option>
            <option value="2">2+ seats</option>
            <option value="4">4+ seats</option>
            <option value="5">5+ seats</option>
            <option value="7">7+ seats</option>
          </select>
        </div>
      </div>
    </div>
  );
}
