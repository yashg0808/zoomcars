-- Zoomcar Clone Database Schema
-- Production-ready with all fixes applied
-- PostgreSQL 15+

-- =============================================
-- Enable Required Extensions
-- =============================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- Create Enum Types
-- =============================================

CREATE TYPE transmission_type AS ENUM ('MANUAL', 'AUTOMATIC');
CREATE TYPE fuel_type AS ENUM ('PETROL', 'DIESEL', 'ELECTRIC', 'CNG');
CREATE TYPE booking_status AS ENUM ('PENDING', 'CONFIRMED', 'CANCELLED', 'EXPIRED', 'COMPLETED');

-- =============================================
-- Table: users
-- =============================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone VARCHAR(15) UNIQUE NOT NULL,
    name VARCHAR(100),
    email VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_phone ON users(phone);
CREATE INDEX idx_users_created_at ON users(created_at DESC);

-- =============================================
-- Table: locations (Car Hubs)
-- =============================================

CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(50) NOT NULL,
    address TEXT,
    coordinates GEOGRAPHY(POINT, 4326) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_locations_geo ON locations USING GIST(coordinates);
CREATE INDEX idx_locations_city ON locations(city) WHERE is_active = TRUE;

-- =============================================
-- Table: cars
-- =============================================

CREATE TABLE cars (
    id SERIAL PRIMARY KEY,
    location_id INT NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
    make VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    year INT NOT NULL CHECK (year >= 2015 AND year <= EXTRACT(YEAR FROM NOW()) + 1),
    image_url TEXT,
    transmission transmission_type NOT NULL,
    fuel_type fuel_type NOT NULL,
    seating_capacity INT CHECK (seating_capacity BETWEEN 2 AND 8),
    base_hourly_rate DECIMAL(10, 2) NOT NULL CHECK (base_hourly_rate > 0),
    rating DECIMAL(2, 1) DEFAULT 4.5 CHECK (rating BETWEEN 0 AND 5),
    total_trips INT DEFAULT 0 CHECK (total_trips >= 0),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cars_location ON cars(location_id) WHERE is_active = TRUE;
CREATE INDEX idx_cars_type ON cars(transmission, fuel_type) WHERE is_active = TRUE;
CREATE INDEX idx_cars_rate ON cars(base_hourly_rate ASC);

-- =============================================
-- Table: bookings (CRITICAL - With Double Booking Prevention)
-- =============================================

CREATE TABLE bookings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    car_id INT NOT NULL REFERENCES cars(id) ON DELETE RESTRICT,
    
    -- Booking Period
    booking_start TIMESTAMPTZ NOT NULL,
    booking_end TIMESTAMPTZ NOT NULL,
    
    -- Total Period Including Buffer (used for exclusion constraint)
    -- Includes 1 hour buffer after drop-off for cleaning
    total_period tstzrange NOT NULL,
    
    -- Status & Payment
    status booking_status NOT NULL DEFAULT 'PENDING',
    payment_order_id VARCHAR(100),
    payment_id VARCHAR(100),
    total_amount DECIMAL(10, 2) NOT NULL CHECK (total_amount > 0),
    
    -- Expiration for PENDING bookings
    expires_at TIMESTAMPTZ,
    
    -- Idempotency key (prevents duplicate requests)
    idempotency_key VARCHAR(100) UNIQUE,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CHECK (booking_start < booking_end),
    CHECK (status != 'PENDING' OR expires_at IS NOT NULL),
    
    -- EXCLUSION CONSTRAINT: Prevents double bookings
    -- Only considers CONFIRMED and PENDING bookings
    -- Uses EXPIRED status instead of NOW() for deterministic behavior
    CONSTRAINT no_double_booking EXCLUDE USING GIST (
        car_id WITH =,
        total_period WITH &&
    ) WHERE (status IN ('CONFIRMED', 'PENDING'))
);

CREATE INDEX idx_bookings_user ON bookings(user_id, created_at DESC);
CREATE INDEX idx_bookings_car ON bookings(car_id, status);
CREATE INDEX idx_bookings_status ON bookings(status, expires_at) WHERE status = 'PENDING';
CREATE INDEX idx_bookings_payment_order ON bookings(payment_order_id) WHERE payment_order_id IS NOT NULL;
CREATE INDEX idx_bookings_idempotency ON bookings(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- GiST index for fast range queries
CREATE INDEX idx_bookings_period ON bookings USING GIST (car_id, total_period);

-- =============================================
-- Table: booking_history (Audit Log)
-- =============================================

CREATE TABLE booking_history (
    id SERIAL PRIMARY KEY,
    booking_id UUID NOT NULL REFERENCES bookings(id),
    old_status booking_status,
    new_status booking_status NOT NULL,
    changed_by VARCHAR(50),
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_booking_history_booking ON booking_history(booking_id, created_at DESC);

-- =============================================
-- Helper Functions
-- =============================================

-- Function to calculate total_period with buffer
CREATE OR REPLACE FUNCTION calculate_total_period(
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    buffer_hours DECIMAL DEFAULT 1.0
) RETURNS tstzrange AS $$
BEGIN
    RETURN tstzrange(
        start_time,
        end_time + (buffer_hours || ' hours')::INTERVAL,
        '[)'
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to auto-update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to log booking status changes
CREATE OR REPLACE FUNCTION log_booking_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO booking_history (booking_id, old_status, new_status, changed_by)
        VALUES (NEW.id, OLD.status, NEW.status, 'SYSTEM');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Triggers
-- =============================================

-- Auto-update updated_at for users
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-update updated_at for bookings
CREATE TRIGGER update_bookings_updated_at 
    BEFORE UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Log booking status changes
CREATE TRIGGER log_booking_status 
    AFTER UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION log_booking_status_change();

-- =============================================
-- Sample Data
-- =============================================

-- Insert sample locations
INSERT INTO locations (name, city, address, coordinates) VALUES
('Indira Nagar Metro', 'Bangalore', '100 Feet Road, Indira Nagar, Bangalore 560038', 
 ST_SetSRID(ST_MakePoint(77.6412, 12.9716), 4326)),
('Koramangala Hub', 'Bangalore', '5th Block, Koramangala, Bangalore 560095', 
 ST_SetSRID(ST_MakePoint(77.6309, 12.9352), 4326)),
('HSR Layout', 'Bangalore', 'Sector 2, HSR Layout, Bangalore 560102', 
 ST_SetSRID(ST_MakePoint(77.6473, 12.9121), 4326)),
('Whitefield Station', 'Bangalore', 'ITPL Main Road, Whitefield, Bangalore 560066', 
 ST_SetSRID(ST_MakePoint(77.7500, 12.9698), 4326)),
('MG Road Hub', 'Bangalore', 'MG Road Metro Station, Bangalore 560001', 
 ST_SetSRID(ST_MakePoint(77.6067, 12.9758), 4326)),
('Bandra West', 'Mumbai', 'Hill Road, Bandra West, Mumbai 400050', 
 ST_SetSRID(ST_MakePoint(72.8296, 19.0596), 4326)),
('Andheri East', 'Mumbai', 'MIDC, Andheri East, Mumbai 400093', 
 ST_SetSRID(ST_MakePoint(72.8691, 19.1136), 4326)),
('Connaught Place', 'Delhi', 'Block A, Connaught Place, New Delhi 110001', 
 ST_SetSRID(ST_MakePoint(77.2177, 28.6315), 4326)),
('Gurgaon Cyber City', 'Delhi', 'DLF Cyber City, Gurgaon 122002', 
 ST_SetSRID(ST_MakePoint(77.0892, 28.4949), 4326)),
('T Nagar', 'Chennai', 'Pondy Bazaar, T Nagar, Chennai 600017', 
 ST_SetSRID(ST_MakePoint(80.2399, 13.0418), 4326)),
('OMR', 'Chennai', 'Thoraipakkam, OMR, Chennai 600097', 
 ST_SetSRID(ST_MakePoint(80.2279, 12.9312), 4326)),
('Hitech City', 'Hyderabad', 'Cyber Towers, Hitech City, Hyderabad 500081', 
 ST_SetSRID(ST_MakePoint(78.3772, 17.4474), 4326)),
('Banjara Hills', 'Hyderabad', 'Road No 12, Banjara Hills, Hyderabad 500034', 
 ST_SetSRID(ST_MakePoint(78.4411, 17.4156), 4326)),
('Gachibowli', 'Hyderabad', 'Biodiversity Junction, Gachibowli, Hyderabad 500032', 
 ST_SetSRID(ST_MakePoint(78.3489, 17.4401), 4326)),
('Viman Nagar', 'Pune', 'Phoenix Market City, Viman Nagar, Pune 411014', 
 ST_SetSRID(ST_MakePoint(73.9147, 18.5679), 4326)),
('Hinjewadi', 'Pune', 'Phase 1, Hinjewadi IT Park, Pune 411057', 
 ST_SetSRID(ST_MakePoint(73.7378, 18.5912), 4326)),
('Koregaon Park', 'Pune', 'North Main Road, Koregaon Park, Pune 411001', 
 ST_SetSRID(ST_MakePoint(73.8943, 18.5362), 4326));

-- Insert sample cars
INSERT INTO cars (location_id, make, model, year, image_url, transmission, fuel_type, seating_capacity, base_hourly_rate, rating, total_trips) VALUES
-- Bangalore - Indira Nagar
(1, 'Maruti', 'Swift', 2023, 'https://images.zoomcar.com/swift.jpg', 'MANUAL', 'PETROL', 5, 99.00, 4.5, 150),
(1, 'Maruti', 'Dzire', 2022, 'https://images.zoomcar.com/dzire.jpg', 'AUTOMATIC', 'PETROL', 5, 129.00, 4.6, 120),
(1, 'Hyundai', 'i20', 2023, 'https://images.zoomcar.com/i20.jpg', 'MANUAL', 'PETROL', 5, 119.00, 4.7, 89),
(1, 'Hyundai', 'Creta', 2023, 'https://images.zoomcar.com/creta.jpg', 'AUTOMATIC', 'DIESEL', 5, 199.00, 4.8, 67),
(1, 'Tata', 'Nexon EV', 2024, 'https://images.zoomcar.com/nexon-ev.jpg', 'AUTOMATIC', 'ELECTRIC', 5, 249.00, 4.9, 45),

-- Bangalore - Koramangala
(2, 'Maruti', 'Baleno', 2023, 'https://images.zoomcar.com/baleno.jpg', 'AUTOMATIC', 'PETROL', 5, 139.00, 4.5, 98),
(2, 'Honda', 'City', 2022, 'https://images.zoomcar.com/city.jpg', 'AUTOMATIC', 'PETROL', 5, 179.00, 4.7, 112),
(2, 'Kia', 'Seltos', 2023, 'https://images.zoomcar.com/seltos.jpg', 'AUTOMATIC', 'DIESEL', 5, 219.00, 4.8, 78),
(2, 'Mahindra', 'XUV700', 2023, 'https://images.zoomcar.com/xuv700.jpg', 'AUTOMATIC', 'DIESEL', 7, 299.00, 4.9, 34),

-- Bangalore - HSR Layout
(3, 'Maruti', 'Wagon R', 2022, 'https://images.zoomcar.com/wagonr.jpg', 'MANUAL', 'CNG', 5, 79.00, 4.3, 201),
(3, 'Hyundai', 'Venue', 2023, 'https://images.zoomcar.com/venue.jpg', 'MANUAL', 'PETROL', 5, 149.00, 4.5, 67),
(3, 'Toyota', 'Innova Crysta', 2022, 'https://images.zoomcar.com/innova.jpg', 'AUTOMATIC', 'DIESEL', 7, 349.00, 4.8, 89),

-- Mumbai - Bandra
(6, 'Maruti', 'Swift', 2023, 'https://images.zoomcar.com/swift.jpg', 'MANUAL', 'PETROL', 5, 109.00, 4.4, 178),
(6, 'Tata', 'Tiago', 2023, 'https://images.zoomcar.com/tiago.jpg', 'MANUAL', 'PETROL', 5, 89.00, 4.3, 223),
(6, 'Hyundai', 'Creta', 2024, 'https://images.zoomcar.com/creta.jpg', 'AUTOMATIC', 'PETROL', 5, 229.00, 4.7, 56),

-- Delhi - Connaught Place
(8, 'Maruti', 'Ertiga', 2023, 'https://images.zoomcar.com/ertiga.jpg', 'MANUAL', 'CNG', 7, 159.00, 4.5, 134),
(8, 'Honda', 'Amaze', 2022, 'https://images.zoomcar.com/amaze.jpg', 'AUTOMATIC', 'PETROL', 5, 129.00, 4.4, 167),
(8, 'MG', 'Hector', 2023, 'https://images.zoomcar.com/hector.jpg', 'AUTOMATIC', 'PETROL', 5, 249.00, 4.6, 45),
(8, 'Maruti', 'Swift', 2023, 'https://images.zoomcar.com/swift.jpg', 'MANUAL', 'PETROL', 5, 99.00, 4.5, 189),
(8, 'Hyundai', 'Verna', 2023, 'https://images.zoomcar.com/verna.jpg', 'AUTOMATIC', 'PETROL', 5, 169.00, 4.6, 92),
(8, 'Tata', 'Harrier', 2023, 'https://images.zoomcar.com/harrier.jpg', 'AUTOMATIC', 'DIESEL', 5, 279.00, 4.7, 38),

-- Delhi - Gurgaon Cyber City
(9, 'BMW', '3 Series', 2023, 'https://images.zoomcar.com/bmw3.jpg', 'AUTOMATIC', 'PETROL', 5, 599.00, 4.9, 23),
(9, 'Mercedes', 'A-Class', 2023, 'https://images.zoomcar.com/aclass.jpg', 'AUTOMATIC', 'PETROL', 5, 649.00, 4.9, 18),
(9, 'Hyundai', 'Creta', 2024, 'https://images.zoomcar.com/creta.jpg', 'AUTOMATIC', 'PETROL', 5, 209.00, 4.7, 67),
(9, 'Kia', 'Carens', 2023, 'https://images.zoomcar.com/carens.jpg', 'AUTOMATIC', 'DIESEL', 7, 239.00, 4.6, 54),
(9, 'Maruti', 'Grand Vitara', 2024, 'https://images.zoomcar.com/vitara.jpg', 'AUTOMATIC', 'PETROL', 5, 259.00, 4.8, 41),

-- Mumbai - Andheri East
(7, 'Maruti', 'Brezza', 2023, 'https://images.zoomcar.com/brezza.jpg', 'MANUAL', 'PETROL', 5, 139.00, 4.5, 145),
(7, 'Tata', 'Punch', 2023, 'https://images.zoomcar.com/punch.jpg', 'MANUAL', 'PETROL', 5, 99.00, 4.4, 187),
(7, 'Honda', 'City', 2022, 'https://images.zoomcar.com/city.jpg', 'AUTOMATIC', 'PETROL', 5, 179.00, 4.6, 98),
(7, 'Mahindra', 'Thar', 2023, 'https://images.zoomcar.com/thar.jpg', 'MANUAL', 'DIESEL', 4, 329.00, 4.8, 42),
(7, 'Hyundai', 'i20', 2023, 'https://images.zoomcar.com/i20.jpg', 'MANUAL', 'PETROL', 5, 119.00, 4.5, 134),

-- More Mumbai - Bandra
(6, 'Kia', 'Sonet', 2023, 'https://images.zoomcar.com/sonet.jpg', 'AUTOMATIC', 'DIESEL', 5, 169.00, 4.6, 89),
(6, 'Maruti', 'Baleno', 2023, 'https://images.zoomcar.com/baleno.jpg', 'AUTOMATIC', 'PETROL', 5, 139.00, 4.5, 112),
(6, 'Toyota', 'Glanza', 2023, 'https://images.zoomcar.com/glanza.jpg', 'MANUAL', 'PETROL', 5, 109.00, 4.4, 156),

-- Chennai - T Nagar
(10, 'Maruti', 'Swift', 2023, 'https://images.zoomcar.com/swift.jpg', 'MANUAL', 'PETROL', 5, 99.00, 4.5, 167),
(10, 'Hyundai', 'Grand i10', 2022, 'https://images.zoomcar.com/grandi10.jpg', 'MANUAL', 'PETROL', 5, 79.00, 4.3, 234),
(10, 'Toyota', 'Innova Crysta', 2023, 'https://images.zoomcar.com/innova.jpg', 'AUTOMATIC', 'DIESEL', 7, 349.00, 4.8, 76),
(10, 'Maruti', 'Ciaz', 2022, 'https://images.zoomcar.com/ciaz.jpg', 'AUTOMATIC', 'PETROL', 5, 149.00, 4.5, 98),
(10, 'Tata', 'Nexon', 2023, 'https://images.zoomcar.com/nexon.jpg', 'MANUAL', 'PETROL', 5, 139.00, 4.6, 87),

-- Chennai - OMR
(11, 'Hyundai', 'Creta', 2024, 'https://images.zoomcar.com/creta.jpg', 'AUTOMATIC', 'PETROL', 5, 209.00, 4.7, 54),
(11, 'Kia', 'Seltos', 2023, 'https://images.zoomcar.com/seltos.jpg', 'AUTOMATIC', 'DIESEL', 5, 219.00, 4.7, 67),
(11, 'Maruti', 'Dzire', 2023, 'https://images.zoomcar.com/dzire.jpg', 'AUTOMATIC', 'PETROL', 5, 129.00, 4.5, 145),
(11, 'Honda', 'Amaze', 2022, 'https://images.zoomcar.com/amaze.jpg', 'AUTOMATIC', 'PETROL', 5, 119.00, 4.4, 178),
(11, 'Tata', 'Tiago EV', 2024, 'https://images.zoomcar.com/tiago-ev.jpg', 'AUTOMATIC', 'ELECTRIC', 5, 159.00, 4.6, 32),

-- Hyderabad - Hitech City
(12, 'Hyundai', 'Verna', 2023, 'https://images.zoomcar.com/verna.jpg', 'AUTOMATIC', 'PETROL', 5, 169.00, 4.6, 89),
(12, 'Kia', 'Carens', 2023, 'https://images.zoomcar.com/carens.jpg', 'AUTOMATIC', 'PETROL', 7, 229.00, 4.7, 56),
(12, 'Maruti', 'Swift', 2023, 'https://images.zoomcar.com/swift.jpg', 'MANUAL', 'PETROL', 5, 99.00, 4.5, 198),
(12, 'Tata', 'Nexon EV', 2024, 'https://images.zoomcar.com/nexon-ev.jpg', 'AUTOMATIC', 'ELECTRIC', 5, 249.00, 4.8, 34),
(12, 'Honda', 'City', 2023, 'https://images.zoomcar.com/city.jpg', 'AUTOMATIC', 'PETROL', 5, 179.00, 4.7, 78),
(12, 'Mahindra', 'XUV300', 2023, 'https://images.zoomcar.com/xuv300.jpg', 'MANUAL', 'DIESEL', 5, 149.00, 4.5, 112),

-- Hyderabad - Banjara Hills
(13, 'BMW', 'X1', 2023, 'https://images.zoomcar.com/bmwx1.jpg', 'AUTOMATIC', 'PETROL', 5, 549.00, 4.9, 19),
(13, 'Audi', 'Q3', 2023, 'https://images.zoomcar.com/audiq3.jpg', 'AUTOMATIC', 'PETROL', 5, 579.00, 4.9, 15),
(13, 'Mercedes', 'GLA', 2023, 'https://images.zoomcar.com/gla.jpg', 'AUTOMATIC', 'PETROL', 5, 599.00, 4.9, 12),
(13, 'Hyundai', 'Tucson', 2023, 'https://images.zoomcar.com/tucson.jpg', 'AUTOMATIC', 'DIESEL', 5, 329.00, 4.8, 34),
(13, 'Jeep', 'Compass', 2023, 'https://images.zoomcar.com/compass.jpg', 'AUTOMATIC', 'DIESEL', 5, 349.00, 4.7, 28),

-- Hyderabad - Gachibowli
(14, 'Maruti', 'Baleno', 2023, 'https://images.zoomcar.com/baleno.jpg', 'AUTOMATIC', 'PETROL', 5, 139.00, 4.5, 134),
(14, 'Hyundai', 'i20', 2023, 'https://images.zoomcar.com/i20.jpg', 'MANUAL', 'PETROL', 5, 119.00, 4.6, 156),
(14, 'Tata', 'Altroz', 2023, 'https://images.zoomcar.com/altroz.jpg', 'MANUAL', 'PETROL', 5, 109.00, 4.5, 167),
(14, 'Kia', 'Sonet', 2023, 'https://images.zoomcar.com/sonet.jpg', 'MANUAL', 'DIESEL', 5, 159.00, 4.6, 89),
(14, 'Volkswagen', 'Virtus', 2023, 'https://images.zoomcar.com/virtus.jpg', 'AUTOMATIC', 'PETROL', 5, 189.00, 4.7, 54),

-- Pune - Viman Nagar
(15, 'Maruti', 'Swift', 2023, 'https://images.zoomcar.com/swift.jpg', 'MANUAL', 'PETROL', 5, 99.00, 4.5, 189),
(15, 'Hyundai', 'Venue', 2023, 'https://images.zoomcar.com/venue.jpg', 'MANUAL', 'PETROL', 5, 149.00, 4.5, 112),
(15, 'Tata', 'Punch', 2023, 'https://images.zoomcar.com/punch.jpg', 'MANUAL', 'PETROL', 5, 99.00, 4.4, 178),
(15, 'Honda', 'Amaze', 2022, 'https://images.zoomcar.com/amaze.jpg', 'AUTOMATIC', 'PETROL', 5, 129.00, 4.5, 134),
(15, 'Maruti', 'Ertiga', 2023, 'https://images.zoomcar.com/ertiga.jpg', 'MANUAL', 'CNG', 7, 159.00, 4.6, 87),

-- Pune - Hinjewadi
(16, 'Hyundai', 'Creta', 2024, 'https://images.zoomcar.com/creta.jpg', 'AUTOMATIC', 'PETROL', 5, 209.00, 4.7, 67),
(16, 'Kia', 'Seltos', 2023, 'https://images.zoomcar.com/seltos.jpg', 'AUTOMATIC', 'DIESEL', 5, 219.00, 4.7, 54),
(16, 'Maruti', 'Grand Vitara', 2024, 'https://images.zoomcar.com/vitara.jpg', 'AUTOMATIC', 'PETROL', 5, 249.00, 4.8, 38),
(16, 'Tata', 'Harrier', 2023, 'https://images.zoomcar.com/harrier.jpg', 'AUTOMATIC', 'DIESEL', 5, 279.00, 4.7, 29),
(16, 'Mahindra', 'Scorpio N', 2023, 'https://images.zoomcar.com/scorpio.jpg', 'AUTOMATIC', 'DIESEL', 7, 299.00, 4.6, 34),

-- Pune - Koregaon Park
(17, 'BMW', '2 Series', 2023, 'https://images.zoomcar.com/bmw2.jpg', 'AUTOMATIC', 'PETROL', 5, 549.00, 4.9, 21),
(17, 'Mini', 'Cooper', 2023, 'https://images.zoomcar.com/mini.jpg', 'AUTOMATIC', 'PETROL', 4, 599.00, 4.9, 14),
(17, 'Volkswagen', 'Taigun', 2023, 'https://images.zoomcar.com/taigun.jpg', 'AUTOMATIC', 'PETROL', 5, 209.00, 4.7, 56),
(17, 'Skoda', 'Slavia', 2023, 'https://images.zoomcar.com/slavia.jpg', 'AUTOMATIC', 'PETROL', 5, 189.00, 4.6, 67),
(17, 'MG', 'Astor', 2023, 'https://images.zoomcar.com/astor.jpg', 'AUTOMATIC', 'PETROL', 5, 229.00, 4.7, 45);

-- =============================================
-- Verification Queries
-- =============================================

-- Verify extensions
SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'btree_gist', 'uuid-ossp');

-- Verify tables
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Verify indexes
SELECT indexname FROM pg_indexes WHERE schemaname = 'public';

-- Verify constraints
SELECT conname FROM pg_constraint WHERE contype = 'x'; -- Exclusion constraints
