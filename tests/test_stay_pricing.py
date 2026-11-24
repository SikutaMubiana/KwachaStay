import tempfile
import unittest
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

import app as kwachastay


class StayTypeAndPricingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database = kwachastay.DATABASE
        self.original_database_url = kwachastay.DATABASE_URL
        kwachastay.DATABASE_URL = ''
        kwachastay.DATABASE = self.temp_dir.name + '/stay-pricing-test.db'
        kwachastay.init_db()
        kwachastay.app.config['TESTING'] = True

        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            self.owner_id = db.execute(
                '''INSERT INTO users (full_name, email, phone, password, role, is_admin)
                   VALUES (?, ?, ?, ?, 'owner', 0)''',
                ('Host One', 'host@example.com', '+260971111111', generate_password_hash('StrongPass1!')),
            ).lastrowid
            self.tenant_id = db.execute(
                '''INSERT INTO users (full_name, email, phone, password, role, is_admin)
                   VALUES (?, ?, ?, ?, 'tenant', 0)''',
                ('Guest One', 'guest@example.com', '+260972222222', generate_password_hash('StrongPass1!')),
            ).lastrowid
            db.commit()
        self.client = kwachastay.app.test_client()

    def tearDown(self):
        kwachastay.DATABASE = self.original_database
        kwachastay.DATABASE_URL = self.original_database_url
        self.temp_dir.cleanup()

    def _login_as(self, user_id):
        with self.client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['session_version'] = 1
            sess['_csrf_token'] = 'stay-test-csrf'
        return 'stay-test-csrf'

    def test_house_and_hostel_do_not_require_daily_checkin_times(self):
        csrf = self._login_as(self.owner_id)

        for ptype, title in (('House', '3-Bed Family House'), ('Hostel', 'UNZA Student Hostel')):
            resp = self.client.post('/add_house', data={
                'csrf_token': csrf,
                'title': title,
                'description': 'Spacious long-term rental in Lusaka.',
                'property_type': ptype,
                'price_period': 'month',
                'price': '3500',
                'compound': 'Kabulonga',
                'room_capacity': '2',
                'checkin_time': '',
                'checkout_time': '',
                'image_url': 'https://example.com/property.jpg',
            }, follow_redirects=True)
            self.assertEqual(resp.status_code, 200)

        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            rows = db.execute(
                'SELECT title, property_type, price_period, checkin_time, checkout_time FROM properties ORDER BY id'
            ).fetchall()
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(row['price_period'], 'month')
                self.assertEqual(row['checkin_time'], '')
                self.assertEqual(row['checkout_time'], '')

    def test_hotel_nightly_multi_day_pricing_and_quote(self):
        csrf = self._login_as(self.owner_id)
        resp = self.client.post('/add_house', data={
            'csrf_token': csrf,
            'title': 'Rhodes Park Boutique Hotel',
            'description': 'Comfortable hotel rooms per night.',
            'property_type': 'Hotel',
            'price_period': 'night',
            'price': '100',
            'cleaning_fee': '25',
            'compound': 'Rhodes Park',
            'room_capacity': '2',
            'checkin_time': '14:00',
            'checkout_time': '11:00',
            'image_url': 'https://example.com/property.jpg',
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            prop = db.execute("SELECT * FROM properties WHERE title = 'Rhodes Park Boutique Hotel'").fetchone()
            self.assertIsNotNone(prop)
            self.assertEqual(prop['price_period'], 'night')
            self.assertEqual(prop['checkin_time'], '14:00')
            self.assertEqual(prop['checkout_time'], '11:00')
            prop_id = prop['id']

        self._login_as(self.tenant_id)
        check_in = (date.today() + timedelta(days=5)).isoformat()

        # 4 days at K100/night = K400 + K50 service fee + K25 cleaning fee = K475
        quote_resp = self.client.get(f'/property/{prop_id}/price-quote?check_in={check_in}&duration=4')
        self.assertEqual(quote_resp.status_code, 200)
        quote = quote_resp.get_json()
        self.assertEqual(quote['base_amount'], 400.0)
        self.assertEqual(quote['service_fee'], kwachastay.BOOKING_SERVICE_FEE)
        self.assertEqual(quote['cleaning_fee'], 25.0)
        self.assertEqual(quote['total_price'], 400.0 + kwachastay.BOOKING_SERVICE_FEE + 25.0)

        # 1 week (7 days) at K100/night = K700 + fees
        week_resp = self.client.get(f'/property/{prop_id}/price-quote?check_in={check_in}&duration=7')
        self.assertEqual(week_resp.status_code, 200)
        self.assertEqual(week_resp.get_json()['base_amount'], 700.0)

        # Checkout page renders presets (1 week, 1 month, custom) and carries ?duration=4
        page = self.client.get(f'/checkout/{prop_id}?duration=4')
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('1 Week (7 Days)', html)
        self.assertIn('1 Month (30 Days)', html)
        self.assertIn('value="4" selected', html)

        # Property details page shows quick stay estimator
        detail_page = self.client.get(f'/property/{prop_id}')
        self.assertEqual(detail_page.status_code, 200)
        detail_html = detail_page.get_data(as_text=True)
        self.assertIn('1 Week (7 Days)', detail_html)
        self.assertIn('Estimated total', detail_html)

    def test_monthly_house_supports_multi_year_checkout(self):
        csrf = self._login_as(self.owner_id)
        self.client.post('/add_house', data={
            'csrf_token': csrf,
            'title': 'Ibex Hill Executive House',
            'description': 'Long-term family home.',
            'property_type': 'House',
            'price_period': 'month',
            'price': '5000',
            'compound': 'Ibex Hill',
            'room_capacity': '4',
            'checkin_time': '',
            'checkout_time': '',
            'image_url': 'https://example.com/property.jpg',
        }, follow_redirects=True)

        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            prop_id = db.execute("SELECT id FROM properties WHERE title = 'Ibex Hill Executive House'").fetchone()['id']

        csrf = self._login_as(self.tenant_id)
        check_in = (date.today() + timedelta(days=10)).isoformat()

        # 3 years (36 months) at K5,000/month = K180,000 + service fee
        quote_resp = self.client.get(f'/property/{prop_id}/price-quote?check_in={check_in}&duration=36')
        self.assertEqual(quote_resp.status_code, 200)
        quote = quote_resp.get_json()
        self.assertEqual(quote['base_amount'], 180000.0)
        self.assertEqual(quote['total_price'], 180000.0 + kwachastay.BOOKING_SERVICE_FEE)

        # Checkout page hides daily hotel check-in times and shows multi-year options
        page = self.client.get(f'/checkout/{prop_id}')
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('Long-term stay (months / years)', html)
        self.assertIn('3 Years (36 Months)', html)
        self.assertNotIn('Check-in 15:00', html)

        # Submitting 36-month booking succeeds and calculates authoritative server total
        post_resp = self.client.post(f'/checkout/{prop_id}', data={
            'csrf_token': csrf,
            'check_in': check_in,
            'duration_val': '36',
            'tenant_name': 'Guest One',
            'tenant_phone': '+260972222222',
            'accept_policies': 'on',
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            booking = db.execute('SELECT * FROM bookings WHERE property_id = ?', (prop_id,)).fetchone()
            self.assertIsNotNone(booking)
            self.assertEqual(booking['duration'], 36)
            self.assertEqual(booking['duration_unit'], 'month')
            self.assertEqual(float(booking['base_amount']), 180000.0)
            self.assertEqual(float(booking['total_price']), 180000.0 + kwachastay.BOOKING_SERVICE_FEE)

    def test_automatic_location_google_maps_embed_and_geocode_api(self):
        # 1. Geocode API parses Google Maps URLs and Lusaka neighbourhoods directly
        maps_url = 'https://www.google.com/maps/@-15.4245,28.3525,17z'
        resp_url = self.client.get(f'/api/geocode?q={maps_url}')
        self.assertEqual(resp_url.status_code, 200)
        data_url = resp_url.get_json()
        self.assertAlmostEqual(data_url['latitude'], -15.4245, places=4)
        self.assertAlmostEqual(data_url['longitude'], 28.3525, places=4)

        resp_area = self.client.get('/api/geocode?q=Kabulonga')
        self.assertEqual(resp_area.status_code, 200)
        data_area = resp_area.get_json()
        self.assertEqual(data_area['compound'], 'Kabulonga')
        self.assertAlmostEqual(data_area['latitude'], kwachastay.LUSAKA_NEIGHBOURHOOD_COORDS['Kabulonga'][0], places=4)

        # 2. Listing without manual pin automatically centers on Kabulonga in Google Maps + Satellite + Nearby UI
        csrf = self._login_as(self.owner_id)
        self.client.post('/add_house', data={
            'csrf_token': csrf,
            'title': 'Kabulonga Garden Villa',
            'description': 'Luxury villa with swimming pool.',
            'property_type': 'Villa',
            'price_period': 'night',
            'price': '800',
            'compound': 'Kabulonga',
            'room_capacity': '4',
            'checkin_time': '15:00',
            'checkout_time': '10:00',
            'image_url': 'https://example.com/property.jpg',
        }, follow_redirects=True)

        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            prop_id = db.execute("SELECT id FROM properties WHERE title = 'Kabulonga Garden Villa'").fetchone()['id']

        detail = self.client.get(f'/property/{prop_id}')
        self.assertEqual(detail.status_code, 200)
        csp = detail.headers.get('Content-Security-Policy', '')
        self.assertIn('frame-src', csp)
        self.assertIn('https://maps.google.com', csp)
        html = detail.get_data(as_text=True)
        self.assertIn('https://maps.google.com/maps?q=', html)
        self.assertIn('Satellite View', html)
        self.assertIn('Explore nearby surroundings on Google Maps', html)
        self.assertIn('Google Street View', html)
        self.assertIn('How far from me?', html)
        self.assertIn(str(kwachastay.LUSAKA_NEIGHBOURHOOD_COORDS['Kabulonga'][0]), html)

    def test_boarding_house_room_sharing_wifi_and_upfront_months(self):
        csrf = self._login_as(self.owner_id)
        resp = self.client.post('/add_house', data={
            'csrf_token': csrf,
            'title': 'UNZA Campus Boarding House',
            'description': 'Clean student apartments near Great East Road.',
            'property_type': 'Boarding House',
            'room_sharing': 'shared',
            'room_capacity': '2',
            'price_period': 'month',
            'price': '1500',
            'upfront_months': '3',
            'has_wifi': 'on',
            'compound': 'Kalingalinga',
            'checkin_time': '',
            'checkout_time': '',
            'image_url': 'https://example.com/property.jpg',
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            prop = db.execute("SELECT * FROM properties WHERE title = 'UNZA Campus Boarding House'").fetchone()
            self.assertIsNotNone(prop)
            self.assertEqual(prop['property_type'], 'Boarding House')
            self.assertEqual(prop['room_sharing'], 'shared')
            self.assertEqual(int(prop['has_wifi']), 1)
            self.assertEqual(int(prop['upfront_months']), 3)
            prop_id = prop['id']

        detail = self.client.get(f'/property/{prop_id}')
        self.assertEqual(detail.status_code, 200)
        html = detail.get_data(as_text=True)
        self.assertIn('Shared Room', html)
        self.assertIn('WiFi Available', html)
        self.assertIn('3 Months Upfront Required', html)

        # Upfront minimum enforced: 1 month rejected, 3 months accepted
        self._login_as(self.tenant_id)
        check_in = (date.today() + timedelta(days=5)).isoformat()
        too_short = self.client.get(f'/property/{prop_id}/price-quote?check_in={check_in}&duration=1')
        self.assertEqual(too_short.status_code, 400)
        self.assertIn('3 months', too_short.get_json()['error'])

        valid_upfront = self.client.get(f'/property/{prop_id}/price-quote?check_in={check_in}&duration=3')
        self.assertEqual(valid_upfront.status_code, 200)
        self.assertEqual(valid_upfront.get_json()['base_amount'], 4500.0)

    def test_hotel_villa_hostel_hourly_booking_minimum_3_hours(self):
        csrf = self._login_as(self.owner_id)
        self.client.post('/add_house', data={
            'csrf_token': csrf,
            'title': 'Longacres City Hotel',
            'description': 'Flexible hours, days, and weeks.',
            'property_type': 'Hotel',
            'price_period': 'night',
            'price': '400',
            'hourly_rate': '60',
            'compound': 'Longacres',
            'room_capacity': '2',
            'checkin_time': '14:00',
            'checkout_time': '11:00',
            'image_url': 'https://example.com/property.jpg',
        }, follow_redirects=True)

        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            prop = db.execute("SELECT * FROM properties WHERE title = 'Longacres City Hotel'").fetchone()
            self.assertEqual(float(prop['hourly_rate']), 60.0)
            prop_id = prop['id']

        csrf = self._login_as(self.tenant_id)
        check_in = (date.today() + timedelta(days=4)).isoformat()

        # Less than 3 hours must be rejected
        too_short = self.client.get(f'/property/{prop_id}/price-quote?check_in={check_in}&unit=hour&duration=2')
        self.assertEqual(too_short.status_code, 400)

        # 3 hours at K60/hr = K180 + service fee
        three_hr = self.client.get(f'/property/{prop_id}/price-quote?check_in={check_in}&unit=hour&duration=3')
        self.assertEqual(three_hr.status_code, 200)
        q = three_hr.get_json()
        self.assertEqual(q['duration_unit'], 'hour')
        self.assertEqual(q['base_amount'], 180.0)
        self.assertEqual(q['total_price'], 180.0 + kwachastay.BOOKING_SERVICE_FEE)

        # Submitting a 4-hour booking saves duration=4, duration_unit='hour', base_amount=240
        post_resp = self.client.post(f'/checkout/{prop_id}', data={
            'csrf_token': csrf,
            'check_in': check_in,
            'duration_unit': 'hour',
            'duration_val': '4',
            'tenant_name': 'Guest One',
            'tenant_phone': '+260972222222',
            'accept_policies': 'on',
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            b = db.execute('SELECT * FROM bookings WHERE property_id = ?', (prop_id,)).fetchone()
            self.assertIsNotNone(b)
            self.assertEqual(b['duration'], 4)
            self.assertEqual(b['duration_unit'], 'hour')
            self.assertEqual(float(b['base_amount']), 240.0)
            self.assertEqual(float(b['total_price']), 240.0 + kwachastay.BOOKING_SERVICE_FEE)

    def test_zambia_multicity_essentials_boarding_details_and_viewing_flow(self):
        csrf = self._login_as(self.owner_id)
        # Create a Kitwe CBU Boarding House with full Zambia essentials & boarding details
        resp = self.client.post('/add_house', data={
            'csrf_token': csrf,
            'title': 'Riverside CBU Student Apartments',
            'description': 'Secure female-only student boarding house near Copperbelt University.',
            'property_type': 'Boarding House',
            'room_sharing': 'single',
            'room_capacity': '1',
            'boarding_gender': 'female',
            'nearby_university': 'Copperbelt University — CBU (Kitwe)',
            'campus_distance': 'walk_5',
            'gate_curfew_policy': '24h_access',
            'bed_spaces_left': '4',
            'semester_rate': '6500',
            'has_bed_mattress': 'on',
            'has_stove_fridge': 'on',
            'has_laundry_area': 'on',
            'has_study_desk': 'on',
            'has_study_backup_power': 'on',
            'city': 'Kitwe',
            'compound': 'Riverside',
            'price_period': 'month',
            'price': '1800',
            'upfront_months': '1',
            'furnishing_status': 'furnished',
            'master_self_contained': 'on',
            'zesco_meter_type': 'own',
            'security_fence': 'electric_fence',
            'listing_source': 'owner',
            'viewing_fee': '0',
            'has_wifi': 'on',
            'checkin_time': '',
            'checkout_time': '',
            'image_url': 'https://example.com/property.jpg',
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            prop = db.execute("SELECT * FROM properties WHERE title = 'Riverside CBU Student Apartments'").fetchone()
            self.assertIsNotNone(prop)
            self.assertEqual(prop['city'], 'Kitwe')
            self.assertEqual(prop['furnishing_status'], 'furnished')
            self.assertEqual(int(prop['master_self_contained']), 1)
            self.assertEqual(prop['zesco_meter_type'], 'own')
            self.assertEqual(prop['security_fence'], 'electric_fence')
            self.assertEqual(prop['boarding_gender'], 'female')
            self.assertEqual(int(prop['bed_spaces_left']), 4)
            self.assertEqual(float(prop['semester_rate']), 6500.0)
            prop_id = prop['id']

        # Filter by city=Kitwe, campus_distance=walk_5, gate_curfew_policy=24h_access, has_study_backup_power=1 (as tenant on /stays)
        tenant_csrf = self._login_as(self.tenant_id)
        browse_hit = self.client.get(
            '/stays?city=Kitwe&zesco_meter_type=own&master_self_contained=1&furnishing_status=furnished'
            '&campus_distance=walk_5&gate_curfew_policy=24h_access&has_study_backup_power=1&has_study_desk=1'
        )
        self.assertEqual(browse_hit.status_code, 200)
        self.assertIn('Riverside CBU Student Apartments', browse_hit.get_data(as_text=True))

        browse_miss = self.client.get('/stays?city=Livingstone')
        self.assertEqual(browse_miss.status_code, 200)
        self.assertNotIn('Riverside CBU Student Apartments', browse_miss.get_data(as_text=True))

        # Property details displays all badges, boarding details, student amenities, and viewing button
        detail = self.client.get(f'/property/{prop_id}')
        html = detail.get_data(as_text=True)
        self.assertIn('Riverside, Kitwe', html)
        self.assertIn('Female Only', html)
        self.assertIn('Walking distance (under 5 min)', html)
        self.assertIn('24-Hour Gate Access (No Curfew)', html)
        self.assertIn('4 bed spaces left', html)
        self.assertIn('ZMW 6,500 / semester', html)
        self.assertIn('Bed &amp; Mattress Provided', html)
        self.assertIn('Stove &amp; Fridge Access', html)
        self.assertIn('Laundry Area', html)
        self.assertIn('Study Desk / Quiet Study Area', html)
        self.assertIn('Backup Solar / Inverter for Study Lights &amp; Laptop Charging', html)
        self.assertIn('Master Self-Contained (MSC)', html)
        self.assertIn('Own ZESCO Prepaid Meter', html)
        self.assertIn('Wall + Electric Fence', html)
        self.assertIn('Direct Owner (No Agent Fee)', html)
        self.assertIn('Book a Physical Viewing', html)

        # Tenant schedules a physical viewing
        visit_date = (date.today() + timedelta(days=3)).isoformat()
        v_resp = self.client.post(f'/property/{prop_id}/request-viewing', data={
            'csrf_token': tenant_csrf,
            'viewing_date': visit_date,
            'viewing_time': '10:00',
            'visitor_name': 'Guest One',
            'visitor_phone': '+260972222222',
            'notes': 'Coming with my parent to inspect the room.',
        }, follow_redirects=False)
        self.assertEqual(v_resp.status_code, 302)

        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            viewing = db.execute('SELECT * FROM property_viewings WHERE property_id = ?', (prop_id,)).fetchone()
            self.assertIsNotNone(viewing)
            self.assertEqual(viewing['status'], 'pending')
            viewing_id = viewing['id']

        # Landlord sees viewing request & confirms it
        owner_csrf = self._login_as(self.owner_id)
        ldash = self.client.get('/landlord/dashboard')
        self.assertIn('Riverside CBU Student Apartments', ldash.get_data(as_text=True))
        self.assertIn('Coming with my parent to inspect the room.', ldash.get_data(as_text=True))

        confirm_resp = self.client.post(f'/viewing/{viewing_id}/update', data={
            'csrf_token': owner_csrf,
            'status': 'confirmed',
            'owner_response_note': 'See you at the main gate at 10:00.',
        }, follow_redirects=False)
        self.assertEqual(confirm_resp.status_code, 302)

        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            updated = db.execute('SELECT status, owner_response_note FROM property_viewings WHERE id = ?', (viewing_id,)).fetchone()
            self.assertEqual(updated['status'], 'confirmed')
            self.assertIn('main gate', updated['owner_response_note'])

        # Tenant sees confirmed viewing with host phone in Tenant Dashboard, then cancels
        tenant_csrf = self._login_as(self.tenant_id)
        tdash = self.client.get('/tenant/dashboard')
        tdash_html = tdash.get_data(as_text=True)
        self.assertIn('My Scheduled Viewings', tdash_html)
        self.assertIn('+260971111111', tdash_html)

        cancel_resp = self.client.post(f'/viewing/{viewing_id}/cancel', data={'csrf_token': tenant_csrf}, follow_redirects=False)
        self.assertEqual(cancel_resp.status_code, 302)
        with kwachastay.app.app_context():
            status_after = kwachastay.get_db().execute('SELECT status FROM property_viewings WHERE id = ?', (viewing_id,)).fetchone()['status']
            self.assertEqual(status_after, 'cancelled')

    def test_family_yard_water_couples_privacy_landmarks_and_group_split_estimator(self):
        csrf = self._login_as(self.owner_id)
        resp = self.client.post('/add_house', data={
            'csrf_token': csrf,
            'title': 'Kabulonga Executive Pool Villa',
            'description': 'Private villa ideal for couples, families, or friend getaways.',
            'property_type': 'Villa',
            'price_period': 'night',
            'price': '2400',
            'hourly_rate': '350',
            'city': 'Lusaka',
            'compound': 'Kabulonga',
            'room_capacity': '6',
            'water_supply': 'borehole_solar_pump',
            'yard_type': 'own_yard',
            'has_paved_yard': 'on',
            'is_family_friendly': 'on',
            'is_pet_friendly': 'on',
            'has_private_entrance': 'on',
            'couples_friendly': 'on',
            'has_smart_tv': 'on',
            'allows_small_gatherings': 'on',
            'offers_airport_transfer': 'on',
            'checkin_time': '15:00',
            'checkout_time': '10:00',
            'image_url': 'https://example.com/property.jpg',
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with kwachastay.app.app_context():
            prop = kwachastay.get_db().execute(
                "SELECT * FROM properties WHERE title = 'Kabulonga Executive Pool Villa'"
            ).fetchone()
            self.assertIsNotNone(prop)
            self.assertEqual(prop['water_supply'], 'borehole_solar_pump')
            self.assertEqual(prop['yard_type'], 'own_yard')
            self.assertEqual(int(prop['has_paved_yard']), 1)
            self.assertEqual(int(prop['has_private_entrance']), 1)
            self.assertEqual(int(prop['couples_friendly']), 1)
            self.assertEqual(int(prop['has_smart_tv']), 1)
            self.assertEqual(int(prop['allows_small_gatherings']), 1)
            self.assertEqual(int(prop['offers_airport_transfer']), 1)
            prop_id = prop['id']

        self._login_as(self.tenant_id)
        # Filter by yard_type=own_yard
        filtered = self.client.get('/stays?yard_type=own_yard')
        self.assertIn('Kabulonga Executive Pool Villa', filtered.get_data(as_text=True))

        # Property details displays family/yard tags, couples/privacy/group tags, automatic KKIA landmarks, and split estimator
        detail_html = self.client.get(f'/property/{prop_id}').get_data(as_text=True)
        self.assertIn('Own Private Yard', detail_html)
        self.assertIn('Paved Yard', detail_html)
        self.assertIn('Kids / Family-Friendly', detail_html)
        self.assertIn('Pet-Friendly', detail_html)
        self.assertIn('Private Entrance / Discreet Access', detail_html)
        self.assertIn('Couples Welcome / Discreet Parking', detail_html)
        self.assertIn('Smart TV (Netflix) / DSTV', detail_html)
        self.assertIn('Small Gatherings / Braai (BBQ) Allowed', detail_html)
        self.assertIn('Airport Transfer Available', detail_html)
        self.assertIn('KKIA Airport', detail_html)
        self.assertIn('Split cost (friends / group)', detail_html)

        # Checkout also displays the group split-cost estimator
        checkout_html = self.client.get(f'/checkout/{prop_id}').get_data(as_text=True)
        self.assertIn('Split cost with friends / group', checkout_html)

    def test_zambia_city_neighbourhood_cascade_and_apartment_listing(self):
        # Verify all 7 Zambian cities & recognizable neighbourhoods are configured
        for city, expected_areas in (
            ('Kitwe', ('Riverside', 'Parklands', 'Nkana East', 'Nkana West')),
            ('Ndola', ('Kansenshi', 'Northrise', 'Itawa')),
            ('Kabwe', ('Highridge', 'Mulungushi', 'Bwacha')),
            ('Livingstone', ('Highlands', 'Dambwa North', 'Maramba')),
            ('Chipata', ('Kanjala', 'Kapata', 'Magazine')),
            ('Solwezi', ('Kimasala', 'Mushitala', 'Kyawama')),
            ('Lusaka', ('Kabulonga', 'Ibex Hill', 'Rhodes Park')),
        ):
            self.assertIn(city, kwachastay.ZAMBIA_CITIES)
            for area in expected_areas:
                self.assertIn(area, kwachastay.ZAMBIA_CITY_NEIGHBOURHOODS[city])

        # Public landing page shows guided 3-step finder (City -> Neighbourhood -> Property Type)
        landing_html = ' '.join(self.client.get('/').get_data(as_text=True).split())
        self.assertIn('1. Select City', landing_html)
        self.assertIn('2. Select Neighbourhood', landing_html)
        self.assertIn('3. Property Type', landing_html)
        self.assertIn('Kitwe', landing_html)
        self.assertIn('Nkana East', landing_html)

        # Listing an Apartment in Nkana East, Kitwe defaults cleanly to monthly
        csrf = self._login_as(self.owner_id)
        resp = self.client.post('/add_house', data={
            'csrf_token': csrf,
            'city': 'Kitwe',
            'compound': 'Nkana East',
            'property_type': 'Apartment',
            'title': 'Nkana East 2-Bed Modern Apartment',
            'description': 'Clean apartment in Nkana East, Kitwe.',
            'price': '4200',
            'price_period': 'month',
            'room_capacity': '2',
            'checkin_time': '',
            'checkout_time': '',
            'image_url': 'https://example.com/property.jpg',
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with kwachastay.app.app_context():
            row = kwachastay.get_db().execute(
                "SELECT city, compound, property_type, price_period FROM properties WHERE title = 'Nkana East 2-Bed Modern Apartment'"
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['city'], 'Kitwe')
            self.assertEqual(row['compound'], 'Nkana East')
            self.assertEqual(row['property_type'], 'Apartment')
            self.assertEqual(row['price_period'], 'month')

    def test_active_availability_check_stale_hiding_and_video_walkthrough(self):
        csrf = self._login_as(self.owner_id)
        # 1. Unsafe javascript: video URL is rejected
        bad_resp = self.client.post('/add_house', data={
            'csrf_token': csrf,
            'city': 'Lusaka',
            'compound': 'Chalala',
            'property_type': 'House',
            'title': 'Bad Video House',
            'description': 'Should fail video URL check.',
            'price': '3000',
            'price_period': 'month',
            'video_tour_url': 'javascript:alert(1)',
            'image_url': 'https://example.com/property.jpg',
        }, follow_redirects=True)
        self.assertEqual(bad_resp.status_code, 200)
        with kwachastay.app.app_context():
            self.assertIsNone(
                kwachastay.get_db().execute("SELECT id FROM properties WHERE title = 'Bad Video House'").fetchone()
            )

        # 2. Valid YouTube Shorts walkthrough saves & renders privacy-enhanced embed
        ok_resp = self.client.post('/add_house', data={
            'csrf_token': csrf,
            'city': 'Lusaka',
            'compound': 'Chalala',
            'property_type': 'House',
            'title': 'Chalala Walkthrough Home',
            'description': 'Modern 3 bedroom home with video tour.',
            'price': '4500',
            'price_period': 'month',
            'video_tour_url': 'https://www.youtube.com/shorts/dQw4w9WgXcQ',
            'image_url': 'https://example.com/property.jpg',
        }, follow_redirects=True)
        self.assertEqual(ok_resp.status_code, 200)

        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            prop_id = db.execute("SELECT id FROM properties WHERE title = 'Chalala Walkthrough Home'").fetchone()['id']

        detail = self.client.get(f'/property/{prop_id}')
        self.assertIn('https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ', detail.get_data(as_text=True))
        self.assertIn('https://www.youtube-nocookie.com', detail.headers.get('Content-Security-Policy', ''))

        # 3. Listing unconfirmed for 16 days triggers landlord prompt banner but stays visible
        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            db.execute(
                "UPDATE properties SET last_confirmed_at = datetime('now', '-16 days') WHERE id = ?",
                (prop_id,),
            )
            db.commit()
            kwachastay.sweep_stale_availability_checks(db, force=True)

        ldash = self.client.get('/landlord/dashboard').get_data(as_text=True)
        self.assertIn('Active Availability Check', ldash)
        self.assertIn('Yes, Still Available', ldash)

        # 4. Listing unconfirmed for 35 days is auto-hidden from search as stale_unconfirmed
        with kwachastay.app.app_context():
            db = kwachastay.get_db()
            db.execute(
                "UPDATE properties SET last_confirmed_at = datetime('now', '-35 days') WHERE id = ?",
                (prop_id,),
            )
            db.commit()
            kwachastay.sweep_stale_availability_checks(db, force=True)
            status = db.execute('SELECT availability_status FROM properties WHERE id = ?', (prop_id,)).fetchone()['availability_status']
            self.assertEqual(status, 'stale_unconfirmed')

        self._login_as(self.tenant_id)
        stays_hidden = self.client.get('/stays').get_data(as_text=True)
        self.assertNotIn('Chalala Walkthrough Home', stays_hidden)

        # 5. Landlord confirms "Yes, Still Available" -> immediately visible again!
        owner_csrf = self._login_as(self.owner_id)
        confirm = self.client.post(f'/property/{prop_id}/confirm-details', data={'csrf_token': owner_csrf}, follow_redirects=False)
        self.assertEqual(confirm.status_code, 302)

        self._login_as(self.tenant_id)
        stays_restored = self.client.get('/stays').get_data(as_text=True)
        self.assertIn('Chalala Walkthrough Home', stays_restored)

    def test_seven_city_launch_positioning_and_strict_city_validation(self):
        expected_cities = ['Lusaka', 'Kitwe', 'Livingstone', 'Kabwe', 'Solwezi', 'Chipata', 'Ndola']
        self.assertEqual(set(kwachastay.ZAMBIA_CITIES), set(expected_cities))
        self.assertEqual(len(kwachastay.ZAMBIA_CITIES), 7)

        # 1. Homepage messaging & 7-city positioning (no Lusaka-only copy)
        home = self.client.get('/')
        self.assertEqual(home.status_code, 200)
        home_html = home.get_data(as_text=True)
        self.assertIn('Find Your Next Home', home_html)
        self.assertIn('Across Zambia.', home_html)
        self.assertIn('Discover houses, apartments, hostels, hotels, villas and short-term accommodation across Zambia’s major cities.', home_html)
        self.assertIn('Explore Properties Across Our Cities.', home_html)
        self.assertIn('List Your Property on KwachaStay.', home_html)
        self.assertIn('Your trusted marketplace for discovering and listing properties across Zambia.', home_html)
        self.assertNotIn('Made for Lusaka', home_html)
        self.assertNotIn('Lusaka Areas', home_html)
        self.assertNotIn('Have a property in Lusaka?', home_html)
        for city in expected_cities:
            self.assertIn(city, home_html)

        # 2. /areas, /cities, and /about pages reflect 7-city positioning
        for path in ('/areas', '/cities'):
            r_cities = self.client.get(path)
            self.assertEqual(r_cities.status_code, 200)
            cities_html = r_cities.get_data(as_text=True)
            self.assertIn('Explore Properties Across Our Cities.', cities_html)
            for city in expected_cities:
                self.assertIn(city, cities_html)

        r_about = self.client.get('/about')
        self.assertEqual(r_about.status_code, 200)
        about_html = r_about.get_data(as_text=True)
        self.assertIn('KwachaStay is a Zambian property marketplace connecting property seekers, landlords, real estate agents, property managers, hotels and accommodation providers across multiple major cities in Zambia.', about_html)
        self.assertNotIn('Lusaka, Zambia only', about_html)

        # 3. Registration recognizes all 7 launch cities and rejects unsupported cities
        r_signup_get = self.client.get('/signup')
        self.assertEqual(r_signup_get.status_code, 200)
        signup_html = r_signup_get.get_data(as_text=True)
        for city in expected_cities:
            self.assertIn(f'value="{city}"', signup_html)
        with self.client.session_transaction() as sess:
            signup_csrf = sess.get('_csrf_token')

        bad_signup = self.client.post('/signup', data={
            'csrf_token': signup_csrf,
            'full_name': 'Unsupported City User',
            'email': 'unsupported-city@example.com',
            'country_code': '+260',
            'phone': '971112233',
            'password': 'Password123',
            'role': 'tenant',
            'preferred_city': 'Kasama',
        }, follow_redirects=True)
        self.assertIn('seven Zambian cities', bad_signup.get_data(as_text=True))
        with kwachastay.app.app_context():
            self.assertIsNone(
                kwachastay.get_db().execute("SELECT id FROM users WHERE email = 'unsupported-city@example.com'").fetchone()
            )

        ok_signup = self.client.post('/signup', data={
            'csrf_token': signup_csrf,
            'full_name': 'Solwezi Member',
            'email': 'solwezi-member@example.com',
            'country_code': '+260',
            'phone': '971112244',
            'password': 'Password123',
            'role': 'tenant',
            'preferred_city': 'Solwezi',
        }, follow_redirects=False)
        self.assertEqual(ok_signup.status_code, 302)
        with kwachastay.app.app_context():
            u = kwachastay.get_db().execute(
                "SELECT preferred_city FROM users WHERE email = 'solwezi-member@example.com'"
            ).fetchone()
            self.assertIsNotNone(u)
            self.assertEqual(u['preferred_city'], 'Solwezi')

        # 4. Property submission rejects unsupported cities & works across all 7 launch cities
        owner_csrf = self._login_as(self.owner_id)
        add_get = self.client.get('/add_house').get_data(as_text=True)
        self.assertIn('List Your Property on KwachaStay.', add_get)
        self.assertNotIn('Lusaka Essentials (Critical)', add_get)

        bad_city_prop = self.client.post('/add_house', data={
            'csrf_token': owner_csrf,
            'city': 'Chingola',
            'compound': 'Nchanga',
            'property_type': 'House',
            'title': 'Unsupported Chingola Home',
            'description': 'Should be rejected.',
            'price': '3000',
            'price_period': 'month',
            'image_url': 'https://example.com/property.jpg',
        }, follow_redirects=True)
        self.assertIn('seven Zambian cities', bad_city_prop.get_data(as_text=True))
        with kwachastay.app.app_context():
            self.assertIsNone(
                kwachastay.get_db().execute("SELECT id FROM properties WHERE title = 'Unsupported Chingola Home'").fetchone()
            )

        city_samples = [
            ('Lusaka', 'Kabulonga'),
            ('Kitwe', 'Riverside'),
            ('Livingstone', 'Highlands'),
            ('Kabwe', 'Highridge'),
            ('Solwezi', 'Kimasala'),
            ('Chipata', 'Kanjala'),
            ('Ndola', 'Kansenshi'),
        ]
        created_ids = {}
        for city, area in city_samples:
            resp = self.client.post('/add_house', data={
                'csrf_token': owner_csrf,
                'city': city,
                'compound': area,
                'property_type': 'House',
                'title': f'{city} Launch Home',
                'description': f'Quality property in {area}, {city}.',
                'price': '4000',
                'price_period': 'month',
                'image_url': 'https://example.com/property.jpg',
            }, follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            with kwachastay.app.app_context():
                row = kwachastay.get_db().execute(
                    'SELECT id, city, compound FROM properties WHERE title = ?',
                    (f'{city} Launch Home',),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row['city'], city)
                self.assertEqual(row['compound'], area)
                created_ids[city] = row['id']

        # 5. Public search filters each of the 7 cities cleanly & detail page renders true city
        self.client.post('/logout', data={'csrf_token': owner_csrf})
        for city, area in city_samples:
            r_city = self.client.get(f'/?city={city}')
            self.assertEqual(r_city.status_code, 200)
            body = r_city.get_data(as_text=True)
            self.assertIn(f'{city} Launch Home', body)
            for other_city, _ in city_samples:
                if other_city != city:
                    self.assertNotIn(f'{other_city} Launch Home', body)

            detail = self.client.get(f'/property/{created_ids[city]}').get_data(as_text=True)
            self.assertIn(f'{area}, {city}, Zambia', detail)

        # 6. Geocode API recognizes non-Lusaka launch cities
        for city in ('Livingstone', 'Solwezi', 'Chipata', 'Kabwe', 'Kitwe', 'Ndola'):
            geo = self.client.get(f'/api/geocode?q={city}')
            self.assertEqual(geo.status_code, 200)
            payload = geo.get_json()
            self.assertEqual(payload['city'], city)


if __name__ == '__main__':
    unittest.main()
