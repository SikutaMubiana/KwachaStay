import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app


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


if __name__ == '__main__':
    unittest.main()
