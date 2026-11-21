import tempfile
import unittest

from werkzeug.security import generate_password_hash

import app


class AdminDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database = app.DATABASE
        self.original_database_url = app.DATABASE_URL
        self.original_admin_emails = app.ADMIN_EMAILS
        app.DATABASE_URL = ''
        app.DATABASE = self.temp_dir.name + '/admin-test.db'
        app.ADMIN_EMAILS = set()
        app.init_db()
        app.app.config['TESTING'] = True

    def tearDown(self):
        app.DATABASE = self.original_database
        app.DATABASE_URL = self.original_database_url
        app.ADMIN_EMAILS = self.original_admin_emails
        self.temp_dir.cleanup()

    def create_user(self, full_name, email, phone, role='tenant', is_admin=0):
        with app.app.app_context():
            db = app.get_db()
            cursor = db.execute(
                '''INSERT INTO users (full_name, email, phone, password, role, is_admin)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (full_name, email, phone, generate_password_hash('Pass1234'), role, is_admin),
            )
            db.commit()
            return cursor.lastrowid

    def create_property(self, owner_id, title='Kabulonga Villa'):
        with app.app.app_context():
            db = app.get_db()
            cursor = db.execute(
                '''INSERT INTO properties (owner_id, title, description, price_per_night, compound, property_type)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (owner_id, title, 'Spacious home', 1200, 'Kabulonga', 'Villa'),
            )
            db.commit()
            return cursor.lastrowid

    def login_as(self, client, user_id):
        with client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['_csrf_token'] = 'admin-csrf'
        return 'admin-csrf'

    def test_admin_access_control(self):
        client = app.app.test_client()
        # Anonymous -> redirected to login
        anon_resp = client.get('/admin', follow_redirects=False)
        self.assertEqual(anon_resp.status_code, 302)
        self.assertTrue(anon_resp.headers['Location'].endswith('/login'))

        # Regular tenant -> redirected to tenant dashboard (not landing page)
        user_id = self.create_user('Normal User', 'normal@example.com', '+260971000001')
        self.login_as(client, user_id)
        non_admin_resp = client.get('/admin', follow_redirects=False)
        self.assertEqual(non_admin_resp.status_code, 302)
        self.assertTrue(non_admin_resp.headers['Location'].endswith('/tenant/dashboard'))

    def test_admin_dashboard_and_management_actions(self):
        admin_id = self.create_user('Site Admin', 'admin@example.com', '+260971000000', role='owner', is_admin=1)
        host_id = self.create_user('Host User', 'host@example.com', '+260971000002', role='owner', is_admin=0)
        prop_id = self.create_property(host_id, 'Woodlands Cottage')

        client = app.app.test_client()
        csrf = self.login_as(client, admin_id)

        # Dashboard renders all tabs & seeded records
        resp = client.get('/admin')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Admin Dashboard', resp.data)
        self.assertIn(b'Woodlands Cottage', resp.data)
        self.assertIn(b'Host User', resp.data)

        # Verify & unverify property
        self.assertEqual(client.post(f'/admin/verify_property/{prop_id}', data={'csrf_token': csrf}).status_code, 302)
        with app.app.app_context():
            is_verified = app.get_db().execute('SELECT is_verified FROM properties WHERE id = ?', (prop_id,)).fetchone()[0]
            self.assertEqual(is_verified, 1)

        self.assertEqual(client.post(f'/admin/unverify_property/{prop_id}', data={'csrf_token': csrf}).status_code, 302)
        with app.app.app_context():
            is_verified = app.get_db().execute('SELECT is_verified FROM properties WHERE id = ?', (prop_id,)).fetchone()[0]
            self.assertEqual(is_verified, 0)

        # Force delist & relist property
        self.assertEqual(client.post(f'/admin/force_delist/{prop_id}', data={'csrf_token': csrf}).status_code, 302)
        with app.app.app_context():
            is_active = app.get_db().execute('SELECT is_active FROM properties WHERE id = ?', (prop_id,)).fetchone()[0]
            self.assertEqual(is_active, 0)

        self.assertEqual(client.post(f'/admin/force_relist/{prop_id}', data={'csrf_token': csrf}).status_code, 302)
        with app.app.app_context():
            is_active = app.get_db().execute('SELECT is_active FROM properties WHERE id = ?', (prop_id,)).fetchone()[0]
            self.assertEqual(is_active, 1)

        # Grant & revoke admin on another user, while blocking self-demotion
        self.assertEqual(client.post(f'/admin/toggle_admin/{admin_id}', data={'csrf_token': csrf}).status_code, 302)
        with app.app.app_context():
            self.assertEqual(app.get_db().execute('SELECT is_admin FROM users WHERE id = ?', (admin_id,)).fetchone()[0], 1)

        self.assertEqual(client.post(f'/admin/toggle_admin/{host_id}', data={'csrf_token': csrf}).status_code, 302)
        with app.app.app_context():
            self.assertEqual(app.get_db().execute('SELECT is_admin FROM users WHERE id = ?', (host_id,)).fetchone()[0], 1)

        self.assertEqual(client.post(f'/admin/toggle_admin/{host_id}', data={'csrf_token': csrf}).status_code, 302)
        with app.app.app_context():
            self.assertEqual(app.get_db().execute('SELECT is_admin FROM users WHERE id = ?', (host_id,)).fetchone()[0], 0)

        # Ban & unban non-admin user
        self.assertEqual(client.post(f'/admin/ban_user/{host_id}', data={'csrf_token': csrf}).status_code, 302)
        with app.app.app_context():
            role = app.get_db().execute('SELECT role FROM users WHERE id = ?', (host_id,)).fetchone()[0]
            self.assertEqual(role, 'banned')

        self.assertEqual(client.post(f'/admin/unban_user/{host_id}', data={'csrf_token': csrf}).status_code, 302)
        with app.app.app_context():
            role = app.get_db().execute('SELECT role FROM users WHERE id = ?', (host_id,)).fetchone()[0]
            self.assertEqual(role, 'tenant')

    def test_admin_emails_env_auto_promotes_on_login(self):
        app.ADMIN_EMAILS = {'boss@example.com'}
        user_id = self.create_user('Boss User', 'boss@example.com', '+260971000009', role='owner', is_admin=0)
        client = app.app.test_client()
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'login-csrf'
        resp = client.post(
            '/login',
            data={'email': 'boss@example.com', 'password': 'Pass1234', 'csrf_token': 'login-csrf'},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers['Location'].endswith('/admin'))
        with app.app.app_context():
            is_admin = app.get_db().execute('SELECT is_admin FROM users WHERE id = ?', (user_id,)).fetchone()[0]
            self.assertEqual(is_admin, 1)
        self.assertEqual(client.get('/admin').status_code, 200)

    def test_admin_multipage_sections_and_account_settings(self):
        admin_id = self.create_user('Chief Admin', 'chief@example.com', '+260971000010', role='owner', is_admin=1)
        other_id = self.create_user('Other User', 'other@example.com', '+260971000011', role='tenant', is_admin=0)
        self.create_property(admin_id, 'Roma Penthouse')

        client = app.app.test_client()
        # Non-admin blocked on every dedicated admin page
        self.login_as(client, other_id)
        for path in (
            '/admin/listings', '/admin/bookings', '/admin/accounting',
            '/admin/users', '/admin/moderation', '/admin/audit', '/admin/settings',
        ):
            self.assertEqual(client.get(path, follow_redirects=False).status_code, 302)

        # Admin can open every dedicated page
        csrf = self.login_as(client, admin_id)
        expected_snippets = {
            '/admin': b'Admin Dashboard',
            '/admin/listings': b'Roma Penthouse',
            '/admin/bookings': b'Bookings Management',
            '/admin/accounting': b'Money &amp; Accounting',
            '/admin/users': b'Other User',
            '/admin/moderation': b'Moderation &amp; Support',
            '/admin/audit': b'Administrative Audit Log',
            '/admin/settings': b'Account &amp; Security Settings',
        }
        for path, snippet in expected_snippets.items():
            r = client.get(path)
            self.assertEqual(r.status_code, 200, f'Expected 200 on {path}')
            self.assertIn(snippet, r.data)

        # Changing email without correct current password must be rejected
        client.post('/admin/settings/profile', data={
            'full_name': 'Chief Admin',
            'email': 'newchief@example.com',
            'country_region': 'ZM',
            'phone': '+260971000010',
            'current_password': 'WrongPassword1',
            'csrf_token': csrf,
        })
        with app.app.app_context():
            email = app.get_db().execute('SELECT email FROM users WHERE id = ?', (admin_id,)).fetchone()[0]
            self.assertEqual(email, 'chief@example.com')

        # Changing name, email, and phone with correct password succeeds
        client.post('/admin/settings/profile', data={
            'full_name': 'Updated Admin',
            'email': 'newchief@example.com',
            'country_region': 'ZM',
            'phone': '971000099',
            'current_password': 'Pass1234',
            'csrf_token': csrf,
        })
        with app.app.app_context():
            row = app.get_db().execute('SELECT full_name, email, phone FROM users WHERE id = ?', (admin_id,)).fetchone()
            self.assertEqual(row['full_name'], 'Updated Admin')
            self.assertEqual(row['email'], 'newchief@example.com')
            self.assertEqual(row['phone'], '+260971000099')

        # Changing admin password via /admin/settings/password succeeds
        client.post('/admin/settings/password', data={
            'current_password': 'Pass1234',
            'new_password': 'NewAdminPass9',
            'confirm_password': 'NewAdminPass9',
            'csrf_token': csrf,
        })
        from werkzeug.security import check_password_hash
        with app.app.app_context():
            pw_hash = app.get_db().execute('SELECT password FROM users WHERE id = ?', (admin_id,)).fetchone()[0]
            self.assertTrue(check_password_hash(pw_hash, 'NewAdminPass9'))


if __name__ == '__main__':
    unittest.main()
