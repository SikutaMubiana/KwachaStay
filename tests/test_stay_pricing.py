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


if __name__ == '__main__':
    unittest.main()
