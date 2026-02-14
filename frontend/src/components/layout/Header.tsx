"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X, Car, User, MapPin } from "lucide-react";
import { useAuthStore } from "@/store/auth";

export function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const { user, isAuthenticated, logout } = useAuthStore();

  return (
    <header className="bg-white shadow-sm sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2">
            <Car className="h-8 w-8 text-zoomcar-green" />
            <span className="text-xl font-bold text-zoomcar-dark">Zoomcar</span>
          </Link>

          {/* Desktop Navigation */}
          {/* <nav className="hidden md:flex items-center space-x-8">
            <Link
              href="/search"
              className="text-gray-600 hover:text-zoomcar-green transition-colors"
            >
              Search Cars
            </Link>
            <Link
              href="/locations"
              className="text-gray-600 hover:text-zoomcar-green transition-colors flex items-center"
            >
              <MapPin className="h-4 w-4 mr-1" />
              Locations
            </Link>
            {isAuthenticated ? (
              <div className="flex items-center space-x-4">
                <Link
                  href="/bookings"
                  className="text-gray-600 hover:text-zoomcar-green transition-colors"
                >
                  My Bookings
                </Link>
                <div className="relative group">
                  <button className="flex items-center space-x-2 text-gray-600 hover:text-zoomcar-green">
                    <User className="h-5 w-5" />
                    <span>{user?.name || user?.phone}</span>
                  </button>
                  <div className="absolute right-0 top-full mt-2 w-48 bg-white shadow-lg rounded-lg py-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all">
                    <Link
                      href="/profile"
                      className="block px-4 py-2 text-gray-600 hover:bg-gray-50"
                    >
                      Profile
                    </Link>
                    <button
                      onClick={logout}
                      className="w-full text-left px-4 py-2 text-red-600 hover:bg-gray-50"
                    >
                      Logout
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <Link
                href="/login"
                className="bg-zoomcar-green text-white px-6 py-2 rounded-lg hover:bg-green-600 transition-colors"
              >
                Login
              </Link>
            )}
          </nav> */}

          {/* Mobile menu button */}
          <button
            className="md:hidden p-2"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? (
              <X className="h-6 w-6" />
            ) : (
              <Menu className="h-6 w-6" />
            )}
          </button>
        </div>

        {/* Mobile Navigation */}
        {/* {isMenuOpen && (
          <div className="md:hidden py-4 border-t">
            <nav className="flex flex-col space-y-4">
              <Link
                href="/search"
                className="text-gray-600 hover:text-zoomcar-green"
                onClick={() => setIsMenuOpen(false)}
              >
                Search Cars
              </Link>
              <Link
                href="/locations"
                className="text-gray-600 hover:text-zoomcar-green"
                onClick={() => setIsMenuOpen(false)}
              >
                Locations
              </Link>
              {isAuthenticated ? (
                <>
                  <Link
                    href="/bookings"
                    className="text-gray-600 hover:text-zoomcar-green"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    My Bookings
                  </Link>
                  <Link
                    href="/profile"
                    className="text-gray-600 hover:text-zoomcar-green"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    Profile
                  </Link>
                  <button
                    onClick={() => {
                      logout();
                      setIsMenuOpen(false);
                    }}
                    className="text-left text-red-600"
                  >
                    Logout
                  </button>
                </>
              ) : (
                <Link
                  href="/login"
                  className="bg-zoomcar-green text-white px-6 py-2 rounded-lg text-center"
                  onClick={() => setIsMenuOpen(false)}
                >
                  Login
                </Link>
              )}
            </nav>
          </div>
        )} */}
      </div>
    </header>
  );
}
