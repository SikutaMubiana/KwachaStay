import io
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app
from upload_storage import LocalUploadStorage


class AuthAndRoleSeparationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database = app.DATABASE
        self.original_database_url = app.DATABASE_URL
        self.original_provider = app.EMAIL_PROVIDER
        app.DATABASE_URL = ''
        app.DATABASE = self.temp_dir.name + '/auth-test.db'
        app.init_db()
        app.app.config['TESTING'] = True

    def tearDown(self):
        app.DATABASE = self.original_database
        app.DATABASE_URL = self.original_database_url
        app.EMAIL_PROVIDER = self.original_provider
        self.temp_dir.cleanup()

    def csrf(self, client):
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-csrf'
        return 'test-csrf'

    def test_brevo_is_removed(self):
        self.assertFalse(hasattr(app, 'BREVO_API_KEY'))
        self.assertFalse(hasattr(app, 'BREVO_SENDER_EMAIL'))
        self.assertFalse(hasattr(app, 'BREVO_WEBHOOK_TOKEN'))
        self.assertFalse(hasattr(app, '_send_brevo_email'))
        app.EMAIL_PROVIDER = 'brevo'
        self.assertFalse(app.email_delivery_configured())

        client = app.app.test_client()
        csrf = self.csrf(client)
        self.assertEqual(client.post('/webhooks/brevo', data={'csrf_token': csrf}).status_code, 404)
        self.assertEqual(client.get('/verify-contact').status_code, 404)

    def test_tenant_can_register_and_login_to_tenant_dashboard_only(self):
        client = app.app.test_client()
        csrf = self.csrf(client)
        with patch.object(app, 'send_email') as send_email_mock, patch.object(
            app, 'send_twilio_verification_sms'
        ) as send_sms_mock:
            signup_resp = client.post(
                '/signup',
                data={
                    'full_name': 'Chanda Renter',
                    'email': 'renter@example.com',
                    'country_code': '+260',
                    'phone': '971234567',
                    'password': 'Password123',
                    'role': 'tenant',
                    'csrf_token': csrf,
                },
                follow_redirects=False,
            )
            self.assertEqual(signup_resp.status_code, 302)
            self.assertTrue(signup_resp.headers['Location'].endswith('/login'))
            send_email_mock.assert_not_called()
            send_sms_mock.assert_not_called()

            csrf = self.csrf(client)
            login_resp = client.post(
                '/login',
                data={
                    'email': 'renter@example.com',
                    'password': 'Password123',
                    'csrf_token': csrf,
                },
                follow_redirects=False,
            )
            self.assertEqual(login_resp.status_code, 302)
            self.assertTrue(login_resp.headers['Location'].endswith('/tenant/dashboard'))
            send_email_mock.assert_not_called()
            send_sms_mock.assert_not_called()

        # /dashboard dispatches to /tenant/dashboard
        dispatch_resp = client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dispatch_resp.status_code, 302)
        self.assertTrue(dispatch_resp.headers['Location'].endswith('/tenant/dashboard'))

        dashboard_resp = client.get('/tenant/dashboard')
        self.assertEqual(dashboard_resp.status_code, 200)
        self.assertIn(b'Tenant Dashboard', dashboard_resp.data)
        self.assertIn(b'My Trips', dashboard_resp.data)
        self.assertNotIn(b'Incoming Bookings', dashboard_resp.data)

        # Tenant cannot access Landlord Dashboard or Add House (must create separate landlord account)
        landlord_dash_resp = client.get('/landlord/dashboard', follow_redirects=False)
        self.assertEqual(landlord_dash_resp.status_code, 302)
        self.assertTrue(landlord_dash_resp.headers['Location'].endswith('/tenant/dashboard'))

        add_house_resp = client.get('/add_house', follow_redirects=False)
        self.assertEqual(add_house_resp.status_code, 302)
        self.assertTrue(add_house_resp.headers['Location'].endswith('/tenant/dashboard'))

    def test_owner_can_register_and_login_to_landlord_dashboard_only(self):
        client = app.app.test_client()
        csrf = self.csrf(client)
        with patch.object(app, 'send_email') as send_email_mock, patch.object(
            app, 'send_twilio_verification_sms'
        ) as send_sms_mock:
            signup_resp = client.post(
                '/signup',
                data={
                    'full_name': 'Mulenga Host',
                    'email': 'host@example.com',
                    'country_code': '+260',
                    'phone': '961234567',
                    'password': 'HostPass123',
                    'role': 'owner',
                    'csrf_token': csrf,
                },
                follow_redirects=False,
            )
            self.assertEqual(signup_resp.status_code, 302)
            self.assertTrue(signup_resp.headers['Location'].endswith('/login'))
            send_email_mock.assert_not_called()
            send_sms_mock.assert_not_called()

            csrf = self.csrf(client)
            login_resp = client.post(
                '/login',
                data={
                    'email': 'host@example.com',
                    'password': 'HostPass123',
                    'csrf_token': csrf,
                },
                follow_redirects=False,
            )
            self.assertEqual(login_resp.status_code, 302)
            self.assertTrue(login_resp.headers['Location'].endswith('/landlord/dashboard'))
            send_email_mock.assert_not_called()
            send_sms_mock.assert_not_called()

        # /dashboard dispatches to /landlord/dashboard
        dispatch_resp = client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dispatch_resp.status_code, 302)
        self.assertTrue(dispatch_resp.headers['Location'].endswith('/landlord/dashboard'))

        dashboard_resp = client.get('/landlord/dashboard')
        self.assertEqual(dashboard_resp.status_code, 200)
        self.assertIn(b'Landlord Dashboard', dashboard_resp.data)
        self.assertIn(b'My Listings', dashboard_resp.data)
        self.assertIn(b'Incoming Bookings', dashboard_resp.data)
        self.assertNotIn(b'My Trips', dashboard_resp.data)

        add_house_resp = client.get('/add_house')
        self.assertEqual(add_house_resp.status_code, 200)

        # Landlord cannot access Tenant Dashboard or Tenant Checkout / Wishlist
        tenant_dash_resp = client.get('/tenant/dashboard', follow_redirects=False)
        self.assertEqual(tenant_dash_resp.status_code, 302)
        self.assertTrue(tenant_dash_resp.headers['Location'].endswith('/landlord/dashboard'))

        with app.app.app_context():
            db = app.get_db()
            owner_id = db.execute("SELECT id FROM users WHERE email = 'host@example.com'").fetchone()[0]
            prop_id = db.execute(
                '''INSERT INTO properties (owner_id, title, description, price_per_night, compound, property_type)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (owner_id, 'Test Home', 'Nice house', 500, 'Kabulonga', 'House'),
            ).lastrowid
            db.commit()

        checkout_resp = client.get(f'/checkout/{prop_id}', follow_redirects=False)
        self.assertEqual(checkout_resp.status_code, 302)
        self.assertTrue(checkout_resp.headers['Location'].endswith('/landlord/dashboard'))

        csrf = self.csrf(client)
        wishlist_resp = client.post(
            f'/toggle_wishlist/{prop_id}',
            headers={'X-CSRF-Token': csrf},
            follow_redirects=False,
        )
        self.assertEqual(wishlist_resp.status_code, 403)

        # Log out and log back in with phone number
        client.get('/logout')
        csrf = self.csrf(client)
        phone_login = client.post(
            '/login',
            data={
                'email': '+260961234567',
                'password': 'HostPass123',
                'csrf_token': csrf,
            },
            follow_redirects=False,
        )
        self.assertEqual(phone_login.status_code, 302)
        self.assertTrue(phone_login.headers['Location'].endswith('/landlord/dashboard'))

    def test_existing_unverified_user_can_login_directly(self):
        with app.app.app_context():
            db = app.get_db()
            db.execute(
                '''INSERT INTO users (full_name, email, phone, password, role, email_verified_at, phone_verified_at)
                   VALUES (?, ?, ?, ?, ?, NULL, NULL)''',
                ('Legacy User', 'legacy@example.com', '+260977777777', generate_password_hash('Legacy123'), 'owner'),
            )
            db.commit()

        client = app.app.test_client()
        csrf = self.csrf(client)
        resp = client.post(
            '/login',
            data={'email': 'LEGACY@EXAMPLE.COM', 'password': 'Legacy123', 'csrf_token': csrf},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers['Location'].endswith('/landlord/dashboard'))

    def test_landing_page_is_separated_from_all_dashboards(self):
        client = app.app.test_client()

        # Logged-out visitor sees the public landing page
        landing = client.get('/')
        self.assertEqual(landing.status_code, 200)
        self.assertIn(b'How KwachaStay Works', landing.data)

        with app.app.app_context():
            db = app.get_db()
            tenant_id = db.execute(
                '''INSERT INTO users (full_name, email, phone, password, role, is_admin)
                   VALUES (?, ?, ?, ?, 'tenant', 0)''',
                ('Tenant User', 't@example.com', '+260971000011', generate_password_hash('Pass1234')),
            ).lastrowid
            owner_id = db.execute(
                '''INSERT INTO users (full_name, email, phone, password, role, is_admin)
                   VALUES (?, ?, ?, ?, 'owner', 0)''',
                ('Owner User', 'o@example.com', '+260971000012', generate_password_hash('Pass1234')),
            ).lastrowid
            admin_id = db.execute(
                '''INSERT INTO users (full_name, email, phone, password, role, is_admin)
                   VALUES (?, ?, ?, ?, 'tenant', 1)''',
                ('Admin User', 'a@example.com', '+260971000013', generate_password_hash('Pass1234')),
            ).lastrowid
            db.commit()

        # 1. Tenant visiting / redirects to /tenant/dashboard and uses dashboard shell (no landing nav/hero)
        with client.session_transaction() as sess:
            sess['user_id'] = tenant_id
        r_tenant_root = client.get('/', follow_redirects=False)
        self.assertEqual(r_tenant_root.status_code, 302)
        self.assertTrue(r_tenant_root.headers['Location'].endswith('/tenant/dashboard'))

        r_tenant_dash = client.get('/tenant/dashboard')
        self.assertEqual(r_tenant_dash.status_code, 200)
        self.assertIn(b'Tenant Portal', r_tenant_dash.data)
        self.assertNotIn(b'Lusaka Areas', r_tenant_dash.data)
        self.assertNotIn(b'How KwachaStay Works', r_tenant_dash.data)

        r_stays = client.get('/stays')
        self.assertEqual(r_stays.status_code, 200)
        self.assertIn(b'Browse Stays', r_stays.data)
        self.assertNotIn(b'How KwachaStay Works', r_stays.data)
        self.assertNotIn(b'Lusaka Areas', r_stays.data)

        # 2. Landlord visiting / redirects to /landlord/dashboard and has no landing chrome
        with client.session_transaction() as sess:
            sess['user_id'] = owner_id
        r_owner_root = client.get('/', follow_redirects=False)
        self.assertEqual(r_owner_root.status_code, 302)
        self.assertTrue(r_owner_root.headers['Location'].endswith('/landlord/dashboard'))

        r_owner_dash = client.get('/landlord/dashboard')
        self.assertEqual(r_owner_dash.status_code, 200)
        self.assertIn(b'Landlord Portal', r_owner_dash.data)
        self.assertNotIn(b'Lusaka Areas', r_owner_dash.data)
        self.assertNotIn(b'How KwachaStay Works', r_owner_dash.data)

        # 3. Admin visiting / redirects to /admin and has no landing chrome
        with client.session_transaction() as sess:
            sess['user_id'] = admin_id
        r_admin_root = client.get('/', follow_redirects=False)
        self.assertEqual(r_admin_root.status_code, 302)
        self.assertTrue(r_admin_root.headers['Location'].endswith('/admin'))

        r_admin_dash = client.get('/admin')
        self.assertEqual(r_admin_dash.status_code, 200)
        self.assertIn(b'Admin Portal', r_admin_dash.data)
        self.assertNotIn(b'Lusaka Areas', r_admin_dash.data)
        self.assertNotIn(b'View Site', r_admin_dash.data)

    def test_landlord_can_upload_photo_and_list_property(self):
        original_storage = app.upload_storage
        original_backend = app.STORAGE_BACKEND
        original_enabled = app.app.config['UPLOADS_ENABLED']
        app.upload_storage = LocalUploadStorage(self.temp_dir.name)
        app.STORAGE_BACKEND = 'local'
        app.app.config['UPLOADS_ENABLED'] = True
        try:
            with app.app.app_context():
                db = app.get_db()
                owner_id = db.execute(
                    '''INSERT INTO users (full_name, email, phone, password, role)
                       VALUES (?, ?, ?, ?, 'owner')''',
                    ('Lister User', 'lister@example.com', '+260971000099', generate_password_hash('Pass1234')),
                ).lastrowid
                db.commit()

            client = app.app.test_client()
            with client.session_transaction() as sess:
                sess['user_id'] = owner_id
                sess['_csrf_token'] = 'upload-csrf'

            png_bytes = (
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0'
                b'\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82'
            )
            upload_resp = client.post(
                '/upload_image',
                data={'image': (io.BytesIO(png_bytes), 'house.png')},
                headers={'X-CSRF-Token': 'upload-csrf'},
                content_type='multipart/form-data',
            )
            self.assertEqual(upload_resp.status_code, 200)
            image_url = upload_resp.get_json()['url']

            add_resp = client.post(
                '/add_house',
                data={
                    'title': 'Ibex Hill Modern Home',
                    'description': 'Clean 3 bedroom house in Ibex Hill with solar backup and borehole water.',
                    'price': '2500',
                    'price_period': 'month',
                    'compound': 'Ibex Hill',
                    'property_type': 'House',
                    'bedrooms': '3',
                    'bathrooms': '2',
                    'image_url': image_url,
                    'main_photo_category': 'entrance',
                    'extra_images': image_url,
                    'extra_image_categories': 'bedroom',
                    'has_solar': 'on',
                    'csrf_token': 'upload-csrf',
                },
                follow_redirects=False,
            )
            self.assertEqual(add_resp.status_code, 302)
            self.assertTrue(add_resp.headers['Location'].endswith('/landlord/dashboard'))

            dash = client.get('/landlord/dashboard')
            self.assertEqual(dash.status_code, 200)
            self.assertIn(b'Ibex Hill Modern Home', dash.data)
        finally:
            app.upload_storage = original_storage
            app.STORAGE_BACKEND = original_backend
            app.app.config['UPLOADS_ENABLED'] = original_enabled


if __name__ == '__main__':
    unittest.main()
