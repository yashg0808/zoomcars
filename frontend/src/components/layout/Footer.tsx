import Link from "next/link";
import { Car, Phone, Mail, MapPin } from "lucide-react";

export function Footer() {
  return (
    <footer className="bg-zoomcar-dark text-white">
      <div className="container mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div>
            <Link href="/" className="flex items-center space-x-2 mb-4">
              <Car className="h-8 w-8 text-zoomcar-green" />
              <span className="text-xl font-bold">Zoomcar</span>
            </Link>
            <p className="text-gray-400 text-sm">
              India's largest self-drive car rental platform. Drive anywhere,
              anytime.
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="font-semibold mb-4">Quick Links</h3>
            <ul className="space-y-2 text-gray-400 text-sm">
              <li>
                <Link
                  href="/search"
                  className="hover:text-white transition-colors"
                >
                  Search Cars
                </Link>
              </li>
              <li>
                <Link
                  href="/locations"
                  className="hover:text-white transition-colors"
                >
                  Locations
                </Link>
              </li>
              <li>
                <Link
                  href="/about"
                  className="hover:text-white transition-colors"
                >
                  About Us
                </Link>
              </li>
              <li>
                <Link
                  href="/faq"
                  className="hover:text-white transition-colors"
                >
                  FAQs
                </Link>
              </li>
            </ul>
          </div>

          {/* Cities */}
          <div>
            <h3 className="font-semibold mb-4">Popular Cities</h3>
            <ul className="space-y-2 text-gray-400 text-sm">
              <li>
                <Link
                  href="/search?city=Bangalore"
                  className="hover:text-white transition-colors"
                >
                  Bangalore
                </Link>
              </li>
              <li>
                <Link
                  href="/search?city=Mumbai"
                  className="hover:text-white transition-colors"
                >
                  Mumbai
                </Link>
              </li>
              <li>
                <Link
                  href="/search?city=Delhi"
                  className="hover:text-white transition-colors"
                >
                  Delhi
                </Link>
              </li>
              <li>
                <Link
                  href="/search?city=Chennai"
                  className="hover:text-white transition-colors"
                >
                  Chennai
                </Link>
              </li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h3 className="font-semibold mb-4">Contact Us</h3>
            <ul className="space-y-3 text-gray-400 text-sm">
              <li className="flex items-center space-x-2">
                <Phone className="h-4 w-4" />
                <span>+91 80 6666 7777</span>
              </li>
              <li className="flex items-center space-x-2">
                <Mail className="h-4 w-4" />
                <span>support@zoomcar.com</span>
              </li>
              <li className="flex items-start space-x-2">
                <MapPin className="h-4 w-4 mt-1" />
                <span>
                  Bengaluru, Karnataka
                  <br />
                  India - 560001
                </span>
              </li>
            </ul>
          </div>
        </div>

        <div className="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400 text-sm">
          <p>
            &copy; {new Date().getFullYear()} Zoomcar Clone. All rights
            reserved.
          </p>
          <div className="mt-2 space-x-4">
            <Link
              href="/privacy"
              className="hover:text-white transition-colors"
            >
              Privacy Policy
            </Link>
            <Link href="/terms" className="hover:text-white transition-colors">
              Terms of Service
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
