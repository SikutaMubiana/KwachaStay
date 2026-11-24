-- Generated from schema.sql for PostgreSQL (Supabase).
-- Regenerate with: python scripts/migrate_sqlite_to_postgres.py --print-schema

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'tenant', -- 'tenant' or 'owner'
    preferred_city TEXT,
    profile_pic TEXT,
    is_admin INTEGER DEFAULT 0,
    host_verification_status TEXT DEFAULT 'unverified',
    host_verification_note TEXT,
    email_verified_at TIMESTAMP,
    email_verification_token TEXT,
    email_verification_token_hash TEXT,
    email_verification_expires DOUBLE PRECISION,
    email_verification_code_hash TEXT,
    email_verification_code_expires DOUBLE PRECISION,
    email_verification_sent_at DOUBLE PRECISION,
    email_verification_attempts INTEGER NOT NULL DEFAULT 0,
    phone_verified_at TIMESTAMP,
    phone_verification_token TEXT,
    phone_verification_expires DOUBLE PRECISION,
    phone_verification_sent_at DOUBLE PRECISION,
    phone_verification_attempts INTEGER NOT NULL DEFAULT 0,
    email_delivery_status TEXT DEFAULT 'unknown',
    email_delivery_last_event TEXT,
    email_bounced_at DOUBLE PRECISION,
    password_reset_token TEXT, -- legacy plaintext token, cleared when hashed token is issued
    password_reset_expires DOUBLE PRECISION, -- legacy expiry paired with password_reset_token
    password_reset_token_hash TEXT,
    session_version INTEGER NOT NULL DEFAULT 1,
    totp_secret TEXT,
    totp_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS properties (
    id BIGSERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price_per_night DOUBLE PRECISION NOT NULL, -- Storing as generic price value
    price_period TEXT DEFAULT 'night', -- 'night' or 'month'
    city TEXT NOT NULL DEFAULT 'Lusaka',
    compound TEXT NOT NULL,
    location_details TEXT,
    property_type TEXT NOT NULL DEFAULT 'House', -- House, Boarding House, Hotel, Villa, Guest House, Hostel
    listing_category TEXT DEFAULT 'rental',
    availability_status TEXT DEFAULT 'available',
    
    -- Specific Amenities
    bed_type TEXT, -- Single, Double, Bunk (primarily for hostels/guest houses)
    room_sharing TEXT, -- 'single' or 'shared' (for boarding houses / student apartments)
    room_capacity INTEGER, -- Number of people per room
    bedrooms INTEGER DEFAULT 1,
    bathrooms INTEGER DEFAULT 1,
    kitchen_type TEXT, -- Private, Shared, None
    has_sitting_room INTEGER DEFAULT 0,
    upfront_months INTEGER NOT NULL DEFAULT 1, -- Minimum upfront months required for monthly rentals
    hourly_rate DOUBLE PRECISION, -- Optional explicit hourly rate for Hotel/Villa/Hostel short stays (min 3 hours)
    furnishing_status TEXT DEFAULT 'unfurnished',
    master_self_contained INTEGER NOT NULL DEFAULT 0,
    zesco_meter_type TEXT DEFAULT '',
    listing_source TEXT DEFAULT 'owner',
    viewing_fee DOUBLE PRECISION NOT NULL DEFAULT 0,
    security_fence TEXT DEFAULT '',
    nearby_university TEXT DEFAULT '',
    campus_distance TEXT DEFAULT '',
    boarding_gender TEXT DEFAULT '',
    gate_curfew_policy TEXT DEFAULT '',
    bed_spaces_left INTEGER,
    semester_rate DOUBLE PRECISION,
    has_study_desk INTEGER NOT NULL DEFAULT 0,
    has_bed_mattress INTEGER NOT NULL DEFAULT 0,
    has_stove_fridge INTEGER NOT NULL DEFAULT 0,
    has_laundry_area INTEGER NOT NULL DEFAULT 0,
    has_study_backup_power INTEGER NOT NULL DEFAULT 0,
    yard_type TEXT DEFAULT '',
    has_paved_yard INTEGER NOT NULL DEFAULT 0,
    is_pet_friendly INTEGER NOT NULL DEFAULT 0,
    is_family_friendly INTEGER NOT NULL DEFAULT 0,
    has_private_entrance INTEGER NOT NULL DEFAULT 0,
    has_smart_tv INTEGER NOT NULL DEFAULT 0,
    couples_friendly INTEGER NOT NULL DEFAULT 0,
    allows_small_gatherings INTEGER NOT NULL DEFAULT 0,
    offers_airport_transfer INTEGER NOT NULL DEFAULT 0,
    video_tour_url TEXT DEFAULT '',
    availability_prompted_at TIMESTAMP,
    
    -- Lusaka Essentials & Luxury
    has_solar INTEGER DEFAULT 0,
    has_borehole INTEGER DEFAULT 0,
    has_pool INTEGER DEFAULT 0,
    has_garden INTEGER DEFAULT 0,
    has_bbq INTEGER DEFAULT 0,
    has_balcony INTEGER DEFAULT 0,
    has_ac INTEGER DEFAULT 0,
    has_wifi INTEGER DEFAULT 0,
    has_parking INTEGER DEFAULT 0,
    
    -- Status & Verification
    is_verified INTEGER DEFAULT 0,
    is_featured INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,

    image_main TEXT,
    agent_name TEXT,
    agent_phone TEXT,
    cancellation_policy TEXT DEFAULT 'moderate',
    house_rules TEXT,
    last_confirmed_at TIMESTAMP,
    cleaning_fee DOUBLE PRECISION NOT NULL DEFAULT 0,
    refundable_deposit DOUBLE PRECISION NOT NULL DEFAULT 0,
    utilities_included INTEGER NOT NULL DEFAULT 0,
    power_backup TEXT,
    water_supply TEXT,
    internet_availability TEXT,
    internet_speed_mbps INTEGER,
    arrival_instructions TEXT,
    arrival_directions TEXT,
    nearby_essentials TEXT,
    emergency_contact_name TEXT,
    emergency_contact_phone TEXT,
    checkin_time TEXT NOT NULL DEFAULT '15:00',
    checkout_time TEXT NOT NULL DEFAULT '10:00',
    self_checkin_method TEXT,
    main_photo_category TEXT DEFAULT 'other',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS property_images (
    id BIGSERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL,
    image_url TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id BIGSERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL, -- 1-5
    cleanliness_rating INTEGER,
    accuracy_rating INTEGER,
    communication_rating INTEGER,
    location_rating INTEGER,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (property_id) REFERENCES properties (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS review_photos (
    id BIGSERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL,
    image_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (review_id) REFERENCES reviews (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bookings (
    id BIGSERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL,
    user_id INTEGER, -- Link to registered user
    tenant_name TEXT NOT NULL,
    tenant_phone TEXT NOT NULL,
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    total_price DOUBLE PRECISION NOT NULL,
    base_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    service_fee DOUBLE PRECISION NOT NULL DEFAULT 0,
    cleaning_fee DOUBLE PRECISION NOT NULL DEFAULT 0,
    refundable_deposit DOUBLE PRECISION NOT NULL DEFAULT 0,
    payment_status TEXT DEFAULT 'pending', -- 'pending', 'paid', 'failed'
    booking_status TEXT DEFAULT 'pending', -- 'pending', 'confirmed', 'declined', 'cancelled'
    payment_method TEXT,
    duration INTEGER,
    duration_unit TEXT DEFAULT 'night', -- 'day' or 'month'
    tx_ref TEXT UNIQUE,
    refund_status TEXT DEFAULT 'none',
    payment_reference TEXT,
    payment_claim_reference TEXT,
    payment_claim_submitted_at TIMESTAMP,
    refund_reference TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_payment_reference
ON bookings(payment_reference)
WHERE payment_reference IS NOT NULL AND payment_reference != '';

CREATE TABLE IF NOT EXISTS payment_attempts (
    id BIGSERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL,
    tx_ref TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL DEFAULT 'flutterwave',
    status TEXT NOT NULL DEFAULT 'pending',
    checkout_url TEXT,
    provider_transaction_id TEXT,
    provider_reference TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings (id)
);

CREATE TABLE IF NOT EXISTS wishlists (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, property_id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    property_id INTEGER,
    content TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    parent_id INTEGER REFERENCES messages (id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users (id),
    FOREIGN KEY (receiver_id) REFERENCES users (id),
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

CREATE TABLE IF NOT EXISTS availability (
    id BIGSERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL,
    date DATE NOT NULL,
    status TEXT DEFAULT 'blocked', -- 'blocked', 'booked'
    UNIQUE(property_id, date),
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

CREATE TABLE IF NOT EXISTS payout_methods (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    provider TEXT NOT NULL, -- 'Bank Transfer', 'Mobile Money', 'Airtel Money', 'MTN Money'
    bank_name TEXT,
    account_name TEXT NOT NULL,
    account_number TEXT NOT NULL,
    branch_code TEXT,
    is_primary INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS saved_searches (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    search_query TEXT,
    compound TEXT,
    min_price DOUBLE PRECISION,
    max_price DOUBLE PRECISION,
    property_type TEXT,
    power_backup TEXT,
    water_supply TEXT,
    near_lat DOUBLE PRECISION,
    near_lon DOUBLE PRECISION,
    near_radius_km DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS property_reports (
    id BIGSERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL,
    reporter_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    details TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (property_id) REFERENCES properties (id),
    FOREIGN KEY (reporter_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS support_requests (
    id BIGSERIAL PRIMARY KEY,
    reporter_id INTEGER NOT NULL,
    booking_id INTEGER,
    category TEXT NOT NULL,
    details TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    admin_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reporter_id) REFERENCES users (id),
    FOREIGN KEY (booking_id) REFERENCES bookings (id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    link TEXT,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS trip_plans (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    share_token TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL DEFAULT 'My Lusaka shortlist',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trip_plan_items (
    trip_plan_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trip_plan_id, property_id),
    FOREIGN KEY (trip_plan_id) REFERENCES trip_plans (id) ON DELETE CASCADE,
    FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS calendar_feeds (
    property_id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS calendar_imports (
    id BIGSERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, source_name),
    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS calendar_import_events (
    id BIGSERIAL PRIMARY KEY,
    import_id INTEGER NOT NULL,
    event_uid TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    FOREIGN KEY (import_id) REFERENCES calendar_imports(id) ON DELETE CASCADE,
    UNIQUE(import_id, event_uid)
);

CREATE TABLE IF NOT EXISTS seasonal_pricing (
    id BIGSERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    price DOUBLE PRECISION,
    minimum_stay INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_date > start_date),
    CHECK (price IS NULL OR price >= 0),
    CHECK (minimum_stay BETWEEN 1 AND 365),
    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_seasonal_pricing_dates
ON seasonal_pricing(property_id, start_date, end_date);

CREATE TABLE IF NOT EXISTS payout_ledger (
    id BIGSERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL UNIQUE,
    owner_id INTEGER NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reference TEXT,
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS email_messages (
    id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_message_id TEXT,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    template_key TEXT,
    status TEXT NOT NULL DEFAULT 'accepted',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at DOUBLE PRECISION,
    delivered_at DOUBLE PRECISION,
    delayed_at DOUBLE PRECISION,
    bounced_at DOUBLE PRECISION,
    failed_at DOUBLE PRECISION,
    complained_at DOUBLE PRECISION,
    last_event_at DOUBLE PRECISION,
    failure_reason TEXT,
    UNIQUE(provider, provider_message_id)
);

CREATE TABLE IF NOT EXISTS email_webhook_events (
    id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, event_id)
);

CREATE TABLE IF NOT EXISTS email_rate_limits (
    action TEXT NOT NULL,
    rate_key TEXT NOT NULL,
    window_started DOUBLE PRECISION NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(action, rate_key)
);

CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    admin_id INTEGER,
    admin_email TEXT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    details TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_created_at
ON admin_audit_logs(created_at DESC);

CREATE TABLE IF NOT EXISTS property_viewings (
    id BIGSERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    viewing_date TEXT NOT NULL,
    viewing_time TEXT NOT NULL,
    visitor_name TEXT NOT NULL,
    visitor_phone TEXT NOT NULL,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    owner_response_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_property_viewings_owner ON property_viewings(owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_property_viewings_tenant ON property_viewings(tenant_id, created_at DESC);

CREATE OR REPLACE FUNCTION julianday(ts text, modifier text DEFAULT NULL)
RETURNS double precision
LANGUAGE sql STABLE
AS $$
    SELECT EXTRACT(EPOCH FROM (
        (CASE WHEN ts = 'now' THEN now()::text ELSE ts END)::timestamp
        + COALESCE(modifier, '0 days')::interval
    )) / 86400.0 + 2440587.5
$$;

CREATE OR REPLACE FUNCTION julianday(ts timestamp without time zone, modifier text DEFAULT NULL)
RETURNS double precision
LANGUAGE sql STABLE
AS $$
    SELECT julianday(ts::text, modifier)
$$;

CREATE OR REPLACE FUNCTION julianday(ts timestamp with time zone, modifier text DEFAULT NULL)
RETURNS double precision
LANGUAGE sql STABLE
AS $$
    SELECT julianday((ts AT TIME ZONE 'UTC')::text, modifier)
$$;

CREATE OR REPLACE FUNCTION distance_km(
    latitude_a double precision,
    longitude_a double precision,
    latitude_b double precision,
    longitude_b double precision
)
RETURNS double precision
LANGUAGE sql IMMUTABLE
AS $$
    SELECT CASE
        WHEN latitude_a IS NULL OR longitude_a IS NULL
             OR latitude_b IS NULL OR longitude_b IS NULL THEN NULL
        ELSE 6371 * 2 * ASIN(SQRT(LEAST(1,
            POWER(SIN(RADIANS(latitude_b - latitude_a) / 2), 2)
            + COS(RADIANS(latitude_a)) * COS(RADIANS(latitude_b))
            * POWER(SIN(RADIANS(longitude_b - longitude_a) / 2), 2)
        )))
    END
$$;

-- Supabase Storage bucket for listing images (public read).
INSERT INTO storage.buckets (id, name, public)
VALUES ('property-images', 'property-images', true)
ON CONFLICT (id) DO UPDATE SET public = EXCLUDED.public;
