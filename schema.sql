CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'tenant', -- 'tenant' or 'owner'
    profile_pic TEXT,
    is_admin BOOLEAN DEFAULT 0,
    host_verification_status TEXT DEFAULT 'unverified',
    host_verification_note TEXT,
    email_verified_at TIMESTAMP,
    email_verification_token TEXT,
    email_verification_token_hash TEXT,
    email_verification_expires REAL,
    email_verification_code_hash TEXT,
    email_verification_code_expires REAL,
    email_verification_sent_at REAL,
    email_verification_attempts INTEGER NOT NULL DEFAULT 0,
    phone_verified_at TIMESTAMP,
    phone_verification_token TEXT,
    phone_verification_expires REAL,
    phone_verification_sent_at REAL,
    phone_verification_attempts INTEGER NOT NULL DEFAULT 0,
    email_delivery_status TEXT DEFAULT 'unknown',
    email_delivery_last_event TEXT,
    email_bounced_at REAL,
    password_reset_token TEXT, -- legacy plaintext token, cleared when hashed token is issued
    password_reset_expires REAL, -- legacy expiry paired with password_reset_token
    password_reset_token_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price_per_night REAL NOT NULL, -- Storing as generic price value
    price_period TEXT DEFAULT 'night', -- 'night' or 'month'
    compound TEXT NOT NULL,
    location_details TEXT,
    property_type TEXT NOT NULL DEFAULT 'House', -- House, Hotel, Villa, Guest House, Hostel
    listing_category TEXT DEFAULT 'rental',
    availability_status TEXT DEFAULT 'available',
    
    -- Specific Amenities
    bed_type TEXT, -- Single, Double, Bunk (primarily for hostels/guest houses)
    room_capacity INTEGER, -- Number of people per room
    bedrooms INTEGER DEFAULT 1,
    bathrooms INTEGER DEFAULT 1,
    kitchen_type TEXT, -- Private, Shared, None
    has_sitting_room BOOLEAN DEFAULT 0,
    
    -- Lusaka Essentials & Luxury
    has_solar BOOLEAN DEFAULT 0,
    has_borehole BOOLEAN DEFAULT 0,
    has_pool BOOLEAN DEFAULT 0,
    has_garden BOOLEAN DEFAULT 0,
    has_bbq BOOLEAN DEFAULT 0,
    has_balcony BOOLEAN DEFAULT 0,
    has_ac BOOLEAN DEFAULT 0,
    has_wifi BOOLEAN DEFAULT 0,
    has_parking BOOLEAN DEFAULT 0,
    
    -- Status & Verification
    is_verified BOOLEAN DEFAULT 0,
    is_featured BOOLEAN DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    latitude REAL,
    longitude REAL,

    image_main TEXT,
    agent_name TEXT,
    agent_phone TEXT,
    cancellation_policy TEXT DEFAULT 'moderate',
    house_rules TEXT,
    last_confirmed_at TIMESTAMP,
    cleaning_fee REAL NOT NULL DEFAULT 0,
    refundable_deposit REAL NOT NULL DEFAULT 0,
    utilities_included BOOLEAN NOT NULL DEFAULT 0,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    image_url TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    image_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (review_id) REFERENCES reviews (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    user_id INTEGER, -- Link to registered user
    tenant_name TEXT NOT NULL,
    tenant_phone TEXT NOT NULL,
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    total_price REAL NOT NULL,
    base_amount REAL NOT NULL DEFAULT 0,
    service_fee REAL NOT NULL DEFAULT 0,
    cleaning_fee REAL NOT NULL DEFAULT 0,
    refundable_deposit REAL NOT NULL DEFAULT 0,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, property_id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    property_id INTEGER,
    content TEXT NOT NULL,
    is_read BOOLEAN DEFAULT 0,
    parent_id INTEGER REFERENCES messages (id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users (id),
    FOREIGN KEY (receiver_id) REFERENCES users (id),
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

CREATE TABLE IF NOT EXISTS availability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    date DATE NOT NULL,
    status TEXT DEFAULT 'blocked', -- 'blocked', 'booked'
    UNIQUE(property_id, date),
    FOREIGN KEY (property_id) REFERENCES properties (id)
);

CREATE TABLE IF NOT EXISTS payout_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    provider TEXT NOT NULL, -- 'Bank Transfer', 'Mobile Money', 'Airtel Money', 'MTN Money'
    bank_name TEXT,
    account_name TEXT NOT NULL,
    account_number TEXT NOT NULL,
    branch_code TEXT,
    is_primary BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS saved_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    search_query TEXT,
    compound TEXT,
    min_price REAL,
    max_price REAL,
    property_type TEXT,
    power_backup TEXT,
    water_supply TEXT,
    near_lat REAL,
    near_lon REAL,
    near_radius_km REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS property_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    link TEXT,
    is_read BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS trip_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, source_name),
    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS calendar_import_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL,
    event_uid TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    FOREIGN KEY (import_id) REFERENCES calendar_imports(id) ON DELETE CASCADE,
    UNIQUE(import_id, event_uid)
);

CREATE TABLE IF NOT EXISTS seasonal_pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    price REAL,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL UNIQUE,
    owner_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reference TEXT,
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS email_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    provider_message_id TEXT,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    template_key TEXT,
    status TEXT NOT NULL DEFAULT 'accepted',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at REAL,
    delivered_at REAL,
    delayed_at REAL,
    bounced_at REAL,
    failed_at REAL,
    complained_at REAL,
    last_event_at REAL,
    failure_reason TEXT,
    UNIQUE(provider, provider_message_id)
);

CREATE TABLE IF NOT EXISTS email_webhook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    window_started REAL NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(action, rate_key)
);
