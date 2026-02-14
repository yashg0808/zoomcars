/**
 * Car Image Utility
 * Maps car make+model to high-quality stock images from Unsplash
 */

// Map of car make+model to high-quality stock images (Unsplash CDN)
const CAR_IMAGE_MAP: Record<string, string> = {
  // Maruti
  "maruti swift":
    "https://images.unsplash.com/photo-1609521263047-f8f205293f24?w=400&h=300&fit=crop",
  "maruti dzire":
    "https://images.unsplash.com/photo-1590362891991-f776e747a588?w=400&h=300&fit=crop",
  "maruti baleno":
    "https://images.unsplash.com/photo-1619767886558-efdc259cde1a?w=400&h=300&fit=crop",
  "maruti wagon r":
    "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=400&h=300&fit=crop",
  "maruti ertiga":
    "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=400&h=300&fit=crop",
  "maruti brezza":
    "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=400&h=300&fit=crop",
  "maruti ciaz":
    "https://images.unsplash.com/photo-1550355291-bbee04a92027?w=400&h=300&fit=crop",
  "maruti grand vitara":
    "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=400&h=300&fit=crop",

  // Hyundai
  "hyundai i20":
    "https://images.unsplash.com/photo-1605559424843-9e4c228bf1c2?w=400&h=300&fit=crop",
  "hyundai creta":
    "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=400&h=300&fit=crop",
  "hyundai venue":
    "https://images.unsplash.com/photo-1606611013016-969c19ba27bb?w=400&h=300&fit=crop",
  "hyundai verna":
    "https://images.unsplash.com/photo-1580273916550-e323be2ae537?w=400&h=300&fit=crop",
  "hyundai grand i10":
    "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=400&h=300&fit=crop",
  "hyundai tucson":
    "https://images.unsplash.com/photo-1625231334168-30f9c597dc8d?w=400&h=300&fit=crop",

  // Tata
  "tata nexon":
    "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?w=400&h=300&fit=crop",
  "tata nexon ev":
    "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?w=400&h=300&fit=crop",
  "tata punch":
    "https://images.unsplash.com/photo-1502877338535-766e1452684a?w=400&h=300&fit=crop",
  "tata tiago":
    "https://images.unsplash.com/photo-1541899481282-d53bffe3c35d?w=400&h=300&fit=crop",
  "tata tiago ev":
    "https://images.unsplash.com/photo-1560958089-b8a1929cea89?w=400&h=300&fit=crop",
  "tata harrier":
    "https://images.unsplash.com/photo-1606016159991-dfe4f2746ad5?w=400&h=300&fit=crop",
  "tata altroz":
    "https://images.unsplash.com/photo-1583121274602-3e2820c69888?w=400&h=300&fit=crop",

  // Honda
  "honda city":
    "https://images.unsplash.com/photo-1618843479313-40f8afb4b4d8?w=400&h=300&fit=crop",
  "honda amaze":
    "https://images.unsplash.com/photo-1617469767053-d3b523a0b982?w=400&h=300&fit=crop",

  // Kia
  "kia seltos":
    "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=400&h=300&fit=crop",
  "kia sonet":
    "https://images.unsplash.com/photo-1606016159991-dfe4f2746ad5?w=400&h=300&fit=crop",
  "kia carens":
    "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=400&h=300&fit=crop",

  // Mahindra
  "mahindra xuv700":
    "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=400&h=300&fit=crop",
  "mahindra xuv300":
    "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=400&h=300&fit=crop",
  "mahindra thar":
    "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=400&h=300&fit=crop",
  "mahindra scorpio n":
    "https://images.unsplash.com/photo-1606016159991-dfe4f2746ad5?w=400&h=300&fit=crop",

  // Toyota
  "toyota innova crysta":
    "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=400&h=300&fit=crop",
  "toyota glanza":
    "https://images.unsplash.com/photo-1609521263047-f8f205293f24?w=400&h=300&fit=crop",

  // Premium
  "bmw 3 series":
    "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=400&h=300&fit=crop",
  "bmw x1":
    "https://images.unsplash.com/photo-1556189250-72ba954cfc2b?w=400&h=300&fit=crop",
  "bmw 2 series":
    "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=400&h=300&fit=crop",
  "mercedes a-class":
    "https://images.unsplash.com/photo-1618843479313-40f8afb4b4d8?w=400&h=300&fit=crop",
  "mercedes gla":
    "https://images.unsplash.com/photo-1606016159991-dfe4f2746ad5?w=400&h=300&fit=crop",
  "audi q3":
    "https://images.unsplash.com/photo-1606664515524-ed2f786a0bd6?w=400&h=300&fit=crop",
  "mini cooper":
    "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&h=300&fit=crop",
  "jeep compass":
    "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=400&h=300&fit=crop",

  // MG / Volkswagen / Skoda
  "mg hector":
    "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=400&h=300&fit=crop",
  "mg astor":
    "https://images.unsplash.com/photo-1606016159991-dfe4f2746ad5?w=400&h=300&fit=crop",
  "volkswagen virtus":
    "https://images.unsplash.com/photo-1580273916550-e323be2ae537?w=400&h=300&fit=crop",
  "volkswagen taigun":
    "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=400&h=300&fit=crop",
  "skoda slavia":
    "https://images.unsplash.com/photo-1550355291-bbee04a92027?w=400&h=300&fit=crop",
};

// Default fallback images by car type
export const FALLBACK_BY_TYPE: Record<string, string> = {
  suv: "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=400&h=300&fit=crop",
  sedan:
    "https://images.unsplash.com/photo-1550355291-bbee04a92027?w=400&h=300&fit=crop",
  hatchback:
    "https://images.unsplash.com/photo-1609521263047-f8f205293f24?w=400&h=300&fit=crop",
  mpv: "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=400&h=300&fit=crop",
  electric:
    "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?w=400&h=300&fit=crop",
  default:
    "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=400&h=300&fit=crop",
};

interface CarInfo {
  make: string;
  model: string;
  fuel_type?: string;
  seating_capacity?: number;
}

/**
 * Get a valid image URL for a car
 * Falls back to stock images based on make/model
 */
export function getCarImageUrl(
  car: CarInfo,
  originalUrl?: string | null,
): string {
  // If there's a valid original URL that's not the fake zoomcar domain, use it
  if (originalUrl && !originalUrl.includes("zoomcar.com")) {
    return originalUrl;
  }

  // Try exact make+model match
  const key = `${car.make} ${car.model}`.toLowerCase();
  if (CAR_IMAGE_MAP[key]) {
    return CAR_IMAGE_MAP[key];
  }

  // Try just the model (for variations like "Nexon" vs "Nexon EV")
  const modelKey = Object.keys(CAR_IMAGE_MAP).find((k) =>
    k.includes(car.model.toLowerCase()),
  );
  if (modelKey) {
    return CAR_IMAGE_MAP[modelKey];
  }

  // Fallback by car type
  if (car.fuel_type === "Electric" || car.fuel_type === "ELECTRIC") {
    return FALLBACK_BY_TYPE.electric;
  }
  if (car.seating_capacity && car.seating_capacity >= 7) {
    return FALLBACK_BY_TYPE.mpv;
  }

  // SUVs (common models)
  const suvModels = [
    "creta",
    "seltos",
    "venue",
    "nexon",
    "harrier",
    "xuv",
    "scorpio",
    "thar",
    "hector",
    "compass",
    "tucson",
  ];
  if (suvModels.some((s) => car.model.toLowerCase().includes(s))) {
    return FALLBACK_BY_TYPE.suv;
  }

  // Sedans
  const sedanModels = [
    "city",
    "verna",
    "ciaz",
    "amaze",
    "dzire",
    "virtus",
    "slavia",
  ];
  if (sedanModels.some((s) => car.model.toLowerCase().includes(s))) {
    return FALLBACK_BY_TYPE.sedan;
  }

  return FALLBACK_BY_TYPE.default;
}

/**
 * Simple fallback for when only make+model are available (like booking page)
 */
export function getCarImageByMakeModel(make: string, model: string): string {
  return getCarImageUrl({ make, model });
}

export default getCarImageUrl;
